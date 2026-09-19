"""prompt_toolkit custom app built OUTSIDE the stderr session — reproduces the
eager-construction trap (application.py:263): UI renders into stdout file."""
import sys

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.output import create_output
from prompt_toolkit.widgets import RadioList

from menu import MENU

radio = RadioList(values=[(k, k) for k, _ in MENU])
kb = KeyBindings()


@kb.add("enter", eager=True)
def _accept(event):
    event.app.exit(result=radio.current_value)


@kb.add("c-c", eager=True)
def _cancel(event):
    event.app.exit(result=None)


# constructed OUTSIDE any create_app_session block:
app = Application(
    layout=Layout(HSplit([Window(FormattedTextControl("Pick one:"), height=1), radio])),
    key_bindings=kb,
)

if __name__ == "__main__":
    if not sys.stdin.isatty():
        print("RESULT:None")
        sys.exit(0)
    print(f"RESULT:{app.run()}")
