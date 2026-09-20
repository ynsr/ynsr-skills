# Per-tier stacks and audience add-ons

Libraries verified per `DECISIONS.md` rows A–F (release ≤12 months, permissive license, live-proven in `specs/spikes/`).

## Python (single-file and project)

| Concern | Library | Notes |
|---|---|---|
| CLI parsing | typer 0.27.2 (MIT) | pin `>=0.27.2`; keep 3-line `completion_init()` workaround |
| Output/help | rich | panels for help; table/CSV/TSV emitter in `output.py` |
| HTTP | httpx (+`socks` extra) | one client factory; normalize `socks://`→`socks5://` there |
| Retry | own helper (tenacity/stamina acceptable) | 3 attempts + exponential backoff |
| Config | platformdirs + tomllib | precedence flag > env > profile > default |
| Picker | questionary 2.1.1 + wrapper | stderr render, non-TTY → usage error, Ctrl-C → 130; see DECISIONS.md row A |
| Lint/tests | ruff, pytest | mock-transport tests run offline |

## Bash (bashly, DECISIONS row D)

Generate with [bashly](https://bashly.dannyb.co/) from YAML: standalone single-file script, runs on bash ≥4.2 alone (verified under `env -i`). Completions via `completely` (single static file — no per-Tab fork; ble.sh-safe). Richer YAML (examples, defaults, allowed-list validation) maps onto the universal contract; unknown keys fail loudly at generation.

## Go (DECISIONS row E)

| Concern | Library |
|---|---|
| CLI/help/version/completion/man | cobra v1.10.2 + fang v2.0.1 |
| Pickers/forms | huh v2.0.3 behind wrapper (WithOutput(stderr) + isatty guard + NO_COLOR→ThemeBase + abort→130) |
| Table/CSV/TSV | go-pretty v6.8.3 (JSON via stdlib) |
| Retry | own 36-LOC `RetryClient` helper (3 attempts + backoff) — NOT retryablehttp (15 mo old, MPL-2.0) |
| Lint | golangci-lint v2.13.2 (dev only) |
| Logging | slog to stderr |

## Audience add-on matrix (spec §2.4 — tier-scoped)

| Add-on | bash | single-file | python-project | go |
|---|---|---|---|---|
| `--profiles` + wizard | — | — | ✓ | ✓ |
| `--service` (systemd) | — | — | — | ✓ |
| env-var config | ✓ | ✓ | ✓ | ✓ |

Agent audience additionally enables: `--fields`, `--limit`, `schema`/`commands` introspection subcommand, JSON error envelope. Human audience: pretty tables by default, pager for long output, did-you-mean hints.

## Template size guidance

Bash escalation ceiling: a tool exceeding ~300 LOC or needing real data structures → escalate to Python.
