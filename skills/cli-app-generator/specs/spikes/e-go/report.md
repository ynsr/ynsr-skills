# SPIKE E — Go stack: cobra+fang, huh, table lib, retryablehttp

Date: 2026-09-20 · Scratch: `specs/spikes/e-go/` (probe module `src/`, outputs `evidence/`) · Go toolchain used: **1.27.1 user-local** (pre-approved upgrade; base install was 1.22.5).

## 1. What I ran

### Go install (user-local, no sudo)
```bash
curl -sL https://go.dev/dl/?mode=json | jq -r '.[0].version'            # -> go1.27.1
curl -sLO https://go.dev/dl/go1.27.1.linux-amd64.tar.gz                 # 47.3 s
echo 63d339f0da5ab53635a56f2490a7984dfe12dfcff22ad749f63edaf590168445 go1.27.1.linux-amd64.tar.gz | sha256sum -c -
mkdir -p ~/.local && tar -C ~/.local -xzf go1.27.1.linux-amd64.tar.gz   # 0.75 s
export PATH=~/.local/go/bin:$PATH && go version                          # go1.27.1 linux/amd64
```
Why the upgrade: `fang v2.0.1` go.mod says `go 1.25.0`, `huh v2.0.3` says `go 1.25.8`, `lipgloss v2.0.6` says `go 1.25.0`. Installed 1.22.5 cannot build them. Total install effort: ~48 s download+extract, zero conflicts (isolated in `~/.local/go`, PATH override only in spike shell).

### Module pin (src/go.mod, all `go mod tidy`-clean)
```
charm.land/fang/v2 v2.0.1 · charm.land/huh/v2 v2.0.3 · charm.land/lipgloss/v2 v2.0.6
github.com/hashicorp/go-retryablehttp v0.7.8 · github.com/jedib0t/go-pretty/v6 v6.8.3 · github.com/spf13/cobra v1.10.2
```
Probes: `cmd/demo-fang`, `cmd/demo-huh`, `cmd/demo-gopretty`, `cmd/demo-lipgloss`, `cmd/demo-retry`. All build (`go build ./...`) and run.

### Library verification (checked on proxy.golang.org + GitHub API, 2026-09-20)

| Library | Latest | Released | Age | License | go.mod req | Maintained (pushed) | Verdict vs criteria |
|---|---|---|---|---|---|---|---|
| charmbracelet/fang | v2.0.1 (charm.land/fang/v2) | 2026-03-11 | 6.3 mo | MIT | **1.25.0** | 2026-05-04, 24 open issues | PASS (self-described experimental — see concerns) |
| charmbracelet/huh | v2.0.3 (charm.land/huh/v2) | 2026-03-10 | 6.3 mo | MIT | **1.25.8** | 2026-09-01, 7168 stars | PASS (wrapper rules required) |
| charmbracelet/lipgloss | v2.0.6 | 2026-08-11 | 5.7 wk | MIT | 1.25.0 | 2026-09-13 | PASS (already transitively present via fang) |
| jedib0t/go-pretty | v6.8.3 | 2026-07-19 | 2 mo | MIT | **1.18** | 2026-09-18 (yesterday) | PASS |
| hashicorp/go-retryablehttp | v0.7.8 | 2025-06-18 | **15 mo** | MPL-2.0 | 1.23 | 2026-05-11 | **FAILS release-age** criterion |
| golangci-lint | v2.13.2 | 2026-08-27 | 3.4 wk | GPL-3.0 (dev tool only, never linked into generated apps) | — | active | PASS |
| spf13/cobra | v1.10.2 | 2025-12-03 | 9.5 mo | Apache-2.0 | 1.16 | active | PASS |

fang README stability quote (main branch, fetched 2026-09-20): *"The CLI starter kit. **A small, experimental library** for batteries-included [Cobra] applications."* — the experimental label is confirmed on the v2 line too (pkg.go.dev/charm.land/fang/v2 synopsis).

## 2. Observed evidence

### 2.1 fang (cobra wrapped): demo-fang

