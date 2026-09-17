# Commands, architecture, and module map for AI agents working on mycli.

## Build / test / run

```bash
uv sync                      # create .venv with deps
uv run pytest                # full suite (offline; httpx.MockTransport)
uv run pytest tests/unit -q  # unit only
uv run pytest --cov=mycli    # coverage (target >=75% on core logic)
```

All tests pass offline — HTTP is mocked with httpx.MockTransport. Never write tests that hit a real server.

## Architecture (end-to-end)

1. `cli.py` — Typer app; parses args, resolves active profile via `config.resolve_profile()`, dispatches to ops, prints CSV/JSON to stdout / logs to stderr.
2. `config.py` — profile store: `~/.config/mycli/profiles/*.json` (0600). Resolution order: env vars > `--profile` flag > default profile. Raises `ProfileError` with actionable messages.
3. `client.py` — httpx.Client wrapper: injects Bearer auth, normalizes `socks://` proxy env to `socks5://` before client build, retry with exponential backoff on 5xx/429/timeouts/connect errors, request+response logging to stderr when verbose.
4. `ops.py` — business operations shared by CLI and tests: request builders, response parsing, error mapping.
5. `completions.py` + `cli.py` completions group — shell scripts via Click (`show`), idempotent rc install (`install`), `autocompletion=` value callbacks (profiles). No hand-coded ordering.
6. `doctor.py` + `cli.py` doctor command — install-receipt self-check: compares `~/.local/share/mycli/install-receipt.json` (written by install.sh; SHA-256 over source `*.py`, 12 hex chars) against the live tree; exit 0 in sync / 1 stale-missing with the fix command. Keep the hashing identical to install.sh.

## Conventions

- Primary audience: AI agents — CSV with a header row defaults for lists/structured data; `--json` opts into JSON.
- stdout carries ONLY command output (CSV/JSON); every log/progress line goes to stderr — `--json` pipes into `jq` must never break.
- Destructive ops require `--yes` non-interactively; a missing `--yes` exits 2 (usage).
- Exit codes: 0 success · 1 general/runtime error · 2 usage error · 3 network/timeout.
- No credentials in code or tests; profile files hold them locally under the user's config dir only.
