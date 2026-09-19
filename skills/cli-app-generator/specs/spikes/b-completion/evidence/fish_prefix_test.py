import os, pty, time, select, fcntl, termios, struct, signal
import pyte
screen = pyte.Screen(120, 35); stream = pyte.Stream(screen)
pid, fd = pty.fork()
if pid == 0:
    os.execvp("env", ["env","HOME=/tmp/spikehome","TERM=xterm-256color",
        "PATH=/home/bs/projects/personal/ynsr-skills/.worktrees/cli-app-generator-v2/skills/cli-app-generator/specs/spikes/b-completion/bin:/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin",
        "SPIKE_ITEMS_DIR=/tmp/spikehome/.config/spike-items","fish"])
fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 35, 120, 0, 0))
def pump(d):
    end=time.time()+d
    while time.time()<end:
        r,_,_=select.select([fd],[],[],0.05)
        if r:
            try: stream.feed(os.read(fd,65536).decode("utf-8","replace"))
            except OSError: return
pump(12.0)
os.write(fd, b"tool i\t"); pump(2.5); pump(0.3)
print("SCREEN AFTER 'tool i'+Tab:")
print("\n".join(l for l in screen.display if l.strip()))
os.write(fd, b"show a\t"); pump(2.5); pump(0.3)
print("SCREEN AFTER append 'show a'+Tab:")
print("\n".join(l for l in screen.display if l.strip()))
os.kill(pid, signal.SIGHUP)
