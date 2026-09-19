# Install, uninstall, doctor, and completion

## Install / uninstall (DECISIONS row C)

- python-project: `uv tool install --editable .` — a venv `.pth` references the source tree, so source edits propagate to the installed binary with **zero reinstall** (staleness structurally impossible). Cold 3.7s / warm 0.19s; `upgrade` no-op; uninstall clean.
- python-single-file: PEP 723 shebang + `ln -sf "$PWD/tool.py" ~/.local/bin/<tool>`. Warm start ~0.09s; stdout-pure (uv noise on stderr); runs from any cwd; a dangling link fails loudly (exit 127) and `cli-hub prune` flags it.
- Both tiers: one canonical installer (uv preferred); `install.sh`/`uninstall.sh` idempotent; **uninstall reverses everything install created** (package/symlink, completion files, systemd units, tool config, hub entry).
- Receipt file, stale-guard hashing, and dev-warning are **deleted** (replaced by editable/symlink install).

## Doctor contract (cli-hub consumes this — do not change)

`<tool> doctor` prints `status: ok|missing` (prefix frozen; **`stale` is never emitted**) + `--json` flag. Slim shape: dependency, config, connectivity checks only.

## cli-hub registration

`install.sh` ends with a guarded best-effort register (hub absent → never fail the install):

```bash
if command -v cli-hub &>/dev/null; then
  REPO="$(git -C "$DIR" remote get-url origin 2>/dev/null || true)"
  cli-hub register <tool> --version "<v>" --description "<one-liner>" \
    --group "<git|media|db|net|meta|misc>" --source-path "$DIR" \
    ${REPO:+--repo "$REPO"} --config-path "${HOME}/.config/<tool>" \
    --uninstall "$DIR/uninstall.sh" --reinstall "$DIR/install.sh" --yes || true
fi
```

`uninstall.sh` ends with `cli-hub unregister <tool> --yes || true`. Register the **scripts**, not inline backend commands — hub reinstall/uninstall re-run install.sh/uninstall.sh, which detect the backend themselves.

## Completion (file-drop, DECISIONS row B)

Framework-generated scripts installed by file drop — no rc marker blocks:

| Shell | Path |
|---|---|
| bash | `~/.local/share/bash-completion/completions/<tool>` |
| zsh | `_<tool>` in a dir on `fpath`, e.g. `~/.local/share/zsh/site-functions` |
| fish | `~/.config/fish/completions/<tool>.fish` |

zsh needs `fpath=(<dir> $fpath); autoload -Uz compinit; compinit` **before** the first compinit in `~/.zshrc`. Uninstall removes the dropped files.

### Typer ≥0.27 workaround (KEEP — still broken on 0.27.2)

With `add_completion=False`, typer registers completion classes only inside `completion_init()`, which the env-var completion server never calls → every Tab dies with `Shell bash not supported.` (exit 1), all four shells. Verified live on 0.27.0 AND 0.27.2; ble.sh fires the server per keystroke, spamming the shell. Issue: https://github.com/fastapi/typer/issues/1905 (related: #498).

Workaround — 3 lines in `main()` before `app()`:

```python
import typer.completion
typer.completion.completion_init()
```

This also exposes `get_completion_script(prog_name=..., complete_var=..., shell=...)` for the file drop. Always build with `add_completion=False`; dynamic `autocompletion=` callbacks read local state only, import lazily, return `[]` on any failure (short `timeout=` on subprocesses — the server fires per keystroke under ble.sh). The `2>/dev/null` on sourced/eval'd completion output is mandatory: a stale script/binary pair must degrade to "no candidates", never print into the shell.

### Migration (old marker-block installs)

Old `# >>> <tool> completions >>>` rc blocks are harmless leftovers; after reinstalling with file-drop completion, remove with:

```bash
sed -i '/^# >>> <tool> completions >>>$/,/^# <<< <tool> completions <<<$/d' ~/.bashrc
```
