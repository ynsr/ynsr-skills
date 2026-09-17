#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# install.sh — install the <tool> single-file CLI into ~/.local/bin
#
# Usage:
#   ./install.sh
#
# Idempotent: safe to re-run (upgrades in place, refreshes the receipt).
# Steps: copy → chmod → install receipt (stale-warning guard) → verify →
#        register with cli-hub (best-effort).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL="<tool>"                       # installed command name
SRC="$DIR/tool.py"
BIN="${HOME}/.local/bin/${TOOL}"

echo "==> Installing ${TOOL} (single-file CLI) …"

mkdir -p "${HOME}/.local/bin"
cp -f "$SRC" "$BIN"
chmod +x "$BIN"

# Install receipt: SHA-256 over the script bytes (12 hex). The tool reads it
# to warn when the source tree changed after install ("installed copy is
# stale"). Keep the hashing identical to _source_hash() in tool.py.
python3 -c "
import datetime, hashlib, json, pathlib
src = pathlib.Path('$SRC').resolve()
receipt = pathlib.Path.home() / '.local' / 'share' / '${TOOL}' / 'install-receipt.json'
receipt.parent.mkdir(parents=True, exist_ok=True)
h = hashlib.sha256(src.read_bytes()).hexdigest()[:12]
receipt.write_text(json.dumps({
    'source_hash': h,
    'installed_at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
    'source_path': str(src),
    'installed_path': '$BIN',
}, indent=2) + '\n')
print('  → install receipt:', h)
"

# Verify.
if command -v "$TOOL" &>/dev/null; then
    "$TOOL" version || true
else
    echo "  ! ${TOOL} not found in PATH after install." >&2
    echo "    Ensure ~/.local/bin is on PATH (then re-login or re-run):" >&2
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\"" >&2
fi

echo ""
echo "==> Done."
echo ""
echo "Quick start:"
echo "  ${TOOL} --help"
echo ""
echo "Uninstall:"
echo "  ${DIR}/uninstall.sh"

# Register with cli-hub (best-effort; never fail the install when the hub is
# absent). Hooks point at this directory's scripts so the hub re-runs the
# exact installer that owns the receipt.
if command -v cli-hub &>/dev/null; then
    REPO_URL="$(git -C "$DIR" remote get-url origin 2>/dev/null || true)"
    VERSION="$("$TOOL" version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
    cli-hub register "$TOOL" \
        --version "${VERSION:-0.1.0}" \
        --description "<one-line description>" \
        --group "<group: git|media|db|net|meta|misc>" \
        --source-path "$BIN" \
        ${REPO_URL:+--repo "$REPO_URL"} \
        --uninstall "${DIR}/uninstall.sh" \
        --reinstall "${DIR}/install.sh" \
        --yes || true
fi
