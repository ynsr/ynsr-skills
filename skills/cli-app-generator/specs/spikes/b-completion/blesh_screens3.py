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
    ("A: 'tool ' Tab -> subcommand menu", b"tool \t", 2.0),
    ("B: C-c (abort -> fresh prompt)", b"\x03", 1.2),
    ("C: 'tool items --pick ' Tab -> dynamic menu", b"tool items --pick \t", 2.2),
    ("D: Tab#2 -> accept first", b"\t", 1.5),
    ("E: C-c (fresh prompt)", b"\x03", 1.2),
    ("F: 'tool show a' Tab -> single dynamic match inserts", b"tool show a\t", 2.2),
    ("G: C-c (fresh prompt)", b"\x03", 1.2),
    ("H: 'tool i' Tab -> prefix insert", b"tool i\t", 2.2),
    ("I: C-c (fresh prompt)", b"\x03", 1.2),
    ("J: 'tool show x' Tab -> no match (empty menu state)", b"tool show x\t", 2.2),
    ("K: C-c, then type 'tool items' + RET to prove shell still healthy", b"\x03tool items\r", 2.5),
]
run(keys, "blesh_screens3.txt")
print(open("blesh_screens3.txt").read())
