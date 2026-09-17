#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# uninstall.sh — remove the <tool> single-file CLI (reverses install.sh)
#
# Usage:
#   ./uninstall.sh
#
# Idempotent: safe to re-run when already uninstalled.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

TOOL="<tool>"

echo "==> Removing ${TOOL} …"

# Binary.
rm -f "${HOME}/.local/bin/${TOOL}"

# Shared data directory (includes the install receipt).
rm -rf "${HOME}/.local/share/${TOOL}"

# Drop from the cli-hub registry (best-effort).
if command -v cli-hub &>/dev/null; then
    cli-hub unregister "$TOOL" --yes 2>/dev/null || true
fi

echo "  ✔ ${TOOL} has been uninstalled."
