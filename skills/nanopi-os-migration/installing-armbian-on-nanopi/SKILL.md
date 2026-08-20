---
name: installing-armbian-on-nanopi
description: Use when installing or re-flashing Armbian (or another OS image) onto a NanoPi board (R1/R4S/R5S/R6S or other Rockchip boards) by self-flashing from the running OS over SSH, or helping with image verification, checksum discovery, eMMC identification, and first-boot setup
disable-model-invocation: true
user-invocable: true
---

# Installing Armbian on a NanoPi (self-flash over SSH)

Flash a new Armbian OS onto a NanoPi without any cables, by writing the image to
the eMMC from the currently running OS over SSH. This is the no-cables path that
works on R-series boards already booted from eMMC (e.g. FriendlyWrt/OpenWrt).
The same procedure applies when the target for the first boot is the SD card or
a recovery/Live environment — only the device you overwrite changes.

**Core principle:** confirm exactly which block device is the eMMC (`mmcblk*`),
prove the image is genuine, write it in one uninterrupted step, then reboot
immediately and get off the disk. Do all download/verify/decompress before the
write so the only thing between you and recovery is a single `dd`.

## When to use

- Migrating a NanoPi from FriendlyWrt/OpenWrt to Armbian (and its restore guide).
- Refreshing or recovering an Armbian install when you can still boot something.
- Any task where you must be sure you are writing the OS image to the **eMMC
  and NOT to a connected data SSD/HDD** (`sda`/`sdb`).

**When NOT to use this path:** if the board is unbootable (bricked), do not
self-flash — you cannot reach the OS over SSH. Use the recovery/bootstrap path
(maskrom + `rkdeveloptool`, or an SD card) instead.

## Safety and decisions

These are non-negotiable for a self-flash over SSH:

1. **Only overwrite the eMMC.** On R-series boards it is `mmcblk2`
   (`/sys/block/*/device/type` reports `MMC`); SATA/USB drives report `SD` or `SSD`.
   Connected data drives (here `sda`/`sdb` Toshiba/WD) must never be written.
2. **Prove the image is genuine before writing.** Verify SHA256 against the
   publisher's published checksum. If you cannot find the checksum, mount the
   decompressed image read-only and inspect `/etc/armbian-release` (BOARD,
   VERSION, KERNEL) before trusting it.
3. **Stage in `/tmp` (tmpfs)** and decompress there; confirm it fits. The only
   disk write is the `dd`. `/tmp` is RAM-backed and survives only until reboot.
4. **The running OS keeps no write lock on the eMMC it booted from** in practice
   on these boxes, but once you write the eMMC the running system's root reads
   start returning garbage. Plan to `sync` + `reboot -f` immediately, `exit 0`
   from your command, and accept the connection drop.
5. **Confirm the SSH session and ask before the irreversible `dd`.** A botched
   write forces cable/serial recovery. All data must live on drives you are NOT
   overwriting.
6. **Do not change the root password, network, or data drives during this skill**
   unless asked — those are restore steps, not install steps.

## Discover the board and image

Identify the SSH alias you can reach the device at and enumerate its disks:

```bash
# On the device (over SSH). Confirm BOTH type and size before writing.
lsblk -o NAME,SIZE,TYPE,TRAN,MOUNTPOINTS
for b in /sys/block/mmcblk*; do
  echo "$b $(cat $b/device/type 2>/dev/null) $(cat $b/size 2>/dev/null)"
done
free -h                      # RAM headroom for staging in /tmp
findmnt /tmp                 # confirm /tmp is tmpfs (RAM-backed)
```

Must-hold invariants:

| Probe | Expected on NanoPi R-series | Meaning |
|---|---|---|
| eMMC device | `mmcblk2`, `device/type == MMC` | THE target |
| Data drives | `sda`/`sdb` (`SD`/`SSD`/`HDD`) | NEVER write |
| `/tmp` | tmpfs, free space ≥ decompressed image | stage here |
| root device of running OS | `mmcblk2p*` (FriendlyWrt/OpenWrt root) | confirms eMMC is the boot disk |

