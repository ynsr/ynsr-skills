---
name: pr-reviewer
description: >
  Review GitHub pull requests and GitLab merge requests. Trigger on "review PR/MR", "check PR/MR", or GitHub PR/GitLab MR URLs. 
category: code-review
---

# PR/MR Reviewer Skill

Conduct comprehensive, professional code reviews for GitHub Pull Requests and GitLab Merge Requests (gitlab.com and self-hosted) using industry-standard criteria and automated tooling.

## Table of Contents

- [Purpose](#purpose)
- [When to Use](#when-to-use)
- [Review Process Workflow](#review-process-workflow)
- [Reviewing Others Code](#reviewing-others-code)
- [Reviewing Own Code (Self-Review)](#reviewing-own-code-self-review)
- [Reference Documentation](#reference-documentation)
- [Scripts Reference](#scripts-reference)
- [Best Practices](#best-practices)
- [Quick Reference Commands](#quick-reference-commands)
- [Tips for Effective Reviews](#tips-for-effective-reviews)
- [Resources](#resources)

## Purpose

This skill performs code reviews by:

1. **Automating data collection** - Fetching all review-related information (metadata, diff, comments, commits, issues)
2. **Organizing review workspace** - Creating structured directory with all artifacts
3. **Applying systematic criteria** - Reviewing against comprehensive quality checklist
4. **Facilitating inline feedback** - Posting comments directly to PR/MR code on approval
5. **Fixing after approval** - Applying code fixes only after explicit fix approval
6. **Ensuring completeness** - Checking functionality, security, testing, maintainability

## When to Use

Activate this skill when:
- A GitHub PR URL or GitLab MR URL (gitlab.com or self-hosted) is provided with a review request
- Receiving "review this PR/MR", "review my code", or "code review" requests
- Checking PR/MR quality before merging
- Providing systematic feedback on proposed changes
- Asked to fix review findings after approval

## Review Process Workflow

**IMPORTANT**: This skill uses a **two-stage approval process**. Nothing is posted to GitHub/GitLab until explicit approval with `/send` or `/send-decline`. Code is never touched until a second explicit fix approval. Both flows below are intentionally identical today; they are documented separately because the self-review flow is expected to drift (auto-fix policies, branch handling).

### Overview

1. **Fetch review data** - Collect all information (GitHub PR or GitLab MR)
2. **Generate review files** - Create detailed, human, and inline comment files
3. **Review and edit** - Examine files, make changes as needed (use `/show`)
4. **Approve and post** - Use `/send` (approve) or `/send-decline` (request changes); posts summary plus every inline note
5. **Fix after approval** - Only on explicit fix approval, apply fixes in the working branch

### Step 1: Fetch Review Data

GitHub PRs:

```bash
python scripts/fetch_pr_data.py <pr_url> [--output-dir <dir>] [--no-clone]
```

GitLab MRs (gitlab.com or self-hosted; host auto-detected from the URL):

```bash
python scripts/fetch_mr_data.py <mr_url> [--output-dir <dir>] [--no-clone]
```

**Actions performed:**
- Parse review URL (GitHub `.../pull/<n>`; GitLab `.../-/merge_requests/<iid>`, subgroups supported)
- Create directory structure under `~/dev/PRs/`: `<repo>/<n>/` (GitHub) or `<group>_<project>/<iid>/` (GitLab)
- Fetch metadata (title, author, state, branches, labels/assignees)
- Download diff and commit history
- Retrieve existing comments/discussions
- Extract ticket references (JIRA, `#123`, `PROJ-456`)
- Optionally clone source branch (GitHub also generates git diff)

**Example:**
```bash
python scripts/fetch_pr_data.py https://github.com/facebook/react/pull/28476
python scripts/fetch_mr_data.py https://git.jibit.cloud/server/ipg-commons/-/merge_requests/38 --no-clone
```

**GitLab auth and host notes:**
- `glab` resolves the instance from the git remote or the `-R <project-url>` flag. `fetch_mr_data.py` always passes the full project URL derived from the MR URL, so bare `group/project` paths never leak to the default host.
- Authenticate per host once: `glab auth login --hostname <host>`.
- Required token scope: `api` (read MR + post notes). Posting inline notes additionally needs Developer role or higher on the project. Resolving threads needs the same.
- Tested against GitLab 18.5 (Community). `glab mr note create --file/--line` is flagged experimental by glab; `--dry-run` in `add_mr_note.py` previews without posting.

**Output structure (GitHub, default `~/dev`):**
```
~/dev/PRs/<repo-name>/<PR-NUMBER>/
├── metadata.json           # PR metadata (title, author, branches)
├── diff.patch             # PR diff from gh CLI
├── git_diff.patch         # Git diff (if cloned)
├── comments.json          # Review comments on code
├── commits.json           # Commit history
├── related_issues.json    # Linked GitHub issues
├── ticket_numbers.json    # Extracted ticket references
├── SUMMARY.txt            # Human-readable summary
└── source/                # Cloned repository (if not --no-clone)
```

**Output structure (GitLab, default `~/dev`):**
```
~/dev/PRs/<group>_<project>/<IID>/
├── platform.json           # platform/host/project_url for downstream scripts
├── metadata.json           # MR metadata (title, author, branches)
├── diff.patch             # MR diff from glab CLI
├── notes.json             # Discussions (inline + general notes)
├── commits.json           # Commit history
├── ticket_numbers.json    # Extracted ticket references
├── SUMMARY.txt            # Human-readable summary
└── source/                # Cloned repository (if not --no-clone)
```


### Step 2: Analyze Review Data

After fetching, analyze collected data against review criteria:

1. Read `SUMMARY.txt` - High-level overview
2. Review `metadata.json` - Context, labels, assignees/reviewers
3. Examine `diff.patch` - Code changes
4. Check `comments.json` (GitHub) / `notes.json` (GitLab) - Existing feedback
5. Review `commits.json` - Commit quality and messages
6. Check `related_issues.json` (GitHub) / ticket references (GitLab) - Linked tickets/issues
7. Apply review criteria - Evaluate against comprehensive checklist

GitLab note: `notes.json` holds discussions (each with inline position info when applicable). `platform.json` carries host/project_url for downstream posting commands.

### Step 3: Generate Review Files

**CRITICAL**: After analysis, use `generate_review_files.py` to create structured review documents:

```bash
python scripts/generate_review_files.py <review_dir> --findings <findings_json> [--metadata <metadata_json>]
```

Creates three files in `review_dir/pr/`:

1. **`pr/review.md`** - Detailed internal review with emojis and line numbers
2. **`pr/human.md`** - Clean review for posting (no emojis, em-dashes, line numbers)
3. **`pr/inline.md`** - Proposed inline comments with code snippets and per-comment post commands (GitHub `add_inline_comment.py` or GitLab `add_mr_note.py` based on `metadata.platform`)

**Also creates slash commands** in `.claude/commands/`:
- `/send` - Post human.md, approve, then post every inline note
- `/send-decline` - Post human.md, request changes (GitLab: blocking inline threads; no native request-changes API), then post every inline note
- `/show` - Open review directory in VS Code

**Findings JSON structure**:
```json
{
  "summary": "Overall assessment of the PR...",
  "metadata": {
    "platform": "github",
    "repository": "owner/repo",
    "number": 123,
    "title": "PR title",
    "author": "username",
    "head_branch": "feature",
    "base_branch": "main"
  },
  "blockers": [
    {
      "category": "Security",
      "issue": "SQL injection vulnerability",
      "file": "src/db/queries.py",
      "line": 45,
      "details": "Using string concatenation for SQL query",
      "fix": "Use parameterized queries",
      "code_snippet": "result = db.execute('SELECT * FROM users WHERE id = ' + user_id)"
    }
  ],
  "important": [...],
  "nits": [...],
  "suggestions": ["Consider adding...", "Future enhancement..."],
  "questions": ["Is this intended to...", "Should we..."],
  "praise": ["Excellent test coverage", "Clear documentation"],
  "inline_comments": [
    {
      "file": "src/app.py",
      "line": 42,
      "comment": "Consider edge case handling for empty input",
      "code_snippet": "def process(data):\n    return data.strip()",
      "start_line": 41,
      "end_line": 43,
      "owner": "owner",
      "repo": "repo",
      "pr_number": 123
    }
  ]
}
```

GitLab findings: set `metadata` to `{ "platform": "gitlab", "host": "<host>", "project_path": "<group/project>", "number": <iid>, ... }` (copy from `platform.json`). Inline comments support `"side": "LEFT"` for removed-line notes (emitted as `--old-line`); `start_line`/`end_line` become `--line START:END`. `owner`/`repo`/`pr_number` per-comment fields are GitHub-only and ignored for GitLab.

### Step 4: Review and Edit Files

**Use `/show` to open the review directory in VS Code.**

Actions available:
- Read `pr/review.md` - Detailed analysis
- Edit `pr/human.md` - Modify before posting
- Review `pr/inline.md` - Check proposed comments
- Adjust any content as needed

**NOTHING is posted until explicit approval in Step 5.**

### Step 5: Approve and Post

Post the review when ready. Both flows post the summary AND every inline note:

**Option A: Approve**
```
/send
```
- Posts `pr/human.md` as comment
- Approves the PR/MR
- Posts each inline comment from `pr/inline.md` with its command
- Confirms action, then STOPS

**Option B: Request Changes**
```
/send-decline
```
- Posts `pr/human.md` as comment
- Requests changes (GitHub native; GitLab via blocking inline threads, see generated command)
- Posts each inline comment from `pr/inline.md` with its command
- Confirms action, then STOPS

**Inline posting commands:**
- GitHub: `python scripts/add_inline_comment.py <owner> <repo> <n> latest "<file>" <line> "<comment>"`
- GitLab: `python scripts/add_mr_note.py https://<host>/<project> <iid> --file "<file>" --line <line|start:end> -m "<comment>"` (`--old-line` for removed lines, `--unique` for idempotent re-posts, `--dry-run` to preview)

### Step 6: Fix After Approval (Both Flows)

Only after the user explicitly approves fixes (a second approval after posting):

1. Check out the PR/MR source branch locally (never fix on the default branch)
2. Apply fixes for blockers, then important issues; nits only if asked
3. Run the project's checks (tests/lint) before reporting done
4. Report what changed; do NOT push unless the user asks

Scope rule: own code and others' code follow the same gate. Never auto-fix without the fix approval, never auto-commit on `main`/`master`/`develop`.

### Step 7: Apply Review Criteria

Reference `references/review_criteria.md` for comprehensive checklist. Review against these categories:

| Category | Key Questions |
|----------|--------------|
| Functionality | Does code solve the problem? Bugs? Edge cases? |
| Readability | Clear code? Meaningful names? DRY? |
| Style | Follows linter rules? Consistent with codebase? |
| Performance | Efficient algorithms? Scalable? |
| Security | Vulnerabilities addressed? Secrets protected? |
| Testing | Tests exist? Cover happy paths and edge cases? |
| PR Quality | Focused scope? Clean commits? Clear description? |

**Priority markers for findings:**
- Blocker: Must be fixed before merge
- Important: Should be addressed
- Nit: Nice to have, optional
- Suggestion: Consider for future
- Question: Clarification needed
- Praise: Good work

**For detailed criteria:** Read `references/review_criteria.md`

## Reviewing Others Code

Same five-step workflow as the overview. Extra rules:
- Never fix code without the author's (or user's) explicit fix approval. Post findings, stop.
- `/send-decline` on GitLab leaves blocking inline threads instead of a native request-changes review.
- Resolving threads is the author's call; use `glab mr note resolve <iid> <discussion-id>` only when asked.

## Reviewing Own Code (Self-Review)

> [!NOTE]
> This flow is intentionally identical to [Reviewing Others Code](#reviewing-others-code) today. It is kept as a separate section because drift is expected here (stricter auto-fix policies, branch handling, push rules). Change this section first when the flows diverge.

Same five steps, same two approvals:
1. Fetch with `fetch_pr_data.py` (GitHub) or `fetch_mr_data.py` (GitLab).
2. Analyze, generate review files.
3. Review/edit via `/show`.
4. On `/send` or `/send-decline`: post summary plus every inline note, confirm, STOP.
5. On explicit fix approval: check out the MR/PR source branch, fix blockers then important issues, run project checks, report. Do not push unless asked; never commit on the default branch.

## Reference Documentation

This skill includes comprehensive reference guides:

| Reference | Purpose |
|-----------|---------|
| `references/review_criteria.md` | Complete checklist covering functionality, security, testing, and more |
| `references/gh_cli_guide.md` | Quick reference for GitHub CLI commands |
| `references/scenarios.md` | Detailed workflows for common review scenarios |
| `references/troubleshooting.md` | Common issues and solutions |

## Scripts Reference

### `scripts/review_platform.py`

Shared URL parsing and CLI helpers. No direct CLI use needed; imported by the fetch/post scripts.

```bash
python -c "from review_platform import parse_review_url; print(parse_review_url('<pr-or-mr-url>'))"
```

Supports GitHub `.../pull/<n>` and GitLab `.../-/merge_requests/<iid>` (subgroups, self-hosted hosts). `default_reviews_base()` returns `~/dev` (both fetchers use it as the `--output-dir` default).

### `scripts/fetch_pr_data.py`

Automated PR data fetching and organization.

```bash
python scripts/fetch_pr_data.py <pr_url> [options]

Options:
  --output-dir DIR    Base output directory (default: ~/dev, review lands in ~/dev/PRs/...)
  --no-clone         Skip cloning repository
```

### `scripts/fetch_mr_data.py`

Automated GitLab MR data fetching and organization (gitlab.com and self-hosted).

```bash
python scripts/fetch_mr_data.py <mr_url> [options]

Options:
  --output-dir DIR    Base output directory (default: ~/dev, review lands in ~/dev/PRs/...)
  --no-clone         Skip cloning repository
```

Writes `platform.json` (host/project_url for downstream scripts), `metadata.json`, `diff.patch`, `notes.json`, `commits.json`, `ticket_numbers.json`, `SUMMARY.txt`, plus `source/` unless `--no-clone`.

### `scripts/generate_review_files.py`

Generate structured review files from analysis findings.

```bash
python scripts/generate_review_files.py <pr_review_dir> --findings <findings_json> [--metadata <metadata_json>]
```

**Creates:**
- `pr/review.md` - Detailed internal review
- `pr/human.md` - Clean review for posting
- `pr/inline.md` - Proposed inline comments with commands
- `.claude/commands/send.md` - Slash command to approve and post
- `.claude/commands/send-decline.md` - Slash command to request changes
- `.claude/commands/show.md` - Slash command to open in VS Code
- `REVIEW_READY.txt` - Summary of next steps

### `scripts/add_inline_comment.py`

Add inline code review comments to specific lines in a GitHub PR.

```bash
python scripts/add_inline_comment.py <owner> <repo> <pr_number> <commit_id> <file_path> <line> "<comment>" [options]

Options:
  --side RIGHT|LEFT       Side of diff (default: RIGHT)
  --start-line N         Starting line for multi-line comment
  --start-side RIGHT|LEFT Starting side for multi-line comment
```

### `scripts/add_mr_note.py`

Post a review note on a GitLab MR (general, file-level, or inline diff comment).

```bash
python scripts/add_mr_note.py <project-url> <iid> -m "body" [--file PATH] [--line 42|10:15|--old-line N] [--reply ID] [--unique] [--body-file FILE] [--dry-run]
```

Positioning targets the latest diff version (no commit SHA needed): `--line` = new side, `--old-line` = removed line. Use `--body-file` for long markdown bodies, `--unique` for idempotent re-posts, `--dry-run` to preview.

### `tests/`

pytest suite (no network): URL parsing matrix, fetcher helpers, note-command construction, review-file generation for both platforms.

```bash
python -m pytest tests/ -q
```

## Best Practices

### Communication
- Frame feedback as suggestions, not criticism
- Explain why an issue matters, not just what is wrong
- Acknowledge excellent practices
- Prioritize blockers first, style issues last

### Review Efficiency
- Use scripts to automate data fetching and comment posting
- Reference `review_criteria.md` as checklist
- Focus: Critical issues > Important > Nice-to-have
- Review promptly (within 24 hours if possible)

### Inline Comments
- Reference exact lines and files
- Provide better alternatives
- Test inline comments on test PRs first
- Use sparingly to avoid overwhelming

### PR Size Handling
- Large PRs (>400 lines): Suggest splitting
- Review in logical chunks
- Focus on architecture for large changes

**For detailed scenarios:** Read `references/scenarios.md`

## Quick Reference Commands

```bash
# Fetch review data (defaults to ~/dev/PRs/<repo|group_project>/<n>/)
python scripts/fetch_pr_data.py https://github.com/owner/repo/pull/123
python scripts/fetch_mr_data.py https://git.jibit.cloud/server/ipg-commons/-/merge_requests/38 --no-clone

# Add inline comment (GitHub)
python scripts/add_inline_comment.py owner repo 123 latest "src/app.py" 42 "Comment"

# Add inline note (GitLab) - preview first
python scripts/add_mr_note.py https://git.jibit.cloud/server/ipg-commons 38 --file "src/app.py" --line 42 -m "Comment" --dry-run

# View in browser
gh pr view 123 --repo owner/repo --web
glab mr view -R https://git.jibit.cloud/server/ipg-commons 38 --web

# Check status
gh pr checks 123 --repo owner/repo
glab ci get --merge-request 38

# View existing comments
gh api /repos/owner/repo/pulls/123/comments --jq '.[] | {path, line, body}'
glab mr note list -R https://git.jibit.cloud/server/ipg-commons 38

# Run skill tests
python -m pytest tests/ -q
```

## Tips for Effective Reviews

1. Start with context: Read PR description, linked issues, commit messages
2. Understand intent: Identify the problem being solved
3. Check tests first: Verify tests demonstrate the fix/feature
4. Look for patterns: Repeated issues suggest architecture problems
5. Consider alternatives: Evaluate simpler approaches
6. Think about maintenance: Assess future modification ease
7. Remember humans: Maintain kindness, respect, and constructive tone

**For troubleshooting:** Read `references/troubleshooting.md`

## Resources

- **Review Criteria**: `references/review_criteria.md`
- **gh CLI Guide**: `references/gh_cli_guide.md`
- **glab CLI Guide**: `references/glab_cli_guide.md`
- **Scenarios**: `references/scenarios.md`
- **Troubleshooting**: `references/troubleshooting.md`
- **Google Engineering Practices**: https://google.github.io/eng-practices/review/
- **OWASP Top 10**: https://owasp.org/www-project-top-ten/
