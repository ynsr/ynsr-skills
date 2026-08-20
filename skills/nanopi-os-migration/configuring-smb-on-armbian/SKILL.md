---
name: configuring-smb-on-armbian
description: Use when configuring authenticated Samba/SMB shares on Armbian or Debian, especially for mounted ext4 data folders, OpenMediaVault-generated smb.conf, shareuser credentials, Samba write-permission failures, or auto-mounting those shares on an Ubuntu desktop client
disable-model-invocation: true
user-invocable: true
---

# Configuring SMB on Armbian

Configure Samba as a standalone authenticated file server for mounted Armbian/Debian data volumes. This skill covers both plain Armbian and OpenMediaVault (OMV) hosts, including the important distinction between Samba's `read only` setting and the underlying Linux filesystem permissions.

## Safety and decisions

Before changing the host:

1. Confirm the intended server paths are mounted data filesystems, not empty mount-point directories:
   ```bash
   findmnt /srv/media
   findmnt /srv/appdata
   df -hT /srv/media /srv/appdata
   ```
2. Confirm the requested share names, users, and read/write policy.
3. Treat a writable share of an application-data tree as a security decision. It may expose secrets, databases, Docker metadata, TLS keys, and service configuration.
4. Never record the Samba password in a skill, report, shell history, command output, or commit. Use interactive `smbpasswd` or a protected credentials file.
5. Do not use `force user = root`, guest access, SMB1, or recursive `chown -R` on an application-data tree.

If the user wants only a data subdirectory writable, share that subdirectory instead of granting ACLs to the entire application tree.

## Discover the host

```bash
. /etc/os-release
printf '%s %s\n' "$ID" "$VERSION_ID"
command -v smbd || true
systemctl status smbd --no-pager || true
getent passwd shareuser || true
findmnt /srv/media || true
findmnt /srv/appdata || true
```

On Armbian, install the native packages if missing:

```bash
apt update
apt install -y samba acl
systemctl enable --now smbd
```

Do not replace an existing OMV-managed Samba installation with a hand-written configuration until the OMV path below has been considered.

## Create or verify the Unix and Samba user

The Unix account and the Samba passdb account are separate. The user must exist in both places:

```bash
id shareuser
# If it does not exist, create it with a UID/GID compatible with existing data.
# Do not invent a UID when mounted files already belong to a known numeric owner.

smbpasswd -a shareuser
smbpasswd -e shareuser
pdbedit -L | grep '^shareuser:'
```

`smbpasswd -a` prompts for the password twice. Never pass the password as a command-line argument.

## Configure plain Armbian/Debian Samba

Back up the current configuration before editing it:

```bash
install -d -m 700 /root/samba-backups
cp -a /etc/samba/smb.conf /root/samba-backups/smb.conf.$(date +%Y%m%d-%H%M%S)
```

Use SMB2 or newer and require authentication. Replace the paths and share names with the approved values:

```ini
[global]
    workgroup = WORKGROUP
    server role = standalone server
    security = user
    passdb backend = tdbsam
    map to guest = never
    server min protocol = SMB2
    disable spoolss = yes
    load printers = no

[media]
    path = /srv/media
    valid users = shareuser
    guest ok = no
    read only = no
    browseable = yes
    inherit acls = yes
    inherit permissions = yes
    create mask = 0664
    directory mask = 0775

[appdata]
    path = /srv/appdata
    valid users = shareuser
    guest ok = no
    read only = no
    browseable = yes
    inherit acls = yes
    inherit permissions = yes
    create mask = 0664
    directory mask = 0775
```

`read only = no` only makes the Samba share writable. The authenticated Unix process still needs write permission on every parent directory and file it modifies.

## Preserve shares on OpenMediaVault

OMV regenerates `/etc/samba/smb.conf`; direct edits are temporary. Keep custom shares in a separate root-owned file and load it through OMV's persistent SMB extra-options field.

Create `/etc/samba/smb.conf.custom` with the share sections from above. Keep it private:

```bash
install -o root -g root -m 600 /path/to/smb.conf.custom /etc/samba/smb.conf.custom
```