- **--help rendering** (TTY-quality, stdout, exit 0):
```
  A probe binary for the Go CLI stack spike. Emits sample rows.
  USAGE
    demo-fang [command] [--flags]
  COMMANDS
    completion [command]  Generate the autocompletion script for the specified shell
    get                   Fetch sample items
    help [command]        Help about any command
  FLAGS
    --dry-run             Show what would run, change nothing
    -h --help             Help for demo-fang
    --json                Shorthand for --output json
    -o --output           Output format (table|json|csv|tsv) (table)
    -v --verbose          Increase verbosity (repeatable)
    --version             Version for demo-fang
    -y --yes              Assume yes; skip confirmation prompts
```
Significantly better than stock cobra: grouped COMMANDS/FLAGS sections, defaults in parens, merged short/long flags.

- **NO_COLOR=1 TERM=dumb → zero ANSI**: `grep -cP '\x1b\[' help_nocolor.out` → `0`. Also `0` for piped help and piped error output (fang's colorprofile auto-detects non-TTY and downgrades to plain). Full contract: colorprofile env handling is built in.
- **Non-TTY never blocks**: `timeout 5 ./demo-fang --help </dev/null` → exit 0 immediately; `timeout 5 ./demo-fang get -o json </dev/null` → `{"items":["alpha","beta","gamma"]}`, exit 0.
- **Errors**: `./demo-fang get -o bogus` → styled `ERROR` block on **stderr**, stdout empty (0 bytes), exit 1. Unknown flag/unknown command: same, exit 1 (`Unknown flag: --bogus.`). Note: fang renders a *human* error card, not the contract's `{"error":{...}}` JSON envelope — the envelope needs a custom path via `fang.WithErrorHandler(handler ErrorHandler)` (fang.go:95) or plain cobra error handling. Mapping beyond 0/1 (contract codes 2/3/4) is caller responsibility either way.
- **Extras out of the box**: `--version` (from build info: `demo-fang version unknown (built from source)`; settable via ldflags), hidden `man` command (generated 89-line roff page), `completion` command emitting the framework-generated cobra bash V2 script (426 lines, `# bash completion V2 for demo-fang`). ble.sh-safety of that script is spike D's territory — handoff noted.

### 2.2 huh v2 picker: demo-huh

Behavior matrix (probe: `huh.NewForm(NewGroup(NewSelect[string]()))`, `HUH_STDERR=1` adds `form.WithOutput(os.Stderr)`):

| Condition | Behavior observed |
|---|---|
| TTY (script pty), Enter | Full TUI, exit 0, selection printed: `table` |
| TTY, Ctrl-C | Exit 130, stderr `picker: aborted by user`; raw-mode restore sequences seen at exit (`^[[?25h`, `^[[?2004l`, modifyOtherKeys reset) — no hang, no garble |
| stdin `</dev/null`, TERM≠dumb | **Fails fast, non-blocking**: `picker: huh: bubbletea: error opening TTY: bubbletea: could not open TTY: open /dev/tty: no such device or address`, exit 1, stderr only |
| stdin `</dev/null`, TERM=dumb | Auto-falls-back to accessible mode, **silently selects the first option on EOF, exit 0** — `table` printed as if chosen. Prompt written with ANSI to **stdout** |
| NO_COLOR=1 (+TERM=dumb), accessible | **ANSI still emitted**: `^[[1;38;2;90;86;224mPick an output format^[[m` on stdout — NO_COLOR ignored in accessible mode |

Source facts backing the matrix: huh v2 `NewForm` **defaults TUI output to `tea.WithOutput(os.Stderr)`** (form.go:118-120 — contract-compliant), but accessible mode writes to `cmp.Or[io.Writer](f.output, os.Stdout)` (form.go:675) — stdout, inconsistent with TUI mode; and `if os.Getenv("TERM") == "dumb" { f.WithAccessible(true) }` (form.go:131-134).

**Adopt-with-wrapper verdict.** Template Go layer must: (1) always `WithOutput(os.Stderr)`; (2) isatty(stdin) guard before invoking huh — never rely on its own non-TTY fallback, because TERM=dumb + EOF silently auto-picks the first option (contract violation: "fail with actionable message"); (3) on `NO_COLOR` pass `huh.ThemeBase(dark)` to defuse the accessible-mode ANSI gap; (4) map `huh.ErrUserAborted` → 130. The three TTY requirements (renders, returns on non-TTY, Ctrl-C restore) all pass; the two contract gaps are caller-fixable, one line each.

### 2.3 Table head-to-head (same 5×3 dataset from one `[]Item` struct)

**go-pretty emission (17 non-blank lines) — table+CSV from ONE writer, JSON stdlib** (go-pretty v6.8.3 ships **no json package**: verified by zip listing — only `list/`, `progress/`, `table/`, `text/`; the `Writer` interface has `Render/RenderCSV/RenderTSV/RenderHTML/RenderMarkdown` from one definition, writer.go:8-46):
```go
w := table.NewWriter()
w.AppendHeader(table.Row{"NAME", "COUNT", "STATUS"})
rows := make([]table.Row, len(items))
for i, it := range items { rows[i] = table.Row{it.Name, it.Count, it.Status} }
w.AppendRows(rows)
w.SetStyle(table.StyleLight)
fmt.Print(w.Render())    // ASCII box table
fmt.Print(w.RenderCSV()) // RFC 4180-escaped CSV, header included
b, err := json.Marshal(items)          // JSON = stdlib from the same slice
os.Stdout.WriteString(string(b) + "\n")
```
**lipgloss emission (20 non-blank lines) — table only; CSV manual, JSON stdlib:**
```go
rows := make([][]string, len(items))              // conversion shared by table+csv
for i, it := range items { rows[i] = []string{it.Name, fmt.Sprint(it.Count), it.Status} }
t := table.New().Headers("NAME", "COUNT", "STATUS").Rows(rows...)
fmt.Println(t.Render())
w := csv.NewWriter(os.Stdout)                     // manual CSV
_ = w.Write([]string{"NAME", "COUNT", "STATUS"})
_ = w.WriteAll(rows)
w.Flush()
b, err := json.Marshal(items)                     // JSON = stdlib either way
```
Rendered outputs: both correct, **0 ANSI escapes** in either (`grep -cP` → 0). go-pretty auto right-aligns the COUNT column and auto-escapes CSV quotes per RFC 4180 (render_csv.go); lipgloss left-aligns all and needs manual CSV/TSV (~+4 LOC per extra format). Adding `--output tsv|html|markdown` to go-pretty is +1 line each (`w.RenderTSV()` etc.). Binary weight: go-pretty probe 3.13 M stripped < lipgloss probe 4.33 M — go-pretty is not heavier. **Winner by least code: go-pretty.**

### 2.4 retryablehttp on flaky handler (500, 500, 200), RetryMax=2

```
=== STDOUT (data only) ===
status=200 attempts=3 body="payload"
=== STDERR (slog on stderr) ===
level=INFO  msg="starting flaky fetch" url=http://127.0.0.1:38409
level=DEBUG msg="performing request" method=GET url=http://127.0.0.1:38409
level=DEBUG msg="retrying request" request="GET http://127.0.0.1:38409 (status: 500)" timeout=10ms remaining=2
level=DEBUG msg="retrying request" request="GET http://127.0.0.1:38409 (status: 500)" timeout=20ms remaining=1
```
3 attempts proven, exponential backoff (10ms → 20ms) proven, retry+app logs routed to stderr while stdout stays data-only. The slog bridge must implement `LeveledLogger` (`Error/Info/Warn/Debug(msg, kvs...)` — client.go:350-355); passing a mismatched adapter **panics** (`panic: invalid logger type passed, must be Logger or LeveledLogger`) — the type switch is deliberate. Bridge is 4 one-line methods.

### 2.4b The adopted alternative: own retry helper (src/cmd/demo-retryown/httpx.go, 36 LOC)

`httpx.go` implements `RetryClient{HTTP, RetryMax, WaitMin, WaitMax, Logger *slog.Logger}` with `Do(req)` retrying transport errors and 5xx via `WaitMin * 2^attempt` capped at `WaitMax`, replaying bodies through `req.GetBody` (GET/HEAD/replayable requests), logging retry decisions at debug to the injected stderr slog logger. Same flaky-handler run (500, 500, 200):

```
=== STDOUT (data only) ===
status=200 attempts=3 body="payload"
=== STDERR (slog) ===
level=INFO  msg="starting flaky fetch" url=http://127.0.0.1:43937
level=DEBUG msg="retrying request" status=500 timeout=10ms remaining=2
level=DEBUG msg="retrying request" status=500 timeout=20ms remaining=1
```
Identical observable behavior to retryablehttp's probe (3 attempts, 10ms→20ms backoff progression — real elapsed: +11ms then ~+21ms per stderr timestamps, response body received, retry+app logs stderr-only, 0 ANSI in both streams). LOC: **36** non-blank non-comment lines, zero external deps (stdlib `net/http`, `log/slog`, `math`, `time`). Known limits, stated honestly: no per-host transport pooling tuning (uses caller's `*http.Client`), no retry-on-429/Retry-After, no error-classification beyond transport-vs-5xx, no metrics hooks — sufficient for template scope (GET/JSON calls with backoff); if exotic needs appear, retryablehttp (proven in §2.4, 15-mo-old release caveat) is the documented fallback.

