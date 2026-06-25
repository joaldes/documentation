# Power-Loss Boot Failure & Recovery — 2026-06-24

**Last Updated**: 2026-06-24
**Related Systems**: Proxmox host Shipyard, OWC Mercury Elite Pro Quad enclosure, CTs 102/104/105/124/128/130/131/132/134, GPU passthrough

## Summary
A Tucson power outage (~2026-06-23 19:00) left the USB enclosure's disks unavailable on the next boot. Because the enclosure mounts in `/etc/fstab` lacked `nofail`, systemd's "Timed out waiting for device" cascaded into `local-fs.target` failing and the host dropped to **emergency mode**. As an emergency measure the operator commented out the enclosure lines to boot on the internal NVMe. Recovery reattached the enclosure (all 10 filesystems came back **clean** — no repair needed), restored fstab with `nofail` + correct MergerFS ordering, and fixed two collateral failures (GPU passthrough and the PBS datastore mount). No data was lost.

## Problem / Goal
- Host would not boot normally after the outage; landed in emergency mode requiring the root password.
- Most of the data layer (`/mnt/documents`, `/mnt/docker`, `/mnt/hometheater`, `/mnt/pictures`, `/mnt/frigate`, `/mnt/backups`, `/mnt/birdnet`, `/mnt/pbs`) was offline.
- Two stopped services (Komodo CT 128, foundry CT 130) and Unmanic CT 105 failed to start with `TASK ERROR: /dev/dri/card0 is not a device`.
- CT 132 (garmin) failed to start. PBS backups were silently running without their datastore.

## Root Cause
The boot-blocker was **not** dirty disks — it was a **missing-device timeout**. With the enclosure absent and fstab entries lacking `nofail` (`pass=2`), each device wait failed its `mnt-*.mount` unit, which cascaded to `local-fs.target` → `emergency.target`.

Confirmed from `journalctl -b -2`:
```
Timed out waiting for device .../birdnet-data .../frigate .../documents .../docker ...
 → Dependency failed for mnt-*.mount
 → Dependency failed for local-fs.target - Local File Systems
 → Reached target emergency.target
```
No `I/O error` / `EXT4-fs error` / medium errors anywhere — the disks were **absent, not failing**. All 10 enclosure filesystems later reported `Filesystem state: clean`. Deeper cause: **no UPS** + a USB enclosure slow/flaky to re-enumerate on cold power-up. (Same OWC Mercury Elite Pro Quad as the [2026-01-21 Samba outage](2026-01-21-samba-usb-outage.md).)

## Solution
Reattach the enclosure, verify filesystems read-only, harden fstab with `nofail` so a missing/slow USB device degrades instead of blocking boot, and fix the two collateral failures.

## Implementation Details

### Steps Performed
1. **Pre-work safety** — stopped the two active-write/delete risks before remount so they couldn't act on empty mountpoints:
   ```bash
   pct stop 103   # Syncthing (deletion propagation risk on empty /mnt/documents,/mnt/pictures)
   pct stop 111   # urbackup (rw bind on empty /mnt/backups)
   ```
2. **Reconnect & identify** (read-only) — all four disks enumerated with no USB resets:
   ```bash
   lsblk -o NAME,SIZE,FSTYPE,UUID,MODEL,TRAN
   blkid
   ```
3. **Filesystem check** — superblock state first (fast), then a forced read-only check on the two critical infra filesystems:
   ```bash
   dumpe2fs -h /dev/sdX | grep 'Filesystem state'   # all => clean
   e2fsck -fn /dev/sdf4   # documents — clean
   e2fsck -fn /dev/sdf3   # docker — clean (only benign "extent tree could be shorter" notes)
   ```
   All clean → **no repair (`e2fsck -fy`) needed.**
