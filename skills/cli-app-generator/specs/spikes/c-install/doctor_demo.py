#!/usr/bin/env python3
"""Slim doctor (spike C draft): prints `status: ok|missing`; stale is never emitted."""
import argparse
import importlib.util
import json
import tomllib
import urllib.request
from pathlib import Path


def _importable(name):
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def main():
    p = argparse.ArgumentParser(prog="doctor")
    p.add_argument("--config", default="", metavar="TOML")
    p.add_argument("--ping", action="store_true", help="require connectivity")
    p.add_argument("--json", action="store_true", help="single-line dict for cli-hub")
    a = p.parse_args()
    checks = [(f"dep {d}", _importable(d), "") for d in ("tomllib", "rich", "httpx")]  # tool's deps
    cfg = Path(a.config).expanduser() if a.config else None
    if cfg and cfg.is_file():
        try:
            tomllib.loads(cfg.read_text(encoding="utf-8"))
            checks.append(("config", True, ""))
        except (tomllib.TOMLDecodeError, OSError) as e:
            checks.append(("config", False, str(e)))
    elif cfg:
        checks.append(("config", False, f"not found: {cfg}"))
    else:
        checks.append(("config", True, "defaults"))
    if a.ping:
        try:
            urllib.request.urlopen("https://pypi.org/simple/", timeout=3).close()
            checks.append(("connectivity", True, ""))
        except OSError as e:
            checks.append(("connectivity", False, str(e)))
    status = "ok" if all(ok for _, ok, _ in checks) else "missing"
    if a.json:
        print(json.dumps({"status": status, "message": "; ".join(n for _, ok, n in checks if not ok and n)}))
    else:
        print(f"status: {status}")
        for name, ok, note in checks:
            print(f"  {'ok ' if ok else 'FAIL'} {name}" + (f": {note}" if note else ""))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
