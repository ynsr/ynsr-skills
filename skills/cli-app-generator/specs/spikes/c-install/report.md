# SPIKE C — Install without stale copies (editable tool install + symlink single-file) + slim doctor

Status: **DONE**

## 1. What I ran (exact commands)

### 1a. Editable tool install (uv 0.11.26)
Scratch package: `demo-pkg/` (pyproject with `[project.scripts] spikec-demo = "spikec_demo.cli:main"`, hatchling backend mirroring `templates/python-project/pyproject.toml`).

```bash
uv tool install --help | grep -iA2 editable        # flag exists
time uv tool install --editable ./demo-pkg         # 3.7s first time (cold build), 0.19s re-run (warm)
spikec-demo                                        # installed binary, pre-edit
# — edit one source line in demo-pkg/src/spikec_demo/cli.py (no reinstall) —
spikec-demo                                        # installed binary, post-edit
uv tool upgrade spikec-demo                        # upgrade path
uv tool install --editable ./demo-pkg              # idempotency (2nd install)
uv tool uninstall spikec-demo                      # uninstall path
cat ~/.local/share/uv/tools/spikec-demo/lib/python3.13/site-packages/_editable_impl_spikec_demo.pth
```

### 1b. Single-file PEP 723 + symlink
Scratch script: `single/tool.py` — shebang `#!/usr/bin/env -S uv run --script`, inline metadata `dependencies = ["rich>=13.7"]`.

```bash
chmod +x single/tool.py
mkdir -p bin && ln -sf "$PWD/single/tool.py" bin/spikec-single
export PATH=".../c-install/bin:$PATH"
cd /tmp && spikec-single            # from another cwd
cd ~    && spikec-single
"$BIN/spikec-single" 2>/dev/null    # stdout purity check
time "$BIN/spikec-single"           # warm start latency
mv single/tool.py /tmp/tool.py.moved && spikec-single; echo "exit=$?"   # dangling-symlink edge
```

