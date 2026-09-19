# SPIKE B — Python completion by file drop (Typer/Click-generated scripts)

Date: 2026-09-20. Scratch: `skills/cli-app-generator/specs/spikes/b-completion/`.
Runtime: Python 3.14.6 (venvs via uv 0.11.26). All interactive tests in real ptys (python `pty.fork` + `pyte` screen rendering; driver `evidence/blesh_screens3.py` et al.). Throwaway `HOME=/tmp/spikehome` everywhere — no real rc dirs touched.

## 0. Library pin + verification criteria

- **typer 0.27.2** — latest on PyPI (checked via `pip index versions typer` + `pypi.org/pypi/typer/0.27.2/json`). Release date **2026-08-28** (0.27.1: 2026-08-03; 0.27.0: 2026-07-15; 0.26.8: 2026-06-26).
- License **MIT**, `requires_python >=3.10` → meets the binding criteria (≤12 months old ✓, permissive ✓, Python ≥3.12 target ✓ — verified live on 3.14.6, both venvs `uv venv --python 3.14`).
- Install: `uv venv --python 3.14 .venv && uv pip install --python .venv/bin/python typer` (0.27.2) and `.venv-bug` pinned `typer==0.27.0`. Wall time ~4 s each.

## 1. What I ran (exact commands)

Test app (add_completion=False, 2 subcommands, dynamic `autocompletion=` reading a local dir lazily) — `app/__main__.py`, entry `bin/tool` (PATH-installed so `_detect_program_name()` → `tool` → var `_TOOL_COMPLETE`):

```console
# Bug repro (typer 0.27.0 venv)
$ SPIKE_ITEMS_DIR=/tmp/spikehome/.config/spike-items _TOOL_COMPLETE=complete_bash .venv-bug/bin/python tool i
Shell bash not supported.        # exit=1
$ SPIKE_ITEMS_DIR=... _TOOL_COMPLETE=complete_bash .venv-bug/bin/python tool items --pick a
Shell bash not supported.        # exit=1

# Same on latest 0.27.2 (.venv) — root, subcommand, flag, empty, source:
$ _TOOL_COMPLETE=complete_bash .venv/bin/python tool i
Shell bash not supported.        # exit=1
$ _TOOL_COMPLETE=complete_bash .venv/bin/python tool items --pick a
Shell bash not supported.        # exit=1
$ _TOOL_COMPLETE=complete_bash .venv/bin/python tool items ''
Shell bash not supported.        # exit=1
$ _TOOL_COMPLETE=source_bash  .venv/bin/python tool
Shell bash not supported.

# click-8 word order (what an agent would try first from click docs):
$ _TOOL_COMPLETE=bash_complete .venv-bug/bin/python tool i
Shell complete not supported.    # exit=1  (typer keeps click-7 order: complete_bash)

# Workaround variant (appwk/__main__.py = 3-line patch inlined), both versions:
$ COMP_WORDS="tool i" COMP_CWORD=1 _TOOLW_COMPLETE=complete_bash .venv-bug/bin/python toolw i
items                            # exit=0
$ COMP_WORDS="tool items --pick a" COMP_CWORD=3 _TOOLW_COMPLETE=complete_bash .venv-bug/bin/python toolw items --pick a
alpha                            # exit=0
$ COMP_WORDS='toolw i' _TYPER_COMPLETE_ARGS='toolw i' _TOOLW_COMPLETE=complete_zsh .venv/bin/python toolw i
_arguments '*: :(("items":"List items, optionally picking one."))'
$ _TOOLW_COMPLETE=complete_fish _TYPER_COMPLETE_FISH_ACTION=get-args _TYPER_COMPLETE_ARGS=() .venv/bin/python toolw
items	List items, optionally picking one.
show	Show a single key.
```

File-drop generation (same code path `--show-completion` uses; exposed because the workaround initializes the class registry):

```console
$ .venv/bin/python -c 'import typer.completion as tc; tc.completion_init(); \
    print(tc.get_completion_script(prog_name="tool", complete_var="_TOOL_COMPLETE", shell="bash"))'
# → dropped to ~/.local/share/bash-completion/completions/tool  (HOME=/tmp/spikehome)
# fish → ~/.config/fish/completions/tool.fish ; zsh → a dir on fpath as `_tool`
```

Live pty tests: `python3 pty_drive.py rc_drop.sh …` (bash), `blesh_screens3.py` (ble.sh), `zsh_screens.py` (ZDOTDIR scratch), `fish_screens.py`. Latency: `python -X importtime -c 'import app.__main__'` and full-server wall clock ×10.

## 2. Observed evidence

### 2.1 The typer ≥0.27 bug — reproduced AND still present on latest

