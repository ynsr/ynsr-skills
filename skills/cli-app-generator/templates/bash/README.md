# sample — bash tier skeleton (bashly)

Single-concern CLI: `bashly.yml` + handlers → one standalone script (bash ≥4.2 + jq alone, verified under `env -i`). Replace the sample surface with your commands.

    ./install.sh                     # generate + symlink ~/.local/bin/sample + file-drop completions
    ./check.sh                       # shellcheck + bats + verify-cli (regenerates first)
    sample show data.json            # JSON object → NAME/VALUE table
    sample show data.json -o csv     # --output json|csv|tsv (--json alias)
    sample delete f.txt --dry-run    # plan → stdout; add --yes (refuses = exit 2; never prompts)
    sample completions               # static bash completion (completely; ble.sh-safe)

Contract: stdout data-only · `{"error":{code,message,hint}}` on stderr (TTY: one-liner + hint) · exit codes in `--help` · never blocks · NO_COLOR + `--no-color` · `--version`/`-v`, `-q`.

- Generated-tool runtime deps: bash ≥4.2, jq (`column` optional — falls back to tabs).
- New commands: `src/bashly.yml` + `src/<name>_command.sh` + whitelist in `src/initialize.sh`.
- Escalation: >~300 LOC or real data structures → Python tier (spec §10.2).
