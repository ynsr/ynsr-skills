---
name: jalali-date-convert
description: Convert dates between Jalali/Shamsi/Persian calendar and Gregorian calendar. Trigger on any mention of Jalali, Shamsi, Persian date, Iranian calendar, تاریخ شمسی, g2j, j2g, "convert date", "today's Jalali date", "امروز چه تاریخیه", or when timestamps in logs/reports/DB need to be shown in or converted from the Persian calendar. Use whenever the user references a Shamsi date (e.g. 1403/06/15) or asks to convert to/from Gregorian.
---

# Jalali Date Convert

Convert dates between Jalali (Shamsi) and Gregorian calendars via the `g2j`, `j2g`, `today-jalali`, `now-jalali` shell functions.

## Installation

Requires `jdatetime` for at least one python:

```bash
pip install jdatetime
```

The script lives in this folder (`skills/jalali-date-convert/jalali-date-convert.sh`) inside the private repo `ynsr/cli-agents-config`, so it must come from your own checkout — a raw GitHub URL won't work for a private repo.

From anywhere inside your checkout, install it (the path is resolved relative to your current directory, no hardcoded path needed):

```bash
echo "source $PWD/skills/jalali-date-convert/jalali-date-convert.sh" >> ~/.bash_aliases
source ~/.bash_aliases
```

Or source it on demand without installing:

```bash
source skills/jalali-date-convert/jalali-date-convert.sh   # run from the repo root
```

The script resolves at call time which python can `import jdatetime` (python3.12, python3.11, then python3), so pip/python version mismatches don't break it.

## Usage

- Gregorian → Jalali: `g2j 2026-08-11` → `1405-05-20`
- Jalali → Gregorian: `j2g 1405-05-20` → `2026-08-11`
- Today in Jalali: `today-jalali`
- Now in Jalali (with time): `now-jalali`
