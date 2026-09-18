---
name: cli-app-generator
description: Generate or update a CLI tool/app/script explicitly requested by user. Ignore for ad-hoc ephemeral one-off scripts
---

# CLI App Generator

Governs how to build a CLI tool when the user wants something reusable — not throwaway diagnostics.

## Step 0: Is this actually a "tool" request?

- **Use**: "script that reconciles X against Y", "build a CLI tool for downloading movies", "tool that queries logs in a time range"
- **Skip, answer inline**: "quick script to check if this table has duplicates", one-liners

Ambiguous → treat as a real tool.

## Step 1: Ask for missing required inputs — don't guess

Before writing code: missing required/high-impact inputs (credentials, target paths, API endpoints) → **stop and ask interactively**; never invent a placeholder or silent default. Options with a genuinely safe default (`--timeout`) → just default them and mention it in `--help`.

## Step 2: Identify the audience — AI agents or humans?

Decide before writing code. The request is clear only if it names who consumes the output ("for my terminal use", "for agents to call"); otherwise **stop and ask** — "CLIs get piped anyway" and "CSV is the safe default" are guessing. Updating an existing CLI → read the audience line from its AGENTS.md; missing → ask. Recording the audience is required: full projects in AGENTS.md (see below), standalone scripts in the `--help` epilog.

- **AI agents**: machine-parseable defaults — CSV with a header row for lists/structured data (`--json` opts into JSON), stable documented exit codes, non-interactive. No pretty-printing by default.
- **Human users**: experience-first — pretty-printed tables/lists (Rich), formatted and colored help, readable progress, confirmations before destructive actions; `--csv`/`--json` opt-in flags for scripting.

## Step 3: Pick the tier

| Tier | Use when | Runtime |
|---|---|---|
| **Bash** | Single concern, orchestrating existing CLI tools (`jq`, `curl`, `psql`, `git`), no real data structures | `bash` |
| **Python, single-file** | Real argument parsing, structured data, retry/backoff logic, or bash would be unreadable/unsafe | `uv run script.py` via PEP 723 inline metadata |
| **Python, full project** | >~1000 lines, multiple modules, install/distribution beyond one machine, or plugin architecture | `uv` deps, `pipx install .` entry point |
| **Go** | Must keep running: port listener, background service/daemon | Standard layout, likely a systemd unit |

Prefer Python over bash once parsing structured output, >2-3 error branches, or non-trivial conditionals — bash error handling degrades fast.

**Single-file Python (PEP 723)**:
```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "typer"]
# ///
```
Default for the Python tier unless the user wants it installed elsewhere.

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
For anything that must survive reboot or run unattended, add a systemd unit (see below).

Templates: `templates/python-project/` (profiles, setup wizard, completions, doctor/receipt, mock-transport offline tests) and `templates/python-single-file/` (one file + install/uninstall scripts with receipt, registration, dev-warning). Copy them rather than reinventing; Bash/Go templates don't exist yet — follow the layouts above.

### README.md and AGENTS.md (full projects)

**README.md**: one-line description up top (GitHub-repo short) → Introduction → Install → Uninstall → Usage (real commands) → Caveats → short How It Works.

**AGENTS.md**: opens with the audience line (e.g. `Primary audience: AI agents — CSV/JSON output, non-interactive`), then copy-pasteable build/test commands, end-to-end architecture, and a responsibility→module map ("retry logic → `internal/retry`") so an agent finds the right file without grepping. Add a line referencing this skill (`cli-app-generator`) so future agents follow its conventions.

### Install/uninstall scripts

**Required by default** (unless the user explicitly declined): idempotent, re-runnable `install.sh` + `uninstall.sh` adapted from the templates — never prose instructions. `uninstall.sh` reverses everything `install.sh` created (package, completions, cron/systemd units, tool config, receipt).

