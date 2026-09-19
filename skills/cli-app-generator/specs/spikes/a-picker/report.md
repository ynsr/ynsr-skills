# SPIKE A — Python picker: questionary vs raw prompt_toolkit vs iterfzf

Date: 2026-09-20 · Runtime: Python 3.14.6 (linuxbrew), uv 0.11.26 · Worktree: `.worktrees/cli-app-generator-v2`

## 1. What I ran (exact commands)

Install (user-local, timed — total **6.2 s**):

```
uv venv --python 3.14 .venv                                  # 0.05 s
uv pip install --python .venv/bin/python questionary prompt_toolkit iterfzf
                                                             # 6.18 s
# resolved: questionary 2.1.1, prompt-toolkit 3.0.53, iterfzf 1.9.0.67.0, wcwidth 0.8.4
```

Version/license/release checks (PyPI JSON API + GitHub API; raw excerpts saved in `evidence/` — checked 2026-09-20).

Probes (all runnable from this dir; `./run_all.sh` replays everything into `evidence.txt`, including the native-defect and NO_COLOR runs):

- `ptytest.py` — pty harness with 3 modes, 80×24 winsize set via `TIOCSWINSZ`:
  - **t1** stdout purity: child gets stdin=pty, **stdout→file**, stderr=pty; harness waits for all 5 menu items on the pty, sends Enter, then asserts the file is exactly `RESULT:alpha\n` with no ANSI.
  - **t2** non-TTY: `timeout 5 <venv-python> <probe> </dev/null`; asserts rc=0 and stdout `RESULT:None\n`.
  - **t3** Ctrl-C restore: child fully on a pty; after render settle sends `^C` byte (terminal-driver path) **and** `killpg(SIGINT)` (out-of-band path); then runs `stty -a` on the pty slave and asserts `icanon`+`echo` restored; also greps the capture for cursor-show `\x1b[?25h` after hide `\x1b[?25l` and alt-screen exit `\x1b[?1049l`.
- `probe_questionary.py` — `questionary.select()` with `Choice(description=…)` + stderr-routing wrapper (the chosen integration shape).
- `probe_unwrapped.py` — bare `.ask()` with **no** wrapper/guards, isolated to log the native defects (unwrapped t1/t2/t3 + the X2 stdout-file Ctrl-C run).
- `probe_prompt_toolkit.py` — `radiolist_dialog` as-shipped (logged failing).
- `probe_prompt_toolkit_custom.py` — raw prompt_toolkit custom `Application` + `RadioList` widget, the honest integration shape for "raw prompt_toolkit".
- `probe_pt_eager_bug.py` — same custom app but constructed **outside** the stderr session, isolated to log the eager-construction trap.
- `probe_iterfzf.py` — `iterfzf()` subprocess probe.
- `evidence_extra.py` — X1 (radiolist Tab-then-Enter flow) and X2 (unwrapped Ctrl-C → stdout file) runs, appended to `evidence.txt`.
- `wrapper.py` — the drafted production wrapper (decision artifact, 18 AST-LOC), smoke-tested.
- Menu fixture (`menu.py`): 5 items `alpha beta gamma delta omega`, one with a description (`beta does the beta thing`) — identical across all probes.

## 2. Observed evidence

Full log: `evidence.txt` (142 lines; all claims below carry `[evidence.txt:N]` line refs; the stale pre-fix log is kept as `evidence-pre-fix.txt` for the 9-original-verdicts record).

**Primary matrix — wrapped/correct integration shapes (9 verdicts, all True):**

| probe | t1 stdout-pure | t2 non-TTY None, no hang | t3 Ctrl-C restores terminal |
|---|---|---|---|
| questionary 2.1.1 + wrapper | PASS [ev:6] | PASS 0.20 s [ev:11] | PASS, exit 0 [ev:21] |
| prompt_toolkit 3.0.53 custom app | PASS [ev:55] | PASS 0.10 s [ev:59] | PASS, exit 0 [ev:72] |
| iterfzf 1.9.0.67.0 | PASS [ev:79] | PASS 0.10 s [ev:83] | tty restored by fzf itself; probe dies by SIG2 = normal ^C semantics [ev:93-96] |

