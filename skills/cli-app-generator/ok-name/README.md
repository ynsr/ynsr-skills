# ok-name — Go tier skeleton (cobra + fang + go-pretty)

Single static binary CLI skeleton: wire real commands onto `main.go`'s shape. Runtime deps: none.

    ./install.sh                       # go build → ~/.local/bin/ok-name (+ cli-hub register)
    ./check.sh                         # golangci-lint + go test + verify-cli
    ok-name list [-o json|csv|tsv]      # ok-name rows; URL arg → fetch via retry helper (errors → exit 3)
    ok-name delete f.txt --dry-run      # plan → stdout; add --yes to execute (refuses = exit 2; never prompts)
    ok-name profile create https://api.example.com/v1
                                       # 0600 JSON store (token from OK_NAME_TOKEN env); list honors --output
    ok-name list                     # no URL arg → uses the default profile (URL + Bearer token)

Contract: stdout data-only · `{"error":{code,message,hint}}` on stderr · exit codes in `--help` ·
never blocks · NO_COLOR + `--no-color` (output is plain by construction) · `--version`/`-v`, `-q`.

- Retry: `httpx.go` (own 36-LOC helper per DECISIONS row E; swap to retryablehttp v0.7.8 if you
  need 429/Retry-After or metrics hooks). Tables use go-pretty's ASCII StyleDefault — box-drawing
  styles would taint stdout.
- huh picker deliberately omitted; wrapper recipe (WithOutput(stderr) + isatty + NO_COLOR→ThemeBase
  + abort→130) is documented in templates/python-single-file/README.md if a tool needs one.
