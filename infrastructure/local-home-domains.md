# Local `.lan` Domain Setup

**Last Updated**: 2026-03-28
**Related Systems**: AdGuard DNS (Container 101), Nginx Proxy Manager (Container 112), All web services

## Summary
Configured 41 local `.lan` domains for all web services, routed through Nginx Proxy Manager. Services are accessible at clean URLs like `http://paperless.lan` from any device on the LAN using AdGuard as DNS. No internet required.

**Migration note (2026-03-28):** Migrated from `.home` to `.lan` because `.home` was added as a real IANA TLD in 2023, risking future DNS conflicts. AdGuard DHCP's `local_domain_name` was changed from `lan` to `dhcp` to avoid conflicts with DHCP auto-hostnames.

A wildcard `*.1701.me` DNS rewrite also exists (added 2026-02-24) so that all `.1701.me` domains resolve locally to NPM when on the LAN, bypassing hairpin NAT through the public IP.

## How It Works
1. **AdGuard DNS** (192.168.0.11) has a DNS rewrite for each `.lan` domain pointing to NPM (192.168.0.30)
2. **Nginx Proxy Manager** (192.168.0.30) receives the request, matches the hostname, and routes to the correct backend IP:port
3. Browser loads the service — no port number needed in the URL

### `.1701.me` Wildcard (added 2026-02-24)

A single wildcard rewrite `*.1701.me → 192.168.0.30` means all `.1701.me` domains resolve to NPM locally. This avoids hairpin NAT (where local requests to `*.1701.me` would resolve to the public IP 76.159.199.214, leave the network, and come back in). With this rewrite, local requests stay on the LAN.

**External access still works**: devices outside the LAN don't use AdGuard, so they resolve `*.1701.me` via the public CNAME as before.

## Domain List

### Standalone Containers

| Domain | Backend | Container |
|--------|---------|-----------|
| `adguard.lan` | 192.168.0.11:80 | 101 |
| `bazarr.lan` | 192.168.0.48:6767 | 115 |
| `claude.lan` | 192.168.0.180:3000 | 124 |
| `emby.lan` | 192.168.0.13:8096 | 102 |
| `frigate.lan` | 192.168.0.122:5000 | — |
| `homelable.lan` | 192.168.0.218:80 | 109 |
| `homepage.lan` | 192.168.0.70:3000 | 118 |
| `homeassistant.lan` | 192.168.0.154:8123 | VM 100 |
| `jellyseerr.lan` | 192.168.0.43:5055 | 113 |
| `npm.lan` | 192.168.0.30:81 | 112 |
| `proxmox.lan` | 192.168.0.151:8006 | Host |
| `pulse.lan` | 192.168.0.175:7655 | 120 |
| `radarr.lan` | 192.168.0.42:7878 | 107 |
| `scanopy.lan` | 192.168.0.219:60072 | 121 |
| `sonarr.lan` | 192.168.0.24:8989 | 110 |
| `syncthing.lan` | 192.168.0.45:8384 | 103 |
| `tracearr.lan` | 192.168.0.211:3000 | 116 |
| `unmanic.lan` | 192.168.0.207:8888 | 105 |
| `uptimekuma.lan` | 192.168.0.44:3001 | 114 |
| `urbackup.lan` | 192.168.0.209:55414 | 111 |
| `wikijs.lan` | 192.168.0.57:3000 | 117 |
| `zwave.lan` | 192.168.0.153:8091 | 108 |

### Docker Services on Komodo (192.168.0.179)

| Domain | Port |
|--------|------|
| `authentik.lan` | 9000 |
| `bentopdf.lan` | 8095 |
| `birds.lan` | 8060 |
| `fragments.lan` | 8075 |
| `grafana.lan` | 3001 |
| `immich.lan` | 2283 |
| `jellystat.lan` | 3000 |
| `komodo.lan` | 9120 |
| `manyfold.lan` | 3214 |
| `mealie.lan` | 9925 |
| `notifiarr.lan` | — |
| `paperless.lan` | 8010 |
| `paperless-ai.lan` | 3030 |
| `prometheus.lan` | 9092 |
| `reyday.lan` | 8105 |
| `sander.lan` | 8100 |
| `tandoor.lan` | 8090 |
| `tdarr.lan` | — |
| `weather.lan` | 8076 |

## Adding a New `.lan` Domain

1. **AdGuard**: Add DNS rewrite via API or web UI (`http://192.168.0.11`)
   ```bash
   curl -u adguarduser:adguardpassword -X POST http://192.168.0.11/control/rewrite/add \
     -H 'Content-Type: application/json' \
     -d '{"domain":"newservice.lan","answer":"192.168.0.30","enabled":true}'
   ```

2. **NPM**: Add proxy host via web UI (`http://192.168.0.30:81`) or API
   - Domain: `newservice.lan`
   - Forward: `http://<service-ip>:<port>`

## Troubleshooting

- **Domain goes to internet instead of local service**: Device is not using AdGuard (192.168.0.11) as its DNS server
- **404 from NPM**: DNS rewrite exists but no matching NPM proxy host — create one in NPM
- **Service loads but iframe blocked in HA**: Add `proxy_hide_header X-Frame-Options;` in the NPM proxy host's Advanced tab
- **Can't get HTTPS**: `.lan` domains cannot get Let's Encrypt certificates — use HTTP only, or use `.1701.me` domains for HTTPS
- **Domain resolves to wrong IP**: Check if a DHCP hostname conflicts — AdGuard DHCP uses `local_domain_name: dhcp` (changed from `lan` on 2026-03-28)

## SSL Certificates (`.1701.me` domains)

Let's Encrypt certificates managed by NPM (CT 112):

| Domain | NPM Cert ID | Proxy Host | Notes |
|--------|-------------|------------|-------|
| `home.1701.me` | 18 | #23 | Force SSL, HTTP/2 — Trailhead dashboard |
| `auth.1701.me` | 19 | #54 | Force SSL, HTTP/2 — Authentik SSO |

Added 2026-03-07 to enable external HTTPS access from mobile networks.

## Related Incidents
- [2026-02-18-birdnet-iframe-blocked.md](../incidents/2026-02-18-birdnet-iframe-blocked.md) — BirdNET X-Frame-Options fix via NPM
- [2026-02-18-uptime-kuma-iframe-blocked.md](../incidents/2026-02-18-uptime-kuma-iframe-blocked.md) — Uptime Kuma native env var fix
