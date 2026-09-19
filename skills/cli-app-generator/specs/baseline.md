# Baseline (measured 2026-09-19)

Reference point for the cli-app-generator v2 redesign. Re-measure at the end and report deltas.

## Metrics

| Metric | Baseline | Target (spec §1) |
|---|---|---|
| SKILL.md words | 1,846 | ≤ 1000 |
| Template non-test LOC | 1,793 | ≤ 1000 |
| — python-project | 1,249 | — |
| — python-single-file | 544 | — |
| Tests | 426 LOC / 29 passing | 29 passing after redesign (new equivalents for changed surface) |
| references/install-and-completion-internals.md | 154 lines | ≤ 100 |
| references/e2e-bash-testing.md | 162 lines | ≤ 100 |

Note: the spec §3 lists e2e-bash-testing.md at 164 lines; re-measured 162 (current working tree). Both over the cap either way.

## Measurement commands

```sh
# SKILL.md words
wc -w skills/cli-app-generator/SKILL.md

# Template non-test LOC (excludes tests/, .venv, caches, uv.lock)
wc -l skills/cli-app-generator/templates/python-project/src/mycli/*.py \
      skills/cli-app-generator/templates/python-project/{install.sh,uninstall.sh} \
      skills/cli-app-generator/templates/python-project/{pyproject.toml,README.md,AGENTS.md} \
      skills/cli-app-generator/templates/python-single-file/tool.py \
      skills/cli-app-generator/templates/python-single-file/{install.sh,uninstall.sh}

# Test LOC / passing count
wc -l skills/cli-app-generator/templates/python-project/tests/**/*.py
cd skills/cli-app-generator/templates/python-project && uv sync -q && uv run pytest -v

# Reference lines
wc -l skills/cli-app-generator/references/*.md
```

## Test evidence

```
$ cd skills/cli-app-generator/templates/python-project && uv sync -q && uv run pytest -v 2>&1 | tail -3
tests/unit/test_completions.py ...........                               [ 65%]
tests/unit/test_doctor.py ..........                                     [100%]
============================== 29 passed in 0.17s ==============================
```
