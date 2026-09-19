"""Drive bash+ble.sh in a pty; render final screen via pyte after each Tab."""
import os, pty, time, select, fcntl, termios, struct, signal
import pyte

def run(keys, out):
    screen = pyte.Screen(120, 35)
    stream = pyte.Stream(screen)
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp("env", ["env","HOME=/tmp/spikehome","TERM=xterm-256color","bash","--rcfile","rc_blesh.sh","-i"])
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 35, 120, 0, 0))
    def pump(d):
        end=time.time()+d
        while time.time()<end:
            r,_,_=select.select([fd],[],[],0.05)
            if r:
                try: stream.feed(os.read(fd,65536).decode("utf-8","replace"))
                except OSError: return
    pump(3.0)
    log=open(out,"w")
    for label, kb, wait in keys:
        os.write(fd, kb); pump(wait)
        pump(0.3)
        log.write(f"===== {label} =====\n")
        for i,line in enumerate(screen.display):
            if line.strip(): log.write(f"{i:2d}| {line.rstrip()}\n")
        log.write("\n")
    os.kill(pid, signal.SIGHUP)
    log.close()

keys = [
    ("A: 'tool ' Tab#1 (subcommands)", b"tool \t", 2.0),
    ("B: Tab#2 (cycle)", b"\t", 1.5),
    ("C: Ctrl-U 'tool items --pick ' Tab#1 (dynamic)", b"\x15tool items --pick \t", 2.2),
    ("D: Tab#2", b"\t", 1.5),
    ("E: ESC dismiss", b"\x1b", 1.0),
    ("F: Ctrl-U 'tool show a' Tab (single match)", b"\x15tool show a\t", 2.2),
    ("G: Ctrl-U 'tool i' Tab (prefix)", b"\x15tool i\t", 2.2),
]
run(keys, "blesh_screens.txt")
print(open("blesh_screens.txt").read())