Exact output (both 0.27.0 and 0.27.2, all four instruction suffixes):

```
Shell bash not supported.        # stderr, exit 1   (_TOOL_COMPLETE=complete_bash)
Shell complete not supported.    # stderr, exit 1   (_TOOL_COMPLETE=bash_complete, click-8 order)
```

**Root cause (verified in source, both versions identical):** `typer/main.py → get_command()` calls `get_install_completion_arguments() → get_completion_inspect_parameters() → completion_init()` **only under `if typer_instance._add_completion:`** (3 sites: lines ~1174/1184/1202). `completion_init()` (`typer/_completion_classes.py:224`) is what registers `BashComplete/ZshComplete/FishComplete/PowerShellComplete` into `typer._click.shell_completion._available_shells`. With `add_completion=False` the registry stays `{}` — measured directly:

```
after get_command(add_completion=False): {}        # .venv-bug AND .venv
```

so `typer.completion.shell_complete()` → `get_completion_class("bash") → None` → `echo "Shell bash not supported." ; exit 1` (`typer/completion.py:126-130`). All four generated tools (bash/zsh/fish/powershell servers) are dead the same way.

**Upstream:** searched `api.github.com` (`repo:fastapi/typer "Shell bash not supported"`, `add_completion False completion`, issues+PRs since 2026-06) — **no exact upstream issue exists as of 2026-09-20**; nearest are [#1905](https://github.com/fastapi/typer/issues/1905) (documents the lazy `add_completion_class` registry design, different symptom) and [#498](https://github.com/fastapi/typer/issues/498) (decouple options from autocompletion). 0.27.0 release notes contain no completion entry. Recommend filing an issue; the task's "regression shipped 2025-08 in four generated tools" could not be confirmed as a filed report.

### 2.2 Fix status on latest typer → NOT FIXED → keep workaround

0.27.2 (`.venv`) reproduces byte-identical `Shell bash not supported.` for every position (§1). Decision: **keep the shortest workaround** — 3 lines in the generated app module before `app = typer.Typer(add_completion=False)` (full patch + rationale: `workaround-completion-init.patch.md`):

```python
import typer.completion as _typer_completion
# typer >=0.27: add_completion=False never registers shell completion classes,
# so the env-var completion server dies with "Shell bash not supported."
_typer_completion.completion_init()
```

Verified on **0.27.0 and 0.27.2**: bash/zsh/fish servers return correct candidates (§1 block). Idempotent, no-ops under add_completion=True, costs 2.6 ms import (`typer.completion` 33896 vs 31245 µs cumulative).

### 2.3 File-drop installs (HOME=/tmp/spikehome) + generated script heads

- **bash** → `~/.local/share/bash-completion/completions/tool` (bash-completion's lazy loader path; test sourced it from rcfile). Head (exact as-generated bytes):
  ```
  _tool_completion() {
      local IFS=$'
  '
      COMPREPLY=( $( env COMP_WORDS="${COMP_WORDS[*]}" \
                     COMP_CWORD=$COMP_CWORD \
  ```
  (the `IFS=$'\n<newline>'` is a literal embedded newline — valid bash; see Concerns)
- **fish** → `~/.config/fish/completions/tool.fish`, 1 line:
  ```
  complete --command tool --no-files --arguments "(env _TOOL_COMPLETE=complete_fish _TYPER_COMPLETE_FISH_ACTION=get-args _TYPER_COMPLETE_ARGS=(commandline -cp) tool)" --condition "env _TOOL_COMPLETE=complete_fish _TYPER_COMPLETE_FISH_ACTION=is-args _TYPER_COMPLETE_ARGS=(commandline -cp) tool"
  ```
- **zsh** → file named **`_<prog>`** in an fpath dir; rc lines (documented, marker-free):
  ```zsh
  fpath=("$HOME/.local/share/zsh/site-functions" $fpath)   # BEFORE compinit
  autoload -Uz compinit
  compinit
  ```
  Generated `zfunc/_tool` head: `#compdef tool` / blank / `_tool_completion() {` / `  eval $(env _TYPER_COMPLETE_ARGS="${words[1,$CURRENT]}" _TOOL_COMPLETE=complete_zsh tool)` / `}`.
- Prog-name caveat: the complete-var is derived from the *detected* prog name — `python tool.py i` derives `_TOOL.PY_COMPLETE` → server silently not invoked (exit 2 usage error). Tests/installs must use the installed name (`tool`).

**Live pty results (plain bash, `evidence/bash_file_drop_transcript.txt`):**
```
tool ␉␉            → menu:  items  show
tool items --pick ␉␉ → menu:  alpha  beta   gamma     ← dynamic callback through env-var runtime
tool show a␉        → inserts: tool show alpha
tool i␉             → inserts: tool items
```

**zsh (brew 4.0.x zsh 5.9, `evidence/zsh_screens.txt`):** `tool ␉␉` → menu with help strings (`items  -- List items, optionally picking one.` / `show -- Show a single key.`); `tool items --pick ␉` → `alpha beta gamma`; `tool show a␉` → inserts `alpha`; `tool i␉` → inserts `items`. fpath+compinit install verified live.

**fish (brew fish 4.9.3, `evidence/fish_screens.txt`, `evidence/fish_raw.py`):** state honestly — the first run showed file-name menus because the pty child lacked PATH (tool not on PATH → fish refuses to autoload `tool.fish` → file fallback); **not a file-drop defect**. With PATH exported: `tool ␉` → menu `items (List items…) show (Show a single key.)`; `tool items --pick ␉` → `alpha beta gamma`; `tool show a␉` → raw stream shows completion accepted: `tool show a` → `tool show alpha`. Raw fish probe also: `complete --do-complete "tool "` → `items/show`; `"tool items --pick "` → `alpha beta gamma` (once `tool` is on PATH). Prefix-insert step E was inconclusive in the transcript (stale pyte row + fish's gray autosuggestion rendering `--pick` as dim text after accepting `items`) — flagged, not load-bearing.

### 2.4 Dynamic callbacks through the static script + latency

- Dynamic value completion confirmed routing through the env-var runtime in **all three live shells** (menus `alpha beta gamma` above) and via direct server invocation (§1).
- Lazy import: callback does `os.listdir` only — `-X importtime` profile identical before/after callback execution; only delta is `typer.completion` registry init (+2.6 ms). No top-level heavy import in the callback path. ✓
- **importtime (Python 3.14):** slowest cumulative lines for `import app.__main__` (`evidence/importtime_app.log`):
  ```
  31220 µs  app.__main__          ← whole import
  29546 µs    typer
  16864 µs      typer.main
   9717 µs        typer._click.exceptions
   9629 µs          typer._click.core
   4629 µs            _colorize      (rich-less colorizer)
   4590 µs            inspect
  ```
  Full server process wall clock (spawn → completions, 10 runs): **best 0.05 s / median 0.05 s**. Every Tab costs one fresh interpreter ≈ 50 ms — acceptable for agent-driven CLIs; noted as inherent to the file-drop + subprocess model.

### 2.5 ble.sh LIVE test (mandatory; real ble.sh at `~/.local/share/blesh/ble.sh`)

Spawned `bash --rcfile rc_blesh.sh` (`source /home/bs/.local/share/blesh/ble.sh --noattach` + source the file-drop script + `ble-attach`) inside a pty; keystrokes driven by `evidence/blesh_screens3.py`, screen states via pyte. **Canonical transcript: `evidence/blesh_screens3.txt`** (earlier raw byte stream: `evidence/blesh_raw_transcript.txt`). Steps below quote `blesh_screens3.txt`:

```
A: 'tool ' Tab            → 0| $ tool            1| items show                 ← clean candidate menu, no garbling
B: C-c                    → fresh prompt, no residue
C: 'tool items --pick ' Tab → 0| $ tool items --pick  1| alpha beta  gamma       ← dynamic menu through ble.sh
D: Tab#2                  → 0| $ tool items --pick alpha                            ← accepted
E: C-c                    → clean
F: 'tool show a' Tab      → 0| $ tool show alpha                                    ← single dynamic match inserted
G: C-c, 'tool i' Tab      → 0| $ tool items                                          ← prefix insert
J: 'tool show x' Tab      → 0| $ tool show blesh_screensx [blesh_screens.txt]        ← SEE CONCERN: -o default file fallback leak
K: C-c + 'tool items' RET → command ran, prompt healthy, shell alive
```

Canonical run: no garbling, no repeated errors, no decode errors, no hang; shell stays healthy after C-c and accepts new commands (step K). ble.sh-safety: **PASS**.

**Honesty note on earlier runs:** an intermediate transcript (`evidence/blesh_raw_transcript.txt`, steps F/G) DOES show garbled lines (`alphattttool` etc.) — these were harness artifacts of my pty driver (raw Ctrl-U injection racing ble.sh's keymap; an earlier instrumented logging wrapper recursing), not behavior of the generated completion script. `blesh_screens3.txt` is the canonical clean run (C-c resets); its only genuine finding is the J-step fallback leak. The "no garbling" claim applies to the canonical run only.

## 3. DECISIONS row

| B — Python completion (file drop) | Adopt typer file-drop: bash `~/.local/share/bash-completion/completions/<tool>`, fish `~/.config/fish/completions/<tool>.fish`, zsh `_<tool>` in `~/.local/share/zsh/site-functions` + `fpath=(<dir> $fpath); autoload -Uz compinit; compinit` BEFORE compinit; typer pinned 0.27.2 (2026-08-28, MIT). KEEP 3-line workaround `typer.completion.completion_init()` in template (regression live on 0.27.0 AND 0.27.2: `add_completion=False` → registry never initialized → server prints `Shell bash not supported.` exit 1; all four shells' servers dead; fix verified on both versions) | Reproduced bug in 2 typer versions; file-drop verified live in real ptys for bash/zsh/fish + real ble.sh (clean menus, dynamic values, single-match + prefix insert, no garbling); lazy import proven (callback = os.listdir only); 50 ms/Tab subprocess cost acceptable | marker-block rc edit — deleted (file-drop + documented fpath lines make rc surgery unnecessary; ble.sh-safe by construction); click-8 env instruction `bash_complete` — wrong order for typer (expects click-7 `complete_bash`); click's own `--show-completion` under add_completion=False — option doesn't exist in that mode | evidence/bash_file_drop_transcript.txt, evidence/blesh_screens.txt, evidence/zsh_screens.txt, evidence/fish_screens.txt, evidence/importtime_app.log, workaround-completion-init.patch.md |

## 4. Concerns

1. **`-o default` filename-fallback leak** (ble.sh step J, also plain bash): when the dynamic callback returns no candidates, typer's `complete -o default -F _tool_completion <tool>` falls back to filename completion — file names offered as values (cosmetic, but pollutes agent UX). Template may want to emit its own `complete` line (drop `-o default`, or keep only for Path-typed params).
2. **Generated bash file contains a literal embedded newline** inside `local IFS=$'...'` — valid, but fragile under linters/beautifiers; template could rewrite to `local IFS=$'\n'` (verified equivalent live).
3. **No upstream issue exists** for the add_completion=False regression (searched 2026-09-20; nearest #1905/#498). Filing one to fastapi/typer is recommended; delete the workaround when upstream registers classes unconditionally.
4. **Prog-name coupling:** complete-var derives from the detected prog name (`tool.py` → `_TOOL.PY_COMPLETE` → server silently skipped). Template tests must exercise the installed name.
5. fish 4.9.3 in a pty waits ~10 s for terminal-capability query timeout (PDA) — dumb-pty harness artifact, not a file-drop defect; fish prefix-insert step E left an inconclusive transcript (fish's gray autosuggestion renders inside the line).
6. zsh/fsh/brew installs for the spike: `brew install --quiet zsh fish` (user-local, 69 s wall) — recorded as install-effort evidence.
7. **Scratch hygiene (controller action):** before commit, prune spike scratch: `.venv/`, `.venv-bug/`, `__pycache__/`, `DynamicPlugin/`, `rc_*.sh`, top-level `importtime_*.log`, `/tmp/drop*.txt`, `/tmp/blesh.txt`, `/tmp/pristine_tool_bash.txt`. Keep: `app/`, `appwk/`, `bin/tool`, `bin/toolw`, `tool`, `toolw`, `evidence/`, `workaround-completion-init.patch.md`, `report.md`.
8. **DECISIONS-row caveats (exact wording for controller):** append to the row: "caveats: (a) fish prefix-insert step inconclusive in transcript — fish gray autosuggestion renders inside the prompt line, not re-tested; (b) empty dynamic candidate list (`tool show x` + Tab) falls back to filename completion via typer's `complete -o default` — file names offered as flag values."

## Fix report (post-review, 2026-09-20)

All must-fix items addressed with **logged re-runs** (not downgrades):
1. Dual-version repro re-run and logged: `evidence/bug-repro-0.27.0.log`, `evidence/bug-repro-0.27.2.log` — both show `Shell bash not supported.` exit=1 at root/flag/arg positions.
2. Workaround server outputs re-run and logged: `evidence/workaround-server.log` — bash `items`/`alpha` (both typer versions), zsh `_arguments` line, fish `items`/`show` help lines, all exit=0.
3. Root-cause probe logged: `evidence/registry-probe.log` — `after get_command(add_completion=False): {}`; `after explicit completion_init(): ['bash','fish','powershell','pwsh','zsh']`.
4. ble.sh citation fixed: report now cites `evidence/blesh_screens3.txt` as canonical; garbled F/G in `evidence/blesh_raw_transcript.txt` explicitly disclosed as driver artifacts (see honesty note in §2.5).
5. Tab latency logged: `evidence/tab-latency.log` — 10 runs, best 0.05 s / median 0.06 s / worst 0.06 s; importtime head 37.6 ms cumulative.
6. Scratch-prune list stated in Concerns #7.
7. Exact DECISIONS caveat wording supplied in Concerns #8.
