# SPIKE F — Scaffolder: copier vs plain scaffold.sh

Status: **DONE**

## 1. What I ran (exact commands)

Env: uv 0.11.26, Python 3.14.6, bash 5.3.9, 20-core x64 Linux. No sudo; nothing installed system-wide — copier ran via `uvx` (user-local uv cache).

```bash
# copier availability + timing
uvx copier --version            # cold: 20.06s (downloads 21 packages), warm: 0.31s, --offline: 0.32s

# copier: local-path copy, feature flag ON
uvx copier copy ./copier-template dest-a -d tier=python-project -d audience=agent -d name=demo -d profiles=true -f
# run 2 (determinism)
uvx copier copy ./copier-template dest-b ... -f
# run 3 (flag OFF)
uvx copier copy ./copier-template dest-c ... -d profiles=false -f
# non-TTY probe (must not hang)
timeout 15 uvx copier copy ./copier-template dest-probe -d tier=python-project < /dev/null
# dry-run probe
uvx copier copy ... --pretend

# scaffold.sh (187 LOC)
./scaffold.sh --tier python-project --audience agent --name demo --dest dest-sh-1 --profiles
./scaffold.sh ... --dest dest-sh-2 --profiles          # determinism run
./scaffold.sh ... --dest dest-sh-3                     # flag OFF
./scaffold.sh --tier bash-tool --audience human --name mytool --dest dest-sh-4
./scaffold.sh --tier bogus ...                          # exit-code check
./scaffold.sh --tier go-cli ... --dry-run

# byte-parity between the two approaches
diff -r dest-a dest-sh-1
```

Template dir: `copier-template/` with `copier.yml` (params: tier, audience, name, profiles), two content templates (`README.md.jinja`, `src/{{ name }}.py.jinja`), one conditional file (`{% if profiles %}AGENT_PROFILE.md{% endif %}.jinja`).

Conditional-file syntax (from copier docs, "Conditional files and directories"): template the file NAME itself — `{% if use_precommit %}.pre-commit-config.yaml{% endif %}.jinja`; the `.jinja` suffix must sit OUTSIDE the Jinja condition. Copier 9.18.2, MIT, released 2026-09-07, requires_python >=3.10 — passes the binding criteria (≤12mo, permissive, Python ≥3.12-compatible).

## 2. Observed evidence

