# LXC Container Onboarding Guide

**Last Updated**: 2026-06-25
**Proxmox Host**: 192.168.0.151 (Shipyard)

---

## Overview

This document defines the standard configuration for all LXC containers in the Proxmox homelab. Following this checklist ensures consistent access, security updates, and emergency recovery capabilities.

---

## Standard Configuration Checklist

### 1. Root Password
**Standard**: `password`

```bash
# Set from Proxmox host
pct exec <CTID> -- bash -c 'echo "root:password" | chpasswd'
```

**Why**: Guarantees emergency access if other methods fail.

---

### 2. AppArmor Disabled
**Add to**: `/etc/pve/lxc/<CTID>.conf`

```
lxc.apparmor.profile: unconfined
```

**Why**: Ubuntu containers ship with 110+ desktop AppArmor profiles that slow boot by ~45 seconds. Server containers don't need them. Host-level Proxmox AppArmor protection remains active.

**Note**: Requires container restart to take effect.

---

### 3. SSH Access Enabled

```bash
# Install and enable SSH
pct exec <CTID> -- apt-get update
pct exec <CTID> -- apt-get install -y openssh-server
pct exec <CTID> -- systemctl enable --now ssh

# Allow root login (if needed)
pct exec <CTID> -- sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
pct exec <CTID> -- systemctl restart ssh
```

**Why**: Enables file transfers (scp), port forwarding, and remote administration.

---

### 4. Console Auto-Login

For Debian/Ubuntu containers, edit `/etc/systemd/system/container-getty@.service.d/override.conf`:

```bash
pct exec <CTID> -- mkdir -p /etc/systemd/system/container-getty@.service.d
pct exec <CTID> -- bash -c 'cat > /etc/systemd/system/container-getty@.service.d/override.conf << EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear --keep-baud tty%I 115200,38400,9600 \$TERM
EOF'
pct exec <CTID> -- systemctl daemon-reload
```

**Why**: Provides immediate root shell access via Proxmox console without password prompt.

---

### 5. SSH Key for Claude AI (CT 124)

```bash
# Deploy Claude AI's public key for passwordless access
pct exec <CTID> -- bash -c 'mkdir -p /root/.ssh && chmod 700 /root/.ssh && echo "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC6bFl3Ti0W6ZY5zkqgdovFawDDQ/y3YvCGoIrVzDX28OnOCnQWg0H1xcwUB+6jjM51tFtLGXtNzWOu6L0m+G+Q4LLrwo6cDDIb5j2tr0Kse3TE0uJCZ2XEknpoXEDU2ttV+Mk18lwBhIxDDRdA7RggicwX88EY9vj0HqIipUr+SFX/rYkt7ky3t1EQhBvPVRugIXQPplG2+AJA7gdSCNnn1kAEyHgZS5AWR5X+tF6JkFPRkWZqcAEDxJJGEUxuDBIbxUxh7NKWUS7kFIRvrsnOabuK7zykyh8N5ZxO3pvBm+t+a2G1k6lWcz9WzHACwshrs/LVRhw6QE25Ev9LXnoc7HrTv9N9Z5EbrjogNyGnsEP5uQnL0z0b16pzvriWRuj8THBu9yG9Hp2BJluCLDClvX7QLUWezwT36deGrvF44lLBQ7svrYHLh9vPToLZWHDUkM0H6wOBviKv5SbgXzKGqap/EUnXY7UbHoWTRcEtkDcv4xCQl6qPAYH6/SGQSkE= claudeai@claudeai" >> /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys'
```

**Why**: Allows Claude AI (CT 124) to SSH into containers without passwords, enabling faster automation and management. The key is also deployed to the Proxmox host (`claude` user).

---

### 6. Unattended Security Upgrades

```bash
pct exec <CTID> -- apt-get install -y unattended-upgrades apt-listchanges
pct exec <CTID> -- bash -c 'echo -e "APT::Periodic::Update-Package-Lists \"1\";\nAPT::Periodic::Unattended-Upgrade \"1\";" > /etc/apt/apt.conf.d/20auto-upgrades'
```

**Why**: Ensures security patches are applied automatically. Only installs security updates, won't upgrade major versions or reboot automatically.

---

### 7. Clear ext4 MMP on Container Volumes

