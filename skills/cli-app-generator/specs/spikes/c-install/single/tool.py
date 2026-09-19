#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["rich>=13.7"]
# ///
"""Spike C single-file PEP 723 demo: symlink-installed, runs from any cwd."""

from rich import print as rprint


def main() -> int:
    rprint({"tool": "spikec-single", "version": "0.1.0", "mode": "symlink"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
