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
eval "$(tool completions show bash 2>/dev/null)"   # ~/.bashrc
eval "$(tool completions show zsh 2>/dev/null)"    # ~/.zshrc
tool completions show fish 2>/dev/null | source    # fish config (fish has no $())
```

**Typer ≥ 0.27 server pitfall** (shipped as a real regression in four tools, 2026-09): with `add_completion=False`, typer registers its completion classes only inside `completion_init()`, which the env-var server never calls — every Tab then dies with `Shell bash not supported.`, and ble.sh/zsh-autocomplete fire the server per keystroke, spamming the shell. Both templates ship `ensure_completion_classes()`; call it once in `main()` before `app()`. It registers via typer's own `typer._click` registry (a plain-click registry does not feed typer's server) and falls back to plain click on older typers. The `2>/dev/null` in the sourced line is mandatory for the same reason: a stale script/binary pair must degrade to "no candidates", never print into the shell (manual `completions show` still shows errors). Tests MUST include a subprocess runtime-protocol test (env vars set, `sys.argv = [prog, '']` before `main()` → candidates, rc 0, empty stderr); the complete-var name derives from `sys.argv[0]`'s basename, so an argv0 ≠ prog silently disables the server.

**`completions install [shell] [--rcfile] [--yes]`** idempotently writes a marker block (`# >>> {prog} completions >>>` … `# <<<`) into the rc file:

- The rc edit is destructive per the dry-run rule → confirm on a TTY; `--yes` bypasses for non-interactive/agent use.
- No shell arg → detect from `$SHELL` (`detect_shell()`; None → usage error naming the supported shells).
- Per-shell rc defaults: `~/.bashrc`, `~/.zshrc`, `~/.config/fish/config.fish`; `--rcfile` overrides (tests use it).
- Atomic write (tmp + rename), `.bak` backup before overwrite, and a stale block from an older version is **replaced**, not duplicated.
- After a change print `installed <prog> completion for <shell> in <rc>` plus `restart your shell or run: source <rc>` to stderr; a no-op prints `already installed in <rc>`.
- The zsh block also ensures `compinit`.

**Ordering is never hand-coded.** Click resolves the cursor position: subcommand names and `-`/`--` flags complete automatically. The only custom code is one `autocompletion=` callback per *dynamic value* (profile/resource names, like `git branch` cycling branches): filter on the `incomplete` prefix, read local state only (never network), never raise — return `[]` on any failure so Tab never breaks. Template helpers: `completions.complete_profile_names(list_profiles)` / `_complete_profiles`.

**README tradeoff** (document in generated READMEs): the eval line spawns Python on every new shell (~200–400ms for Typer apps) but never goes stale when commands change — the right default for this tier.

**Tests** (project tier, `tests/unit/test_completions.py`): `show` output non-empty per shell + unknown shell exits 2; install preserves existing rc content, creates `.bak`, second run is a byte-identical no-op; Click-level check that subcommands/flags resolve; value callback filters prefixes and returns `[]` on missing config; subprocess runtime-protocol regression test (see server pitfall above).

## Example: `complete_names()` callback factory ([harness](https://github.com/ynsr/harness))

[Harness](https://github.com/ynsr/harness) implements the paragraph above as one factory plus thin *source functions*. The factory owns the `[]`-on-failure rule, so sources stay plain — local state reads or `check=True` subprocess calls with a short `timeout=`.
```python
def complete_names(list_fn: Callable[[], object]) -> Callable:
    """Build an ``autocompletion=`` callback over locally stored names.

    ``list_fn`` returns an iterable of names (read LOCAL state only, never
    the network); wrapped so ANY failure (missing dir, bad JSON) yields []
    instead of breaking Tab.
    """


    def _complete(ctx, incomplete: str) -> list[str]:
        try:
            raw = list_fn()
            names = list(raw.keys()) if isinstance(raw, dict) else list(raw)
        except Exception:
            return []
        return sorted(n for n in names if n.startswith(incomplete))
    return _complete


def _cwd_git_branches() -> list[str]:
    """Local branch names in the current working directory (offline, fast).

    Raises on failure (not a repo, git missing) — ``complete_names`` turns
    that into [] so Tab never breaks the shell.
    """
    out = subprocess.run(["git", "branch", "--format=%(refname:short)"],
                         capture_output=True, text=True, timeout=2, check=True).stdout
    return out.split()
```

`timeout=` on every subprocess source is mandatory: the env-var server fires per keystroke under ble.sh/zsh-autocomplete, so a hanging source freezes the shell. Sources may raise — a source outside a repo raises `CalledProcessError`, which the factory converts to `[]`.

Wiring — one line per dynamic value, options just reference the callback:

```python
_complete_repos = _completions.complete_names(repos.repo_names)          # registered repo names (local state)
_complete_branches = _completions.complete_names(_completions._cwd_git_branches)

base: Optional[str] = typer.Option(None, "--base", autocompletion=_complete_branches,
                                    help="Base branch (default: repo default).")
```

Test the callback directly (no Click machinery): prefix filter and sort order inside a git repo, `[]` outside one (`tests/test_cli.py::test_base_completion_lists_cwd_git_branches`), plus a live `_HARNESS_COMPLETE=complete_bash` protocol check.

## Template verification

- `templates/python-project/`: `uv sync && .venv/bin/python -m pytest` — full suite, offline (httpx.MockTransport).
- `templates/python-single-file/`: `uv run --with requests,typer,click,rich <tool> --help`, then one real invocation, after any edit.
