---
name: recovering-from-edit-thrash
description: Use when surgical file edits keep failing, corrupting nearby lines, or producing cascading fix-on-fix churn
---

# Recovering From Edit Thrash

## Overview

Line-anchored edit tools reject or mis-apply patches when ranges drift from current file state. Each retry compounds the damage: dropped lines, duplicated entries, widening diffs. The fix is to stop patching and switch to a script that computes the target state, applies it atomically, and verifies in a loop.

**Core principle:** 3 failed edit attempts on one file = stop editing, script the repair.

## When to Use

- Same file needed 3+ edit calls and still isn't right
- Edits drop or duplicate nearby lines (`__all__` entries, imports, list items)
- `git diff` shows deletions you never intended
- Fix produces a new error requiring another fix (cascading churn)
- Re-reading + re-issuing the same patch shape keeps failing

When NOT to use: first-attempt edits, single clean patches, genuinely new content (not repair).

## Core Pattern

Before (thrash): read → patch range → range rejected → re-read → patch wider range → nearby lines dropped → patch to restore → another line dropped → ...

After (script): write one script that reads the file, computes the desired end state programmatically, writes it back, then runs the verifier (lint/tests) — loop the script, not the patch.

```python
# Swap/reconcile list entries deterministically, then verify each loop
src = read(path)
src = src.replace(unwanted, wanted)          # string-level, no line numbers
write(path, src)
# then: lint + tests; report all results per loop iteration
```

## Quick Reference

| Step | Action |
|---|---|
| 1. Stop | After 3rd failed patch on one file, no more `edit` calls on it |
| 2. Diff | `git diff` to list exactly which lines are damaged vs intended |
| 3. Script | One `eval`/`write` script: read → transform → write (no line numbers) |
| 4. Loop | Re-run script + verifier (lint/tests) until clean; report each iteration |
| 5. Confirm | Final `git diff` must be additive-only vs intent (no stray deletions) |

## Implementation

1. **Freeze the intent**: write down the exact end state (e.g. "add 4 entries to `__all__`, change nothing else").
2. **Script the transform**: prefer whole-string `replace()` / set-reconciliation over line ranges. For ordered lists, compute `sorted(current | additions)` and rewrite the block.
3. **Verify in the loop**: each script run ends with the cheapest decisive check (targeted lint, single test file), and you report the result before the next iteration.
4. **Widen only at the end**: full suite + full lint once the loop is green.

## Common Mistakes

- **Widening the range to "fix" a rejection** — wider ranges swallow keepers; re-read instead, then script.
- **Restoring dropped lines one by one** — each restore risks dropping another; reconcile the whole block at once.
- **Mixing new content into a repair script** — repair first, extend after green.
- **Skipping the final additive-only diff check** — the loop can converge on a wrong-but-clean state.

## Real-World Impact

`__init__.py` `__all__` edits thrashed for 15+ patch calls (each restore dropped a different entry). One set-reconciliation script fixed it in a single pass; looped lint confirmed green each iteration.
