# cli-app-generator v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Spike tasks (2–7) are parallelizable except where noted; template tasks (9–13) depend on DECISIONS.md.

**Goal:** Rebuild the `cli-app-generator` skill so agents generate CLIs faster with less custom code: library-backed stack, scaffolder, one conformance script, ≤1000-word SKILL.md, ≤1000 non-test template LOC, ≤100-line references.

**Architecture:** SKILL.md shrinks to gate + ask-once + stack table + 12-bullet universal contract + scaffold command + output checklist. Long-form detail moves to four ≤100-line references. A scaffolder emits tier × audience skeletons (audience is a parameter); `scripts/verify-cli` is the single conformance gate copied into every generated project. Spikes pick every library; `DECISIONS.md` records choice/why/rejected; `CHANGES.md` is the owner veto list.

**Tech Stack:** uv, typer+rich, httpx (+socks extra), pydantic v2, platformdirs, tomllib, tenacity/stamina, ruff, pytest; spike-picked picker; bashly-or-argc, gum/fzf/jq/mlr; cobra+fang+huh (spike E), go-pretty-or-lipgloss/table; copier-or-scaffold.sh.

**Spec:** `specs/2026-09-19-redesign-spec.md` (metrics, contract, budgets, migration notes).

## Global Constraints

- SKILL.md ≤ 1000 words (baseline 1,846). Aim ~900.
- Template LOC (non-test; excludes `tests/`, `.venv`, `__pycache__`, `.pytest_cache`, `uv.lock`) ≤ 1000 (baseline 1,793). File budgets: python-project ≤ 380, go ≤ 185, single-file ≤ 175, bash ≤ 145.
- Every reference file ≤ 100 lines.
- Delete instead of deprecate; no features beyond this plan. Every removal/replacement → one CHANGES.md line.
- Verify every library claim yourself (PyPI/pkg.go.dev/GitHub): release ≤ 12 months old, permissive license, compatible versions, no open blocker. Drop unmaintained. Never adopt a library without running it in the spike.
- Completion must stay ble.sh-safe (project decision memory: a non-ble.sh-safe completion script garbles interactive typing).
- LOC/word metric commands (use verbatim in report):
  - `wc -w SKILL.md`
  - `find templates -type f -not -path '*/.venv/*' -not -path '*/__pycache__/*' -not -path '*/.pytest_cache/*' -not -name uv.lock -not -path '*/tests/*' | xargs wc -l | tail -1`
- Repo is `ynsr/ynsr-skills` on branch `main`; work on a feature branch (`cli-app-generator-v2`), never commit to `main` directly; final delivery = push + MR via glab skill.
- Existing `templates/python-project/` tests: 29 passing — keep them passing (adapted) until task 9 replaces the surface.

---

### Task 1: Baseline + ledgers + workspace hygiene

**Files:**
- Create: `specs/baseline.md`, `CHANGES.md`, `DECISIONS.md`
- Modify: `templates/python-project/.gitignore` (add caches; `.venv` already untracked)

**Interfaces:**
- Produces: `baseline.md` (metrics + test output), `DECISIONS.md` with empty table header `| Spike | Choice | Why | Rejected | Evidence |`, `CHANGES.md` with header + baseline-removal lines.

- [ ] Step 1: Record baseline (already measured 2026-09-19; copy into `baseline.md`): SKILL.md 1,846 words; template non-test LOC 1,793 (python-project 1,249; single-file 544); tests 426 LOC / 29 passing; references 154/164 lines.
- [ ] Step 2: `cd templates/python-project && uv run pytest -v 2>&1 | tail -3` → paste into baseline.md. Expected: `29 passed`.
- [ ] Step 3: Remove untracked noise: `rm -rf templates/python-project/.venv templates/python-project/.pytest_cache templates/python-project/**/__pycache__ templates/python-single-file/__pycache__` (venv is regenerable via `uv sync`).
- [ ] Step 4: Init `DECISIONS.md` and `CHANGES.md` (formats in spec §5, §7). First CHANGES lines: cache cleanup, e2e-bash-testing.md scheduled for rewrite.

### Task 2 (SPIKE A): Python picker

**Files:** Create `specs/spikes/a-picker/` (throwaway venv + probe script); append row to `DECISIONS.md`.

**Interfaces:** Produces DECISIONS row A + the picker call signature the templates will use: `pick(label, options) -> int | None` semantics (index or None), rendered on stderr.

- [ ] Step 1: Maintenance check (PyPI + GitHub, last release ≤ 12 months, license): `questionary`, `prompt_toolkit`, `iterfzf`, `InquirerPy`. Record versions/credits in the row.
- [ ] Step 2: Probe script exercising: 1) renders to stderr (stdout captured must be empty), 2) returns None when stdin non-TTY (`</dev/null`), 3) Ctrl-C restores terminal (manual PTY check: `script -qec` under `pty`), 4) LOC needed. Timebox: 45 min.
- [ ] Step 3: If no lib routes to stderr cleanly → decision is "≤20-line wrapper around <lib>", justify.
- [ ] Step 4: Append DECISIONS row A. Evidence = probe script path + observed behavior lines.

