#!/usr/bin/env python3
"""
Post a review note on a GitLab merge request.

Thin wrapper over `glab mr note create` so review agents post inline diff
comments with one stable interface. Mirrors add_inline_comment.py (GitHub).

Positioning follows glab semantics, NOT GitHub's:
- --line N or N:M targets the NEW side of the latest diff version
  (no LEFT/RIGHT or commit_id concept; GitLab binds to the latest version).
- --old-line N targets a REMOVED line (old side).
- Omit both for a file-level comment; omit --file for a general MR comment.

Long bodies: pass --body-file (piped to glab stdin) to avoid shell quoting
pitfalls with backticks/$/backslashes. --unique skips posting when the same
body already exists (idempotent re-runs). --validate checks --file/--line
against `glab mr diff` first: GitLab only accepts lines inside a diff hunk,
so a worktree file line number is rejected with `Line N not found in diff`.

Usage:
    python add_mr_note.py <project-url> <iid> -m "body" [--file PATH] [--line 42]
    python add_mr_note.py https://git.jibit.cloud/server/ipg-commons 38 \\
        --file src/Main.java --line 10:15 --body-file /tmp/note.md --unique --dry-run
"""

import argparse
import re
import subprocess
import sys

def build_command(project_url: str, iid: str, body: str | None, *,
                  file: str | None = None, line: str | None = None,
                  old_line: int | None = None, reply: str | None = None,
                  unique: bool = False, resolvable: bool = True) -> list:
    """
    Build the `glab mr note create` argv (without the body transport).

    Raises ValueError on flag combinations glab rejects: --line/--old-line
    require --file, are mutually exclusive; --file/--reply/--unique are
    mutually exclusive; --resolvable=false forbids --reply/--file.
    """
    if line is not None and old_line is not None:
        raise ValueError("--line and --old-line cannot be used together")
    if (line is not None or old_line is not None) and file is None:
        raise ValueError("--line/--old-line require --file")
    exclusive = [file is not None, reply is not None, unique]
    if sum(exclusive) > 1:
        raise ValueError("--file, --reply and --unique are mutually exclusive")
    if not resolvable and (reply is not None or file is not None):
        raise ValueError("--resolvable=false cannot be combined with --reply or --file")

    cmd = ['glab', 'mr', 'note', 'create', '-R', project_url, iid]
    if file is not None:
        cmd += ['--file', file]
    if line is not None:
        cmd += ['--line', str(line)]
    if old_line is not None:
        cmd += ['--old-line', str(old_line)]
    if reply is not None:
        cmd += ['--reply', reply]
    if unique:
        cmd += ['--unique']
    if not resolvable:
        cmd += ['--resolvable=false']
    if body is not None:
        cmd += ['-m', body]
    return cmd

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_diff_line_ranges(diff_text: str) -> dict:
    """Map each new-file path in a unified diff to its (old, new) line ranges.

    Returns {path: {\"old\": [(start, end)], \"new\": [(start, end)]}} where each
    (start, end) spans one hunk, inclusive. Context-only lines count for both
    sides; `-` lines only for old, `+` lines only for new.
    """
    files: dict = {}
    path = None
    old_ln = new_ln = 0
    hunk_old: list | None = None
    hunk_new: list | None = None

    def close_hunk() -> None:
        if path is not None and hunk_old is not None and hunk_new is not None:
            entry = files.setdefault(path, {"old": [], "new": []})
            if hunk_old[0] <= hunk_old[1]:
                entry["old"].append((hunk_old[0], hunk_old[1]))
            if hunk_new[0] <= hunk_new[1]:
                entry["new"].append((hunk_new[0], hunk_new[1]))

    def norm(side: str, prefix: str) -> str | None:
        side = side.strip()
        if side in ("", "/dev/null"):
            return None
        if side == prefix:
            return None
        if side.startswith(prefix + "/"):
            return side[len(prefix) + 1:]
        return side

    for raw in diff_text.splitlines():
        if raw.startswith("--- "):
            close_hunk()
            hunk_old = hunk_new = None
            path = norm(raw[4:], "a")
            continue
        if raw.startswith("+++ "):
            new_side = norm(raw[4:], "b")
            path = new_side if new_side is not None else None
            continue
        m = _HUNK_RE.match(raw)
        if m:
            close_hunk()
            old_ln = int(m.group(1))
            new_ln = int(m.group(3))
            hunk_old = [old_ln, old_ln - 1]
            hunk_new = [new_ln, new_ln - 1]
            continue
        if hunk_old is None or path is None:
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            hunk_new[1] = new_ln
            new_ln += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            hunk_old[1] = old_ln
            old_ln += 1
        else:
            # Context line (or "\ No newline" marker): advance both cursors.
            if raw.startswith("\\"):
                continue
            hunk_old[1] = old_ln
            hunk_new[1] = new_ln
            old_ln += 1
            new_ln += 1
    close_hunk()
    return files


