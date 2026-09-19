"""Probe: raw prompt_toolkit 3.0.53 custom Application — the real integration
shape, since radiolist_dialog has no c-c binding and no output= kwarg.
NOTE: Application resolves output eagerly at construction (application.py:263),
so it MUST be constructed inside the create_app_session block.
RadioList's own enter/space binding only sets current_value, never exits —
app-level eager enter/space bindings are required on top."""
import sys

from prompt_toolkit.application import Application, create_app_session
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.output import create_output
from prompt_toolkit.widgets import RadioList

from menu import MENU


def pick():
    if not sys.stdin.isatty():              # guard G1
        return None
    radio = RadioList(
        values=[
            (k, f"{k} — {d}" if d else k)  # descriptions only inline
            for k, d in MENU
        ]
    )
    kb = KeyBindings()

    @kb.add("enter", eager=True)
    def _accept(event):
        event.app.exit(result=radio.current_value)

    @kb.add("c-c", eager=True)              # default bindings IGNORE c-c!
    def _cancel(event):
        event.app.exit(result=None)

    @kb.add("escape", eager=True)
    def _esc(event):
        event.app.exit(result=None)

    with create_app_session(output=create_output(stdout=sys.stderr)):
        app = Application(
            layout=Layout(
                HSplit([Window(FormattedTextControl("Pick one:"), height=1), radio])
            ),
            key_bindings=kb,
        )
        try:
            return app.run()
        except (KeyboardInterrupt, EOFError):   # guard G2
            return None


if __name__ == "__main__":
    print(f"RESULT:{pick()}")
