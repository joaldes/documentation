# Local `.home` Domain Setup

**Last Updated**: 2026-02-24
**Related Systems**: AdGuard DNS (Container 101), Nginx Proxy Manager (Container 112), All web services

## Summary
Configured 38+ local `.home` domains for all web services, routed through Nginx Proxy Manager. Services are accessible at clean URLs like `http://paperless.home` from any device on the LAN using AdGuard as DNS. No internet required.

A wildcard `*.1701.me` DNS rewrite was also added (2026-02-24) so that all `.1701.me` domains resolve locally to NPM when on the LAN, bypassing hairpin NAT through the public IP.

## How It Works
1. **AdGuard DNS** (192.168.0.11) has a DNS rewrite for each `.home` domain pointing to NPM (192.168.0.30)
2. **Nginx Proxy Manager** (192.168.0.30) receives the request, matches the hostname, and routes to the correct backend IP:port
3. Browser loads the service — no port number needed in the URL

### `.1701.me` Wildcard (added 2026-02-24)

A single wildcard rewrite `*.1701.me → 192.168.0.30` means all `.1701.me` domains resolve to NPM locally. This avoids hairpin NAT (where local requests to `*.1701.me` would resolve to the public IP 76.159.199.214, leave the network, and come back in). With this rewrite, local requests stay on the LAN.

**External access still works**: devices outside the LAN don't use AdGuard, so they resolve `*.1701.me` via the public CNAME as before.

## Domain List

### Standalone Containers

| Domain | Backend | Container |
|--------|---------|-----------|
| `adguard.home` | 192.168.0.11:80 | 101 |
| `bazarr.home` | 192.168.0.48:6767 | 115 |
| `claude.home` | 192.168.0.180:3000 | 124 |
| `emby.home` | 192.168.0.13:8096 | 102 |
| `frigate.home` | 192.168.0.122:5000 | — |
| `homepage.home` | 192.168.0.70:3000 | 118 |
| `homeassistant.home` | 192.168.0.154:8123 | VM 100 |
| `jellyseerr.home` | 192.168.0.43:5055 | 113 |
| `npm.home` | 192.168.0.30:81 | 112 |
| `proxmox.home` | 192.168.0.151:8006 | Host |
| `pulse.home` | 192.168.0.175:7655 | 120 |
| `radarr.home` | 192.168.0.42:7878 | 107 |
| `sonarr.home` | 192.168.0.24:8989 | 110 |
| `syncthing.home` | 192.168.0.45:8384 | 103 |
| `tracearr.home` | 192.168.0.211:3000 | 116 |
| `unmanic.home` | 192.168.0.207:8888 | 105 |
| `uptimekuma.home` | 192.168.0.44:3001 | 114 |
| `urbackup.home` | 192.168.0.209:55414 | 111 |
| `wikijs.home` | 192.168.0.57:3000 | 117 |
| `zwave.home` | 192.168.0.153:8091 | 108 |

### Docker Services on Komodo (192.168.0.179)

| Domain | Port |
|--------|------|
| `authentik.home` | 9000 |
| `bentopdf.home` | 8095 |
| `birds.home` | 8060 |
| `fragments.home` | 8075 |
| `grafana.home` | 3001 |
| `immich.home` | 2283 |
| `jellystat.home` | 3000 |
| `komodo.home` | 9120 |
| `manyfold.home` | 3214 |
| `mealie.home` | 9925 |
| `paperless.home` | 8010 |
| `paperless-ai.home` | 3030 |
| `prometheus.home` | 9092 |
| `reyday.home` | 8105 |
| `sander.home` | 8100 |
| `tandoor.home` | 8090 |
| `weather.home` | 8076 |

## Adding a New `.home` Domain

1. **AdGuard**: Add DNS rewrite via API or web UI (`http://192.168.0.11`)
   ```bash
   curl -u adguarduser:adguardpassword -X POST http://192.168.0.11/control/rewrite/add \
     -H 'Content-Type: application/json' \
     -d '{"domain":"newservice.home","answer":"192.168.0.30","enabled":true}'
   ```

2. **NPM**: Add proxy host via web UI (`http://192.168.0.30:81`) or API
   - Domain: `newservice.home`
   - Forward: `http://<service-ip>:<port>`

## Troubleshooting

- **Domain goes to internet instead of local service**: Device is not using AdGuard (192.168.0.11) as its DNS server
- **404 from NPM**: DNS rewrite exists but no matching NPM proxy host — create one in NPM
- **Service loads but iframe blocked in HA**: Add `proxy_hide_header X-Frame-Options;` in the NPM proxy host's Advanced tab
- **Can't get HTTPS**: `.home` domains cannot get Let's Encrypt certificates — use HTTP only, or use `.1701.me` domains for HTTPS

## Related Incidents
- [2026-02-18-birdnet-iframe-blocked.md](../incidents/2026-02-18-birdnet-iframe-blocked.md) — BirdNET X-Frame-Options fix via NPM
- [2026-02-18-uptime-kuma-iframe-blocked.md](../incidents/2026-02-18-uptime-kuma-iframe-blocked.md) — Uptime Kuma native env var fix
