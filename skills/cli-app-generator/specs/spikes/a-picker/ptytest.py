#!/usr/bin/env python3
"""pty harness for picker probes.

Modes:
  t1 <probe>   stdin=pty, stdout=file, stderr=pty. Wait for menu render on pty
               traffic, send Enter, wait for exit; then prove stdout file holds
               ONLY the RESULT line.
  t2 <probe>   plain subprocess: stdin=/dev/null, timeout 5s. Proves no hang.
  t3 <probe>   stdin/stdout/stderr=pty. Wait for render, send SIGINT (as ^C
               byte on the tty AND as process-group SIGINT), wait for exit;
               then query `stty -a` on the pty and check canonical mode + echo
               restored, and cursor-show sequence emitted in cleanup.
"""
import fcntl
import os
import pty
import select
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from menu import MENU  # noqa: E402

NEEDLES = [k.encode() for k, _ in MENU]


def spawn(argv, stdout_path=None):
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
    slave_path = os.ttyname(slave)
    pid = os.fork()
    if pid == 0:
        os.close(master)
        os.setsid()
        fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
        os.dup2(slave, 0)
        os.dup2(slave, 2)
        if stdout_path:
            fd = os.open(stdout_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
            os.dup2(fd, 1)
            os.close(fd)
        else:
            os.dup2(slave, 1)
        os.close(slave)
        os.execvp(argv[0], argv)
        os._exit(127)
    os.close(slave)
    return pid, master, slave_path


def drain(master, seconds=0.3):
    """Read pty for up to `seconds`, return accumulated bytes."""
    out = b""
    deadline = time.time() + seconds
    while time.time() < deadline:
        r, _, _ = select.select([master], [], [], min(0.05, deadline - time.time()))
        if not r:
            continue
        try:
            chunk = os.read(master, 65536)
        except OSError:
            break
        if not chunk:
            break
        out += chunk
    return out


def wait_for(pid, master, needles, timeout=6.0, settle=0.4):
    """Read pty until all needles seen or child exits or timeout.
    Returns (buffer, matched_all, status_or_None)."""
    buf = b""
    matched = set()
    status = None
    start = time.time()
    while time.time() - start < timeout:
        r, _, _ = select.select([master], [], [], 0.1)
        if r:
            try:
                chunk = os.read(master, 65536)
            except OSError:
                chunk = b""
            if chunk:
                buf += chunk
                for n in needles:
                    if n not in matched and n in buf:
                        matched.add(n)
        wpid, st = os.waitpid(pid, os.WNOHANG)
        if wpid:
            status = st
            buf += drain(master, 0.5)
            break
        if len(matched) == len(needles):
            buf += drain(master, settle)
            return buf, True, None
    return buf, False, status


def status_str(status):
    if status is None:
        return "TIMEOUT/HUNG (killed)"
    if os.WIFSIGNALED(status):
        return f"KILLED by signal {os.WTERMSIG(status)}"
    return f"exit {os.WEXITSTATUS(status)}"


def reaped_wait(pid, master, buf, seconds):
    deadline = time.time() + seconds
    while time.time() < deadline:
        wpid, st = os.waitpid(pid, os.WNOHANG)
        if wpid:
            buf += drain(master, 0.5)
            return st, buf
        buf += drain(master, 0.1)
    os.kill(pid, signal.SIGKILL)
    os.waitpid(pid, 0)
    return None, buf


def mode_t1(probe):
    with tempfile.NamedTemporaryFile(suffix=".out", delete=False) as tf:
        stdout_path = tf.name
    py = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv/bin/python")
    pid, master, _ = spawn([py, probe], stdout_path=stdout_path)
    buf, ok, status = wait_for(pid, master, NEEDLES)
    if ok:
        os.write(master, b"\r")  # Enter: accept highlighted item
        status, buf = reaped_wait(pid, master, buf, 5)
    elif status is None:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    with open(stdout_path, "rb") as f:
        stdout_bytes = f.read()
    os.unlink(stdout_path)
    has_ansi = b"\x1b[" in stdout_bytes
    print(f"[t1] {probe}")
    print(f"[t1] pty-capture bytes (stderr//tty side): {len(buf)}")
    print(f"[t1] child status: {status_str(status)}")
    print(f"[t1] STDOUT FILE ({len(stdout_bytes)} bytes): {stdout_bytes!r}")
    print(f"[t1] stdout contains ANSI escapes: {has_ansi}")
    ok1 = stdout_bytes == b"RESULT:alpha\n"
    print(f"[t1] VERDICT stdout-pure: {ok1}")
    return 0 if ok1 else 1


def mode_t2(probe):
    py = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv/bin/python")
    start = time.time()
    r = subprocess.run(
        ["timeout", "5", py, probe],
        stdin=subprocess.DEVNULL,
        capture_output=True,
    )
    wall = time.time() - start
    print(f"[t2] {probe}")
    print(f"[t2] rc={r.returncode} wall={wall:.2f}s (124=timeout hung)")
    print(f"[t2] stdout: {r.stdout!r}")
    print(f"[t2] stderr tail: {r.stderr[-300:]!r}")
    ok = r.returncode == 0 and r.stdout == b"RESULT:None\n"
    print(f"[t2] VERDICT non-tty-None-no-hang: {ok}")
    return 0 if ok else 1


def mode_t3(probe):
    py = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv/bin/python")
    pid, master, slave_path = spawn([py, probe])
    buf, ok, status = wait_for(pid, master, NEEDLES)
    if ok:
        buf += drain(master, 1.0)   # let menu finish render + termios setup
        os.write(master, b"\x03")   # ^C byte: terminal-driver path (realistic)
        os.killpg(os.getpgid(pid), signal.SIGINT)  # out-of-band group SIGINT too
        outcome, buf = reaped_wait(pid, master, buf, 8)
    else:
        outcome = status
        if outcome is None:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
    # terminal restore check: fresh fd on the slave, ask stty
    with open(slave_path, "rb") as sf:
        stty = subprocess.run(["stty", "-a"], stdin=sf, capture_output=True, timeout=5)
    flags = set(stty.stdout.decode(errors="replace").split())
    icanon_ok = "icanon" in flags and "-icanon" not in flags
    echo_ok = "echo" in flags and "-echo" not in flags
    cursor_shown = buf.rfind(b"\x1b[?25h") > buf.rfind(b"\x1b[?25l")
    alt_exit = b"\x1b[?1049l" in buf
    print(f"[t3] {probe}")
    print(f"[t3] after SIGINT child: {status_str(outcome)}")
    print(f"[t3] pty tail: {buf[-200:]!r}")
    print(f"[t3] stty -a: {stty.stdout.decode(errors='replace').strip()[:160]}")
    print(f"[t3] icanon restored: {icanon_ok}; echo restored: {echo_ok}")
    print(f"[t3] cursor-show emitted after hide: {cursor_shown}")
    print(f"[t3] alt-screen exit emitted (full-screen apps): {alt_exit}")
    ok3 = icanon_ok and echo_ok
    print(f"[t3] VERDICT ctrl-c-restores-terminal: {ok3}")
    return 0 if ok3 else 1


if __name__ == "__main__":
    mode = sys.argv[1]
    probe = sys.argv[2]
    sys.exit({"t1": mode_t1, "t2": mode_t2, "t3": mode_t3}[mode](probe))
