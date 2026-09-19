# CHANGES

One line per removal/replacement during the v2 redesign: `- <what> → <replacement or "deleted"> : <one-line why>`. Appended during implementation; owner may veto any line before merge.

- templates/python-project/.venv + .pytest_cache + all __pycache__ under templates/ → deleted (hygiene, regenerable via `uv sync`) : untracked build noise; caches now gitignored
- references/e2e-bash-testing.md → scheduled for rewrite (Task 9, → bash-testing.md) : 162 lines, mostly git-fixture content unrelated to the skill; over 100-line cap
- references/install-and-completion-internals.md → scheduled for rewrite (Task 9, → install-and-completion.md) : 154 lines, over 100-line cap
