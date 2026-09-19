# shellcheck shell=bash disable=SC2154  # args[] is injected by bashly at runtime
if [[ -n ${args[file]:-} ]]; then
  data=$(cat "${args[file]}") || fail 1 "cannot read file: ${args[file]}" "check the path"
else
  data='{"name":"alice","role":"admin","active":true}'   # builtin sample — replace with your data
fi
fmt=${args[--output]:-}
[[ ${args[--json]:-} == 1 ]] && fmt=json
jq -e 'if type == "object" then . else error("not an object") end' <<<"$data" >/dev/null 2>&1 ||
  fail 1 "invalid JSON input" "top-level JSON must be an object"
case $fmt in
json) jq -c 'to_entries' <<<"$data" ;;
csv) printf 'name,value\n'; jq -r 'to_entries[] | [.key, (.value | tostring)] | @csv' <<<"$data" ;;
tsv) printf 'name\tvalue\n'; jq -r 'to_entries[] | [(.key | tostring), (.value | tostring)] | @tsv' <<<"$data" ;;
table) printf 'NAME\tVALUE\n'; jq -r 'to_entries[] | "\(.key)\t\(.value)"' <<<"$data" | emit_table ;;
esac