### 1c. Slim doctor draft
`doctor_demo.py` (53 physical lines / ~40 code lines; the ~25-line figure in the spec refers to the template's narrower dep list). Ran: ok / missing / bad-config / `--ping` / `--json` modes; exit codes checked.

### 1d. cli-hub integration smoke
Hub source read: `~/.local/share/uv/tools/cli-hub/lib/python3.13/site-packages/cli_hub/{cli.py,registry.py,probe.py}` (v0.3.1, untouched). Register block draft: `register-block.sh`, executed against a **throwaway registry** (`CLI_HUB_CONFIG=/tmp/spikec-hub.yml`) — real `~/.config/cli-hub/config.yml` never touched. Test tools `spikec-fail`/`spikec-bare` exercised hub doctor propagation; all test artifacts (temp registry, fake bins, `~/.local/share/spikec-*` dirs) deleted afterward; `spikec-demo` uninstalled.

## 2. Observed evidence (key output lines)

### 1a. Editable — edit propagates through installed binary, NO reinstall
```
$ uv tool install --editable ./demo-pkg
   Built spikec-demo @ file:///…/c-install/demo-pkg
 + spikec-demo==0.1.0 (from file:///…/c-install/demo-pkg)
Installed 1 executable: spikec-demo          # real 3.7s
$ spikec-demo
spikec-demo 0.1.0 (pre-edit)
$ spikec-demo                                # after editing cli.py line 3 only
spikec-demo 0.1.0 (post-edit: EDIT PROPAGATED)
$ uv tool upgrade spikec-demo
Nothing to upgrade
$ uv tool install --editable ./demo-pkg      # 2nd run: idempotent, 0.19s
 ~ spikec-demo==0.1.0 (from file:///…/demo-pkg)
Installed 1 executable: spikec-demo
$ uv tool uninstall spikec-demo
Uninstalled 1 executable: spikec-demo        # gone from PATH
```
Mechanism: venv `.pth` points at the source tree —
`_editable_impl_spikec_demo.pth` = `/home/bs/…/c-install/demo-pkg/src`; shim `~/.local/bin/spikec-demo -> ~/.local/share/uv/tools/spikec-demo/bin/spikec-demo`. Note the tool venv used **Python 3.13** (uv's choice for `requires-python >=3.12`); runtime here is 3.14.6 — both satisfy the template floor.
`uv tool install -e, --editable`: "Install the target package in editable mode, such that changes in the package's source directory are reflected without reinstallation" — observed behavior matches the help.

### 1b. Symlink — runs from any cwd
```
$ cd /tmp && spikec-single
Installed 4 packages in 4ms        # stderr, first run only (dep resolution)
{'tool': 'spikec-single', 'version': '0.1.0', 'mode': 'symlink'}
$ cd ~ && spikec-single
{'tool': 'spikec-single', 'version': '0.1.0', 'mode': 'symlink'}
$ spikec-single 2>/dev/null        # stdout data-only
{'tool': 'spikec-single', 'version': '0.1.0', 'mode': 'symlink'}
warm start: real 0m0.088s–0.104s
```
Dangling-symlink edge (one line): moving/renaming the target breaks the symlink — exec fails with `command not found`, **exit 127** (no stale copy is ever left behind, which is the point); uninstall/`ln -sf` owns the link, and hub `prune` catches it (`shutil.which` → None).

### 1c. Slim doctor (`doctor_demo.py`, runnable)
```
$ uv run --with rich --with httpx doctor_demo.py
status: ok
  ok  dep tomllib / dep rich / dep httpx / config: defaults        (exit 0)
$ python3 doctor_demo.py
status: missing
  FAIL dep rich …                                                  (exit 1)
$ doctor_demo.py --config bad.toml    → status: missing, FAIL config: Expected '=' after a key …
$ doctor_demo.py --ping               → connectivity FAIL: handshake timed out (offline sandbox; ping is opt-in, off by default)
$ doctor_demo.py --json
{"status": "ok", "message": ""}       # single-line dict = cli-hub's preferred payload
```
Literal `status: ` prefix is line 1 of stdout in plain mode; `stale` is never emitted (no receipt reading anywhere in the file).

### 1d. cli-hub register block + doctor consumption (temp registry)
```
$ CLI_HUB_CONFIG=/tmp/spikec-hub.yml cli-hub register spikec-demo --version 0.1.0 …
registered 'spikec-demo' in /tmp/spikec-hub.yml
# registry gained: installed_path=/home/bs/.local/bin/spikec-demo (derived),
# repo=https://github.com/ynsr/ynsr-skills.git (derived from git remote), config_path='' (nothing to guess)
$ cli-hub doctor spikec-demo          # no ~/.local/share/spikec-demo yet
│ spikec-demo │ no receipt │         │   (exit 0 — informational, not unhealthy)
$ mkdir ~/.local/share/spikec-demo && cli-hub doctor spikec-demo
│ spikec-demo │ ok │ spikec-demo health │  ← hub ran `spikec-demo doctor --json`, parsed our dict
$ JSON doctor exits 1 with {"status":"missing",…} → hub row: missing │ dep X absent  (exit 1)
$ bare doctor (no --json) exits 1     → hub row: error │ doctor exited 1
```
Hub source facts (cli.py v0.3.1): `_tool_doctor()` (cli.py:466-508) runs `<tool> doctor --json` first, parses the JSON dict from stdout (single-line or last-line scanned) and reads `payload["status"]` verbatim; only if the tool rejects `--json` (rc 2 / usage error) does it retry bare, where rc≠0 can map to `"stale"` (cli.py:498-508). `doctor_cmd` also gates on the receipt dir existing before ever calling the tool doctor (cli.py:567-569). `refresh_entry()` (probe.py:59) already derives `installed_path`, `repo`, `config_path` hub-side — only `version` and `description` still arrive from the installer.

## 3. DECISIONS row

| C — Install without stale copies | **Adopt: `uv tool install --editable .` for python-project; `ln -sf` symlink into `~/.local/bin` for python-single-file. Slim doctor = status-only (`status: ok|missing` + `--json`); receipt, stale-guard, dev-warning deleted.** | Editable install references the source tree via venv `.pth` (verified: source edit propagates through the installed binary with zero reinstall; 3.7s cold / 0.19s warm; `upgrade` is a no-op; uninstall clean) — staleness becomes structurally impossible instead of detected. Symlink start ~0.09s warm, stdout-pure (uv dep noise on stderr), works from any cwd; dangling link fails loudly (exit 127) and hub `prune` flags it. Doctor keeps the frozen `status: ` prefix and adds `--json` so cli-hub reads status verbatim (proven: `missing` propagates, `stale` never emitted by the doctor). | Rejected: receipt-hash staleness scheme — deleted: editable/symlink installs share inode with source, so "installed copy drifted" cannot occur; hashing only ever detected the stale-copy bug class that no longer exists, at ~15 LOC + doctor coupling + hub "no receipt" row noise. Snapshot install (`uv tool install .` / `cp -f`) — rejected: edits land only after a manual re-run, i.e. it IS the stale-copy bug. `pipx install -e` — rejected: uv 0.11.26 native support suffices; pipx absent here. | evidence/editable-propagation.log + evidence/symlink-probe.log; probe outputs in report §2 (1a–1d); register block register-block.sh; doctor draft doctor_demo.py |

## 4. Hub-side proposal note (≤10 lines, to DECISIONS.md owner — hub untouched)

1. `register`'s `--version` help already says "generated installers derive it from pyproject.toml", but v0.3.1 doesn't: hub could read `version`/`description` from `pyproject.toml` at `--source-path` (tomllib, stdlib) when the flag is empty.
2. That shrinks the generated register block from 10 → 6 lines: `register <name> --source-path --uninstall --reinstall --yes` (repo/config/installed-path already derived by `refresh_entry`).
3. Drop the receipt-dir gate in `doctor_cmd` (cli.py:567): with receipts deleted, new tools get a "no receipt" row forever; run `<tool> doctor --json` whenever a binary exists instead.
4. Single-file tools register `--source-path <script>`: `detect_repo()` already handles file paths (uses parent dir) — no change needed.
5. Optional: make the bare-output doctor fallback map rc≠0 to "missing" rather than "stale", retiring the word for real once all tools emit `--json`.

## 5. Install effort (user-local only, no sudo)

Nothing new needed to install: uv 0.11.26 already present (`/home/bs/.local/bin/uv`); editable install of the demo tool 3.7s cold, 0.19s warm; PEP 723 deps resolved from uv cache in 4ms. No downloads, no `gem`/`pip --user` work required for this spike.

## 6. Concerns

- **uv picks its own Python** for tool venvs (3.13 here despite 3.14.6 system runtime). Harmless (≥3.12 floor), but generated install.sh should not assume the interpreter version.
- **`uv tool upgrade` on editable tools says "Nothing to upgrade"** — correct, but if a template ever pins non-editable installs, upgrade would be the stale-fix path; keep editable as the only blessed mode.
- **cli-hub 0.3.1 rows**: without hub-side change 5(3), every receipt-free tool shows an informational "no receipt" row in `cli-hub doctor` (exit stays 0). Acceptable until the hub ships the tweak; the proposal is filed, hub untouched per constraints.
- **Network**: `--ping` cannot be verified against a live pypi.org from this sandbox (TLS handshake times out); the failure path (→ `status: missing`, opt-in only) is what was verified.
- Doctor draft is a standalone sketch (deps hardcoded for the demo, `--dep` demo hook dropped during compaction); the template's doctor hardcodes its own import list and config path.

## Fix report (review round 1)

**What changed**
- Added `evidence/` with two full terminal transcripts (the original probes were verified live but not saved as artifacts; both re-run end-to-end and captured):
  - `evidence/editable-propagation.log` — fresh `uv tool install --editable` → run pre-edit → `sed` one source line (no reinstall) → run post-edit → `cat` the venv `.pth` → uninstall (cleanup restored).
  - `evidence/symlink-probe.log` — `bin/` drop recreated (`mkdir -p bin && ln -sf single/tool.py bin/spikec-single`), runs from `/tmp` and `~`, stdout-purity check, warm timings, dangling-target exit-127 capture; target restored, `bin/spikec-single` left in place as the artifact.
- Report text fixes (no probe changes): §2.1d hub citation widened `cli.py:498-508` → **cli.py:466-508** (JSON-first parse + status read + bare fallback; the 498-508 range remains cited inline for the bare-fallback mapping itself). DECISIONS row evidence cell now cites `evidence/*.log` + "report §2 (1a–1d)" — section-numbering clarification: probe definitions live in §1a–1d, their outputs in §2 (subsections headed `1a.`–`1d.`, i.e. §2.1a–§2.1d). Both DECISIONS.md-unrelated edits were made in this file only.

**Exact commands + key output (full transcripts in the two log files)**

editable-propagation.log:
```
$ uv tool install --editable …/c-install/demo-pkg
Installed 1 executable: spikec-demo
$ spikec-demo
spikec-demo 0.1.0 (pre-edit)
$ sed -i 's/(pre-edit)/(POST-EDIT: EDIT PROPAGATED)/' demo-pkg/src/spikec_demo/cli.py   # NO reinstall
$ spikec-demo
spikec-demo 0.1.0 (POST-EDIT: EDIT PROPAGATED)
$ cat ~/.local/share/uv/tools/spikec-demo/lib/python3.*/site-packages/_editable_impl_spikec_demo.pth
/home/bs/…/c-install/demo-pkg/src                       # venv references the source tree
$ uv tool uninstall spikec-demo
Uninstalled 1 executable: spikec-demo
```
symlink-probe.log:
```
$ ln -sf $D/single/tool.py bin/spikec-single; which spikec-single → …/c-install/bin/spikec-single
$ cd /tmp && spikec-single        → {'tool': 'spikec-single', 'version': '0.1.0', 'mode': 'symlink'}
$ cd ~ && spikec-single           → {'tool': 'spikec-single', 'version': '0.1.0', 'mode': 'symlink'}
$ $D/bin/spikec-single 2>/dev/null → stdout-pure data line
$ time $D/bin/spikec-single       → real 0m0.098s / 0m0.093s (warm)
$ mv $D/single/tool.py /tmp/tool.py.moved && spikec-single
error: command not found: spikec-single
exit=127                          # dangling link fails loudly; target restored, runs again
```

**Status: DONE.** DECISIONS.md untouched; nothing committed; `spikec-demo` uninstalled after the re-run.
