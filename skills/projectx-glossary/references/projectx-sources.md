# ProjectX Sources — details

## REST & NATS Swagger
Raw YAML, fetch directly.
- REST: `components.schemas` = candidate DTOs; each property's `description` = grounding for `definition_en`. Endpoint `summary`/`description` = source for flow-level terms with no single field.
- NATS: same shape, per request-reply subject. Treat as a sync call (request+response DTO), not an event. Subject name itself is a candidate term (e.g. `ppg.v3.settlement.complete`).

## Prose docs
Fetch as rendered HTML/text.
- Flow descriptions → terms with no single code location.
- Error codes → one row each (`term`=code/name, `definition_en`=documented meaning, cross-ref matching Java exception/enum if any).
- Call examples → grounding context only, not their own rows.

## db-schema.md
Parse like migration comments (base skill Step 3 category 4). On jOOQ disagreement, jOOQ wins — `[SCHEMA-DOC-DRIFT]` rule in SKILL.md.

## Dedup across REST/NATS/prose
1. Extract per-source candidates first, don't interleave.
2. Group by normalized term name (same normalization as the base skill's Step 5).
3. Apply REST > NATS > prose only on actual conflicts; union `code_refs` regardless.
4. Same name, genuinely different things → keep separate rows, cross-ref via `do_not_confuse_with`.
