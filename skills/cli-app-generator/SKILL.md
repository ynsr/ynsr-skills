---
name: cli-app-generator
description: Generate CLI tool/app/script explicitly requested by user. Ignore for ad-hoc ephemeral one-off scripts
---

# CLI App Generator

Governs how to build a CLI tool when the user wants something reusable — not throwaway diagnostics.

## Step 0: Is this actually a "tool" request?

- **Use this skill**: "write a script that reconciles X against Y", "build a CLI tool for downloading movies from these sites", "make a tool that queries logs in a time range"
- **Skip it, just answer inline**: "quick script to check if this table has duplicates", "one-liner to see what's in this log"

If ambiguous, default to treating it as a real tool — better to over-deliver structure than leave a script that has to be rebuilt later.

## Step 1: Ask for missing required inputs — don't guess

Before writing code, check whether the tool needs any of: credentials/connection info, target paths, API endpoints, or other inputs that materially change behavior and weren't given. If a required or high-impact option is missing, **stop and ask the user interactively** rather than inventing a placeholder or a silent default. Non-critical options (things with a genuinely safe default, like `--timeout`) don't need to be asked — just default them and mention the default in `--help`.

## Step 2: Pick the tier

Decide from complexity signals, not a line-count guess.

| Tier | Use when | Runtime |
|---|---|---|
| **Bash** | Single concern, orchestrating existing CLI tools (`jq`, `curl`, `psql`, `git`), no real data structures | `bash` |
| **Python, single-file** | Real argument parsing (subcommands, many flags), structured data (JSON/CSV/dict), retry/backoff logic, or bash would be unreadable/unsafe | `uv run script.py` via **PEP 723 inline metadata** — no project scaffolding |
| **Python, full project** | >~1000 lines, multiple modules, needs install/distribution beyond one machine, or plugin-style architecture | `uv` for deps, `pipx install .` for the entry point |
| **Go** | Must keep running: listens on a port, background service/daemon, survives independent of a shell session | Standard Go layout, likely a systemd unit |

Prefer Python over bash once you're parsing structured output, handling more than 2-3 error branches, or doing non-trivial conditionals — bash error handling degrades fast past that point.

**Single-file Python (PEP 723)** — the tier people skip. Real deps, no project ceremony:
```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "typer"]
# ///
```
Default to this for the Python tier unless the user wants it installed elsewhere.

**Full Python project:**
```
tool-name/
├── pyproject.toml       # uv-managed, console_scripts entry point
├── README.md
├── AGENTS.md
├── src/tool_name/{__init__.py,cli.py,...}
└── tests/{unit,e2e}/
```
Install via `pipx install .` (or `--editable .` while iterating) — note this in the README.

**Go project:**
```
tool-name/
├── go.mod
├── README.md
├── AGENTS.md
├── cmd/tool-name/main.go
├── internal/
└── *_test.go beside the code they cover
```
For anything meant to survive a reboot or run unattended, generate a systemd unit alongside it (see the systemd rules below).

### README.md and AGENTS.md (full projects)

**README.md**: one-line description up top (short enough as a GitHub repo description) → Introduction (plain-terms problem it solves) → Install → Uninstall → Usage (real commands) → Caveats (known limits, footguns) → short How It Works.

**AGENTS.md**: exact build/test commands (copy-pasteable), how the app works end to end, and a responsibility→module map (e.g. "retry logic → `internal/retry`") so an agent can find the right file without grepping the whole tree.

### Install/uninstall scripts

Generate separate `install.sh`/`uninstall.sh` when the tool is bash-based (no package manager to lean on) or install involves more than copying one file (config dirs, systemd unit, venv, completions). Idempotent, safe to re-run; `uninstall.sh` reverses everything `install.sh` created, including disabling/removing a systemd service.

### systemd-managed services

Typically the Go tier. Default to a **user-scoped service** (`~/.config/systemd/user/`, `systemctl --user`) — system-wide only if explicitly requested or domain-required (pre-login start, privileged port, multi-user). `install` must also check/enable lingering (`loginctl show-user $USER --property=Linger`; if not on, `loginctl enable-linger $USER`) — without it a user service dies at logout, silently defeating the point. Ship dedicated lifecycle subcommands — `tool-name service install|uninstall|start|stop|restart|status|logs` — wrapping the unit file + `systemctl --user`/`journalctl --user` calls so the user never hand-writes them.

## Step 3: Cross-cutting rules (every tier)

**Idempotency.** Re-running with the same inputs must be safe and non-duplicating: check state before mutating, use atomic writes (temp file + rename), and if a step truly can't be idempotent, use a marker/lock file to block re-execution rather than silently repeating it.

