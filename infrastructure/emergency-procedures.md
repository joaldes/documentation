# Emergency Response Procedures

**Last Updated**: 2026-01-26
**Proxmox Host**: 192.168.0.151 (Shipyard)

---

## Emergency Classification

| Level | Description | Examples |
|-------|-------------|----------|
| 1 | Service Degradation | Single service slow/intermittent |
| 2 | Service Outage | Critical service completely down |
| 3 | System Failure | Container/VM won't start |
| 4 | Infrastructure Failure | Proxmox host or network down |

---

## Quick Access Reference

```bash
# API Token
claude@pam!api = e8d6b1cf-087a-47b6-a232-9f2a7d4216b7

# SSH to Proxmox host
ssh claude@192.168.0.151  # password: claudepassword

# Container access
pct exec <CTID> -- bash

# All containers use root password: password
ssh root@<container_ip>
```

---

## Level 1: Service Degradation

### Immediate Actions (0-5 min)

```bash
# 1. Verify issue
curl -I http://<service_ip>:<port>

# 2. Check service status
pct exec <CTID> -- systemctl status <service>

# 3. Check logs
pct exec <CTID> -- journalctl -u <service> -n 50
```

### Resolution

```bash
# Restart service
pct exec <CTID> -- systemctl restart <service>

# Verify
pct exec <CTID> -- systemctl status <service>
```

---

## Level 2: Service Outage

### Immediate Actions (0-2 min)

```bash
# 1. Confirm outage
ping -c 3 <service_ip>
curl -I --connect-timeout 5 http://<service_ip>:<port>

# 2. Check container status via API
curl -k -H "Authorization: PVEAPIToken=claude@pam!api=e8d6b1cf-087a-47b6-a232-9f2a7d4216b7" \
  "https://192.168.0.151:8006/api2/json/nodes/Shipyard/lxc/<CTID>/status/current"
```

### Diagnostic Phase (2-10 min)

```bash
# Resource check
pct exec <CTID> -- df -h
pct exec <CTID> -- free -h

# Log analysis
pct exec <CTID> -- journalctl --since "30 minutes ago" | grep -i error

# Failed services
pct exec <CTID> -- systemctl --failed
```

### Resolution (10-30 min)

```bash
# 1. Try service restart
pct exec <CTID> -- systemctl restart <service>

# 2. If that fails, restart container
pct stop <CTID>
sleep 10
pct start <CTID>
```

---

## Level 3: System Failure

### Container Won't Start

```bash
# 1. Check status
pct status <CTID>

# 2. Try starting
pct start <CTID>

# 3. Check config
cat /etc/pve/lxc/<CTID>.conf

# 4. Check host resources
df -h
free -h

# 5. Check for filesystem errors
pct mount <CTID>
# If errors found:
fsck /dev/pve/vm-<CTID>-disk-0
pct unmount <CTID>
pct start <CTID>
```

### Snapshot Recovery

```bash
# List snapshots
curl -k -H "Authorization: PVEAPIToken=claude@pam!api=e8d6b1cf-087a-47b6-a232-9f2a7d4216b7" \
  "https://192.168.0.151:8006/api2/json/nodes/Shipyard/lxc/<CTID>/snapshot"

# Rollback to snapshot
curl -k -X POST -H "Authorization: PVEAPIToken=claude@pam!api=e8d6b1cf-087a-47b6-a232-9f2a7d4216b7" \
  "https://192.168.0.151:8006/api2/json/nodes/Shipyard/lxc/<CTID>/snapshot/<snapname>/rollback"
```

---

## Level 4: Infrastructure Failure

### Host Connectivity Check

```bash
# From any working system
ping -c 3 192.168.0.151
ping -c 3 192.168.0.1  # Gateway
```

### Multi-Container Status

```bash
# Check all containers
for vm in 101 104 111 128; do
  echo "Container $vm:"
  curl -sk -H "Authorization: PVEAPIToken=claude@pam!api=e8d6b1cf-087a-47b6-a232-9f2a7d4216b7" \
    "https://192.168.0.151:8006/api2/json/nodes/Shipyard/lxc/$vm/status/current" | jq -r '.data.status'
done
```

### Recovery Priority Order

Start containers in this order:

1. **101** - AdGuard (DNS)
2. **104** - Samba (File shares)
3. **128** - Komodo (Docker services)
4. **111** - UrBackup
5. Other containers

```bash
for vm in 101 104 128 111; do
  echo "Starting container $vm"
  pct start $vm
  sleep 30
done
```

---

## Critical Services Quick Reference

| Service | CTID | IP | Port | Health Check |
|---------|------|-----|------|--------------|
| AdGuard | 101 | 192.168.0.11 | 80 | `curl -I http://192.168.0.11` |
| Samba | 104 | 192.168.0.176 | 445 | `nc -zv 192.168.0.176 445` |
| UrBackup | 111 | 192.168.0.209 | 55414 | `curl -I http://192.168.0.209:55414` |
| Komodo | 128 | 192.168.0.179 | 9120 | `curl -I http://192.168.0.179:9120` |
| Grafana | 128 | 192.168.0.179 | 3001 | `curl -I http://192.168.0.179:3001` |
| Prometheus | 128 | 192.168.0.179 | 9092 | `curl -I http://192.168.0.179:9092` |
| Immich | 128 | 192.168.0.179 | 2283 | `curl -I http://192.168.0.179:2283` |
| Frigate | 128 | 192.168.0.179 | 5000 | `curl -I http://192.168.0.179:5000` |

---

## USB Storage Outage Recovery

The Mercury Elite Pro Quad USB enclosure can disconnect due to USB protocol errors.

### Symptoms
- Samba shares unavailable
- Docker services on Komodo failing
- dmesg shows "USB disconnect" and "EXT4-fs error"

### Recovery Steps

```bash
# 1. Check current mounts
mount | grep /mnt/

# 2. Check what SHOULD be mounted (fstab)
cat /etc/fstab | grep /mnt/

# 3. Compare UUIDs
blkid | grep -E 'sdb|sdf'

# 4. If wrong disk mounted, fix it:
umount /mnt/backups
mount UUID=<correct-uuid> /mnt/backups

# 5. Restart affected containers
pct stop 104 && pct start 104  # Samba
pct stop 128 && pct start 128  # Komodo
```

See [incident-2026-01-21-samba-usb-outage.md](incident-2026-01-21-samba-usb-outage.md) for detailed case study.

---

## Post-Emergency Checklist

### Immediate (0-30 min)
- [ ] All services operational
- [ ] User access verified
- [ ] Data integrity confirmed
- [ ] Logs monitored for recurring issues

### Short-term (1-24 hours)
- [ ] Create incident report
- [ ] Root cause analysis
- [ ] Update monitoring/alerting

### Long-term (1-7 days)
- [ ] Implement preventive measures
- [ ] Update procedures if needed
- [ ] Review backup/recovery status

---

## Network Reference

```
Gateway:     192.168.0.1
DNS:         192.168.0.11 (AdGuard)
Proxmox:     192.168.0.151
Subnet:      192.168.0.0/24
```