Proxmox formats every guest volume with the ext4 **Multi-Mount Protection (MMP)** feature, which forces a
**~45-second mount-time stall per filesystem** at boot. With many containers this makes a cold boot /
power-loss recovery take 15–20+ minutes. MMP only guards against two hosts mounting one filesystem
(shared/clustered storage) — useless on this single node, pure boot tax. Clear it on every new container.

```bash
# From the Proxmox host. Requires the volume OFFLINE → stop the container first.
# Clears mmp on the container's rootfs AND any storage-backed mountpoint disks (mpX).
CTID=<CTID>
pct stop $CTID
for vol in $(pct config $CTID | grep -E '^(rootfs|mp[0-9]+):' \
            | grep -oE '(pve|local-lvm|ssd):vm-[0-9]+-disk-[0-9]+'); do
    stor=${vol%%:*}; lv=${vol##*:}
    case "$stor" in pve|local-lvm) vg=pve;; ssd) vg=ssd;; *) continue;; esac
    tune2fs -O ^mmp /dev/$vg/$lv && echo "  cleared mmp: /dev/$vg/$lv"
done
pct start $CTID
```

**Why**: removes the ~45s/volume boot stall (a CT restart drops from ~45s to ~3s). Metadata-only, instant,
reversible (`tune2fs -O mmp` re-adds it). **Recurs**: PVE re-applies `mmp` to any newly created / restored
/ migrated volume — so this must be run for every new container (and after any `pct restore` or disk move).
Bind mounts (`mpX: /host/path,...`) are NOT volumes — only storage-backed `vg:vm-N-disk-N` get mmp; VM
disks are unaffected.

---

## Quick Onboarding Script

Run this from the Proxmox host to fully onboard a container:

```bash
#!/bin/bash
CTID=$1

if [ -z "$CTID" ]; then
    echo "Usage: $0 <CTID>"
    exit 1
fi

echo "=== Onboarding Container $CTID ==="

# 1. Set root password
echo "[1/7] Setting root password..."
pct exec $CTID -- bash -c 'echo "root:password" | chpasswd'

# 2. Install and enable SSH
echo "[2/7] Enabling SSH..."
pct exec $CTID -- apt-get update -qq
pct exec $CTID -- apt-get install -y -qq openssh-server
pct exec $CTID -- sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
pct exec $CTID -- systemctl enable --now ssh
pct exec $CTID -- systemctl restart ssh

# 3. Enable unattended-upgrades
echo "[3/7] Enabling unattended-upgrades..."
pct exec $CTID -- apt-get install -y -qq unattended-upgrades apt-listchanges
pct exec $CTID -- bash -c 'echo -e "APT::Periodic::Update-Package-Lists \"1\";\nAPT::Periodic::Unattended-Upgrade \"1\";" > /etc/apt/apt.conf.d/20auto-upgrades'

# 4. Console auto-login
echo "[4/7] Enabling console auto-login..."
pct exec $CTID -- mkdir -p /etc/systemd/system/container-getty@.service.d
pct exec $CTID -- bash -c 'cat > /etc/systemd/system/container-getty@.service.d/override.conf << EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear --keep-baud tty%I 115200,38400,9600 \$TERM
EOF'
pct exec $CTID -- systemctl daemon-reload

# 5. Deploy Claude AI SSH key
echo "[5/7] Deploying Claude AI SSH key..."
pct exec $CTID -- bash -c 'mkdir -p /root/.ssh && chmod 700 /root/.ssh && grep -qF "claudeai@claudeai" /root/.ssh/authorized_keys 2>/dev/null || echo "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC6bFl3Ti0W6ZY5zkqgdovFawDDQ/y3YvCGoIrVzDX28OnOCnQWg0H1xcwUB+6jjM51tFtLGXtNzWOu6L0m+G+Q4LLrwo6cDDIb5j2tr0Kse3TE0uJCZ2XEknpoXEDU2ttV+Mk18lwBhIxDDRdA7RggicwX88EY9vj0HqIipUr+SFX/rYkt7ky3t1EQhBvPVRugIXQPplG2+AJA7gdSCNnn1kAEyHgZS5AWR5X+tF6JkFPRkWZqcAEDxJJGEUxuDBIbxUxh7NKWUS7kFIRvrsnOabuK7zykyh8N5ZxO3pvBm+t+a2G1k6lWcz9WzHACwshrs/LVRhw6QE25Ev9LXnoc7HrTv9N9Z5EbrjogNyGnsEP5uQnL0z0b16pzvriWRuj8THBu9yG9Hp2BJluCLDClvX7QLUWezwT36deGrvF44lLBQ7svrYHLh9vPToLZWHDUkM0H6wOBviKv5SbgXzKGqap/EUnXY7UbHoWTRcEtkDcv4xCQl6qPAYH6/SGQSkE= claudeai@claudeai" >> /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys'

# 6. AppArmor (manual step)
echo "[6/7] AppArmor..."
if grep -q "lxc.apparmor.profile: unconfined" /etc/pve/lxc/${CTID}.conf 2>/dev/null; then
    echo "  AppArmor already disabled"
else
    echo "  ADD THIS LINE to /etc/pve/lxc/${CTID}.conf:"
    echo "  lxc.apparmor.profile: unconfined"
    echo "  Then restart the container: pct reboot $CTID"
fi

# 7. Clear ext4 MMP (removes ~45s/volume boot stall) — needs the volume offline
echo "[7/7] Clearing ext4 MMP on container volume(s)..."
pct stop $CTID
for vol in $(pct config $CTID | grep -E '^(rootfs|mp[0-9]+):' \
            | grep -oE '(pve|local-lvm|ssd):vm-[0-9]+-disk-[0-9]+'); do
    stor=${vol%%:*}; lv=${vol##*:}
    case "$stor" in pve|local-lvm) vg=pve;; ssd) vg=ssd;; *) continue;; esac
    tune2fs -O ^mmp /dev/$vg/$lv >/dev/null 2>&1 && echo "  cleared mmp: /dev/$vg/$lv"
done
pct start $CTID

echo ""
echo "=== Onboarding Complete ==="
echo "Test access:"
echo "  SSH: ssh root@<CONTAINER_IP>  (password: password)"
echo "  Console: pct enter $CTID"
```

