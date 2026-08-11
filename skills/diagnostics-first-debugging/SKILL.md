---
name: diagnostics-first-debugging
description: Use this skill for ANY bug, error, exception, failing test, crash, unexpected behavior, or "this isn't working" report in source code (Java/Spring Boot, React/Angular, Python, JS/TS, Bash, config, CI, infra-as-code, or any other language). Trigger even if the user asks you to "just fix it," "quickly patch," or sounds confident about the cause themselves. Trigger on regressions, intermittent/flaky failures, production incidents, build failures, and "works on my machine" issues. Do NOT trigger for pure feature requests, refactors, or greenfield code with no bug involved. If you catch yourself about to edit code in response to an error message before reading the actual failure context, that is the signal this skill should have fired.
---

# Diagnostics-First Debugging

**Rule: no fix or edit until you can state root cause AND the specific evidence (real stack trace, real test output, real code you read) that confirms it.** "Probably / likely / usually caused by" = a guess, not a diagnosis — if you write that phrase, turn it into a check instead of a fix.

## Workflow

1. **Get raw evidence first.** Full stack trace (not just the message), actual failing test output, the diff/commit before a regression if one exists, and whether it reproduces on demand or is intermittent. If the user only gave a prose symptom, ask for the raw artifact — paraphrases lose the detail that matters.

2. **List 2-4 plausible layers before picking one.** Don't fix the first plausible cause. Examples — Spring/Java: caller, method body, DI/bean wiring, transactions, connection pool, serialization, config/profiles, infra/JVM. React/Angular: state, props, async timing/race conditions, render cycle, build config, browser quirks.

3. **Find the cheapest check that discriminates between candidates** — log/breakpoint, targeted test, grep for call sites, or reading the actual library implementation instead of recalling it from memory (versions change defaults: Spring 2 vs 3, Jackson bumps, React 17 vs 18). If you have file/tool access, read code and run the failing test yourself rather than asking the user to paste things. Ask the user only for what you can't see yourself (live prod state, their env, timing-dependent repro).

4. **Narrow using only real, observed output** — never simulate or assume what a log/test "would probably show." Ambiguous evidence → find the next check, don't pick the most plausible remaining guess.

5. **State it before fixing:** "Root cause is X, confirmed by Y." If Y isn't something you actually observed, you're not done with step 4. Then apply the smallest fix that addresses the confirmed cause — not the smallest change that hides the symptom (e.g. a swallowing try/catch).

6. **If the fix fails, re-diagnose — don't stack a second guess on the first.** The failure is new evidence; go back to step 2 with it.

## Resist these specifically

- Pattern-matching to the "famous" cause (NPE → assumed missing null check) instead of checking which of several real causes (proxy/AOP null, config profile mismatch, etc.) actually applies.
- Trusting remembered library/framework behavior instead of checking the version actually in use.
- Presenting an unreproduced fix with the same confidence as a confirmed one — say explicitly if it's unverified.
- Caving to urgency: if pushed to skip diagnosis for speed, say so explicitly ("fast guess vs. confirmed fix — your call") rather than silently skipping checks.
- Ignoring blast radius: grep for other callers before changing shared code's behavior.

## With full codebase/tool access

Prefer gathering your own evidence over asking: grep all call sites before changing shared code, run the actual failing test, check git log/blame for what changed before a regression, read real config files instead of assuming defaults, reproduce with a script/test rather than reasoning from the trace alone. Only ask the user for runtime/environment state you genuinely can't observe.