#!/usr/bin/env bash
# Jalali <-> Gregorian date conversion helpers.
# Provides: g2j, j2g, today-jalali, now-jalali
# Requires: jdatetime installed for at least one python (pip install jdatetime)
#
# Source from ~/.bash_aliases (or ~/.bashrc):
#   echo 'source ~/projects/personal/cli-agents-config/skills/jalali-date-convert/jalali-date-convert.sh' >> ~/.bash_aliases

# Pick the first python that can import jdatetime (checks 3.12, 3.11, then
# default python3). Survives pip/python version mismatches, e.g. pip installing
# into python3.12 while `python3` is a different interpreter.
_py_with_jdatetime() {
    for _p in python3.12 python3.11 python3; do
        if command -v "$_p" >/dev/null 2>&1 && "$_p" -c "import jdatetime" >/dev/null 2>&1; then
            printf '%s\n' "$_p"
            return 0
        fi
    done
    return 1
}

# Usage: g2j 2026-08-11
g2j() {
    if [ -z "${1:-}" ]; then
        echo "Usage: g2j YYYY-MM-DD"
        return 1
    fi
    _py=$(_py_with_jdatetime) || {
        echo "jdatetime not found for any python (run: pip install jdatetime)" >&2
        return 1
    }
    "$_py" -c "
import jdatetime, datetime, sys
try:
    g = datetime.date.fromisoformat(sys.argv[1])
    j = jdatetime.date.fromgregorian(date=g)
    print(f'{j.year}-{j.month:02d}-{j.day:02d}')
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
" "$1"
}

# Usage: j2g 1405-05-20
j2g() {
    if [ -z "${1:-}" ]; then
        echo "Usage: j2g YYYY-MM-DD"
        return 1
    fi
    _py=$(_py_with_jdatetime) || {
        echo "jdatetime not found for any python (run: pip install jdatetime)" >&2
        return 1
    }
    "$_py" -c "
import jdatetime, sys
try:
    y, m, d = map(int, sys.argv[1].split('-'))
    g = jdatetime.date(y, m, d).togregorian()
    print(g.isoformat())
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
" "$1"
}

# Usage: today-jalali  (no args)
today-jalali() {
    _py=$(_py_with_jdatetime) || {
        echo "jdatetime not found for any python (run: pip install jdatetime)" >&2
        return 1
    }
    "$_py" -c "import jdatetime; print(jdatetime.date.today())"
}

# Usage: now-jalali  (with time)
now-jalali() {
    _py=$(_py_with_jdatetime) || {
        echo "jdatetime not found for any python (run: pip install jdatetime)" >&2
        return 1
    }
    "$_py" -c "import jdatetime; print(jdatetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))"
}