4. **Restore fstab** — backed up, then uncommented every enclosure line with `nofail,x-systemd.device-timeout=30`. The MergerFS pool line additionally requires both branch mounts (the branches are siblings of the pool, so systemd won't otherwise order them first):
   ```
   /mnt/hometheater-disk1:/mnt/hometheater-disk2 /mnt/hometheater fuse.mergerfs \
     defaults,allow_other,use_ino,cache.files=partial,dropcacheonclose=true,category.create=mfs,\
     nofail,x-systemd.requires=/mnt/hometheater-disk1,x-systemd.requires=/mnt/hometheater-disk2 0 0
   ```
   ```bash
   cp -a /etc/fstab /etc/fstab.bak.$(date +%Y%m%d-%H%M%S)
   systemctl daemon-reload && findmnt --verify && mount -a
   systemctl start mnt-hometheater.mount   # mount -a rejects mergerfs 'nofail'; systemd handles it
   ```
5. **GPU passthrough fix (render-only)** — on this boot, kernel `simpledrm` grabbed DRM minor 0 (`card0`) before `i915`, so the Intel iGPU became `card1`; configs hardcoding `card0` failed (and LXC `create=file` left a junk 0-byte `card0`). Switched all six GPU containers to the stable render node only:
   ```bash
   rm /dev/dri/card0                                   # junk 0-byte file
   # 102/104/120: drop the lxc.mount.entry .../card0 line, keep renderD128
   # 105/128/130: dev0: /dev/dri/renderD128  (drop the card0 dev entry)
   ```
   `renderD128` (226,128) is stable and sufficient for Emby/Immich/Unmanic QSV/VAAPI. (PVE `dev0:` cannot use a `by-path` symlink — no destination option.)
6. **Restart consumers** — started the stopped, incident-affected CTs (132, 105, 128, 130, then 111, then 103 last). Running containers needed **no** restart — PVE LXC bind mounts propagate late host mounts, so they saw restored data live.
7. **Birdnet storage** — confirmed `is_mountpoint 1` present (no write-into-empty-dir risk).

### Enclosure Topology (OWC Quad, all ext4)
| Disk | Filesystem(s) | Mount |
|------|---------------|-------|
| sdd (16TB) | hometheater-d1 | `/mnt/hometheater-disk1` |
| sde (16TB) | hometheater-d2 | `/mnt/hometheater-disk2` |
| — | mergerfs `disk1:disk2` (29T) | `/mnt/hometheater` |
| sdf (20TB) | sdf1 frigate, sdf2 pictures, sdf3 docker, sdf4 documents, sdf5 birdnet | `/mnt/{frigate,pictures,docker,documents,birdnet}` |
| sdg (20TB) | sdg1 backups; sdg2 → VG `pbs` → `pbs-store` LV | `/mnt/backups`, `/mnt/pbs` (CT 134 datastore) |
| sdc (USB) | sdc1 container-backups; sdc2 → VG `ssd` | `/mnt/container-backups` + live guest storage |

### Key Files Modified
- `/etc/fstab` — enclosure lines uncommented with `nofail,x-systemd.device-timeout=30`; MergerFS line gets `x-systemd.requires=` both branches. Backup: `/etc/fstab.bak.20260624-210440`.
- `/etc/pve/lxc/{102,104,105,120,128,130}.conf` — GPU passthrough switched to render-only. Backups: `/tmp/<ctid>.conf.bak.*`.

## Verification
- `findmnt --verify` clean; all 10 filesystems + the 29T pool mounted; `pvesm status` shows every storage **active** (incl. `smb-hometheater` 31T, `pbs-homelab` 7.4T).
- `/mnt/documents` repopulated (github repo + system-inventory visible inside CT 124 with no restart).
- CTs 128/130/105 start cleanly (no `card0` error); Emby sees `renderD128`; CT 132 running.
- CT 134 PBS sees its real 7T datastore (`.chunks` present, services active) — backups protected.
- CT 101 AdGuard (DNS/DHCP) stayed up throughout (rootfs on internal NVMe, no pool dependency).

## Troubleshooting / Lessons
- **`nofail` is the boot fix, not fsck.** A missing/slow USB device with `pass>0` and no `nofail` fails `local-fs.target` → emergency mode. Every removable/USB mount needs `nofail,x-systemd.device-timeout=N`.
- **MergerFS branch ordering:** when branch mountpoints are siblings of the pool (not nested), add `x-systemd.requires=` for each branch or the pool can mount empty onto root at boot.
- **`mount -a` vs systemd for fuse.mergerfs:** `mount -a` errors `fuse: unknown option 'nofail'`; use `systemctl start mnt-<pool>.mount` (mirrors boot).
- **GPU `card0` renumber:** `simpledrm` can win DRM minor 0 before `i915`, shifting the iGPU to `card1`. Pass the stable `renderD128` only. Permanent fix (needs reboot): `initcall_blacklist=simpledrm_platform_driver_init` on the kernel cmdline (and drop the unused `i915.enable_gvt=1`).
- **LXC bind propagation:** PVE `mp` bind mounts propagate late host mounts into running containers — no restart needed to see remounted data. Verify before mass-restarting.

## Open Recommendations (not yet done)
1. **UPS on the Beelink host + the enclosure** with NUT → graceful `pveshutdown`. This is the real fix; `nofail` only stops dirty disks from blocking boot.
2. **USB-VG fragility:** the live `ssd` VG runs off a USB disk (sdc2); CTs 131/133/134 + VM 100 root off it, sharing the physical disk with the `container-backups` target → correlated failure. Interim: UPS + verified PBS backups of those guests (internal migration isn't possible — pools are full).
3. **Optional reboot proof-test** (with enclosure attached, then powered off) to confirm the hardened boot survives a missing enclosure.
