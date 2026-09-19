"""Probe: questionary 2.1.1 select(). Integration = pick() + its 2 guards only."""
import sys
import questionary
from prompt_toolkit.application import create_app_session
from prompt_toolkit.output import create_output
from questionary import Choice

from menu import MENU


def pick():
    if not sys.stdin.isatty():          # guard G1: non-TTY -> None (contract 4.1.4)
        return None
    try:
        with create_app_session(output=create_output(stdout=sys.stderr)):
            return questionary.select(
                "Pick one:",
                choices=[
                    Choice(key, value=key) if desc is None
                    else Choice(key, value=key, description=desc)
                    for key, desc in MENU
                ],
            ).ask()
    except (KeyboardInterrupt, EOFError):   # guard G2: Ctrl-C/EOF -> None
        return None


if __name__ == "__main__":
    print(f"RESULT:{pick()}")
