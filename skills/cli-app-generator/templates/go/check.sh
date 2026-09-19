#!/usr/bin/env bash
# check.sh — lint + tests + verify-cli (skill scaffolding copies scripts/verify-cli next to this).
set -euo pipefail
DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
command -v go >/dev/null 2>&1 || export PATH="$HOME/.local/go/bin:$PATH"
command -v golangci-lint >/dev/null 2>&1 || export PATH="$HOME/.local/bin:$PATH"
(cd "$DIR" && golangci-lint run ./... && go test ./...)
VERIFY="$DIR/../verify-cli"; [ -f "$VERIFY" ] || VERIFY=$(command -v verify-cli)
BIN=$(mktemp); FIXTURE=$(mktemp)
printf 'junk\n' > "$FIXTURE"; trap 'rm -f "$BIN" "$FIXTURE"' EXIT
(cd "$DIR" && go build -o "$BIN" .)
"$VERIFY" "$BIN" "list" "delete $FIXTURE"
