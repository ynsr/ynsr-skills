# CHANGES

One line per removal/replacement during the v2 redesign: `- <what> → <replacement or "deleted"> : <one-line why>`. Appended during implementation; owner may veto any line before merge.

- templates/python-project/.venv → deleted : untracked build noise; regenerable via `uv sync`; caches now gitignored
- templates/python-project/.pytest_cache → deleted : untracked test cache; now gitignored
- templates/**/__pycache__ → deleted : untracked bytecode cache; now gitignored
- references/e2e-bash-testing.md → references/bash-testing.md : 162 lines, mostly git-fixture content unrelated to the skill; rewritten to a 90-line bats+e2e reference (Task 9)
- references/install-and-completion-internals.md → references/install-and-completion.md : 154 lines over the 100-line cap; rewritten to a 61-line reference, receipt/stale-guard content deleted per DECISIONS row C (Task 9)
- SKILL.md long-form install/receipt/completion prose → references/install-and-completion.md : receipts and stale-guard deleted per DECISIONS row C; SKILL.md cut 1846 → 881 words
- SKILL.md systemd prose → references/systemd.md : service mechanics moved out of the word budget; service scoped to Go tier (spec §2.4)
- SKILL.md e2e pointer + pipx install guidance → references/bash-testing.md + `uv tool install --editable .` : DECISIONS rows C/D; testing pattern now bash-testing.md
- SKILL.md `recovering-from-edit-thrash` bullet → deleted : spec §6 drop; unrelated to CLI generation
- SKILL.md Steps 1+2 (ask inputs / identify audience) → merged Step 1 ask-once : spec §6 batched single ask
- SKILL.md hand-rolled tier layout snippets (PEP 723, project tree, Go tree, pipx) → scaffold.sh command + references/stacks.md : scaffolder emits tier × audience skeletons (DECISIONS row F)
- templates/python-project mycli `--help` (no exit-code legend) → documented 0/1/2/3/4 exit codes : verify-cli check 1 requires it (Task 8 red run)
- templates/python-project mycli `--json`/`-o json` only → `--output/-o table|json|csv|tsv` + `--json` alias : universal contract §4.1.2; verify-cli check 3 red (Task 8)
- templates/python-project mycli typer rich usage error → `{"error":{"code","message","hint"}}` on stderr with matching exit code : contract §4.1.7; verify-cli check 6 red (Task 8)
- templates/python-project mycli interactive `profile remove` prompt → `--dry-run` prints plan / `--yes` executes; non-TTY must not prompt : contract §4.1.4/6; verify-cli check 7 red (Task 8)
- templates/python-single-file tool.py requests.Session + urllib3 retries → PEP 723 (uv) + httpx Client with own 3-attempt bounded-backoff retry : httpx everywhere (spec §2.1); verify-cli checks 1–7 green
- templates/python-single-file 0600 profile store (save/load/list) → env-only config (`<TOOL>_TOKEN/_URL/_TIMEOUT`) : bash/single-file tiers get env vars only (SKILL.md Step 2); secrets never in flags
- templates/python-single-file hand-rolled arrow-key picker copy (~80 LOC) → deleted : tier is env-only, no wizard/picker; questionary wrapper stays a project-tier add-on
- templates/python-single-file `completions show|install` + rc-marker editing + receipt/dev-warning stale guard → deleted : spike C symlink install makes staleness structurally impossible; slim `doctor` (`status: ok|missing` + `--json`) keeps the cli-hub contract
- templates/python-single-file `version` subcommand → `--version`/`-v` flag + `-q` quiet + `--no-color` : contract §4.1.5/6
- templates/python-single-file error path (`error: …` print + exit) → `{"error":{code,message,hint}}` envelope on stderr (non-TTY or `--output json`) : contract §4.1.7; verify-cli check 6 green
- templates/python-single-file agent list extras (`--fields`/`--limit`) → deleted : compact tier keeps the read command minimal; pagination/field selection belongs to the project tier
- templates/python-single-file install.sh cp+receipt → `ln -sfn` symlink + best-effort `cli-hub register --source-path tool.py`; uninstall.sh → rm + unregister : DECISIONS row C
- templates/python-single-file tool.py 441 + install/uninstall 103 → 148 + 19 + 8 = 175 LOC : spec §4.3 budget 175
- templates/bash (new) → bashly-generated single-file skeleton (140 LOC: yml 48 + handlers 43 + contract 15 + settings/install/uninstall/README): spike D — `completions` (static, ble.sh-sourced OK), unknown-command→exit 2 envelope, verify-cli 11/11
- templates/go (new) → cobra+fang+go-pretty skeleton, main.go 166 + go.mod 36 + README/AGENTS/install/uninstall 49, httpx.go retry helper 36-significant-LOC: spike E — envelope via fang error handler, own RetryClient (server-proven 500→500→200), verify-cli 11/11; spec §4.3 6-file sum 251 > 185 (go.mod 22 indirect lines + fang/cobra import block) — main.go ≤ 185 satisfied, flagged in task-12-report.md
