---
name: deprecation-test-fixer
description: >
  Use when tests fail to compile after a feature, its DTO fields, enum values, or service methods have been deprecated and deleted.
  Diagnoses "cannot find symbol" errors in parametrized test data, constant references, builder invocations, and import statements.
  Walks through git-history reconstruction of what was removed, grep-based verification, then systematic removal of invalid test entries
  with handling for trailing commas and cascading removals. Suited for Java/Spring Boot with Maven or Gradle; principle extends to
  any statically-typed language (C#, TypeScript, Kotlin).
compatibility: >
  Java/Spring Boot projects with Maven or Gradle. Works with parametrized tests (@MethodSource, @CsvSource), constant-based error codes,
  builder/helper methods, and test data providers. Principle applies to any statically-typed language.
disable-model-invocation: true
user-invocable: true
---

# Deprecation/Deletion Test Fixer

When a feature is deprecated and its DTO fields, enums, or service methods are deleted, test files that reference them fail to compile. The fix is almost always **removal of test-side noise that referenced the deleted parts** — rarely does production code need changing.

**Core principle:** Compilation errors tell you what symbols are gone. Git history tells you *why* they were removed. Combine both to decide whether to remove, replace, or update each failing reference.

## Phase 0 — Finding what changed

Before editing anything, establish exactly what was deleted and why. Never assume — verify against both git history and the current source.

### 0a. Reconstruct from git history

```bash
# Find commits that touched a file of interest
git log --oneline --all -- src/main/java/ir/jibit/projectx/config/terminal/TerminalDto.java

# See exactly what was removed in the most recent commit on that file
git log --oneline --all --diff-filter=D -- <file-or-directory>

# Search commit messages for deprecation/removal
git log --oneline --all --grep="deprecat\|remov\|delet\|clean" -20

# Show the diff of a specific commit (what was deleted, what was added)
git show <commit-hash>

# Show only deleted lines in a range of commits
git log --all -p -- <file> | grep "^-.*" | head -30

# Find when a specific symbol was last referenced in source
git log --all -S "earlySettlementMaxAmount" --oneline

# List all commits that touched a file, with diffstat
git log --oneline --stat -- <file>
```

The `-S` (pickaxe) flag is the most useful — it finds commits that *changed the number of occurrences* of a string, which is exactly what you need when a symbol vanished.

### 0b. Inspect the current source directly

Cross-check what git history suggests against what's actually in the codebase:

```bash
# Check if a DTO field still exists
grep -rn "earlySettlement" src/main/java/ir/jibit/projectx/ 2>/dev/null | head -20

# Check enums for removed values
grep -rn "RemovedEnumValue" src/main/java/ir/jibit/projectx/ 2>/dev/null

# Check if a service method still exists
grep -rn "someDeletedMethod" src/main/java/ir/jibit/projectx/ 2>/dev/null

# List all imports in a failing test file
grep "^import" src/test/java/.../FailingTest.java

# Check if a production class still exists
find src/main/java -name "DeletedClass.java" 2>/dev/null
```

### 0c. Pinpoint the exact removal commit

When multiple changes happened around the same time, narrow down:

```bash
# Bisect by file — which commit removed the symbol?
git log --all -L '/private static final String earlySettlement/,/;/':src/test/java/.../FailingTest.java --oneline

# Or pickaxe search across the whole history
git log --all -S "earlySettlementPercentageInvalid" -- "*.java"
```

Then read the commit message and diff to understand *intent* — was this field renamed, replaced by a different mechanism, or simply no longer validated?

### 0d. Classify each error

For every `cannot find symbol` error, determine:

| Error Type | What happened | Likely fix |
|---|---|---|
| Constant field `FOO_VALIDATION` | Test-side validation code removed with the field it validated | Remove constant + usage lines |
| DTO field `.getFoo()` / `.setFoo()` | DTO property deleted | Remove test lines that called it |
| Enum value `FooType.REMOVED` | Enum constant removed | Remove references or update to replacement value |
| Import `import ...DeletedClass` | Entire class deleted | Remove import + all usages |
| Method `someService.foo()` | Service method signature changed | Update call site or mock setup |

## The Pattern

The typical failure sequence (observed in Java/Spring Boot with parametrized tests):

1. **Round 1** — `mvn test-compile` produces 5-15 `cannot find symbol` errors, all referencing constants or methods that called deleted DTO fields/enums.
2. **After removing those** — a new `illegal start of expression` error appears. This is a **trailing comma** on what is now the last argument in a `Stream.of(...)` or similar varargs call. Java does not allow trailing commas in method argument lists (unlike Python or JSON).
3. **After fixing the comma** — clean compile.

The fix is **always** removal of test-side entries that referenced now-deleted production code, **never** restoring the deleted production code.

## Workflow

### Step 1 — Run compilation and collect all errors

```bash
mvn test-compile 2>&1 | grep "cannot find symbol"
```

List every line number and the symbol name. Group them into:

- **Constant definitions** — `private static final String SOME_CONST = "...";` that referenced the deleted DTO field
- **Usage lines** — `arguments(newFooBuilder(...), someDeletedConstant),` in a `Stream.of(...)` block
- **Import statements** — `import ...DeletedClass;`
- **Method call sites** — `someDto.getRemovedField()` or `service.deletedMethod()`

### Step 2 — Identify the correct removal set

For each error, determine whether it references the deleted feature:

- **Constant definitions** → remove the entire line.
- **Usage lines in parametrized test data** → remove the entire `arguments(...)` or `Arguments.of(...)` line.
- **Imports** → remove the import line.
- **Test methods exclusively testing deleted behavior** → remove the entire `@Test` method.
- **Builder invocations passing deleted values** → remove the argument from the builder call, but **do not remove the builder method parameter** (see Pitfall 6).

> **Important:** Before removing a constant definition, `grep` the file for other references to that constant. If it's used in multiple test methods, only remove the usage lines — keep the constant definition until all usages are gone.

Do not remove any line that tests a still-valid feature, even if it sits right next to deleted lines.

### Step 3 — Use a script for non-contiguous removals

When lines to remove are scattered (constants at the top of the file, usage lines in middle methods), a small Python script is safest — line-by-line `sed` with shifting line numbers is error-prone:

```python
import re

path = "path/to/TestFile.java"
lines_to_remove_patterns = [
    r"earlySettlementPercentageInvalid",
    r"maxEarlySettlementInvalid",
    r"percentageAndMaxEarlySettlementReq",
]

with open(path) as f:
    lines = f.readlines()

# Find lines matching any pattern, in descending order
to_remove = set()
for i, line in enumerate(lines):
    for pat in lines_to_remove_patterns:
        if re.search(pat, line):
            to_remove.add(i)

for i in sorted(to_remove, reverse=True):
    del lines[i]

# Fix trailing comma: after removals, last argument before ");" might have trailing comma
# (handled by pattern-matching in a real implementation)

with open(path, "w") as f:
    f.writelines(lines)
```

Alternatively, if all deletions are in one contiguous block at the end of a method, a single `sed` range is fine:

```bash
# Only for a contiguous block you've verified
sed -i '100,105d' FileUnderTest.java
```

### Step 4 — Fix trailing commas

After removing lines from a `Stream.of(...)` or `Arguments.of(...)` call, the last remaining argument may now have a trailing comma. Java rejects this:

```java
// BROKEN — trailing comma after removals
Stream.of(
    arguments(...),      // kept
    arguments(...),      // <-- was followed by deleted lines, now last — ERROR
);

// FIXED
Stream.of(
    arguments(...),      // kept
    arguments(...)       // trailing comma removed
);
```

**Check:** Find the last argument before `);` in every `Stream.of(...)` block you edited. If it ends with `,`, remove it.

### Step 5 — Recompile and iterate

```bash
mvn test-compile 2>&1 | grep -E "illegal start of expression|cannot find symbol|error:"
```

Common second-round errors:

| Error | Cause | Fix |
|---|---|---|
| `illegal start of expression` | Trailing comma (Step 4) | Remove trailing comma on last argument |
| `unused import` | Only the deleted lines used it | Remove the import line |
| `unused variable / never read` | Only the deleted lines referenced it | Remove the field/variable (check for other usages first) |
| `cannot find symbol` (new ones) | Cascading — earlier deletions exposed more | Go back to Step 1 |

### Step 6 — Verify final compilation

```bash
mvn test-compile 2>&1 | grep -E "BUILD SUCCESS|BUILD FAILURE"
```

Only proceed when `BUILD SUCCESS` is confirmed.

### Step 7 — Run the affected tests

```bash
mvn test -Dtest="TestClassName" 2>&1 | tail -20
```

Check for:

- `BUILD SUCCESS` — test compilation and execution passed
- `Tests run: N, Failures: 0, Errors: 0` — all tests passed

**If tests still fail at runtime:** the deleted feature's behavior may be referenced in test assertions or mock setups that compiled OK but fail at runtime. This is a different class of problem — apply systematic debugging, not this skill.

## Quick Reference

| Step | Command | What to look for |
|---|---|---|
| Phase 0a | `git log -S "symbol" --oneline` | Which commit removed the symbol |
| Phase 0b | `grep -rn "symbol" src/main/` | Whether the symbol is truly gone |
| Phase 0c | `git show <hash>` | Diff + commit message (intent) |
| Step 1 | `mvn test-compile \| grep "cannot find"` | All broken references |
| Step 3 | Python script for scattered removals | Prevents line-number drift |
| Step 5 | `mvn test-compile \| grep -E "error\|cannot find"` | Second-round errors |
| Step 7 | `mvn test -Dtest="ClassName"` | Runtime pass/fail |

## Common Pitfalls

### Pitfall 1: Forgetting to check for other usages before deleting a constant

A constant like `earlySettlementPercentageInvalid` might be used in multiple test methods (e.g., both `registerPfTerminal` and `updatePfTerminal` data providers). Always `grep` the file for all references before removing the constant definition.

### Pitfall 2: Trailing comma after the second-last item, not the last

```java
Stream.of(
    arguments(...),  // deleted
    arguments(...),  // now last — has trailing comma -> ERROR
    arguments(...)   // deleted — but what if only this was deleted?
);
```

If you delete the last argument but keep the second-to-last, the second-to-last now needs its trailing comma removed. Always check which line is the final remaining argument after your deletions.

### Pitfall 3: Line number shifts

Each deletion shifts all subsequent line numbers. When using `sed` for multiple non-contiguous removals, apply them in **descending** line number order (highest first) so earlier deletions don't invalidate later references. Better yet, use the Python script approach which is order-independent.

### Pitfall 4: Commented-out lines

A commented-out line (`// arguments(...)`) is harmless — leave it alone. It does not cause compile errors and does not contribute to the trailing comma problem since Java ignores it.

### Pitfall 5: HashMap-based test data (not Arguments.of)

```java
arguments(Map.of("code", "e", "sourceCreditClientCode", "e".repeat(101)), someErrorConstant),
```

Here the field reference is inside a Map literal string key, not a Java symbol. The error will be `cannot find symbol` on `someErrorConstant`, but the Map entry itself is fine and does not need removal (the field name is just a string key — `sourceCreditClientCode` is not a Java symbol here). Only remove the `arguments(...)` line if the error constant itself is deleted.

### Pitfall 6: Builder methods still having deleted parameters

Builder/helper methods (e.g., `newPfTerminal(...)`) may still have parameters named after deleted fields and pass them into Map literals. These compile fine as long as the parameters themselves are not removed from the method signature. **Leave builder method signatures untouched** — removing their parameters would cascade into every call site, many of which may not even reference the deleted feature.

### Pitfall 7: Assuming the fix is always test-side

Occasionally the test was correct but the production code deletion was too aggressive — a legitimate validation was removed along with the feature's data. In this case, the right fix may be **restoring the deleted validation in production code**, not removing the test. Read the commit message from Phase 0 to understand intent before deciding.

## Example trace (from a real session)

1. `mvn test-compile` → 10 `cannot find symbol` errors for `earlySettlementPercentageInvalid`, `maxEarlySettlementInvalid`, `percentageAndMaxEarlySettlementReq`
2. Phase 0: `git log -S "earlySettlementMaxAmount" --oneline` found the removal commit. `git show <hash>` confirmed the DTO fields `earlySettlementMaxAmount` and `earlySettlementPercentage` were intentionally deleted from terminal DTOs.
3. Found 3 constant definitions + 5 usage lines in `provideInvalidRegisterPfTerminalData()` + 5 usage lines in `provideInvalidUpdatePfTerminalData()` = 13 lines to remove
4. After removal → 1 `illegal start of expression` at the trailing comma on the `activeSettlementIbanInvalid` line (now the last argument)
5. Removed trailing comma → `mvn test-compile` → BUILD SUCCESS
6. `mvn test -Dtest="TerminalAdminControllerIT"` → all 10 previously failing tests passed

**Root cause:** DTO fields `earlySettlementMaxAmount` and `earlySettlementPercentage` were deleted from the terminal DTOs, but test constants referencing their validation error codes, and argument lines using those constants in parametrized test data providers, were not updated to match.

## When not to use this skill

- **Runtime test failures** (tests compile but fail at runtime) — use systematic debugging instead
- **Compilation errors in production code** — this skill only handles test-side issues
- **If the deleted feature needs test replacement, not just removal** — this skill only removes invalid entries; it does not write new tests for replacement behavior