def validate_diff_position(diff_text: str, file: str, line: str | None = None,
                           old_line: int | None = None) -> None:
    """Pre-validate an inline position against `glab mr diff` output.

    Raises ValueError with a clear message (valid ranges included) when the
    file is absent from the diff or the line/range falls outside every hunk.
    GitLab only accepts positions inside a diff hunk — NOT arbitrary file
    line numbers — so this catches the mistake client-side before glab's
    terse `Line N not found in diff` error.
    """
    ranges = parse_diff_line_ranges(diff_text)
    if file not in ranges:
        known = ", ".join(sorted(ranges)) or "(empty diff)"
        raise ValueError(f"{file!r} is not in the MR diff. Files in diff: {known}")

    def fmt(side_ranges: list) -> str:
        return ", ".join(f"{s}-{e}" if s != e else f"{s}" for s, e in side_ranges)

    if old_line is not None:
        covered = any(s <= old_line <= e for s, e in ranges[file]["old"])
        if not covered:
            raise ValueError(
                f"--old-line {old_line} is outside every hunk of {file!r} "
                f"(removed-side lines in diff: {fmt(ranges[file]['old']) or 'none'}). "
                "Use a removed (-) line inside a @@ hunk, or drop --old-line for a file-level note.")
        return
    if line is not None:
        try:
            lo_s, _, hi_s = line.partition(":")
            lo, hi = int(lo_s), int(hi_s) if hi_s else int(lo_s)
        except ValueError:
            raise ValueError(f"--line {line!r}: expected N or N:M with integer lines")
        if lo > hi:
            raise ValueError(f"--line {line!r}: start must not exceed end")
        side = ranges[file]["new"]
        if not any(s <= lo and hi <= e for s, e in side):
            raise ValueError(
                f"--line {line} is outside every hunk of {file!r} "
                f"(added-side lines in diff: {fmt(side) or 'none'}). "
                "Use a line inside a @@ hunk, or drop --line for a file-level note.")


def fetch_mr_diff(project_url: str, iid: str) -> str:
    """Fetch the MR unified diff via glab (used for --validate position checks)."""
    try:
        result = subprocess.run(
            ["glab", "mr", "diff", "-R", project_url, iid],
            capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to fetch MR diff for validation: {e.stderr.strip() or e}")
    except FileNotFoundError:
        raise RuntimeError("glab CLI not found. See https://gitlab.com/gitlab-org/cli")


def post_note(cmd: list, body_from_stdin: str | None = None) -> str:
    """Run the glab command; body_from_stdin pipes long bodies via stdin."""
    try:
        result = subprocess.run(cmd, input=body_from_stdin,
                                capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to post MR note: {e.stderr.strip() or e}")
    except FileNotFoundError:
        raise RuntimeError("glab CLI not found. See https://gitlab.com/gitlab-org/cli")


def main() -> None:
    parser = argparse.ArgumentParser(description='Post a review note on a GitLab MR',
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__)
    parser.add_argument('project_url', help='Full project URL, e.g. https://git.jibit.cloud/server/ipg-commons')
    parser.add_argument('iid', help='MR iid (number after !)')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-m', '--body', help='Short inline body')
    group.add_argument('--body-file', help='File with note body (piped via stdin, preferred for markdown)')
    parser.add_argument('--file', help='File path for a diff comment')
    parser.add_argument('--line', help='New-side line or range (e.g. 42 or 10:15)')
    parser.add_argument('--old-line', type=int, help='Old-side line for removed code')
    parser.add_argument('--reply', help='Discussion ID (or 8+ char prefix) to reply in')
    parser.add_argument('--unique', action='store_true', help='Skip if same body already exists')
    parser.add_argument('--resolvable', default='true', choices=['true', 'false'],
                        help='false = non-resolvable note (automation/status only)')
    parser.add_argument('--dry-run', action='store_true', help='Print the glab command, do not post')
    parser.add_argument('--validate', action='store_true',
                        help='Check --file/--line/--old-line against `glab mr diff` before posting')
    args = parser.parse_args()

    try:
        body = args.body
        stdin_body = None
        if args.body_file:
            with open(args.body_file) as f:
                stdin_body = f.read()
        cmd = build_command(args.project_url, args.iid, body,
                            file=args.file, line=args.line, old_line=args.old_line,
                            reply=args.reply, unique=args.unique,
                            resolvable=args.resolvable == 'true')
        if args.validate and args.file is not None and (args.line is not None or args.old_line is not None):
            validate_diff_position(fetch_mr_diff(args.project_url, args.iid),
                                   args.file, line=args.line, old_line=args.old_line)
        if args.dry_run:
            shown = [c if not c.startswith('-') or len(c) < 40 else c[:40] + '...' for c in cmd]
            print('DRY-RUN:', ' '.join(f'"{c}"' if ' ' in c else c for c in shown))
            if stdin_body is not None:
                print(f'(body piped via stdin, {len(stdin_body)} chars)')
            return
        if stdin_body is not None:
            print(post_note(cmd, body_from_stdin=stdin_body))
        else:
            print(post_note(cmd))
        print("Note posted successfully.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
