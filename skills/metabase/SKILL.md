---
name: metabase  
description: Query/manage Metabase via mbapi CLI for BI and data analysis.
---

# Metabase CLI (mbapi)

`mbapi` — session-authenticated Metabase CLI for instances without API keys or admin access.
Source: `~/projects/personal/metabase-api-cli` (repo `ynsr/metabase-api-cli`), installed at `~/.local/bin/mbapi`.

## How it works

- `POST /api/session` with `{username, password}` → session token, cached per-URL in `~/.config/mbapi/credentials.json` (0600).
- All calls send `X-Metabase-Session: <token>`; on 401 with `MB_PASS` set it auto re-logins, else exits 5.
- Destructive methods (POST/PUT/PATCH/DELETE) need `--yes`.
- Exit codes: 0 ok / 2 usage / 3 network / 4 HTTP>=400 / 5 auth.

## Auth (one-time, interactive — never ask for the password in chat)

```sh
mbapi login    # prompts, or MB_USER/MB_PASS env
mbapi status   # verify
```

## Commands

```sh
mbapi whoami
mbapi get /api/database                        # list DBs
mbapi get /api/collection                      # collections
mbapi get '/api/card/42/query/json'            # run saved question
mbapi get '/api/database/1/metadata'           # DB schema
mbapi api GET /api/anything                    # passthrough
mbapi api POST /api/dataset --yes --data '{"database":1,"type":"native","native":{"query":"SELECT 1"}}'
```

`--json` = single-line JSON on stdout; `--url` overrides target (default `$MB_URL`).

- clio.jibit.cloud runs Metabase v0.52; official `mb` CLI unusable there (needs API key or v63+).
- Native SQL via `POST /api/dataset` → response `data.rows` / `data.cols`.
- **Int64 precision: wrap big IDs server-side with `toString()`** (`SELECT toString(id) ...`). Metabase middleware coerces large Int64 to float in JSON (`js-int-to-string`), so raw `id` arrives as `1.015...e+18` and is unjoinable. Affects ClickHouse Int64 keys (e.g. `purchase_dist.id`); also applies to Nullable(UUID) like `terminal_id` when exact text is needed.
- Tests: `python3 -m pytest -q` in the repo; live e2e `MBAPI_E2E=1 pytest -k e2e`.
