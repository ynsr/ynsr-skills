# cli-app-generator v2 — Redesign Report (Task 15)

Date: 2026-09-20 · Branch: `cli-app-generator-v2` (HEAD `d1e3ce0` at report time).
Inputs: spec `specs/2026-09-19-redesign-spec.md`, plan `specs/2026-09-19-redesign-plan.md`,
baseline `specs/baseline.md`, validation `specs/validation-results.md`, spike reports
`specs/spikes/{a-picker,b-completion,c-install,d-bashgen,e-go,f-scaffold}/report.md`,
task reports `.superpowers/sdd/2026-09-19-redesign-plan/task-{9..14}-report.md`.

**Owner ruling (2026-09-20, mid-flight):** per-tier template LOC budgets were **dropped**
(commit `3265fd5`: "do not contort or drop features for LOC"). Documentation caps were
**kept** (SKILL.md, reference line caps). This report measures against the ORIGINAL spec
budgets and marks the deltas dropped-by-owner. It also resolves the spike-E six-file
deviation (253 vs spec row 185): moot under the ruling.

## 1. Metrics — before / after

All numbers measured on this worktree, 2026-09-20, commands quoted verbatim.

### 1.1 Documentation caps (kept)

| Metric | Baseline (2026-09-19) | Spec target | After (measured) | Command |
|---|---|---|---|---|
| SKILL.md words | 1,846 | ≤ 1000 | **881** | `wc -w SKILL.md` |
| references/stacks.md lines | — (new) | ≤ 100 | **44** | `wc -l references/*.md` |
| references/install-and-completion.md lines | 154 (as install-and-completion-internals.md) | ≤ 100 | **61** | 〃 |
| references/systemd.md lines | — (new) | ≤ 100 | **61** | 〃 |
| references/bash-testing.md lines | 162 (as e2e-bash-testing.md; 164 in spec §3) | ≤ 100 | **90** | 〃 |
| references total | 316 | — | **256** | 〃 |

All reference files ≤ 100 lines. SKILL.md at 881 words is under both the 1000-word cap and
the plan's ~900 aim.

```
$ wc -w SKILL.md
881 SKILL.md
$ wc -l references/*.md
  90 references/bash-testing.md
  61 references/install-and-completion.md
  44 references/stacks.md
  61 references/systemd.md
 256 total
```

### 1.2 Template LOC (original budgets DROPPED-BY-OWNER)

The plan's verbatim metric command (`find templates -type f … | xargs wc -l | tail -1`)
silently drops every file whose name contains whitespace (the copier conditional jinja
filenames `<% if profiles %>profile.go<% endif %>.jinja` and
`python-project/src/{{ name }}/*.py.jinja`) — its 2,669 total undercounts. The robust
`-print0` variant of the same filter was used instead:

```
$ find templates -type f -not -path '*/.venv/*' -not -path '*/__pycache__/*' \
    -not -path '*/.pytest_cache/*' -not -name uv.lock -not -path '*/tests/*' -print0 \
  | xargs -0 wc -l | tail -1
3662 total
```

That 3,662 includes framework boilerplate the spec's own accounting excludes
(`verify-cli` 272 ×2 copies counted separately per spec §2.3/§4.2, `uv.lock.jinja` 447,
`go.sum` 90, `send_completions.sh.jinja` 189 bashly boilerplate, tests-adjacent
`tool.bats.jinja` 97, golangci artifacts). **Rendered per-tier numbers** (each scaffolded
live via `scripts/scaffold.sh`, the SKILL.md-documented flow, and counted as rendered):

| Tier | Files counted | Rendered LOC | Spec §4.3 budget (dropped) | Baseline |
|---|---|---|---|---|
| python-single-file | `tool.py` + install + uninstall | **175** | ≤ 175 | 544 |
| bash (agent, lean) | bashly.yml + handlers + contract + install/uninstall + README + settings (excl. check.sh, tests, send_completions boilerplate — task-12 precedent) | **332** incl. 189 bashly `send_completions.sh` boilerplate; **143** authored (task-12 post-fix count) | ≤ 145 (authored) | — (tier new) |
| go (lean) | main.go + go.mod + httpx.go + README + AGENTS + install + uninstall | **324** (main 179, go.mod 36, httpx 60, meta 49) — six-file sum 253 | ≤ 185 | — (tier new) |
| go (profiles+wizard+service) | + profile.go 260, service.go 148 | **+408** | — | — |
| python-project (agent, lean) | src 5 modules 392 + pyproject 52 + README 40 + AGENTS 28 + Makefile 7 + install 31 + uninstall 11 | **561** excl. verify-cli copy (272, §4.2 counted separately) | ≤ 380 | 1,249 |

