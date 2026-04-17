# Proxmox Homelab System Documentation

Official documentation for the Proxmox-based homelab infrastructure.

**Host**: 192.168.0.151 (Shipyard)
**Last Updated**: 2026-04-17

---

## Documentation Index

### Infrastructure

| Document | Description |
|----------|-------------|
| [lxc-onboarding.md](infrastructure/lxc-onboarding.md) | Standard LXC container setup checklist |
| [prometheus-monitoring.md](infrastructure/prometheus-monitoring.md) | Prometheus + Grafana monitoring stack |
| [proxmox-changelog.md](infrastructure/proxmox-changelog.md) | System change history |
| [emergency-procedures.md](infrastructure/emergency-procedures.md) | Emergency response runbook |
| [backups-samba-share.md](infrastructure/backups-samba-share.md) | Backups disk Samba share + Mac HFS+ data copy |
| [local-home-domains.md](infrastructure/local-home-domains.md) | Local .home domain setup (AdGuard DNS + NPM routing) |
| [docker-cpu-optimization.md](infrastructure/docker-cpu-optimization.md) | Docker CPU resource limits & cAdvisor tuning (CT 128) |
| [subtitle-standardization.md](infrastructure/subtitle-standardization.md) | Subtitle filename standardization (Emby naming conventions) |
| [samba-smb3-migration.md](infrastructure/samba-smb3-migration.md) | Samba minimum protocol raised to SMB3, LANMAN/NTLMv1 disabled (CT 104) |

### Services

| Document | Description |
|----------|-------------|
| [urbackup-setup.md](services/urbackup-setup.md) | UrBackup server configuration |
| [unmanic-config.md](services/unmanic-config.md) | Unmanic transcoding service |
| [prometheus-config.yaml](services/prometheus-config.yaml) | Prometheus scrape configuration |
| [homeassistant-mcp-integration.md](services/homeassistant-mcp-integration.md) | Home Assistant MCP integration for Claude |
| [rtl433-honeywell-setup.md](services/rtl433-honeywell-setup.md) | RTL-433 SDR + Honeywell 5800 sensor integration |
| [birdnet-deployment-guide.md](services/birdnet-deployment-guide.md) | BirdNET bird detection system (Pi audio stream + BirdNET-Go + settings) |
| [reyday-file-server.md](services/reyday-file-server.md) | Reyday media file server with upload (nginx + WebDAV) |
| [trailhead.md](services/trailhead.md) | Trailhead — Weather & Wildlife dashboard (Ecowitt + BirdNET + Authentik SSO + NPS design) |
| [ollama.md](services/ollama.md) | Ollama + Open WebUI — Local LLM inference on Intel iGPU (CT 130) |
| [scanopy.md](services/scanopy.md) | Scanopy — Network scanner & host inventory (CT 121) |
| [timeteam-downloads.md](services/timeteam-downloads.md) | Time Team complete download system — YouTube + Patreon to Emby library |
| [timeteam-runbook.md](services/timeteam-runbook.md) | Time Team library processing runbook — download, classify, rename, Emby sync |

### Incidents

| Document | Description |
|----------|-------------|
| [2026-01-21-samba-usb-outage.md](incidents/2026-01-21-samba-usb-outage.md) | USB enclosure disconnect causing Samba outage |
| [2026-02-04-ha-cpu-spike-piper-bootloop.md](incidents/2026-02-04-ha-cpu-spike-piper-bootloop.md) | Home Assistant CPU spike from Piper add-on boot loop |
| [2026-02-06-urbackup-wrong-disk-mounted.md](incidents/2026-02-06-urbackup-wrong-disk-mounted.md) | UrBackup missing clients due to wrong disk mounted |
| [2026-02-16-zwave-usb-passthrough-stale.md](incidents/2026-02-16-zwave-usb-passthrough-stale.md) | Z-Wave USB passthrough stale device number on CT 108 |
| [2026-02-18-birdnet-iframe-blocked.md](incidents/2026-02-18-birdnet-iframe-blocked.md) | BirdNET-Go iframe blocked in Home Assistant by X-Frame-Options header |
| [2026-02-18-uptime-kuma-iframe-blocked.md](incidents/2026-02-18-uptime-kuma-iframe-blocked.md) | Uptime Kuma iframe blocked in HA — fixed with native env var |
| [2026-03-08-immich-frozen-ui.md](incidents/2026-03-08-immich-frozen-ui.md) | Immich frozen UI incident |
| [2026-03-12-birdnet-owl-detection-drop.md](incidents/2026-03-12-birdnet-owl-detection-drop.md) | BirdNET owl detection 90% drop — false positive filter/overlap mismatch |
| [2026-03-13-trailhead-sky-tv-navigation-broken.md](incidents/2026-03-13-trailhead-sky-tv-navigation-broken.md) | Trailhead Sky Events & TV Calendar pages not loading — nginx regex mismatch |
| [2026-03-23-frigate-detect-stream-offline.md](incidents/2026-03-23-frigate-detect-stream-offline.md) | Frigate detect stream offline — PID limit not applied after container recreation |
| [2026-04-06-nightstand-button-duplicates.md](incidents/2026-04-06-nightstand-button-duplicates.md) | Nightstand button sending duplicate commands |
| [2026-04-16-lizard-tank-overheat.md](incidents/2026-04-16-lizard-tank-overheat.md) | Lizard tank aux heat stuck ON 5hrs — old NR flow binary sensor gate blocked turn-off |

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

### One Doc Per Service

Each service gets exactly **one** comprehensive document in `services/`. All subsystems, configuration, access control, and troubleshooting for a service belong in that single file as separate sections. This prevents documentation drift between multiple files covering the same service.

- No separate setup/config/rebuild/permissions docs that can drift apart
- If a service has multiple subsystems (e.g., Trailhead + Authentik SSO), use sections within the single doc
- Incidents stay in `incidents/` — they're timestamped events, not service docs

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
- All VMs (VMID, name, status)
- Docker stacks grouped by compose project (name, container count, state)
- Storage pools and usage
- Network bridges
- Host metrics

Generated by `/root/bin/system-inventory.sh` on Proxmox host. Commits to git only when meaningful changes detected (new containers, stack state changes, IP changes).

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
| BirdNET-Go | 192.168.0.179 | 8060 | Bird detection (on Komodo) |
| BirdNET Pi | 192.168.0.136 | 8554 | RTSP audio stream (gazebo) |
| Trailhead | 192.168.0.179 | 8076 | Weather & wildlife dashboard (on Komodo) |
| Ollama | 192.168.0.130 | 11434 | Local LLM API |
| Open WebUI | 192.168.0.130 | 8085 | Ollama chat interface |

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
