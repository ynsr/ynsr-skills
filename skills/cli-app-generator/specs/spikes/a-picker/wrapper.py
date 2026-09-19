"""Production-shape picker wrapper — the Spike A decision artifact.

questionary 2.1.1 + 2-line prompt_toolkit session wrapper.
Meets contract 4.1.1 (stdout data-only), 4.1.4 (non-TTY never blocks -> None)
and Ctrl-C terminal restore (probed, see report.md + evidence.txt).
<=20 LOC excluding docstring.
"""
import sys

from prompt_toolkit.application import create_app_session
from prompt_toolkit.output import create_output
from questionary import Choice, select


def pick(message, choices, default=None):
    """choices: [(key, desc_or_None), ...]. Returns key, or None on
    non-TTY stdin / Ctrl-C / EOF."""
    if not sys.stdin.isatty():
        return None
    opts = [
        Choice(k, value=k, description=d) if d else Choice(k, value=k)
        for k, d in choices
    ]
    try:
        with create_app_session(output=create_output(stdout=sys.stderr)):
            return select(message, choices=opts, default=default).ask()
    except (KeyboardInterrupt, EOFError):
        return None