### Task 3 (SPIKE B): Python completion by file drop

**Files:** Create `specs/spikes/b-completion/` (minimal typer app, `add_completion=False`); DECISIONS row B; findings → `references/install-and-completion.md` outline.

- [ ] Step 1: Confirm latest typer on PyPI + its release date; confirm the ≥0.27 bug: with `add_completion=False`, run env-var server (`_TOOL_COMPLETE=bash_complete tool …`) → expect `Shell bash not supported.` Include the upstream issue link.
- [ ] Step 2: Fixed upstream on latest? → plan says delete `ensure_completion_classes()`; verify by rerunning server. Record.
- [ ] Step 3: File-drop install test per shell: bash → `~/.local/share/bash-completion/completions/<tool>` (generate via `typer --print-completion bash`-equivalent / click script); fish → `~/.config/fish/completions/<tool>.fish`; zsh → document exact fpath line (`fpath=(~/.zfunc $fpath); autoload -Uz compinit && compinit`).
- [ ] Step 4: ble.sh test (ble.sh IS installed): `bash --rcfile <(echo 'source ~/.local/share/blesh/ble.sh; source <gen-file>')`, trigger Tab on subcommand + flag; record garbling or clean candidates. If automation can't drive it interactively, script the keystroke feed via a pty and record; otherwise list as manual check with exact steps.
- [ ] Step 5: Dynamic value callback: confirm the static script still invokes the env-var runtime for dynamic completions; make callback import lazily (module-level `import` forbidden inside callback path); measure Tab latency: `python -X importtime -c "import <app>" 2>&1 | tail -1`.
- [ ] Step 6: DECISIONS row B (keep/delete `ensure_completion_classes()`, file-drop paths, latency numbers, ble.sh verdict).

### Task 4 (SPIKE C): Install without stale copies

**Files:** Probe in `specs/spikes/c-install/`; DECISIONS row C.

