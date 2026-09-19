# shellcheck shell=bash  # unknown command → contract envelope (exit 2); add new commands to the whitelist below
case "${command_line_args[0]:-}" in
'' | -* | show | delete | completions) ;;
*) fail 2 "unknown command: ${command_line_args[0]}" "try --help" ;;
esac
command -v jq >/dev/null || fail 1 "jq is required" "install jq (the generated tool needs bash >=4.2 + jq)"
