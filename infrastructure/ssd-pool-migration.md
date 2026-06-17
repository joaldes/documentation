# SSD Pool Migration — Rescue Guests off Dying Crucial onto Samsung

**Last Updated**: 2026-06-16
**Related Systems**: Proxmox host Shipyard (192.168.0.151); CT 130/131/132/133, VM 100/119; storages `littlestorage` (Crucial), `ssd` (Samsung 870 QVO)

## Summary
The internal **Crucial BX500 2 TB** SSD (`/dev/sda`, VG/storage `littlestorage`) holding the live VM/CT pool was endurance-exhausted (SMART attr 202 *Percent_Lifetime_Remain* = `FAILING_NOW`, 100 % life used). All six live guests were migrated onto a **new `ssd` LVM-thin pool** carved from the empty ~839 GiB tail of the **Samsung 870 QVO 2 TB** (`/dev/sde`, USB-attached) — with **zero data loss and ~1.5 min total downtime** (HA only). The Crucial was left physically in place with retained fallback copies for a soak period.

## Problem / Goal
- **Crucial BX500** = DRAM-less QLC; died of write amplification (~281×) absorbing small/sync VM writes. `smartctl -H` still PASSED but attr 202 = FAILING_NOW → "replace promptly."
- It held all live guests: CT 130 foundry, 131 cartography, 132 garmin, 133 vpn, VM 100 Home Assistant, VM 119 WindowsTiny10 (~163 GB real data).
- **Goal:** get every live guest off the dying drive with minimal downtime and no data loss.

## Solution
The Samsung 870 QVO is a 2 TB disk but only its first 1 TB (`sde1`) was in use (`/mnt/container-backups`). The **~839 GiB tail was empty** → carve a new partition there, make it an LVM-thin pool, and move the guests in. No backup relocation, never touches the archive on `sde1`.

> **Note on the target drive:** the Samsung is also QLC, so under live VM I/O it projects to ~1.6 yr, not 5. Accepted knowingly (storage prices). Future fix = a TLC + DRAM (ideally enterprise w/ PLP) SSD in the freed internal SATA bay. A SMART attr-202 wear alert is the planned safeguard.

## Implementation Details

### Positive disk ID (critical — Samsung is behind a generic JMicron USB bridge)
The Samsung enumerates with a generic clone serial (`usb-JMicron_Generic_DISK00_0123456789ABCDEF`). Confirmed the real device via SAT passthrough before any write:
```bash
smartctl -i -d sat /dev/sde      # → Samsung SSD 870 QVO 2TB, S/N S6R4NJ0W101631J
```
Targeted everything by `/dev/disk/by-id/usb-JMicron_Generic_DISK00_0123456789ABCDEF-0:0` (stable across reboots), never `/dev/sdX`.

### Steps Performed
1. **Disable the nightly backup job** for the window (it writes to `sde1`, same physical disk):
   ```bash
   pvesh set /cluster/backup/backup-220f568d-ade5 --enable 0
   ```
2. **Carve the free tail** into a new LVM-thin pool. `sde1` is mounted so `partprobe` fails "device busy" — use `sgdisk` + `partx` to add *only* the new partition:
   ```bash
   ID=/dev/disk/by-id/usb-JMicron_Generic_DISK00_0123456789ABCDEF-0:0
   sgdisk --new=2:0:0 --typecode=2:8e00 --change-name=2:ssd-vm-pool "$ID"
   partx -a -n 2:2 "$ID"                 # NOT partprobe (sde1 busy)
   pvcreate "${ID}-part2"
   vgcreate ssd "${ID}-part2"
   lvcreate --type thin-pool -l 100%FREE -n data ssd   # -l 100%FREE avoids GiB/GB unit trap
   pvesm add lvmthin ssd --vgname ssd --thinpool data --content rootdir,images
   ```
3. **Move each guest, verifying it boots before the next.** `--delete 0` keeps the Crucial source as a fallback (`unusedN`).
   - **Containers (offline — rootfs must be stopped):**
     ```bash
     pct stop 130 && pct move-volume 130 rootfs ssd --delete 0 && pct start 130
     # repeat for 131, 132; CT 133 also: pct move-volume 133 mp0 ssd --delete 0
     ```
   - **VM 100 Home Assistant — scsi0 ONLINE (no downtime):**
     ```bash
     qm disk move 100 scsi0 ssd --delete 0       # live drive-mirror, HA stays up
     ```
   - **VM 100 efidisk0 — must be OFFLINE** (online fails: *"source and target image have different sizes"*). One brief stop:
     ```bash
     qm stop 100 && qm disk move 100 efidisk0 ssd --delete 0 ; qm start 100
     ```
   - **VM 119 (already stopped) — offline, exclude the raw USB passthrough `scsi1`:**
     ```bash
     qm disk move 119 efidisk0 ssd --delete 0
     qm disk move 119 tpmstate0 ssd --delete 0
     qm disk move 119 scsi0 ssd --delete 0
     ```
4. **Re-enable the nightly backup job:**
   ```bash
   pvesh set /cluster/backup/backup-220f568d-ade5 --enable 1
   ```

### Excluded from the move (intentionally)
| Guest | Excluded | Why |
|---|---|---|
| CT 130 | `mp4` /mnt/docker, `mp5` /mnt/documents | host bind-mounts (live on `sdf3` / samba) |
| CT 131 | `mp5` /mnt/docker | host bind-mount |
| CT 132 | `mp0` garmin-archive | host bind-mount |
| VM 119 | `scsi1` | raw Seagate USB passthrough (`/dev/disk/by-id/usb-Seagate_BUP_Slim_RD_...`) |
| — | `littlestorage-docker` 100 G LV | unmounted orphan on the Crucial (stale storage.cfg comment; real `/mnt/docker` = `sdf3`). Abandoned with the drive. |

## Verification
```bash
pvesm status | grep -E 'ssd|littlestorage'      # ssd active; guests' active volumes all off littlestorage
pct list ; qm list                              # all running (VM 119 intentionally stopped)
```
- All active guest volumes confirmed on `ssd`; foundry GPU (`/dev/dri`) intact; gis/garmin/HA/wg web endpoints returned HTTP 200; WireGuard `wg0` up with peer.
- `/mnt/container-backups` (`sde1`) untouched throughout.

## Performance Notes / Gotchas
- **Bottleneck = Samsung QLC write over USB (~14–23 MB/s, 100 % util), NOT the dying Crucial** (reads fine ~48 MB/s, ~46 % util). QLC bursts into SLC cache (~0.5 GB/s) then sags to native QLC speed once the cache saturates.
- **`qm disk move` copies all non-zero blocks, not just filesystem-"used".** VM 100's 100 G disk reported ~46 G "used" but the mirror copied ~96 G of un-TRIM'd deleted data → ~1h45m. (TRIM/`fstrim` inside guests before a move would shrink this.)
- **efidisk0 / tpmstate0 cannot move online** ("different sizes") — must be done with the VM stopped.
- **The drive may need `vgchange -ay ssd`** on a future host reboot if the USB `ssd` VG loses the enumeration race. Internal reseat (or TLC replacement) removes this USB window.

## Rollback
Every move used `--delete 0`, so each guest retains its original copy on `littlestorage` as an `unusedN` entry. To revert a guest: point its disk back at the `littlestorage:` volume and start. The Crucial is left in place during the soak; disable + pull later:
```bash
pvesm set littlestorage --disable 1     # after soak, before pulling the drive
```
