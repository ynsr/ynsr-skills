#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────
# Uninstall <tool-name> — reverses install.sh
# Idempotent: safe to re-run when already uninstalled.
# ───────────────────────────────────────────────────────────
set -euo pipefail

TOOL="<tool-name>"                      # e.g. harness-model-sync
SHARE_DIR="${HOME}/.local/share/${TOOL}"

echo "==> Removing scheduled jobs / services for ${TOOL} …"
# Tool-specific teardown first (cron, systemd, completions), e.g.:
#   "$TOOL" remove-cron --harness all 2>/dev/null || true
#   systemctl --user disable --now "${TOOL}.service" 2>/dev/null || true

echo "==> Removing Python package …"
if command -v uv &>/dev/null; then
    uv tool uninstall "$TOOL" 2>/dev/null || echo "  (not installed via uv)"
elif command -v pipx &>/dev/null; then
    pipx uninstall "$TOOL" 2>/dev/null || echo "  (not installed via pipx)"
else
    echo "  (neither uv nor pipx found; skipping package removal)"
fi

if command -v cli-hub &>/dev/null; then
    cli-hub unregister "$TOOL" --yes 2>/dev/null || true
fi

echo "  → Removing shared data directory (includes install receipt) …"
rm -rf "$SHARE_DIR"

echo "  ✔ ${TOOL} has been uninstalled."