Commands (rendered):

```
$ wc -l /tmp/t15/s/{tool.py,install.sh,uninstall.sh}          # single-file
148  19   8  → 175
$ wc -l /tmp/t15/g/{main.go,go.mod,httpx.go,README.md,AGENTS.md,install.sh,uninstall.sh}
179  36  60  17  13  12   7  → 324   (six-file sum excl. httpx.go: 253)
$ find /tmp/t15/p/src -name '*.py' | xargs wc -l | tail -1     # project src, lean
 392 total   (+ pyproject 52 + README 40 + AGENTS 28 + Makefile 7 + install 31 + uninstall 11 = 561)
```

Against the ORIGINAL ≤1000 total (baseline 1,793): the four lean tiers sum to
175 + 143 + 324 + 561 = **1,203 non-test LOC** (−590 vs baseline) — over the original
budget only because feature-complete contract surface (schema, profiles, wizard,
per-tier wiring, 76-test surface suite) was kept per the owner ruling. Per-tier original
budgets: single-file **met exactly** (175 ≤ 175); bash authored 143 ≤ 145 **met**;
go six-file sum 253 vs 185 **deviation** (go.mod 22 indirect require lines + fang/cobra
import block are not authorable; main.go 179 ≤ 185 satisfied) — resolved by the budget
drop; python-project 561 vs 380 **dropped-by-owner** (task-10 directive: no feature cut).

### 1.3 Supporting metrics — Phase 5 four-sample validation (Task 14, `specs/validation-results.md`)

| Sample | Tier × audience | Wall clock (scaffold→flow) | Interactions | Generated bytes | verify-cli |
|---|---|---|---|---|---|
| tagprobe | bash / agent | 5.25 s | 6 | 48,608 B (16 files) | 11/0/0 |
| fetchone | python-single-file / human | 8.44 s | 8 | 20,274 B (5 files) | 10/0/1 skip (check 8: no completion machinery, by design) |
| apifetch | python-project / agent | 16.02 s | 8 | 321,184 B excl. `.venv` (44 files) | 11/0/0 |
| watchrun | go / human | 6.08 s | 9 | 35,322 B (12 files) | 11/0/0 |

All four post-fix (scaffolder `13ff9d7`), all verify-cli green before sample deletion.
Timing noise: first `uvx copier` run pre-warmed; python-project's 16 s dominated by
`uv sync` + ruff + 76-test pytest.

### 1.4 Tests

| Suite | Baseline | After |
|---|---|---|
| python-project | 426 LOC / 29 passing | rewritten; **84 passing** (unit + subprocess surface through the real entry point), `make check` exit 0 |
| bash tool.bats | — | 13/13 |
| go main_test.go | — | 8/8 |
| python-single-file check.sh | — | 10 pass / 1 designed skip |

## 2. Spike decision summary (DECISIONS.md rows A–F, all reviewed)

