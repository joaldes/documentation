# Proxmox Homelab Monitoring Stack

A comprehensive Prometheus + Grafana monitoring solution for a Proxmox-based homelab infrastructure.

## Overview

This monitoring stack provides complete observability for:
- **Proxmox host** - CPU, memory, disk, network metrics
- **LXC containers** - Per-container resource usage via Node Exporter
- **Docker containers** - Container metrics via cAdvisor
- **Services** - HTTP/TCP endpoint monitoring via Blackbox Exporter
- **Proxmox VE API** - VM/LXC stats via PVE Exporter

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Proxmox Host (192.168.0.151)                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │ Node Exporter   │  │ PVE Exporter    │  │ LXC Containers      │  │
│  │ :9100           │  │ :9221           │  │ (Node Exporter each)│  │
│  └────────┬────────┘  └────────┬────────┘  └──────────┬──────────┘  │
└───────────┼─────────────────────┼─────────────────────┼─────────────┘
            │                     │                     │
            └──────────┬──────────┴──────────┬──────────┘
                       │                     │
┌──────────────────────▼─────────────────────▼────────────────────────┐
│                    Komodo LXC (192.168.0.179)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │ Prometheus  │  │ Grafana     │  │ Alertmanager│  │ Blackbox   │  │
│  │ :9092       │  │ :3001       │  │ :9093       │  │ :9115      │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │
│  ┌─────────────┐  ┌─────────────┐                                   │
│  │ cAdvisor    │  │ Node Export │                                   │
│  │ :8080       │  │ :9100       │                                   │
│  └─────────────┘  └─────────────┘                                   │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

| Component | Port | Purpose |
|-----------|------|---------|
| Prometheus | 9092 | Metrics collection and storage |
| Grafana | 3001 | Visualization and dashboards |
| Alertmanager | 9093 | Alert routing and notifications |
| Node Exporter | 9100 | Host/container system metrics |
| PVE Exporter | 9221 | Proxmox VE API metrics |
| Blackbox Exporter | 9115 | HTTP/TCP endpoint probing |
| cAdvisor | 8080 | Docker container metrics |

## Monitored Targets

### LXC Containers (18 active)

| Container | IP | VMID | Status |
|-----------|-----|------|--------|
| adguard | 192.168.0.11 | 101 | Active |
| emby | 192.168.0.13 | 102 | Active |
| syncthing | 192.168.0.45 | 103 | Active |
| samba | 192.168.0.176 | 104 | Active |
| unmanic | 192.168.0.207 | 105 | Active |
| radarr | 192.168.0.42 | 107 | Active |
| zwave-js-ui | 192.168.0.153 | 108 | Active |
| tdarr | 192.168.0.51 | 109 | Stopped |
| sonarr | 192.168.0.24 | 110 | Active |
| urbackup | 192.168.0.209 | 111 | Active |
| nginxproxymanager | 192.168.0.30 | 112 | Active |
| jellyseerr | 192.168.0.43 | 113 | Active |
| uptimekuma | 192.168.0.44 | 114 | Active |
| bazarr | 192.168.0.48 | 115 | Active |
| wikijs | 192.168.0.57 | 117 | Active |
| homepage | 192.168.0.70 | 118 | Active |
| pulse | 192.168.0.175 | 120 | Active |
| notifiarr | 192.168.0.96 | 121 | Stopped |
| claude-ai | 192.168.0.180 | 124 | Active |
| komodo | 192.168.0.179 | 128 | Active |

### Blackbox HTTP Probes (26 endpoints)