### 2.5 Build/size (importtime-equivalent) + lint

- Cold full-module build (all 5 probes, empty cache, 12-core): **4.9 s** wall. Warm rebuild: 0.35 s.
- Stripped sizes (`-ldflags="-s -w"`): demo-fang (cobra+fang) **4.52 M**; demo-huh 4.71 M; demo-gopretty 3.13 M; demo-lipgloss 4.33 M; demo-retry (net/http+retry) 7.58 M. Unstripped fang demo: 6.55 M.
- `golangci-lint run ./...` (v2.13.2, defaults): 3 errcheck findings on throwaway probe code, **1.6 s** run. Install: `curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/HEAD/install.sh | sh -s -- -b ~/.local/bin v2.13.2` — **15.8 s**, user-local, no sudo. Built with go1.27.0 — matches toolchain.

## 3. DECISIONS row

| E — Go stack (cobra+fang, huh, table lib, retry, lint) | Adopt cobra v1.10.2 + fang v2.0.1 (help/errors/version/completion/man), huh v2.0.3 for pickers behind a template wrapper (WithOutput(stderr) + isatty guard + NO_COLOR→ThemeBase + abort→130), go-pretty v6.8.3 for table/CSV/TSV emission (JSON stdlib), own 36-LOC retry helper PROVEN on the flaky-handler probe (not retryablehttp), golangci-lint v2.13.2 as dev lint | fang delivers contract-relevant behavior verbatim (NO_COLOR clean, non-TTY non-blocking, styled stderr errors, exit 1, framework completions); huh TUI defaults to stderr and restores terminal on Ctrl-C (e2e under pty); go-pretty renders table+CSV+TSV from one writer (17 vs 20 LOC, auto-alignment, RFC4180 escaping, smaller binary); own helper reproduces retryablehttp's proven behavior exactly — 3 attempts, 10→20ms backoff, stderr-only logs, data-only stdout — in 36 stdlib LOC with zero deps; Go upgrade to 1.27.1 is a 48-s user-local tarball | retryablehttp rejected: latest release v0.7.8 is 15 mo old (2025-06-18) — fails binding ≤12-mo criterion; tradeoff accepted: battle-tested-but-stale vs fresh-but-now-proven 36-LOC helper (retryablehttp stays the documented fallback if exotic retry needs appear: 429/Retry-After, custom backoff, metrics); lipgloss/table rejected as table emitter: table-only, manual CSV/TSV (+4 LOC per format), no alignment; plain-cobra-with-tiny-error-styling kept as documented fallback if fang's experimental churn bites (one-function swap) | specs/spikes/e-go/evidence/* (help.out, help_nocolor.out, err.err, huh_*.txt/out, gopretty.out, lipgloss.out, retry.out/err, retryown.out/err, fang.man), src/go.mod, src/cmd/*/main.go |

