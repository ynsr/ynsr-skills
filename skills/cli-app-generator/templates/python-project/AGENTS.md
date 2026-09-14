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
5. `cli.py` subcommand wiring: `init` (setup wizard), `list`, `profile` (create/list/use/remove).

## Conventions

- stdout carries ONLY command output (CSV/JSON); every log/progress line goes to stderr — `--json` pipes into `jq` must never break.
- Destructive ops require `--yes` non-interactively; a missing `--yes` exits 2 (usage).
- Exit codes: 0 success · 1 general/runtime error · 2 usage error · 3 network/timeout.
- No credentials in code or tests; profile files hold them locally under the user's config dir only.
