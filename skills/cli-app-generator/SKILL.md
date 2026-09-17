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

- `templates/python-project/` — full multi-file layout (solr-cli extract): profile store + httpx client with proxy normalization/retries + Typer CLI (`add_completion=False`; CSV default, `--json`, wizard with completion-install offer, interactive pick) + `completions show|install` (eval-line scripts, idempotent rc edit) + mock-transport pytest suite (16 tests incl. completion idempotency, offline). Verified: `uv sync && .venv/bin/python -m pytest` → all pass.
- `templates/python-single-file/tool.py` — one-file layout (mbapi extract): constants → 0600 profile store → requests.Session with retries → domain functions → Typer commands (`add_completion=False`, `completions show|install` inline) → `main()`. Verified: runs under `uv run --with requests,typer,click`.

Bash and Go templates: not yet provided — follow the tiers above.

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

**AGENTS.md**: exact build/test commands (copy-pasteable), how the app works end to end, and a responsibility→module map (e.g. "retry logic → `internal/retry`") so an agent can find the right file without grepping the whole tree. Add a line referencing this skill (`cli-app-generator`) so future agents updating the CLI follow its conventions rather than inventing new ones.

### Install/uninstall scripts

**Required by default.** Every generated CLI ships explicit `install.sh` + `uninstall.sh` — adapted from `templates/python-project/` for full projects; trivial copy-into-`~/.local/bin/` + `chmod +x` + register versions for bash/single-file tiers — **unless the user explicitly asked otherwise**. Never leave installation as prose instructions: an install story the user must hand-assemble is not delivered. Scripts are idempotent and safe to re-run; `uninstall.sh` reverses everything `install.sh` created — package, completions, cron/systemd units, tool-created config, and the install receipt. Templates: `templates/python-project/install.sh` / `uninstall.sh` (`<tool-name>`/`<package>` placeholders).

**Stale-install guard (Python project tier).** `uv tool install` and `pipx install` snapshot the source into an isolated venv — workspace edits never reach the installed binary until reinstall. Every Python CLI ships three parts:
1. `install.sh` writes `~/.local/share/<tool>/install-receipt.json` (`source_hash`: SHA-256 over source `*.py`, relative paths + bytes, 12 hex chars; `installed_at`; `source_dir`) and runs `<tool> doctor` as a self-check. One canonical installer (uv preferred, pipx fallback) — mixing both fights over `~/.local/bin`.
2. `<tool> doctor` compares the receipt hash against the live tree: exit 0 in sync, exit 1 with the fix command (`./install.sh` or `pipx install --force .`) when stale/missing. Share-dir path must honor `$HOME` so tests can redirect it.
3. A dev-run warning on every invocation when `__file__` resolves to a working tree (not `site-packages`/`.local/share`) and the tree hash differs from the receipt — catches "edited source, forgot to reinstall" before it confuses the user. Never warn from the installed copy itself.

### cli-hub registration

