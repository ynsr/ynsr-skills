# Restoring Services on Armbian (post-OpenWrt)

**Use case:** Migrating from OpenWrt/FriendlyWrt to Armbian/Debian while preserving Docker services, system data, and network configuration.

**Based on:** NanoPi R6S restoration (2026-08-20), FriendlyWrt 24.10.4 → Armbian/Debian.

---

## Key Principles

1. **Preserve the data drives.** Only re-flash the boot media (eMMC/SD). Never format `/dev/sda` or `/dev/sdb` — they contain all live data and the backup bundle.
2. **Re-use existing Docker data root.** Point Docker at the preserved `/srv/appdata/docker` (or equivalent) rather than rebuilding containers from scratch.
3. **OpenWrt UCI configs are reference only.** Armbian does not use UCI. Use them to re-create equivalent Debian services.
4. **Check everything after restoration.** Services may start but not function until dependent infrastructure (proxy, DNS, mounts) is also restored.

---

## Backup Bundle Structure

The backup bundle (typically at `/srv/appdata_backup/migration-to-armbian/`) contains:

```
01-system-configs/      # OpenWrt UCI configs, cron jobs, Docker daemon config, Tailscale state, scripts
02-root-archive/        # /root contents: syncthing config, v2rayA backups, geodata, compose projects
03-appdata-projects/    # Docker Compose projects (vaultwarden, agents, squid, jellyfin, etc.)
04-docker-images/       # docker save | gzip image tarballs
05-inventory/           # Text dumps: docker state, blkid, configs, packages, etc.
```

---

## Pre-Restoration Checklist

- [ ] Identify data drives and UUIDs (`blkid` from old system or `05-inventory/blkid.txt`)
- [ ] Identify Docker compose projects, images, and their mount points
- [ ] Identify system users (especially non-root service users like `shareuser`)
- [ ] Identify cron jobs (`05-inventory/crontab-root.txt`)
- [ ] Identify network services that need Armbian equivalents (Tailscale, Samba, Syncthing, v2rayA, etc.)
- [ ] Note any proxy/VPN dependencies (v2rayA SOCKS on port 20173, etc.)
- [ ] Note any host pinning in `/etc/hosts` (required for some upstream endpoints)
- [ ] Note which Docker images to exclude (e.g., Claude, Hermes)

---

## Step-by-Step Restoration

### 1. Mount Data Drives

```bash
# Add to /etc/fstab (use UUIDs from 05-inventory/blkid.txt, NOT device names)
UUID=<appdata-uuid>    /srv/appdata        ext4  rw,noatime,nodiratime,commit=30,errors=remount-ro  0 2
UUID=<media-uuid>      /srv/media          ext4  rw,noatime,errors=remount-ro                       0 2
UUID=<backup-uuid>     /srv/appdata_backup ext4  rw,noatime,nodiratime,commit=30,errors=remount-ro  0 2

mkdir -p /srv/appdata /srv/media /srv/appdata_backup
mount -a
```

**Verify:** `df -h | grep srv` shows all three mounted. `ls /srv/appdata_backup/migration-to-armbian` shows the bundle.

### 2. Install Docker + Compose

```bash
apt update && apt install -y docker.io docker-compose-v2
```

Point Docker at the preserved data root (from backup `01-system-configs/etc-docker/daemon.json`):

```bash
cp /srv/appdata_backup/migration-to-armbian/01-system-configs/etc-docker/daemon.json /etc/docker/daemon.json
# daemon.json should set: data-root /srv/appdata/docker/, storage-driver vfs
systemctl enable --now docker
docker info | grep "Docker Root Dir"   # Must show /srv/appdata/docker
```

**Gotcha:** If `daemon.json` specifies `"storage-driver": "vfs"`, ensure that driver is available. The `vfs` driver works everywhere but is slower and uses more disk.

**Gotcha:** If you also have a registry mirror configured (e.g., `docker.arvancloud.ir`), copy `proxy.conf` to `/etc/docker/` as well.

### 3. Recreate System Users

Extract UIDs/GIDs from the old `/etc/passwd` and `/etc/shadow` (in `01-system-configs/etc-essential/`):

```bash
groupadd -g 32771 shareuser
useradd -u 32771 -g 32771 -m -s /bin/bash shareuser
# Set password from old shadow entry, or use: passwd shareuser
```

Then fix ownership on media/share directories:
```bash
chown -R shareuser:shareuser /srv/media /srv/appdata/shares
```

**Verify:** `id shareuser` shows correct UID/GID.

### 4. Load Docker Images (Offline)

