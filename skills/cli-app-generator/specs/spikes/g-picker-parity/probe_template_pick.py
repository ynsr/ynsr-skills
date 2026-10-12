"""Probe: EXACT template _pick shape from cli.py.jinja (questionary 2.1.1)."""
import sys

from menu import MENU


def _pick(message, choices):
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


if __name__ == "__main__":
    print(f"RESULT:{_pick('Pick one:', MENU)!r}")
