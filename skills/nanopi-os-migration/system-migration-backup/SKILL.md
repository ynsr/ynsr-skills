---
name: system-migration-backup
description: Use when planning to change, upgrade, reflash, or reinstall the OS on a Linux server, NAS, or SBC (e.g. OpenWrt/FriendlyWrt to Armbian, a distro hop, or an eMMC/SD reimage), and you need to back up the running apps, Docker images and volumes, configs, and cronjobs so they can be restored on the new OS.
---

# System Migration Backup

## Overview

Before a destructive OS change, inventory everything that runs on the box using **read-only** commands, present the list and a plan for **explicit user approval**, then build a backup bundle designed for easy restore on the target OS. Two hard rules:

1. **Never modify anything during discovery.** List first, get approval, back up second.
2. **The backup is self-documenting.** Generate a `README.md` describing each exported item and a `RESTORE-GUIDE-<target>.md` with step-by-step restore steps, and **copy them into the bundle beside the archives** so anyone can restore without the original session.

## When to Use

- Reflashing/replacing the boot OS (eMMC/SD reimage, OpenWrt→Armbian, distro switch).
- Need to protect whatever a reinstall will wipe from the **root filesystem** (configs, custom scripts, cron, users, service state).
- You want data/service definitions back up with minimal fiddling later.

**Not for:** copying one directory, rsyncing a single data folder, or backing up a lone database. Use ordinary backup tooling for those.

## Core Pattern

```
Discovery (read-only) → inventory + plan → user approval → build restore-friendly bundle
→ generate self-documenting .md files beside archives → verify (gzip -t, diff, counts)
```

## Phase 1 — Read-only Discovery

Run every command over SSH; capture for later. Sample command set (adjust to the box):

| Category | Command |
|---|---|
| Identity | `hostname; uname -a; cat /etc/os-release` |
| IP/tailnet | `ip -4 addr show; tailscale status` |
| Docker | `docker ps -a`, `docker images`, `docker volume ls`, `docker network ls`, `docker inspect` (ports/env/mounts) |
| Compose | `find /srv /opt /root -maxdepth 3 -iname 'docker-compose*.yml' -o -iname 'compose.yml' 2>/dev/null` |
| Services | `ls /etc/init.d/` or `systemctl list-units --type=service --state=running` |
| Configs | `ls -la /etc/config/` (OpenWrt), `/etc/docker/`, custom scripts in `/usr/bin`, `/root/*` |
| Cron | `crontab -l; cat /etc/crontabs/*` |
| Packages | `opkg list-installed` / `dpkg -l` / `rpm -qa` → save versions |
| **Proxy stack** | `/etc/config/{v2raya,passwall,smartdns,xray,sing-box}`, `/etc/docker/daemon.json` + `proxy.conf` (registry mirrors) |
| **Drives** | `blkid` (UUIDs!), `df -h`, `cat /etc/fstab` — identify what survives vs. what's wiped |

Check the package count, note which containers are local builds vs. public images (public ones can be re-pulled; local `build:` ones need their **Dockerfile** saved and an image tarball).

## Phase 2 — Approval Gate (REQUIRED)

Present a consolidated inventory + a proposed bundle location, then use `ask_user` for the decisions. Standard decision points:

1. **Bundle scope** — full bundle vs. core-only (configs/cron/scripts/docs vs. also root archive + image tarballs).
2. **Docker images** — custom/local images only, all in-use images, or none (re-pull later).
3. **Sensitive data** — tailnet/SSH identity state files, `/etc/shadow`, password DBs, shell history: include or exclude.

Also state explicitly what is **not** backed up because it's too large (e.g. media/shares that live on their own persistent drives) and will be re-mounted instead.

## Phase 3 — Restore-Friendly Bundle Structure

Number the folders so restore order is obvious; keep small configs **uncompressed** for browsing alongside **tarballs** for integrity. Example:

```
<backup-root>/<migration-to-target>/
├── 01-system-configs/   # /etc configs, cron, docker, tailscale state, users, custom scripts (plain copies)
├── 02-root-archive/     # /root essentials as one tar.gz
├── 03-appdata-projects/ # compose projects + Dockerfiles + Caddyfile + ssl (self-contained copy)
├── 04-docker-images/    # `docker save IMG | gzip > file.tar.gz` for offline restore
├── 05-inventory/        # text dumps: blkid, docker ps/images, crontab, package list, configs
├── README.md            # description of EVERY item
└── RESTORE-GUIDE-<target>.md  # step-by-step restore how-to
```

**Choose the backup root on a physical drive that survives the OS change** (a dedicated backup disk, not the rootfs being replaced). Record the drive UUIDs and warn the user not to format the data drives during install.

