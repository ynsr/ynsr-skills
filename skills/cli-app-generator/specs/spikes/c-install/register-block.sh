# ── Register with cli-hub (best-effort; never fails the install) ─────────────
# Frozen call shape; repo/config-path omitted on purpose: `refresh_entry`
# derives repo from the git remote of --source-path and config-path from
# ~/.config/<name>; installed_path resolves from PATH. Editable hooks make
# reinstall a ~0.2s metadata swap and uninstall a clean `uv tool uninstall`.
if command -v cli-hub &>/dev/null; then
    cli-hub register "$TOOL" \
        --version "$("$TOOL" --version 2>/dev/null | grep -m1 -oE '[0-9]+(\.[0-9]+)+')" \
        --description "<one-line description>" \
        --group "<group: git|media|db|net|meta|misc>" \
        --source-path "$REPO_DIR" \
        --uninstall "uv tool uninstall $TOOL" \
        --reinstall "uv tool install --editable $REPO_DIR" \
        --yes || true
fi
