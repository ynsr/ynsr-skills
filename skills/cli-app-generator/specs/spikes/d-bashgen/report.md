# SPIKE D — Bash generator: bashly vs argc

Date: 2026-09-20 · Worktree: `/home/bs/projects/personal/ynsr-skills/.worktrees/cli-app-generator-v2`

## 1. What ran (exact commands + install wall times)

### Install — bashly (user-local gem, ~31 s first run; ~24 s on logged re-run)
```bash
ruby --version                            # ruby 3.3.8 (2025-04-09) — preinstalled, no version friction
time gem install --user-install bashly    # ~31 s first run (24 gems incl. bashly-1.4.0, completely-0.8.0)
# logged re-run: /usr/bin/time -f "wall=%es" gem install --user-install --force bashly → wall=24.26s
export PATH=~/.local/share/gem/ruby/3.3.0/bin:$PATH   # gem bin dir NOT on PATH by default
bashly --version                          # 1.4.0 ; completely --version → 0.8.0
```
Friction: user-install drops binaries in `~/.local/share/gem/ruby/3.3.0/bin/` (ruby-version-suffixed path; recipe must export it). Full transcript: `evidence/install.log`.

### Install — argc (single binary; first run ~6 s, logged re-run ~11 s incl. network)
```bash
curl -sL https://api.github.com/repos/sigoden/argc/releases/latest | jq -r '.tag_name, .published_at'
# v1.24.0, 2026-05-20  → ~4 months old, within 12-month window ✓
curl -sL https://github.com/sigoden/argc/releases/download/v1.24.0/argc-v1.24.0-x86_64-unknown-linux-musl.tar.gz -o /tmp/argc.tgz \
  && tar -xzf /tmp/argc.tgz -C ~/.local/bin argc && chmod +x ~/.local/bin/argc
# /usr/bin/time log: wall=11.28s — tarball root is a single 1.2M static musl binary
argc --argc-version                       # argc 1.24.0
```

### Toy tool (identical surface both sides)
`show FILE` (reads JSON, prints TSV table via jq), `delete FILE [--dry-run|--yes]`, global `--version`, completions.
- bashly: `bashly/src/bashly.yml` (34 lines) + `bashly generate` (~0.3 s) + two handler files; completions via `bashly add completions` + `./toytool completions > toytool_completions.bash` (172 lines).
- argc: single `argc/toytool` (33 lines; copy `argc/toytool-argc` used for argv[0]-name transcripts) with `# @cmd / # @arg file! / # @flag --dry-run / # @meta version` tags + trailing `eval "$(argc --argc-eval "$0" "$@")"`; completions via `argc --argc-completions {bash,zsh,fish} toytool-argc` (47/51/49 lines).

## 2. Observed evidence (transcripts in `evidence/`)

### Runtime deps of generated output — DECISIVE (`evidence/runtime-deps.log`)
```
$ env -i PATH=/usr/bin:/bin HOME=$HOME ./bashly/toytool show /tmp/data.json
NAME	VALUE
name	alice
role	admin
active	true
exit=0

$ env -i PATH=/usr/bin:/bin HOME=$HOME ./argc/toytool-argc show /tmp/data.json
./argc/toytool-argc: line 33: argc: command not found
exit=0
```
bashly `toytool` (757 lines, recounted from disk): standalone single file with own guard `bash version 4.2 or higher is required`; zero deps beyond bash ≥4.2 (jq only in my handler code). Note: `--compact` does not exist in bashly 1.4.0 — default output is already single-file standalone. argc `toytool` (33 lines) ends with `eval "$(argc --argc-eval "$0" "$@")"` and **hard-requires the 1.2M argc binary at every invocation**.

### --help quality (`evidence/bashly-help.log`, `evidence/argc-help.log`)
bashly `./toytool --help`:
```
toytool - Toy tool for spike D

Usage:
  toytool COMMAND
  toytool [COMMAND] --help | -h
  toytool --version | -v

Commands:
  show          Read a JSON file and print a table
  delete        Delete a file
  completions   Generate bash completion script
```
`./toytool show --help` adds `Allowed: table, json, csv, tsv`, `Default: table`, `Examples: toytool show data.json`.