Set the OMV configuration without discarding its existing settings:

```bash
omv-confdbadm read conf.service.smb \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); d["extraoptions"]="include = /etc/samba/smb.conf.custom"; print(json.dumps(d))' \
  | omv-confdbadm update conf.service.smb -

omv-salt deploy run samba --no-color
```

Never edit the generated file as the primary fix. After deployment, verify that it contains the include and that the effective configuration contains the shares:

```bash
grep -n '^include = /etc/samba/smb.conf.custom' /etc/samba/smb.conf
testparm -s
```

## Grant actual write access

First inspect existing ownership and ACLs:

```bash
getfacl -p /srv/media /srv/appdata
find /srv/appdata -mindepth 1 -maxdepth 1 -printf '%M %u:%g %p\n' | sort
sudo -u shareuser test -w /srv/media && echo media-root-writable || echo media-root-denied
sudo -u shareuser test -w /srv/appdata && echo appdata-root-writable || echo appdata-root-denied
```

If the user explicitly approved writable access to the entire trees, grant an ACL rather than changing ownership. This preserves service ownership while granting `shareuser` access:

```bash
for root in /srv/media /srv/appdata; do
    setfacl -R -m u:shareuser:rwX "$root"
    find "$root" -xdev -type d -exec setfacl -m d:u:shareuser:rwx {} +
done
```

`rwX` grants read/write and directory traversal, while only adding execute permission to files that already had it. The default ACL on directories makes future content writable by `shareuser`. On very large trees this changes ACL metadata on many inodes; tell the user before starting and allow the command to finish.

For a safer application-data layout, grant ACLs only to a dedicated data directory, for example `/srv/appdata/shares`, and keep Docker/service directories protected. Do not claim that a share is fully writable until a real `shareuser` write test succeeds.

## Validate on the server

Run all applicable checks:

```bash
testparm -s
systemctl enable --now smbd
systemctl is-enabled smbd
systemctl is-active smbd
ss -ltn | grep -E ':(445|139)\b'
pdbedit -L | grep '^shareuser:'
```

Test the underlying filesystem as the Samba identity without leaving test files:

```bash
sudo -u shareuser sh -c 'touch /srv/media/.smb-write-test && rm /srv/media/.smb-write-test'
sudo -u shareuser sh -c 'touch /srv/appdata/.smb-write-test && rm /srv/appdata/.smb-write-test'
```

If using a large application tree, test one representative nested directory as well. These tests prove Linux permissions, not network authentication.

## Validate from an Ubuntu client

Install the client and mount with a password prompt:

```bash
sudo apt update
sudo apt install -y cifs-utils smbclient
sudo mkdir -p /mnt/r6s-media /mnt/r6s-appdata

sudo mount -t cifs //SERVER_IP/media /mnt/r6s-media \
  -o username=shareuser,vers=3.0,rw,uid=$(id -u),gid=$(id -g),file_mode=0664,dir_mode=0775

sudo mount -t cifs //SERVER_IP/appdata /mnt/r6s-appdata \
  -o username=shareuser,vers=3.0,rw,uid=$(id -u),gid=$(id -g),file_mode=0664,dir_mode=0775
```

The `uid`, `gid`, `file_mode`, and `dir_mode` options control how the mounted share appears locally; the server-side ACL remains the authority for access.

Test both the SMB session and writes:

```bash
smbclient //SERVER_IP/media -U shareuser -c 'ls'
smbclient //SERVER_IP/appdata -U shareuser -c 'ls'
touch /mnt/r6s-media/.ubuntu-write-test && rm /mnt/r6s-media/.ubuntu-write-test
touch /mnt/r6s-appdata/.ubuntu-write-test && rm /mnt/r6s-appdata/.ubuntu-write-test
```

Use the server's LAN IP for local clients or its reachable Tailscale IP for tailnet clients. Prefer IP addresses while troubleshooting hostname or mDNS resolution.

## Auto-mount the shares on an Ubuntu desktop client

For persistent desktop access, avoid boot-time hangs when the server is offline. Use a root-only credentials file plus systemd automount entries in `/etc/fstab`: the share mounts on first access, so login and boot are never blocked, and the mount simply re-triggers whenever the server is reachable again.

