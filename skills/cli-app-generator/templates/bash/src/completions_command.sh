# shellcheck shell=bash disable=SC2154  # args[] is injected by bashly at runtime
case "${args[shell]:-}" in
'' | bash) send_completions ;;
*) fail 2 "unsupported shell: ${args[shell]}" "completions are bash-only (completely, static single file)" ;;
esac
