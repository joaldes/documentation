# Samba Outage - 2026-01-21

## Summary
At 11:55:51, the Mercury Elite Pro Quad USB enclosure experienced a USB protocol error (-71 EPROTO) and disconnected completely. All 4 disks disconnected simultaneously, causing filesystem corruption and read-only remounts. This was a USB connection issue, NOT disk failure.

---

## What Happened

### Timeline
- **11:55:51** - USB protocol error triggered disconnect
- **11:55:51-53** - All 4 disks disconnected, journals aborted, filesystems went read-only
- **11:55:55** - Enclosure reconnected with new device letters (sde→sdh, etc.)
- **~14:27** - User noticed Samba shares were down
- **~14:30** - Investigation started
- **~14:45** - Root cause identified as USB protocol error
- **~15:00** - User initiated reboot for fsck and clean remount

### Root Cause
USB protocol error on the Mercury Elite Pro Quad enclosure caused complete hub disconnect.

**Key log entry:**
```
Jan 21 11:55:51 Shipyard kernel: usb 4-3.3: cmd cmplt err -71
Jan 21 11:55:51 Shipyard kernel: usb 4-3: USB disconnect, device number 3
```

Error -71 = EPROTO (USB Protocol Error). Common causes:
1. Bad/degraded USB cable
2. USB port/controller issues
3. Enclosure power supply problems
4. UAS (USB Attached SCSI) driver incompatibility

---

## Technical Details

### Enclosure Information
- **Product**: Mercury Elite Pro Quad (OWC)
- **USB ID**: Vendor=1e91, Product=a4a7
- **Serial**: 000000001
- **Connection**: USB 4-3 (SuperSpeed Plus Gen 2x1)

### Affected Partitions

| Partition | Mount Point | Size | UUID | Label |
|-----------|-------------|------|------|-------|
| sdh1 (was sde1) | /mnt/frigate | 1TB | 3fd2919e-f8e6-4519-8926-f6752f554ac6 | frigate-data |
| sdh2 (was sde2) | /mnt/pictures | 10TB | 39ca2674-bded-4bcc-81f5-d29c8656e858 | pictures-data |
| sdh3 (was sde3) | /mnt/docker | 2TB | efec87bd-11dd-4e31-990d-2b5fa29fd13c | docker-data |
| sdh4 (was sde4) | /mnt/documents | 1TB | fc703734-ed1a-4f84-9c87-5d86bc483772 | docs-data |

### Why Mounts Failed After Reconnect
1. When USB disconnected, kernel had mounts to /dev/sde1-4
2. Filesystems went read-only, journals aborted
3. Mount entries stayed in kernel mount table (now "zombie" mounts)
4. Enclosure reconnected as /dev/sdh1-4 (new device letters)
5. Old stale mounts blocked new mounts
6. fstab uses UUIDs but only runs at boot or manual `mount -a`
7. `mount -a` couldn't work because filesystems had errors

### fstab Configuration (Host)
```
/dev/disk/by-uuid/39ca2674-bded-4bcc-81f5-d29c8656e858 /mnt/pictures ext4 defaults 0 2
/dev/disk/by-uuid/3fd2919e-f8e6-4519-8926-f6752f554ac6 /mnt/frigate ext4 defaults 0 2
UUID=efec87bd-11dd-4e31-990d-2b5fa29fd13c /mnt/docker ext4 defaults,noatime 0 2
UUID=fc703734-ed1a-4f84-9c87-5d86bc483772 /mnt/documents ext4 defaults,noatime 0 2
```

### LXC 104 (Samba) Mount Configuration
```
mp0: /mnt/hometheater,mp=/mnt/hometheater
mp1: /mnt/frigate,mp=/mnt/frigate
mp2: /mnt/pictures,mp=/mnt/pictures
mp3: /mnt/documents,mp=/mnt/documents
mp4: /mnt/docker,mp=/mnt/docker
```
LXC uses host mount paths, not device paths - will work once host mounts are restored.

---

## Error Log Excerpts

### USB Disconnect Sequence
```
Jan 21 11:55:51 usb 4-3.3: cmd cmplt err -71
Jan 21 11:55:51 usb 4-3: USB disconnect, device number 3
Jan 21 11:55:51 usb 4-3.1: USB disconnect, device number 4
Jan 21 11:55:51 sd 3:0:0:0: [sdc] Synchronizing SCSI cache
Jan 21 11:55:51 usb 4-3.2: USB disconnect, device number 5
Jan 21 11:55:51 sd 4:0:0:0: [sdd] tag#1 uas_zap_pending 0 uas-tag 8 inflight: CMD
Jan 21 11:55:51 sd 5:0:0:0: [sde] tag#21 FAILED Result: hostbyte=DID_NO_CONNECT driverbyte=DRIVER_OK
```

