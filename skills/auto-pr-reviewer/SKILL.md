---
name: auto-pr-reviewer
description: Use when a GitHub PR or GitLab MR must be reviewed and posted with no human in the loop - CI jobs, scheduled sweeps, bot flows. Trigger on "auto-review", "review and post", or a PR/MR URL paired with hands-off, post-directly, or no-confirmation.
---

# Auto PR Reviewer

## Overview

Non-interactive wrapper around the `pr-reviewer` fetch/post scripts. Same review quality bar (`pr-reviewer/references/review_criteria.md`), zero manual gates: fetch to a temp dir, analyze, generate, post, report. One command publishes; nothing waits for `/send`, `/show`, or fix approval.

**REQUIRED BACKGROUND:** Reuses `pr-reviewer` scripts. Know its fetch/post CLIs; this skill only defines the hands-off pipeline and verdict policy.

## When to Use

- Automated flow explicitly requests review + post with no user present (CI, cron, bot).
- Caller passes `PR_URL` (or `MR_URL`) plus optional `MODE`/`FIX_MODE` and goes away.
- Batch sweeps over many PRs/MRs.

When NOT to use: any human is available to read the review first (use `pr-reviewer`); the change needs discussion before posting; push/fix should land without a separate approval gate (out of scope, see Fix Policy).

## Inputs

| Variable / flag | Default | Meaning |
|---|---|---|
| `PR_URL` (or `MR_URL`) | required | `.../pull/<n>` or `.../-/merge_requests/<iid>` |
| `MODE` | `comment` | `comment` (never approve), `verdict` (approve iff clean), `strict` (`verdict` + request-changes on blockers) |
| `FIX_MODE` | `off` | `off` (report only). `suggest` appends unified-diff suggestions for blockers. Never commits or pushes. |
| `MAX_INLINE` | `10` | Cap on posted inline notes; blockers first, then important, then nits. |
| `DRY_RUN` | `false` | `true` prints every post command, posts nothing. |
| `LABELS` | empty | Extra labels to apply, e.g. `auto-reviewed`. |

Auth: `gh auth login` once (GitHub); `glab auth login --hostname <host>` per GitLab host, token scope `api`, Developer role+ to post inline notes.

## Pipeline

Run `scripts/auto_review.py` (single shot; exits non-zero on any post failure):

1. **Fetch** to temp dir (`fetch_pr_data.py` / `fetch_mr_data.py --no-clone`). No persistent `~/dev/PRs` tree, no `source/` clone.
2. **Analyze** diff + metadata + existing notes against `review_criteria.md`. Produce findings JSON (same schema as `pr-reviewer` Step 3: `blockers`, `important`, `nits`, `suggestions`, `questions`, `praise`, `inline_comments`).
3. **Generate** only `pr/human.md` via `generate_review_files.py`.
4. **Post** in order: summary comment, verdict action, inline notes (each with `--unique` / idempotent re-post; GitLab positions pre-validated with `--validate`).
5. **Report** one line to stdout: `verdict=<approve|request-changes|comment> blockers=<n> important=<n> posted=<n> skipped=<n> url=<review-url>`. Machine-readable receipt stays in the temp dir; temp dir is deleted unless `KEEP_DIR=true`.

```bash
python scripts/auto_review.py "$PR_URL" --mode verdict --findings findings.json
python scripts/auto_review.py "$MR_URL" --mode strict --max-inline 5 --dry-run
```

## Verdict Policy

Deterministic mapping from findings; no judgment calls at post time:

| Findings | `comment` | `verdict` | `strict` |
|---|---|---|---|
| `blockers` > 0 | post summary + inline, no approve | same as `comment` | + request-changes (GitHub native; GitLab = blocking resolvable inline threads, no approve) |
| `important` > 0, no blockers | post summary + inline, no approve | post summary + inline, no approve | request-changes |
| only nits/suggestions | post summary, no approve | approve + post summary | approve + post summary |
| clean | post summary, no approve | approve + post summary | approve + post summary |

Large PRs (>400 lines): note `suggest-split` in the summary; still review.

## Dropped vs Kept Artifacts

`pr-reviewer` artifacts built for human checkpoints are skipped; nothing interactive is generated:

| Artifact | Dropped? | Reason |
|---|---|---|
| `pr/review.md` (emoji detailed review) | dropped | Internal human-reading doc; agent analysis already in context |
| `pr/inline.md` preview + per-comment shell snippets | dropped | Agent posts directly; no human preview step |
| `/send`, `/send-decline`, `/show` slash commands | dropped | Manual approval and VS Code editing gates |
| `REVIEW_READY.txt`, `SUMMARY.txt` | dropped | Human next-step prompts; replaced by stdout report line |
| `source/` clone, `git_diff.patch` | dropped | `--no-clone`; hosted diff is sufficient |
| `comments.json` / `notes.json` / `commits.json` / `related_issues.json` on disk | dropped | Read-then-discard; only ticket refs surviving into findings |
| `pr/human.md` | kept (transient) | Post body, deleted with temp dir |
| `metadata.json`, `diff.patch`, post receipts | kept (transient) | Needed for verdict + idempotency debugging |

## Fix Policy

- `FIX_MODE=off`: never touch code. Report only.
- `FIX_MODE=suggest`: may append ```diff fenced suggestions inside the posted comments. Never checks out branches, never commits, never pushes.
- Auto-fix with commit/push is out of scope. A human promotes suggestions via `pr-reviewer` Step 6.

## Safety Rails

- Never approve when `blockers` > 0, any mode. `strict` is the only mode that ever request-changes.
- Idempotent re-runs: GitLab `--unique`; GitHub dedupes by matching existing inline body on the same file/line before posting.
- Inline positions validated before posting (inside a diff hunk, correct old/new side); invalid ones degrade to a file-level note, never dropped silently - counted in `skipped`.
- Secrets: findings must never include tokens/keys from the diff; redact before posting.
- On any post failure: exit non-zero, print which step failed, leave temp dir in place (`KEEP_DIR` forced true) for forensics.

## Failure Handling

- Fetch/auth failure: exit 2, `verdict=error`, post nothing.
- Empty diff or closed/merged target: exit 0, `verdict=skip`, post nothing.
- Partial inline failure: summary + verdict still posted; report `posted`/`skipped` counts; exit 1.

## Reference

- Criteria: `../pr-reviewer/references/review_criteria.md`
- Fetch/post CLIs: `../pr-reviewer/scripts/{fetch_pr_data,fetch_mr_data,generate_review_files,add_inline_comment,add_mr_note}.py`
- CLI auth quirks (self-hosted hosts, token scopes): `../pr-reviewer/SKILL.md` Step 1 notes.
