# Install, cli-hub, and completion internals

Long-form reference for `cli-app-generator`. SKILL.md holds the contracts; this file holds the mechanics needed when adapting the templates (`templates/python-project/`, `templates/python-single-file/`) or debugging an installed tool.

## Install receipt + stale-install guard (Python project tier)

`uv tool install` / `pipx install` snapshot the source into an isolated venv — workspace edits never reach the installed binary until reinstall. Three parts guard against that:

1. **`install.sh`** writes `~/.local/share/<tool>/install-receipt.json`:
   - `source_hash` — SHA-256 over all source `*.py` files (relative paths + bytes), first 12 hex chars
   - `installed_at`, `source_dir`

   then runs `<tool> doctor` as a self-check. One canonical installer (uv preferred, pipx fallback) — mixing both fights over the same `~/.local/bin` symlink; the script's backend detection owns that choice.
2. **`<tool> doctor`** compares the receipt hash against the live tree: exit 0 in sync; exit 1 with the fix command (`./install.sh` or `pipx install --force .`) when stale or missing. The share-dir path must honor `$HOME` so tests can redirect it.
3. **Dev-run warning**: every invocation checks whether `__file__` resolves to a working tree (not `site-packages`/`.local/share`) whose hash differs from the receipt — warn on stderr with the fix. Never warn from the installed copy itself.

`uninstall.sh` reverses everything `install.sh` created: package, completions, cron/systemd units, tool-created config, and the install receipt.

## cli-hub registration

Every generated CLI self-registers with [cli-hub](https://github.com/ynsr/cli-agents-config/tree/main/tools/cli-hub) (`~/.config/cli-hub/config.yml`, re-read on every hub call) so all skill-generated tools stay discoverable from one entry point.

`install.sh` ends with a best-effort registration (hub absent → never fail the install):

```bash
if command -v cli-hub &>/dev/null; then
  REPO="$(git -C "$DIR" remote get-url origin 2>/dev/null || true)"
  cli-hub register <tool-name> \
    --version "<version>" \
    --description "<one-line description>" \
    --group "<group>" \
    --source-path "$DIR" \
    ${REPO:+--repo "$REPO"} \
    --config-path "${HOME}/.config/<tool-name>" \
    --uninstall "$DIR/uninstall.sh" \
    --reinstall "$DIR/install.sh" \
    --yes || true
fi
```

`uninstall.sh` ends with `cli-hub unregister <tool-name> --yes || true` (same guard).

**Field sources**: `--version` from `pyproject.toml` / `--version`; `--description` from the README one-liner; `--group` a domain noun (`git`, `media`, `db`, `net`, `meta`, `misc`); `--source-path` the project dir (single-file tier: the installed copy in `~/.local/bin/`); `--repo` the git origin URL (empty when none); `--config-path` `~/.config/<tool>`; `--uninstall`/`--reinstall` the project's own scripts.

**Register the scripts, never inline backend commands.** Hub reinstall/uninstall re-run `install.sh`/`uninstall.sh`, which detect the backend themselves (uv or pipx — never hardcode either) and rewrite the install receipt. Inline `pipx install --force`-style hooks bypass the receipt write and leave `doctor` reporting stale forever. When the user declines install/uninstall scripts, run the equivalent `cli-hub register` inline once after copying the script into `~/.local/bin/`.

**Hub self-monitoring** (no generation-side cleanup needed beyond `unregister`):

- `cli-hub prune` lists entries whose binary is missing from `PATH` and removes them only after user confirmation.
- `cli-hub doctor` runs `<tool> doctor` for every entry with an install receipt (JSON status preferred, bare-exit fallback) — keep the `status: ok|stale|missing` output contract so installs self-monitor.

## Shell completion internals

Both Python templates ship ONE completion system; construct the app with `add_completion=False` so Typer's competing `--install-completion`/`--show-completion` flags don't appear.

**`completions show <bash|zsh|fish>`** prints the init script for an eval line:

```bash
eval "$(tool completions show bash)"   # ~/.bashrc
eval "$(tool completions show zsh)"    # ~/.zshrc
tool completions show fish | source    # fish config (fish has no $())
```

**`completions install [shell] [--rcfile] [--yes]`** idempotently writes a marker block (`# >>> {prog} completions >>>` … `# <<<`) into the rc file:

- The rc edit is destructive per the dry-run rule → confirm on a TTY; `--yes` bypasses for non-interactive/agent use.
- No shell arg → detect from `$SHELL` (`detect_shell()`; None → usage error naming the supported shells).
- Per-shell rc defaults: `~/.bashrc`, `~/.zshrc`, `~/.config/fish/config.fish`; `--rcfile` overrides (tests use it).
- Atomic write (tmp + rename), `.bak` backup before overwrite, and a stale block from an older version is **replaced**, not duplicated.
- After a change print `installed <prog> completion for <shell> in <rc>` plus `restart your shell or run: source <rc>` to stderr; a no-op prints `already installed in <rc>`.
- The zsh block also ensures `compinit`.

**Ordering is never hand-coded.** Click resolves the cursor position: subcommand names and `-`/`--` flags complete automatically. The only custom code is one `autocompletion=` callback per *dynamic value* (profile/resource names, like `git branch` cycling branches): filter on the `incomplete` prefix, read local state only (never network), never raise — return `[]` on any failure so Tab never breaks. Template helpers: `completions.complete_profile_names(list_profiles)` / `_complete_profiles`.

**README tradeoff** (document in generated READMEs): the eval line spawns Python on every new shell (~200–400ms for Typer apps) but never goes stale when commands change — the right default for this tier.

**Tests** (project tier, `tests/unit/test_completions.py`): `show` output non-empty per shell + unknown shell exits 2; install preserves existing rc content, creates `.bak`, second run is a byte-identical no-op; Click-level check that subcommands/flags resolve; value callback filters prefixes and returns `[]` on missing config.

## Template verification

- `templates/python-project/`: `uv sync && .venv/bin/python -m pytest` — full suite, offline (httpx.MockTransport).
- `templates/python-single-file/`: `uv run --with requests,typer,click,rich <tool> --help`, then one real invocation, after any edit.
