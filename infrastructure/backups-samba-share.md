# Backups Samba Share Setup

**Last Updated**: 2026-02-13
**Related Systems**: Container 104 (Samba), Proxmox Host

## Summary
Added `/mnt/backups` as a Samba share on Container 104, and copied 841GB of Mac HFS+ backup data from an external Seagate drive to `/mnt/backups/mac-backup/`.

## Problem / Goal
A 2TB Seagate external drive (sdg) containing two Mac user folder backups needed to be copied to permanent storage and made browsable over the network. The backups disk (`/mnt/backups`, 10TB) had no Samba share.

## Solution
1. Copied Mac data via rsync to `/mnt/backups/mac-backup/`
2. Added bind mount to Container 104 for `/mnt/backups`
3. Created Samba share exposing the full backups disk

## Implementation Details

### 1. Data Copy
```bash
sudo mkdir -p /mnt/backups/mac-backup
sudo rsync -ah --info=progress2 /mnt/sdg/ /mnt/backups/mac-backup/
```
- Source: `/mnt/sdg/` (HFS+ mounted read-only)
- Destination: `/mnt/backups/mac-backup/` (841GB total)
- Contents:
  - `Back Up 2.22.18/` — Movies, Pictures
  - `Old Back Up/` — Movies, Pictures, iTunes, Docs, Desktop

### 2. Bind Mount (Container 104)
Added to `/etc/pve/lxc/104.conf`:
```
mp5: /mnt/backups,mp=/mnt/backups
```
Container 104 already had mp0-mp4 (hometheater, frigate, pictures, documents, docker).

### 3. Samba Share
Added to `/etc/samba/smb.conf` in Container 104:
```ini
[backups]
    path = /mnt/backups
    browseable = yes
    read only = no
    valid users = sambauser
    force user = root
    force group = root
    create mask = 0775
    directory mask = 0775
    comment = Backups Storage
```

### 4. Post-Copy
- Unmounted Mac drive: `sudo umount /mnt/sdg`
- External drive safe to disconnect

### Key Files Modified
- `/etc/pve/lxc/104.conf` — Added mp5 bind mount
- `/etc/samba/smb.conf` (Container 104) — Added [backups] share

## Verification
```bash
# Check data exists
ls /mnt/backups/mac-backup/
du -sh /mnt/backups/mac-backup/   # Should show ~841G

# Test Samba share from any network client
# \\192.168.0.176\backups (sambauser / sambapassword)
```

## Notes
- The share exposes ALL of `/mnt/backups`, not just mac-backup. This includes UrBackup data, client backups, etc.
- The backups disk is 10TB (`/dev/sdf1`) with ~4.5TB free after the Mac copy.
