# Glossary CSV Format (fixed — do not deviate)

One file per module: `docs/glossary/<module-name>-glossary.csv` (e.g. `docs/glossary/orders-glossary.csv`)

## Header (exact column order)
```
term,status,code_refs,definition_en,definition_fa,aliases_loose,do_not_confuse_with,confidence,needs_review,last_scanned
```

## Column definitions
| Column | Meaning | Example |
|---|---|---|
| `term` | Canonical business-facing name, lowercase, spaced (not code-cased) | `settlement batch` |
| `status` | `active`, `deprecated` (still in code, marked deprecated), or `db-only-legacy` (in schema, no code reference) — see SKILL.md "Handling deprecated and DB-only fields" | `active` |
| `code_refs` | Semicolon-separated list of exact code/schema locations | `Order;orders (table)` |
| `definition_en` | One plain sentence. Untagged if `code-grounded`; prefixed `[INFERRED] ` if guessed with no grounding (see SKILL.md Step 4). | `A grouped set of confirmed transactions submitted to a PSP for payout in one settlement run.` |
| `definition_fa` | Farsi definition. Untagged if taken verbatim from a native Farsi source in the repo; prefixed `[TRANSLATED] ` if machine-translated from a grounded `definition_en`; prefixed `[INFERRED] ` if guessed with no grounding at all. Never untagged unless it's a native source. | `[TRANSLATED] ...` |
| `aliases_loose` | Semicolon-separated loose terms people actually use (EN and FA mixed, both directions) — leave blank at generation time unless found in code comments/logs; this column is mainly filled by human reviewers over time | `batch;settlement run` |
| `do_not_confuse_with` | Semicolon-separated cross-module collisions detected in Step 5, with a one-clause disambiguator | `order (see orders-core.csv: confirmed purchase; not a money movement)` |
| `confidence` | `code-grounded`, `name-only`, or `human-confirmed` (person confirmed live during a downstream tool, e.g. `bug-issue-generator`) | `code-grounded` |
| `needs_review` | `yes`/`no` — default `yes`; always `yes` for `[TRANSLATED]`/`[INFERRED]`. `human-confirmed` rows may be `no` — the one case a non-human-reviewer may set it. | `yes` |
| `last_scanned` | ISO date this row was generated/updated by the scan | `2026-08-07` |

## Escaping rules (standard CSV, RFC 4180)
- Wrap any field containing a comma, double-quote, or newline in double quotes.
- Escape internal double quotes by doubling them (`"` → `""`).
- Use `;` (semicolon) as the internal separator for multi-value fields (`code_refs`, `aliases_loose`, `do_not_confuse_with`) — never a comma, to avoid ambiguity with CSV's own delimiter.
- UTF-8 encoding, no BOM. This is required for Farsi text to render correctly in any downstream tool (Mattermost agent, spreadsheet, etc.).
- One header row, no blank rows, no trailing commas.

## Example rows
```csv
term,status,code_refs,definition_en,definition_fa,aliases_loose,do_not_confuse_with,confidence,needs_review,last_scanned
order,active,Order;orders (table),A confirmed customer purchase queued for fulfillment.,[TRANSLATED] a Farsi rendering of the English sentence,,,code-grounded,yes,2026-08-07
invoice ledger entry,active,InvoiceLedgerEntry;ledger_entries (table),[INFERRED] Likely records a single financial entry against an order for accounting; based on class name and its place in the ledger package.,[INFERRED] a Farsi guess mirroring the English guess,,order (see orders-core.csv: confirmed purchase; not a money movement),name-only,yes,2026-08-07
legacy archive flag,db-only-legacy,archived_v1 (column; not in current entity code),TBD,,,,name-only,yes,2026-08-07
```
