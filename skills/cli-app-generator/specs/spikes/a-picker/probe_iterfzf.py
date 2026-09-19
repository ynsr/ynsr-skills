"""Probe: iterfzf 1.9.0.67.0. REJECTED on license (GPL-3.0-or-later);
probed only to measure integration LOC + vendors-own-fzf evidence."""
import subprocess
import sys

from iterfzf import iterfzf

from menu import MENU


def pick():
    lines = [f"{key}\t{desc}" if desc else key for key, desc in MENU]
    try:
        sel = iterfzf(lines, print_query=False)
    except subprocess.CalledProcessError:   # fzf exits 130 on SIGINT / errors w/o tty
        return None
    if sel is None:
        return None
    return sel.split("\t")[0]


if __name__ == "__main__":
    print(f"RESULT:{pick()}")