### copier path — all pass
- **Local path, offline**: `uvx --offline copier --version` → `copier 9.18.2` (0.32s) from warm uv cache — command, output, and exit code logged in evidence/copier-runs.log. Copy from `./copier-template` (non-git local dir) worked with zero network.
- **Determinism**: `diff -r dest-a dest-b` → `RESULT: IDENTICAL` (byte-identical; no `.copier-answers.yml` is written for a non-git local template — `ls -a dest-a dest-b` in the log shows none).
- **Feature flag**: `profiles=true` → `AGENT_PROFILE.md` created; `profiles=false` → absent (`diff -r dest-a dest-c` → `Only in dest-a: AGENT_PROFILE.md`). Exactly the one file toggles; nothing else changes.
- **Non-TTY, all data given**: completes without prompting (exit 0, no hang).
- **Non-TTY, missing data**: fails fast with actionable message — ``Interactive session required: Use `--defaults` and/or `--data`/`--data-file````, exit 1 (satisfies the universal "never block on input" contract; full stderr + exit logged in evidence/copier-runs.log).
- **`--pretend`**: true dry-run — logs `create README.md`, `create src/x.py` to stderr, creates nothing.
- **File modes carried**: `src/demo.py` → 775 (executable), text files → 664.
- **Gotcha found**: legacy `_copier.yml` filename is copied verbatim into the destination. Renamed to modern `copier.yml` → does NOT leak into dest. Documented upstream gotcha, now encoded in our template.

### scaffold.sh path — all pass
- **Determinism**: `diff -r dest-sh-1 dest-sh-2` → `RESULT: IDENTICAL`.
- **Feature flag**: `--profiles` includes `AGENT_PROFILE.md`; without it → `Only in dest-sh-1: AGENT_PROFILE.md`.
- **stdout data-only**: per-file lines to stdout, all logs to stderr; `2>/dev/null` run exits 0 with clean stdout.
- **Skeleton runs**: `python3 dest-sh-1/src/demo.py` → `demo ready (tier=python-project, audience=agent)`; `./dest-sh-4/bin/mytool` (755) → `mytool ready (tier=bash-tool, audience=human)`.
- **Exit codes**: unknown tier → 1 + usage on stderr; missing required params → 1 + usage; dest-exists → 2.
- **`--dry-run`**: logs plan to stderr, writes nothing, `/tmp/never-exists` never created.

### Content parity between approaches
`diff -r dest-a dest-sh-1` → **`RESULT: IDENTICAL`** — copier and scaffold.sh produce **content-identical** trees for identical params (apples-to-apples comparison). Mode delta observed: `dest-a/src/demo.py` is 775 vs `dest-sh-1/src/demo.py` 755 (copier preserves the template file's exec bits; scaffold.sh chmods 755 — both executable); plain `diff -r` ignores mode bits, so parity here is content-only. The copier-vs-copier determinism claim (byte-identical `diff -r`) stands separately.

### Timing / install effort
| path | cold | warm | offline |
|---|---|---|---|
| copier via uvx | 20.06s (first, downloads 21 pkgs) | 0.31s | 0.32s (`--offline`, needs warm cache) |
| scaffold.sh | n/a (no install) | ~0.05s | always works |

## 3. Maintenance-touchpoint comparison (primary criterion)

Maintainer surface LOC: **copier = 66 lines across 4 declarative files** (29 copier.yml + 22 README.jinja + 11 src.py.jinja + 4 conditional filename); **scaffold.sh = 187 lines in one file** (~90 of which are heredoc template content equivalent to copier's 36 content lines; ~100 lines are parsing/validation/plumbing machinery).

| Change scenario | copier touchpoints | scaffold.sh touchpoints |
|---|---|---|
| Change a template file's content | **1** (edit the .jinja) | **1** (edit the heredoc) — TIE |
| Add one feature flag (optional file) | **2** (copier.yml question + prefix filename with `{% if %}`) | **3** (usage text, parser case, emit case branch; `validate()` needs no profiles check) |
| Add one tier's file set | **2** (copier.yml choice + new template file) | **3** (usage text, validate case, emit case branch) |
| Change flag semantics (tri-state, choices) | **1** (edit copier.yml question) | **2–3** (parser + validate + case) |

copier wins every scenario except content-edit (tie). Additional maintenance deltas:
- copier: declarative conditionals in filenames; **file modes carried automatically**; hand-rolled `subst()` sed-escaping bug class (defended in scaffold.sh with `esc_sed`, but it's ours to maintain forever) is avoided entirely; **built-in `recopy`/update machinery** — out of scope for one-shot generation but the natural v2 follow-up, free with copier.
- copier costs: 21-package runtime dependency, second templating dialect (Jinja) to learn, one documented sharp edge (legacy `_copier.yml` leaking), requires warm uv cache for offline use (solvable once via `uv tool install copier`).

## 4. Decision

**Choice: copier** (`uvx copier copy` from a local template path, `copier.yml` + Jinja-conditional filenames).

Why (≤5 lines):
1. Primary criterion (less-to-maintain): fewer touchpoints in every change scenario except content-edit (tie); 66 vs 187 LOC; conditionals/modes/update machinery are declarative, not hand-rolled.
2. Hard requirements pass: offline (uv-cache warm + `--offline`, 0.32s), deterministic (byte-identical `diff -r` across copier runs), local-path template, non-TTY-safe.
3. Content lives as real files (editor tooling, no heredoc/sed-escaping risk) — the sed-escaping bug class in scaffold.sh's `subst()` is eliminated, not just defended.
4. copier's `recopy`/update machinery is the natural follow-up for template revs and comes free.
5. Costs accepted: 21-package uvx dep (operational, cached), Jinja dialect, `_copier.yml` legacy-name gotcha (use `copier.yml`).

Rejected: **scaffold.sh** — 3× the LOC, more touchpoints per change scenario, owns a permanent sed-escaping/file-mode/plumbing maintenance burden in bash for a problem copier already solved declaratively.

## DECISIONS row

| F — scaffolder | copier (`uvx copier copy <local-template> <dest> --data ...`) | Less-to-maintain (primary): fewer touchpoints in every change scenario (1–2 vs 1–3), 66 vs 187 LOC, declarative conditionals, automatic file-mode carrying; offline + deterministic both proven (byte-identical diff -r across copier runs, `uvx --offline` works); `recopy`/update machinery free for v2 | scaffold.sh — 3× LOC, 3+ touchpoints per flag/tier change, permanent sed-escaping + plumbing maintenance burden in bash | skills/cli-app-generator/specs/spikes/f-scaffold/evidence/{copier-runs,scaffold-runs,parity-and-loc}.log; copier-template/; scaffold.sh |
|---|---|---|---|---|

## 5. Concerns

1. **`_copier.yml` leaks into destination** — only with the legacy filename. Our template uses `copier.yml` (no leak, verified). Worth a note in the skill's template-authoring docs if copier is adopted.
2. **Offline requires a warm uv cache** — first-ever copier run downloads 21 packages (20s). Fully offline after that (`--offline` works), or make it permanent with `uv tool install copier` in the skill's setup. scaffold.sh has no such precondition — if air-gapped cold-start is a hard requirement for the skill, this is the one real argument for the bash path.
3. **shellcheck not installed in this env** (exit 127) — scaffold.sh is unlinted; if the bash path were ever chosen, shellcheck must gate it. Moot under the copier decision.
4. **`.copier-answers.yml` not written in these runs** — for a non-git local template (version None) copier wrote no answers file (`ls -a` proof in the log). Docs: answers recording defaults on with no disable option (answers_file setting), so if the template later ships from a git-tagged repo, expect the file to appear — include it in the expected tree.
5. **Template version is `None` for non-git local templates** — fine offline, but means no version pinning/updates for local-path use. If template revs matter later, the skill should ship the template inside a git repo (copier tags then work).

## Fix report

Review (Main) found 5 report accuracy issues; all fixed, report-only. The two missing artifacts were appended to evidence/copier-runs.log (scratch log only, as instructed).

1. **[fixed] Determinism parenthetical (line 44)** — removed the false "(byte-equal, including `.copier-answers.yml`)": no answers file exists in dest-a/dest-b (`ls -a` proof appended to evidence/copier-runs.log).
2. **[fixed] Cross-scaffolder parity (lines 60–61)** — "Byte parity" downgraded to **content-identical** with the observed mode delta (dest-a/src/demo.py 775 vs dest-sh-1/src/demo.py 755; plain `diff -r` ignores mode bits; stat proof appended to log). Copier-vs-copier determinism claim unchanged.
3. **[fixed] Missing offline artifact** — ran `uvx --offline copier --version` (→ `copier 9.18.2`, exit 0), appended command + output + exit to evidence/copier-runs.log; §2 offline bullet now references it.
4. **[fixed] Missing-data quote (line 47)** — failing probe re-run and appended to evidence/copier-runs.log (`Warning: Input is not a terminal (fd=0).` + `Interactive session required: ...`, exit 1); quote corrected to match the log verbatim.
5. **[fixed] Flag touchpoints 4→3 (lines 76, 99)** — `validate()` has no profiles check; table now 3 (usage text, parser case, emit case branch); DECISIONS row updated to (1–2 vs 1–3) and "3+ touchpoints per flag/tier change".
6. **[also corrected, same error class as #1] Concern #4** — rewritten to observed reality: no `.copier-answers.yml` in these runs (non-git local template, version None); docs' default-on answers recording for git-tagged templates noted.