Monitors web services including:
- Proxmox Web UI (https://192.168.0.151:8006)
- AdGuard, NPM, Uptime Kuma, Homepage, Home Assistant
- Media stack: Emby, Radarr, Sonarr, Bazarr, Jellyseerr, Tdarr
- Komodo Docker services: Immich, Paperless-NGX, Tandoor, Stirling PDF, Frigate, Mealie, Komodo UI

### Blackbox TCP Probes (2 endpoints)

- Samba SMB (192.168.0.176:445)
- Komodo SSH (192.168.0.179:22)

## Installation

### Prerequisites

- Proxmox VE host with LXC containers
- Docker installed on monitoring host (Komodo LXC)
- Network connectivity between all containers

### 1. Install Node Exporter on Proxmox Host

```bash
# On Proxmox host
apt-get update && apt-get install -y prometheus-node-exporter
systemctl enable --now prometheus-node-exporter
```

### 2. Install PVE Exporter on Proxmox Host

```bash
# Install
pip3 install prometheus-pve-exporter

# Create config
cat > /etc/prometheus/pve.yml << 'EOF'
default:
  user: prometheus@pve
  token_name: prometheus
  token_value: YOUR_TOKEN_HERE
  verify_ssl: false
EOF

# Create systemd service
cat > /etc/systemd/system/prometheus-pve-exporter.service << 'EOF'
[Unit]
Description=Prometheus PVE Exporter
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/pve_exporter --config.file /etc/prometheus/pve.yml
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now prometheus-pve-exporter
```

### 3. Install Node Exporter on LXC Containers

```bash
# From Proxmox host, for each container:
pct exec <CTID> -- bash -c 'apt-get update && apt-get install -y prometheus-node-exporter && systemctl enable --now prometheus-node-exporter'
```

### 4. Deploy Monitoring Stack on Docker Host

Create `/etc/komodo/stacks/prometheus/compose.yaml`:

```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9092:9090"
    volumes:
      - ./prometheus.yaml:/etc/prometheus/prometheus.yml:ro
      - ./rules:/etc/prometheus/rules:ro
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:latest
    container_name: alertmanager
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
      - alertmanager-data:/alertmanager
    restart: unless-stopped

  blackbox-exporter:
    image: prom/blackbox-exporter:latest
    container_name: blackbox-exporter
    ports:
      - "9115:9115"
    volumes:
      - ./blackbox.yml:/config/blackbox.yml:ro
    command:
      - '--config.file=/config/blackbox.yml'
    cap_add:
      - NET_RAW
    restart: unless-stopped

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    container_name: cadvisor
    ports:
      - "8080:8080"
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
    privileged: true
    restart: unless-stopped

volumes:
  prometheus-data:
  alertmanager-data:
```

### 5. Start the Stack

```bash
cd /etc/komodo/stacks/prometheus
docker compose up -d
```

## Configuration Files

### Prometheus Config (`prometheus.yaml`)

See [prometheus-new.yaml](prometheus-new.yaml) for the full configuration.

Key sections:
- Global scrape interval: 30s
- Alert rules: `/etc/prometheus/rules/*.yml`
- Alertmanager: `alertmanager:9093`

### Blackbox Config (`blackbox.yml`)

```yaml
modules:
  http_2xx:
    prober: http
    timeout: 10s
    http:
      valid_http_versions: ["HTTP/1.1", "HTTP/2.0"]
      valid_status_codes: [200, 301, 302, 401, 403]
      follow_redirects: true
      preferred_ip_protocol: "ip4"
      tls_config:
        insecure_skip_verify: true

  tcp_connect:
    prober: tcp
    timeout: 10s
```

### Alertmanager Config (`alertmanager.yml`)

```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default'

receivers:
  - name: 'default'
```

## Alert Rules

Located in `/etc/prometheus/rules/alerts.yml`:

| Alert | Severity | Description |
|-------|----------|-------------|
| InstanceDown | critical | Target unreachable for 2 minutes |
| MountReadOnly | critical | Filesystem mounted read-only (USB disconnect detection) |
| DiskSpaceCritical | critical | Less than 10% disk space |
| DiskSpaceWarning | warning | Less than 20% disk space |
| HighMemoryUsage | warning | Memory usage above 90% |
| HighCPUUsage | warning | CPU usage above 80% for 5 minutes |
| ContainerDown | critical | Docker container stopped |
| ServiceDown | critical | HTTP endpoint unreachable |
| SambaDown | critical | SMB port unreachable |
| ContainerHighMemory | warning | Container using >1GB memory |
| ProxmoxNodeDown | critical | Proxmox host unreachable |

## Grafana Dashboards

Access Grafana at: http://192.168.0.179:3001

**Credentials:** admin / admin123

### Imported Dashboards

| Dashboard | ID | Purpose |
|-----------|----|---------|
| Node Exporter Full | 1860 | Detailed host/container metrics |
| Cadvisor Exporter | 14282 | Docker container metrics |
| Blackbox Exporter (HTTP prober) | - | HTTP endpoint status |
| Proxmox via Prometheus | 10347 | Proxmox VE metrics |

## Useful PromQL Queries

### Container CPU Usage
```promql
100 - (avg by(container) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

### Container Memory Usage
```promql
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100
```

### Disk Space Used
```promql
100 - ((node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100)
```

### Service Availability
```promql
probe_success{job="blackbox-http"}
```

### Docker Container Status
```promql
container_last_seen{name!=""}
```

## Troubleshooting

### Check Target Status
```bash
curl -s 'http://192.168.0.179:9092/api/v1/targets' | jq '.data.activeTargets[] | {job: .labels.job, health: .health, instance: .labels.instance}'
```

### Reload Prometheus Config
```bash
docker exec prometheus kill -HUP 1
# or
curl -X POST http://192.168.0.179:9092/-/reload
```

### View Prometheus Logs
```bash
docker logs prometheus --tail 100
```

### Test Blackbox Probe
```bash
curl 'http://192.168.0.179:9115/probe?target=http://192.168.0.70:3000&module=http_2xx'
```

### Check Alert Status
```bash
curl -s 'http://192.168.0.179:9092/api/v1/alerts' | jq '.data.alerts[]'
```

## Known Issues

1. **Stopped containers show as down** - This is expected behavior. Containers 109 (tdarr) and 121 (notifiarr) are intentionally stopped.

2. **PVE Exporter requires `--config.file` flag** - Version 3.8.0+ changed the CLI syntax from positional argument to named flag.

3. **Docker networking** - Prometheus config must use container names (e.g., `blackbox-exporter:9115`) not `localhost` when running in Docker.

## Maintenance

### Update Containers
```bash
cd /etc/komodo/stacks/prometheus
docker compose pull
docker compose up -d
```

### Backup Prometheus Data
```bash
docker run --rm -v prometheus-data:/data -v $(pwd):/backup alpine tar czf /backup/prometheus-backup.tar.gz /data
```

### Clear Old Data
```bash
# Prometheus auto-prunes based on retention (30d default)
# To manually compact:
curl -X POST http://192.168.0.179:9092/api/v1/admin/tsdb/clean_tombstones
```

## Implementation Log

- **2026-01-21**: Initial deployment
  - Installed Node Exporter on Proxmox host and 18 LXC containers
  - Installed PVE Exporter on Proxmox host (fixed `--config.file` flag issue)
  - Deployed Prometheus, Alertmanager, Blackbox Exporter, cAdvisor on Komodo
  - Fixed Docker networking (localhost → container names)
  - Created alert rules for infrastructure and services
  - Imported 4 Grafana dashboards
  - Verified Frigate native metrics at :5000/api/metrics

## License

This configuration is provided as-is for homelab use.
