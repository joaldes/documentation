# UrBackup Server Setup Documentation

**Date**: 2026-01-16
**Author**: Claude AI
**Status**: In Progress

---

## Overview

UrBackup is deployed to back up:
- Local Proxmox host partitions (pictures, documents, docker, frigate)
- 3 Windows PCs on the network

## Infrastructure Summary

### Storage Layout

| Disk | Device | Size | Mount Point | Purpose |
|------|--------|------|-------------|---------|
| Seagate 20TB | sdf1 | 10TB partition | /mnt/backups | UrBackup storage |
| Seagate 20TB | sdf2 | ~8TB | (unused) | Future expansion |
| Generic USB | sdb1 | 1TB | /mnt/container-backups | Proxmox vzdump |
| Seagate 18TB | sde | 18TB | Multiple partitions | Source data |

### Source Data Partitions (on sde)

| Partition | Size | Mount Point | Used | Content |
|-----------|------|-------------|------|---------|
| sde1 | 1TB | /mnt/frigate | 478GB | Frigate NVR recordings |
| sde2 | 10TB | /mnt/pictures | 2.2TB | Photo archive |
| sde3 | 2TB | (unused) | - | Reserved |
| sde4 | 937GB | /mnt/documents | 193MB | Documents |
| LVM | 98GB | /mnt/docker | 26GB | Docker application data |

### Container Details

| Setting | Value |
|---------|-------|
| Container ID | 111 |
| Hostname | urbackupserver |
| IP Address | 192.168.0.208 (DHCP) |
| Web UI | http://192.168.0.208:55414 |
| OS | Debian (tteck community script) |
| Resources | 1 core, 1GB RAM, 16GB root disk |
| Created By | tteck Proxmox community script |

---

## Configuration Changes Made

### 1. Disk Partitioning (sdf)

Partitioned /dev/sdf (18.2TB) on Proxmox host:
- Partition 1: 10TB for UrBackup (ext4, label: urbackup-data)
- Partition 2: ~8TB reserved for future use

```bash
# Commands executed:
parted /dev/sdf --script mklabel gpt
parted /dev/sdf --script mkpart primary ext4 0% 10TiB
parted /dev/sdf --script mkpart primary ext4 10TiB 100%
mkfs.ext4 -L urbackup-data -m 0 -T largefile4 /dev/sdf1
```

### 2. Mount Point Reorganization

**Before:**
- /mnt/backups → sdb1 (Proxmox vzdump, 1TB)
- /mnt/urbackup → sdf1 (new, 10TB)

**After:**
- /mnt/backups → sdf1 (UrBackup, 10TB)
- /mnt/container-backups → sdb1 (Proxmox vzdump, 1TB)

**Rationale:** User preferred /mnt/backups for UrBackup to match naming conventions.

### 3. Files Modified

#### /etc/fstab (Proxmox Host)
Added entries:
```
# UrBackup Storage (10TB)
UUID=702673ce-559f-4c1c-866c-f44ff415e421 /mnt/backups ext4 defaults,noatime,nodiratime 0 2

# Proxmox Backups (vzdump, images)
UUID=e424b756-df58-41b6-83fd-291525fc6e95 /mnt/container-backups ext4 defaults,noatime 0 2
```

#### /etc/systemd/system/mnt-backups.mount (Proxmox Host)

**IMPORTANT**: This systemd mount unit file exists and takes precedence over fstab. If the wrong disk is mounted at `/mnt/backups`, check this file first.

```ini
[Unit]
Description=Mount backups storage

[Mount]
What=/dev/disk/by-uuid/702673ce-559f-4c1c-866c-f44ff415e421
Where=/mnt/backups
Type=ext4
Options=defaults

[Install]
WantedBy=multi-user.target
```

**UUIDs Reference:**
- `702673ce-559f-4c1c-866c-f44ff415e421` = sdf1 (10TB) — **Correct** for UrBackup
- `e424b756-df58-41b6-83fd-291525fc6e95` = sdd1 (1TB) — Proxmox vzdump backups

After modifying this file, run:
```bash
systemctl daemon-reload
systemctl restart mnt-backups.mount
```

#### /etc/pve/storage.cfg (Proxmox Host)
Modified storage entries:
```
dir: backups
    path /mnt/backups
    content snippets
    is_mountpoint 1
    nodes Shipyard
    shared 0
    prune-backups keep-all=1

dir: container-backups
    path /mnt/container-backups
    content rootdir,images,snippets,vztmpl,iso,backup
    is_mountpoint 1
    nodes Shipyard
    prune-backups keep-daily=7,keep-weekly=4,keep-monthly=3
```

#### /etc/pve/lxc/111.conf (Container Config)
Added mount points and settings:
```
# Startup order (after storage mounts are ready)
startup: order=10

# AppArmor disabled
lxc.apparmor.profile: unconfined

# Backup storage (RW)
mp0: /mnt/backups,mp=/mnt/backups

# Source data (RO) - mirror host paths
mp1: /mnt/pictures,mp=/mnt/pictures,ro=1
mp2: /mnt/documents,mp=/mnt/documents,ro=1
mp3: /mnt/docker,mp=/mnt/docker,ro=1
mp4: /mnt/frigate,mp=/mnt/frigate,ro=1
```

#### /var/urbackup/backupfolder (Inside Container)
Changed from `/opt/urbackup/backups` to `/mnt/backups`

---

## UrBackup Server Configuration

