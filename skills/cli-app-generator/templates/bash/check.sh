#!/usr/bin/env bash
# check.sh — lint + tests + verify-cli (skill scaffolding copies scripts/verify-cli next to this).
set -euo pipefail
DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
command -v bashly >/dev/null 2>&1 || export PATH="$(echo ~/.local/share/gem/ruby/*/bin | tr ' ' ':'):$PATH"
command -v shellcheck >/dev/null 2>&1 || export PATH="$HOME/.local/bin:$PATH"
(cd "$DIR" && bashly generate)
shellcheck "$DIR/sample" "$DIR"/src/*.sh "$DIR"/src/lib/contract.sh 2>/dev/null
bats "$DIR"/test
FIXTURE=$(mktemp); printf '{"name":"alice","role":"admin"}\n' > "$FIXTURE"; trap 'rm -f "$FIXTURE"' EXIT
VERIFY="$DIR/../verify-cli"; [ -f "$VERIFY" ] || VERIFY=$(command -v verify-cli)
"$VERIFY" "$DIR/sample" "show" "delete $FIXTURE"