- [ ] Step 1: `uv tool install --editable .` on a scratch project (uv 0.11.26): does `--editable` exist and survive reinstall/upgrade/uninstall? Then edit a source file → installed binary reflects change without reinstall.
- [ ] Step 2: Single-file PEP 723: `ln -sf $PWD/tool.py ~/.local/bin/tool` + shebang `#!/usr/bin/env -S uv run --script` → runs from anywhere; document.
- [ ] Step 3: Rewrite `doctor` shape: prints `status: ok|missing` + deps/config/connectivity checks (stale never emitted — cli-hub contract preserved). Draft the ~30-line doctor.
- [ ] Step 4: cli-hub 10-line register: verify current frozen call works from a 10-line install.sh (register + guard + exit). Hub-side metadata-derivation proposal → one paragraph in final report (hub source reachable at `~/.local/share/uv/tools/cli-hub` — cite, don't modify).
- [ ] Step 5: DECISIONS row C (editable+symlink adopted? what got deleted: receipt, stale guard, dev-warning; doctor contract text).

### Task 5 (SPIKE D): Bash generator — bashly vs argc

**Files:** Probe `specs/spikes/d-bashgen/` (same toy CLI written in both); DECISIONS row D (≤5-line reason).

- [ ] Step 1: Install both, timing the effort: bashly needs ruby (`gem install bashly` — record Ubuntu friction); argc single binary from GitHub releases (or `cargo install argc`) → `~/.local/bin`. Record commands + minutes.
- [ ] Step 2: Same toy tool (2 subcommands, 1 flag, completions) in each; compare: standalone output (single file? deps at runtime?), `--help` quality, bash/zsh/fish completion quality (argc native; bashly via `completely`), how mechanical it is for an agent to write correctly (spec surface: YAML schema vs comment tags).
- [ ] Step 3: DECISIONS row D: choice, why (≤5 lines), rejected alternative, evidence paths.

### Task 6 (SPIKE E): Go stack

**Files:** Probe `specs/spikes/e-go/` (module with cobra+fang+huh+table lib); DECISIONS row E. **Prerequisite:** if libs require Go > 1.22.5, install current stable Go (owner-approved upgrade) and record in DECISIONS row E.

- [ ] Step 1: Verify on pkg.go.dev/GitHub: `fang` (experimental flag — check stability statement, NO_COLOR handling, non-TTY behavior), `huh` (maintenance, license), `lipgloss/table` vs `go-pretty` (one table definition → Table + CSV + JSON; count LOC for each path), `hashicorp/go-retryablehttp`, `golangci-lint` current version. Record versions + release dates.
- [ ] Step 2: Probe: cobra command with fang wrapper; NO_COLOR + `</dev/null` non-TTY run; huh picker on stderr; render one dataset as table + CSV + JSON from ONE definition with each table lib; retryablehttp on a 500-mock.
- [ ] Step 3: Confirm widened Go tier criterion stands (daemon OR static binary for servers/jump hosts) — reject if evidence contradicts.
- [ ] Step 4: DECISIONS row E: cobra/fang adopt-or-fallback, huh, table lib choice, retry helper, lint; rejected alternatives.

### Task 7 (SPIKE F): Scaffolder — copier vs scaffold.sh

**Files:** Probe `specs/spikes/f-scaffold/` (same param set through both); DECISIONS row F.

- [ ] Step 1: copier: template dir + `_copier.yml` (params: tier, audience, name; feature flags profiles/wizard/service), `uvx copier copy <local-template> dest --data …` — works offline with a local path? deterministic repeat runs? feature toggles via include/exclude?
- [ ] Step 2: scaffold.sh: ~200 LOC bash: args + `case` feature includes + placeholder substitution. Compare maintenance (what changes when a template file changes), offline (zero deps), determinism.
- [ ] Step 3: Judge: less to maintain / works offline / deterministic / one command → working tested skeleton. DECISIONS row F; note scaffolder LOC is reported separately from the template budget.

### Task 8: `scripts/verify-cli` conformance script

**Files:** Create `scripts/verify-cli` (bash, executable, self-test at bottom `--self-test`).
**Interfaces:** Consumes: universal contract (spec §4.1). Produces: `verify-cli <cmd> [probe-read] [probe-destructive]` → 0 all pass / 1 failures listed. Checks = spec §4.2 table, exactly 1–8.

- [ ] Step 1: Implement checks 1,2,4,5,8 unconditional; 3,6,7 conditional on probe args (absent → SKIP, not FAIL).
- [ ] Step 2: Red run against CURRENT `templates/python-project` mycli: expect failures on `--output table|csv|tsv` (only `--json` exists), error envelope, `--dry-run` shape. Record which checks fail — this is the contract delta, paste into CHANGES.md.
- [ ] Step 3: Green run: `bash scripts/verify-cli --self-test` against a tiny throwaway conformant toy → 0.
- [ ] Step 4: Commit `scripts/verify-cli`.

### Task 9: SKILL.md v2 + references

**Files:** Rewrite `SKILL.md`; create `references/{stacks,install-and-completion,bash-testing,systemd}.md`; delete `references/install-and-completion-internals.md`, `references/e2e-bash-testing.md`.

**Interfaces:** SKILL.md references scaffold command `scripts/scaffold.sh --tier <t> --audience <a> --name <n> [--profiles] [--wizard] [--service]` and output step "run `verify-cli`". References must exist and be ≤100 lines before SKILL.md points at them.

- [ ] Step 1: Write the four reference files from surviving content: stacks (per-tier libs + audience add-on matrix), install-and-completion (file-drop paths incl. zsh fpath, uninstall-reverses-all, Typer issue link + workaround per spike B, `status:` contract, rc-block cleanup sed line), bash-testing (bats skeleton + e2e essentials, trimmed of git-fixture content), systemd (user unit + linger + service subcommands, per spec §2.4 Go-only).
- [ ] Step 2: `wc -l references/*.md` — every file ≤ 100; trim before proceeding.
- [ ] Step 3: Rewrite SKILL.md per spec §6 outline; frontmatter unchanged. Fill stack table from DECISIONS.md rows.
- [ ] Step 4: `wc -w SKILL.md` → ≤ 1000; if over, move prose to references, never delete a contract bullet.
- [ ] Step 5: Update CHANGES.md: each deleted section/file → one line + why.

### Task 10: python-project template rebuild

**Files:** Rewrite `templates/python-project/` per budget ≤ 380 non-test LOC: `src/mycli/{cli,output,client,config,doctor}.py` (completions.py, pick.py, ops.py deleted); `pyproject.toml` (+ruff config, pinned deps, uv.lock committed); install.sh (uv tool install --editable . + 10-line register), uninstall.sh; tests adapted.

**Interfaces:** Consumes: spike A picker call, spike B completion file-drop, spike C doctor. Produces: conformance with all 12 contract bullets; `uv run pytest` green; `check` target (Makefile or pyproject script): ruff + pytest + verify-cli copy.

- [ ] Step 1: Write failing tests first for new surface: `--output table|json|csv|tsv` matrix incl. `--json` alias; error envelope shape; `--dry-run` without `--yes`; NO_COLOR; non-TTY no-block.
- [ ] Step 2: Implement per budgets: `output.py` (one emit() → table/csv/tsv/json + envelope), `client.py` (httpx+socks factory, tenacity/stamina retry, `--timeout/--retries/--retry-delay`), `config.py` (platformdirs, envvar precedence), `doctor.py` (status-only), `cli.py` (typer envvar= wiring, schema/commands introspection from Click tree + pydantic JSON Schema — agent audience only).
- [ ] Step 3: Delete superseded files; `git rm` completions.py pick.py ops.py doctor.py receipt logic.
- [ ] Step 4: `uv sync && uv run pytest -v` green; `ruff check .` clean; LOC ≤ 380 (metric command).
- [ ] Step 5: CHANGES.md lines for every deletion/replacement.

### Task 11: python-single-file template rebuild

**Files:** Rewrite `templates/python-single-file/tool.py` (≤ 175 with install/uninstall): PEP 723 + httpx (drop requests), env-only config, audience parameter via scaffold, delete picker copy + completions machinery + receipt/dev-warning (spike C symlink); install.sh = symlink + register; uninstall.sh = rm + unregister.

- [ ] Step 1: Verify with smoke commands — the single-file tier has no pytest file; its verification surface is verify-cli plus direct `uv run tool.py` invocations, keeping the file lean: `uv run tool.py --help`, `--output csv` roundtrip, non-TTY no-block.
- [ ] Step 2: LOC ≤ 175; CHANGES.md lines.

### Task 12: bash + go templates (new)

**Files:** Create `templates/bash/` (`tool.sh` ≤ 145 with install/uninstall/README; bats test) per spike D; create `templates/go/` (main.go ≤ 185, go.mod, README, AGENTS, install/uninstall) per spike E.

- [ ] Step 1: bash skeleton: `set -euo pipefail`, error envelope helper (jq), `--output` switch via column/jq/mlr, `check` = shellcheck + bats + verify-cli copy. Escalation ceiling per owner decision: a bash tool exceeding ~300 LOC or needing real data structures → escalate to Python (spec §10.2).
- [ ] Step 2: go skeleton: cobra(+fang per DECISIONS), output switch (chosen table lib), retryablehttp, slog stderr, `go test` for emit + envelope, `check` = golangci-lint + go test + verify-cli copy.
- [ ] Step 3: Both pass their own check targets; LOC within budget; CHANGES.md lines.

### Task 13: Scaffolder + check wiring

**Files:** Create `scripts/scaffold.sh` (or copier template per DECISIONS row F); every skeleton gets `scripts/verify-cli` copy + `check` target.

- [ ] Step 1: Implement per DECISIONS row F: params tier, audience, name, optional `--profiles --wizard --service` (tier-scoped per spec §2.4; unknown tier/audience → usage error).
- [ ] Step 2: Scaffold × {bash, single-file, project, go} × {human, agent} → all produce trees; each tree's `check` runs green (lint + tests + verify-cli).
- [ ] Step 3: Determinism: two scaffold runs → identical trees (`diff -r`).
- [ ] Step 4: CHANGES.md lines.

### Task 14: Phase 5 validation — four samples

- [ ] Step 1: Using ONLY updated SKILL.md flow + scaffolder, generate: (bash, agent), (python-single-file, human), (python-project, agent), (go, human) — each with one read + one destructive command. Time each (wall clock), count interactions, record generated bytes.
- [ ] Step 2: `verify-cli` green on all four (checks 1–8 with probes).
- [ ] Step 3: Delete samples; record results in `specs/validation-results.md`.

### Task 15: Report + delivery

**Files:** Create `specs/2026-09-19-redesign-report.md`; finalize `CHANGES.md`, `DECISIONS.md`.

- [ ] Step 1: Re-measure all metrics (Global Constraints commands) → before/after table (skill words, template LOC, scaffold times) + spike decision table + CHANGES log + migration notes (spec §9) + open questions.
- [ ] Step 2: Self-review: every Global Constraint re-checked against artifacts; CHANGES.md has no unexplained removal.
- [ ] Step 3: Branch `cli-app-generator-v2` → commit → push → MR to `main` via glab skill (tests green first). MR description links spec, plan, report, CHANGES, DECISIONS.

---

## Self-review notes

- Spec coverage: metrics §1→Global Constraints+Task 15; contract §4.1→Task 8+10–12; budgets §4.3→Tasks 10–12; spikes §5→Tasks 2–7; SKILL.md §6→Task 9; CHANGES §7→Tasks 1,9–13,15; validation §8→Task 14; migration §9→Task 15 Step 1. Gaps: none open — cli-hub hub-side proposal intentionally an issue-note only (spec §10.1).
- Type consistency: `verify-cli <cmd> [probe-read] [probe-destructive]` used identically in Tasks 8, 10–14. `pick(label, options) -> int | None` (Task 2) is the signature templates consume in Tasks 10–11.
- Spike tasks intentionally stop at DECISIONS rows, not final code — that is the plan's declared dependency, not a placeholder; template tasks consume exactly those rows.
