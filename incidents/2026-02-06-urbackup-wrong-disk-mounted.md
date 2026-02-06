# UrBackup Clients Missing — Wrong Disk Mounted

**Date**: 2026-02-06
**Duration**: Unknown (discovered during troubleshooting session)
**Severity**: Medium — backups not running, but data was intact
**Related Systems**: UrBackup (CT 111), Proxmox host storage mounts

---

## Summary

UrBackup appeared as a fresh install with no clients or backup history. Investigation revealed the wrong disk was mounted at `/mnt/backups` — sdd1 (1TB) instead of sdf1 (10TB). The actual UrBackup data (clients Hydrofoil, Megsy, and full database) was on sdf1, which was not mounted.

---

## Symptoms

- UrBackup web UI showed no clients configured
- No backup history visible
- Container 111 appeared to have a fresh/empty database
- `/mnt/backups/clients/` folder was empty

---

## Root Cause

**Systemd mount unit file had wrong UUID.**

| Mount Point | Was Mounted | Should Be |
|-------------|-------------|----------------------|
| `/mnt/backups` | sdd1 (1TB) ❌ | sdf1 (10TB) |
| `/mnt/container-backups` | not mounted | sdd1 (1TB) |

The fstab was correct, but a systemd mount unit file at `/etc/systemd/system/mnt-backups.mount` had the **wrong UUID** (sdd1 instead of sdf1). Systemd mount units take precedence over fstab entries, so the wrong disk was mounted at every boot.

**The problematic file:**
```ini
# /etc/systemd/system/mnt-backups.mount (BEFORE fix)
[Mount]
What=/dev/disk/by-uuid/e424b756-df58-41b6-83fd-291525fc6e95  # ← Wrong! This is sdd1
Where=/mnt/backups
```

**UUIDs:**
- sdf1: `702673ce-559f-4c1c-866c-f44ff415e421` (10TB, UrBackup data)
- sdd1: `e424b756-df58-41b6-83fd-291525fc6e95` (1TB, labeled "proxmox-backups")

---

## Resolution

1. Stopped UrBackup container 111
2. Unmounted incorrect mounts:
   ```bash
   umount /mnt/sdf1-check  # temp diagnostic mount
   umount /mnt/backups     # was sdd1, wrong
   ```
3. Mounted correctly:
   ```bash
   mount /mnt/backups           # now sdf1 (10TB)
   mount /mnt/container-backups  # now sdd1 (1TB)
   ```
4. Started UrBackup container 111
5. Verified clients (Hydrofoil, Megsy) appeared in web UI with backup history
6. **Fixed root cause** — updated `/etc/systemd/system/mnt-backups.mount`:
   ```bash
   # Changed UUID from e424b756... (sdd1) to 702673ce... (sdf1)
   systemctl daemon-reload
   ```

---

## Data Impact

- **No data loss** — all UrBackup client data (3.9TB) was intact on sdf1
- Backups were not running during the period the wrong disk was mounted
- Clients will resume backups on next scheduled interval

---

## Prevention

- **Check systemd mount units first** — they override fstab:
  ```bash
  ls /etc/systemd/system/*.mount
  cat /etc/systemd/system/mnt-backups.mount
  ```
- After any reboot or storage changes, verify mounts:
  ```bash
  df -h /mnt/backups /mnt/container-backups
  # /mnt/backups should show ~10T (sdf1)
  # /mnt/container-backups should show ~1T (sdd1)
  ```
- The systemd mount unit file is documented in [urbackup-setup.md](../services/urbackup-setup.md)

---

## Related Documentation

- [urbackup-setup.md](../services/urbackup-setup.md) — UrBackup configuration details