## Phase 4 — Self-Documentation (REQUIRED)

Generate two markdown files and **copy them inside the bundle, next to the archives** (e.g. via `scp`):

- **`README.md`** — a table describing each exported item/folder and what it contains (incl. secrets location warnings).
- **`RESTORE-GUIDE-<target>.md`** — a numbered, testable how-to for the target OS: re-mount drives by UUID in `/etc/fstab`, recreate users, install Docker + restore data-root, `docker load` the tarballs, `docker compose up -d` per project, restore cron, and a translation table for OpenWrt-only services → distro equivalents. End with a QA checklist and a rollback note.

## Phase 5 — Verify

Before reporting success:

```bash
for f in *.tar.gz; do gzip -t "$f" && echo "OK $f" || echo "FAIL $f"; done
diff -rq /etc/config $BUNDLE/01-system-configs/etc-config   # configs byte-identical
df -h <backup-root>; find $BUNDLE -type f | wc -l
```

Report total size, free space left, and verify the two `.md` docs are present in the bundle.

## Iranian / Sanctioned-Region Proxy Stack (bake these in)

Common on OpenWrt-based routers and SBCs (FriendlyWrt, Passwall) where public services are filtered. The Docker apps **depend** on this stack, so discover it, save it verbatim, and make the restore guide pin the exact ports.

**v2rayA rule-SOCKS — the linchpin.** Typically a local rule proxy on `127.0.0.1:20173`: Iranian destinations go direct, foreign traffic is proxied. Docker agents and JVM apps commonly reference it:

```yaml
environment:
  - ALL_PROXY=socks5://127.0.0.1:20173
  - http_proxy=socks5://127.0.0.1:20173
  - no_proxy=localhost,127.0.0.1,192.168.88.0/24
  - JAVA_OPTS=-DsocksProxyHost=127.0.0.1 -DsocksProxyPort=20173   # e.g. Bifrost
```

Restore on Armbian: `apt install v2raya`, reproduce the rule-SOCKS on the **same port**, and start it *before* the containers that use it — otherwise agent builds, `docker pull`, and LLM calls fail with connect errors.

**smartdns (port 53)** with server groups worth preserving: `domestic` (Iranian resolvers), `DoH` (dns.google, cloudflare-dns), `anti-sanction` (Shecan `178.22.122.100` / `185.51.200.2`), `adblock` (AdGuard `94.140.14.14`/`.15`). Save `/etc/config/smartdns`; rebuild with `smartdns` on the target.

**passwall (OpenWrt-only).** Subscriptions + server nodes live in `/etc/config/passwall` and are not portable to Debian. Extract the nodes/subscriptions from the saved config and re-create them as v2rayA / xray / sing-box on Armbian.

**Docker registry mirrors.** Public registries may be slow or blocked; typical boxes use `docker.arvancloud.ir` (also `mirrors.pardisco.co`). Save `/etc/docker/daemon.json` + `proxy.conf` and restore the mirror so `docker pull` still works pre-VPN.

Golden rule: save these configs and port numbers verbatim, and in the restore guide's service table list exactly which proxy port each container expects — the whole Docker stack collapses if the proxy isn't up on the same port.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Editing source during discovery | All discovery commands must be read-only; write nothing until approval |
| Backing up onto the rootfs being replaced | Use a drive that survives the reflash |
| Forgetting `blkid`/UUIDs | The restore mounts by UUID — always dump `blkid` |
| Local-build images with no registry copy | Always `docker save` local `build:` images and save their Dockerfiles |
| Backing up `/etc/config` (UCI) but no translation | UCI configs don't apply to Debian/Armbian — the guide must map them to distro equivalents |
| Finishing without `.md` docs in the bundle | The docs must live **beside the archives**, not just in the chat/session |
| Forgetting the proxy stack the containers depend on | Save v2rayA/passwall/smartdns configs + `daemon.json` mirrors, and pin the rule-SOCKS port in the restore guide |

## Real-World Impact

Built from a live NanoPi R6S OpenWrt→Armbian migration: the read-only inventory surfaced 4 Docker containers, ~17 images, 3 persistent data drives, a 45-file `/etc/config` tree, and 16 cron entries; the resulting 3.0 GB self-contained bundle (7 gzip-verified tarballs + 2 markdown guides) lets the user re-mount drives by UUID, `docker load` images, and `docker compose up` each project with no session context needed. It also records the v2rayA rule-SOCKS port (20173) that the agents and Bifrost depend on, plus the smartdns/passwall configs and the arvancloud registry mirror, so the proxy stack comes back intact.