```bash
cd /srv/appdata_backup/migration-to-armbian/04-docker-images
# Load all images EXCEPT those you want to exclude (e.g., Claude, Hermes)
for f in squid-ssl-arm64-latest.tar.gz maximhq-bifrost-latest.tar.gz jellyfin-jellyfin-latest.tar.gz; do
    docker load -i "$f"
done
docker images
```

**Gotcha:** Some images may already exist from the preserved Docker data root. `docker load` will overwrite if the name/tag matches.

**Gotcha:** Do NOT load images you don't intend to run (e.g., `r6s-claude-latest.tar.gz` if excluding Claude).

### 5. Start Compose Projects

The projects on the SSD already have correct bind-mount paths. Start them in dependency order:

```bash
# Start proxy first if other services depend on it
cd /srv/appdata/agents/bifrost && docker compose up -d

# Then dependent services
for d in /srv/appdata/squid /srv/appdata/jellyfin/docker; do
    (cd "$d" && docker compose up -d)
done

docker ps   # expect: bifrost-gateway, squid-proxy, jellyfin
```

**Gotcha:** If a container already exists (from preserved Docker metadata), Compose will refuse to recreate it with "already exists" error. This is normal — the existing container is fine.

**Gotcha:** If a service depends on a proxy (e.g., SOCKS on port 20173), start the proxy first or accept that dependent services will log connection errors until the proxy is available.

### 6. Install and Configure Network Services

#### Tailscale

```bash
# Install from official Tailscale repository
curl -fsSL https://tailscale.com/install.sh | sh
# Restore saved state to keep the same node identity
cp /srv/appdata_backup/migration-to-armbian/01-system-configs/etc-tailscale/tailscaled.state /var/lib/tailscale/
systemctl enable --now tailscaled
tailscale up
```

**Verify:** `tailscale status` shows the node with its previous IP (e.g., `100.120.183.69`).

#### Samba

```bash
apt install -y samba
# Create shareuser in Samba password database (SEPARATE from system password)
smbpasswd -a shareuser
```

Add share definitions to `/etc/samba/smb.conf` or a custom include:

```ini
[media]
   path = /srv/media
   valid users = shareuser
   read only = no
   browseable = yes

[appdata]
   path = /srv/appdata
   valid users = shareuser
   read only = no
   browseable = yes
```

**Gotcha:** Samba passwords are separate from system passwords. Set them explicitly with `smbpasswd`.

**Verify:** `testparm` shows no errors. `smbclient -L localhost -U shareuser` lists shares.

#### Syncthing

```bash
apt install -y syncthing
systemctl enable --now syncthing@root
```

**Gotcha:** If the backup `.config/syncthing` directory was empty, Syncthing starts with a new identity and must be re-paired with other devices. There is no way to recover the old device ID.

#### v2rayA / V2Ray

**Step 1: Add the official repository**

```bash
# Install prerequisites
apt install -y curl gnupg2

# Add v2rayA GPG key and repository (check v2raya.org for current instructions)
curl -fsSL https://apt.v2raya.org/key/public-key.asc | gpg --dearmor -o /usr/share/keyrings/v2raya-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/v2raya-archive-keyring.gpg] https://apt.v2raya.org/ v2raya main" > /etc/apt/sources.list.d/v2raya.list
apt update
apt install -y v2raya v2ray
```

**Step 2: Start the service**

```bash
systemctl enable --now v2raya
```

**Step 3: Create admin account via web UI**

Access `http://<host>:2017` in a browser. Create the admin account (username/password).

**Step 4: Start the core via API**

```bash
# Authenticate and start the core
curl -s http://127.0.0.1:2017/api/login -d '{"username":"root","password":"<password>"}' -c /tmp/v2raya-cookie
curl -s http://127.0.0.1:2017/api/v1/service/start -b /tmp/v2raya-cookie
```

**Gotcha (v2rayA 2.4.x):** The core does NOT auto-start after upgrade from 2.2.x. You MUST authenticate and start it manually.

**Step 5: Install nftables if using transparent proxy**

If the restored config uses transparent proxy (`redirect` mode):

```bash
apt install -y nftables
systemctl enable --now nftables
# May need V2RAYA_NFTABLES_SUPPORT=on in v2raya environment
```

**Step 6: Copy geodata files**

```bash
# Copy from laptop or backup
scp laptop:/usr/share/v2raya/geoip.dat /usr/share/v2raya/
scp laptop:/usr/share/v2raya/geosite.dat /usr/share/v2raya/
scp laptop:/usr/share/v2raya/iran.dat /usr/share/v2raya/

# Verify hashes match source
sha256sum /usr/share/v2raya/{geoip,geosite,iran}.dat
```

**Step 7: Apply routing/DNS rules via API**

