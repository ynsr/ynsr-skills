json=$(cat "${args[file]}")
printf 'NAME\tVALUE\n'
printf '%s\n' "$json" | jq -r 'to_entries[] | "\(.key)\t\(.value)"'
