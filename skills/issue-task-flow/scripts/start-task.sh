#!/usr/bin/env bash
# start-task.sh — create (or resume) a git worktree for a task.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/lib.sh"

usage() {
  cat <<'EOF'
start-task.sh — set up an isolated git worktree/branch for a task.

USAGE:
  start-task.sh --branch <name> [--base <branch>] [--repo <path>]
  start-task.sh --resume <branch>

MODES:
  new task (default)   Create a new branch off --base (or the repo's default
                        branch if omitted) and a worktree for it at
                        ~/dev/worktrees/<repo>/<branch>.
  --resume <branch>     Continue work on an EXISTING branch. Reuses its
                        worktree if still present (worktrees are kept until
                        the PR is merged/closed), otherwise recreates one
                        from the remote branch.

OPTIONS:
  --branch <name>       New branch name. If --type/--issue are given instead,
                         the name is built as <type>/<issue>-<slug>.
  --type <feat|fix|chore>
  --issue <id>           Issue id, folded into the branch name.
  --slug <text>          Short description, folded into the branch name.
  --base <branch>        Base branch for a new task (default: repo's default branch).
  --repo <path>          Repo to operate in (default: current directory's repo).
  --resume <branch>      Resume an existing branch instead of creating one.
  --non-interactive       Never prompt. Any decision that would normally be
                          asked interactively (default-branch detection,
                          dirty-base handling) instead fails fast — see
                          EXIT CODES below.
  --on-dirty <choice>     Pre-supply the dirty-base decision so it never
                          prompts, interactive or not. One of: stash, commit,
                          push, ignore.
  -h, --help             Show this help.

EXIT CODES:
  0  success
  1  hard failure (git error, bad arguments, etc.)
  2  needs human input — an interactive decision was required but
     --non-interactive was set (or stdin isn't a terminal). stderr names
     what's needed and which flag supplies it.

EXAMPLES:
  start-task.sh --type fix --issue 482 --slug null-pointer-on-refund
  start-task.sh --branch chore/bump-deps --base develop
  start-task.sh --resume feat/123-webhook-retries
  start-task.sh --type feat --issue 55 --slug retries --base develop \
    --non-interactive --on-dirty ignore
EOF
}

branch="" base="" repo="" type="" issue="" slug="" resume="" on_dirty=""

while [ $# -gt 0 ]; do
  case "$1" in
    --branch) branch="$2"; shift 2 ;;
    --base) base="$2"; shift 2 ;;
    --repo) repo="$2"; shift 2 ;;
    --type) type="$2"; shift 2 ;;
    --issue) issue="$2"; shift 2 ;;
    --slug) slug="$2"; shift 2 ;;
    --resume) resume="$2"; shift 2 ;;
    --non-interactive) export ITF_NONINTERACTIVE=1; shift ;;
    --on-dirty) on_dirty="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1 (see --help)" ;;
  esac
done

case "$on_dirty" in
  ""|stash|commit|push|ignore) : ;;
  *) die "--on-dirty must be one of: stash, commit, push, ignore" ;;
esac

[ -n "$repo" ] && cd "$repo"
repo_root >/dev/null   # validate we're in a repo

if [ -n "$resume" ]; then
  wt="$(worktree_path "$resume")"
  if git worktree list | awk '{print $1}' | grep -qx "$wt"; then
    echo "Resuming existing worktree: $wt"
  else
    echo "No existing worktree for '$resume' — recreating from origin."
    git fetch origin "$resume" 2>/dev/null || true
    mkdir -p "$(worktrees_base)"
    if git show-ref --verify --quiet "refs/heads/$resume"; then
      git worktree add "$wt" "$resume"
    else
      git worktree add "$wt" -b "$resume" "origin/$resume"
    fi
  fi
  echo "cd $wt"
  exit 0
fi

# --- new task ---
[ -z "$branch" ] && {
  [ -n "$type" ] || die "need --branch, or --type (+ --issue/--slug), or --resume"
  parts="$type"
  [ -n "$issue" ] && parts="$parts/$issue"
  [ -n "$slug" ] && parts="$parts-$slug"
  branch="$parts"
}

[ -z "$base" ] && base="$(detect_default_branch)"

prompt_dirty_if_checked_out "$base" "$on_dirty" >/dev/null
git fetch origin "$base" || die "couldn't fetch origin/$base"

# If base is checked out somewhere locally, fast-forward that worktree's pointer too.
base_wt="$(git worktree list --porcelain | awk -v b="refs/heads/$base" '
  /^worktree /{p=$2} $0=="branch "b{print p}')"
if [ -n "${base_wt:-}" ]; then
  git -C "$base_wt" pull --ff-only origin "$base" || echo "warning: couldn't fast-forward $base_wt" >&2
fi

if git show-ref --verify --quiet "refs/heads/$branch"; then
  die "branch '$branch' already exists locally — use --resume $branch to continue work on it, or pick a different --branch/--slug"
fi

wt="$(worktree_path "$branch")"
if [ -e "$wt" ]; then
  die "a worktree already exists at $wt — use --resume $branch, or remove it first (cleanup-task.sh --branch $branch --force)"
fi

mkdir -p "$(worktrees_base)"
git worktree add -b "$branch" "$wt" "origin/$base"

echo "Created worktree for '$branch' off '$base':"
echo "cd $wt"
