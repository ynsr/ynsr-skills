import os, pty, time, select, fcntl, termios, struct, signal
pid, fd = pty.fork()
if pid == 0:
    os.execvp("env", ["env","HOME=/tmp/spikehome","TERM=xterm-256color",
        "PATH=/home/bs/projects/personal/ynsr-skills/.worktrees/cli-app-generator-v2/skills/cli-app-generator/specs/spikes/b-completion/bin:/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin",
        "SPIKE_ITEMS_DIR=/tmp/spikehome/.config/spike-items","fish"])
fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 35, 120, 0, 0))
def pump(d):
    out=b""; end=time.time()+d
    while time.time()<end:
        r,_,_=select.select([fd],[],[],0.05)
        if r:
            try: out+=os.read(fd,65536)
            except OSError: return
    return out
pump(12.0)
pump(0.5)
out = pump(0.1)
os.write(fd, b"tool i\t")
o = pump(3.0)
print("AFTER 'tool i'+Tab raw:")
print(repr(o[-1500:]))
os.kill(pid, signal.SIGHUP)