argc (from `evidence/argc-help.log`, run against the installed-name copy `toytool-argc`):
```
$ ./toytool-argc --help
USAGE: toytool-argc <COMMAND>

COMMANDS:
  show    Read a JSON file and print a table
  delete  Delete a file

$ ./toytool-argc delete --help
Delete a file

USAGE: toytool-argc delete [OPTIONS] <FILE>

ARGS:
  <FILE>  File to delete

OPTIONS:
      --output <FORMAT>  Output format [possible values: table, json, csv, tsv]
      --dry-run          Print what would be deleted
  -y, --yes              Skip confirmation
  -h, --help             Print help

$ ./toytool-argc --version
toytool-argc 0.1.0

$ ./toytool-argc show /tmp/data.json
NAME	VALUE
name	alice
role	admin
active	true
exit=0

$ ./toytool-argc delete /tmp/data.json --dry-run
Would delete: /tmp/data.json
exit=0

$ ./toytool-argc show   (missing required arg)
error: the following required arguments were not provided:
  <FILE>
exit=1
```
bashly help is substantially richer (examples, defaults, allowed lists); argc leaner but shows `[possible values]`.

### Completion quality per shell (`evidence/completions.log`)
- bashly (completely, static, **bash-only**): `toytool_completions.bash` 172 lines, pure bash, no external calls. Observed:
  ```
  == bashly (static, bash-only; completely-generated, no external calls) ==
  $ source bashly/toytool_completions.bash; COMP_WORDS=(toytool sh) ...
  → [show]
  $ ... COMP_WORDS=(toytool delete --dr) ...
  → [--dry-run]
  ```
  No zsh/fish emitted at all. The static, no-per-Tab-fork design is suggestive for ble.sh compatibility, but interactive ble.sh verification was NOT performed in this spike — that happens in spike B / task 13.
- argc (dynamic, 3 shells): `comp.bash` 47 / `comp.zsh` 51 / `comp.fish` 49 lines; completer forks `argc --argc-compgen` per Tab. Observed:
  ```
  $ source argc/comp.bash; COMP_WORDS=(toytool-argc sh) ...
  → [show ]
  $ argc --argc-compgen bash "" toytool-argc delete --dr   (direct compgen)
  --dry-run 
  $ argc --argc-compgen bash "" toytool-argc delete --output ""   (choice values)
  table 
  json 
  csv 
  tsv 
  ```
  zsh script passes `zsh -n`; fish not runtime-exercised. Quirk: compgen resolves the first word via PATH (or `ARGC_SCRIPT` env), not cwd — completions only work for a PATH-installed command name (verified via strace PATH walks).

### Agent-writability failure modes (`evidence/bashly-invalid-key.log`, `evidence/bashly-typo.log`, `evidence/argc-typo.log`)
- bashly invalid **key** — caught loudly:
  ```
  (a) invalid KEY: sed required:→require:
   Bashly::ConfigurationError 
  root.commands[0].args[0] contains invalid options: require
  exit=1
  ```
- bashly **value typos** — silent rename, exit 0:
  ```
  (c) silent rename, value typo in command name: sed name: show→name: shwo
  exit=0
  shwo_command.sh        # stub silently created
  29:  printf "  %s   Read a JSON file and print a table\n" "shwo       "
  ...
  (c2) silent rename, flag long typo: sed long: --output→long: --outpuy
  exit=0
  66:    printf "  %s\n" "--outpuy FORMAT"
  553:      --outpuy)
  ```
- argc unknown **tag** — caught loudly:
  ```
  (b) unknown tag: sed @flag→@flg on delete --dry-run
  Error: @flg(line 19) is unknown tag
  exit=1
  ```
