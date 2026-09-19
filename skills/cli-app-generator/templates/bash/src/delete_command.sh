# shellcheck shell=bash disable=SC2154  # args[] is injected by bashly at runtime
file=${args[file]}
if [[ ${args[--dry-run]:-} == 1 ]]; then
  printf 'plan: rm %s\n' "$file"    # the plan is data → stdout (contract §4.1.6)
  exit 0
fi
if [[ ${args[--yes]:-} != 1 ]]; then
  fail 2 "refusing to delete without --yes" "append --yes to execute; --dry-run previews the plan"
fi
rm -- "$file" || fail 1 "delete failed: $file" "check permissions"
[[ ${args[--quiet]:-} != 1 ]] && printf 'deleted: %s\n' "$file" >&2
