# SPIKE D — Bash generator: bashly vs argc

Date: 2026-09-19/20 · Worktree: `/home/bs/projects/personal/ynsr-skills/.worktrees/cli-app-generator-v2`

## 1. What ran (exact commands + install wall time)

### bashly (ruby gem path)
```bash
ruby --version                      # ruby 3.3.8 (2025-04-09) — preinstalled, NO version friction
time gem install --user-install bashly   # real 0m31.237s, 24 gems incl. bashly-1.4.0 + completely-0.8.0
export PATH=~/.local/share/gem/ruby/3.3.0/bin:$PATH   # gem bin dir NOT on PATH by default
bashly --version                    # 1.4.0 ; completely --version → 0.8.0
```
Friction noted: user-install drops binaries in `~/.local/share/gem/ruby/3.3.0/bin/` (version-suffixed path). Install = one command, ~31 s.

### argc (single binary)
```bash
curl -sL https://api.github.com/repos/sigoden/argc/releases/latest | jq -r '.tag_name, .published_at'
# → v1.24.0, 2026-05-20  (≈4 months old → within 12-month window ✓)
time (curl -sL https://github.com/sigoden/argc/releases/download/v1.24.0/argc-v1.24.0-x86_64-unknown-linux-musl.tar.gz -o /tmp/argc.tgz && tar -xzf /tmp/argc.tgz -C ~/.local/bin argc && chmod +x ~/.local/bin/argc)
# real 0m5.793s  (tarball root contains a single 1.2M static musl `argc` binary)
argc --argc-version                 # argc 1.24.0
```

### Toy tool (same surface both sides)
`show FILE` (reads JSON, prints TSV table), `delete FILE [--dry-run|--yes]`, global `--version`/`--help`, completions.
- bashly: `bashly.yml` (34 lines) + `bashly generate` (0.3 s) + two handler files; completions via `bashly add completions` + `./toytool completions`.
- argc: single `toytool` file (33 lines) with `# @cmd/# @arg/# @flag/# @meta` tags + trailing `eval "$(argc --argc-eval "$0" "$@")"`; completions via `argc --argc-completions {bash,zsh,fish} toytool-argc`.

## 2. Observed evidence

### `--help` quality (both quoted)
bashly `./toytool --help` (rich, per-command pages add Options/Arguments/Allowed/Default/Examples):
```
toytool - Toy tool for spike D

Usage:
  toytool COMMAND
  toytool [COMMAND] --help | -h
  toytool --version | -v

Commands:
  show     Read a JSON file and print a table
  delete   Delete a file
...
```
`./toytool show --help` includes `Allowed: table, json, csv, tsv` and `Default: table` plus `Examples: toytool show data.json`.

argc `./toytool --help` (clap-style, terser):
```
USAGE: toytool <COMMAND>

COMMANDS:
  show    Read a JSON file and print a table
  delete  Delete a file
```
`./toytool-argc delete --help`:
```
USAGE: toytool-argc delete [OPTIONS] <FILE>
ARGS:
  <FILE>  File to delete
OPTIONS:
      --output <FORMAT>  Output format [possible values: table, json, csv, tsv]
      --dry-run          Print what would be deleted
  -y, --yes              Skip confirmation
  -h, --help             Print help
```
bashly help is substantially richer (examples, defaults, allowed-lists, aliases shown); argc is leaner but includes `[possible values]`.

### (a) Runtime deps of generated output — DECISIVE
- bashly `toytool` (746 lines): standalone bash file, header check `bash version 4.2 or higher is required`; runs with `env -i PATH=/usr/bin:/bin` — **zero deps beyond bash** (jq used only by my handler). `--compact` does not exist in 1.4.0 — output is already single-file standalone.
- argc `toytool` (33 lines): line 33 `eval "$(argc --argc-eval "$0" "$@")"`. With argc stripped from PATH:
  `./argc/toytool: line 33: argc: command not found` — **the generated CLI hard-requires the 1.2M argc binary at every invocation.** Verified: same script runs once argc is on PATH.

