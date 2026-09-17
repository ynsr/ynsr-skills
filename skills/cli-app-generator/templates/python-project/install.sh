#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────
# Install <tool-name> — <one-line description>
# Idempotent: safe to re-run. Reinstalls the package, refreshes
# the install receipt (for `<tool> doctor`), and registers with cli-hub.
#
# Usage: ./install.sh [OPTIONS]
#
# Options:
#   -h, --help           Show this help message and exit.
#   -s, --schedule CRON  Cron schedule (default: '0 */6 * * *' = every 6h)
#                        (only for tools with periodic sync)
#
# Examples:
#   ./install.sh                              # install + all extras
#   ./install.sh --schedule='0 */3 * * *'     # custom schedule
# ───────────────────────────────────────────────────────────
set -euo pipefail

# ── Parse arguments ─────────────────────────────────────────────────────────
SCHEDULE="0 */6 * * *"

usage() {
    sed -n '/^# Usage:/,/^# ──/p' "$0" | sed 's/^# //;s/^#$//'
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage ;;
        -s|--schedule) SCHEDULE="$2"; shift 2 ;;
        --schedule=*) SCHEDULE="${1#*=}"; shift ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

# ── Install ─────────────────────────────────────────────────────────────────
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL="<tool-name>"                      # e.g. harness-model-sync
PKG_DIR="src/<package>"                 # e.g. src/harness_model_sync
SHARE_DIR="${HOME}/.local/share/${TOOL}"

echo "==> Installing ${TOOL} …"

# 1. Installer backend: uv preferred, pipx fallback.
#    Both snapshot the source into an isolated venv — workspace edits do NOT
#    reach the installed binary until this script re-runs. Pick ONE canonical
#    installer per tool; supporting both here avoids hard failure, but mixing
#    them fights over the same ~/.local/bin symlink (pipx then reports
#    "symlink missing or pointing to unexpected location").
if ! command -v uv &>/dev/null && ! command -v pipx &>/dev/null; then
    echo "ERROR: 'uv' or 'pipx' is required but neither was found."
    echo "Install uv with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 2. Install the Python package (snapshot, not editable) via whichever
#    backend is available — cli-hub reinstall/uninstall re-run this script,
#    which re-detects the backend (never a hardcoded one).
echo "  → Installing Python package …"
cd "$REPO_DIR"
if command -v uv &>/dev/null; then
    uv tool install --force .
elif command -v pipx &>/dev/null; then
    pipx install --force .
fi

# 2b. Write install receipt: SHA-256 over source *.py (relative paths + bytes,
# truncated to 12 hex chars). `<tool> doctor` compares this against the live
# tree and reports stale installs. Keep the hashing identical in both places.
python3 -c "
import hashlib, json, datetime
from pathlib import Path
pkg = Path('.') / '${PKG_DIR}'
d = hashlib.sha256()
for f in sorted(pkg.rglob('*.py')):
    if '.venv' in f.parts:
        continue
    d.update(f.relative_to(pkg).as_posix().encode())
    d.update(f.read_bytes())
receipt = Path.home() / '.local' / 'share' / '${TOOL}' / 'install-receipt.json'
receipt.parent.mkdir(parents=True, exist_ok=True)
receipt.write_text(json.dumps({'source_hash': d.hexdigest()[:12], 'installed_at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'), 'source_dir': str(Path('.').resolve())}, indent=2))
print('  → install receipt:', d.hexdigest()[:12])
"

# 3. Create share directory for logs/data.
mkdir -p "$SHARE_DIR"

# 4. Verify installation (including staleness self-check).
echo "  → Verifying …"
if command -v "$TOOL" &>/dev/null; then
    echo "  ✔ ${TOOL} is now available."
    "$TOOL" --version
    "$TOOL" doctor || echo "  ! doctor reports stale/missing receipt (see above)."
else
    echo "  ✗ ${TOOL} not found in PATH after install."
    echo "    Ensure ~/.local/bin is in your PATH, then re-login or:"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# 5. Tool-specific extras (cron, systemd, completions) go here.
#    Example — per-harness cron (harness-model-sync):
#    "$TOOL" install-cron --schedule="$SCHEDULE" --harness=all

echo ""
echo "==> Done."
echo ""
echo "Quick start:"
echo "  ${TOOL} --help"
echo "  ${TOOL} doctor                               # verify install is in sync"
echo ""
echo "Uninstall:"
echo "  ${REPO_DIR}/uninstall.sh"

# 6. Register with cli-hub (best-effort; never fail the install).
if command -v cli-hub &>/dev/null; then
    REPO_URL="$(git -C "$REPO_DIR" remote get-url origin 2>/dev/null || true)"
    VERSION="$("$TOOL" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
    cli-hub register "$TOOL" \
        --version "${VERSION:-0.1.0}" \
        --description "<one-line description>" \
        --group "<group: git|media|db|net|meta|misc>" \
        --source-path "$REPO_DIR" \
        ${REPO_URL:+--repo "$REPO_URL"} \
        --config-path "${HOME}/.config/${TOOL}" \
        --uninstall "${REPO_DIR}/uninstall.sh" \
        --reinstall "${REPO_DIR}/install.sh" \
        --yes || true
fi
