---
name: projectx-glossary
description: >
  Generates/updates/refreshes the ProjectX glossary. Thin layer on top of `glossary-generator`: adds ProjectX's sources (REST/NATS Swagger, prose API docs, docs/agents/db-schema.md) and this project's conflict-precedence rules. Does not reimplement the base workflow — composes with `glossary-generator` by reference.
compatibility: >
  Requires the `glossary-generator` skill installed. This skill only adds ProjectX-specific sources/rules on top of it — not a standalone generator.
disable-model-invocation: true
user-invocable: true
---

# ProjectX Glossary — composition layer

## Step 0 — Run the base skill first
Locate `glossary-generator` (check available skills, or a sibling `glossary-generator/SKILL.md`). Not found → stop, tell the user to install it — don't recreate its workflow inline.

Run its full workflow (Steps 1–8) against this repo with:
- Stack profile: Java/Spring (`references/java-spring.md`). DB is **CockroachDB, not Postgres** — jOOQ's Postgres dialect generally works against it, but for Cockroach-specific schema features (`FAMILY`, hash-sharded indexes, `AS OF SYSTEM TIME`) trust migrations/jOOQ output over generic Postgres assumptions.
- Module: `projectx` (the repo/module name). Other modules still get their own CSV via the base skill's normal scoping.

Everything below is additive to the base skill's Step 3/4 (scanning/grounding) and Step 6 (merge/drift).

## Extra sources
1. REST Swagger (raw YAML): `https://napi.jibit.ir/ppg/v3/static/docs/swagger/swagger.yaml`
2. NATS Swagger (raw YAML): `https://napi.jibit.ir/ppg/v3/static/docs/swagger/nats-swagger.yaml` — request-reply, not async pub/sub; treat each subject as a sync call (request+response DTO).
3. Prose API docs: `https://napi.jibit.ir/ppg/v3/static/docs/index.html`
4. `docs/agents/db-schema.md` — alongside jOOQ-generated code (already schema truth per the base profile).

Both Swagger URLs are raw YAML — fetch and parse directly, no viewer parsing needed. Details: `references/projectx-sources.md`.

## Precedence (only when sources actually disagree on the same field/term)
- REST Swagger > NATS Swagger > prose docs. Only one source has it → use it regardless of rank.
- jOOQ > `db-schema.md`. On disagreement, jOOQ wins for `status`/`code_refs`, but flag it: `[SCHEMA-DOC-DRIFT] db-schema.md says X, jOOQ says Y — db-schema.md may be stale, flag for doc update too.` in `do_not_confuse_with`.
- Same term across REST/NATS/prose → one row, not three. Union all sources into `code_refs`, use only the winning source's text for `definition_en`.
- Same boilerplate-field skip rule as the base skill — applies to repeated API schema fields too.

## Extra candidate category: external-only API fields
Public fields with no internal DTO/entity match (renamed/reshaped for external consumers) → still add as rows. `code_refs` = swagger source only, `confidence=code-grounded`. Note the internal equivalent if the name differs, e.g. `external "referenceId" = internal "trackingCode" (SettlementBatchEntity.trackingCode)`.

## Output
Same schema as the base skill (`csv-format.md`), same `[TRANSLATED]`/`[INFERRED]` tagging. Path: `docs/glossary/projectx-glossary.csv`.
