#!/usr/bin/env python3
"""Parity harness for spike G: template _pick vs workagent behaviors.

Modes (all use stdout->file, stderr->pty like spike A t1):
  g1 <probe>  nav+erase: wait for menu, DOWN DOWN UP, Enter; assert stdout
              file is exactly the result line; report whether the option
              block was erased from the pty after choose (workagent erases).
  g2 <probe>  ctrl-c-file: wait for menu, stdout->file already set; send ^C
              byte + group SIGINT; assert stdout file has NO 'Cancelled'
              leak beyond the RESULT line.
  g3 <probe>  q-esc: send 'q' then (fresh spawn) Escape; report what each
              key does (workagent: abort -> None).
  g4 <probe>  dup: DOWN x3 to land on the duplicate 'alpha', Enter; report
              whether the result disambiguates (value vs index).
  g5 <probe>  jk: send 'j' 'j' then Enter; report whether j moves selection.
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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from menu import MENU  # noqa: E402

NEEDLES = [b"alpha", b"beta", b"omega"]
PY = os.path.join(HERE, ".venv/bin/python")


def spawn(argv, stdout_path):
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
        fd = os.open(stdout_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        os.dup2(fd, 1)
        os.close(fd)
        os.close(slave)
        os.execvp(argv[0], argv)
        os._exit(127)
    os.close(slave)
    return pid, master, slave_path


def drain(master, seconds=0.3):
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


def wait_render(pid, master, timeout=6.0):
    buf = b""
    matched = set()
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
                for n in NEEDLES:
                    if n in buf:
                        matched.add(n)
        wpid, st = os.waitpid(pid, os.WNOHANG)
        if wpid:
            return buf, False, st
        if matched == set(NEEDLES):
            buf += drain(master, 0.4)
            return buf, True, None
    return buf, False, None


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


def read_stdout_file(path):
    with open(path, "rb") as f:
        return f.read()


def status_str(status):
    if status is None:
        return "TIMEOUT/HUNG (killed)"
    if os.WIFSIGNALED(status):
        return f"KILLED by signal {os.WTERMSIG(status)}"
    return f"exit {os.WEXITSTATUS(status)}"


def run_g1(probe):
    with tempfile.NamedTemporaryFile(suffix=".out", delete=False) as tf:
        sp = tf.name
    pid, master, _ = spawn([PY, probe], sp)
    buf, ok, status = wait_render(pid, master)
    if ok:
        os.write(master, b"\x1b[B\x1b[B\x1b[A")  # DOWN DOWN UP -> gamma(idx2)
        time.sleep(0.4)
        os.write(master, b"\r")
        status, buf = reaped_wait(pid, master, buf, 5)
    elif status is None:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    out = read_stdout_file(sp)
    os.unlink(sp)
    print(f"[g1] {probe}")
    print(f"[g1] child: {status_str(status)}")
    print(f"[g1] STDOUT FILE ({len(out)} bytes): {out!r}")
    print(f"[g1] stdout-pure (no ANSI): {b'\x1b[' not in out}")
    # erase check: after choose, workagent's _erase rewrites option lines;
    # report trailing erase sequences as evidence either way
    print(f"[g1] pty tail: {buf[-160:]!r}")


def run_g2(probe):
    with tempfile.NamedTemporaryFile(suffix=".out", delete=False) as tf:
        sp = tf.name
    pid, master, slave_path = spawn([PY, probe], sp)
    buf, ok, status = wait_render(pid, master)
    if ok:
        buf += drain(master, 1.0)
        os.write(master, b"\x03")
        os.killpg(os.getpgid(pid), signal.SIGINT)
        outcome, buf = reaped_wait(pid, master, buf, 8)
    else:
        outcome = status
        if outcome is None:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
    out = read_stdout_file(sp)
    os.unlink(sp)
    print(f"[g2] {probe}")
    print(f"[g2] after SIGINT child: {status_str(outcome)}")
    print(f"[g2] STDOUT FILE ({len(out)} bytes): {out!r}")
    print(f"[g2] 'Cancelled' leaked to stdout file: {b'Cancelled' in out}")


def run_g3(probe):
    for key, name in ((b"q", "q"), (b"\x1b", "Esc")):
        with tempfile.NamedTemporaryFile(suffix=".out", delete=False) as tf:
            sp = tf.name
        pid, master, _ = spawn([PY, probe], sp)
        buf, ok, status = wait_render(pid, master)
        if ok:
            os.write(master, key)
            status, buf = reaped_wait(pid, master, buf, 5)
        elif status is None:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        out = read_stdout_file(sp)
        os.unlink(sp)
        print(f"[g3] {probe} key={name}")
        print(f"[g3] child: {status_str(status)}")
        print(f"[g3] STDOUT FILE ({len(out)} bytes): {out!r}")
        print(f"[g3] pty tail: {buf[-120:]!r}")


def run_g4(probe):
    with tempfile.NamedTemporaryFile(suffix=".out", delete=False) as tf:
        sp = tf.name
    pid, master, _ = spawn([PY, probe], sp)
    buf, ok, status = wait_render(pid, master)
    if ok:
        os.write(master, b"\x1b[B\x1b[B\x1b[B")  # -> 2nd 'alpha' (idx3)
        time.sleep(0.4)
        os.write(master, b"\r")
        status, buf = reaped_wait(pid, master, buf, 5)
    elif status is None:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    out = read_stdout_file(sp)
    os.unlink(sp)
    print(f"[g4] {probe} (duplicate-label select)")
    print(f"[g4] child: {status_str(status)}")
    print(f"[g4] STDOUT FILE ({len(out)} bytes): {out!r}")
    print("[g4] NOTE: template returns the value ('alpha' either way); "
          "workagent returns the index (3 here). Ambiguity unresolvable by caller.")


def run_g5(probe):
    with tempfile.NamedTemporaryFile(suffix=".out", delete=False) as tf:
        sp = tf.name
    pid, master, _ = spawn([PY, probe], sp)
    buf, ok, status = wait_render(pid, master)
    if ok:
        os.write(master, b"jj")
        time.sleep(0.4)
        os.write(master, b"\r")
        status, buf = reaped_wait(pid, master, buf, 5)
    elif status is None:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    out = read_stdout_file(sp)
    os.unlink(sp)
    print(f"[g5] {probe} (j/k navigation)")
    print(f"[g5] child: {status_str(status)}")
    print(f"[g5] STDOUT FILE ({len(out)} bytes): {out!r}")
    print("[g5] NOTE: workagent jjj lands on idx2; questionary 'j' may act as "
          "vim-bind or type-ahead depending on version.")


if __name__ == "__main__":
    mode = sys.argv[1]
    probe = os.path.join(HERE, sys.argv[2])
    {"g1": run_g1, "g2": run_g2, "g3": run_g3, "g4": run_g4, "g5": run_g5}[mode](probe)
