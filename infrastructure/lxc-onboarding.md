# LXC Container Onboarding Guide

**Last Updated**: 2026-01-26
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

### 5. Unattended Security Upgrades

```bash
pct exec <CTID> -- apt-get install -y unattended-upgrades apt-listchanges
pct exec <CTID> -- bash -c 'echo -e "APT::Periodic::Update-Package-Lists \"1\";\nAPT::Periodic::Unattended-Upgrade \"1\";" > /etc/apt/apt.conf.d/20auto-upgrades'
```

**Why**: Ensures security patches are applied automatically. Only installs security updates, won't upgrade major versions or reboot automatically.

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
echo "[1/5] Setting root password..."
pct exec $CTID -- bash -c 'echo "root:password" | chpasswd'

# 2. Install and enable SSH
echo "[2/5] Enabling SSH..."
pct exec $CTID -- apt-get update -qq
pct exec $CTID -- apt-get install -y -qq openssh-server
pct exec $CTID -- sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
pct exec $CTID -- systemctl enable --now ssh
pct exec $CTID -- systemctl restart ssh

# 3. Enable unattended-upgrades
echo "[3/5] Enabling unattended-upgrades..."
pct exec $CTID -- apt-get install -y -qq unattended-upgrades apt-listchanges
pct exec $CTID -- bash -c 'echo -e "APT::Periodic::Update-Package-Lists \"1\";\nAPT::Periodic::Unattended-Upgrade \"1\";" > /etc/apt/apt.conf.d/20auto-upgrades'

# 4. Console auto-login
echo "[4/5] Enabling console auto-login..."
pct exec $CTID -- mkdir -p /etc/systemd/system/container-getty@.service.d
pct exec $CTID -- bash -c 'cat > /etc/systemd/system/container-getty@.service.d/override.conf << EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear --keep-baud tty%I 115200,38400,9600 \$TERM
EOF'
pct exec $CTID -- systemctl daemon-reload

# 5. AppArmor (manual step)
echo "[5/5] AppArmor..."
if grep -q "lxc.apparmor.profile: unconfined" /etc/pve/lxc/${CTID}.conf 2>/dev/null; then
    echo "  AppArmor already disabled"
else
    echo "  ADD THIS LINE to /etc/pve/lxc/${CTID}.conf:"
    echo "  lxc.apparmor.profile: unconfined"
    echo "  Then restart the container: pct reboot $CTID"
fi

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
   ssh root@<CONTAINER_IP>    # password: password
   scp file.txt root@<IP>:/tmp/
   ```

---

## Current Container Status (2026-01-26)

| CTID | Name | IP | AppArmor | SSH | Upgrades | Password |
|------|------|-----|----------|-----|----------|----------|
| 101 | adguard | 192.168.0.11 | ✓ | ✓ | ✓ | ✓ |
| 102 | emby | 192.168.0.13 | ✓ | ✓ | ✓ | ✓ |
| 103 | syncthing | 192.168.0.45 | ✓ | ✓ | ✓ | ✓ |
| 104 | samba | 192.168.0.176 | ✓ | ✓ | ✓ | ✓ |
| 105 | unmanic | 192.168.0.207 | ✓ | ✓ | ✓ | ✓ |
| 107 | radarr | 192.168.0.42 | ✓ | ✓ | ✓ | ✓ |
| 108 | zwave-js-ui | 192.168.0.153 | ✓ | ✓ | ✓ | ✓ |
| 110 | sonarr | 192.168.0.24 | ✓ | ✓ | ✓ | ✓ |
| 111 | urbackup | 192.168.0.209 | ✓ | ✓ | ✓ | ✓ |
| 112 | nginxproxymanager | 192.168.0.30 | ✓ | ✓ | ✓ | ✓ |
| 113 | jellyseerr | 192.168.0.43 | ✓ | ✓ | ✓ | ✓ |
| 114 | uptimekuma | 192.168.0.44 | ✓ | ✓ | ✓ | ✓ |
| 115 | bazarr | 192.168.0.48 | ✓ | ✓ | ✓ | ✓ |
| 117 | wikijs | 192.168.0.57 | ✓ | ✓ | ✓ | ✓ |
| 118 | homepage | 192.168.0.70 | ✓ | ✓ | ✓ | ✓ |
| 120 | pulse | 192.168.0.175 | ✓ | ✓ | ✓ | ✓ |
| 124 | claude-ai | 192.168.0.180 | ✓ | ✓ | ✓ | ✓ |
| 128 | komodo | 192.168.0.179 | ✓ | ✓ | ✓ | ✓ |

**Stopped containers** (not audited):
- 109 (tdarr)
- 121 (notifiarr)

---

## Troubleshooting

### Can't SSH to container
1. Verify container is running: `pct status $CTID`
2. Check SSH service: `pct exec $CTID -- systemctl status ssh`
3. Check firewall: `pct exec $CTID -- iptables -L`
4. Test from host: `pct exec $CTID -- ss -tlnp | grep 22`

### Slow container boot
1. Check if AppArmor is disabled in config
2. Look for stuck services: `pct exec $CTID -- systemd-analyze blame`
3. Common culprits: systemd-logind, motd-news, network-wait

### Password not working
1. Reset via pct: `pct exec $CTID -- bash -c 'echo "root:password" | chpasswd'`
2. Verify SSH allows root: Check `/etc/ssh/sshd_config` for `PermitRootLogin yes`

---

## Version History

| Date | Change |
|------|--------|
| 2026-01-26 | Initial document created |
| 2025-12-26 | Standards established (per CLAUDE.md) |
| 2025-12-24 | AppArmor disabled on all containers |
