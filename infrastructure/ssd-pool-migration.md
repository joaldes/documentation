# SSD Consolidation — Guest Tier onto Internal Micron 5300 (+ NVMe relief)

**Last Updated**: 2026-07-07
**Related Systems**: Proxmox host Shipyard (192.168.0.151); all LXC guests (roots) + VM 100/119; storages `ssd` (Micron 5300, internal SATA), `ssd_old` (Samsung 870 QVO — rollback), retired `littlestorage` (Crucial BX500, pulled)

> **History:** This doc has two chapters. **Chapter 2 (below, 2026-07-07)** is the current as-built state:
> the whole guest tier now lives on a new internal-SATA **Micron 5300**. **Chapter 1 (June 2026)** was the
> emergency stopgap that rescued the live guests off the dying Crucial BX500 onto the USB Samsung 870 QVO —
> kept at the bottom for context. The Micron swap is the "future fix" Chapter 1 itself pointed to.

---

## Summary
The entire VM/CT guest tier was consolidated onto a new **Micron 5300 MAX 1.92 TB** (TLC + DRAM + PLP)
installed in the host's internal SATA bay. In one overnight maintenance window (2026-07-06→07, checkpointed
host script) every guest volume — all ~24 LXC roots plus VM 100/119 disks and Unmanic's `/cache` — moved
onto the Micron (VG `ssd`, `/dev/sda`). The move also pulled ~20 LXC roots **off the boot NVMe**, dropping
it from **97 % → 35 %** full. The dying Crucial BX500 was physically removed to free the SATA bay; the
Samsung 870 QVO was demoted to VG `ssd_old` and kept as a rollback net for a 7-day soak. **Zero data loss.**
The window's cold power-off doubled as the acceptance test for the separate sdd→LVM `data` migration — all
six `data` shares auto-mounted from cold (**gate PASS**).

## Problem / Goal
Two storage weaknesses remained after the June stopgap (Chapter 1):
- **The live guest tier was on QLC over USB.** The Samsung 870 QVO is DRAM-less QLC (projected ~1.6 yr under
  live VM I/O) *and* attached over a JMicron USB bridge that loses the enumeration race on some reboots
  (needed manual `vgchange -ay ssd`). Not a durable home for the write-heavy guest tier.
- **The boot NVMe was ~97 % full.** ~20 LXC roots on `local-lvm` (the `pve` thin pool) had filled the OS
  drive to the danger zone.

**Goal:** put the guest tier on a proper endurance SSD (TLC + DRAM + PLP) in the *internal SATA* bay
(no USB), consolidate **all** guest roots there, relieve the NVMe, and retire the dead Crucial — with
minimal downtime and no data loss.

## Solution
- **Micron 5300 MAX 1.92 TB** → internal SATA bay (the slot freed by pulling the Crucial) → `/dev/sda`,
  new VG **`ssd`**, thin pool `data`.
- **Consolidate ALL guest roots**, not just the 9 that were on the old `ssd` pool: also migrate the ~20 LXC
  roots living on the boot NVMe's `local-lvm`. Combined real usage ~657 GiB on the 1.7 TiB Micron ≈ 38 %.
- **Deliberately NOT moved (stay on NVMe):** `pve/root` + `swap` (host OS, mandatory) and **CT128 Komodo** —
  its `/var/lib/docker` overlay is the busiest random-write surface and belongs on the fast NVMe (its
  persistent data is already bind-mounted to `/mnt/docker`).
- **Old Samsung QVO** kept intact as VG `ssd_old` (renamed, not wiped) = the rollback net for a 7-day soak.
- **Crucial BX500** physically pulled (its VG `littlestorage` held only unmounted orphans by then).

## Implementation Details

### Driver
The window was driven by a checkpointed, resumable host script **`/root/micron-migrate.sh`** (already-moved
volumes auto-skip on resume). Log: `/root/micron-migrate.log`. Pre-flight config tarball:
`/root/migration-pre-2026-07-06.tar.gz` (note: `/etc/pve/lxc` is a pmxcfs symlink → tar needs `-h`).
Destructive commands pinned to `/dev/disk/by-id/…`, never bare `sdX`.

### Phases
1. **poweroff** — `onboot: 0` on all migrating guests (prior values saved to `/root/onboot-before.txt`;
   running set to `/root/running-before.txt`); shut every guest down (CT134 PBS last); power the host off.
2. **gate (HARD GATE)** — on cold boot, verify all six `data` shares auto-mount by UUID. This *is* the
   acceptance test for the separate sdd→LVM `data` migration. **PASS** = proceed; else stop.
3. **setup** — positively ID the Micron by-id (`ata-Micron_5300_MTFDDAK1T9TDT_20302959B027`), SMART short
   self-test (clean), wipe, `pvcreate` → VG **`ssd_new`** → thin pool `data`.
