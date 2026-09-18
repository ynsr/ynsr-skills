"""Shell completion: `completions show|install` + value-completion helpers.

Why this exists instead of Typer's built-in `--install-completion`:
the app is constructed with ``add_completion=False`` so there is exactly
one completion system. ``completions show <shell>`` prints a script for
``eval "$(mycli completions show bash)"``; ``completions install`` drops
that eval line into ~/.bashrc / ~/.zshrc idempotently inside a marker
block (atomic write, backup kept).

Completion order (subcommands -> positional values -> flags) is NOT
hand-coded: Click resolves the cursor position and offers only valid
next tokens. Subcommand names and ``-``/``--`` flags are free. The only
custom code needed is an ``autocompletion=`` callback per dynamic
positional/option value (e.g. profile names, like ``git branch`` cycling
branches). Those callbacks MUST be fast, offline, and never raise —
return [] on any failure so Tab never breaks the shell.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Callable, Optional

__all__ = [
    "SUPPORTED_SHELLS",
    "RC_FILES",
    "START_MARKER",
    "END_MARKER",
    "detect_shell",
    "ensure_completion_classes",
    "eval_line",
    "install_snippet",
    "install_completion",
    "complete_names",
    "get_completion_script",
]

SUPPORTED_SHELLS = ("bash", "zsh", "fish")

RC_FILES = {
    "bash": "~/.bashrc",
    "zsh": "~/.zshrc",
    "fish": "~/.config/fish/config.fish",
}

START_MARKER = "# >>> {prog} completions >>>"
END_MARKER = "# <<< {prog} completions <<<"


def ensure_completion_classes():
    """Register Typer's shell completion classes; return shell_completion.

    typer >= 0.27 vendors click but only registers its bash/zsh/fish
    completion classes inside ``completion_init()``, which the env-var
    completion server (``_MYCLI_COMPLETE=complete_<shell>``) never
    calls — without this every Tab dies with "Shell bash not
    supported." (ble.sh fires the server on every keystroke). Call once
    at CLI startup (``main()``) and before rendering a script.
    Idempotent; falls back to a plain click install (classes
    self-register there).
    """
    try:
        from typer._click import shell_completion
    except ImportError:  # older typer: plain click
        import click.shell_completion as shell_completion
        return shell_completion
    if not shell_completion.get_completion_class("bash"):
        from typer._completion_classes import completion_init
        completion_init()
    return shell_completion


def detect_shell() -> Optional[str]:
    """Best-effort shell name from $SHELL; None if unknown/unsupported."""
    shell = os.path.basename(os.environ.get("SHELL", "")).strip()
    return shell if shell in SUPPORTED_SHELLS else None


def eval_line(prog: str, shell: str) -> str:
    """The rc line the user sources. fish uses () instead of $().

    Server stderr is discarded inside the sourced line: a failing
    completion server must never print into the shell (ble.sh/zsh fire
    it on every keystroke). Manual `completions show` still shows errors.
    """
    if shell == "fish":
        return f"{prog} completions show fish 2>/dev/null | source"
    return f'eval "$({prog} completions show {shell} 2>/dev/null)"'


def install_snippet(prog: str, shell: str) -> str:
    """Marker block written into the rc file. zsh needs compinit first."""
    lines = [START_MARKER.format(prog=prog)]
    if shell == "zsh":
        lines.append("autoload -U compinit && compinit  # required for completion (added by %s)" % prog)
    lines.append(eval_line(prog, shell))
    lines.append(END_MARKER.format(prog=prog))
    return "\n".join(lines) + "\n"


def install_completion(prog: str, shell: str, rcfile: Optional[Path] = None) -> tuple[Path, bool]:
    """Idempotently ensure the marker block is in the rc file.

    Returns (rc path, changed). Atomic write (tmp + rename); keeps a
    ``.bak`` copy on first modification. Re-running is a no-op.
    Raises ValueError on unsupported shell.
    """
    if shell not in SUPPORTED_SHELLS:
        raise ValueError(f"unsupported shell {shell!r} (choose from: {', '.join(SUPPORTED_SHELLS)})")
    rc = Path(rcfile).expanduser() if rcfile else Path(RC_FILES[shell]).expanduser()
    snippet = install_snippet(prog, shell)
    existing = rc.read_text(encoding="utf-8") if rc.is_file() else ""
    if snippet.strip() in existing:
        return rc, False
    # Replace a stale block from an older version rather than duplicating.
    pattern = re.compile(
        re.escape(START_MARKER.format(prog=prog)) + r".*?" + re.escape(END_MARKER.format(prog=prog)) + r"\n?",
        re.DOTALL,
    )
    if pattern.search(existing):
        updated = pattern.sub(snippet, existing)
    else:
        sep = "" if not existing or existing.endswith("\n") else "\n"
        updated = existing + (sep + "\n" if existing else "") + snippet
    rc.parent.mkdir(parents=True, exist_ok=True)
    if rc.is_file():
        import shutil
        shutil.copy2(rc, rc.parent / (rc.name + ".bak"))  # backup before overwrite
    tmp = rc.parent / (rc.name + ".tmp")
    tmp.write_text(updated, encoding="utf-8")
    tmp.replace(rc)
    return rc, True


def complete_names(list_fn: Callable[[], object]) -> Callable:
    """Build an ``autocompletion=`` callback over locally stored names.

    ``list_fn`` returns the names to offer — usually ``list_profiles`` or any
    local-state read (dict- or list-returning). It is called ONCE per Tab and
    wrapped so ANY failure (missing dir, bad JSON, non-zero subprocess)
    yields [] instead of breaking Tab. The factory owns the failure rule, so
    sources stay plain — including ``check=True`` subprocess calls with a
    short ``timeout=`` (the completion server fires per keystroke).
    Usage::

        _complete_profiles = complete_names(list_profiles)
        _complete_branches = complete_names(_cwd_git_branches)  # see references/

        @app.command("list")
        def list_cmd(resource: str = typer.Argument(..., autocompletion=_complete_profiles)): ...
    """

    def _complete(ctx, incomplete: str) -> list[str]:
        try:
            raw = list_fn()
            names = list(raw.keys()) if isinstance(raw, dict) else list(raw)
        except Exception:
            return []
        return sorted(n for n in names if n.startswith(incomplete))

    return _complete


def get_completion_script(prog: str, shell: str, click_cmd=None) -> str:
    """Render Click's completion script for *shell*.

    ``click_cmd`` is the resolved click command (``typer.main.get_command(app)``);
    pass it explicitly so this module never imports your app (no cycles).
    Raises ValueError on unsupported shell.
    """
    shell_completion = ensure_completion_classes()

    if shell not in SUPPORTED_SHELLS:
        raise ValueError(f"unsupported shell {shell!r} (choose from: {', '.join(SUPPORTED_SHELLS)})")
    if click_cmd is None:
        raise ValueError("click_cmd is required (pass typer.main.get_command(app))")
    cls = shell_completion.get_completion_class(shell)
    if cls is None:  # defensive: registration covers every supported shell
        raise ValueError(f"unsupported shell {shell!r} (choose from: {', '.join(SUPPORTED_SHELLS)})")
    complete_var = f"_{prog.upper().replace('-', '_')}_COMPLETE"
    return cls(click_cmd, {}, prog, complete_var).source()


def print_install_hint(prog: str, shell: Optional[str], rc: Path, file=sys.stderr) -> None:
    """Tell the user to reload — completion needs a fresh shell."""
    print(f"installed {prog} completion for {shell} in {rc}", file=file)
    print(f"restart your shell or run: source {rc}", file=file)
