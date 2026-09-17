# GitLab CLI (glab) Guide for MR Reviews

Quick commands and patterns for accessing MR data using `glab`. Mirrors `gh_cli_guide.md` for GitHub.

## Prerequisites

Install: https://gitlab.com/gitlab-org/cli

Authenticate per host (gitlab.com and each self-hosted instance):

```bash
glab auth login --hostname gitlab.com
glab auth login --hostname git.jibit.cloud
```

Required token scope: `api`. Inline notes additionally need Developer role or higher on the project.

## Host Resolution (Important)

`glab` resolves the target instance from the **git remote** of the current repo or the **`-R` flag**. A bare `-R group/project` outside a clone hits the default host (usually gitlab.com). Always pass the **full project URL** derived from the MR URL:

```bash
glab mr view -R https://git.jibit.cloud/server/ipg-commons 38 --output json
```

`scripts/fetch_mr_data.py` and `scripts/add_mr_note.py` do this automatically.

## Basic MR Information

```bash
# View MR details (JSON)
glab mr view -R https://<host>/<group>/<project> <iid> --output json

# Key fields only
glab mr view -R https://<host>/<group>/<project> <iid> --output json \
  | jq '{iid, title, state, author: .author.username, source_branch, target_branch, sha}'

# View diff
glab mr diff -R https://<host>/<group>/<project> <iid>

# Open in browser
glab mr view -R https://<host>/<group>/<project> <iid> --web
```

## Discussions and Notes

```bash
# List discussions (inline + general notes)
glab mr note list -R https://<host>/<group>/<project> <iid>

# Machine-readable
glab mr note list -R https://<host>/<group>/<project> <iid> -F json \
  | jq '.[] | {id, file: .notes[0].position.new_path, line: .notes[0].position.new_line}'

# Reply inside a thread (full discussion ID or 8+ char prefix)
glab mr note create -R https://<host>/<group>/<project> <iid> --reply <discussion-id> -m "I agree!"

# Resolve / reopen a thread
glab mr note resolve <iid> <discussion-id>
glab mr note reopen <iid> <discussion-id>
```

## Inline Diff Notes

```bash
# New-side line (latest diff version; no commit SHA needed)
glab mr note create -R https://<host>/<group>/<project> <iid> \
  --file path/to/file --line 42 -m "Needs refactoring"

# Range (multiline)
glab mr note create -R https://<host>/<group>/<project> <iid> \
  --file path/to/file --line 10:15 -m "Extract this block"

# Removed line (old side)
glab mr note create -R https://<host>/<group>/<project> <iid> \
  --file path/to/file --old-line 7 -m "Why was this removed?"

# File-level comment (no line)
glab mr note create -R https://<host>/<group>/<project> <iid> \
  --file path/to/file -m "General comment on this file"

# Long markdown body: pipe via stdin (avoids quoting pitfalls)
glab mr note create -R https://<host>/<group>/<project> <iid> \
  --file path/to/file --line 42 < /tmp/note.md

# Idempotent re-post (skip if same body exists)
glab mr note create -R https://<host>/<group>/<project> <iid> -m "LGTM" --unique
```

Flag rules: `--line`/`--old-line` require `--file` and are mutually exclusive; `--file`, `--reply`, `--unique` are mutually exclusive. Prefer the `scripts/add_mr_note.py` wrapper, which validates these and adds `--dry-run`.

## Commits

```bash
# Via API (needs numeric project id; see metadata.json project_id)
glab api projects/<id>/merge_requests/<iid>/commits --hostname <host> \
  | jq '.[] | {short_id, title}'

# Diff refs (base/head SHAs for positioning context)
glab mr view -R https://<host>/<group>/<project> <iid> --output json \
  | jq '.diff_refs'
```

## Approvals and Merge Status

```bash
glab mr view -R https://<host>/<group>/<project> <iid> --output json \
  | jq '{state, detailed_merge_status, has_conflicts, approvals_required, approved}'

glab mr approve -R https://<host>/<group>/<project> <iid>
```

Note: GitLab has no `request-changes` review event. The skill's `/send-decline` leaves blocking inline threads instead.

## CI Status

```bash
glab ci get --merge-request <iid>
glab ci status
```

## Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| `401 Unauthorized` on gitlab.com | Bare `-R group/project` resolved to the wrong host; use the full project URL |
| `Not a git repository` | `glab mr diff`/`note list` need repo context or `-R <full-url>` |
| `None of the git remotes ... point to a known GitLab host` | Run outside any repo without `-R`, or host not authed: `glab auth login --hostname <host>` |
| Note targets wrong line | glab binds to the latest diff version; re-fetch `glab mr diff` after new pushes |