**1) stdout purity.** `t1 probe_questionary.py`: `STDOUT FILE (13 bytes): b'RESULT:alpha\n'` [ev:5], `stdout contains ANSI escapes: False` [ev:6], all 300 bytes of UI on the pty (stderr side) [ev:4]. Same for pt-custom (13 bytes [ev:53]) and iterfzf (13 bytes [ev:77]; fzf draws on `/dev/tty`).
**Native (unwrapped) failure — LOGGED**: `t1 probe_unwrapped.py`: `STDOUT FILE (111 bytes): b'? Pick one: (Use arrow keys)\r\n » alpha …'` [ev:101] — the whole UI rendered as *plain text* into redirected stdout. Root cause (code-read, confirmed by the logged run): default `AppSession` uses `create_output()` **without** `always_prefer_tty=True` (`application/current.py:68`; that flag exists only in `create_app_session_from_tty`). The 2-line wrapper `create_app_session(output=create_output(stdout=sys.stderr))` fixes it; questionary's `Application` is constructed at `.select()` call time, inside the block.
**Eager-construction trap — LOGGED**: `t1 probe_pt_eager_bug.py` (app built outside the session block): `STDOUT FILE (825 bytes)` of full UI [ev:123]. Code path: `self.output = output or session.output` at `application.py:263`, resolved at construction.

**2) non-TTY returns None without hanging.** t2 all three wrapped probes: `rc=0 wall=0.20s` / `stdout: b'RESULT:None\n'` [ev:8-11, 56-59, 80-83].
**Unwrapped failure — LOGGED**: `t2 probe_unwrapped.py`: `rc=1`, stderr traceback ending `raise EOFError` [ev:105-108] — `.ask()` catches `KeyboardInterrupt` but not `EOFError` (source: `questionary/question.py` try-clause). Also (code-read): `ask()` prints `"Cancelled by user"` via plain `print()` — and the X2 run shows exactly where it lands: `STDOUT FILE (306 bytes): b'…Cancelled by user\n\nRESULT:None\n'` [ev:150].

**3) Ctrl-C restores the terminal.** t3 questionary: `after SIGINT child: exit 0` [ev:13]; capture tail shows cleanup `\x1b[?2004l` (bracketed-paste off) + `\x1b[?12l\x1b[?25h` (cursor shown) [ev:14]; `stty -a` on the slave: `icanon restored: True; echo restored: True` [ev:21]. pt-custom: `exit 0` [ev:64], same stty result [ev:69]. iterfzf: `KILLED by signal 2` (group-SIGINT race in the probe's `waitpid` — standard ^C semantics) but fzf restored the tty itself: `icanon restored: True; echo restored: True` [ev:93], `alt-screen exit emitted: True` [ev:95].
**radiolist_dialog as-shipped failure — LOGGED**: t3 `after SIGINT child: TIMEOUT/HUNG (killed)` [ev:40], `icanon restored: False; echo restored: False` [ev:45], t1 `child status: TIMEOUT/HUNG (killed)` (Enter in the list doesn't exit) [ev:28]. Cause (code-read, behavior confirmed): default key bindings ignore `c-c`/`<sigint>` (`key_binding/bindings/basic.py:49,135` — both in the "don't do anything" list) and `radiolist_dialog` ships no c-c binding.
**Tab-then-Enter — LOGGED** (X1 run [ev:143-147]): `after Tab+Enter child: exit 0`, `alt-screen exit (1049l) seen: True`, `cursor-show after hide: True` — works, but requires Tab-then-Enter UX and alt-screen geometry, wrong for a CLI data picker (this is why the custom-app shape, not the shipped dialog, represents "raw prompt_toolkit").

**4) Integration LOC — exact counting command + output LOGGED** ([ev:150-156]; scope: non-blank/non-comment lines covered by module-level AST nodes, excluding the module docstring, `from menu import MENU`, and the `__main__` block):

| candidate | AST-LOC | notes |
|---|---|---|
| iterfzf | 12 | but GPL + fzf subprocess + descriptions only by string-mangling + stderr junk |
| **questionary + wrapper** | **18** (`wrapper.py`; raw non-blank count 24 [ev:156] — difference is the docstring) | descriptions native (`Choice(description=)` footer) |
| prompt_toolkit custom app | 38 | widget glue we own forever (bindings, layout, eager-output trap) |

**5) NO_COLOR/TERM=dumb — LOGGED** [ev:126-142]: `NO_COLOR=1 TERM=dumb` questionary t1: `exit 0`, stdout exactly `RESULT:alpha\n` [ev:130-132]; t3: `exit 0`, `icanon restored: True; echo restored: True` [ev:134, 139].

