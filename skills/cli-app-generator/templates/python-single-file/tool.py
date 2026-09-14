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
import sys
from pathlib import Path
from typing import NoReturn

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
    profile_name: str = typer.Option(None, "--profile", "-p", envvar="MYCLI_PROFILE", help="Auth profile."),
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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
