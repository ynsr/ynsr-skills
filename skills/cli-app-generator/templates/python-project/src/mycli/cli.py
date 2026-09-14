"""Typer app: commands, output formatting (CSV default / --json), setup wizard.

stdout carries ONLY command output; every log/progress line goes to stderr.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from typing import Optional

import typer

from . import ops
from .client import Client, NetworkError, SolrHTTPError
from .config import Profile, ProfileError, config_dir, get_default, list_profiles, resolve_profile, save_profile, set_default

__version__ = "0.1.0"

EXIT_OK, EXIT_GENERAL, EXIT_USAGE, EXIT_NETWORK = 0, 1, 2, 3

app = typer.Typer(
    name="mycli",
    help="One-line tool description.",
    no_args_is_help=True,
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
    url: str = typer.Option(..., "--url", prompt="Source base URL"),
    token: str = typer.Option(None, "--token", help="API token (prompted if omitted; prefer MYCLI_TOKEN env)."),
    name: str = typer.Option("default", "--name", help="Profile name to save."),
) -> None:
    """Setup wizard: configure endpoint + auth, save a profile, verify with one live call."""
    import getpass

    tok = token or os.environ.get("MYCLI_TOKEN") or getpass.getpass("API token: ")
    save_profile(Profile(name=name, url=url, token=tok))
    set_default(name)
    try:
        with Client(resolve_profile(None)) as client:
            ops.health_check(client)   # one cheap authenticated call
        print(f"OK: profile '{name}' saved as default and verified.")
    except (NetworkError, SolrHTTPError, ProfileError) as exc:
        _fail(f"profile saved but verification failed: {exc}", EXIT_NETWORK)


import os  # noqa: E402  (kept at bottom of imports for clarity in template)


# -- example data command: CSV default, --json opt-in -------------------------


@app.command("list")
def list_cmd(
    resource: str = typer.Argument(..., help="Resource to list."),
    json_output: bool = typer.Option(False, "--json", help="JSON instead of CSV."),
    profile_name: Optional[str] = typer.Option(None, "--profile", "-p", envvar="MYCLI_PROFILE", help="Profile to use (default: stored default)."),
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
def profile_use(name: str = typer.Argument(...)) -> None:
    """Set the default profile."""
    if name not in list_profiles():
        _fail(f"profile '{name}' not found", EXIT_USAGE)
    set_default(name)
    print(f"default profile: {name}")


@profile_app.command("remove")
def profile_remove(name: str = typer.Argument(...), yes: bool = typer.Option(False, "--yes", help="Skip confirmation.")) -> None:
    """Delete a profile."""
    if not yes and not typer.confirm(f"Remove profile '{name}'?"):
        raise typer.Exit(EXIT_USAGE)
    from .config import delete_profile
    delete_profile(name)
    print(f"removed '{name}'")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
