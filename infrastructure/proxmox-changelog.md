# Proxmox Host Changelog

Custom configurations and changes to Shipyard (192.168.0.151).

---

## Host-Level Customizations

### smartd - `/etc/smartd.conf`
```
/dev/sda -a -I 202 -m root -M exec /usr/share/smartmontools/smartd-runner
```
- **Why**: Crucial BX500 SSDs have firmware bug causing false "FAILING_NOW" on attribute 202 (Percent_Lifetime_Remain)
- **Effect**: Ignores bogus lifetime counter, still monitors real health attributes
- ⚠ **STALE (2026-07-07)**: the Crucial BX500 was pulled in the Micron swap and `/dev/sda` is now the
  **Micron 5300**. This line now suppresses attr-202 on the healthy Micron (masking a real wear signal) →
  **slated for removal** (deferred cleanup, docs-only pass). See [ssd-pool-migration.md](ssd-pool-migration.md).

### rsyslog - `/etc/rsyslog.d/10-filter-acpi-rucc.conf`
```
:msg, contains, "UBTC.RUCC" stop
```
- **Why**: AZW SEi mini PC BIOS bug spams ACPI errors for USB-C ports
- **Effect**: Filters ~50 useless errors per boot from logs

### vzdump - `/etc/vzdump.conf`
```
tmpdir: /mnt/backups
exclude-path: /var/lib/docker /var/log/journal
```
- **Why**: Default tmpdir was /tmp (on NVMe), caused local storage to fill during backups
- **Effect**: Temp files go directly to backup drive

