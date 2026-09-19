"""Drive an interactive shell in a pty; feed keystrokes; capture transcript."""
import os, pty, sys, time, select, fcntl, termios, struct, signal

def drive(cmd, keystrokes, out_path, cols=120, rows=35, settle=1.2, max_wait=90):
    """keystrokes: list of (label, bytes, wait_seconds_after). Writes transcript to out_path."""
    pid, fd = pty.fork()
    if pid == 0:  # child
        os.execvp(cmd[0], cmd)
    # parent
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    transcript = []
    buf = b""
    def pump(dur):
        nonlocal buf
        end = time.time() + dur
        while time.time() < end:
            r, _, _ = select.select([fd], [], [], 0.1)
            if r:
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    return False
                if not chunk:
                    return False
                buf += chunk
        return True
    pump(0.5)  # initial output
    for label, keys, wait in keystrokes:
        os.write(fd, keys)
        pump(wait)
        transcript.append(f"### STEP {label}\n--- keystrokes: {keys!r}\n--- transcript tail ---\n")
        transcript.append(buf.decode("utf-8", "replace"))
        buf = b""
    # final drain
    pump(settle)
    transcript.append("### FINAL DRAIN\n")
    transcript.append(buf.decode("utf-8", "replace"))
    try:
        os.kill(pid, signal.SIGHUP)
    except ProcessLookupError:
        pass
    try:
        os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass
    with open(out_path, "w") as f:
        f.write("".join(transcript))
    return out_path

if __name__ == "__main__":
    rcfile, out_path, script_name = sys.argv[1], sys.argv[2], sys.argv[3]
    rc = f"source {rcfile}"
    cmd = ["env", "HOME=/tmp/spikehome", "TERM=xterm-256color", "SPIKE_ITEMS_DIR=/tmp/spikehome/.config/spike-items",
           "bash", "--rcfile", f"<(echo '{rc}')", "-i"]
    # --rcfile <(...) requires bash to exec the substitution itself; env execs bash fine
    keys = [
        ("type 'tool ' + Tab (subcommand completion)", b"tool \t", 2.0),
        ("Tab again (cycle/list)", b"\t", 2.0),
        ("type 'items --pick ' + Tab (dynamic flag value)", b"items --pick \t", 2.5),
        ("Tab again", b"\t", 2.0),
        ("type 'show a' + Tab (dynamic arg, single match -> insert)", b"\nshow a\t", 2.5),
    ]
    drive(cmd, keys, out_path)
    print("wrote", out_path)
