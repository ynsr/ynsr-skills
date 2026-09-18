"""Typer app: commands, output formatting (CSV default / --json), setup wizard.

stdout carries ONLY command output; every log/progress line goes to stderr.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from typing import Optional

import typer

from . import completions as _completions
from . import ops
from .client import Client, NetworkError, SolrHTTPError
from .config import Profile, ProfileError, get_default, list_profiles, load_profile, resolve_profile, save_profile, set_default
from . import doctor as _doctor

__version__ = "0.1.0"

EXIT_OK, EXIT_GENERAL, EXIT_USAGE, EXIT_NETWORK = 0, 1, 2, 3

_complete_profiles = _completions.complete_names(list_profiles)

app = typer.Typer(
    name="mycli",
    help="One-line tool description.",
    no_args_is_help=True,
    add_completion=False,  # single completion system: `completions show|install` (see completions.py)
    context_settings={"help_option_names": ["-h", "--help"]},
    pretty_exceptions_enable=False,
)
profile_app = typer.Typer(help="Manage saved connection profiles.", no_args_is_help=True)
app.add_typer(profile_app, name="profile")


def _version_callback(value: bool) -> None:
    if value:
        print(f"mycli {__version__}")
        raise typer.Exit(0)


@app.callback()
def _main(
    version: Optional[bool] = typer.Option(None, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."),
) -> None:
    """Global options."""


def _fail(msg: str, code: int) -> None:
    print(f"error: {msg}", file=sys.stderr)
    raise typer.Exit(code)


def _echo_json(payload) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def _emit_rows(rows: list[dict], json_output: bool, keys: list[str] | None = None) -> None:
    """List output: CSV with header row by default, JSON with --json."""
    if json_output:
        _echo_json(rows)
        return
    if not rows:
        return
    if keys is None:
        keys = list(rows[0].keys())
    w = csv.writer(sys.stdout)
    w.writerow(keys)
    for r in rows:
        w.writerow([r.get(k, "") for k in keys])


def _interactive_pick(label: str, options: dict[str, str]) -> str:
    """Prompted selection when stdin is a TTY; None otherwise."""
    if not sys.stdin.isatty():
        return None
    print(label, file=sys.stderr)
    items = list(options.items())
    for i, (name, desc) in enumerate(items, 1):
        print(f"  {i}. {name}" + (f" — {desc}" if desc else ""), file=sys.stderr)
    raw = input(f"number [1-{len(items)}]: ")
    try:
        return items[int(raw) - 1][0]
    except (ValueError, IndexError):
        return None


# -- setup wizard ------------------------------------------------------------


@app.command("init")
def init(
    name: str = typer.Argument("default", help="Profile name — new, or an existing one to update (prompts prefill from it)."),
    url: Optional[str] = typer.Option(None, "--url", help="Source base URL (prompted if omitted)."),
    token: Optional[str] = typer.Option(None, "--token", help="API token (prompted if omitted; prefer MYCLI_TOKEN env)."),
    no_completion: bool = typer.Option(False, "--no-completion", help="Skip the shell-completion install prompt at the end."),
) -> None:
    """Setup wizard: create or update a profile, mark it default, verify with one live call.

    Example:
      mycli init                     # profile 'default', prompted for URL + token
      mycli init prod --url https://prod.example
      mycli init default             # re-run against an existing profile to update it
    """
    import getpass

    existing = load_profile(name) if name in list_profiles() else None
    url_val = url or typer.prompt("Source base URL", default=existing.url if existing else None)
    tok = (token
           or os.environ.get("MYCLI_TOKEN")
           or getpass.getpass("API token (enter to keep existing): ")
           or (existing.token if existing else None))
    prof = existing or Profile(name=name, url=url_val, token=tok)
    prof.url, prof.token = url_val, tok
    save_profile(prof)
    set_default(name)
    try:
        with Client(resolve_profile(None)) as client:
            ops.health_check(client)   # one cheap authenticated call
        print(f"OK: profile '{name}' {'updated' if existing else 'created'} as default and verified.")
    except (NetworkError, SolrHTTPError, ProfileError) as exc:
        _fail(f"profile saved but verification failed: {exc}", EXIT_NETWORK)
    if not no_completion and sys.stdin.isatty():
        shell = _completions.detect_shell()
        if shell and typer.confirm(f"Install shell completion for {shell}?", default=False):
            rc, changed = _completions.install_completion("mycli", shell, None)
            if changed:
                _completions.print_install_hint("mycli", shell, rc)


# -- example data command: CSV default, --json opt-in -------------------------


@app.command("list")
def list_cmd(
    resource: str = typer.Argument(..., help="Resource to list."),
    json_output: bool = typer.Option(False, "--json", help="JSON instead of CSV."),
    profile_name: Optional[str] = typer.Option(None, "--profile", "-p", envvar="MYCLI_PROFILE", autocompletion=_complete_profiles, help="Profile to use (default: stored default)."),
    timeout: Optional[float] = typer.Option(None, "--timeout", help="Per-request timeout seconds."),
    retries: Optional[int] = typer.Option(None, "--retries", min=0, help="Retries on 5xx/429/timeouts."),
) -> None:
    """List items from the source (CSV with headers by default).

    Example:
      mycli list widgets
      mycli list widgets --json | jq '.[0]'
      mycli list widgets --profile other-org
    """
    try:
        profile = resolve_profile(profile_name)
    except ProfileError as exc:
        # interactive pick when nothing was resolved and we're on a TTY
        chosen = _interactive_pick("Available profiles:", {n: p.url for n, p in list_profiles().items()})
        if chosen is None:
            _fail(str(exc), EXIT_USAGE)
        profile = resolve_profile(chosen)

    def do(client: Client):
        rows = ops.list_resource(client, resource, timeout=timeout, retries=retries)
        _emit_rows(rows, json_output)

    try:
        with Client(profile) as client:
            do(client)
    except ProfileError as exc:
        _fail(str(exc), EXIT_USAGE)
    except NetworkError as exc:
        _fail(str(exc), EXIT_NETWORK)
    except SolrHTTPError as exc:
        _fail(str(exc), EXIT_GENERAL)


# -- profile management -------------------------------------------------------


@profile_app.command("create")
def profile_create(
    name: str = typer.Argument(..., help="Profile name."),
    url: str = typer.Option(..., "--url", help="Source base URL."),
    token: str = typer.Option(None, "--token", help="API token (omit: prompted via getpass; prefer piping)."),
    set_default_flag: bool = typer.Option(False, "--default", help="Mark as the default profile."),
) -> None:
    """Save a connection profile (stored 0600 under ~/.config/mycli/profiles/)."""
    import getpass

    tok = token or getpass.getpass("API token (empty = none): ")
    save_profile(Profile(name=name, url=url, token=tok))
    if set_default_flag:
        set_default(name)
    print(f"saved profile '{name}'" + (" (default)" if set_default_flag else ""))


@profile_app.command("list")
def profile_list() -> None:
    """List saved profiles."""
    profiles = list_profiles()
    default = get_default()
    for name, p in profiles.items():
        star = "*" if name == default else " "
        print(f"{star} {name}  {p.url}")


@profile_app.command("use")
def profile_use(name: str = typer.Argument(..., autocompletion=_complete_profiles)) -> None:
    """Set the default profile."""
    if name not in list_profiles():
        _fail(f"profile '{name}' not found", EXIT_USAGE)
    set_default(name)
    print(f"default profile: {name}")


@profile_app.command("remove")
def profile_remove(name: str = typer.Argument(..., autocompletion=_complete_profiles), yes: bool = typer.Option(False, "--yes", help="Skip confirmation.")) -> None:
    """Delete a profile."""
    if not yes and not typer.confirm(f"Remove profile '{name}'?"):
        raise typer.Exit(EXIT_USAGE)
    from .config import delete_profile
    delete_profile(name)
    print(f"removed '{name}'")


# -- shell completion ---------------------------------------------------------

completions_app = typer.Typer(help="Shell completion: print the init script or install it into your rc file.", no_args_is_help=True)
app.add_typer(completions_app, name="completions")


@completions_app.command("show")
def completions_show(
    shell: str = typer.Argument(..., help="Shell to print the init script for (bash, zsh, fish)."),
) -> None:
    """Print the shell init script — source it via eval in your rc file.

    Example:
      eval "$(mycli completions show bash)"   # ~/.bashrc
      eval "$(mycli completions show zsh)"    # ~/.zshrc
      mycli completions show fish | source    # fish config
    """
    import typer.main as _typer_main

    try:
        script = _completions.get_completion_script("mycli", shell, click_cmd=_typer_main.get_command(app))
    except ValueError as exc:
        _fail(str(exc), EXIT_USAGE)
    print(script, end="" if script.endswith("\\n") else "\\n")


@completions_app.command("install")
def completions_install(
    shell: Optional[str] = typer.Argument(None, help="Shell to install for (bash, zsh, fish). Omit: detect from $SHELL."),
    rcfile: Optional[str] = typer.Option(None, "--rcfile", help="Rc file to edit (default: ~/.bashrc, ~/.zshrc, fish config)."),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation (needed for non-interactive/agent use)."),
) -> None:
    """Install the eval line into your rc file (idempotent; keeps a .bak backup).

    Example:
      mycli completions install          # detect shell from $SHELL
      mycli completions install bash     # explicit shell
      mycli completions install zsh --rcfile ~/.zshrc --yes
    """
    from pathlib import Path as _Path

    resolved = shell or _completions.detect_shell()
    if resolved is None:
        _fail(f"cannot detect shell from $SHELL={os.environ.get('SHELL', '')!r}; pass bash, zsh, or fish explicitly", EXIT_USAGE)
    if not yes and sys.stdin.isatty() and not typer.confirm(f"Add mycli completion to your {resolved} rc file?"):
        raise typer.Exit(EXIT_USAGE)
    try:
        rc, changed = _completions.install_completion("mycli", resolved, _Path(rcfile) if rcfile else None)
    except ValueError as exc:
        _fail(str(exc), EXIT_USAGE)
    if changed:
        _completions.print_install_hint("mycli", resolved, rc)
    else:
        print(f"already installed in {rc}", file=sys.stderr)


@app.command("doctor")
def doctor() -> None:
    """Check the installed copy is in sync with the source tree.

    Example: mycli doctor

    Exit codes: 0 in sync · 1 stale/missing receipt (fix: ./install.sh).
    """
    status, message = _doctor.check()
    print(message)
    if status != _doctor.OK:
        raise typer.Exit(EXIT_GENERAL)


def main() -> None:
    _completions.ensure_completion_classes()  # typer 0.27: runtime server needs registered classes
    app()


if __name__ == "__main__":
    main()
