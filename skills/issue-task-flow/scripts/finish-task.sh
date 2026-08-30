#!/usr/bin/env bash
# finish-task.sh — run the full test suite, push, and open a draft PR.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/lib.sh"

usage() {
  cat <<'EOF'
finish-task.sh — full test run, single push, draft PR.

USAGE:
  finish-task.sh [--worktree <path>] [--base <branch>] [--title <text>] [--skip-tests]

Runs whatever full test commands it can detect (Maven/Gradle/Go/Rust/
Python[pytest,poetry]/npm/pnpm/bun), and only if they all pass: pushes the branch (first and only push —
all your milestone commits go up together) and opens a DRAFT pull request
against --base (default: repo's default branch). It never marks a PR ready
for review — do that yourself with 'gh pr ready' / 'glab mr update --ready'
once you've reviewed it.

On test failure, full output is saved to <worktree>/.issue-task-flow/test-output.log.
The tool-specific failure lines (build summary, stack-trace markers, etc.)
are grepped out and printed — falls back to the last 50 raw lines if
nothing matches.

OPTIONS:
  --worktree <path>   Worktree to operate in (default: current directory).
  --base <branch>     PR target branch (default: repo's default branch).
  --title <text>      PR title (default: derived from the branch name).
  --skip-tests        Skip the test run (you already ran it yourself).
  --non-interactive    Never prompt (e.g. for default-branch detection).
                       Fails fast with exit 2 instead — see EXIT CODES.
  -h, --help          Show this help.

EXIT CODES:
  0  success
  1  hard failure (tests failed, push failed, PR creation failed, etc.)
  2  needs human input — see stderr for what's needed.

On success, the last line of output is machine-parseable:
  RESULT: pushed=<branch> pr=<url-or-"none">
EOF
}

wt="" base="" title="" skip_tests=""

while [ $# -gt 0 ]; do
  case "$1" in
    --worktree) wt="$2"; shift 2 ;;
    --base) base="$2"; shift 2 ;;
    --title) title="$2"; shift 2 ;;
    --skip-tests) skip_tests=1; shift ;;
    --non-interactive) export ITF_NONINTERACTIVE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1 (see --help)" ;;
  esac
done

[ -n "$wt" ] && cd "$wt"
repo_root >/dev/null
branch="$(git rev-parse --abbrev-ref HEAD)"
[ -n "$base" ] || base="$(detect_default_branch)"

if [ -z "$skip_tests" ]; then
  echo "== running full test suite =="
  log_dir="$(repo_root)/.issue-task-flow"
  mkdir -p "$log_dir"
  log_file="$log_dir/test-output.log"
  : > "$log_file"

  # Runs "$@", appending its combined output to $log_file. On failure, greps
  # the log for $pattern (an ERE tuned to the tool via fail_pattern_for) and
  # prints the matches — usually far more useful than a raw tail, since
  # verbose tools (Gradle especially) can bury the actual failure well
  # before the log ends. Falls back to a raw tail if the pattern finds
  # nothing, so a failure is never silently hidden by a pattern miss.
  run_tests() {
    local desc="$1" pattern="$2"; shift 2
    echo "-- $desc --" >> "$log_file"
    if ! "$@" >>"$log_file" 2>&1; then
      local hits
      hits="$(grep -nE "$pattern" "$log_file" 2>/dev/null | tail -n 50 || true)"
      if [ -n "$hits" ]; then
        echo "--- $desc failed — matching lines from $log_file ---" >&2
        echo "$hits" >&2
      else
        echo "--- $desc failed — last 50 lines of $log_file (no pattern match) ---" >&2
        tail -n 50 "$log_file" >&2
      fi
      die "$desc failed — full output: $log_file"
    fi
  }

  ran_any=""
  [ -f pom.xml ] && { ran_any=1; run_tests "maven tests" "$(fail_pattern_for maven)" mvn -q test; }
  { [ -f build.gradle ] || [ -f build.gradle.kts ]; } && { ran_any=1; run_tests "gradle tests" "$(fail_pattern_for gradle)" ./gradlew test; }
  [ -f go.mod ] && { ran_any=1; run_tests "go tests" "$(fail_pattern_for go)" go test ./...; }
  [ -f Cargo.toml ] && { ran_any=1; run_tests "cargo tests" "$(fail_pattern_for rust)" cargo test; }
  if [ -f pyproject.toml ] || [ -f setup.py ] || [ -f setup.cfg ] || [ -f requirements.txt ] || [ -f pytest.ini ]; then
    if has_cmd poetry && [ -f poetry.lock ]; then
      ran_any=1; run_tests "python tests" "$(fail_pattern_for python)" poetry run pytest
    elif has_cmd pytest; then
      ran_any=1; run_tests "python tests" "$(fail_pattern_for python)" pytest
    else
      echo "warning: python project detected (pyproject.toml/setup.py/requirements.txt) but no pytest/poetry on PATH — skipping" >&2
    fi
  fi
  if [ -f package.json ]; then
    ran_any=1
    if has_cmd bun && { [ -f bun.lockb ] || [ -f bun.lock ]; }; then
      run_tests "bun tests" "$(fail_pattern_for node)" bun test
    elif has_cmd pnpm && [ -f pnpm-lock.yaml ]; then
      run_tests "pnpm tests" "$(fail_pattern_for node)" pnpm test
    else
      run_tests "npm tests" "$(fail_pattern_for node)" npm test
    fi
  fi
  [ -z "$ran_any" ] && echo "warning: no known test runner detected — verify manually" >&2
else
  echo "skipping tests (--skip-tests)"
fi

echo "== pushing $branch (single push, all milestone commits) =="
git push -u origin "$branch"

cli="$(detect_host_cli)"
[ -z "$title" ] && title="$(echo "$branch" | sed -E 's#^[a-z]+/##; s/[-_]/ /g')"
issue="$(issue_id_from_branch "$branch")"
body="Automated PR for branch \`$branch\`."
[ -n "$issue" ] && body="$body

Closes #$issue"

echo "== opening draft PR ($base <- $branch) =="
pr_url="none"
case "$cli" in
  gh)
    out="$(gh pr create --base "$base" --head "$branch" --title "$title" --body "$body" --draft)" \
      || die "gh pr create failed: $out"
    echo "$out"
    pr_url="$(printf '%s\n' "$out" | grep -o 'https://[^[:space:]]*' | tail -n1)"
    [ -z "$pr_url" ] && pr_url="created (see output above)"
    ;;
  glab)
    out="$(glab mr create --target-branch "$base" --source-branch "$branch" --title "$title" --description "$body" --draft)" \
      || die "glab mr create failed: $out"
    echo "$out"
    pr_url="$(printf '%s\n' "$out" | grep -o 'https://[^[:space:]]*' | tail -n1)"
    [ -z "$pr_url" ] && pr_url="created (see output above)"
    ;;
  *)
    echo "no gh/glab access — push is done, create the PR manually."
    ;;
esac

echo "RESULT: pushed=$branch pr=$pr_url"
