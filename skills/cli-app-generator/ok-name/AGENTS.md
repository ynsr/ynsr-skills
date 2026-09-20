# AGENTS.md — ok-name (Go tier skeleton)

Agent guidance for this tool. Contract harness: `scripts/verify-cli`; stack: cobra v1.10.2 + fang v2.0.1 + go-pretty v6.8.3 (DECISIONS rows E-F).

- stdout = data only (slog → stderr; delete --dry-run plan → stdout).
- Errors: return `cerr{code, msg, hint}` from RunE — the fang error handler emits the
  `{"error":{code,message,hint}}` envelope and sets the exit code; usage-shaped strings
  ("unknown command", "unknown flag:", ...) map to code 2 via `codeOf`.
- Keep `emit`/`profileEmit` the only rendering paths; contract flags live on `root.PersistentFlags()` so they
  parse after the subcommand; delete's --dry-run/--yes are command-local.
- `httpx.go` RetryClient retries transport errors + 5xx (WaitMin·2^attempt capped, GetBody replay).
- `go test ./...` covers emit formats, envelope shape, usage-code classification; `./check.sh` runs
  lint + tests + verify-cli.
- Profiles: `profile.go` (0600 JSON store under os.UserConfigDir(); token from env only, masked as
  set/unset in list output; default profile feeds `list` when no URL arg).