---

## Verification Commands

### Check All Settings

```bash
# From Proxmox host, for a specific container:
CTID=128

echo "=== Container $CTID Status ==="

# AppArmor
echo -n "AppArmor: "
grep -q "lxc.apparmor.profile: unconfined" /etc/pve/lxc/${CTID}.conf && echo "DISABLED (good)" || echo "ENABLED (needs fix)"

# MMP (ext4 multi-mount protection — should be CLEARED for fast boot)
echo -n "MMP: "
mmp=0
for vol in $(pct config $CTID | grep -E '^(rootfs|mp[0-9]+):' | grep -oE '(pve|local-lvm|ssd):vm-[0-9]+-disk-[0-9]+'); do
    s=${vol%%:*}; lv=${vol##*:}; case "$s" in pve|local-lvm) vg=pve;; ssd) vg=ssd;; *) continue;; esac
    tune2fs -l /dev/$vg/$lv 2>/dev/null | grep -qw mmp && mmp=1
done
[ $mmp -eq 0 ] && echo "CLEARED (good)" || echo "PRESENT (needs fix — ~45s/volume boot stall)"

# SSH
echo -n "SSH: "
pct exec $CTID -- systemctl is-active ssh 2>/dev/null && echo "" || echo "NOT RUNNING"

# Unattended-upgrades
echo -n "Unattended-upgrades: "
pct exec $CTID -- dpkg -l unattended-upgrades 2>/dev/null | grep -q "^ii" && echo "INSTALLED" || echo "NOT INSTALLED"

# Root password (test from another machine)
echo "Root password: Test with 'sshpass -p password ssh root@<IP>'"
```

### Bulk Audit All Containers

```bash
for CTID in $(pct list | tail -n +2 | awk '{print $1}'); do
    STATUS=$(pct status $CTID | awk '{print $2}')
    if [ "$STATUS" = "running" ]; then
        echo "=== Container $CTID ==="
        grep -q "lxc.apparmor.profile: unconfined" /etc/pve/lxc/${CTID}.conf && echo "  AppArmor: OK" || echo "  AppArmor: NEEDS FIX"
        mmp=0; for vol in $(pct config $CTID | grep -E '^(rootfs|mp[0-9]+):' | grep -oE '(pve|local-lvm|ssd):vm-[0-9]+-disk-[0-9]+'); do s=${vol%%:*}; lv=${vol##*:}; case "$s" in pve|local-lvm) vg=pve;; ssd) vg=ssd;; *) continue;; esac; tune2fs -l /dev/$vg/$lv 2>/dev/null | grep -qw mmp && mmp=1; done; [ $mmp -eq 0 ] && echo "  MMP: OK" || echo "  MMP: NEEDS FIX"
        pct exec $CTID -- systemctl is-active ssh &>/dev/null && echo "  SSH: OK" || echo "  SSH: NEEDS FIX"
        pct exec $CTID -- dpkg -l unattended-upgrades 2>/dev/null | grep -q "^ii" && echo "  Upgrades: OK" || echo "  Upgrades: NEEDS FIX"
    fi
done
```

