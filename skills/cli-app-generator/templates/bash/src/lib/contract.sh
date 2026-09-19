# shellcheck shell=bash disable=SC2154  # contract helpers (§4.1); args[] is injected by bashly at runtime
fail() {                # fail EXIT MESSAGE HINT — envelope on stderr; one-liner on a TTY
  local code=$1 msg=$2 hint=$3 slug=error
  case $code in 2) slug=usage ;; 3) slug=network ;; 4) slug=partial ;; esac
  if [ -t 2 ]; then
    printf '%s: %s\nhint: %s\n' "$slug" "$msg" "$hint" >&2
  else
    jq -cn --arg s "$slug" --arg m "$msg" --arg h "$hint" \
      '{error:{code:$s,message:$m,hint:$h}}' >&2
  fi
  exit "$code"
}
emit_table() {          # TSV on stdin → aligned via column (tab fallback)
  column -t -s $'\t' 2>/dev/null || cat
}