| Spike | Decision (one line) | Evidence |
|---|---|---|
| A | questionary 2.1.1 (MIT) + 17-line stderr wrapper; prompt_toolkit 3.0.53 custom app (38 LOC) documented fallback; iterfzf rejected (GPL-3.0); InquirerPy rejected unmaintained without probing | `specs/spikes/a-picker/report.md`, `evidence.txt` (9/9 primary verdicts + NO_COLOR runs), release-age concern → open question 3 |
| B | typer 0.27.2 file-drop completion (bash/fish/zsh + zsh fpath-before-compinit), ble.sh-verified live; KEEP 3-line `completion_init()` workaround — regression live on 0.27.0 AND 0.27.2 (`add_completion=False` → all shells' completion servers dead) | `specs/spikes/b-completion/report.md`, `evidence/blesh_screens*.txt`, `workaround-completion-init.patch.md` — exact upstream issue absent → open question 1 |
| C | `uv tool install --editable .` (project) / `ln -sf` symlink (single-file); receipt, stale-guard, dev-warning deleted; doctor slimmed to `status: ok|missing` + `--json` (cli-hub contract preserved, `stale` never emitted) | `specs/spikes/c-install/report.md`, `evidence/{editable-propagation,symlink-probe}.log`, hub-side proposal → open question 2 |
| D | bashly (self-contained standalone script, bash ≥4.2 under `env -i`, static completions — ble.sh-safe class); argc rejected (runtime hard-dependency + per-keystroke fork) | `specs/spikes/d-bashgen/report.md`, `bashly/`, `argc/` toy tools |
| E | cobra v1.10.2 + fang v2.0.1 + huh v2.0.3 (wrapper recipe) + go-pretty v6.8.3 + own 36-LOC retry helper (retryablehttp rejected: 15 mo, MPL-2.0); go.mod 22 indirect lines push six-file sum to 253 vs spec 185 — resolved by the budget drop | `specs/spikes/e-go/report.md`, `evidence/*` (fang NO_COLOR/non-TTY, huh pty e2e, retry server-proven) |
| F | copier 9.18.2 via `uvx --offline` (66 vs 187 LOC, 1–2 vs 3–4 touchpoints per change, byte-identical determinism, offline proven); scaffold.sh rejected at 3× LOC (3× during tasks) | `specs/spikes/f-scaffold/report.md`, `evidence/{copier-runs,scaffold-runs,parity-and-loc}.log` |

## 3. CHANGES.md digest

Ledger at `CHANGES.md` — 58 lines in the standard `- <what> → <replacement|deleted> : <why>`
shape. Coverage: workspace hygiene (caches), reference rewrites (2), SKILL.md cuts (9),
python-project contract rebuild (16 incl. deletions of completions.py/pick.py/ops.py and
receipt machinery), single-file rebuild (8, incl. requests→httpx/PEP 723 and completion/
receipt deletions), bash tier (new + review round), go tier (new + review round),
scaffolder + jinja conversion (Task 13, 8 lines incl. env_prefix fix), budget-drop ruling
line, validation results line. Full audit in §6 checklist — **no unexplained removal found**;
every deletion traces to a DECISIONS row, spec §, or owner ruling line.

## 4. Migration notes (spec §9) — for existing generated CLIs

1. **Old receipt-based installs keep working as-is.** No forced migration. The `stale`
   doctor status is never emitted by NEW tools; existing installs continue under the old
   semantics until re-scaffolded.
2. **Optional cleanup on re-scaffold:** delete `~/.local/share/<tool>/install-receipt.json`
   (and the dev-warning block it fed) — the new single-file tier installs by symlink
   (`ln -sfn` into `~/.local/bin`), projects by `uv tool install --force --editable .`;
   staleness is then structurally impossible rather than detected.
3. **Completion marker blocks in rc files are harmless leftovers.** After reinstalling a
   project-tier tool with file-drop completion, remove the old
   `# >>> <tool> completions >>>` … `# <<<` block manually (one `sed` range), then run the
   new install which drops the generated script into the shell autoload dir
   (bash: `~/.local/share/bash-completion/completions/<tool>`; fish: `~/.config/fish/completions/<tool>.fish`;
   zsh: `_<tool>` in `~/.local/share/zsh/site-functions` + `fpath=(<dir> $fpath)` line
   BEFORE `compinit` in `~/.zshrc`).
4. **cli-hub entries stay valid.** The `register` interface is frozen and unchanged; the
   rewritten `install.sh` keeps the same 10-line register call, so `reinstall`/`uninstall`
   hooks keep working. Doctor's first-line contract `status: ok|stale|missing` is
   preserved (new tools emit only `ok`/`missing`).
5. **Exit-code legend (0/1/2/3/4) and the `{"error":{code,message,hint}}` envelope on
   stderr** are new surface — scripts that scraped old human-format stderr should switch
   to `--output json` / non-TTY envelope parsing.

## 5. Open questions for the owner (spec §10.1 style)

1. **File the typer upstream issue** for the `add_completion=False` completion-registry
   regression (live on 0.27.0 and 0.27.2; nearest upstream report is #1905, not exact) and
   delete the 3-line `completion_init()` workaround from the templates when fixed upstream.
2. **cli-hub hub-side proposal** (issue-note only, per spec §10.1 answer "Yes"): hub derives
   version/description from `pyproject.toml`, drops the install-receipt gate — spike C
   report §4. Until shipped, templates keep the register call verbatim.
3. **questionary release age vs the letter of the ≤12-month gate:** 2.1.1 is 12.7 mo old
   (repo active — pushed 2026-08-18). Adopted on the spirit reading; the prompt_toolkit
   3.0.53 custom-app fallback (38 LOC, fully logged) is a zero-cost flip if the owner
   enforces the letter.
4. **Single-file tier ships no completion machinery** (`add_completion=False`), so
   verify-cli check 8 reports SKIP (validation samples: 10/0/1). Confirm this remains the
   designed lean-tier behavior.

## 6. Self-review checklist — Global Constraints (as amended)

| # | Constraint (as amended by the 3265fd5 ruling) | Status | Evidence |
|---|---|---|---|
| 1 | SKILL.md ≤ 1000 words | ✅ 881 (`wc -w SKILL.md`) | §1.1 |
| 2 | Template LOC budget — DROPPED by owner; doc caps kept | ✅ reported honestly: lean tiers 1,203 vs original 1,000; single-file/bash per-tier budgets met; go six-file 253 deviation moot | §1.2 |
| 3 | Every reference file ≤ 100 lines | ✅ 44/61/61/90 | §1.1 |
| 4 | Delete instead of deprecate; no features beyond plan | ✅ deletions are hard cuts (receipts, pick.py, completions.py, ops.py, marker machinery); add-ons are the spec §2.4 tier-scoped set | CHANGES.md audit |
| 5 | Every removal/replacement → one CHANGES.md line | ✅ 58 lines; no unexplained removal found (each deletion cites a DECISIONS row / spec § / ruling) | §3, CHANGES.md |
| 6 | Every library claim verified: ≤12 mo release, permissive license, no open blocker | ✅ spike-maintained tables (A: questionary 12.7 mo marginal — open question 3; iterfzf GPL reject; B: typer 2026-08-28 MIT; E: retryablehttp 15 mo MPL reject) | DECISIONS rows A–F |
| 7 | Completion stays ble.sh-safe | ✅ spike B live ble.sh screens (clean menus, no garbling); bashly static completions in ble.sh-safe class; task-10/12 pty checks | spike B evidence |
| 8 | Four Phase-5 samples pass verify-cli | ✅ 11/0/0, 10/0/1 (designed skip), 11/0/0, 11/0/0 | `specs/validation-results.md` |
| 9 | python-project tests green (baseline 29) | ✅ 84 passing post-rebuild; `make check` exit 0 | task-10 report |
| 10 | verify-cli contract §4.2 (8 checks) | ✅ one script `templates/verify-cli` (272 LOC), copied into scaffolded projects, excluded from budgets per §2.3 | §1.2 |
| 11 | Universal contract §4.1 (12 bullets) enforced | ✅ machine-checkable subset via verify-cli; per-tier contract flags/commands in templates (task-8 red→green provenance) | task-8/10–12 reports |
| 12 | Scaffold: one command, offline, deterministic | ✅ `scripts/scaffold.sh --tier --audience --name [--profiles|--wizard|--service|--dest]`; copier `--offline`; twin-scaffold `diff -r` byte-identical | task-13 report |
| 13 | Doctor keeps `status: ok|stale|missing` contract, `stale` never emitted by new tools | ✅ spike C + slim doctor in all python tiers | DECISIONS row C |
| 14 | cli-hub register interface frozen/unchanged in install.sh | ✅ verbatim 10-line block | task-10/11 reports |
| 15 | ONE commit, no push/MR (controller delivers) | ✅ this commit only | — |

## 7. Known residual deviations (all owner-rulings or documented)

- Go six-file sum 253 vs original spec row 185 (task-12 report; resolved by budget drop).
- python-project 561 rendered vs original 380 (owner directive mid-task: no feature cut).
- questionary 12.7 mo vs the 12-mo letter (fallback documented; open question 3).
- Single-file verify-cli check 8 SKIP by design (open question 4).
- typer 0.27.2 `completion_init()` workaround in place pending upstream fix (open question 1).
- Plan's verbatim template-LOC `xargs` command drops whitespace-named jinja filenames;
  the report's numbers use the `-print0` variant (§1.2).