4. **move** — `pct move-volume … ssd_new --delete 1` (+ MMP-clear) / `qm disk move` for VM 100/119
   (incl. `efidisk0`/`tpmstate0`, which move **offline** only). **29 volumes.** Exception: CT134's disk moved
   **without `--delete`** so its source copy survives on the QVO as an extra rollback.
5. **final** (ran **detached** via `nohup`, so it's absent from the main log) — move **CT124 last** (it's
   this container; moving it drops the live session), then `vgrename ssd → ssd_old` (`-an`) and
   `ssd_new → ssd`, flip storage IDs in guest configs (`ssd_new:` → `ssd:`), MMP-clear, restore `onboot`
   from `onboot-before.txt`, and start guests (CT134 first) from `running-before.txt`.
6. **verify** — see below.

## Verification (as-built, confirmed 2026-07-07)

| Check | Result |
|---|---|
| Micron placement | `/dev/sda`, internal SATA, VG `ssd`, 1.75 TiB, thin pool `data` |
| Guest volumes | All ~24 LXC roots + VM 100/119 + Unmanic `/cache` on VG `ssd` |
| Boot NVMe (`pve`/local-lvm) | **35.5 %** used (was ~92–97 %) |
| ext4 MMP on moved volumes | Cleared (no `mmp` feature) — no ~45 s/volume boot stall |
| QVO rollback | VG `ssd_old` (`/dev/sdd2`) holds drained old pool + `vm-134-disk-0` |
| `littlestorage` (BX500) | VG gone — drive physically pulled |
| Thread-A cold-reboot gate | **PASS** — all 6 `data` mounts auto-came-up by UUID |
| `onboot` | Restored (109/118/121 = 0, rest = 1) |
| Config flip | No live guest config references `ssd_new` or `littlestorage` |
| `/mnt/container-backups` | Mounted (QVO `sdd1`) — untouched |
| Guest health | Immich / Komodo / Paperless (and all others) healthy |

```bash
pvs                                   # /dev/sda→ssd, /dev/sdd2→ssd_old
lvs -o lv_name,data_percent pve       # local-lvm thin pool ~35%
pct list; qm list                     # all running (109/118/121/111 intentionally stopped)
```

## Gotchas
- **Device letters reshuffled on the cold reboot** — Micron took `/dev/sda`, the QVO shifted `sde`→`sdd`,
  the Seagate data disk `sdd`→`sde`, PBS disk → `sdf`. **LVM assembles by UUID so every VG came up correctly**
  regardless. Always target drives by `/dev/disk/by-id/` or UUID, never bare `sdX`.
- **The gate false-failed once** — it flagged `openipmi.service` (a harmless LSB IPMI init script; this board
  has no BMC) as a failed unit. The six storage mounts were all OK; operator re-ran → **PASS**.
- **The `final` phase ran detached** (nohup, so CT124's own move wouldn't kill it) and did **not** write back
  to `/root/micron-migrate.log` — the log ends at "move end." **Verify completion by system state, not the
  log tail** (VG rename present, CT124 rootfs on `ssd`, onboot restored).
- Old guidance still holds: `efidisk0` / `tpmstate0` can only move with the VM stopped.

## Rollback + Remaining Cleanup
- **Rollback net:** VG `ssd_old` (the Samsung QVO) is intact and still holds the drained pool + CT134's
  no-`--delete` copy. To revert a guest during the soak, point its disk back at an `ssd_old:` volume.
- **7-day soak → ~2026-07-14**, then close out:
  - `vgchange -an ssd_old` → `vgremove ssd_old` (relocate `/mnt/container-backups` off `sdd1` first).
  - Repurpose the QVO as USB secondary scratch; retire the pulled BX500 (worn QLC — do not reuse for
    anything that matters).
- **Deferred host fixes (docs-only this pass — NOT yet applied):**
  - Remove the smartd line `/dev/sda -a -I 202` from `/etc/smartd.conf` — `/dev/sda` is **now the Micron**
    (the BX500 that the `-I 202` ignore was written for is gone), so it would suppress a *real* wear signal.
  - `systemctl mask openipmi.service` so it stops showing failed (no BMC on this board; it's what
    false-tripped the gate).
- **Tidiness note:** immediately post-swap, `ssd_old` was left **active** (the rename used `-an` per the
  runbook but the LVs re-activated). Harmless; the `vgchange -an` above puts it back to a cold standby.

The Micron carries forward into the future tower build as the primary guest tier.

---

# Chapter 1 (historical) — June 2026 emergency stopgap: rescue guests off the dying Crucial onto the Samsung QVO

*Kept for context. This is the intermediate state the Micron swap (above) replaced.*