**6) Maintenance gate table** (PyPI JSON API + GitHub API, checked 2026-09-20; raw excerpts in `evidence/pypi-*.json`, `evidence/gh-*.txt`, `evidence/iterfzf-wheel.txt`):

| package | version | license | latest release | py req | gate |
|---|---|---|---|---|---|
| questionary | 2.1.1 | MIT | **2025-08-28** (12.7 mo) | ≥3.9 | release-age **marginal fail** (repo pushed 2026-08-18 [ev:gh-questionary]; recent open issues are feature-requests/dep-bumps only [ev:gh-questionary-open-issues]; runs clean on 3.14) |
| prompt_toolkit | 3.0.53 | BSD-3 | 2026-07-26 | ≥3.10 | PASS all gates |
| iterfzf | 1.9.0.67.0 | **GPL-3.0-or-later** | 2026-01-25 | ≥3.8 | license FAIL |
| InquirerPy | 0.3.4 | MIT | **2022-06-27** | ≥3.7,<4 | unmaintained → rejected **without probing** per task |

Blocker scan (code-read + repo check, not a logged run): prompt_toolkit #1820 "terminal left broken when binding ctrl-c" is open but only affects user bindings that `sys.exit()` bypassing cleanup — our `event.app.exit()` path restored the terminal in every logged t3 run.

**7) Bonus: iterfzf vendors its own fzf — LOGGED** (`evidence/iterfzf-wheel.txt`): installed package contains `fzf` binary 4,411,544 bytes + `fzf-0.67.0-release.json` (fzf 0.67.0 embedded; system fzf not needed; system fzf here is also 0.67.0-debian). Wheel-bundled binary = version coupling + 4 MB payload; irrelevant now given GPL.

## 3. DECISIONS row

| Spike | Choice | Why | Rejected | Evidence |
|---|---|---|---|---|
| A — Python picker | **questionary 2.1.1 (MIT, PyPI) + 18-LOC stderr wrapper** (`create_app_session(output=create_output(stdout=sys.stderr))` around `.ask()`); fallback if controller enforces release-age gate strictly: **prompt_toolkit 3.0.53 (BSD-3) custom Application, 38 LOC** | Only candidate meeting (a)(b)(c) with least LOC: 18 vs 38. Wrapper fixes logged native defects: default AppSession renders UI into redirected stdout (111 bytes [ev:101]); `.ask()` prints "Cancelled by user" to stdout on Ctrl-C (306-byte stdout file [ev:150]) and propagates EOFError on non-TTY [ev:108]. Native `Choice(description=)` footer for the description requirement; Ctrl-C/EOF → None; icanon+echo+cursor restored on pty (stty -a verified [ev:21]). Works on 3.14, NO_COLOR/TERM=dumb logged clean [ev:126-142]. Marginal: release 12.7 mo old, but repo pushed 2026-08-18 — flagged, controller may enforce letter and take the probed pt fallback | iterfzf — GPL-3.0-or-later license gate fail (METADATA License-Expression in evidence/iterfzf-wheel.txt; +fzf subprocess, no description support, stderr junk `inappropriate ioctl` [ev:84]); InquirerPy — last release 2022-06-27, unmaintained, rejected without probing; prompt_toolkit `radiolist_dialog` as-shipped — default bindings ignore Ctrl-C (hang, raw mode left set [ev:40-45]), no output= kwarg, Tab-Enter UX + alt-screen geometry [ev:143-147] | `specs/spikes/a-picker/{report.md,evidence.txt,evidence/,{ptytest,probe_questionary,probe_unwrapped,probe_prompt_toolkit,probe_prompt_toolkit_custom,probe_pt_eager_bug,probe_iterfzf,evidence_extra}.py,wrapper.py,run_all.sh}` |

## 4. Concerns

