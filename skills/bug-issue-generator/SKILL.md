---
name: bug-issue-generator
description: >
  Turns a bug/issue thread or ticket into a structured bug report. Accepts a Mattermost thread (mm CLI), Jira issue (jira-cli), GitLab issue (URL), any other URI, or plain text/file. Normalizes loose language against the project glossary (docs/glossary/*-glossary.csv), asking the user when a term is unclear, then drafts a structured Markdown bug report. Run from the project root.
compatibility: >
  Optional tools by source type: mm CLI (Mattermost), jira-cli (Jira), web_fetch (GitLab/URLs). Run from project root for docs/glossary/*-glossary.csv (from glossary-generator, optionally extended by a project skill). No glossary found = still works, lower precision. CSV schema: read glossary-generator/references/csv-format.md, don't assume it.
disable-model-invocation: true
user-invocable: true
---

# Bug Issue Generator

Turns any bug/issue source into a precise, structured report — normalizing loose language against the project glossary, asking you when a term is unclear instead of guessing.

## Step 1 — Get the source content
Ask what the source is if not given. Fetch by type:
- **Mattermost thread** (permalink/post ID) → `mm` CLI. Check `mm --help` first, don't guess flags.
- **Jira issue** (key/link, e.g. `PROJ-123`) → `jira-cli` (e.g. `jira issue view PROJ-123`). Check `jira --help` if unsure.
- **GitLab issue** (URL) → web_fetch, or `glab issue view` if that CLI is available.
- **Other URI** → fetch directly.
- **Plain text / file** → use as given, no fetch.

You need the full description/thread plus every comment/reply, each with author, timestamp, text. Apply Step 2's claim-filtering to comments the same way you would thread replies, regardless of source type.

## Step 2 — Filter and draft
Read `references/report-format.md` now for the claim-filtering rules and fixed 6-section template. Don't reconstruct these from memory.

## Step 3 — Load the module glossary
Find `docs/glossary/*-glossary.csv` in the project root. More than one → infer the module from channel/project name, ask if unclear. None found → say so, proceed without normalization (note this lowers precision).

## Step 4 — Normalize against the glossary
For each term that matters (Title, Steps to Reproduce, Environment — not chatter), check it against `term` / `aliases_loose` (EN+FA) / `definition_en` / `definition_fa`:
- **One confident match** → use the glossary's `term`, not the loose wording.
- **No match anywhere** → keep the original wording, note it as a possible new term in Step 7.
- **Ambiguous, or the match is missing something needed** (blank `definition_fa`, thin aliases) → stop, ask. Batch every such question into one numbered list with candidate options + "something else," don't ask one at a time:
  ```
  1. "the retry thing keeps failing" — which do you mean?
     a) settlement batch retry (projectx: SettlementBatchEntity)
     b) psp call retry (psp-agent-x: PspCallLog)
     c) something else — tell me what
  2. No Farsi definition for "callback timeout" — what's the team's term?
  ```
  Wait for the reply before Step 5.

## Step 5 — Write answers back to the glossary
Real file access, git-tracked — a normal reviewable edit, not a silent mutation.
- New term → append a row: `confidence=human-confirmed`, `needs_review=no`.
- Filling a gap on an existing row → update only that field, same tagging, leave the rest untouched.
- Never touch a row/field the person didn't just confirm.

## Step 6 — Draft the report
Use the resolved terms. Follow `references/report-format.md` exactly. `"Not provided in thread"` for anything ungrounded — never fabricate.

## Step 7 — Summarize
State: glossary file used (or none found), which terms were auto-resolved vs. asked about, which glossary rows changed (so it's visible in `git diff`).

## Out of scope
- Never guess at an ambiguous term.
- Only ask about terms that affect report accuracy, not every unmatched word.
- Never overwrite a glossary row for anything other than what was just confirmed.
- Never fabricate CLI syntax (`mm`/`jira-cli`/etc.) — check `--help`.
- Don't auto-trigger from unrelated requests.