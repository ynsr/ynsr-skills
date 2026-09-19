# Bash testing: bats + e2e pattern

Trivial one-shot bash: no tests. Reused/bashly-generated tools: `bats` for units + an inline e2e harness; every skeleton's `check` target = shellcheck + tests + `scripts/verify-cli`.

## bats skeleton

```bash
# test/tool.bats
setup() {
    TESTDIR="$(mktemp -d)"
    BIN="$BATS_TEST_DIRNAME/../tool.sh"
}
teardown() { rm -rf "$TESTDIR"; }

@test "--help exits 0 and documents exit codes" {
    run "$BIN" --help
    [ "$status" -eq 0 ]
    grep -q "Exit codes" "$output"
}

@test "bad subcommand exits 2 with error envelope on stderr" {
    run "$BIN" nope
    [ "$status" -eq 2 ]
    echo "$output" | grep -q '"error"'
}

@test "stdout is data-only (logs go to stderr)" {
    run "$BIN" list --output csv
    [ "$status" -eq 0 ]
    ! echo "$output" | grep -q '^Log:'
}
```

## Inline e2e harness (when bats is unavailable)

```bash
#!/usr/bin/env bash
PASS=0; FAIL=0; TOTAL=0
cleanup() { rm -rf "$TESTDIR"; }
TESTDIR="$(mktemp -d)"; trap cleanup EXIT

assert_contains() {
    local haystack="$1" needle="$2" label="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$haystack" | grep -qF "$needle"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1)); echo "  ✗ $label (expected to contain: '$needle')"
    fi
}
# TOTAL=$((TOTAL + 1)) needs || true under set -e when the counter starts at 0:
# TOTAL=$((TOTAL + 1)) || true
```

## `set -euo pipefail` pitfalls under test

Scripts with `set -e` abort on any failure. In deletion loops, one failure kills the loop and the runner:

```bash
# BROKEN — first failure exits the whole script
while IFS= read -r item; do
    delete "$item"
    ((count++))
done <<< "$list"

# FIXED — guard the guardable
while IFS= read -r item; do
    [ -z "$item" ] && continue
    if delete "$item"; then
        ((count++)) || true
```
    fi
done <<< "$list"

## Porcelain parsing

```bash
while IFS= read -r line; do
    if [[ $line =~ ^worktree\ (.*) ]]; then
        path="${BASH_REMATCH[1]}"
    fi
done < <(git worktree list --porcelain)
```

## Results block

```bash
echo "Passed: $PASS / $TOTAL, Failed: $FAIL / $TOTAL"
[ "$FAIL" -eq 0 ]
```
