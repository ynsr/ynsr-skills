---
name: ftpctl
description: Safe FTP/FTPS/SFTP client wrapper CLI
---

# ftpctl

`ftpctl` transfers files over FTP/FTPS/SFTP via named profiles in `~/.config/ftpctl/profiles.toml` (0600). stdout carries data only (JSON default); errors go to stderr. Run `ftpctl <command> --help` for details.

## Setup

- `ftpctl profiles --sample > ~/.config/ftpctl/profiles.toml && chmod 600 ~/.config/ftpctl/profiles.toml` — reference config, then uncomment and fill in.
- `ftpctl profiles add --name X --protocol sftp --host H --username U` — interactive onboarding: missing flags prompt, live probe (connect+auth+list root) runs before writing, unknown SFTP key offers pinning after fingerprint verify.
- Secrets: only `${FTPCTL_*}` refs in username/password/host (e.g. `password = "${FTPCTL_X_PASSWORD}"`); set via env (`export FTPCTL_X_PASSWORD='...'`). Never in flags. Missing/empty var → exit 3.
- SFTP pins host keys via `known_hosts` (RejectPolicy, never AutoAdd): `ssh-keyscan -p <port> <host> >> ~/.config/ftpctl/known_hosts` after out-of-band fingerprint verify.

## Core Patterns

- Exit codes: 0 ok · 2 usage/config · 3 missing env var · 4 auth · 5 host key/cert · 6 network/timeout · 7 policy violation · 1 other.
- Read-only default: profiles are `readonly = true` unless explicitly disabled; `put` to a readonly profile is refused.
- All remotes confined under profile `root`; `--config` overrides the config path; `--output table|json|csv|tsv` on list-style commands.
- Size/listing caps guard transfers (`max_download_bytes`, `max_list_entries`).

## Commands

```bash
ftpctl profiles                                  # list profiles (no secrets)
ftpctl profiles add --name prod --protocol sftp --host sftp.example.com --username u --port 22 --no-input --yes
ftpctl check --profile prod                      # connect+auth+list root; reports failing step
ftpctl ls --profile prod /                       # list dir; --recursive, --limit N
ftpctl stat --profile prod /path/file.csv
ftpctl get --profile prod /remote.csv ./local.csv [--overwrite]
ftpctl put --profile prod ./local.csv /remote.csv [--overwrite]   # refused if readonly
```