## Summary
The internal **Crucial BX500 2 TB** SSD (then `/dev/sda`, VG/storage `littlestorage`) holding the live VM/CT
pool was endurance-exhausted (SMART attr 202 *Percent_Lifetime_Remain* = `FAILING_NOW`, 100 % life used). All
six live guests were migrated onto a **new `ssd` LVM-thin pool** carved from the empty ~839 GiB tail of the
**Samsung 870 QVO 2 TB** (then `/dev/sde`, USB-attached) — with **zero data loss and ~1.5 min downtime**
(HA only). The Crucial was left in place with retained fallback copies for a soak. *(That `ssd`-on-QVO pool
is what the Micron swap later became VG `ssd` on the internal Micron; the QVO is now `ssd_old`.)*

## Problem / Goal (June)
- **Crucial BX500** = DRAM-less QLC; died of write amplification (~281×) absorbing small/sync VM writes.
  `smartctl -H` still PASSED but attr 202 = FAILING_NOW → "replace promptly."
- It held all live guests: CT 130 foundry, 131 cartography, 132 garmin, 133 vpn, VM 100 Home Assistant,
  VM 119 WindowsTiny10 (~163 GB real data).
- **Goal:** get every live guest off the dying drive with minimal downtime and no data loss.

## Solution (June)
The Samsung 870 QVO's first 1 TB (`sde1`) was in use (`/mnt/container-backups`); the **~839 GiB tail was
empty** → carve a new partition there, make it an LVM-thin pool, move the guests in. Never touches the
archive on `sde1`.

> **Note (June):** the Samsung is also QLC → ~1.6 yr under live VM I/O, accepted knowingly. **Future fix =
> a TLC + DRAM (ideally enterprise w/ PLP) SSD in the freed internal SATA bay.** ← *This is exactly what the
> 2026-07-07 Micron swap above did.*

### Positive disk ID (Samsung is behind a generic JMicron USB bridge)
The Samsung enumerates with a generic clone serial. Confirmed via SAT passthrough before any write:
```bash
smartctl -i -d sat /dev/sde      # → Samsung SSD 870 QVO 2TB, S/N S6R4NJ0W101631J
```
Targeted by `/dev/disk/by-id/usb-JMicron_Generic_DISK00_0123456789ABCDEF-0:0` (stable), never `/dev/sdX`.

### Steps Performed (June)
1. **Disable the nightly backup job** for the window (writes to `sde1`, same disk):
   ```bash
   pvesh set /cluster/backup/backup-220f568d-ade5 --enable 0
   ```
2. **Carve the free tail** into an LVM-thin pool (`sde1` mounted → `partprobe` fails busy; use `sgdisk`+`partx`):
   ```bash
   ID=/dev/disk/by-id/usb-JMicron_Generic_DISK00_0123456789ABCDEF-0:0
   sgdisk --new=2:0:0 --typecode=2:8e00 --change-name=2:ssd-vm-pool "$ID"
   partx -a -n 2:2 "$ID"                 # NOT partprobe (sde1 busy)
   pvcreate "${ID}-part2"; vgcreate ssd "${ID}-part2"
   lvcreate --type thin-pool -l 100%FREE -n data ssd
   pvesm add lvmthin ssd --vgname ssd --thinpool data --content rootdir,images
   ```
3. **Move each guest, verifying it boots before the next.** `--delete 0` keeps the Crucial source as a
   fallback (`unusedN`). Containers move offline (`pct stop … && pct move-volume … ssd --delete 0 && pct start`);
   VM 100 `scsi0` moved online (live mirror, HA stayed up); `efidisk0`/`tpmstate0` moved offline.
4. **Re-enable the nightly backup job:** `pvesh set /cluster/backup/backup-220f568d-ade5 --enable 1`

## Performance Notes / Gotchas (June)
- **Bottleneck = Samsung QLC write over USB (~14–23 MB/s, 100 % util), NOT the dying Crucial** (reads fine).
- **`qm disk move` copies all non-zero blocks, not just filesystem-"used"** — un-TRIM'd deleted data inflates
  the copy (VM 100's 100 G disk copied ~96 G). `fstrim` inside guests first shrinks it.
- **efidisk0 / tpmstate0 cannot move online** ("different sizes") — VM must be stopped.
- **`ssd` VG was on a USB disk** → sometimes needed `vgchange -ay ssd` after a host reboot. *(The Micron swap
  eliminated this — VG `ssd` is now internal SATA.)*
- **Health verdict (June):** attr 202 FAILING_NOW was **real** (attr 173 Ave_Block-Erase = 2330 vs QLC's
  ~1000 rating; ~280× write amplification). Genuinely endurance-exhausted → retire, do not reuse.