If the running OS's root is on `mmcblk0`/`mmcblk1`, that is the eMMC you must
overwrite — use the number that actually maps to the `MMC` device.

## Pick the right Armbian image

Match the board + desired kernel + flavor, e.g. for a NanoPi R6S:

```text
Armbian_26.8.1_Nanopi-r6s_trixie_vendor_6.1.115-omv_minimal.img.xz
                        ^^^^^^             ^^^^^^^^^^   ^^^^
                        board              kernel       flavor
```

Notes:
- `-omv` is the OpenMediaVault kernel flavor; `minimal` / full are build types.
- The same `_minimal` images you may find in the standard archive are NOT the
  `-omv` builds. Do not assume the first archive listing you find is the flavor
  you downloaded — verify against the exact filename.

### Find the published checksum (including non-obvious flavors)

The naive paths often 404. Worked approach for an `-omv` R6S image:

```bash
# 1. The board's own download page lists published flavors (search its embedded
#    Next.js/RSC payload for the board name + "omv" / "minimal").
curl -fsSL "https://www.armbian.com/nanopi-r6s/" > /tmp/board.html
grep -oiE 'Trixie_(vendor_)?(minimal|full)[a-z_-]*' /tmp/board.html | sort -u

# 2. Fetch that flavor's short .sha. The short name below is what the page links:
curl -fsSL "https://dl.armbian.com/nanopi-r6s/Trixie_vendor_minimal-omv.sha"
# -> 28bd4fe4ee882fa996e62db1fb883a5df2a4f3827efdfc1db21e9a16e8929216

# 3. Compare to the local file:
sha256sum /path/to/Armbian_26.8.1_Nanopi-r6s_*_img.xz
```

Confirm the decompressed size fits your staging space:

```bash
xz -l /path/to/image.img.xz     # lists uncompressed size
```

## Transfer, verify, decompress

All of this happens before the write. Do the network + CPU work first so `dd`
is a single uninterrupted operation:

```bash
# local -> device
scp /path/to/Armbian_*.img.xz nanopi_r6s:/tmp/

# on device
ssh nanopi_r6s 'cd /tmp && sha256sum Armbian_*.img.xz'   # verify again on-device
ssh nanopi_r6s 'cd /tmp && xz -d Armbian_*.img.xz'        # decompress, check free space

# sanity-check it is a real Armbian image before touching the eMMC
ssh nanopi_r6s '
  export PATH=$PATH
  LOSETUP=$(losetup -f)
  losetup "$LOSETUP" /tmp/Armbian_*.img
  partprobe "$LOSETUP"
  # mount the rootfs partition read-only and read armbian-release
  mount -o ro "$LOSETUP"p1 /mnt 2>/dev/null || true
  cat /mnt/etc/armbian-release 2>/dev/null || echo "partition layout differs"
  umount /mnt; losetup -d "$LOSETUP"
'
# Expect BOARD=nanopi-r6s, VERSION, KERNEL=...-vendor-rk35xx
```

If the image mounts differently (offset/partlabel varies), the invariant to
check is `/etc/armbian-release` showing the right `BOARD` and a Rockchip kernel.

## Write the image to the eMMC

Do all of this in ONE command so nothing else runs in between, then reboot
immediately. Buckle the target by printing its type/size right before `dd`:

```bash
ssh -o ConnectTimeout=15 nanopi_r6s '
  set -e
  echo "== target check =="
  cat /sys/block/mmcblk2/device/type          # must be MMC
  lsblk -dno NAME,SIZE /dev/mmcblk2          # must be the eMMC size
  echo "== writing =="
  dd if=/tmp/Armbian_*.img of=/dev/mmcblk2 bs=4M conv=fsync status=progress
  sync && echo DD_OK
  sync
  exit 0
'
```

Then disconnect cleanly and remove power sequencing risk by rebooting with
nothing else in between:

```bash
ssh -o ConnectTimeout=15 nanopi_r6s 'sync; exit 0'   # may time out: it is rebooting
```

