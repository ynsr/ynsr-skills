---
name: restoring-dropped-branch-mr
description: Use when a git branch was deleted or a GitLab MR was closed by mistake and needs restoring from the MR head commit
---

# Restoring Dropped Branch/MR

## Overview

Deleted remote branch + closed MR is recoverable as long as the head commit still exists: GitLab keeps the SHA, and the local object store usually still has it.

## Quick Reference

| Step | Command |
|---|---|
| Get head SHA | `glab mr view <iid> --repo <group/project> --output json` → `.sha` |
| Confirm commit exists | `git cat-file -t <sha>` → `commit` |
| Recreate branch | `git checkout -b <source-branch> <sha>` |
| Push | `git push -u origin <source-branch>` |
| Reopen MR | `glab mr reopen <iid> --repo <group/project>` |
| Verify | state `opened`, `has_conflicts: false`, work present in branch log |

## Implementation

```bash
SHA=$(glab mr view 1771 --repo server/projectx --output json | python3 -c "import sys,json; print(json.load(sys.stdin)['sha'])")
git cat-file -t "$SHA"  # must print "commit"
# source_branch from the same JSON (.source_branch)
git checkout -b "$BRANCH" "$SHA"
git push -u origin "$BRANCH"
glab mr reopen 1771 --repo server/projectx
```

## Common Mistakes

- **Recreating from `develop` instead of the MR SHA** — loses the work; always use `.sha` from the MR JSON.
- **`git checkout -b` failing on stale local branch** — a same-named local branch may linger; delete it first (`git branch -D`) only after confirming the SHA.
- **Remote branch still missing after reopen** — reopen does not recreate the branch; the push must come first.
- **Assuming merged state** — after reopen check `.state == opened`; if it was merged in the meantime, the squash commit is already on the target branch and no restore is needed.