1. **Release-age letter vs spirit (needs controller ruling):** questionary 2.1.1 is 12.7 months old — over the ≤12-month binding gate by ~3 weeks; the repo is demonstrably active (pushed 2026-08-18, dependabot merges same week). I chose the engineering-spirit reading and quantified the letter-enforcement fallback (prompt_toolkit custom app, 38 LOC, logged passing all three modes). Both paths are fully logged; flipping costs nothing.
2. **Wrapper ordering invariant:** prompt_toolkit resolves `Application.output` eagerly at construction (application.py:263, repro logged [ev:123]). Template code must call `.select()` **inside** the `create_app_session` block — our wrapper enforces this; hoisting the app out silently reintroduces stdout pollution (t1 catches it).
3. **Keep the guards:** without `isatty` → EOFError traceback on `</dev/null` (logged [ev:107]); without `try/except` → questionary prints "Cancelled by user" to stdout (logged [ev:150]). Both guards are evidence-necessary, not belt-and-suspenders.
4. **If anyone drops to raw prompt_toolkit:** default bindings ignore `c-c`/`<sigint>` (basic.py:49,135), `RadioList.enter` doesn't exit (widgets/base.py:790-794, 836-844 — code-read; the as-shipped hang is logged [ev:28,40]), and eager output resolution traps — three documented traps; use `wrapper.py`/questionary instead.
5. **Harness fidelity:** probes run on a synthetic pty (80×24, TIOCSWINSZ set, TIOCSCTTY). ble.sh interplay not testable from a bare pty — the ble.sh completion-invariant concern doesn't apply to in-process pickers (no shell integration), but a visual check in a real terminal is cheap at integration time.

## Fix report (2026-09-20, post-review)

Review verdict: decision sound, report overclaimed beyond artifacts. All must-fixes resolved by **logging** (no claims downgraded):

1. **radiolist_dialog failures now logged**: `probe_prompt_toolkit.py` added to `run_all.sh`; its t1 (`TIMEOUT/HUNG`, 0-byte stdout) and t3 (`icanon restored: False; echo restored: False`) are in `evidence.txt` [ev:25-48]. Tab-then-Enter claim logged via new `evidence_extra.py` X1 run [ev:143-147].
2. **111-byte unwrapped stdout capture now logged**: new `probe_unwrapped.py` (bare `.ask()`); t1 run shows `STDOUT FILE (111 bytes)` [ev:97-103].
3. **Eager-construction trap logged**: new `probe_pt_eager_bug.py` (app built outside session); t1 shows 825-byte UI in the stdout file [ev:119-125]. RadioList-enter trap: the as-shipped t1 hang [ev:28] is the behavioral log; the `widgets/base.py` line refs remain code-read citations.
4. **Verdict counts corrected**: primary matrix is 9/9 True (was miscounted as 11; NO_COLOR was an unlogged smoke). NO_COLOR t1+t3 now logged [ev:126-142] (2 more True verdicts, explicitly scoped as NO_COLOR runs, separate from the 9).
5. **LOC corrected**: wrapper is **18 AST-LOC** (was "20/17"); probe_questionary.py probe itself is 20. Exact counting command (AST scope) + output appended to `evidence.txt` [ev:150-156], including the raw 24-non-blank count for transparency.
6. **Evidence path list updated** for the controller: `probe_prompt_toolkit.py` and `probe_unwrapped.py`/`probe_pt_eager_bug.py`/`evidence_extra.py` added (see DECISIONS row).
7. **"Cancelled by user" claim upgraded from pty-tail inference to direct stdout-file proof**: X2 run shows the 306-byte stdout file containing it [ev:150].
8. **API/wheel claims saved to `evidence/`**: `pypi-{questionary,prompt_toolkit,iterfzf,InquirerPy}.json`, `gh-questionary.txt`, `gh-questionary-open-issues.txt`, `gh-python-prompt-toolkit.txt`, `iterfzf-wheel.txt` (incl. dist-info `License-Expression: GPL-3.0-or-later` and the vendored 4.4 MB `fzf` binary + `fzf-0.67.0-release.json` listing). All checked 2026-09-20.

Full replay after fixes: `./run_all.sh && .venv/bin/python evidence_extra.py` → rc=0, all logged verdicts True (13 in run_all + X1/X2).