**Go tier criterion (widened: daemon/background service OR single static binary for servers/jump hosts): stands.** Static binaries confirmed (CGO off trivially, 3–8 M stripped), toolchain upgrade is trivial and user-local, and the whole probe built+ran on a 4.9-s cold build. Keep the widened tier.

## 4. Concerns

1. **fang is self-declared experimental** and already broke API once (v0.x → v2.0.1 vanity move to `charm.land/fang/v2`). Mitigation: pin, and the cobra-alone fallback is a one-function swap (`fang.Execute` → `cmd.Execute` + small error styler); document it in the template.
2. **huh silent-selection footgun**: TERM=dumb + closed stdin → accessible mode silently selects the first option, exit 0. The template's isatty guard is *mandatory*, not optional.
3. **huh accessible mode ignores NO_COLOR** (truecolor ANSI to stdout even with NO_COLOR=1). Wrapper passes `huh.ThemeBase` when NO_COLOR; worth an upstream issue.
4. **fang error output is human-styled, not the contract's JSON envelope** on stderr; agents-mode needs `WithErrorHandler` customization in the template. Exit codes beyond 0/1 (2/3/4) are caller-mapped.
5. **go-pretty dropped its csv/ and json/ subpackages** in the 6.7–6.8 cycle (only `table.RenderCSV/RenderTSV/HTML/Markdown` remain; `json/` is gone entirely). Spike premise "go-pretty does table+csv+json" is outdated — JSON is stdlib for every option; decision unaffected.
6. golangci-lint is GPL-3.0 — fine as a build-time tool; never linked into generated apps.
7. Duplicate `go get` background job hit a transient TLS timeout on first cobra download; re-ran in foreground successfully. One-time, no impact on pins.

