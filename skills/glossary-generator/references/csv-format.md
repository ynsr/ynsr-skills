# Glossary CSV Format (fixed — do not deviate)

One file per module: `docs/glossary/<module-name>-glossary.csv` (e.g. `docs/glossary/projectx-glossary.csv`)

## Header (exact column order)
```
term,module,status,code_refs,definition_en,definition_fa,aliases_loose,do_not_confuse_with,confidence,needs_review,last_scanned
```

## Column definitions
| Column | Meaning | Example |
|---|---|---|
| `term` | Canonical business-facing name, lowercase, spaced (not code-cased) | `settlement batch` |
| `module` | Service/module this belongs to | `ppg-core` |
| `status` | `active`, `deprecated` (still in code, marked deprecated), or `db-only-legacy` (in schema, no code reference) — see SKILL.md "Handling deprecated and DB-only fields" | `active` |
| `code_refs` | Semicolon-separated list of exact code/schema locations | `SettlementBatchEntity;settlement_batches (table)` |
| `definition_en` | One plain sentence. Untagged if `code-grounded`; prefixed `[INFERRED] ` if guessed with no grounding (see SKILL.md Step 4). | `A grouped set of confirmed transactions submitted to a PSP for payout in one settlement run.` |
| `definition_fa` | Farsi definition. Untagged if taken verbatim from a native Farsi source in the repo; prefixed `[TRANSLATED] ` if machine-translated from a grounded `definition_en`; prefixed `[INFERRED] ` if guessed with no grounding at all. Never untagged unless it's a native source. | `[TRANSLATED] ...` |
| `aliases_loose` | Semicolon-separated loose terms people actually use (EN and FA mixed, both directions) — leave blank at generation time unless found in code comments/logs; this column is mainly filled by human reviewers over time | `batch;settlement run` |
| `do_not_confuse_with` | Semicolon-separated cross-module collisions detected in Step 5, with a one-clause disambiguator | `transaction (see psp-agent-x.csv: single outbound PSP call, not full customer payment)` |
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
term,module,status,code_refs,definition_en,definition_fa,aliases_loose,do_not_confuse_with,confidence,needs_review,last_scanned
settlement batch,ppg-core,active,SettlementBatchEntity;settlement_batches (table),A grouped set of confirmed transactions submitted to a PSP for payout in one settlement run.,[TRANSLATED] a Farsi rendering of the English sentence,,,code-grounded,yes,2026-08-07
psp call attempt,psp-agent-x,active,PspCallLog;psp_call_log (table),[INFERRED] Likely represents a single outbound call attempt to a PSP for one leg of a transaction; based on class name and its place in the retry-handling package.,[INFERRED] a Farsi guess mirroring the English guess,,transaction (see ppg-core.csv: full customer payment; not one PSP call),name-only,yes,2026-08-07
legacy retry counter,ppg-core,db-only-legacy,retry_count_v1 (column; not in current entity code),TBD,,,,name-only,yes,2026-08-07
```