Create a root-only credentials file so mounting never prompts for a password:

```bash
sudo install -d -m 700 /etc/samba
sudo tee /etc/samba/credentials-SERVER >/dev/null <<'EOF'
username=shareuser
password=REPLACE_WITH_THE_REAL_PASSWORD
domain=WORKGROUP
EOF
sudo chmod 600 /etc/samba/credentials-SERVER
```

The password is intentionally not written in this skill; it belongs only inside the root-only file above.

Add one fstab line per share. Use the desktop user's numeric `uid`/`gid` (usually 1000) and the same `file_mode`/`dir_mode`/`vers` options as a working manual mount:

```fstab
//SERVER_IP/media   /mnt/r6s-media   cifs credentials=/etc/samba/credentials-SERVER,uid=1000,gid=1000,file_mode=0664,dir_mode=0775,vers=3.0,nofail,_netdev,x-systemd.automount,x-systemd.idle-timeout=60 0 0
//SERVER_IP/appdata /mnt/r6s-appdata cifs credentials=/etc/samba/credentials-SERVER,uid=1000,gid=1000,file_mode=0664,dir_mode=0775,vers=3.0,nofail,_netdev,x-systemd.automount,x-systemd.idle-timeout=60 0 0
```

- `credentials=` removes the login-time password prompt; keep the file root-only (0600).
- `nofail,_netdev` keep boot and login non-blocking when the server is unreachable.
- `x-systemd.automount` defers the mount until the folder is first accessed.
- `x-systemd.idle-timeout=60` drops idle connections and re-mounts on the next access, which reconnects cleanly after the server comes back online.
- `uid`/`gid`/`file_mode`/`dir_mode` only control local presentation; server-side ACLs still enforce real permissions.

Apply and test:

```bash
sudo umount -l /mnt/r6s-media /mnt/r6s-appdata 2>/dev/null || true   # only if previously mounted manually
sudo systemctl daemon-reload
ls /mnt/r6s-media >/dev/null && echo media-ok
ls /mnt/r6s-appdata >/dev/null && echo appdata-ok
systemctl is-active 'mnt-r6s\x2dmedia.automount' 'mnt-r6s\x2dappdata.automount'
findmnt /mnt/r6s-media /mnt/r6s-appdata
```

Optionally show the shares in the GNOME Files sidebar by appending to `~/.config/gtk-3.0/bookmarks` (no root needed):

```text
smb://SERVER_IP/media NanoPi media
smb://SERVER_IP/appdata NanoPi appdata
```

If the server's LAN IP can change, prefer a DHCP reservation, a stable Tailscale IP, or an `/etc/hosts` entry that both fstab and the bookmarks can use.

## Troubleshooting

| Symptom | Check |
|---|---|
| `mount error(13): Permission denied` | Password, `pdbedit`, `valid users`, and guest settings. |
| Share lists but writes fail | Server-side Unix ownership/ACLs; client mount modes cannot grant server permission. |
| `NT_STATUS_ACCESS_DENIED` in `smbclient` | `getfacl` and `sudo -u shareuser` write tests on the exact nested path. |
| Shares disappear after an OMV change | Confirm `/etc/samba/smb.conf` has the persistent custom include, then rerun `omv-salt deploy run samba`. |
| Port unreachable | Check `ss`, host firewall, router firewall, and whether the client is using LAN or Tailscale address. |
| Hostname does not resolve | Use `//SERVER_IP/share`; configure DNS or `/etc/hosts` separately. |
| Shares not mounted after login | Access the mount point to trigger the automount, confirm the credentials file is root-only (0600), then `sudo systemctl daemon-reload`. |
| Existing Docker/service behavior changes | Review ACL scope; do not use recursive `chown`; remove the `shareuser` ACL only with an explicit rollback plan. |

## Completion contract

Do not report completion until the effective Samba configuration passes `testparm`, `smbd` is enabled and active, the Samba user exists, the intended ports are listening, and a `shareuser` write test has passed for every requested writable share. Do not record the password in the completion report.
