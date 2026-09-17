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
body already exists (idempotent re-runs).

Usage:
    python add_mr_note.py <project-url> <iid> -m "body" [--file PATH] [--line 42]
    python add_mr_note.py https://git.jibit.cloud/server/ipg-commons 38 \\
        --file src/Main.java --line 10:15 --body-file /tmp/note.md --unique --dry-run
"""

import argparse
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
