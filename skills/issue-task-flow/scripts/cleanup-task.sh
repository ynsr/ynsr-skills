#!/usr/bin/env bash
# cleanup-task.sh — remove a task's worktree once its PR is merged/closed.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/lib.sh"

usage() {
  cat <<'EOF'
cleanup-task.sh — remove a task's worktree.

USAGE:
  cleanup-task.sh --branch <name> [--repo <path>] [--force] [--delete-branch]

By default this refuses to remove the worktree unless the associated PR/MR
is merged or closed (checked via gh/glab). Use --force to remove it anyway
(e.g. you're abandoning the task).

OPTIONS:
  --branch <name>     Branch/worktree to clean up.
  --repo <path>       Repo to operate in (default: current directory's repo).
  --force             Remove even if the PR looks open or can't be checked.
  --delete-branch     Also delete the local and remote branch after removal.
  -h, --help          Show this help.
EOF
}

branch="" repo="" force="" delete_branch=""

while [ $# -gt 0 ]; do
  case "$1" in
    --branch) branch="$2"; shift 2 ;;
    --repo) repo="$2"; shift 2 ;;
    --force) force=1; shift ;;
    --delete-branch) delete_branch=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1 (see --help)" ;;
  esac
done

[ -n "$repo" ] && cd "$repo"
repo_root >/dev/null
[ -n "$branch" ] || die "need --branch"

if [ -z "$force" ]; then
  cli="$(detect_host_cli)"
  state=""
  case "$cli" in
    gh)   state="$(gh pr view "$branch" --json state -q .state 2>/dev/null || true)" ;;
    glab) state="$(glab mr view "$branch" -F json 2>/dev/null | grep -o '"state":"[^"]*"' | cut -d'"' -f4 || true)" ;;
  esac
  case "$state" in
    MERGED|merged|CLOSED|closed) : ;;
    "") echo "warning: couldn't determine PR/MR state — use --force to remove anyway." >&2; exit 1 ;;
    *) die "PR/MR for '$branch' looks open ($state) — use --force to remove anyway" ;;
  esac
fi

wt="$(worktree_path "$branch")"
git worktree remove "$wt" --force 2>/dev/null || git worktree remove "$wt" || die "couldn't remove worktree at $wt"
echo "Removed worktree: $wt"

if [ -n "$delete_branch" ]; then
  git branch -D "$branch" 2>/dev/null || true
  git push origin --delete "$branch" 2>/dev/null || true
  echo "Deleted local and remote branch '$branch'"
fi
