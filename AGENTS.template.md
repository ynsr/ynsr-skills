**Tradeoff:** Prefer caution over speed; use judgment and avoid padding trivial work.

## 1. Think Before Coding
**Be direct, proactive and critique the user requests, be not passive or reactive, and follow all rules below:**
- Proceed without confirmation on routine, low-risk decisions.
- Present multiple interpretations; never choose silently.
- Mention simpler approaches and push back when warranted.
- Flag risks, tradeoffs, and restrictions; suggest `dryRun` for high-risk or costly work.
- User asks to compare options? output the tradeoffs and risks of each option and recommend one.
- State assumptions and required information before planning or coding.
- Ask for clarification when requirements are ambiguous, conflicting, incomplete, or omit edge cases.
- Flag departures from best practices (of domain, design, pattern, or technology) and suggest reasoned alternatives. 

## 2. Goal-Driven Execution
Transform tasks into verifiable goals. For multi-step work, state a brief plan:
`1. [Step] → verify: [check]` `2. [Step] → verify: [check]`
- Validation: test invalid inputs, then make tests pass.
- Bug fix: reproduce with a test, then fix it.
- Refactor: test before and after.
- Run tests before declaring done.

## 3. During Work
- For multiple unrelated requests:
	- Identify priorities and dependencies.
	- Create a plan or todo list.
	- If possible, execute tasks in parallel
    - Use the main agent for simple tasks and sub-agents for complex ones.
	- After each task, review its changes before committing.
	- If Superpowers skills are loaded, prioritize them over this rule.
- Keep changes idempotent unless impossible by design.
- Add contextual logs at critical I/O and calculation points.
- Add integration tests for production changes.
- Fix bugs exposed by tests; don't hide them by altering tests.
- Update docs and tests, including `CHANGELOG.md` for changes. Keep documentation minimal, pros-free, and direct.
- Review all changes at the end, preferably using a sub-agent.
- Afterward, output 3 next steps and add/update comment on the related Jira/GitHub issue. On feature/bug/chore/improvement branches, auto-commit, push, and create an MR/PR to the default branch only after tests pass.
- Write issue comments and changelog entries for non-technical stakeholders: concise, clear, complete, and jargon-free.
- Never auto-commit on `develop`, `main`, `master`, or the default branch unless asked.
- Never respond in Chinese or any non-English language unless asked.
- **CHANGELOG.md:** Entries <= 150 chars. Append issue ID in brackets: `[123]`
- Never add a nested repository (`.git`) to an already tracked codebase.

## 4. Debugging
- Establish the root cause with evidence (stack trace, test output, or code inspection); turn guesses into checks first.
- List at least two plausible causes before choosing one.
- If a fix fails, re-diagnose from the new evidence; don't compound guesses.

## 5. Forbidden Directories (never read)
`target/` (except `generated-sources`), `build/`, `dist/`, `.gradle/`, `**/*.min.js`, `**/*.map`
