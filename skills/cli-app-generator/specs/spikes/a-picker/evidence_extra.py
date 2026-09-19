#!/usr/bin/env python3
"""Extra logged evidence beyond ptytest.py's standard modes.

X1: radiolist_dialog Tab-then-Enter flow (alt-screen enter/exit, exit 0,
    RESULT on stdout file) — backs the report's Tab-Enter claim.
X2: unwrapped questionary: stdout->file, then ^C byte; proves
    'Cancelled by user' lands on the STDOUT file (not just pty capture).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ptytest  # noqa: E402

py = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv/bin/python")

print("=== X1 radiolist_dialog Tab-then-Enter (probe_prompt_toolkit.py) ===")
pid, master, _ = ptytest.spawn([py, "probe_prompt_toolkit.py"])
buf, ok, st = ptytest.wait_for(pid, master, ptytest.NEEDLES)
print(f"[x1] menu rendered: {ok}; alt-screen enter (1049h) seen: {b'\x1b[?1049h' in buf}")
ptytest.drain(master, 0.8)
os.write(master, b"\t")   # Tab: focus moves to OK button
os.write(master, b"\r")   # Enter: accept
outcome, buf = ptytest.reaped_wait(pid, master, buf, 5)
print(f"[x1] after Tab+Enter child: {ptytest.status_str(outcome)}")
print(f"[x1] alt-screen exit (1049l) seen: {b'\x1b[?1049l' in buf}")
print(f"[x1] cursor-show after hide: {buf.rfind(b'\x1b[?25h') > buf.rfind(b'\x1b[?25l')}")

print("=== X2 unwrapped .ask() Ctrl-C writes 'Cancelled by user' to STDOUT file ===")
import tempfile  # noqa: E402
with tempfile.NamedTemporaryFile(suffix=".out", delete=False) as tf:
    stdout_path = tf.name
pid, master, _ = ptytest.spawn([py, "probe_unwrapped.py"], stdout_path=stdout_path)
buf, ok, st = ptytest.wait_for(pid, master, ptytest.NEEDLES)
ptytest.drain(master, 0.8)
os.write(master, b"\x03")  # ^C byte
outcome, _ = ptytest.reaped_wait(pid, master, buf, 5)
with open(stdout_path, "rb") as f:
    data = f.read()
os.unlink(stdout_path)
print(f"[x2] after ^C child: {ptytest.status_str(outcome)}")
print(f"[x2] STDOUT FILE ({len(data)} bytes): {data!r}")