Expect: the eMMC is now mid-overwrite while the running OS boots/reads from it.
The connection will drop. `fdisk`/`lsblk` output may look like garbage or errors
right after the write — that is expected and confirms the OLD root is returning
corrupted reads. Get off the disk now; recover only via the data drives
(`sda`/`sdb`), which were never written.

## First boot: find it and set a password

The new OS uses DHCP by default (the old static/network config is gone with the
old OS). Armbian's first boot runs `armbian-firstlogin` on the console, so the
default root password `1234` applies over SSH until changed. Old static IP is
gone — scan for the new DHCP lease:

```bash
sleep 60   # give it time to boot
# assume your router is 192.168.88.1; adjust the prefix to your LAN
nmap -sn 192.168.88.0/24 2>/dev/null || \
  for i in $(seq 1 254); do (ping -c1 -W1 192.168.88.$i >/dev/null 2>&1 && \
    echo 192.168.88.$i up &); done; wait

# log in with the temporary default, then set a real password
ssh root@<NEW-IP>                  # password: 1234
passwd                             # set a strong password
hostnamectl set-hostname nanopi-r6s  # if you want a stable hostname
```

Confirm the OS identity and that the data drives survived with unchanged UUIDs:

```bash
ssh root@<NEW-IP> 'uname -a; . /etc/os-release; echo "$PRETTY_NAME"'
ssh root@<NEW-IP> 'blkid | grep -E "sda|sdb"'
```

Compare those UUIDs to the pre-migration inventory (e.g. `05-inventory/blkid.txt`
in the backup bundle) — they must be unchanged. Drive letters may swap between
the old and new OS; that is irrelevant because fstab/mounts use UUIDs.

## First boot: re-attach data drives (by UUID)

Add UUID mounts to `/etc/fstab` (adapt paths/options to the layout), create the
mount points, and mount — no formatting, no data changes:

```fstab
UUID=<appdata-uuid>  /srv/appdata        ext4  defaults,noatime,errors=remount-ro  0 2
UUID=<media-uuid>    /srv/media          ext4  defaults,noatime,errors=remount-ro  0 2
UUID=<backup-uuid>   /srv/appdata_backup ext4  defaults,noatime                    0 2
```

```bash
mkdir -p /srv/appdata /srv/media /srv/appdata_backup
mount -a
findmnt /srv/appdata /srv/media /srv/appdata_backup   # all three mounted
df -h | grep srv
```

## Common mistakes

| Mistake | Fix |
|---|---|
| Writing to `sda`/`sdb` instead of the eMMC | Always gate the `dd` on `device/type == MMC` and the `lsblk` size. Never write from a command that takes the target by position. |
| Trusting a checksum you cannot find | If the published `.sha` is elusive, mount the image read-only and read `/etc/armbian-release` before writing. A missing checksum is a stop, not 'good enough'. |
| Decompressing on the destination root disk | Use `/tmp` (tmpfs). Decompress after transfer, before `dd`, so the write is one contiguous step. |
| Running other commands between `dd` and `reboot` | Don't. `sync` then `reboot -f` (or `exit 0` after `sync`) immediately; treat the drop as success. |
| Assuming the old static IP survives | It does not. New OS uses DHCP. Scan the LAN for the new lease, then set a static IP / hostname as a follow-up step. |
| Leaving the default root password `1234` | Change it at first login. It is a documented factory default. |
| Assuming first archive listing == the flavor you downloaded | The `-omv` flavor lives under a short name on the board page, not in the main `_minimal` archive. Verify against the exact filename's `.sha`. |

## Completion contract

Do not report success until:

- `sha256sum` of the local image matches a published checksum (or the mounted
  image's `/etc/armbian-release` was read and showed the correct board/kernel).
- `dd` completed with `DD_OK`, and the new OS booted (confirmed via `uname` /
  `/etc/os-release` showing the target Armbian version, over SSH on the new IP).
- Every data drive's UUID is unchanged from the pre-migration inventory and, if
  restored, mounted by UUID.
- The default root password is no longer `1234` (or explicitly handed off to the
  user as a required next step).

Do not report that a static IP or services were restored if you only performed
the install — flag those as follow-up work rather than claiming completion.
