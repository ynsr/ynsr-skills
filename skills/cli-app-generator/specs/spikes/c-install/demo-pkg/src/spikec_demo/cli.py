"""Spike C demo console script — line below is EDITED during the spike."""

LABEL = "spikec-demo 0.1.0 (POST-EDIT: EDIT PROPAGATED)"


def main() -> int:
    print(LABEL)
    if len(_argv) > 1 and _argv[1] == "doctor":
        if "--json" in _argv:
            print('{"status": "ok", "message": "spikec-demo health"}')
        else:
            print("status: ok")
            print("deps: ok (demo)")
    return 0


from sys import argv as _argv  # noqa: E402 (kept at bottom so the edit target stays line 2)