**Dry-run for anything destructive.** "Destructive" = deletes/overwrites files, writes to a DB, calls an API with side effects (POST/PUT/PATCH/DELETE), or is otherwise hard to undo.
- `--dry-run` prints exactly what *would* happen — actual records/requests, not just "would proceed"
- destructive actions require `--yes`/`--force` to actually execute; never run unattended by default

**Standard flags, every tool:**
- `-h`/`--help` — full usage, one example per major use case with real args, and exit code meanings. Write it like documentation for another AI agent reading it cold.
- `--version`
- `-v`/`--verbose`, `-q`/`--quiet`
- `--json` where output is structured — **only valid if logs/progress go to stderr and stdout carries just the output.** Mixing status lines into stdout silently breaks piping into `jq` or agent consumption.
- `--yes`/`--force` to bypass confirmation prompts (needed for non-interactive/agent use)

**In-place progress for anything iterative/long-running.** Downloading a file, processing a batch, walking a list of items — update a single line in place (`\r`, no newline until done) rather than a new line per item, showing real detail (percentage, current item, N/total). Only when stdout is a TTY and `--quiet`/`--json` aren't set — never emit `\r` into piped/JSON output; fall back to periodic plain-line updates (e.g. every 10% or every N items) for non-TTY output like logs or `nohup`. Print a final newline on completion/error so the last state survives in scrollback.

**Exit codes.** Small consistent convention, documented in `--help`: `0` success, `1` general error, `2` usage error, and add more (e.g. `3` network/timeout, `4` partial success) if failure modes meaningfully differ.

**Network operations.** Every network call gets `--timeout`, `--retries`, `--retry-delay` (exponential backoff between retries), exposed as flags with sane defaults rather than hardcoded.

**Secrets and config.** Never hardcode credentials or endpoints. Read from env vars or a config file, document which ones in `--help`, and fail immediately with a clear message if something required is missing.

**Non-interactive by default.** Nothing blocks on stdin unless the tool is explicitly interactive. Confirmation prompts only guard destructive actions; `--yes` bypasses them.

**Bash baseline** (when bash is chosen): `set -euo pipefail`, a `trap` for cleanup, shellcheck-clean. Reaching for associative-array-of-arrays or real JSON parsing is a signal to switch to Python.

**Extensibility via composition.** When a tool will plausibly grow new targets (sites, data sources, backends), use a registry/strategy pattern from the start: one small module/function per target behind a common interface, dispatched via a lookup table. Document the extension point in code so adding one later is localized, not a refactor.

**Testing scales with tier.** Trivial bash: none needed. Reused bash: consider `bats`. Python (either tier): pytest covering non-trivial logic. Go: `go test`, table-driven where it fits. Full projects target **≥75% coverage on core logic** (`pytest --cov` / `go test -cover`), excluding thin CLI wiring/`main()` — skip the target where it'd force excessive mocking that makes tests worse than none; fast real e2e tests beat inflated unit coverage. Self-check once with the coverage tool; treat as a target, not a blocking gate.

## Step 4: Where it lives

Standalone scripts (bash, single-file Python) go to `~/.local/bin/`, made executable, no extension on the installed copy — unless the user has already established a different convention in this conversation. Full projects get their own directory and are installed via `pipx install .` / `go install`, not copied by hand.

## Step 5: Version control

For anything that gets its own directory (full Python/Go projects, or a multi-file bash tool with install scripts) — not a single standalone script:

- **`.gitignore` matched to the tier**: Python → `__pycache__/`, `.venv/`, `.pytest_cache/`, `dist/`, `*.egg-info/` (commit `uv.lock`, don't ignore it); Go → build binaries (commit `go.sum`); plus editor/OS cruft. Also ignore real secrets (`.env`, local creds) from the start, not added after the first commit.
- **`git init` + initial commit** for these projects — local bookkeeping, do it without asking.
- **If there's no remote yet**, suggest (don't do) creating a GitHub repo and pushing — an account-touching action needing the user's go-ahead. Use a connected GitHub tool if available, otherwise give the exact `gh repo create`/`git remote add`/`git push` commands. Only for durable multi-file tools, and only after confirming `.gitignore` actually excludes secrets.

## Output

Deliver the working file(s), `chmod +x` scripts, and exercise `--help`, `--dry-run` (if applicable), and one real invocation yourself before handing it over. If install/uninstall scripts or a systemd service subcommand exist, run through those too — install, check `status`, uninstall — rather than handing over untested lifecycle management.