### Backup Directory
- Path: `/mnt/backups`
- Ownership: urbackup:urbackup
- Size: 10TB available

### Backup Intervals (Global Defaults)
| Setting | Value | Seconds |
|---------|-------|---------|
| Incremental File Backup | Every 12 hours | 43200 |
| Full File Backup | Every 7 days | 604800 |
| Incremental Image Backup | Every 7 days | 604800 |
| Full Image Backup | Every 30 days | 2592000 |

### Authentication
- **Status**: No admin user configured (user chose to skip for now)
- Web UI is currently open without authentication

### Service Status
- Service: urbackupsrv
- Status: Running
- Auto-start: Enabled

---

## Mount Points Inside Container 111

All paths mirror host paths for simplicity:

| Container Path | Host Path | Access | Size Used |
|----------------|-----------|--------|-----------|
| /mnt/backups | /mnt/backups | RW | ~0 (empty) |
| /mnt/pictures | /mnt/pictures | RO | 2.2TB |
| /mnt/documents | /mnt/documents | RO | 193MB |
| /mnt/docker | /mnt/docker | RO | 26GB |
| /mnt/frigate | /mnt/frigate | RO | 478GB |

---

## Planned Backup Structure

```
/mnt/backups/urbackup/clients/
├── urbackupserver/           ← Local partition backups
│   ├── Pictures/             (2.2TB)
│   ├── Documents/            (193MB)
│   ├── Docker-Data/          (26GB)
│   └── Frigate/              (478GB)
├── WINDOWS-PC-1/             ← Windows client
├── WINDOWS-PC-2/             ← Windows client
└── WINDOWS-PC-3/             ← Windows client
```

---

## Remaining Tasks

### Not Yet Completed:
1. [ ] Install UrBackup client inside container (for local backup paths)
2. [ ] Add local backup directories (pictures, documents, docker, frigate)
3. [ ] Deploy Windows client agents on 3 PCs
4. [ ] Configure per-client retention policies
5. [ ] Set up admin user authentication
6. [ ] Configure email alerts (optional)

### Retention Policy Plan (Per Client Type)

| Data | Incremental | Full | Retention |
|------|-------------|------|-----------|
| Pictures | 7 days | 90 days | 4 full, 8 incr |
| Documents | 4 hours | 7 days | 8 full, 42 incr |
| Docker | 2 hours | 1 day | 14 full, 24 incr |
| Frigate | 24 hours | 30 days | 2 full, 7 incr |
| Windows Files | 12 hours | 7 days | 4 full, 14 incr |
| Windows Images | 7 days | 30 days | 3 full, 4 incr |

---

## Storage Capacity Analysis

### Source Data (Actual Usage)
| Source | Used |
|--------|------|
| Pictures | 2.2TB |
| Documents | 193MB |
| Docker | 26GB |
| Frigate | 478GB |
| Windows (3 PCs est.) | ~300GB |
| **Total** | **~3TB** |

### With Retention (Estimated)
| Source | Estimated |
|--------|-----------|
| Pictures | ~3TB |
| Documents | ~500MB |
| Docker | ~200GB |
| Frigate | ~700GB |
| Windows | ~600GB |
| **Total** | **~5TB** |

**Conclusion**: 10TB partition is sufficient with ~5TB headroom.

---

## Network & Ports

### UrBackup Server Ports
| Port | Protocol | Purpose |
|------|----------|---------|
| 55414 | TCP | Web UI |
| 55415 | TCP | Client connections |
| 35623 | UDP | Client discovery |

### Container Network
- IP: 192.168.0.208 (DHCP assigned)
- Gateway: 192.168.0.1
- DNS: 192.168.0.11 (AdGuard)

---

## Troubleshooting Notes

### fstab Incident
During configuration, /etc/fstab was accidentally emptied by a sed command. Restored from backup:
- Backup used: `/etc/fstab.backup-20251117-230812`
- Resolution: Restored and added correct entries for both backup mounts

### Password Hash Issue
Initial attempt to create admin user via database failed (wrong hash format). User elected to skip authentication setup for now.

---

## Related Services on Proxmox Host

### Media Processing (Caused Disk Activity)
- **Bazarr**: Subtitle management, uses ffmpeg for audio sync
- **Unmanic**: Media transcoding/processing
- **Emby**: Media server (Container 102)
- **Frigate**: NVR for camera recordings

### External USB Drives
All storage except nvme0n1 (system) and sda (SSD) are USB-connected:
- sdb, sdc, sdd, sde, sdf are all USB drives
- This can cause noise when active

---

## Commands Reference

### Check UrBackup Status
```bash
# Service status
pct exec 111 -- systemctl status urbackupsrv

# Check backup folder setting
pct exec 111 -- cat /var/urbackup/backupfolder

# Check mounts inside container
pct exec 111 -- df -h | grep mnt
```

### Check Disk I/O
```bash
# Real-time I/O
iotop -b -n 1 -o

# Per-disk stats
iostat -xd 1 2

# What's using a disk
lsof +D /mnt/backups
```

### Proxmox Storage
```bash
# List storage status
pvesm status

# Check storage config
cat /etc/pve/storage.cfg
```

---

## Version History

| Date | Change |
|------|--------|
| 2026-01-16 | Initial setup: partitioned sdf, created mounts, configured UrBackup server |
| 2026-01-16 | Renamed storage: backups (10TB), container-backups (1TB) |
| 2026-01-16 | Configured backup intervals, skipped admin user setup |

