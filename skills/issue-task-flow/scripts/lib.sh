#!/usr/bin/env bash
# Shared helpers for issue-task-flow scripts. Source, don't execute.
set -euo pipefail

die() { echo "error: $*" >&2; exit 1; }

# Like die(), but signals "a human needs to decide something" rather than a
# hard failure. Exit code 2 is reserved for this so an orchestrating agent
# can distinguish "ask the user" from "something actually broke" (exit 1) or
# "worked fine" (exit 0) by checking $?.
needs_input() { echo "NEEDS_INPUT: $*" >&2; exit 2; }

has_cmd() { command -v "$1" >/dev/null 2>&1; }

# True only if it's safe to block on a `read` prompt: stdin is a real
# terminal AND the caller hasn't opted out via --non-interactive. Scripts
# must check this before every `read` — never prompt unconditionally, since
# a non-tty stdin can hang forever waiting for input that will never come.
should_prompt() {
  [ "${ITF_NONINTERACTIVE:-0}" != "1" ] && [ -t 0 ]
}

repo_root() {
  git rev-parse --show-toplevel 2>/dev/null || die "not inside a git repo (pass --repo or cd into one)"
}

repo_name() { basename "$(repo_root)"; }

worktrees_base() { echo "$HOME/dev/worktrees/$(repo_name)"; }

worktree_path() { echo "$(worktrees_base)/$1"; }

# Which git-host CLI is usable for this repo's origin remote.
detect_host_cli() {
  if has_cmd gh && gh repo view >/dev/null 2>&1; then
    echo gh
  elif has_cmd glab && glab repo view >/dev/null 2>&1; then
    echo glab
  else
    echo ""
  fi
}

# Resolve the default branch: host API -> origin/HEAD symref -> ask.
detect_default_branch() {
  local cli branch
  cli="$(detect_host_cli)"
  if [ "$cli" = "gh" ]; then
    branch="$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name 2>/dev/null || true)"
  elif [ "$cli" = "glab" ]; then
    branch="$(glab repo view -F json 2>/dev/null | grep -o '"default_branch":"[^"]*"' | cut -d'"' -f4 || true)"
  fi
  if [ -z "${branch:-}" ]; then
    git fetch origin >/dev/null 2>&1 || true
    branch="$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || true)"
  fi
  if [ -z "${branch:-}" ]; then
    if should_prompt; then
      read -rp "Couldn't detect the default branch — enter it (e.g. main/dev/develop): " branch
    else
      needs_input "couldn't detect the default branch (gh/glab not authenticated for this repo, and no origin/HEAD set) — pass --base explicitly"
    fi
  fi
  echo "$branch"
}

# If $1 (a branch) is checked out in some worktree and that worktree is dirty,
# resolve what to do before we touch it. No-op if clean or not checked out.
# $2, if set, is a pre-supplied decision (stash/commit/push/ignore) — e.g. from
# --on-dirty — and skips prompting entirely, interactive or not. Caller is
# responsible for validating $2 against the allowed set before calling this.
prompt_dirty_if_checked_out() {
  local branch="$1" choice="${2:-}" path=""
  while IFS= read -r line; do
    case "$line" in
      worktree\ *) cur_path="${line#worktree }" ;;
      branch\ refs/heads/*)
        if [ "${line#branch refs/heads/}" = "$branch" ]; then path="$cur_path"; fi
        ;;
    esac
  done < <(git worktree list --porcelain)

  [ -z "$path" ] && return 0
  [ -z "$(git -C "$path" status --porcelain 2>/dev/null)" ] && { echo "$path"; return 0; }

  if [ -z "$choice" ]; then
    if should_prompt; then
      echo "'$branch' is checked out at $path and has uncommitted changes." >&2
      read -rp "Choose: [s]tash / [c]ommit / commit-and-[p]ush / [i]gnore / [a]bort: " choice
    else
      needs_input "'$branch' is checked out at $path with uncommitted changes — pass --on-dirty <stash|commit|push|ignore> or rerun interactively"
    fi
  fi
  case "$choice" in
    s|stash) git -C "$path" stash push -u -m "auto-stash before pulling $branch" ;;
    c|commit) git -C "$path" add -A && git -C "$path" commit -m "WIP before pulling $branch" ;;
    p|push) git -C "$path" add -A && git -C "$path" commit -m "WIP before pulling $branch" && git -C "$path" push ;;
    i|ignore) : ;;
    a|abort) die "aborted by user" ;;
    *) die "unrecognized dirty-tree choice: '$choice'" ;;
  esac
  echo "$path"
}

# Extended-regex (grep -E) used to pull the useful failure signal out of a
# tool's raw test-output log, instead of a blind tail. Verbose tools
# (Gradle especially) can bury the actual failure far from the end of the
# log, or keep printing harmless steps after it; a targeted grep surfaces
# the summary/error lines regardless of where they land. Patterns are
# deliberately loose (OR'd terms): a false positive just adds a line to the
# summary, and a false negative is never silent — the caller falls back to
# a raw tail when nothing matches, so no failure detail is ever hidden.
fail_pattern_for() {
  case "$1" in
    maven)  echo 'Caused by:|BUILD SUCCESS|BUILD FAILURE|ERROR|FAILURE|Tests run:|Failed tests:' ;;
    gradle) echo 'BUILD FAILED|> Task .* FAILED|Caused by:|[0-9]+ tests? completed.*failed' ;;
    go)     echo '^--- FAIL|^FAIL\b|panic:|Error Trace:|^\s*Error:' ;;
    node)   echo 'Caused by:|✕|✗|✖|\bFAIL\b|\bfailing\b|AssertionError|^Error:|npm ERR!|ERR_PNPM' ;;
    python) echo 'FAILED\b|^ERRORS?\b|Traceback \(most recent call last\)|AssertionError|short test summary info' ;;
    rust)   echo 'FAILED\b|error\[E[0-9]+\]|panicked at|test result: FAILED|assertion failed|^error:' ;;
    *)      echo '\berror\b|\bfail(ed|ing)?\b' ;;
  esac
}

# Parse "type/issue-id-slug" style branch names to pull out a numeric issue id, if present.
issue_id_from_branch() {
  echo "$1" | grep -oE '[0-9]+' | head -1 || true
}
