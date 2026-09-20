#!/usr/bin/env bash
# uninstall.sh — reverse install.sh (idempotent): remove the binary + cli-hub entry.
set -euo pipefail
TOOL=ok-name                                     # scaffold: replace with the tool name
rm -f ~/.local/bin/"$TOOL"
command -v cli-hub >/dev/null 2>&1 && cli-hub unregister "$TOOL" --yes 2>/dev/null || true
echo "uninstalled: $TOOL (nothing else was created)"
