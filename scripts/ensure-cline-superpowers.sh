#!/usr/bin/env bash
set -euo pipefail
# ensure-cline-superpowers.sh — ensure using-superpowers skill has Cline support
# Canonical source lives in this repo: .agents/skills/using-superpowers/
# Fameuse places (where `npx skills --agent cline` / `cline skill add` installs):
#   - Global:  ~/.agents/skills/using-superpowers
#   - Project: <workspace>/.agents/skills/using-superpowers  (e.g. ~/dev/agents/hermes/.agents/...)
#   - Legacy:  ~/.cline/skills/using-superpowers
#   - Checkout:/tmp/superpowers/skills/using-superpowers
# If a destination exists but lacks the Cline patch, this script copies the
# canonical SKILL.md + references/cline-tools.md over it (idempotent).
#
# Usage:
#   ensure-cline-superpowers.sh [--check|--fix] [--dry-run] [--verbose] [--yes] [--help]
#   --fix is the default (apply patches). --check only reports.
#   Also runnable via cron (no_agent) and manually.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_SOURCE="$REPO_ROOT/.agents/skills/using-superpowers"

SOURCE="$DEFAULT_SOURCE"
MODE="fix"          # fix | check
DRY_RUN=0
VERBOSE=0
YES=0
QUIET=0
GLOBAL_ONLY=0
PROJECT_ONLY=0
EXTRA_DESTS=()

usage() {
  cat <<'EOF'
ensure-cline-superpowers.sh — patch using-superpowers with Cline support in fameuse places

USAGE:
  ensure-cline-superpowers.sh [OPTIONS]

OPTIONS:
  -h, --help          Show this help and exit
      --check         Only check/report — do not modify any files
      --fix           Apply missing patches (default)
      --dry-run       Show what would be done without writing
  -v, --verbose       Verbose output (list every place checked)
  -y, --yes           Non-interactive (no prompts; default already non-interactive)
      --source PATH   Canonical source dir (default: .agents/skills/using-superpowers in this repo)
      --global-only   Only patch global locations (~/.agents, ~/.cline)
      --project-only  Only patch project workspaces (~/dev, ~/projects)
      --dest PATH     Additionally ensure this destination (may be repeated)
  -q, --quiet         Suppress summary when nothing changed (useful for cron)
      --list          List discovered fameuse places and exit

EXAMPLES:
  ensure-cline-superpowers.sh --help
  ensure-cline-superpowers.sh --check --verbose
  ensure-cline-superpowers.sh --fix
  ensure-cline-superpowers.sh --dry-run --verbose
  ensure-cline-superpowers.sh --dest /tmp/my-workspace/.agents/skills/using-superpowers --fix
  ensure-cline-superpowers.sh --quiet   # cron-friendly: silent when already patched

CRON:
  Installed as an hourly cronjob (no_agent) that runs:
    bash /home/bs/projects/personal/ynsr-skills/scripts/ensure-cline-superpowers.sh --fix
  Run manually any time; safe to re-run (idempotent).

EXIT CODES:
  0  all checked places already patched (or were patched now)
  1  usage error
  2  canonical source missing
  3  one or more check failures (only in --check mode)
EOF
}

LIST_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --check) MODE="check"; shift ;;
    --fix) MODE="fix"; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -q|--quiet) QUIET=1; shift ;;
    -y|--yes) YES=1; shift ;;
    --source) SOURCE="${2:-}"; [[ -n "$SOURCE" ]] || { echo "error: --source requires PATH" >&2; exit 1; }; shift 2 ;;
    --source=*) SOURCE="${1#*=}"; shift ;;
    --global-only) GLOBAL_ONLY=1; shift ;;
    --project-only) PROJECT_ONLY=1; shift ;;
    --dest) EXTRA_DESTS+=("${2:-}"); [[ -n "${EXTRA_DESTS[-1]}" ]] || { echo "error: --dest requires PATH" >&2; exit 1; }; shift 2 ;;
    --dest=*) EXTRA_DESTS+=("${1#*=}"); shift ;;
    --list) LIST_ONLY=1; shift ;;
    --) shift; break ;;
    -*) echo "error: unknown option: $1 (try --help)" >&2; exit 1 ;;
    *) echo "error: unexpected argument: $1 (try --help)" >&2; exit 1 ;;
  esac
done

if [[ $GLOBAL_ONLY -eq 1 && $PROJECT_ONLY -eq 1 ]]; then
  echo "error: --global-only and --project-only are mutually exclusive" >&2; exit 1
fi

if [[ ! -f "$SOURCE/SKILL.md" ]]; then
  echo "error: canonical source missing: $SOURCE/SKILL.md" >&2
  echo "hint: expected repo at $REPO_ROOT — did you move it? Use --source PATH to override." >&2
  exit 2
fi
if [[ ! -f "$SOURCE/references/cline-tools.md" ]]; then
  echo "error: canonical source missing: $SOURCE/references/cline-tools.md" >&2; exit 2
fi

# Discover fameuse places
discover() {
  local -a out=()
  if [[ $PROJECT_ONLY -eq 0 ]]; then
    out+=("$HOME/.agents/skills/using-superpowers")
    out+=("$HOME/.cline/skills/using-superpowers")
    out+=("/tmp/superpowers/skills/using-superpowers")
  fi
  if [[ $GLOBAL_ONLY -eq 0 ]]; then
    for root in "$HOME/dev" "$HOME/projects" "$HOME/work" "$HOME/code"; do
      [[ -d "$root" ]] || continue
      while IFS= read -r d; do
        [[ -n "$d" ]] || continue
        out+=("$d")
      done < <(find "$root" -maxdepth 6 -type d -path "*/.agents/skills/using-superpowers" 2>/dev/null | head -n 60)
    done
  fi
  for d in "${EXTRA_DESTS[@]+"${EXTRA_DESTS[@]}"}"; do [[ -n "$d" ]] || continue; out+=("$d"); done
  # Deduplicate preserving order (avoid associative-array bad subscript on slashy keys under set -u)
  local -a uniq=()
  local d u found
  for d in "${out[@]}"; do
    found=0
    for u in "${uniq[@]}"; do [[ "$u" == "$d" ]] && { found=1; break; }; done
    [[ $found -eq 1 ]] && continue
    uniq+=("$d")
  done
  printf '%s\n' "${uniq[@]}"
}

