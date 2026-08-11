---
name: glossary-generator
description: >
  Generates/updates/refreshes a business/domain glossary CSV from a repo. Scans code (entities, DTOs, enums, DB tables/columns, API fields) and drafts one docs/glossary/{module}-glossary.csv per service/module, with English + Farsi definitions and aliases. DRAFT only — a human must confirm before downstream tools trust it.
disable-model-invocation: true
user-invocable: true
---

# Glossary Generator

Maps precise code identifiers to the loose business/ops language people use in chat and tickets. One CSV per module. Drafts, does not certify.

## Invocation: manual only
Never run this as a side effect of an unrelated coding/exploration task. Only on an explicit, deliberate request.

## Core rule: code tells you WHAT, not WHAT IT MEANS
Never invent a `definition_fa` or a confident `definition_en` without a real source in the repo (docstring, comment, README, OpenAPI description, migration comment). No source → tag the value, don't leave it blank and don't present it as fact (Step 4).

## Step 1 — Detect stack, load profile
- `pom.xml` / `build.gradle*` → Java/Spring → read `references/java-spring.md`.
- `package.json` → JS/TS; `requirements.txt`/`pyproject.toml` → Python; `go.mod` → Go → generic patterns (Step 3), no dedicated profile yet.
- Anything else → generic patterns only.
- Polyglot repo → scan each subfolder with its own profile.

## Step 2 — Enumerate modules
One module = one Maven/Gradle subproject, or one top-level dir with its own build file/Dockerfile/package.json, or the whole repo if single-service. **One CSV per module — never merge.** Output: `docs/glossary/<module-name>-glossary.csv`.

## Step 3 — Scan candidates (priority order)
1. Domain/entity objects (persisted, has an ID)
2. DTOs / request-response models (crosses a service/API boundary)
3. Enums / status codes
4. DB tables & columns (migrations/schema docs, ORM models)
5. Public API fields (OpenAPI/GraphQL/controller signatures)

Skip: private/internal helpers, test code, build artifacts, framework boilerplate with no business meaning.

**Skip repeated boilerplate fields.** `createdAt`/`modifiedAt`/`version`/etc. appearing identically across many entities → one shared row per module, not one per entity. Exception: a field's meaning genuinely differs from the generic convention on one entity → give that one its own row.

## Status field
Every row gets `status`:
- `active` — used by current, non-deprecated code.
- `deprecated` — in code but marked deprecated (`@Deprecated`, a "legacy"/"do not use" comment).
- `db-only-legacy` — in schema (migrations/db-schema.md) but no code reference. Ops queries these directly via SQL — don't drop them.

Determine by cross-referencing the code scan against the schema source.

## Step 4 — Draft definitions, tagged by grounding
Grounding priority: javadoc/docstring/comment → OpenAPI/Swagger description → README/module doc → commit/migration comment.

- **Found** → `definition_en` = one plain sentence, your own words. `confidence=code-grounded`.
- **Not found** → `definition_en` = best-effort one-sentence guess, prefixed `[INFERRED] `. `confidence=name-only`, `needs_review=yes`.

`definition_fa` — always in Farsi — always `needs_review=yes` regardless of tier:
1. Native Farsi string in the repo maps to this term → use verbatim, untagged, note source in `code_refs`.
2. No native source, `definition_en` is `code-grounded` → machine-translate it from English (`definition_en` content) to Farsi, prefix `[TRANSLATED] `.
3. No grounding at all → best-effort guess for both `definition_en` and `definition_fa`, prefix both `[INFERRED] `.

Every `definition_fa` is one of: native/untagged, `[TRANSLATED]`, or `[INFERRED]` — never untagged unless native.

## Step 5 — Detect collisions
Same `term` (case-insensitive, ignore plurals) in more than one module → add a cross-reference + one-clause disambiguator to `do_not_confuse_with` in both, e.g. `transaction (see psp-agent-x.csv: single outbound PSP call, not full customer payment)`.

## Step 6 — Merge with existing glossary
If the CSV already exists:
- Never overwrite a row where a human set `needs_review=no` — even if code changed. Instead flag `needs_review=yes` with a note like "code changed since last review."
- Add rows for new candidates.
- Code for a row is gone → check the schema (migrations/db-schema.md) first. Still there → `status=db-only-legacy`, don't flag for deletion. Gone from both → `needs_review=yes`, note "not found in code or schema — confirm before deleting." Deletion is always a human decision.

## Step 7 — Write the CSV
Fixed schema — see `references/csv-format.md`. One file per module, `docs/glossary/<module-name>-glossary.csv`.

## Step 8 — Summarize
Report: modules scanned + paths, counts (new/updated/needs_review) per module, collisions found, a reminder that `definition_fa` and any `needs_review=yes` row need human confirmation before downstream tools trust it.

## Updating vs. generating
Same workflow — Step 6 is the primary path when a CSV already exists. Never touch human-reviewed rows.

## Out of scope
- Never present `[TRANSLATED]`/`[INFERRED]` as final.
- Never merge modules into one file.
- Never delete a row without a human decision.
- Skip test files, build output, vendored code (jOOQ exception: see `references/java-spring.md`).
- Never auto-trigger from unrelated requests.