- argc **malformed payload** — parsed without error, wrong semantics:
  ```
  (d) malformed payload: @option --output[FORMAT] <table|json|csv|tsv> (choices in wrong slot)
  18:# @option --output[FORMAT] <table|json|csv|tsv>   Output format
        --output <TABLE|JSON|CSV|TSV>  Output format [possible values: FORMAT]
  exit=0
  ```
  (the choices/placeholder slots were swapped: help claims `possible values: FORMAT`).

### LOC of authoring surface (recounted from disk)
- bashly: 34 (YAML) + 3 (show handler) + 9 (delete handler) + 1 (completions shim) = **47 lines across 4 files**; two vocabularies (YAML keys, `${args[file]}` accessor). Generated: `toytool` 757 lines + `toytool_completions.bash` 172 lines.
- argc: **33 lines, 1 file**, single vocabulary (`$argc_file`); tags colocated with handlers. Generated completions 47/51/49 lines.

### Exit codes exercised (both)
success 0; missing required arg → 1 (both); bad choice value → 1 (both, `--output must be one of: table, json, csv, tsv` / clap error); no `--yes` → 3 (our handler, both); unknown command → 1 (both).

## 3. DECISIONS row

| D — bash generator | bashly | Generated script is self-contained: runs on bash ≥4.2 alone, verified under `env -i PATH=/usr/bin:/bin` (evidence/runtime-deps.log) — the skill's deliverable must not force a 1.2M argc binary on end users (argc's output dies with `argc: command not found` without it). Static single-file completion script = no per-Tab fork, plain-bash surface — suggestive for ble.sh compat; interactive verification happens in spike B / task 13. Richer declarative YAML (examples, default, allowed-list validation) maps directly onto the spec §4.1 contract; unknown keys fail loudly at generation. | argc rejected: generated CLI hard-depends on the argc binary every invocation and completions fork it per keystroke; completion only completes PATH-installed names. (bashly `--compact` doesn't exist in 1.4.0 — default already single-file, nothing rejected.) | bashly/src/bashly.yml, bashly/toytool, bashly/toytool_completions.bash, argc/toytool, argc/toytool-argc, argc/comp.{bash,zsh,fish}, evidence/*.log, this report |

## 4. Concerns
1. **bashly silently renames on value typos** (`shwo`, `--outpuy` → exit 0, new stub files). Generator must add a generation-time guard: assert spec command/flag names against a whitelist (or diff `--help` before/after).
2. bashly completions are **bash-only** (completely). Spec §4.1 requires bash; zsh/fish would need a separate path if ever demanded — argc is stronger there. Static/no-fork design is suggestive for ble.sh compat but not verified interactively here.
3. bashly has no `-q` global by default; contract `-v/-q` flags need explicit YAML entries (`-v` exists as version alias).
4. gem bin PATH (`~/.local/share/gem/ruby/3.3.0/bin`) must be exported by the install recipe; version-suffixed dir varies with ruby version.
5. argc's argv[0]-derived USAGE means scratch-name copies change help text (`toytool` vs `toytool-argc`); harmless for the decision, noted for spec examples.

## Fix report (post-review, 2026-09-20)
- (1) argc help quotes re-run against a real `toytool-argc` copy (`argc/toytool-argc`, also installed at `~/.local/bin/toytool-argc`); transcript `evidence/argc-help.log`; quotes now match the binary name.
- (2) All four previously unbacked quotes re-run and captured: `evidence/bashly-invalid-key.log` (a), `evidence/argc-typo.log` (b: `Error: @flg(line 19) is unknown tag`, exit 1; d: swapped payload → `--output <TABLE|JSON|CSV|TSV> ... [possible values: FORMAT]`, exit 0), `evidence/bashly-typo.log` (c: `shwo_command.sh` stub + `--outpuy` flag, exit 0). Quoted text now matches logs.
- (3) ble.sh claim reworded: static/no-fork is "suggestive for ble.sh compat"; no interactive ble.sh run happened here (spike B / task 13 will verify).
- (4) Generated line count recounted from disk: 757 (was 746).
- (5) Install times hedged to ~31 s (first run) / ~24 s (logged re-run) and ~6 s (first) / ~11 s (logged re-run incl. network); log at `evidence/install.log`.