### (b) Completion quality per shell
- bashly (via `completely`, static): `toytool_completions.bash` (161–172 lines), pure bash, no external calls. Source-test (COMP_WORDS simulated):
  `toytool sh<TAB>` → `show`; `toytool delete --dr<TAB>` → `--dry-run` (via `--outpuy` rename test also confirmed flag path). **bash-only** — completely emits no zsh/fish script.
- argc (dynamic): `--argc-completions bash|zsh|fish` each ~47–51 lines; completer forks `argc --argc-compgen` per Tab. Observed candidates:
  `toytool-argc sh<TAB>` → `show`; `toytool-argc delete --dr<TAB>` → `--dry-run`; `delete --output <TAB>` → `table json csv tsv` (choice values, prefix-filtered `t` → `table tsv`); with `(Print help)`-style descriptions on flags. zsh script passes `zsh -n`; fish script not runtime-exercised (no fish -n mode). Completion discovery quirk: compgen resolves the first word via **PATH** (or `ARGC_SCRIPT` env), not cwd — completions only work for an installed, on-PATH command name.

### (c) Silence of failures (agent-writability killer)
- bashly YAML: unknown **keys** caught loudly — `root.commands[0].args[0] contains invalid options: require` (exit 1). But unknown/misspelled **values** silently rename: `long: --outpuy` → exit 0, flag renamed; `name: shwo` → exit 0, generated `shwo_command.sh` stub **silently created**.
- argc tags: unknown tag caught loudly — `Error: @flg(line 19) is unknown tag` (exit 1). But malformed tag payloads pass silently: `# @option --output[FORMAT] <table|json|csv|tsv>` parsed without error and simply produced wrong help/choice-completion until corrected to `# @option --output[table|json|csv|tsv] <FORMAT>`.

### (d/e) Authoring surface
- bashly: 34-line YAML + 3+9+1 handler/shim lines = **47 lines across 4 files**; two vocabularies (YAML keys, `${args[file]}` accessor in handlers).
- argc: **33 lines, 1 file**, single vocabulary (`$argc_file`); tags + handlers colocated.

Exit codes exercised both: success 0; missing required arg → 1 (both); bad choice value → 1 (both, "must be one of" / clap error); no `--yes` → 3 (our handler, both); unknown command → 1 both.

## 3. Decision row

| D — Bash generator | **bashly** | Self-contained output: generated script runs on bash ≥4.2 alone — the skill's deliverable must not force a 1.2M binary on end users (argc's output dies with `argc: command not found` without it). Static completion script = no per-Tab fork, plain-bash surface (ble.sh-safe class). Richer declarative YAML (examples, default, allowed-list validation) maps directly onto the spec §4.1 contract, and unknown keys fail loudly at generation. | Rejected argc: generated CLI hard-depends on the argc binary at every invocation and completions fork it per keystroke; completion only completes PATH-installed names. (Within bashly: nothing rejected — `--compact` flag simply no longer exists; default output is already single-file.) | bashly/src/bashly.yml; bashly/toytool; bashly/toytool_completions.bash; argc/toytool; argc/comp.{bash,zsh,fish}; report.md |

## 4. Concerns
1. **bashly silently renames on value typos** (`shwo`, `--outpuy` → exit 0, new stub files). Generator must add a generation-time guard: snapshot `--help`/command list before+after, or assert spec command/flag names against a whitelist.
2. bashly completions are **bash-only** (completely). Spec §4.1 requires bash; zsh/fish would need a separate path if ever demanded — argc is stronger there.
3. bashly embeds no `-q` global; contract flags `-v/-q` need explicit YAML entries (`-v` exists as version alias).
4. gem bin PATH (`~/.local/share/gem/ruby/3.3.0/bin`) must be exported by the generator's install recipe; version-suffixed dir varies with ruby version.
5. argc quirk recorded for the record: `argc <file>` runner form is name-sensitive (`Argcfile.sh`); irrelevant since bashly chosen, but documented above.