mapfile -t DESTS < <(discover)

if [[ $LIST_ONLY -eq 1 ]]; then
  echo "Canonical source: $SOURCE"
  echo "Fameuse places (discovered):"
  for d in "${DESTS[@]}"; do
    if [[ -d "$d" ]]; then echo "  [exists] $d"
    else echo "  [absent] $d"; fi
  done
  exit 0
fi

# Check/patch one dest
need_patch() {
  local dest="$1"
  local skill="$dest/SKILL.md"
  local ref="$dest/references/cline-tools.md"
  [[ -f "$skill" ]] || return 2  # not installed here
  if ! grep -q "cline-tools" "$skill" 2>/dev/null; then return 0; fi
  # Also ensure the reference file exists and is non-empty
  if [[ ! -s "$ref" ]]; then return 0; fi
  # Optional: ensure reference matches canonical (if canonical newer, patch)
  if ! cmp -s "$SOURCE/references/cline-tools.md" "$ref" 2>/dev/null; then
    # Only treat as needing patch if canonical is meaningfully different and dest lacks marker
    # For simplicity, if files differ, we still patch (idempotent copy)
    # But don't flag as failure if SKILL.md already has cline line and ref exists — cmp diff is just drift warning
    if [[ $VERBOSE -eq 1 ]]; then return 0; else return 1; fi
  fi
  return 1
}

patched=0
already=0
absent=0
missing=0
failed=0
drift=0

for dest in "${DESTS[@]}"; do
  if [[ ! -d "$dest" ]]; then
    [[ $VERBOSE -eq 1 ]] && echo "[skip:absent] $dest"
    ((absent++)) || true
    continue
  fi
  if [[ ! -f "$dest/SKILL.md" ]]; then
    [[ $VERBOSE -eq 1 ]] && echo "[skip:no-SKILL.md] $dest"
    ((absent++)) || true
    continue
  fi

  has_cline=0
  has_ref=0
  grep -q "cline-tools" "$dest/SKILL.md" 2>/dev/null && has_cline=1 || true
  [[ -s "$dest/references/cline-tools.md" ]] && has_ref=1 || true

  if [[ $has_cline -eq 1 && $has_ref -eq 1 ]]; then
    # Check drift vs canonical (informational)
    if ! cmp -s "$SOURCE/references/cline-tools.md" "$dest/references/cline-tools.md" 2>/dev/null; then
      ((drift++)) || true
      if [[ $VERBOSE -eq 1 ]]; then echo "[drift] $dest (reference differs from canonical — will refresh on --fix)"; fi
      if [[ "$MODE" == "check" ]]; then continue; fi
      # In fix mode, refresh the reference to canonical
      if [[ $DRY_RUN -eq 1 ]]; then
        echo "[dry-run:refresh] $dest/references/cline-tools.md"
      else
        mkdir -p "$dest/references"
        cp "$SOURCE/references/cline-tools.md" "$dest/references/cline-tools.md"
        echo "[refreshed] $dest/references/cline-tools.md"
        ((patched++)) || true
      fi
      ((already++)) || true
    else
      [[ $VERBOSE -eq 1 ]] && echo "[ok] $dest"
      ((already++)) || true
    fi
    continue
  fi

  ((missing++)) || true
  if [[ "$MODE" == "check" ]]; then
    echo "[needs-patch] $dest (SKILL.md cline=$has_cline ref=$has_ref)"
    ((failed++)) || true
    continue
  fi

  # fix mode
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "[dry-run:patch] $dest (would copy SKILL.md + references/cline-tools.md from $SOURCE)"
    ((patched++)) || true
    continue
  fi

  # Ensure Cline line in SKILL.md: if missing, copy canonical SKILL.md (preserves all, adds Cline entry)
  # We copy the canonical SKILL.md wholesale — it's identical except the added Cline Platform Adaptation line.
  # Safer than sed-patching an arbitrary upstream version.
  if [[ $has_cline -eq 0 ]]; then
    cp "$SOURCE/SKILL.md" "$dest/SKILL.md"
    echo "[patched] $dest/SKILL.md"
  fi
  mkdir -p "$dest/references"
  cp "$SOURCE/references/cline-tools.md" "$dest/references/cline-tools.md"
  echo "[patched] $dest/references/cline-tools.md"
  ((patched++)) || true
done

if [[ $QUIET -eq 1 && $patched -eq 0 && $failed -eq 0 && $drift -eq 0 && $DRY_RUN -eq 0 ]]; then
  # cron-friendly silent success — no output when already patched
  exit 0
fi
echo "---"
if [[ $DRY_RUN -eq 1 ]]; then _dry=" (dry-run)"; else _dry=""; fi
echo "Source : $SOURCE"
echo "Mode   : $MODE$_dry"
echo "Scanned: ${#DESTS[@]} fameuse places"
echo "Present & patched: $already | Newly patched/refreshed: $patched | Need-patch (check): $failed | Absent/empty: $absent | Drift refreshed: $drift"

if [[ "$MODE" == "check" && $failed -gt 0 ]]; then
  echo "Result: CHECK FAILED — $failed place(s) need patching. Run with --fix to apply." >&2
  exit 3
fi
exit 0
