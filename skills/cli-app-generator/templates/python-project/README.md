# mycli

One-line description: what it talks to and what it does.

## Install

```bash
uv tool install .            # or: pipx install .
uv sync                      # dev: venv + deps
uv run pytest                # tests (offline; HTTP mocked)
```

## Quick start

```bash
mycli init                                        # setup wizard: endpoint + token, saved as default
mycli list widgets                                # CSV with headers (default)
mycli list widgets --json | jq '.[0]'             # JSON instead
mycli profile create prod --url https://prod.example --default
mycli list widgets -p prod                        # switch org via --profile
mycli completions install                          # Tab completion: detects shell, edits rc idempotently
```

## Shell completion

```bash
eval "$(mycli completions show bash)"   # ~/.bashrc
eval "$(mycli completions show zsh)"    # ~/.zshrc (compinit handled by install)
mycli completions show fish | source    # fish config
```
`mycli completions install [bash|zsh|fish]` writes the eval line into your rc
file (`--rcfile` to override, `--yes` to skip confirmation); re-running is a
no-op. Subcommands and `--flags` complete automatically; profile/resource
values complete from local state (Tab cycles them like `git branch`).
Tradeoff: the eval line spawns Python on each new shell (~200–400ms) but never
goes stale when commands change.

## Configuration

| Precedence | Source | Example |
|---|---|---|
| 1 | CLI flag | `--profile prod`, `--timeout 10` |
| 2 | Env var | `MYCLI_URL`, `MYCLI_TOKEN`, `MYCLI_PROFILE` |
| 3 | Default profile | `mycli profile use prod` |
| 4 | Built-in | `timeout 30s`, `retries 3` |

Profiles are JSON files (0600) under `~/.config/mycli/profiles/` — secrets never
appear in flags (shell history), logs, or code. Override the dir with
`MYCLI_CONFIG_DIR`.

## Exit codes

`0` success · `1` runtime error · `2` usage error · `3` network/timeout.

## Security notes

- Tokens live only in 0600 profile files or env vars — never in flags, logs, or code.
- Proxy env with bare `socks://` is normalized to `socks5://` automatically (httpx compatibility).
