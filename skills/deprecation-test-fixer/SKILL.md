---
name: deprecation-test-fixer
description: >
  Systematically fix test compilation failures caused by deprecating and deleting a feature, its DTO fields, enum values, or service methods. 
  Walks through diagnostic steps: collect all "cannot find symbol" errors, separate constant definitions from usage lines, 
  remove both, fix trailing commas introduced by the removals, then iterate until clean. 
  Handles the common patterns in Java/Spring Boot test suites with parametrized tests, constant-based error codes, and builder methods.
compatibility: >
  Java/Spring Boot projects with Maven or Gradle. Works with parametrized tests (@MethodSource, @CsvSource), constant-based error codes, 
  and test data builder methods. Principle applies to any statically-typed language (C#, TypeScript, Kotlin).
disable-model-invocation: true
user-invocable: true
---

# Deprecation/Deletion Test Fixer

When a feature is deprecated and its DTO fields, enums, or service methods are deleted, 
test files that reference them fail to compile. This skill provides a systematic workflow 
to fix all such failures by removing invalid test case entries — without modifying production code.

## The Pattern

The typical failure sequence (observed in Java/Spring Boot):

1. **Round 1** — `mvn test-compile` shows many `cannot find symbol` errors for constants or methods that referenced deleted DTO fields.
2. **Round 2** — After removing those constant definitions and their usage lines, a new `illegal start of expression` error appears — caused by a **trailing comma** on what is now the last argument in a `Stream.of(...)` or similar varargs call. Java does not allow trailing commas in method argument lists (unlike Python or JSON).

The fix is always **removal of test-side noise**, never changing source/production code.

## Workflow

### Step 1 — Run compilation and collect all errors

```bash
mvn test-compile 2>&1 | grep "cannot find symbol"
```

List every line number and the symbol name. Group them into:
- **Constant definitions** — `private static final String SOME_CONST = "...";` that referenced the deleted DTO field
- **Usage lines** — e.g., `arguments(newFooBuilder(...), someDeletedConstant),` in a `Stream.of(...)` block

### Step 2 — Identify the correct removal set

For each error, ask: does this reference the deleted feature? If yes:

- **Constant definitions:** remove the entire line.
- **Usage lines in parametrized test data:** remove the entire `arguments(...)` line.
- **Test methods that exclusively test deleted feature behavior:** remove the entire `@Test` method.

> **Important:** Check the file for *other* references to the same symbol before removing a constant definition. If the constant is used in multiple places, only remove the usage lines that reference it — keep the constant if still needed elsewhere.

Do not remove any line that tests a still-valid feature, even if it happens to sit next to deleted lines.

### Step 3 — Edit the file

Use a systematic approach — one-off `sed` commands risk mistakes with line numbers (which shift after each removal). The most reliable approach is a small Python script that reads the file, removes the specified lines, and writes it back:

```python
# Read file, identify lines to remove by pattern matching
# Remove both constant definitions and argument lines
# Handle trailing comma fix
# Write back
```

Alternatively, if you absolutely know the line numbers will not shift (e.g., all deletions are in one contiguous block at the end of a method), a single `sed` is fine:
```bash
sed -i 'START,ENDd' FileUnderTest.java
```

### Step 4 — Fix trailing commas

After removing lines from a `Stream.of(...)` or similar call, the last remaining argument may now have a trailing comma. Java rejects this:

```java
// BROKEN — trailing comma after removals
Stream.of(
    arguments(...),
    arguments(...),  // <-- this was followed by deleted lines, now it's last
);

// FIXED
Stream.of(
    arguments(...),
    arguments(...)  // <-- trailing comma removed
);
```

The fix: find the line that is now the last argument, and remove its trailing comma. The Python script approach should handle this automatically by detecting proximity to `);`.

### Step 5 — Recompile and iterate

```bash
mvn test-compile 2>&1 | grep -E "illegal start of expression|cannot find symbol"
```

If more errors appear, go back to Step 1. Common second-round errors:
- **Trailing comma** (most common) — fix as in Step 4.
- **Unused import** that only the deleted lines needed — remove the import.
- **Unused variable/field** that only the deleted lines referenced — remove it (but check if other tests use it).

### Step 6 — Verify final compilation

```bash
mvn test-compile 2>&1 | grep -E "BUILD SUCCESS|BUILD FAILURE"
```

Only proceed when BUILD SUCCESS is confirmed.

### Step 7 — Run the affected tests

Run only the specific test class(es) that were modified:

```bash
mvn test -Dtest="TestClassName" 2>&1 | tail -20
```

Check for:
- **BUILD SUCCESS** — test compilation and execution passed
- **Tests run: N, Failures: 0, Errors: 0** — all tests passed

If tests still fail at runtime (not compile time), the issue is different — the deleted feature's behavior may be referenced in test assertions or mock setups that compiled OK but fail at runtime. Apply normal root-cause debugging from there.

## Common Pitfalls

### Pitfall 1: Forgetting to check for other usages before deleting a constant

A constant like `earlySettlementPercentageInvalid` might be used in *multiple* test methods (e.g., both `registerPfTerminal` and `updatePfTerminal` data providers). Check all usages before removing the constant definition.

### Pitfall 2: Trailing comma after the second-last item, not the last

```java
Stream.of(
    arguments(...),  // deleted
    arguments(...),  // now last — has trailing comma -> ERROR
    arguments(...)   // deleted — but what if only this was deleted?
);
```

If you delete the *last* argument but keep the second-to-last, the second-to-last now needs its trailing comma removed. Always check which line is the final argument after your deletions.

### Pitfall 3: Line number shifts

Each deletion shifts all subsequent line numbers. If you plan multiple non-contiguous `sed` operations, apply them in *descending* line number order (highest first), so earlier deletions don't invalidate later line references. Or use the Python script approach which is idempotent to order.

### Pitfall 4: Commented-out lines

A commented-out line (`// arguments(...)`) is harmless — leave it alone. It does not cause compile errors and does not contribute to the trailing comma problem since Java ignores it.

### Pitfall 5: HashMap-based test data (not Arguments.of)

Some tests build data as Map entries:
```java
arguments(Map.of("code", "e", "sourceCreditClientCode", "e".repeat(101)), someErrorConstant),
```

Here the field reference is inside a Map literal string key, not a symbol. The error will be `cannot find symbol` on `someErrorConstant`, but the Map entry itself is fine and does not need removal (the field name is just a string key). Only remove the `arguments(...)` line if the error constant itself is deleted.

### Pitfall 6: Builder methods still having deleted parameters

Builder/helper methods (e.g., `newPfTerminal(...)`) may still have parameters named after deleted fields and pass them into Map literals. These compile fine as long as the parameters themselves are not removed from the method signature. **Leave builder method signatures untouched** — they are internal test helpers, and removing their parameters would cascade into every call site.

## Example trace (from a real session)

1. `mvn test-compile` → 10 `cannot find symbol` errors for `earlySettlementPercentageInvalid`, `maxEarlySettlementInvalid`, `percentageAndMaxEarlySettlementReq`
2. Found 3 constant definitions + 5 usage lines in `provideInvalidRegisterPfTerminalData()` + 5 usage lines in `provideInvalidUpdatePfTerminalData()` = 13 lines to remove
3. After removal → 1 `illegal start of expression` at the trailing comma on the `activeSettlementIbanInvalid` line (now the last argument)
4. Removed trailing comma → `mvn test-compile` → BUILD SUCCESS
5. `mvn test -Dtest="TerminalAdminControllerIT"` → all 10 previously failing tests passed

**Root cause:** DTO fields `earlySettlementMaxAmount` and `earlySettlementPercentage` were deleted from the terminal DTOs, but test constants referencing their validation error codes, and argument lines using those constants in parametrized test data providers, were not updated to match.

## When not to use this skill

- **Runtime test failures** (tests compile but fail at runtime) — use systematic debugging instead
- **Compilation errors in production code** — this skill only handles test-side issues
- **If the deleted feature needs test replacement** (not just removal) — this skill only removes, does not write new tests
