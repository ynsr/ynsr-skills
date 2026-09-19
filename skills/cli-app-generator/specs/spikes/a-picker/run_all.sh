#!/usr/bin/env bash
# Spike A — reproducible driver. Run from this dir after `uv venv --python 3.14 .venv`
# and `uv pip install --python .venv/bin/python questionary prompt_toolkit iterfzf`.
set -u
PY=".venv/bin/python"

for p in probe_questionary.py probe_prompt_toolkit.py probe_prompt_toolkit_custom.py probe_iterfzf.py; do
  for m in t1 t2 t3; do
    echo "=== $m $p ==="
    "$PY" ptytest.py "$m" "$p"
  done
done

echo "=== UNWRAPPED questionary .ask() native defects ==="
"$PY" ptytest.py t1 probe_unwrapped.py
"$PY" ptytest.py t2 probe_unwrapped.py
"$PY" ptytest.py t3 probe_unwrapped.py

echo "=== prompt_toolkit eager-construction trap (app built outside session) ==="
"$PY" ptytest.py t1 probe_pt_eager_bug.py

echo "=== NO_COLOR=1 TERM=dumb (questionary) ==="
NO_COLOR=1 TERM=dumb "$PY" ptytest.py t1 probe_questionary.py
NO_COLOR=1 TERM=dumb "$PY" ptytest.py t3 probe_questionary.py
