#!/usr/bin/env bash
# install.sh — idempotent: generate + symlink into ~/.local/bin + file-drop completions + cli-hub register.
set -euo pipefail
DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TOOL=sample                                     # scaffold: replace with the tool name
command -v bashly >/dev/null 2>&1 || export PATH="$(echo ~/.local/share/gem/ruby/*/bin | tr ' ' ':'):$PATH"
mkdir -p ~/.local/bin ~/.local/share/bash-completion/completions
chmod +x "$DIR/$TOOL"
ln -sf "$DIR/$TOOL" ~/.local/bin/"$TOOL"
"$DIR/$TOOL" completions > ~/.local/share/bash-completion/completions/"$TOOL"
"$DIR/$TOOL" --version
echo "installed: $TOOL → ~/.local/bin/$TOOL (bash completions file-dropped; new shells pick it up)"
command -v cli-hub >/dev/null 2>&1 && cli-hub register "$TOOL" --version "$("$DIR/$TOOL" --version)" \
  --description "Sample bashly CLI" --group misc --source-path "$DIR/$TOOL" \
  --uninstall "$DIR/uninstall.sh" --reinstall "$DIR/install.sh" --yes || true
