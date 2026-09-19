# CHANGES

One line per removal/replacement during the v2 redesign: `- <what> → <replacement or "deleted"> : <one-line why>`. Appended during implementation; owner may veto any line before merge.

- templates/python-project/.venv → deleted : untracked build noise; regenerable via `uv sync`; caches now gitignored
- templates/python-project/.pytest_cache → deleted : untracked test cache; now gitignored
- templates/**/__pycache__ → deleted : untracked bytecode cache; now gitignored
- references/e2e-bash-testing.md → references/bash-testing.md : 162 lines, mostly git-fixture content unrelated to the skill; rewritten to a 90-line bats+e2e reference (Task 9)
- references/install-and-completion-internals.md → references/install-and-completion.md : 154 lines over the 100-line cap; rewritten to a 61-line reference, receipt/stale-guard content deleted per DECISIONS row C (Task 9)
- SKILL.md long-form install/receipt/completion prose → references/install-and-completion.md : receipts and stale-guard deleted per DECISIONS row C; SKILL.md cut 1846 → 881 words
- SKILL.md systemd prose → references/systemd.md : service mechanics moved out of the word budget; service scoped to Go tier (spec §2.4)
- SKILL.md e2e pointer + pipx install guidance → references/bash-testing.md + `uv tool install --editable .` : DECISIONS rows C/D; testing pattern now bash-testing.md
- SKILL.md `recovering-from-edit-thrash` bullet → deleted : spec §6 drop; unrelated to CLI generation
- SKILL.md Steps 1+2 (ask inputs / identify audience) → merged Step 1 ask-once : spec §6 batched single ask
- SKILL.md hand-rolled tier layout snippets (PEP 723, project tree, Go tree, pipx) → scaffold.sh command + references/stacks.md : scaffolder emits tier × audience skeletons (DECISIONS row F)