### LVM storage — `ssd` pool added, live guests migrated off Crucial (2026-06-16)
> ⚠ **SUPERSEDED 2026-07-07** by the Micron swap — VG `ssd` is now the internal **Micron 5300** (`/dev/sda`),
> not the Samsung QVO tail. The QVO is now `ssd_old` (rollback). Kept below for history. See the
> 2026-07-07 entry in the Change Log and [ssd-pool-migration.md](ssd-pool-migration.md).
```
lvmthin: ssd
	thinpool data
	vgname ssd
	# on /dev/disk/by-id/usb-JMicron_Generic_DISK00_0123456789ABCDEF-0:0-part2 (Samsung 870 QVO tail)
```
- **Why**: Crucial BX500 (`/dev/sda`, storage `littlestorage`) flagged failing — DRAM-less QLC with high write amplification + a pending sector. Moved all live guests (CT 130/131/132/133, VM 100/119) onto a new `ssd` LVM-thin pool carved from the empty ~839 GiB tail of the Samsung 870 QVO (`/dev/sde`).
- **Effect**: Live pool now on the Samsung; Crucial idle but still installed, holding retained `--delete 0` fallback copies. `littlestorage` still enabled (soak); disable + pull later.
- **Health verdict (full SMART pulled 2026-06-16)**: attr 202 `FAILING_NOW` is **REAL here**, not the BX500 false-positive — corroborated by attr 173 Ave_Block-Erase_Count = **2330** (far beyond QLC's ~1000-cycle rating) and a confirmed **~280× write amplification** (attr 248 FTL pages 336.3B ÷ attr 247 host pages 1.2B; host only wrote ~19.6 TB per attr 246). Drive is genuinely endurance-exhausted. Still PASSED with only 1 reallocated / 1 pending / 0 uncorrectable, so it's "replace promptly," not "corrupting now." **Recommendation: retire it — do not reuse for anything that matters** (worn QLC = poor data retention).
- **Full runbook**: [ssd-pool-migration.md](ssd-pool-migration.md)
- **Standing risk**: `ssd` VG is on a USB disk — may need `vgchange -ay ssd` after a future host reboot.

### Backups Mount - `/etc/systemd/system/mnt-backups.mount`
- **Path**: `/mnt/backups` (was /mnt/pve/backups)
- **Device**: `/dev/sdd1` (UUID: e424b756-df58-41b6-83fd-291525fc6e95)
- **Why**: Consolidated all mounts under /mnt/ for consistency


### Coral TPU - `/etc/udev/rules.d/99-coral-tpu-no-autosuspend.rules`
```
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", ATTR{idProduct}=="9302", TEST=="power/autosuspend_delay_ms", ATTR{power/autosuspend_delay_ms}="-1"
```
- **Why**: Coral TPU (used by Frigate) resets every 1-4 days due to USB autosuspend. Reset on 2026-01-09 preceded a system hang.
- **Effect**: Device stays powered (`autosuspend_delay_ms=-1`), no more periodic resets

---

## Container Standards

All LXC containers have:
- **AppArmor**: Disabled (`lxc.apparmor.profile: unconfined` in `/etc/pve/lxc/<CTID>.conf`)
  - Why: Ubuntu containers load 110+ desktop profiles, adds ~45s to boot
- **Root password**: `password`
- **Console**: Auto-login enabled
- **SSH**: Active

---

## Change Log

### SSD swap — guest tier onto internal Micron 5300 (2026-07-07)
- **Why**: The June stopgap left the live guest tier on QLC-over-USB (Samsung 870 QVO — fragile enumeration,
  ~1.6 yr projected life) and the boot NVMe (`local-lvm`) was ~97 % full.
- **Effect**: New **Micron 5300 MAX 1.92 TB** (TLC + DRAM + PLP) in the internal SATA bay → `/dev/sda`, VG
  `ssd`, thin pool `data`, now hosting **all** guest volumes (~24 LXC roots + VM 100/119 + Unmanic `/cache`).
  ~20 LXC roots moved off the NVMe → **97 % → 35 %**. Dying **Crucial BX500** pulled (VG `littlestorage`
  gone). Samsung QVO demoted to VG **`ssd_old`** (rollback, 7-day soak). Zero data loss. The window's cold
  power-off doubled as the sdd→`data` cold-reboot acceptance test — **PASS** (all 6 `data` mounts by UUID).
  **Not moved (stay on NVMe):** `pve/root`+`swap` and CT128 Komodo (busiest random-write overlay).
- **Deferred cleanup**: after the soak (~2026-07-14) `vgremove ssd_old`; remove the now-misdirected smartd
  `/dev/sda -a -I 202` line; `systemctl mask openipmi.service`.
- **Full runbook**: [ssd-pool-migration.md](ssd-pool-migration.md)

### 2026-01-09
- Disabled USB autosuspend for Coral TPU (18d1:9302) via udev rule
- Reason: Periodic resets were causing system hangs

### 2025-12-29
- Optimized jellystat-db PostgreSQL: synchronous_commit=off, wal_compression=on, checkpoint_timeout=15min
- Reduced jellystat sync interval from 60 to 240 minutes
- Optimized komodo-postgres-1: same PostgreSQL settings
- Result: jellystat writes reduced from 93GB to 104MB (99.9% reduction)

### 2025-12-24
- Moved backups mount from `/mnt/pve/backups` to `/mnt/backups`
- Updated vzdump tmpdir to `/mnt/backups`
- Fixed rsyslog config syntax (removed broken `and` rule)
- Added smartd ignore for BX500 attribute 202
- Disabled AppArmor on all containers
- Removed stale systemd mount units for non-existent UUIDs

### 2025-10-13
- Created rsyslog filter for ACPI UBTC.RUCC errors

---

## Storage Layout

> ⚠ **Device letters are NOT stable across reboots** — all LVM VGs and `/mnt` mounts assemble by UUID.
> The `sdX` labels below are the current (2026-07-07) enumeration; treat them as illustrative, not fixed.

```
/mnt/
├── backups           # sdf1        - Proxmox vzdump backups (ext4)
├── birdnet           # data VG LV  - /dev/mapper/data-birdnet
├── container-backups # sdd1        - LXC backups on the Samsung QVO (ext4)
├── docker            # data VG LV  - /dev/mapper/data-docker (container app data)
├── documents         # data VG LV  - /dev/mapper/data-documents
├── frigate           # data VG LV  - /dev/mapper/data-frigate (NVR footage, disposable)
├── hometheater       # mergerfs (sdb + sdc)
├── hometheater-disk1 # sdb         - 14.6TB
├── hometheater-disk2 # sdc         - 14.6TB
├── music             # data VG LV  - /dev/mapper/data-music
└── pictures          # data VG LV  - /dev/mapper/data-pictures
```
Guest disks (LXC roots + VM 100/119 + Unmanic `/cache`) live on VG **`ssd`** (Micron 5300, `/dev/sda`).
Host OS (`pve/root`+`swap`) and CT128 Komodo stay on the boot NVMe (`nvme0n1`, `pve`/local-lvm).

## Disks

*Current (2026-07-07) enumeration — letters shuffle across reboots; VGs are UUID-assembled.*

| Device | Size | Label/Purpose | Notes |
|--------|------|---------------|-------|
| nvme0n1 | 477GB | `pve` — OS/PVE root + local-lvm | Kingston; boot drive (~35% after guest-tier move) |
| sda | 1.75TB | `ssd` VG — guest tier | **Micron 5300 MAX**, internal SATA (TLC+DRAM+PLP) |
| sdb | 14.6TB | hometheater-disk1 | Seagate ST16000NM; mergerfs member |
| sdc | 14.6TB | hometheater-disk2 | Seagate ST16000NM; mergerfs member |
| sdd | 1.8TB | `ssd_old` VG (`sdd2`) + container-backups (`sdd1`) | Samsung 870 QVO (USB); swap rollback, 7-day soak |
| sde | 18.2TB | `data` VG — all fileshares | Seagate ST20000NT (frigate/pictures/docker/documents/birdnet/music) |
| sdf | 18.2TB | `pbs` VG (`sdf2`) + vzdump backups (`sdf1`) | Seagate ST20000NE |

*Retired 2026-07-07: Crucial BX500 (was `littlestorage`) physically pulled to free the internal SATA bay.*

---

## Docker PostgreSQL Optimizations (Container 128 - Komodo)

Both PostgreSQL databases on the Docker host have been optimized to reduce excessive disk I/O on the DRAMless BX500 SSD.

### jellystat-db (Jellyfin Statistics)
**File**: `/opt/stacks/jellystat/docker-compose.yml`

```yaml
jellystat-db:
  image: postgres:15.2
  command:
    - "postgres"
    - "-c"
    - "synchronous_commit=off"
    - "-c"
    - "wal_compression=on"
    - "-c"
    - "checkpoint_timeout=15min"
    - "-c"
    - "max_wal_size=1GB"
    - "-c"
    - "shared_buffers=256MB"
    - "-c"
    - "work_mem=16MB"
```

**Also changed**: PartialJellyfinSync interval from 60 to 240 minutes (in app_config table)

**Result**: Writes reduced from 93GB to 104MB (**99.9% reduction**)

### komodo-postgres-1 (Komodo/FerretDB)
**File**: `/opt/komodo/compose.yaml`

```yaml
postgres:
  image: ghcr.io/ferretdb/postgres-documentdb
  command:
    - "postgres"
    - "-c"
    - "synchronous_commit=off"
    - "-c"
    - "wal_compression=on"
    - "-c"
    - "checkpoint_timeout=15min"
    - "-c"
    - "shared_buffers=256MB"
    - "-c"
    - "work_mem=16MB"
```

**Result**: Expected 80-90% write reduction (48GB to ~5-10GB)

### Why These Settings

| Setting | Default | New | Effect |
|---------|---------|-----|--------|
| synchronous_commit | on | off | Batches commits, 80-90% fewer disk flushes |
| wal_compression | off | on | Compresses WAL writes ~30% |
| checkpoint_timeout | 5min | 15min | Less frequent checkpoints |
| shared_buffers | 128MB | 256MB | More memory caching |
| work_mem | 4MB | 16MB | Better query performance |

**Risk**: On crash, up to 0.5s of transactions may be lost. Acceptable for stats/management DBs.

**Rollback**: Backup files exist at *.bak-YYYYMMDD

### PBS backup scope + frigate config relocation (2026-07-01/02)
```
/usr/local/bin/pbs-fileshares-backup.sh   # + docker.pxar:/mnt/docker
/etc/komodo/stacks/frigate/compose.yaml   # /mnt/frigate/config → /mnt/docker/frigate/config (CT128)
```
- **Why**: `/mnt/docker` (245G of app state incl. all stack DBs) had no backup; Frigate's 64M config
  (camera setup, events DB) lived on the otherwise-ephemeral 1.5T footage share.
- **Effect**: Nightly 02:48 fileshares backup now covers pictures+documents+docker; frigate config
  relocated into `/mnt/docker/frigate/config` (compose volume edit + container recreate,
  3-agent-reviewed) so it rides in `docker.pxar` — `/mnt/frigate` is now 100% disposable footage.
  One-time 245G read absorbed in a 39-min nightly; steady-state back to minutes (metadata mode).
- **Also (2026-06-30)**: guest-job prune ACL fixed — `DatastorePowerUser` on `pve@pbs` + token
  (`DatastorePrune` is not a valid role name in this PBS version).
