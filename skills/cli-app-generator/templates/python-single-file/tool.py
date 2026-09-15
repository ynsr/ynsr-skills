#!/usr/bin/env python3
"""<tool> — one-line description.

Single-file Python CLI. Layout mirrors mbapi (metabase-api-cli):
constants → profile store (0600 JSON) → requests.Session with retries →
domain API functions → Typer commands → main().

Deps: typer, rich, requests (extras per target API). Run with `uv run <tool> …`
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import NoReturn, Optional

import requests
import typer

# --- constants ---------------------------------------------------------------

VERSION = "0.1.0"
CONFIG_DIR = Path(os.environ.get("MYCLI_CONFIG_DIR", Path.home() / ".config" / "mycli"))
PROFILES_DIR = CONFIG_DIR / "profiles"
BASE_URL = os.environ.get("MYCLI_URL", "https://api.example.com")
TIMEOUT = int(os.environ.get("MYCLI_TIMEOUT", "30"))
RETRY_BACKOFF = 2.0

EXIT_OK, EXIT_GENERAL, EXIT_USAGE, EXIT_NETWORK = 0, 1, 2, 3

# --- profile store (0600 JSON files; secrets never in flags/logs) ------------


def _profile_path(name: str) -> Path:
    return PROFILES_DIR / f"{name}.json"


def save_profile(name: str, data: dict) -> Path:
    """Atomically write a 0600 profile file."""
    _profile_path(name).parent.mkdir(parents=True, exist_ok=True)
    tmp = _profile_path(f".{name}.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    tmp.chmod(0o600)
    tmp.replace(_profile_path(name))
    return _profile_path(name)


def load_profile(name: str) -> dict:
    return json.loads(_profile_path(name).read_text())

def list_profiles() -> list[str]:
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json")) if PROFILES_DIR.is_dir() else []


# --- shell completion (single system: `completions show|install`) -------------
# Subcommand names + -/-- flags complete via Click automatically; only dynamic
# values need an autocompletion= callback (fast, offline, never raise).

PROG = "<tool>"  # rename with the tool; used in markers + eval lines
SUPPORTED_SHELLS = ("bash", "zsh", "fish")
_RC_FILES = {"bash": "~/.bashrc", "zsh": "~/.zshrc", "fish": "~/.config/fish/config.fish"}


def _complete_profiles(ctx, incomplete: str) -> list[str]:
    try:
        names = list_profiles()
    except Exception:
        return []
    return sorted(n for n in names if n.startswith(incomplete))


def _detect_shell() -> Optional[str]:
    shell = os.path.basename(os.environ.get("SHELL", "")).strip()
    return shell if shell in SUPPORTED_SHELLS else None


def _eval_line(shell: str) -> str:
    if shell == "fish":
        return f"{PROG} completions show fish | source"
    return f'eval "$({PROG} completions show {shell})"'


def _install_snippet(shell: str) -> str:
    lines = [f"# >>> {PROG} completions >>>"]
    if shell == "zsh":
        lines.append(f"autoload -U compinit && compinit  # required for completion (added by {PROG})")
    lines.append(_eval_line(shell))
    lines.append(f"# <<< {PROG} completions <<<")
    return "\n".join(lines) + "\n"


def _install_completion(shell: str, rcfile: Optional[Path] = None) -> tuple[Path, bool]:
    """Idempotent rc edit: (rc path, changed). Atomic write, .bak backup."""
    if shell not in SUPPORTED_SHELLS:
        _fail(f"unsupported shell {shell!r} (choose from: {', '.join(SUPPORTED_SHELLS)})", EXIT_USAGE)
    rc = Path(rcfile).expanduser() if rcfile else Path(_RC_FILES[shell]).expanduser()
    snippet = _install_snippet(shell)
    existing = rc.read_text(encoding="utf-8") if rc.is_file() else ""
    if snippet.strip() in existing:
        return rc, False
    pattern = re.compile(f"# >>> {re.escape(PROG)} completions >>>.*?# <<< {re.escape(PROG)} completions <<<\\n?", re.DOTALL)
    updated = pattern.sub(snippet, existing) if pattern.search(existing) else existing + ("" if not existing or existing.endswith("\n") else "\n") + ("\n" if existing else "") + snippet
    rc.parent.mkdir(parents=True, exist_ok=True)
    if rc.is_file():
        import shutil
        shutil.copy2(rc, rc.parent / (rc.name + ".bak"))
    tmp = rc.parent / (rc.name + ".tmp")
    tmp.write_text(updated, encoding="utf-8")
    tmp.replace(rc)
    return rc, True
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json")) if PROFILES_DIR.is_dir() else []


# --- HTTP session ------------------------------------------------------------


def make_session(token: str) -> requests.Session:
    """Session with retries on 5xx/timeouts; base headers + auth."""
    s = requests.Session()
    retries = requests.packages.urllib3.util.retry.Retry(   # type: ignore[attr-defined]
        total=3, backoff_factor=RETRY_BACKOFF,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST", "PUT", "DELETE"}),
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retries)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


def api_get(session: requests.Session, path: str, params: dict | None = None) -> dict:
    """GET + raise SystemExit(EXIT_NETWORK/EXIT_GENERAL) on failure."""
    try:
        resp = session.get(f"{BASE_URL}{path}", params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        print(f"error: request timed out after {TIMEOUT}s", file=sys.stderr)
        sys.exit(EXIT_NETWORK)
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        print(f"error: HTTP {status}: {exc}", file=sys.stderr)
        sys.exit(EXIT_GENERAL)


# --- domain API functions (thin; keep logic here, not in commands) -----------


def fetch_items(session, resource: str) -> list[dict]:
    return api_get(session, f"/{resource}").get("items", [])


# --- Typer commands ----------------------------------------------------------

app = typer.Typer(
    help="<tool> — one-line description.",
    no_args_is_help=True,
    add_completion=False,  # single completion system: `completions show|install` below
    context_settings={"help_option_names": ["-h", "--help"]},
    pretty_exceptions_enable=False,
)


def _fail(msg: str, code: int) -> NoReturn:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def _get_session(profile_name: str | None) -> tuple[requests.Session, dict]:
    name = profile_name or os.environ.get("MYCLI_PROFILE") or "default"
    try:
        prof = load_profile(name)
    except FileNotFoundError:
        _fail(f"profile '{name}' not found; create it with: <tool> profile create {name}", EXIT_USAGE)
    return make_session(prof["token"]), prof


@app.command()
def items(
    resource: str = typer.Argument(..., help="Resource to fetch."),
    json_output: bool = typer.Option(False, "--json", help="JSON instead of CSV."),
    profile_name: str = typer.Option(None, "--profile", "-p", envvar="MYCLI_PROFILE", autocompletion=_complete_profiles, help="Auth profile."),
) -> None:
    """Fetch items (CSV with headers by default; --json for jq).

    Example:
      <tool> items widgets
      <tool> items widgets --json | jq '.[0]'
    """
    session, _ = _get_session(profile_name)
    rows = fetch_items(session, resource)
    if json_output:
        print(json.dumps(rows, indent=2))
        return
    import csv
    if not rows:
        return
    keys = list(rows[0].keys())
    w = csv.writer(sys.stdout)
    w.writerow(keys)
    for r in rows:
        w.writerow([r.get(k, "") for k in keys])


@app.command()
def version() -> None:
    """Print version."""
    print(f"<tool> {VERSION}")


completions_app = typer.Typer(help="Shell completion: print the init script or install it into your rc file.", no_args_is_help=True)
app.add_typer(completions_app, name="completions")


@completions_app.command("show")
def completions_show(shell: str = typer.Argument(..., help="Shell to print the init script for (bash, zsh, fish).")) -> None:
    """Print the shell init script — source it via eval in your rc file.

    Example:
      eval "$(<tool> completions show bash)"   # ~/.bashrc
      eval "$(<tool> completions show zsh)"    # ~/.zshrc
    """
    import typer.main as _typer_main
    import click.shell_completion as _sc

    if shell not in SUPPORTED_SHELLS:
        _fail(f"unsupported shell {shell!r} (choose from: {', '.join(SUPPORTED_SHELLS)})", EXIT_USAGE)
    cls = _sc.get_completion_class(shell)
    complete_var = f"_{PROG.upper().replace('-', '_')}_COMPLETE"
    print(cls(_typer_main.get_command(app), {}, PROG, complete_var).source(), end="")


@completions_app.command("install")
def completions_install(
    shell: Optional[str] = typer.Argument(None, help="Shell to install for (bash, zsh, fish). Omit: detect from $SHELL."),
    rcfile: Optional[str] = typer.Option(None, "--rcfile", help="Rc file to edit (default per shell)."),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation."),
) -> None:
    """Install the eval line into your rc file (idempotent; keeps a .bak backup).

    Example:
      <tool> completions install            # detect shell from $SHELL
      <tool> completions install bash       # explicit shell
    """
    resolved = shell or _detect_shell()
    if resolved is None:
        _fail(f"cannot detect shell from $SHELL={os.environ.get('SHELL', '')!r}; pass bash, zsh, or fish explicitly", EXIT_USAGE)
    if not yes and sys.stdin.isatty() and not typer.confirm(f"Add {PROG} completion to your {resolved} rc file?"):
        sys.exit(EXIT_USAGE)
    rc, changed = _install_completion(resolved, Path(rcfile) if rcfile else None)
    if changed:
        print(f"installed {PROG} completion for {resolved} in {rc}", file=sys.stderr)
        print(f"restart your shell or run: source {rc}", file=sys.stderr)
    else:
        print(f"already installed in {rc}", file=sys.stderr)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
