"""mycli: typer CLI + error envelope. The demo `list` is offline; wire client.Client for your API."""

import json
import os
import sys
from enum import StrEnum
from typing import Annotated

import httpx
import pydantic
import typer
import typer.completion as _typer_completion

# typer >=0.27: add_completion=False never registers shell completion classes, so the env-var
# completion server dies with "Shell bash not supported." (spike B; live on 0.27.0 AND 0.27.2).
_typer_completion.completion_init()
from typer._click.core import Abort as _ClickAbort  # typer 0.27 vendors click (spike B)
from typer._click.core import Exit as _ClickExit
from typer._click.exceptions import ClickException, NoArgsIsHelpError, UsageError

from . import __version__
from .config import (
    Profile,
    default_profile_name,
    list_profiles,
    load_profile,
    profile_path,
    save_profile,
    set_default_profile,
)
from .doctor import run as doctor_run
from .output import CliError, emit, fail


class Shell(StrEnum):
    bash = "bash"
    zsh = "zsh"
    fish = "fish"


app = typer.Typer(add_completion=False, no_args_is_help=True, pretty_exceptions_enable=False, help=(
    "mycli — data-plane CLI for a profile-backed API (the demo `list` source is offline).\n\n"
    "Exit codes: 0 success, 1 error, 2 usage, 3 network, 4 partial."
))

profile_app = typer.Typer(help="Manage connection profiles (0600 files; secrets via env or hidden prompt).")
app.add_typer(profile_app, name="profile")


def _interactive() -> bool:
    """TTY stdin, prompting not disabled (MYCLI_NO_INPUT or CI set → never prompt)."""
    return sys.stdin.isatty() and not os.environ.get("MYCLI_NO_INPUT") and not os.environ.get("CI")


def _pick(message: str, choices: list[tuple[str, str | None]]) -> str | None:
    """questionary select rendered on stderr; None on non-TTY / Ctrl-C / EOF (spike A wrapper)."""
    if not sys.stdin.isatty():
        return None
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.output import create_output
    from questionary import Choice, select

    opts = [Choice(k, value=k, description=d) if d else Choice(k, value=k) for k, d in choices]
    try:
        with create_app_session(output=create_output(stdout=sys.stderr)):
            return select(message, choices=opts).ask()
    except (KeyboardInterrupt, EOFError):
        return None


def _complete_profiles(incomplete: str = "") -> list[str]:
    """Dynamic completion: profile names from local state; [] on any failure, never blocks."""
    try:
        return [p.name for p in list_profiles() if p.name.startswith(incomplete)]
    except Exception:
        return []


def _set_no_color(value: bool) -> None:
    if value:
        os.environ["NO_COLOR"] = "1"


def _print_version(value: bool) -> None:
    if value:
        print(f"mycli {__version__}")
        raise typer.Exit()


Output = Annotated[str | None, typer.Option("--output", "-o", help="table|json|csv|tsv", envvar="MYCLI_OUTPUT")]
Json = Annotated[bool, typer.Option("--json", help="alias for --output json")]
Fields = Annotated[str | None, typer.Option("--fields", help="comma-separated output columns")]
Limit = Annotated[int, typer.Option(min=0, help="max rows (0 = all)")]
NoColor = Annotated[bool, typer.Option("--no-color", callback=_set_no_color, is_eager=True,
                                       help="disable styling (NO_COLOR/TERM=dumb honored too)")]


@app.callback()
def _globals(
    version: Annotated[bool, typer.Option("--version", callback=_print_version, is_eager=True,
                                          help="print version and exit")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="log details to stderr",
                                          envvar="MYCLI_VERBOSE")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="shorter errors: no hints",
                                        envvar="MYCLI_QUIET")] = False,
    no_input: Annotated[bool, typer.Option("--no-input", help="never prompt; fail instead",
                                           envvar="MYCLI_NO_INPUT")] = False,
    no_color: NoColor = False,
) -> None:
    for flag, var in ((verbose, "MYCLI_VERBOSE"), (quiet, "MYCLI_QUIET"), (no_input, "MYCLI_NO_INPUT")):
        if flag:
            os.environ[var] = "1"


DEMO_ROWS = [  # stub: replace with Client(resolve_profile()).request("GET", f"/{resource}") for your API
    {"id": 1, "name": "alpha", "size": 10, "created": "2026-09-20T00:00:00Z"},
    {"id": 2, "name": "beta", "size": 20, "created": "2026-09-20T00:00:01Z"},
    {"id": 3, "name": "gamma", "size": 30, "created": "2026-09-20T00:00:02Z"},
]


@app.command("list")
def list_cmd(
    resource: Annotated[str, typer.Argument(help="resource to list (demo source; wire to your API)")],
    fields: Fields = None,
    limit: Limit = 0,
    output: Output = None,
    as_json: Json = False,
    no_color: NoColor = False,
) -> None:
    """List rows as data on stdout."""
    rows = DEMO_ROWS[:limit] if limit else DEMO_ROWS
    chosen = [f.strip() for f in fields.split(",") if f.strip()] if fields else None
    emit(rows, output or ("json" if as_json else None), chosen)


