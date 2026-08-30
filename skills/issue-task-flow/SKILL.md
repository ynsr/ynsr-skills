---
name: issue-task-flow
description: Handles git plumbing for issue/ticket/bug work: branch+worktree setup, tests, push, draft PR.
---

# Issue Task Flow

Git plumbing only — no planning, no scoping. Pair this with whatever you're
using to plan the task (another skill, or the user's own prompting); this
skill just handles getting a branch ready, keeping commits/tests/push sane,
and shipping a PR.

## When to use this

- Starting work on an issue/ticket/bug — setting up a fresh branch+worktree.
- Wants a new feature/fix/chore branch, including basing it on top of an
  existing (not-yet-merged) branch.
- Resuming/continuing work on a branch already in progress.
- Ready to "finish", "wrap up", or "ship" a task — full test run,
  push, draft PR.
- Cleaning up a worktree after a PR merges or closes.

## Workflow

1. **Start the task** — `scripts/start-task.sh`
   - New task: creates a branch (off the repo's default branch, or `--base
     <branch>` for stacking on top of existing work) and a worktree at
     `~/dev/worktrees/<repo>/<branch>`.
   - Resuming existing work: `--resume <branch>` reuses the worktree if it's
     still there (worktrees survive until the PR merges — see step 4), or
     recreates it from the remote branch if it was already cleaned up.
   - Run `scripts/start-task.sh -h` for all flags/examples before using it.

2. **Implement** — work normally in the worktree. Commit at each meaningful
   milestone (`git commit`), as many times as makes sense. **Do not push
   yet** — pushing happens once, at the end.

3. **Finish the task** — `scripts/finish-task.sh`
   - Runs the full test suite (auto-detects Maven/Gradle/Go/Rust/Python
     [pytest, poetry]/npm/pnpm/bun; use `--skip-tests` if you already ran it
     another way).
   - Only on green tests: pushes the branch once (all milestone commits
     together) and opens a **draft** PR against the base branch, auto-linking
     the issue if the branch name has a numeric id in it.
   - This script never marks a PR ready for review — that's a deliberate gate.
     Do it yourself once you've looked over the diff:
     `gh pr ready <branch>` or `glab mr update <branch> --ready`.
   - Run `scripts/finish-task.sh -h` for flags.

4. **Clean up** — `scripts/cleanup-task.sh` — once the PR is merged or
   closed, removes the worktree (checks PR state via `gh`/`glab` first;
   `--force` to override, e.g. abandoning the task). Add `--delete-branch`
   to also drop the local/remote branch.

## Notes

- **If Superpowers is also installed:** its `using-git-worktrees` and
  `finishing-a-development-branch` skills cover similar ground (worktree
  setup, test-gated merge/PR) but aren't issue/PR-aware. For end-to-end
  issue/ticket/bug work — branch → tests → push → draft PR →
  cleanup-on-merge — use this skill instead of those two. Reach for
  Superpowers' `using-git-worktrees` only for ad hoc feature isolation with
  no issue/PR attached.
- **Unattended/agent use:** `start-task.sh` and `finish-task.sh` accept
  `--non-interactive`, which turns every prompt (default-branch detection,
  dirty-base handling) into a fast failure instead of a block — exit code 2,
  with stderr naming what's needed and which flag supplies it (e.g. `--base`,
  `--on-dirty`). Exit 1 is a hard failure; exit 0 is success, and
  `finish-task.sh` ends with a `RESULT: pushed=<branch> pr=<url>` line for an
  orchestrating agent to parse. Full test output (not just the pass/fail
  summary) is saved to `<worktree>/.issue-task-flow/test-output.log`.
- Worktrees live outside the repo tree on purpose (`~/dev/worktrees/...`),
  not inside it — nesting a worktree inside the parent repo's working
  directory causes tools like `git clean -fdx`, IDE indexers, and
  file-watchers to wander into it.
- If the base branch is dirty where it's currently checked out, `start-task.sh`
  prompts to stash/commit/commit+push/ignore before touching it — it won't
  silently discard anything.
- Branch naming: pass `--branch <name>` directly, or build one from
  `--type <feat|fix|chore>` + `--issue <id>` + `--slug <text>`.
- Requires `gh` or `glab` (whichever matches the repo's host) for default-branch
  detection and PR/MR creation; falls back to asking or leaving PR creation
  to the user if neither is authenticated for the repo.
