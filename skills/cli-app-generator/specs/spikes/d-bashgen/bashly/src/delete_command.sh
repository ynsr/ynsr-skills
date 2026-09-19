if [[ ${args[--dry-run]} == 1 ]]; then
  echo "Would delete: ${args[file]}" >&2
  exit 0
fi
if [[ ${args[--yes]} != 1 ]]; then
  echo "Refusing to delete without --yes (non-interactive contract)" >&2
  exit 3
fi
rm -f "${args[file]}" && echo "Deleted: ${args[file]}" >&2