@profile_app.command("create")
def profile_create(
    name: Annotated[str, typer.Argument(help="profile name")],
    url: Annotated[str, typer.Option("--url", help="API base URL (http/https)")],
    default: Annotated[bool, typer.Option("--default", help="make this the default profile")] = False,
    no_color: NoColor = False,
) -> None:
    """Save a profile; token comes from MYCLI_TOKEN or a hidden prompt (TTY only)."""
    token = os.environ.get("MYCLI_TOKEN", "")
    if not token and _interactive():
        import getpass

        token = getpass.getpass("API token (input hidden, Enter to skip): ")
    try:
        profile = Profile(name=name, url=url, token=token)
    except pydantic.ValidationError as e:
        raise CliError(f"invalid profile: {e.errors()[0]['msg']}", "usage",
                       "url must start with http:// or https://", 2) from e
    save_profile(profile)
    if default:
        set_default_profile(name)
    print(profile_path(name))


@profile_app.command("list")
def profile_list(output: Output = None, as_json: Json = False, no_color: NoColor = False) -> None:
    """List stored profiles (the token is never printed)."""
    rows = [{"name": p.name, "url": str(p.url), "default": p.name == default_profile_name()}
            for p in list_profiles()]
    emit(rows, output or ("json" if as_json else None))


@profile_app.command("remove")
def profile_remove(
    name: Annotated[str | None, typer.Argument(help="profile name (picked interactively on a TTY)",
                                                  autocompletion=_complete_profiles)] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="print the plan, change nothing")] = False,
    yes: Annotated[bool, typer.Option("--yes", help="execute without prompting")] = False,
    no_color: NoColor = False,
) -> None:
    """Remove a profile: --dry-run previews, --yes executes; non-TTY never prompts."""
    if name is None:
        if not _interactive():
            raise CliError("profile name required", "usage",
                           "profile remove <name> --dry-run (see profile list)", 2)
        name = _pick("Remove which profile?", [(p.name, p.url) for p in list_profiles()])
        if name is None:
            raise CliError("no profile selected", "usage", "name the profile: profile remove <name>", 2)
    stored = load_profile(name)
    if dry_run:
        print(f"would remove profile '{name}'"
              + (f" ({profile_path(name)})" if stored else " (not present, nothing to do)"))
        return
    if not yes:
        raise CliError(f"refusing to remove profile '{name}' without --yes", "usage",
                       "--dry-run previews the plan; --yes executes", 2)
    if stored is None:
        raise CliError(f"no such profile: {name}", "error", "profile list shows stored names", 1)
    profile_path(name).unlink()
    print(f"removed {profile_path(name)}")


@app.command()
def doctor(
    as_json: Annotated[bool, typer.Option("--json", help="single-line status dict (cli-hub contract)")] = False,
    no_color: NoColor = False,
) -> None:
    """Self-check: prints 'status: ok|missing' (exit 0|1); stale is never emitted."""
    raise SystemExit(doctor_run(as_json))


@app.command()
def schema(no_color: NoColor = False) -> None:
    """Dump command/parameter introspection + profile JSON Schema (agent audience)."""
    import typer.main

    root = typer.main.get_command(app)
    commands = {
        name: [{"option": f"--{p.name.replace('_', '-')}", "type": p.type.name,
                "required": p.required, "help": p.help or ""} for p in sub.params]
        for name, sub in getattr(root, "commands", {}).items()
    }
    print(json.dumps({"name": "mycli", "version": __version__,
                      "commands": commands, "profile_schema": Profile.model_json_schema()}, indent=2))


@app.command("completion")
def completion_cmd(
    shell: Annotated[Shell, typer.Argument(help="bash | zsh | fish")],
) -> None:
    """Print a completion script (install.sh drops it into your shell's autoload dir)."""
    from typer.completion import get_completion_script

    print(get_completion_script(prog_name="mycli", complete_var="_MYCLI_COMPLETE", shell=shell.value))


def main() -> None:
    """Console entry: envelope errors for agents (non-TTY/--json), plain + hint for humans."""
    try:
        app(standalone_mode=False)
    except (_ClickExit, typer.Exit) as e:
        raise SystemExit(getattr(e, "exit_code", 0)) from e
    except NoArgsIsHelpError:
        fail("no command given", "usage", "run with --help for usage", 2)
    except UsageError as e:
        fail(f"{e}".strip() or "invalid usage", "usage", "run with --help for usage", 2)
    except ClickException as e:
        fail(f"{e}".strip() or "error", "error", "run with --help", 2)
    except (typer.Abort, _ClickAbort, EOFError):
        fail("aborted", "aborted", "", 1)
    except CliError as e:
        fail(str(e), e.code, e.hint, e.status)
    except httpx.TransportError as e:
        fail(f"network: {e}", "network", "check connectivity, proxy env, or profile timeout", 3)
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except Exception as e:  # envelope contract: never a raw traceback (unless -v)
        if os.environ.get("MYCLI_VERBOSE"):
            import traceback

            traceback.print_exc(file=sys.stderr)
        fail(str(e) or repr(e), "error", "re-run with -v for a traceback", 1)
