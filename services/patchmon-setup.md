# PatchMon — Service Version & Patch Monitoring

**Last Updated**: 2026-03-24
**Related Systems**: CT 109 (PatchMon), All LXC Containers, CT 128 (Komodo/Docker)

## Summary

PatchMon is an open-source Linux patch monitoring platform that provides a single dashboard showing all hosts, their installed packages, Docker containers, and available updates. Deployed as a dedicated LXC container (CT 109) via the Proxmox community script, with lightweight Go agents installed on each LXC container.

## Why PatchMon

The homelab runs ~35 services across 20 LXC containers, 45+ Docker containers, and 1 VM with no centralized way to track which services have updates available. PatchMon provides:

- **Single pane of glass** for all Linux servers — package updates, Docker container monitoring, host inventory
- **Lightweight Go agents** on each LXC container (outbound-only, no inbound ports needed)
- **Docker monitoring** built-in — auto-discovers containers, images, volumes on CT 128
- **Proxmox integration** — LXC auto-enrollment support
- **Authentik OIDC SSO** support
- **Web SSH terminal**, compliance scanning, alerting, RBAC
- Active development (2400+ stars, v1.5 coming April 2026)

## Deployment

### Step 1: Create PatchMon LXC Container

Run the Proxmox community script from the host shell:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/ct/patchmon.sh)"
```

This creates a new LXC container with PatchMon pre-installed natively (not Docker). It sets up Node.js, PostgreSQL, Redis, nginx, and a systemd service (`patchmon-server`).

**Container details**:
- **CTID**: 109
- **Port**: 3000 (nginx frontend, proxying to backend on 3001 internally)
- **Resources**: 2 CPU cores, 2048 MB RAM, 4 GB disk, Debian 13
- **Install version**: v1.4.2

After creation, apply standard LXC onboarding:
- Set root password to `password`
- Enable console auto-login
- Disable AppArmor (`lxc.apparmor.profile: unconfined`)
- Enable unattended-upgrades

### Step 2: Initial Configuration

1. Open PatchMon UI at `http://<patchmon-ip>:3000`
2. Complete first-time admin setup (create admin account)
3. Set timezone to `America/Phoenix`

### Step 3: Install Agents on LXC Containers

PatchMon uses a lightweight Go agent binary that communicates outbound-only to the PatchMon server. The agent reports packages, repos, Docker containers, and system info on a cron schedule.

**Agent installation per container:**

1. In PatchMon UI: Hosts → Add Host → generates download link + API credentials
2. Install and configure:

```bash
# Download binary (architecture: linux-amd64)
curl -fsSL -o /usr/local/bin/patchmon-agent <download-url>
chmod +x /usr/local/bin/patchmon-agent

# Configure with API credentials from PatchMon UI
patchmon-agent config set-api <API_ID> <API_KEY> http://<patchmon-ip>:3000

# Test connectivity
patchmon-agent ping

# Send initial report
patchmon-agent report

# Set up cron for automatic reporting
patchmon-agent update-crontab
```

**Agent config files:**
- Main config: `/etc/patchmon/config.yml`
- Credentials: `/etc/patchmon/credentials.yml` (600 permissions)
- Logs: `/var/log/patchmon-agent.log`

**Containers to enroll** (20 total):

| CTID | Name | Services to Track |
|------|------|-------------------|
| 101 | adguard | AdGuard Home |
| 102 | emby | Emby Media Server |
| 103 | syncthing | Syncthing |
| 104 | samba | Samba |
| 105 | unmanic | Unmanic |
| 107 | radarr | Radarr |
| 108 | zwave-js-ui | Z-Wave JS UI |
| 110 | sonarr | Sonarr |
| 111 | urbackup | UrBackup |
| 112 | nginxproxymanager | Nginx Proxy Manager |
| 113 | jellyseerr | Jellyseerr |
| 114 | uptimekuma | Uptime Kuma |
| 115 | bazarr | Bazarr |
| 116 | tracearr | Tracearr |
| 117 | wikijs | Wiki.js |
| 118 | homepage | Homepage |
| 120 | pulse | Pulse |
| 124 | claudeai | Claude AI |
| 128 | komodo | Docker stacks (Immich, Authentik, Frigate, Paperless, etc.) |
| 130 | ollama | Ollama + Open WebUI |

Binary download can be batched via `pct exec`, but API credentials are generated per-host from the PatchMon UI (each host gets unique API_ID/API_KEY).

### Step 4: Docker Monitoring on CT 128

PatchMon auto-discovers Docker containers when the agent has access to the Docker socket. The agent on CT 128 (Komodo) should automatically detect all 45+ Docker containers, their images, and versions.

No extra configuration needed — the agent handles Docker discovery automatically.

### Step 5: Optional — Authentik SSO Integration

PatchMon supports OIDC SSO. Configure in PatchMon backend `.env`:

```
OIDC_ENABLED=true
OIDC_ISSUER_URL=https://auth.1701.me/application/o/patchmon/
OIDC_CLIENT_ID=<from authentik>
OIDC_CLIENT_SECRET=<from authentik>
OIDC_REDIRECT_URI=http://<patchmon-ip>:3000/api/v1/auth/oidc/callback
```

Create an OAuth2 provider + application in Authentik first.

### Step 6: Optional — Add to Nginx Proxy Manager

For external access: add a proxy host in NPM pointing to `<patchmon-ip>:3000`, with Authentik forward auth.

## Agent Management

```bash
# Check agent status
patchmon-agent ping

# Force a report
patchmon-agent report

# Check for agent updates
patchmon-agent check-version

# Update agent to latest
patchmon-agent update-agent

# View config
patchmon-agent config show
```

## Verification

1. PatchMon UI loads at `http://<patchmon-ip>:3000`
2. All 20 LXC containers show as enrolled hosts
3. Docker containers on CT 128 appear in Docker monitoring
4. Package updates are detected for at least some hosts
5. Dashboard shows summary of outdated packages across fleet

## Troubleshooting

### Agent Not Reporting
```bash
# Check agent logs
cat /var/log/patchmon-agent.log

# Verify connectivity
patchmon-agent ping

# Check cron is set up
crontab -l | grep patchmon
```

### PatchMon Server Issues (CT 109)
```bash
# Check service status
systemctl status patchmon-server

# Check nginx
systemctl status nginx

# Check PostgreSQL
systemctl status postgresql

# View server logs
journalctl -u patchmon-server -f
```

### Updating PatchMon Server
Run the community script update function:
```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/ct/patchmon.sh)"
# Select "Update" when prompted
```

## Key URLs

- **PatchMon UI**: `http://<patchmon-ip>:3000`
- **PatchMon docs**: https://docs.patchmon.net
- **GitHub**: https://github.com/PatchMon/PatchMon
- **Proxmox community script**: https://community-scripts.github.io/ProxmoxVE/scripts?id=patchmon
- **Discord**: https://patchmon.net/discord
