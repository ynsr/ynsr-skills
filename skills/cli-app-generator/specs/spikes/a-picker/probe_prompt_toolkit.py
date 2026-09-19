"""Probe: raw prompt_toolkit 3.0.53 radiolist_dialog.

Integration = pick() + stderr-routing session + guards.
radiolist_dialog exposes no output= kwarg; prompt_toolkit routes via the
AppSession, so stderr routing = create_app_session(output=create_output(stdout=sys.stderr)).
"""
import sys

from prompt_toolkit.application import create_app_session
from prompt_toolkit.output import create_output
from prompt_toolkit.shortcuts import radiolist_dialog

from menu import MENU, FIRST


def pick():
    if not sys.stdin.isatty():          # guard G1
        return None
    try:
        with create_app_session(output=create_output(stdout=sys.stderr)):
            return radiolist_dialog(
                title="Pick one",
                text="Select:",
                values=[(key, label) for key, label in MENU],
                default=FIRST,
            ).run()
    except (KeyboardInterrupt, EOFError):   # guard G2
        return None


if __name__ == "__main__":
    print(f"RESULT:{pick()}")
