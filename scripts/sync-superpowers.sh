#!/usr/bin/env bash
set -euo pipefail

# sync-superpowers.sh — Download the latest Superpowers skills, copy the
# archive's `skills` folder into this repo's skills/ dir (overwriting any
# existing files), and add `author: superpowers` to the YAML frontmatter of
# ONLY the Superpowers skills (paths that exist in the downloaded archive).
# Repo-native skills not present in the archive are left untouched.
#
# Usage: scripts/sync-superpowers.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEST="$REPO_ROOT/skills"
URL="https://github.com/obra/superpowers/archive/refs/heads/main.zip"
AUTHOR="superpowers"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Downloading $URL ..."
curl -fsSL "$URL" -o "$TMP/superpowers.zip"

echo "Unzipping ..."
unzip -q "$TMP/superpowers.zip" -d "$TMP/unpack"

SRC="$TMP/unpack/superpowers-main/skills"
if [[ ! -d "$SRC" ]]; then
  echo "error: skills folder not found in archive" >&2
  exit 1
fi

echo "Copying skills into $DEST (overwriting existing) ..."
mkdir -p "$DEST"
cp -R "$SRC/." "$DEST/"

echo "Adding 'author: $AUTHOR' to frontmatter of Superpowers skills ..."
patched=0
skipped=0
while IFS= read -r -d '' rel; do
  f="$DEST/$rel"
  # Only files with a YAML frontmatter block
  if [[ "$(head -n 1 "$f")" == "---" ]]; then
    if grep -q "^author:" "$f"; then
      sed -i "s/^author:.*/author: $AUTHOR/" "$f"
    else
      sed -i "1a author: $AUTHOR" "$f"
    fi
    patched=$((patched + 1))
  else
    skipped=$((skipped + 1))
    echo "warning: no frontmatter in $rel" >&2
  fi
done < <(cd "$SRC" && find . -name 'SKILL.md' -type f -printf '%P\0')

echo "Done. Copied archive skills; patched $patched SKILL.md file(s), skipped $skipped (no frontmatter)."
