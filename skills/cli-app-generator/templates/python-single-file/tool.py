#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["typer>=0.27.2,<0.28", "httpx[socks]>=0.27", "rich>=13.7"]
# ///
"""<tool> — one-line description.
Single-file PEP 723 CLI. Scaffold markers: `<tool>` (display name), `<TOOL>` (env prefix),
`<audience-output>` (DEFAULT_OUTPUT: human → table, agent → csv). Data on stdout; errors and
progress on stderr. Exit codes: 0 success, 1 error, 2 usage, 3 network, 4 partial.
"""

import csv, json, os, sys, time
import httpx, typer
from typer._click import exceptions as _click_exc  # typer 0.27 vendors click
from typer.main import get_command

VERSION = "0.1.0"
TOKEN = os.environ.get("<TOOL>_TOKEN", "")  # secret: env only, never a flag
BASE_URL = os.environ.get("<TOOL>_URL", "https://api.example.com").rstrip("/")
TIMEOUT = float(os.environ.get("<TOOL>_TIMEOUT", "30"))
DEFAULT_OUTPUT = "table"  # <audience-output>
_EXIT_NAMES = {1: "error", 2: "usage", 3: "network", 4: "partial"}; AGENT_JSON, QUIET = False, False

app = typer.Typer(
    help="<tool> — one-line description.\n\nExit codes: 0 success, 1 error, 2 usage, 3 network, 4 partial.",
    no_args_is_help=True, add_completion=False,  # lean tier: no shell-completion machinery
    context_settings={"help_option_names": ["-h", "--help"]}, pretty_exceptions_enable=False)


def _error_out(code: int, message: str, hint: str = "") -> None:
    """Agents (non-TTY or --output json) get {"error":{code,message,hint}}; humans a plain line."""
    if not sys.stderr.isatty() or AGENT_JSON:
        print(json.dumps({"error": {"code": _EXIT_NAMES.get(code, "error"), "message": message, "hint": hint}}), file=sys.stderr)
    else:
        print(f"error: {message}" + ("" if QUIET or not hint else f" (hint: {hint})"), file=sys.stderr)


def _fail(message: str, code: int, hint: str = "") -> None:
    _error_out(code, message, hint); raise typer.Exit(code)


def _client() -> httpx.Client:
    if not TOKEN:
        _fail("config: <TOOL>_TOKEN is not set", 2, hint="export <TOOL>_TOKEN=<token>")
    return httpx.Client(base_url=BASE_URL, timeout=TIMEOUT, headers={"Authorization": f"Bearer {TOKEN}"}, transport=httpx.HTTPTransport(retries=2))


def api_get(client: httpx.Client, path: str) -> dict:
    """GET JSON with 3 attempts on 5xx/timeouts (0.5s→2s capped backoff); 4xx/parse fails fast."""
    err: Exception | None = None
    for attempt in range(3):
        try:
            resp = client.get(path); resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500:
                _fail(f"HTTP {exc.response.status_code} on GET {path}", 1, hint="check <TOOL>_URL / credentials")
            err = exc
        except httpx.TransportError as exc:  # timeouts + connect/reset
            err = exc
        except ValueError:
            _fail(f"GET {path}: response is not JSON", 1)
        time.sleep(min(2.0, 0.5 * 2**attempt))
    _fail(f"GET {path} failed after 3 attempts: {err}", 3, hint="check network / <TOOL>_URL")


def _emit(rows: list[dict], fmt: str) -> None:
    """Render rows: json (stdlib), csv/tsv (RFC4180 quoting), aligned plain table."""
    keys = list(rows[0]) if rows else []
    if fmt == "json":
        print(json.dumps(rows, indent=2, default=str)); return
    if fmt in ("csv", "tsv"):
        writer = csv.writer(sys.stdout, delimiter="\t" if fmt == "tsv" else ",")
        writer.writerow(keys)
        for row in rows:
            writer.writerow([row.get(k, "") for k in keys])
    else:
        cells = [keys] + [[str(row.get(k, "")) for k in keys] for row in rows]
        widths = [max(map(len, col)) for col in zip(*cells)]
        for row in cells:
            print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip())

@app.command()
def items(
    resource: str = typer.Argument(..., help="Resource to fetch (GET <base>/<resource>, reads items[])."),
    output: str | None = typer.Option(None, "--output", "-o", help="table|json|csv|tsv."),
    json_alias: bool = typer.Option(False, "--json", help="Alias for --output json."),
) -> None:
    """List a resource's rows (flat CSV with header by default; --json for jq)."""
    fmt = output or ("json" if json_alias else DEFAULT_OUTPUT)
    if fmt not in ("table", "json", "csv", "tsv"):
        _fail(f"unknown output format '{fmt}'", 2, hint="table|json|csv|tsv")
    global AGENT_JSON; AGENT_JSON = fmt == "json"
    _emit(api_get(_client(), f"/{resource}").get("items", []), fmt)

@app.command()
def doctor(json_flag: bool = typer.Option(False, "--json", help="Single-line JSON status (cli-hub parses it).")) -> None:
    """Health check — prints `status: ok|missing` (never 'stale'); exit 0 ok, 1 missing."""
    problem = "" if TOKEN else "config: <TOOL>_TOKEN is not set"
    print(json.dumps({"status": "missing" if problem else "ok", "message": problem}) if json_flag
          else f"status: {'missing' if problem else 'ok'}" + (f"\n  FAIL {problem}" if problem else ""))
    raise typer.Exit(0 if not problem else 1)

@app.command()
def delete(
    resource: str = typer.Argument(..., help="Resource name."),
    row_id: str = typer.Argument(..., help="Row id to delete."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the request that would be sent."),
    yes: bool = typer.Option(False, "--yes", help="Execute (destructive)."),
) -> None:
    """Template destructive command: --dry-run previews, --yes executes, neither refuses."""
    if dry_run:
        print(f"would send: DELETE {BASE_URL}/{resource}/{row_id}"); return
    if not yes:
        _fail("refusing to delete without --yes", 2, hint="pass --yes to execute, --dry-run to preview")
    try:
        _client().delete(f"/{resource}/{row_id}").raise_for_status()
    except httpx.HTTPStatusError as exc:
        _fail(f"DELETE {resource}/{row_id}: HTTP {exc.response.status_code}", 3 if exc.response.status_code >= 500 else 1, hint="check <TOOL>_URL / credentials")
    except httpx.RequestError as exc:
        _fail(f"DELETE {resource}/{row_id}: {exc}", 3, hint="check network / <TOOL>_URL")
    print(f"deleted {resource}/{row_id}")

def _version(value: bool) -> None:
    if value:
        print(f"<tool> {VERSION}"); raise typer.Exit(0)

@app.callback()
def _main(
    version: bool | None = typer.Option(None, "--version", "-v", callback=_version, is_eager=True, help="Print version and exit."),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Hide hints on error output."),
    no_color: bool = typer.Option(False, "--no-color", help="Accepted for the contract; output is plain text."),
) -> None:
    global QUIET; QUIET = quiet

def main() -> int:
    """Owns exit codes + the error envelope; standalone_mode=False returns (not raises) Exit codes."""
    if "--no-color" in sys.argv:
        os.environ["NO_COLOR"] = "1"  # rich/typer help styling reads it
    try:
        return get_command(app)(standalone_mode=False) or 0
    except _click_exc.ClickException as exc:  # usage errors → envelope, exit 2
        _error_out(exc.exit_code, exc.format_message(), "run with --help"); return exc.exit_code
    except _click_exc.Abort:
        _error_out(130, "aborted by user"); return 130

if __name__ == "__main__":
    raise SystemExit(main())
