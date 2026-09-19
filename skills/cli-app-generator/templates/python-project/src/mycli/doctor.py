"""Doctor: status-only self-check. First line `status: ok|missing` — cli-hub consumes it (never 'stale')."""

import importlib.util
import json
import tomllib

from .config import config_dir

_DEPS = ("typer", "httpx", "pydantic", "platformdirs", "questionary", "tenacity")


def _missing_dep(name: str) -> str:
    try:
        return "" if importlib.util.find_spec(name) else f"dep {name} not installed"
    except (ImportError, ValueError):
        return f"dep {name} not installed"


def run(as_json: bool = False) -> int:
    """Print status; return exit code (0 ok, 1 missing)."""
    problems = [m for m in (_missing_dep(d) for d in _DEPS) if m]
    try:
        tomllib.loads((config_dir() / "config.toml").read_text())
    except FileNotFoundError:
        pass
    except (tomllib.TOMLDecodeError, OSError) as e:
        problems.append(f"config: {e}")
    status = "ok" if not problems else "missing"
    if as_json:
        print(json.dumps({"status": status, "message": "; ".join(problems)}))
    else:
        print(f"status: {status}")
        for problem in problems:
            print(f"  FAIL {problem}")
    return 1 if problems else 0
