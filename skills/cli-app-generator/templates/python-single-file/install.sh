#!/usr/bin/env bash
# install.sh — symlink <tool> into ~/.local/bin (DECISIONS row C: no copy, no receipt, no
# stale-guard; the link always runs this source, a moved file fails loudly with exit 127). Idempotent.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL="<tool>"
BIN="${HOME}/.local/bin/${TOOL}"
mkdir -p "${HOME}/.local/bin"
chmod +x "${DIR}/tool.py" # symlink target must be executable itself
ln -sfn "${DIR}/tool.py" "${BIN}"
echo "==> ${TOOL} installed: ${BIN} -> ${DIR}/tool.py (edits apply immediately)"
"${BIN}" --version >/dev/null 2>&1 || echo "  ! ${TOOL} --version failed; ensure uv is on PATH" >&2
command -v "${TOOL}" >/dev/null 2>&1 || echo "  ! ${TOOL} not on PATH: export PATH=\"\${HOME}/.local/bin:\${PATH}\"" >&2
# Register with cli-hub (best-effort; hub absence never fails the install).
if command -v cli-hub >/dev/null 2>&1; then
    cli-hub register "${TOOL}" --version "$("${BIN}" --version 2>/dev/null | awk '{print $2}')" \
        --description "<one-line description>" --source-path "${DIR}/tool.py" \
        --uninstall "${DIR}/uninstall.sh" --reinstall "${DIR}/install.sh" --yes || true
fi
