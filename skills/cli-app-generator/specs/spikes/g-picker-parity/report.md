# SPIKE G — Picker parity: template wrappers vs workagent `pick.py`

Date: 2026-10-12 · Runtime: Python 3.14.6, questionary 2.1.1 (fresh install) · Go evidence reused from spike E (huh v2.0.3, go1.27.1)

## 1. What I ran

Fresh spike dir `specs/spikes/g-picker-parity/` (throwaway; `.venv/` gitignored):

- `menu.py` — 5 items, one with description, one duplicate label (`alpha` ×2: idx0 plain, idx3 with description).
- `probe_template_pick.py` — byte-identical copy of the `_pick` shape in `templates/python-project/src/{{ name }}/cli.py.jinja` (isatty guard + `create_app_session(stderr)` + `.ask()` + `except (KeyboardInterrupt, EOFError) → None`), returning `repr()` so the duplicate-label case is observable.
- `parity.py` — pty harness (stdout→file, stderr→pty, same geometry as spike A):
  - **g1** nav+erase: DOWN DOWN UP, Enter; assert stdout file; report pty tail.
  - **g2** ctrl-c-file: ^C byte + group SIGINT; assert stdout file content.
  - **g3** q/Esc: send `q`, then fresh spawn + Escape; report behavior.
  - **g4** dup: DOWN×3 to the second `alpha`, Enter; report disambiguation.
  - **g5** j/k: `jj`, Enter; report landing.
- Full log: `evidence-runs.txt` (29 lines).
- Go: no re-run needed — spike E already logged the huh matrix under pty (`specs/spikes/e-go/evidence/huh_*`, report §2.2); this spike re-reads that evidence against the current `profile.go.jinja` wrapper.

## 2. Observed evidence (Python)

| Probe | Result | Verdict |
|---|---|---|
| g1 arrows+Enter | `RESULT:'beta'`, exit 0, stdout ANSI-free | navigation + stdout-purity **PASS** |
| g1 erase | pty tail ends `Pick one: beta` answer-echo + cursor-restore `\x1b[?25h`; option block NOT erased (questionary leaves the answered prompt line) | erase-after-choose **GAP** (cosmetic; workagent erases the block) |
| g2 Ctrl-C | `STDOUT FILE (32 bytes): b'\nCancelled by user\n\nRESULT:None\n'` — leak **CONFIRMED** on the template path | stdout-leak **BUG (confirmed)** |
| g3 `q` | TIMEOUT/HUNG, 0-byte stdout; `q` is inert (likely type-ahead filter, no match) | q-abort **GAP** |
| g3 Esc | TIMEOUT/HUNG, 0-byte stdout; Esc alone does not abort | Esc-abort **GAP** |
| g4 duplicate labels | `RESULT:'alpha'` — idx0 vs idx3 indistinguishable | value-returns **GAP** (caller cannot resolve) |
| g5 `jj`+Enter | `RESULT:'gamma'` — j acts as move-down here, not type-ahead | j/k nav **PASS (this version)** — but version-dependent behavior, not a contract |

Root cause of the g2 leak (code-read, consistent with spike A X2 [ev:150]): questionary's `.ask()` catches `KeyboardInterrupt` internally and `print()`s `"Cancelled by user"` to **stdout** before returning `None`; the template's `except KeyboardInterrupt` therefore never fires on the SIGINT path — the `None` return works, but stdout is already polluted. This breaks universal contract §4.1.1 (stdout carries data only) on every Ctrl-C abort.

## 3. Observed evidence (Go, from spike E re-read)

Current `profile.go.jinja` wrapper already carries all four spike-E recipes (WithOutput(stderr) + stdin&stderr isatty guard + NO_COLOR→ThemeBase + abort→130); spike E logged TTY-select exit 0, TTY-abort exit 130, non-TTY fail-fast exit 1. Deltas vs workagent, by code-read of the template:

1. **Abort granularity**: `pickProfile` calls `os.Exit(130)` inside the helper on `ErrUserAborted` — correct code, wrong layer. A library-style helper should return a sentinel (e.g. `(string, bool)`) and let the caller map to 130; `os.Exit` inside makes the function untestable in-process and unusable from any future web/batch path.
2. **Empty-vs-abort conflation**: renderer failure, non-interactive, and (after fix 1) abort all surface as `""`. Callers distinguish "user aborted" from "no profiles" only by re-checking state. Minor.
3. **Duplicate labels**: options carry `Name` only, no description — same value-collision class as Python g4, plus no description footer at all (workagent dims it per item).
4. **Erase**: huh leaves the answered form on stderr (same cosmetic class as g1); acceptable — stderr is not data.

## 4. Minimal patch proposal (fix wrapper in place; no DECISIONS-choice change)

Python `cli.py.jinja` `_pick` (~10 added lines):
1. Suppress the library's stdout print: wrap the `.ask()` call with `contextlib.redirect_stdout(io.StringIO())` (or sys.stdout→stderr redirect) so `Cancelled by user` can never reach the data stream regardless of questionary internals. Fixes g2; robust to future questionary versions.
2. Unique values: `Choice(k, value=i, ...)` over `enumerate(choices)` and return the index (workagent `pick_index` semantics); callers index into their own list. Fixes g4; also enables duplicate display labels with distinct descriptions.
3. Empty-options guard: `if not choices: return None` before the isatty check.
4. Optional (cheap, workagent-matching): pre-check stdin for `q`/Esc? Not feasible inside questionary's event loop without custom bindings — document as wont-fix; Ctrl-C remains the abort key, now silent.

Go `profile.go.jinja` `pickProfile`:
1. Return `(string, bool)` — `false` = aborted — and move `os.Exit(130)` to the caller. Adds the empty-guard already present; keeps all four spike-E recipes.
2. Attach profile URL/description via `huh.NewOption(...).Description(...)` so the footer matches Python's `Choice(description=)`.

`verify-cli` addition (proposal, not implemented): picker check — pty run of the wizard-gated command's pick path asserting (a) stdout file holds only data lines, (b) Ctrl-C yields exit 130 with clean stdout. Reuse `parity.py` g1/g2 shapes.

## 5. DECISIONS impact

- Rows A/E choices (questionary/huh) stand; this spike proposes wrapper-level edits only, no library change, no new dependency.
- No row-C/B conflicts touched.
- Feature-port inventory (from the approved brief) stays deferred until the wrapper patch lands.

## 6. Concerns

1. `redirect_stdout` suppresses any legitimate stdout writes inside `.ask()` too — that is the point (contract: pickers render on stderr), but it must be scoped to the `.ask()` call only.
2. Index-return changes `_pick`'s signature (`str|None` → `int|None`); the two template call sites (`profile_remove`) need the matching one-line update — include in the same patch.
3. huh `(string, bool)` change touches `removeProfile` only; no other callers exist.
4. q/Esc abort parity is documented wont-fix for questionary (would need custom prompt_toolkit bindings ≈ the 38-LOC fallback); workagent parity on abort = silent Ctrl-C → None/130, which items 1+2 deliver.
