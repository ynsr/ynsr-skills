---
name: solr-cli
description: >
  Use when a task involves running Solr queries, facets, updates, deletes-by-query,
  or admin actions through the `solr-cli` tool — or when asked to inspect/fix/review
  Solr integration for tools built on solr-cli. Covers profile resolution, safe
  mutate practices, and wire-format guarantees. For Jibit prd specifics use the
  projectx-solr skill alongside this one.
---

# solr-cli

## Overview

`solr-cli` is a multi-profile HTTP client for Apache Solr Cloud: query, facet,
mutate, administer — JSON to stdout, logs to stderr, destructive ops gated.
Core principle: **resolve the profile, look at the wire before you fire, never
mutate without `--yes`/`--dry-run`.**

**REQUIRED BACKGROUND:** run `solr-cli <command> --help` before first use in a
session — flags and defaults live there, not here. Full config reference:
`docs/CONFIG.md` in the repo (github.com/ynsr/solr-cli).

## Quick Reference

| Task | Command |
|---|---|
| One doc by id | `solr-cli doc <collection> <id>` |
| Search | `solr-cli select <collection> -q '<lucene>' -f id,amount -l 20` |
| Aggregate | `solr-cli facet <collection> --facet '{"byLabel":{"type":"terms","field":"label"}}'` |
| Edit fields | `solr-cli update <collection> <id> --set 'field=value'` |
| Delete by query | `solr-cli delete-by-query <collection> '<query>' --yes` |
| List collections | `solr-cli collections` |
| Schema fields | `solr-cli schema <collection> [--grep substr|/regex/]` |
| Arbitrary call | `solr-cli raw -X <method> <path> [-d '<json>'] [--param k=v]` |

## Profile & Auth

- Profiles live in `~/.config/solr-cli/profiles/<name>.json` (0600). Active
  profile: `--profile NAME` > ephemeral (`SOLR_URL` + auth env vars) >
  `$SOLR_PROFILE` name > `default_profile` from config.json.
- **Non-interactive cookie auth**: `--auth-cookie` prompts (getpass) — feed it
  via stdin, never a flag: `printf '%s\n' "$SOLR_AUTH_COOKIE" | solr-cli
  profile create prd --url https://host --collection orders --default --auth-cookie`.
  Same pattern refreshes: `... | solr-cli profile set prd --auth-cookie`.
- `SOLR_AUTH_COOKIE` (+ `SOLR_URL`) is the **ephemeral profile only** — it is
  NOT read by `profile create/set`; a create without `--auth-cookie` silently
  saves the profile with no auth.
- Cookie is a raw value — sent as `Cookie: <cookie_name>=<value>`, default
  name `authelia_session`. 302/401 from an authed command = cookie expired.
- TLS: per-profile `--no-verify-tls` at `profile create/set` (default verify).
  Scoped to that profile only.
- `donotintercept: true` header is sent by default (proxy bypass, Jibit-style);
  plain-Solr installs may disable with `--no-donotintercept` at profile create/set.

## Safe Mutation Discipline

`update` and `delete-by-query` are destructive and refuse to run non-interactively
without `--yes` (exit 2). The harness should treat this as required:

1. **Always `--dry-run` first** — prints the exact request (JSON or XML) without
   sending. Check collection, query/field values, and the delete query matches
   only intended docs. `delete-by-query` kills by query scope, not single ids —
   `label:PURCHASE` deletes all PURCHASE docs; prefer `id:` scope when possible.
2. **Narrow before wide**: prefer `doc`-scoped `update` over query-scoped
   deletes; on shared collections prefer `--no-commit`/`--commit-within N` when
   batching, single ops commit immediately by default.
3. **Retries are automatic** on 429/5xx/connect errors with exponential backoff
   (defaults `--retries 3`, `--retry-delay 1.0`) — do not wrap solr-cli in extra
   retry loops; and remember deletes/updates can be retried safely (idempotent).
   Selects are always safe to retry.
4. **Never** place a destructive command in loops, cron, or autonomous agent
   runs without an explicit user-approved, pre-dry-run-checked batch list.

## Wire Format Guarantees (for code review / integration)

- select/facet POST to `/solr/<collection>/select?omitHeader=true` with
  `{"query": ..., "fields": [...], "sort": ..., "limit": ...}` (JSON Query API).
- facet always sends `"limit": 0` — response has `facets` (not `response`);
  don't look for docs there.
- update POSTs atomic-update JSON to `/solr/<collection>/update?overwrite=true&commit=true`:
  `[{"id": "X", "field": {"set": value}}]`.
- delete-by-query POSTs XML `<delete><query>...</query></delete>` to
  `/update?commit=true` (Content-Type `text/xml`).
- stdout = response JSON only (pipe-safe into `jq`); all logs to stderr. Exit
  codes: 0 ok · 1 runtime · 2 usage/refusal · 3 network/timeout.

## SolrQL Notes

- Query strings are Solr/Lucene syntax; values with spaces need quotes:
  `solr-cli select orders -q 'label:"PURCHASE AND REFUND"'` is a phrase match
  on one field value, whereas `label:PURCHASE AND state:FINISHED` is boolean.
- **Schema discovery**: `solr-cli schema <collection>` fetches the LIVE schema
  from the server (`/solr/<coll>/admin/file?file=managed-schema`) — always the
  deployed truth, never a local file. Returns only concrete `<field>` elements
  (no dynamicField/fieldType/copyField), as JSON (or `-F xml`). Find a field
  name before writing a query: `solr-cli schema orders --grep track` or
  `/regex/`. Every subcommand's `--help` also carries real Projectx examples.
- Deep pagination: `--set-x` takes `KEY=JSON` (value must be valid JSON, so
  strings need inner quotes): `--set-x 'cursorMark="*"'` + sort by uniqueKey;
  repeat the flag for multiple params (`--set-x 'min_match="75%"'`).
- `raw` passthrough — profile URL+auth applied, path relative to Solr base:
  `solr-cli raw -X POST /solr/orders/update --data-file payload.json --param commit=true`.

## Common Mistakes

- **Reading docs from `response` on a facet call** — facet returns `facets`.
- **Deleting with a bare term query** — `label:PURCHASE` matches every purchase
  ever; add time/id scope or use `doc`-scoped `update`.
- **Assuming profile auth is set** — a profile saved without auth sends no
  cookie; 302/401 means fix the profile, not the request.
- **Socks proxy env** — if the target host must bypass the local proxy, add it
  to `no_proxy`/`NO_PROXY` before invoking solr-cli (httpx honors proxy env).
- **`--json` doesn't exist** — output is already JSON on stdout; logs on stderr
  by design.
- **Exit code 2 ≠ runtime failure** — 2 is usage/refusal (e.g. destructive op
  without `--yes`); 1 is runtime; 3 is network. Map harness behavior accordingly.
