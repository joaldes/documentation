# Proxmox Homelab System Documentation

Official documentation for the Proxmox-based homelab infrastructure.

**Host**: 192.168.0.151 (Shipyard)
**Last Updated**: 2026-01-26

---

## Documentation Index

### Infrastructure (`infra-*`)

| Document | Description |
|----------|-------------|
| [infra-lxc-onboarding.md](infra-lxc-onboarding.md) | Standard LXC container setup checklist |
| [infra-prometheus-monitoring.md](infra-prometheus-monitoring.md) | Prometheus + Grafana monitoring stack |
| [infra-proxmox-changelog.md](infra-proxmox-changelog.md) | System change history |
| [infra-emergency-procedures.md](infra-emergency-procedures.md) | Emergency response runbook |

### Services (`service-*`)

| Document | Description |
|----------|-------------|
| [service-urbackup-setup.md](service-urbackup-setup.md) | UrBackup server configuration |
| [service-unmanic-config.md](service-unmanic-config.md) | Unmanic transcoding service |
| [service-prometheus-config.yaml](service-prometheus-config.yaml) | Prometheus scrape configuration |
| [service-homeassistant-mcp-integration.md](service-homeassistant-mcp-integration.md) | Home Assistant MCP integration for Claude |

### Incidents (`incident-*`)

| Document | Description |
|----------|-------------|
| [incident-2026-01-21-samba-usb-outage.md](incident-2026-01-21-samba-usb-outage.md) | USB enclosure disconnect causing Samba outage |

---

## Naming Convention

### File Naming Rules

| Prefix | Use For | Examples |
|--------|---------|----------|
| `infra-` | Infrastructure docs (Proxmox, LXC, networking, storage) | `infra-lxc-onboarding.md`, `infra-emergency-procedures.md` |
| `service-` | Service-specific setup and configuration | `service-urbackup-setup.md`, `service-immich-config.md` |
| `incident-` | Incident reports and post-mortems | `incident-2026-01-21-samba-usb-outage.md` |
| `troubleshoot-` | Troubleshooting guides and known issues | `troubleshoot-ext4-noise.md` |

### Format Rules

- **All lowercase** with hyphens (kebab-case)
- **No spaces** in filenames
- **Dates** in ISO format: `YYYY-MM-DD`
- **Config files**: `service-<name>-config.yaml`
- **Documentation**: `.md` (Markdown)

### Document Header Template

Every document should start with:
```markdown
# Title

**Last Updated**: YYYY-MM-DD
**Related Systems**: Container X, Service Y
```

### When to Create New vs Update Existing

| Situation | Action |
|-----------|--------|
| New service installed | Create `service-<name>-setup.md` |
| Infrastructure change | Update relevant `infra-*.md` + changelog |
| Outage or incident | Create `incident-YYYY-MM-DD-<description>.md` |
| Recurring issue solved | Create `troubleshoot-<topic>.md` |
| Config file changed | Update existing or create `service-<name>-config.yaml` |

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

See [infra-lxc-onboarding.md](infra-lxc-onboarding.md) for full details.

---

## Contributing

When adding documentation:
1. Use the naming convention above
2. Update this README index
3. Include last-updated date in document header

*Last synced: 2026-01-29 03:48 UTC*
