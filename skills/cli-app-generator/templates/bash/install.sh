#!/usr/bin/env bash
# install.sh — idempotent: generate + symlink into ~/.local/bin + file-drop completions + cli-hub register.
set -euo pipefail
DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TOOL=sample                                     # scaffold: replace with the tool name
if ! command -v bashly >/dev/null 2>&1; then   # guarded fallback: never put a literal glob in PATH
  shopt -s nullglob
  gems=(~/.local/share/gem/ruby/*/bin)
  shopt -u nullglob
  [ -x "${gems[0]:-}/bashly" ] && export PATH="${gems[0]}:$PATH" || true
fi
(cd "$DIR" && bashly generate)                 # always regenerate: never install a stale script
mkdir -p ~/.local/bin ~/.local/share/bash-completion/completions
ln -sf "$DIR/$TOOL" ~/.local/bin/"$TOOL"
"$DIR/$TOOL" --version
echo "installed: $TOOL → ~/.local/bin/$TOOL (bash completions file-dropped; new shells pick it up)"
command -v cli-hub >/dev/null 2>&1 && cli-hub register "$TOOL" --version "$("$DIR/$TOOL" --version)" \
  --description "Sample bashly CLI" --group misc --source-path "$DIR/$TOOL" --uninstall "$DIR/uninstall.sh" --reinstall "$DIR/install.sh" --yes || true