**Stale-install guard (Python project tier).** `uv tool install`/`pipx install` snapshot source into an isolated venv — edits never reach the installed binary until reinstall. So: `install.sh` writes `~/.local/share/<tool>/install-receipt.json` (SHA-256 over source `*.py`, 12 hex) and runs `<tool> doctor` as a self-check; `doctor` exits 0 in sync, 1 with the fix command when stale/missing (path must honor `$HOME` so tests can redirect it); every invocation warns on stderr when running from a working tree whose hash differs from the receipt — never from the installed copy. One canonical installer (uv preferred, pipx fallback) — mixing both fights over `~/.local/bin`.

### cli-hub registration

Every CLI self-registers with [cli-hub](https://github.com/ynsr/cli-agents-config/tree/main/tools/cli-hub) so skill-generated tools stay discoverable from one entry point: `install.sh` ends with a guarded best-effort `cli-hub register` (hub absent → never fail the install; fill `--version`, `--description`, `--group` (domain noun: `git|media|db|net|meta|misc`), `--source-path`, `--repo` (empty when none), `--config-path`, `--uninstall`/`--reinstall`), `uninstall.sh` ends with guarded `cli-hub unregister`. Register the **scripts**, not inline backend commands: hub reinstall/uninstall re-run `install.sh`/`uninstall.sh`, which detect the backend themselves (uv or pipx — never hardcode) and rewrite the receipt; inline `pipx install --force` hooks leave `doctor` reporting stale forever. User declines scripts → run the equivalent register inline once after copying to `~/.local/bin/`. The hub self-monitors: `prune` catches missing binaries, `cli-hub doctor` runs `<tool> doctor` per entry — keep the `status: ok|stale|missing` output contract.
Long-form mechanics (receipt scheme, register block + field sources, hub self-monitoring, full completion contract): `references/install-and-completion-internals.md`.

### systemd-managed services

Default to a **user-scoped** service (`~/.config/systemd/user/`, `systemctl --user`); system-wide only if explicitly requested or domain-required. `install` checks/enables lingering (`loginctl enable-linger $USER`) — without it the service dies at logout. Ship lifecycle subcommands — `tool-name service install|uninstall|start|stop|restart|status|logs` — wrapping the unit + `systemctl --user`/`journalctl --user`, so nobody hand-writes them.

## Step 4: Cross-cutting rules (every tier)

**Idempotency.** Re-running with the same inputs is safe and non-duplicating: check state before mutating, atomic writes (temp + rename), marker/lock file when a step truly can't be idempotent.

**Dry-run for anything destructive** (deletes/overwrites files, DB writes, side-effecting API calls, otherwise hard to undo): `--dry-run` prints the actual records/requests it *would* use — and execution requires `--yes`/`--force`.

**Standard flags, every tool:** `-h`/`--help` (full usage, one real-arg example per major use case, exit-code meanings, config file path — written for a cold reader matching the Step 2 audience), `--version`, `-v`/`-q`, `--json`, `--yes`/`--force` to bypass confirmations.

**Output format** (defaults follow the Step 2 audience): AI-agent tools — lists/tables default to CSV with a header row, `--json` opts into JSON; human tools — pretty tables by default, `--csv`/`--json` opt into machine formats. Always: **stdout carries output only — every log/progress line goes to stderr**; mixing status into stdout silently breaks `jq`/agent piping.

**In-place progress** for anything iterative/long-running: single line updated in place (`\r`, percentage, current item, N/total) — only on a TTY with `--quiet`/`--json` unset; never emit `\r` into piped/JSON output (non-TTY → periodic plain-line updates). Final newline on completion/error.

**Exit codes** documented in `--help`: `0` success, `1` general error, `2` usage; more (e.g. `3` network/timeout, `4` partial success) only if failure modes meaningfully differ.

**Network operations:** every call gets `--timeout`, `--retries`, `--retry-delay` (exponential backoff) as flags with sane defaults, not hardcoded.

**Secrets and config:** never hardcode credentials/endpoints — env vars or config files, documented in `--help`; required-but-missing → fail immediately with a clear message.

**Env vars** for stable settings (endpoint, token, profile override): precedence CLI flag > env var > profile > built-in default.

**Proxy env:** normalize `socks://` → `socks5://` in ALL_PROXY/HTTP(S)_PROXY before building an httpx client — it raises `ValueError: Unknown scheme` otherwise (see `templates/python-project/src/mycli/client.py`).

**Help rendering (Python):** Typer + Rich panels; docstring's first paragraph is the one-liner; real commands under `Example:`.

**Profiles:** multi-source/org tools get named profiles (create/list/use/remove) + `--profile` on every command; no flag = stored default. Secrets via env vars or 0600 files — never flags (shell history), code, or logs.

**Setup wizard:** `tool init` walks first-run config (endpoint → auth → default profile), saves, verifies with one live call, offers completion install.

**Shell completion** (every Python CLI — see `templates/python-project/src/mycli/completions.py`): construct with `add_completion=False`; ONE system — `completions show <bash|zsh|fish>` (eval-line init script) + `install [shell] [--yes]` (idempotent marker-block rc edit: atomic write, `.bak`, stale-block replace, not duplicate; zsh block ensures `compinit`; no shell arg → detect `$SHELL`; TTY confirm before editing the rc). Never hand-code completion order — Click resolves subcommands/flags from cursor position. Custom code only `autocompletion=` callbacks for dynamic values (profile/resource names): filter on the `incomplete` prefix, read local state only, return `[]` on any failure so Tab never breaks. Typer >= 0.27 with `add_completion=False` breaks the env-var completion server ("Shell bash not supported." per keystroke under ble.sh) — templates ship `ensure_completion_classes()`; call it in `main()` before `app()` and keep `2>/dev/null` in the sourced eval line. Full contract + tests: `references/install-and-completion-internals.md`.
**Interaction model:** non-interactive by default — nothing blocks on stdin unless explicitly interactive. Required choice (profile, resource id) missing + TTY → list options and prompt; non-TTY/`--yes` → fail with an actionable message. Confirmation prompts guard only destructive actions.

**Bash baseline:** `set -euo pipefail`, `trap` cleanup, shellcheck-clean. Associative-array-of-arrays or real JSON parsing → switch to Python.

**Testing scales with tier.** Trivial bash: none. Reused bash: `bats` or inline e2e (`references/e2e-bash-testing.md`). Python: pytest over non-trivial logic. Go: `go test`, table-driven. Full projects: ≥75% coverage on core logic (excluding thin wiring/`main()`) — skip where it would force excessive mocking; fast real e2e beats inflated unit coverage; self-check once, target not gate.

**Repairing export/block churn:** 3 failed patches on one file → stop, script the repair (`recovering-from-edit-thrash`).

## Step 5: Where it lives

Standalone scripts (bash, single-file Python) → `~/.local/bin/`, executable, no extension — unless the user established another convention. Full projects → own directory, installed via `pipx install .` / `go install`, never hand-copied.

## Step 6: Version control

For anything with its own directory (full projects, multi-file bash tools with install scripts):

- **`.gitignore` per tier**: Python → `__pycache__/`, `.venv/`, `.pytest_cache/`, `dist/`, `*.egg-info/` (commit `uv.lock`); Go → build binaries (commit `go.sum`); plus editor/OS cruft and real secrets (`.env`, local creds) from the first commit, not added later.
- **`git init` + initial commit** — local bookkeeping, do without asking.
- **No remote** → suggest (don't create) a GitHub repo — account-touching, needs the user's go-ahead; give exact `gh repo create`/`git remote add`/`git push` commands. Only for durable multi-file tools, only after confirming `.gitignore` excludes secrets.
- **Free to commit** and push to main/default branch of the apps generated by this skill.

## Output

Deliver the working file(s), `chmod +x` scripts, and exercise `--help`, `--dry-run` (if applicable), and one real invocation before handing over. If install/uninstall scripts or a systemd service subcommand exist, run install → `status` → uninstall too — untested lifecycle management is not delivered.
