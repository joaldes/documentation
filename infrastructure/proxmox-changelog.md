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

```
/mnt/
├── backups           # sdd1 - Proxmox backups
├── docker            # LVM on sda - Container docker data
├── documents         # sde4 - Shared documents (1TB)
├── frigate           # sde1 - Frigate NVR data
├── hometheater       # mergerfs (sdb + sdc)
├── hometheater-disk1 # sdb - 14.6TB
├── hometheater-disk2 # sdc - 14.6TB
└── pictures          # sde2 - Photo storage
```

## Disks

| Device | Size | Label/Purpose | Notes |
|--------|------|---------------|-------|
| nvme0n1 | 500GB | OS/PVE root | Boot drive |
| sda | 2TB | littlestorage LVM | BX500 - ignore SMART 202 |
| sdb | 14.6TB | hometheater-disk1 | mergerfs member |
| sdc | 14.6TB | hometheater-disk2 | mergerfs member |
| sdd | 2TB | proxmox-backups | Backup storage |
| sde | 2TB | Multi-partition | frigate/pictures/docker/docs |

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
