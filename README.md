# Proxmox Homelab System Documentation

Official documentation for the Proxmox-based homelab infrastructure.

**Host**: 192.168.0.151 (Shipyard)
**Last Updated**: 2026-01-30

---

## Documentation Index

### Infrastructure

| Document | Description |
|----------|-------------|
| [lxc-onboarding.md](infrastructure/lxc-onboarding.md) | Standard LXC container setup checklist |
| [prometheus-monitoring.md](infrastructure/prometheus-monitoring.md) | Prometheus + Grafana monitoring stack |
| [proxmox-changelog.md](infrastructure/proxmox-changelog.md) | System change history |
| [emergency-procedures.md](infrastructure/emergency-procedures.md) | Emergency response runbook |

### Services

| Document | Description |
|----------|-------------|
| [urbackup-setup.md](services/urbackup-setup.md) | UrBackup server configuration |
| [unmanic-config.md](services/unmanic-config.md) | Unmanic transcoding service |
| [prometheus-config.yaml](services/prometheus-config.yaml) | Prometheus scrape configuration |
| [homeassistant-mcp-integration.md](services/homeassistant-mcp-integration.md) | Home Assistant MCP integration for Claude |
| [rtl433-honeywell-setup.md](services/rtl433-honeywell-setup.md) | RTL-433 SDR + Honeywell 5800 sensor integration |

### Incidents

| Document | Description |
|----------|-------------|
| [2026-01-21-samba-usb-outage.md](incidents/2026-01-21-samba-usb-outage.md) | USB enclosure disconnect causing Samba outage |

---

## Folder Structure

| Folder | Use For |
|--------|---------|
| `infrastructure/` | Proxmox, LXC, networking, storage, monitoring |
| `services/` | Service-specific setup and configuration |
| `incidents/` | Incident reports and post-mortems |
| `troubleshoot/` | Troubleshooting guides and known issues |

### Naming Rules

- **All lowercase** with hyphens (kebab-case)
- **No spaces** in filenames
- **Dates** in ISO format: `YYYY-MM-DD`
- **Documentation**: `.md` (Markdown)

### When to Create New vs Update Existing

| Situation | Action |
|-----------|--------|
| New service installed | Create `services/<name>-setup.md` |
| Infrastructure change | Update relevant `infrastructure/*.md` + changelog |
| Outage or incident | Create `incidents/YYYY-MM-DD-<description>.md` |
| Recurring issue solved | Create `troubleshoot/<topic>.md` |

---

## System Inventory

**[system-inventory.json](system-inventory.json)** - Auto-generated hourly snapshot of system state.

Contains:
- All LXC containers (CTID, name, IP, status, resources)
- All Docker containers and stacks
- Storage pools and usage
- Network bridges
- Host metrics

Commits to git only when meaningful changes detected (new containers, IP changes, status changes).

---

## Quick Reference

### Key IPs

| Service | IP | Port | Purpose |
|---------|-----|------|---------|
| Proxmox | 192.168.0.151 | 8006 | Hypervisor management |
| Komodo | 192.168.0.179 | 9120 | Docker stack management |
| Grafana | 192.168.0.179 | 3001 | Monitoring dashboards |
| Prometheus | 192.168.0.179 | 9092 | Metrics collection |
| AdGuard | 192.168.0.11 | 80 | DNS server |
| UrBackup | 192.168.0.209 | 55414 | Backup server |

### Container Access

All containers use standardized access:
- **Root password**: `password`
- **SSH**: Enabled with root login
- **Console**: Auto-login enabled

See [infrastructure/lxc-onboarding.md](infrastructure/lxc-onboarding.md) for full details.

---

## Contributing

When adding documentation:
1. Place file in appropriate folder
2. Update this README index
3. Include last-updated date in document header
