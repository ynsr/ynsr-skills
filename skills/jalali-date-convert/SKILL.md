---
name: jalali-date-convert
description: Shamsi/Gregorian date conversion
---

# Jalali Date Convert

Convert dates between Jalali (Shamsi) and Gregorian calendars via the `g2j`, `j2g`, `today-jalali`, `now-jalali` shell functions.

## Installation

Requires `jdatetime` for at least one python:

```bash
pip install jdatetime
```

Install from the raw GitHub source (functions appended to `~/.bash_aliases`):

```bash
_JCV=https://raw.githubusercontent.com/ynsr/ynsr-skills/main/skills/jalali-date-convert/jalali-date-convert.sh
curl -fsSL "$_JCV" >> ~/.bash_aliases
source ~/.bash_aliases
```

Or source it on demand, without persisting:

```bash
source <(curl -fsSL "$_JCV")
```

The script resolves at call time which python can `import jdatetime` (python3.12, python3.11, then python3), so pip/python version mismatches don't break it.

## Usage

- Gregorian → Jalali: `g2j 2026-08-11` → `1405-05-20`
- Jalali → Gregorian: `j2g 1405-05-20` → `2026-08-11`
- Today in Jalali: `today-jalali`
- Now in Jalali (with time): `now-jalali`
