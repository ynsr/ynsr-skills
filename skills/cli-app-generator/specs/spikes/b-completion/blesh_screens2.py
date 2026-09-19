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
        os.write(fd, kb); pump(wait); pump(0.3)
        log.write(f"===== {label} =====\n")
        for i,line in enumerate(screen.display):
            if line.strip(): log.write(f"{i:2d}| {line.rstrip()}\n")
        log.write("\n")
    os.kill(pid, signal.SIGHUP)
    log.close()

keys = [
    ("A: 'tool ' Tab (subcommands)", b"tool \t", 2.0),
    ("B: ESC dismiss menu", b"\x1b", 1.2),
    ("C: Enter (empty line -> fresh prompt)", b"\r", 1.5),
    ("D: 'tool items --pick ' Tab (dynamic values)", b"tool items --pick \t", 2.2),
    ("E: ESC, Enter (fresh prompt)", b"\x1b\r", 1.5),
    ("F: 'tool show a' Tab (single dynamic match)", b"tool show a\t", 2.2),
    ("G: ESC, Enter (fresh prompt)", b"\x1b\r", 1.5),
    ("H: 'tool i' Tab (prefix insert)", b"tool i\t", 2.2),
    ("I: ESC, Enter (fresh prompt)", b"\x1b\r", 1.5),
    ("J: 'tool s' Tab (prefix for show)", b"tool s\t", 2.2),
]
run(keys, "blesh_screens2.txt")
print(open("blesh_screens2.txt").read())