## Fix report (review follow-up)

**Critical addressed:** the DECISIONS row previously adopted an unproven "own ~30-LOC retry helper". The helper is now written, run, and proven — decision stands.

Commands (from `specs/spikes/e-go/`):
```bash
# helper file: src/cmd/demo-retryown/httpx.go (RetryClient: transport+5xx retry,
# WaitMin*2^attempt capped at WaitMax, GetBody replay, slog debug logging)
export PATH=~/.local/go/bin:$PATH
cd src && go build -o ../evidence/demo-retryown ./cmd/demo-retryown && cd ../evidence
./demo-retryown > retryown.out 2> retryown.err; echo "exit=$?"      # exit=0
cat retryown.out                                                    # stdout, data only
cat retryown.err                                                    # slog on stderr
grep -cP '\x1b\[' retryown.out retryown.err                         # 0 and 0
grep -cv '^\s*$\|^\s*//' ../src/cmd/demo-retryown/httpx.go          # 36 (LOC)
```
Observed (quoted from `evidence/retryown.out` / `retryown.err`):
```
status=200 attempts=3 body="payload"
level=INFO  msg="starting flaky fetch" url=http://127.0.0.1:43937
level=DEBUG msg="retrying request" status=500 timeout=10ms remaining=2
level=DEBUG msg="retrying request" status=500 timeout=20ms remaining=1
```
Verdict: 3 attempts (initial + 2 retries), exponential backoff 10ms→20ms (stderr timestamps show +11ms then ~+21ms real elapsed), response received, all logs on stderr, stdout data-only with zero ANSI — byte-for-byte the same contract surface the retryablehttp probe (§2.4) demonstrated. The DECISIONS row now cites `retryown.out/err`; §2.4b documents limits (no 429/Retry-After handling, no metrics hooks) and keeps retryablehttp as the documented fallback.

One build note: the helper was first written at module root (`src/httpx.go`, package main) and failed to build from `cmd/demo-retryown` (`undefined: RetryClient`); moved into `src/cmd/demo-retryown/httpx.go`, no behavior change.
