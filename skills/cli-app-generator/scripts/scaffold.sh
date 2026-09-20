#!/usr/bin/env bash
# scaffold.sh — generate a working tier-specific skeleton (spec §2.5, DECISIONS row F).
#
# One command per tier: parameterizes the template with copier (LOCAL paths, offline,
# deterministic — repeated runs into a fresh destination are byte-identical), then wires
# templates/verify-cli into the result so the project checks itself.
#
# Usage:
#   scripts/scaffold.sh --tier <python-project|python-single-file|bash|go>
#                       --audience <human|agent> --name <tool-name>
#                       [--profiles] [--wizard] [--service] [--dest DIR]
#
# Flag semantics (spec §2.4 add-ons):
#   --profiles  include profile subcommands + 0600 store (python-project, go)
#   --wizard    include the interactive picker behind the stderr wrapper (requires --profiles)
#   --service   include the systemd user-unit subcommands (go tier only)
set -euo pipefail

usage() {
    sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 2
}

TIER="" AUDIENCE="" NAME="" DEST="" PROFILES=false WIZARD=false SERVICE=false
while [ $# -gt 0 ]; do
    case "$1" in
        --tier)     [ $# -ge 2 ] || usage; TIER="$2"; shift 2 ;;
        --audience) [ $# -ge 2 ] || usage; AUDIENCE="$2"; shift 2 ;;
        --name)     [ $# -ge 2 ] || usage; NAME="$2"; shift 2 ;;
        --dest)     [ $# -ge 2 ] || usage; DEST="$2"; shift 2 ;;
        --profiles) PROFILES=true; shift ;;
        --wizard)   WIZARD=true; shift ;;
        --service)  SERVICE=true; shift ;;
        -h|--help)  usage ;;
        *)          echo "scaffold.sh: unknown argument: $1" >&2; usage ;;
    esac
done

[ -n "$TIER" ] && [ -n "$AUDIENCE" ] && [ -n "$NAME" ] || { echo "scaffold.sh: --tier, --audience and --name are required" >&2; usage; }

case "$TIER" in
    python-project|python-single-file|bash|go) ;;
    *) echo "scaffold.sh: unknown tier: $TIER (python-project|python-single-file|bash|go)" >&2; exit 2 ;;
esac
case "$AUDIENCE" in human|agent) ;; *) echo "scaffold.sh: unknown audience: $AUDIENCE (human|agent)" >&2; exit 2 ;;
esac

# Name validation: lowercase identifier-ish everywhere; python tiers are also module names,
# so they additionally reject dashes (entry-point name = package name there).
case "$NAME" in
    *[!a-z0-9_-]* | "" ) echo "scaffold.sh: name must match [a-z][a-z0-9_-]* — got: $NAME" >&2; exit 2 ;;
esac
case "$NAME" in
    *[!a-z0-9_]*)
        case "$TIER" in
            python-*) echo "scaffold.sh: python tier names are module names too — dashes not allowed: $NAME" >&2; exit 2 ;;
        esac ;;
esac

case "$TIER:$WIZARD$SERVICE" in
    *:falsefalse) ;;
    python-project:*|go:*) if $WIZARD && ! $PROFILES; then echo "scaffold.sh: --wizard requires --profiles" >&2; exit 2; fi ;;
    *:true*) echo "scaffold.sh: --wizard/--service need --profiles; add-ons apply to python-project and go tiers only" >&2; exit 2 ;;
esac
if $SERVICE && [ "$TIER" != "go" ]; then
    echo "scaffold.sh: --service is a go-tier-only add-on (spec §2.4)" >&2; exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TPL="$ROOT/templates/$TIER"
[ -d "$TPL" ] || { echo "scaffold.sh: template not found: $TPL" >&2; exit 2; }

: "${DEST:=$NAME}"
if [ -e "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then
    echo "scaffold.sh: destination exists and is not empty: $DEST (scaffold into a fresh path)" >&2
    exit 2
fi

# Local template, offline, pinned — deterministic per DECISIONS row F (copier 9.18.2, spike F).
DATA=(-d "name=$NAME" -d "audience=$AUDIENCE")
$PROFILES && DATA+=(-d profiles=true)
$WIZARD && DATA+=(-d wizard=true)
$SERVICE && DATA+=(-d service=true)

uvx --offline "copier==9.18.2" copy "$TPL" "$DEST" "${DATA[@]}" -f -q

# Wire the universal contract checker into the project (owner decision: verify-cli is
# copied per project so `make check` / check.sh and CI reference a local, stable path).
mkdir -p "$DEST/scripts"
cp "$ROOT/templates/verify-cli" "$DEST/scripts/verify-cli"
chmod 755 "$DEST/scripts/verify-cli"

echo "scaffolded $TIER ($AUDIENCE): $NAME -> $DEST"
case "$TIER" in
    python-project)  echo "next: cd '$DEST' && make check   (uv sync + ruff + pytest + scripts/verify-cli)" ;;
    python-single-file) echo "next: cd '$DEST' && ./check.sh   (spins a throwaway server + scripts/verify-cli)" ;;
    bash)            echo "next: cd '$DEST' && ./check.sh   (bashly generate + shellcheck + bats + scripts/verify-cli)" ;;
    go)              echo "next: cd '$DEST' && ./check.sh   (gofmt/golangci-lint/go vet/test + scripts/verify-cli)" ;;
esac