```bash
# Example: Set routing to direct private/Iranian traffic, proxy everything else
curl -s http://127.0.0.1:2017/api/v1/routingA -b /tmp/v2raya-cookie \
  -H 'Content-Type: text/plain' \
  -d 'default: proxy,,,protocol:chain,v2ray-protocol:vmess,v2ray-address:varzesh3.com:8080,...'
```

**Step 8: Add endpoint host pinning if needed**

If the upstream VLESS endpoint requires a specific IP:

```bash
# Backup first!
cp /etc/hosts /etc/hosts.bak-$(date +%Y%m%d)
# Add the pin
echo "185.143.232.201 varzesh3.com" >> /etc/hosts
# Restart v2raya to pick up the change
systemctl restart v2raya
```

**Gotcha:** Without DNS resolution for the endpoint, the proxy will fail with TLS EOF errors.

**Verify:**

```bash
# Test through SOCKS proxy
curl -x socks5://127.0.0.1:20173 https://httpbin.org/ip
# Should return HTTP 200 with a proxy IP, not your direct IP
```

### 7. Restore Cron Jobs

```bash
apt install -y cron && systemctl enable --now cron
# Edit root crontab
crontab -e
# Paste relevant entries from 05-inventory/crontab-root.txt
```

**Gotcha:** Remove OpenWrt-specific cron entries (e.g., Passwall monitors, OpenWrt-specific daemons) that have no Armbian equivalent.

### 8. Restore Monitoring Scripts

```bash
install -m 755 /srv/appdata_backup/migration-to-armbian/01-system-configs/usr-bin-scripts/*.sh /usr/local/sbin/
```

---

## Known Issues and Solutions

| Issue | Solution |
|---|---|
| SSH host key changed after reinstall | Accept new fingerprint; remove old known_hosts entry |
| Docker data root not recognized | Verify `daemon.json` points to correct path; restart Docker |
| Port 80 occupied by OMV nginx | Either stop nginx or drop the service that needs port 80 (e.g., Caddy/Vaultwarden) |
| Browser shows old cached web UI | Clear browser cache/service workers; not a server issue |
| v2rayA core won't start | Create admin account via web UI (port 2017); start core via API |
| v2rayA needs nftables | `apt install nftables`; enable nftables support in v2rayA config |
| Proxy TLS EOF | Check `/etc/hosts` for upstream endpoint pinning; verify DNS resolution |
| `/var/log` fills up (zram) | Truncate generated logs only (`truncate -s 0 /var/log/v2raya/v2raya.log`); do not delete databases or configs |
| Container already exists in Docker | Normal if preserved from old data root; Compose will not recreate it |
| Syncthing loses identity | Backup `.config/syncthing` must be non-empty; otherwise re-pair devices |
| v2rayA BoltDB → SQLite migration | v2rayA 2.4.x auto-migrates; legacy DB preserved as `bolt.db.bak` |

---

## Verification Checklist

After restoration, verify each item:

- [ ] All data drives mounted (`df -h | grep srv`)
- [ ] Docker data root correct (`docker info | grep "Docker Root Dir"`)
- [ ] All expected containers running (`docker ps`)
- [ ] Each container healthy (check logs: `docker logs <container>`)
- [ ] Tailscale node on tailnet (`tailscale status`)
- [ ] Samba shares accessible (`smbclient -L localhost -U shareuser`)
- [ ] v2rayA web UI accessible (`http://<host>:2017`)
- [ ] v2rayA core running (`curl -x socks5://127.0.0.1:20173 https://httpbin.org/ip`)
- [ ] Bifrost/gateway healthy and connected to proxy
- [ ] Cron jobs active (`crontab -l`)
- [ ] No stale OpenWrt-specific services running

---

## Rollback Safety

- Keep the old boot media (eMMC/SD) until restoration is fully verified.
- Data drives are never modified during restoration — they can be re-mounted on the old system at any time.
- Back up critical configs before changes:

```bash
# v2rayA
cp -a /etc/v2raya /etc/v2raya-backup-$(date +%Y%m%d-%H%M%S)

# /etc/hosts before adding pins
cp /etc/hosts /etc/hosts.bak-$(date +%Y%m%d)
```

---

## References

- **Backup bundle location on device:** `/srv/appdata_backup/migration-to-armbian/`
- **Detailed restore guide:** `RESTORE-GUIDE-armbian.md` (in the bundle)
- **Full inventory:** `05-inventory/` (blkid, docker state, configs, packages, etc.)
- **Migration report:** `RESTORE-REPORT-2026-08-20.md`
- **v2rayA docs:** https://v2raya.org/en/docs/