Every generated CLI must self-register with [cli-hub](https://github.com/ynsr/cli-agents-config/tree/main/tools/cli-hub) (`~/.config/cli-hub/config.yml`, re-read on every hub call) so all skill-generated tools stay discoverable from one entry point:

- `install.sh` ends with a best-effort registration (never fail the install when the hub is absent):
  ```bash
  if command -v cli-hub &>/dev/null; then
    REPO="$(git -C "$DIR" remote get-url origin 2>/dev/null || true)"
    cli-hub register <tool-name> \
      --version "<version>" \
      --description "<one-line description>" \
      --group "<group>" \
      --source-path "$DIR" \
      ${REPO:+--repo "$REPO"} \
      --config-path "${HOME}/.config/<tool-name>" \
      --uninstall "$UNINSTALL" \
      --reinstall "$REINSTALL" \
      --yes || true
  fi
  ```
  `UNINSTALL`/`REINSTALL` are set by `install.sh` to the backend actually used at install time — pipx → `pipx uninstall <tool>` / `pipx install --force $DIR`; uv → `uv tool uninstall <tool>` / `uv tool install --force $DIR`. Never hardcode pipx: the hub must re-run the backend that owns the install, or its uninstall/reinstall fights the other backend over `~/.local/bin`.
  Single-file scripts (no `install.sh`): run the equivalent `cli-hub register` inline once after copying the script into `~/.local/bin/`, with `--source-path` pointing at the installed copy and `--reinstall` re-running the copy command.
- `uninstall.sh` ends with `cli-hub unregister <tool-name> --yes || true` (best-effort, same guard).
- Fill every metadata field you know: `--version` (from `pyproject.toml`/`--version`), `--description` (README one-liner), `--group` (domain noun: `git`, `media`, `db`, `net`, `meta`, `misc`), `--source-path` (project dir), `--repo` (git origin URL, empty when none), `--config-path` (`~/.config/<tool>`), `--uninstall`/`--reinstall` (exact commands that reverse/redo the install).
- The hub detects missing binaries itself (`cli-hub prune` lists entries with no binary on `PATH` and removes them only after user confirmation), so uninstall paths don't need hub cleanup beyond `unregister`.

### systemd-managed services

Typically the Go tier. Default to a **user-scoped service** (`~/.config/systemd/user/`, `systemctl --user`) — system-wide only if explicitly requested or domain-required (pre-login start, privileged port, multi-user). `install` must also check/enable lingering (`loginctl show-user $USER --property=Linger`; if not on, `loginctl enable-linger $USER`) — without it a user service dies at logout, silently defeating the point. Ship dedicated lifecycle subcommands — `tool-name service install|uninstall|start|stop|restart|status|logs` — wrapping the unit file + `systemctl --user`/`journalctl --user` calls so the user never hand-writes them.

## Step 3: Cross-cutting rules (every tier)

**Idempotency.** Re-running with the same inputs must be safe and non-duplicating: check state before mutating, use atomic writes (temp file + rename), and if a step truly can't be idempotent, use a marker/lock file to block re-execution rather than silently repeating it.

**Dry-run for anything destructive.** "Destructive" = deletes/overwrites files, writes to a DB, calls an API with side effects (POST/PUT/PATCH/DELETE), or is otherwise hard to undo.
- `--dry-run` prints exactly what *would* happen — actual records/requests, not just "would proceed"
- destructive actions require `--yes`/`--force` to actually execute; never run unattended by default

**Standard flags, every tool:**
- `-h`/`--help` — full usage, one example per major use case with real args, exit code meanings, and the main config file path (e.g. `~/.config/<tool>/config.yaml`). Write it like documentation for another AI agent reading it cold.
- `--version`
- `-v`/`--verbose`, `-q`/`--quiet`
- `--json` where output is structured — **only valid if logs/progress go to stderr and stdout carries just the output.** Mixing status lines into stdout silently breaks piping into `jq` or agent consumption.
- `--yes`/`--force` to bypass confirmation prompts (needed for non-interactive/agent use)

**In-place progress for anything iterative/long-running.** Downloading a file, processing a batch, walking a list of items — update a single line in place (`\r`, no newline until done) rather than a new line per item, showing real detail (percentage, current item, N/total). Only when stdout is a TTY and `--quiet`/`--json` aren't set — never emit `\r` into piped/JSON output; fall back to periodic plain-line updates (e.g. every 10% or every N items) for non-TTY output like logs or `nohup`. Print a final newline on completion/error so the last state survives in scrollback.

**Exit codes.** Small consistent convention, documented in `--help`: `0` success, `1` general error, `2` usage error, and add more (e.g. `3` network/timeout, `4` partial success) if failure modes meaningfully differ.

**Network operations.** Every network call gets `--timeout`, `--retries`, `--retry-delay` (exponential backoff between retries), exposed as flags with sane defaults rather than hardcoded.

**Secrets and config.** Never hardcode credentials or endpoints. Read from env vars or a config file, document which ones in `--help`, and fail immediately with a clear message if something required is missing.

- **Proxy env**: normalize `socks://` → `socks5://` in ALL_PROXY/HTTP(S)_PROXY before building an httpx client — httpx raises `ValueError: Unknown scheme` on bare `socks://`, curl treats it as SOCKS5. (See `templates/python-project/src/mycli/client.py`.)
- **Help**: Typer + Rich — panels, aligned columns, examples per command. Docstring's first paragraph is the one-liner; real example commands under `Example:`.
- **Profiles**: if the tool can reach multiple sources/orgs, support named profiles (create/list/use/remove) + a `--profile` flag on every command; no flag = stored default profile. Secrets via env vars or 0600 local files — never flags (shell history), code, or logs.
- **Setup wizard**: `tool init` walks first-run config (endpoint → auth → default profile), saves it, and verifies with one live call.
- **Shell completion** (every Python CLI — both templates ship it; see `templates/python-project/src/mycli/completions.py`):
  - Construct the app with `add_completion=False` (disables Typer's competing `--install-completion`/`--show-completion` flags) and ship ONE system: a `completions` group with `show <bash|zsh|fish>` (prints the init script for `eval "$(tool completions show bash)"` in `~/.bashrc` / `~/.zshrc`, `| source` for fish) and `install [shell] [--rcfile --yes]` (idempotent marker-block rc edit: atomic tmp+rename write, `.bak` backup, stale-block replace not duplicate; zsh block also ensures `compinit`).
  - Do NOT hand-code completion order — Click resolves the cursor position: subcommand names and `-`/`--` flags complete automatically. The only custom code is one `autocompletion=` callback per *dynamic value* (profile/resource names, like `git branch` cycling branches): filter on the `incomplete` prefix, read local state only (never network), never raise (return `[]` on any failure so Tab never breaks). Use `completions.complete_profile_names(list_profiles)` / `_complete_profiles` in the templates.
  - `install` with no shell arg auto-detects from `$SHELL` (`detect_shell()`; None → usage error telling the user to pass the shell explicitly); `--shell` beats positional for agent/non-interactive use; `--rcfile` overrides per-shell default (`~/.bashrc`, `~/.zshrc`, `~/.config/fish/config.fish`) for tests; `--yes` bypasses the confirm prompt. Confirm before editing the rc file on a TTY (rc edit is destructive per the dry-run rule); print `source <rc>` / restart hint to stderr after a change, `already installed` on no-op.
  - `init` wizard offers completion install at the end (confirm default No; `--no-completion` skips non-interactively). Tradeoff to document in README: `eval $(...)` spawns Python on every new shell (~200–400ms for Typer apps) but never goes stale — the right default for our tier.
  - Tests (project tier, `tests/unit/test_completions.py`): `show` output non-empty per shell + unknown shell exits 2; install preserves existing rc content, creates `.bak`, second run is a byte-identical no-op; Click-level check that subcommands/flags resolve; value callback filters prefixes and returns `[]` on missing config.

**Output format**: list/table output defaults to CSV with a header row; `--json` opts into JSON. stdout carries output only — logs to stderr.

**Env vars**: stable settings (endpoint, auth token, default-profile override) read env vars so users don't repeat flags. Precedence: CLI flag > env var > profile > built-in default.

**Non-interactive by default.** Nothing blocks on stdin unless the tool is explicitly interactive. Confirmation prompts only guard destructive actions; `--yes` bypasses them.

**Interactive selection**: when a required choice (profile, resource id) is missing and stdin is a TTY, list options and prompt; non-TTY/`--yes` skips prompts and fails with an actionable message.

**Bash baseline** (when bash is chosen): `set -euo pipefail`, a `trap` for cleanup, shellcheck-clean. Reaching for associative-array-of-arrays or real JSON parsing is a signal to switch to Python.

**Testing scales with tier.** Trivial bash: none needed. Reused bash: consider `bats` or inline e2e (see `references/e2e-bash-testing.md` for a full self-contained test pattern with temp repos, assert helpers, and git fixture setup). Python (either tier): pytest covering non-trivial logic. Go: `go test`, table-driven where it fits. Full projects target **≥75% coverage on core logic** (`pytest --cov` / `go test -cover`), excluding thin CLI wiring/`main()` — skip the target where it'd force excessive mocking that makes tests worse than none; fast real e2e tests beat inflated unit coverage. Self-check once with the coverage tool; treat as a target, not a blocking gate.

**Repairing export/block churn.** When surgical edits to ordered blocks (`__all__`, imports, flag lists) thrash — 3 failed patches on one file — stop patching and script the repair (see `recovering-from-edit-thrash`).

## Step 4: Where it lives

Standalone scripts (bash, single-file Python) go to `~/.local/bin/`, made executable, no extension on the installed copy — unless the user has already established a different convention in this conversation. Full projects get their own directory and are installed via `pipx install .` / `go install`, not copied by hand.

## Step 5: Version control

For anything that gets its own directory (full Python/Go projects, or a multi-file bash tool with install scripts) — not a single standalone script:

- **`.gitignore` matched to the tier**: Python → `__pycache__/`, `.venv/`, `.pytest_cache/`, `dist/`, `*.egg-info/` (commit `uv.lock`, don't ignore it); Go → build binaries (commit `go.sum`); plus editor/OS cruft. Also ignore real secrets (`.env`, local creds) from the start, not added after the first commit.
- **`git init` + initial commit** for these projects — local bookkeeping, do it without asking.
- **If there's no remote yet**, suggest (don't do) creating a GitHub repo and pushing — an account-touching action needing the user's go-ahead. Use a connected GitHub tool if available, otherwise give the exact `gh repo create`/`git remote add`/`git push` commands. Only for durable multi-file tools, and only after confirming `.gitignore` actually excludes secrets.

## Output

Deliver the working file(s), `chmod +x` scripts, and exercise `--help`, `--dry-run` (if applicable), and one real invocation yourself before handing it over. If install/uninstall scripts or a systemd service subcommand exist, run through those too — install, check `status`, uninstall — rather than handing over untested lifecycle management.