### Filesystem Errors
```
Jan 21 11:55:51 EXT4-fs warning (device sde3): ext4_end_bio:343: I/O error 10 writing to inode 132382755
Jan 21 11:55:51 Aborting journal on device sde1-8.
Jan 21 11:55:51 JBD2: I/O error when updating journal superblock for sde1-8.
Jan 21 11:55:51 EXT4-fs (sde1): Remounting filesystem read-only
Jan 21 11:55:51 EXT4-fs (sde1): This should not happen!! Data will be lost
Jan 21 11:55:52 EXT4-fs (sde3): This should not happen!! Data will be lost
```

### Enclosure Reconnect
```
Jan 21 11:55:55 usb 4-3: new SuperSpeed Plus Gen 2x1 USB device number 8 using xhci_hcd
Jan 21 11:55:55 usb 4-3: Product: Mercury Elite Pro Quad
Jan 21 11:55:55 usb 4-3: Manufacturer: OWC
Jan 21 11:55:55 usb 4-3: SerialNumber: 000000001
```

---

## Resolution

### Reboot Process
1. User rebooted Proxmox host
2. During boot, fsck runs automatically on dirty filesystems
3. Estimated fsck time: 30-60 minutes (14TB total data)
4. fstab will mount using UUIDs (device letters don't matter)
5. LXC containers will start with fresh mounts

---

## Post-Reboot Verification Checklist

### Immediate Checks
- [ ] Host is up: `ping 192.168.0.151`
- [ ] All mounts present: `ssh claude@192.168.0.151 "mount | grep /mnt/"`
- [ ] No mount errors: `ssh claude@192.168.0.151 "dmesg | grep -i 'mount\|ext4' | tail -20"`
- [ ] Samba container running: API check on container 104
- [ ] Komodo container running: API check on container 128

### Samba Verification
- [ ] SSH to Samba: `ssh root@192.168.0.176`
- [ ] Check shares: `smbstatus --shares`
- [ ] Test from network client

### Docker/Komodo Verification
- [ ] SSH to Komodo: `ssh root@192.168.0.179`
- [ ] Docker healthy: `docker ps`
- [ ] Stacks running: Check Komodo UI at :9120

### Disk Health Check
```bash
# Run from Proxmox host after reboot
sudo smartctl -H /dev/sdX  # for each disk in enclosure
sudo smartctl -A /dev/sdX | grep -E 'Reallocated|Current_Pending|Offline_Uncorrectable'
```

---

## Recommendations

### Immediate (After Reboot)
1. **Check SMART data** on all 4 disks to confirm they're healthy
2. **Test write operations** to each mount point
3. **Verify all services** are functioning

### Short-term
1. **Replace USB cable** - Most common cause of -71 errors
2. **Try different USB port** - Preferably on a different controller
3. **Check enclosure power** - Ensure solid connection, try different outlet

### If Issues Persist - Disable UAS
UAS (USB Attached SCSI) can be unstable with some enclosures. To disable:

```bash
# Add to /etc/modprobe.d/usb-storage-quirks.conf on Proxmox host
options usb-storage quirks=1e91:a4a7:u

# Then rebuild initramfs and reboot
update-initramfs -u
```

This forces the enclosure to use legacy USB mass storage instead of UAS.

### Long-term
- Consider direct SATA/SAS connection instead of USB for critical data
- Set up monitoring for USB disconnect events
- Regular SMART monitoring

---

## Related Infrastructure

### Containers Using These Mounts
- **104 (Samba)**: All mounts - primary file server
- **128 (Komodo)**: /mnt/docker - Docker stacks including Immich, Paperless, Frigate, etc.

### Services Affected
- Samba file shares (hometheater, frigate, pictures, documents)
- All Docker stacks on Komodo (Immich, Paperless-NGX, Tandoor, Stirling PDF, Frigate, Mealie, Grafana/Prometheus)

---

## Commands Reference

### Check mounts from Claude container
```bash
# Check host mounts
sshpass -p 'claudepassword' ssh claude@192.168.0.151 "mount | grep /mnt/"

# Check container mounts
SSHPASS='password' sshpass -e ssh root@192.168.0.176 "df -h"
```

### Check container status via API
```bash
curl -s -k -H "Authorization: PVEAPIToken=claude@pam!api=e8d6b1cf-087a-47b6-a232-9f2a7d4216b7" \
  "https://192.168.0.151:8006/api2/json/nodes/Shipyard/lxc/104/status/current"
```

### Check Samba shares
```bash
SSHPASS='password' sshpass -e ssh root@192.168.0.176 "smbstatus --shares"
```