---

## Access Priority Order

When accessing containers, follow this priority:

1. **API First** - Fastest and most reliable
   ```bash
   curl -k -H "Authorization: PVEAPIToken=claude@pam!api=..." \
     "https://192.168.0.151:8006/api2/json/nodes/Shipyard/lxc/$CTID/status/current"
   ```

2. **Console via pct exec** - Immediate root shell
   ```bash
   pct exec $CTID -- /bin/bash
   ```

3. **SSH Direct** - For file transfers and persistent sessions
   ```bash
   ssh root@<CONTAINER_IP>    # key auth from CT 124, or password: password
   scp file.txt root@<IP>:/tmp/
   ```

**Note**: Claude AI (CT 124) has SSH key auth to the Proxmox host (`claude` user) and all containers (`root` user). No passwords needed from CT 124.

---

## Current Container Status (2026-02-16)

| CTID | Name | IP | AppArmor | SSH | Upgrades | Password | SSH Key |
|------|------|-----|----------|-----|----------|----------|---------|
| 101 | adguard | 192.168.0.11 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 102 | emby | 192.168.0.13 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 103 | syncthing | 192.168.0.45 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 104 | samba | 192.168.0.176 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 105 | unmanic | 192.168.0.207 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 107 | radarr | 192.168.0.42 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 108 | zwave-js-ui | 192.168.0.153 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 110 | sonarr | 192.168.0.24 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 111 | urbackup | 192.168.0.209 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 112 | nginxproxymanager | 192.168.0.30 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 113 | jellyseerr | 192.168.0.43 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 114 | uptimekuma | 192.168.0.44 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 115 | bazarr | 192.168.0.48 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 116 | tracearr | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| 117 | wikijs | 192.168.0.57 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 118 | homepage | 192.168.0.70 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 120 | pulse | 192.168.0.175 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 124 | claude-ai | 192.168.0.180 | ✓ | ✓ | ✓ | ✓ | — |
| 126 | tailscale | 192.168.0.126 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 128 | komodo | 192.168.0.179 | ✓ | ✓ | ✓ | ✓ | ✓ |

**SSH Key** = Claude AI (CT 124) public key in `/root/.ssh/authorized_keys`
**Proxmox host** also has the key in `claude` user's `authorized_keys`.

---

## Troubleshooting

### Can't SSH to container
1. Verify container is running: `pct status $CTID`
2. Check SSH service: `pct exec $CTID -- systemctl status ssh`
3. Check firewall: `pct exec $CTID -- iptables -L`
4. Test from host: `pct exec $CTID -- ss -tlnp | grep 22`

### Slow container boot
1. **Check ext4 MMP first** (Step 7) — `~45s` host-side mount stall *per volume* before the container's
   PID 1 even runs. Symptom: `journalctl -b | grep multi_mount_protect` shows "please wait"; `pve-guests`
   starts CTs ~45s apart. This is the #1 cause of a 15–20 min cold boot. Clear with `tune2fs -O ^mmp`.
2. Check if AppArmor is disabled in config
3. Look for stuck services: `pct exec $CTID -- systemd-analyze blame` (note: this measures *inside* the
   container — MMP stall happens on the host BEFORE this, so a fast `systemd-analyze` doesn't rule it out)
4. Common culprits: systemd-logind, motd-news, network-wait

### Password not working
1. Reset via pct: `pct exec $CTID -- bash -c 'echo "root:password" | chpasswd'`
2. Verify SSH allows root: Check `/etc/ssh/sshd_config` for `PermitRootLogin yes`

---

## Version History

| Date | Change |
|------|--------|
| 2026-06-25 | Added Step 7 — clear ext4 MMP on container volumes (fixes ~45s/volume cold-boot stall); added MMP to script, audit, and troubleshooting |
| 2026-02-16 | Added SSH key deployment for Claude AI (CT 124) to onboarding checklist |
| 2026-01-26 | Initial document created |
| 2025-12-26 | Standards established (per CLAUDE.md) |
| 2025-12-24 | AppArmor disabled on all containers |
