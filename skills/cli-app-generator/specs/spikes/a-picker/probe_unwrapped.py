"""Unwrapped questionary .ask() — no stderr session, no guards.
Evidence for native defects: stdout UI pollution + Ctrl-C 'Cancelled by user'
printed to stdout + EOFError propagation on non-TTY stdin."""
import sys

import questionary
from questionary import Choice

from menu import MENU


def pick():
    return questionary.select(
        "Pick one:",
        choices=[
            Choice(key, value=key) if desc is None
            else Choice(key, value=key, description=desc)
            for key, desc in MENU
        ],
    ).ask()


if __name__ == "__main__":
    print(f"RESULT:{pick()}")
