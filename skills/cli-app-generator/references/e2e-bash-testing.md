# E2E Testing Pattern for Bash CLI Tools

A reusable pattern for e2e-testing bash scripts that operate on git repositories, files, or other systems — discovered while writing tests for `cleanup-branches` and `cleanup-worktrees`.

## Structure

```bash
#!/usr/bin/env bash
# Usage: bash test-e2e.sh [-v]

VERBOSE=false
[[ "${1:-}" == "-v" ]] && VERBOSE=true

PASS=0; FAIL=0; TOTAL=0

cleanup() { rm -rf "$TESTDIR"; }
TESTDIR=$(mktemp -d)
trap cleanup EXIT
```

## Assert helpers

```bash
assert_contains() {
    local haystack="$1" needle="$2" label="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$haystack" | grep -qF "$needle"; then
        PASS=$((PASS + 1))
        $VERBOSE && echo "  ✓ $label"
    else
        FAIL=$((FAIL + 1))
        echo "  ✗ $label"
        echo "    expected to contain: '$needle'"
    fi
}

assert_not_contains() {
    local haystack="$1" needle="$2" label="$3"
    TOTAL=$((TOTAL + 1))
    if ! echo "$haystack" | grep -qF "$needle"; then
        PASS=$((PASS + 1))
        $VERBOSE && echo "  ✓ $label"
    else
        FAIL=$((FAIL + 1))
        echo "  ✗ $label"
        echo "    expected NOT to contain: '$needle'"
    fi
}
```

## Running scripts in test repos

```bash
run_script() {
    local script="$1" dir="$2"
    shift 2
    (cd "$dir" && "$script" "$@" 2>&1) || true
}

# Usage:
OUT=$(run_script "$SCRIPT" "$TEST_REPO" some-arg --flag)
assert_contains "$OUT" "expected text" "test description"
```

## Git fixture setup

```bash
# Create a bare-bones repo
git init -q -b main "$TESTDIR/repo"
cd "$TESTDIR/repo"
git config user.email test@test
git config user.name Test
echo "file" > f && git add . && git commit -q -m "init"

# Create branches
git checkout -q -b feat/one
echo "change" >> f && git add . && git commit -q -m "change"
git checkout -q main
```

## Worktree fixtures

```bash
git checkout -q -b feat/branch
echo "worktree-content" >> f && git add . && git commit -q -m "wt"
git checkout -q main
WT_DIR="$TESTDIR/wt"
git worktree add "$WT_DIR" feat/branch
```

## Guarding against `set -euo pipefail` in scripts under test

Scripts with `set -e` abort on any failure. In deletion loops, a single failure kills the loop and the test runner:

```bash
# BROKEN — first failure kills loop and exits the whole script
while IFS= read -r item; do
    delete_branch "$item"
    ((count++))
done <<< "$list"

# FIXED — wrap in if/|| true
while IFS= read -r item; do
    [ -z "$item" ] && continue
    if delete_branch "$item"; then
        ((count++)) || true
    fi
done <<< "$list"
```

The same `|| true` guard applies to `((total++))` when the initial value is 0.

## Interactive mode testing limitation

Functions that use `read -p` inside a `while ... done <<< "$list"` loop read from the heredoc, not from stdio — piping `echo "y"` does NOT feed those prompts. Verify listing behavior instead:

```bash
# Can't test input, but can verify the listing:
OUT=$(run_script "$SCRIPT" "$REPO" interactive)
assert_contains "$OUT" "feat/interactive-test" "interactive shows branch name"
```

## Verifying worktree porcelain parsing

`git worktree list --porcelain` format:

```
worktree /path/to/worktree     ← exact path
HEAD abc123...
branch refs/heads/feature-x    ← 2 lines below
```

Wrong parsing (picks up hashes as paths):
```bash
# BROKEN:
git worktree list --porcelain | awk 'NR>1 {print $2}'
```

Correct parsing:
```bash
while IFS= read -r line; do
    if [[ $line =~ ^worktree\ (.*) ]]; then
        path="${BASH_REMATCH[1]}"
    fi
done < <(git worktree list --porcelain)
```

## Results block

```bash
echo ""
echo "======================================"
echo " RESULTS"
echo "======================================"
echo "  Passed: $PASS / $TOTAL"
echo "  Failed: $FAIL / $TOTAL"
echo ""
if [ "$FAIL" -gt 0 ]; then exit 1; fi
```

## Full example

See `tools/git-tools/test-e2e.sh` in the `cli-agents-config` repo for a complete working test suite with 47 tests across two scripts.