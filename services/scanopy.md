# Scanopy — Network Scanner & Inventory

**Last Updated**: 2026-03-29
**Related Systems**: Container 121 (Scanopy), Container 128 (Komodo/Daemon), AdGuard DNS (101), NPM (112)

## Summary

Scanopy (CT 121) is a network scanner and host inventory tool that discovers and catalogs all devices, services, and ports on the LAN. It runs at `http://scanopy.home` (192.168.0.219:60072) and provides a visual network map with service groups. A daemon runs on Komodo (CT 128) to discover Docker containers automatically.

## Access

| Item | Value |
|------|-------|
| Web UI | `http://scanopy.home` |
| API | `http://192.168.0.219:60072/api/v1` |
| API Token | `Bearer scp_u_SbQNNIfPqOvIKALLKop8zhiaMPEtrs0A` |
| Container | CT 121 (192.168.0.219) |
| PostgreSQL | `scanopy-postgres-1` container inside CT 121 (user: postgres, pw: password, db: scanopy) |

## Architecture

1. **Scanopy Server** (CT 121) — web UI + API + PostgreSQL database
2. **Scanopy Daemon** (Docker on Komodo, CT 128) — network scanner + Docker container discovery
   - Image: `ghcr.io/scanopy/scanopy/daemon:latest`
   - Runs with `--network host` to see the full LAN
   - Discovers hosts, open ports, and Docker containers on Komodo
   - Daemon API key prefix: `scp_d_`

## Current Inventory

**61 total hosts** (58 visible, 3 hidden)

### Tags

| Tag | Color | Purpose |
|-----|-------|---------|
| proxmox-container | Blue | LXC containers and VMs on Shipyard |
| docker-service | Purple | Hosts running Docker services |
| iot | Orange | IoT devices (cameras, sensors, bulbs, etc.) |
| network-infra | Red | Routers, switches, DNS, proxy |
| media | Green | Media-related services (*arr stack, Emby, etc.) |

### Proxmox Containers & VMs (22 hosts)

| Host | Hostname | Management URL | Description |
|------|----------|----------------|-------------|
| AdGuard DNS | `adguard.home` | `http://adguard.home` | CT 101 — DNS server, DHCP |
| Bazarr | `bazarr.home` | `http://bazarr.home` | CT 115 — subtitle management |
| Claude AI | `claude.home` | `http://claude.home` | CT 124 — AI assistant |
| Emby | `emby.home` | `http://emby.home` | CT 102 — media server |
| Home Assistant | `homeassistant.home` | `http://homeassistant.home` | VM 100 — home automation |
| Homelable | `homelable.home` | `http://homelable.home` | CT 109 — network diagram |
| Homepage | `homepage.home` | `http://homepage.home` | CT 118 — dashboard |
| Jellyseerr | `jellyseerr.home` | `http://jellyseerr.home` | CT 113 — media requests |
| Komodo | `komodo.home` | `http://komodo.home` | CT 128 — Docker host (32 services) |
| Nginx Proxy Manager | `npm.home` | `http://npm.home` | CT 112 — reverse proxy |
| Ollama | `ollama.home` | `http://ollama.home` | CT 130 — LLM server + Open WebUI |
| Pulse | `pulse.home` | `http://pulse.home` | CT 120 — system pulse |
| Radarr | `radarr.home` | `http://radarr.home` | CT 107 — movie management |
| Samba Server | `192.168.0.176` | — | CT 104 — file shares (no web UI) |
| Sonarr | `sonarr.home` | `http://sonarr.home` | CT 110 — TV show management |
| Syncthing | `syncthing.home` | `http://syncthing.home` | CT 103 — file sync |
| Tracearr | `tracearr.home` | `http://tracearr.home` | CT 116 — media tracking |
| Unmanic | `unmanic.home` | `http://unmanic.home` | CT 105 — media transcoding |
| Uptime Kuma | `uptimekuma.home` | `http://uptimekuma.home` | CT 114 — monitoring |
| UrBackup | `urbackup.home` | `http://urbackup.home` | CT 111 — backup server |
| Wiki.js | `wikijs.home` | `http://wikijs.home` | CT 117 — wiki |
| Z-Wave JS | `zwave.home` | `http://zwave.home` | CT 108 — Z-Wave controller |

### Docker Services on Komodo (32 services)

All run on 192.168.0.179 and are managed via Komodo stacks:

| Service | Port | .home Domain |
|---------|------|-------------|
| Authentik | 9000 | `authentik.home` |
| BentoPDF | 8095 | `bentopdf.home` |
| BirdNET-Go | 8060 | `birds.home` |
| Blackbox Exporter | 9115 | — |
| Fragments | 8075 | `fragments.home` |
| Frigate | 5000 | — |
| Grafana | 3001 | `grafana.home` |
| Immich | 2283 | `immich.home` |
| Jellystat | 3000 | `jellystat.home` |
| Karakeep | 8055 | — |
| Komodo | 9120 | `komodo.home` |
| Manyfold | 3214 | `manyfold.home` |
| Mealie | 9925 | `mealie.home` |
| Notifiarr | 8120 | `notifiarr.home` |
| Paperless | 8010 | `paperless.home` |
| Paperless AI | 3030 | `paperless-ai.home` |
| Prometheus | 9092 | `prometheus.home` |
| Reyday | 8105 | `reyday.home` |
| Sander | 8100 | `sander.home` |
| Stirling PDF | 8070/8080 | — |
| Tandoor | 8090 | `tandoor.home` |
| Tdarr | 7828 | `tdarr.home` |
| Trailhead | 8076 | `weather.home` |

### Network Infrastructure (2 hosts + Shipyard)

| Host | IP | Description |
|------|-----|-------------|
| Router | 192.168.0.1 | Netgear Nighthawk gateway |
| Shipyard | 192.168.0.151 | Proxmox VE host (`https://proxmox.home`) |

### IoT Devices (28 hosts)

Cameras, sensors, smart home devices. Key ones with web UIs:

| Host | IP | Notes |
|------|-----|-------|
| Display Case WLED | 192.168.0.133 | `http://192.168.0.133` |
| Gazebo WLED | 192.168.0.83 | `http://192.168.0.83` |
| BirdNET Pi | 192.168.0.136 | Raspberry Pi — bird detection |
| Hue Hub | 192.168.0.40 | Philips Hue bridge |
| Ecowitt Gateway | 192.168.0.79 | Weather station |
| Driveway Camera | 192.168.0.113 | Security camera |

Others: Ecobee Thermostat (.15), Google Home Mini (.4), LG TV (.7), LIFX Bulbs 1-6 (.142-.147), Levoit Air Purifier (.203), Petkit Dog Feeder (.170), Printer (.14), Ring Chime 3D (.10), Roborock Vacuum (.71), Stove (.65), Wyze Cams (.52, .123, .124, .169), MS60 Satellites (.5, .6)

### Hidden Hosts (3)

| Host | Reason |
|------|--------|
| komodo-daemon | Daemon self-registration at 127.0.0.1 |
| Ecowitt Gateway (.77) | Duplicate — real device is at .79 |
| Scanopy | Daemon's bloated self-host with 72 Docker bridge interfaces |

## Groups

9 service relationship groups visualize how services connect:

| Group | Type | Color | Services |
|-------|------|-------|----------|
| Media Stack | HubAndSpoke | Purple | Emby → Radarr, Sonarr, Bazarr, Jellyseerr, Unmanic, Tracearr |
| Monitoring Stack | HubAndSpoke | Green | Grafana → Prometheus, Alertmanager, Blackbox Exporter, Uptime Kuma |
| Frigate / Cameras | HubAndSpoke | Red | Frigate → API, RTSP, Secondary, WebRTC, Driveway Cam, BirdNET-Go |
| Document Management | HubAndSpoke | Orange | Paperless → Paperless AI, Stirling PDF, BentoPDF |
| Photo & Media Storage | HubAndSpoke | Blue | Immich → SFTP, Syncthing |
| Auth & Proxy | RequestPath | Purple | Authentik → NPM → Homepage |
| Home Automation | HubAndSpoke | Green | Home Assistant → Z-Wave JS, Hue Hub, Ecobee, Ecowitt |
| Recipes | HubAndSpoke | Orange | Mealie → Tandoor |
| Network Infrastructure | RequestPath | Blue | Router → AdGuard DNS → NPM |

## API Reference

All endpoints require `Authorization: Bearer scp_u_SbQNNIfPqOvIKALLKop8zhiaMPEtrs0A`.

### Hosts

```bash
# List all hosts
curl -s "$API/hosts?limit=100" -H "Authorization: Bearer $TOKEN"

# Get single host (includes services, ports, interfaces)
curl -s "$API/hosts/{id}" -H "Authorization: Bearer $TOKEN"

# Update host (PUT — requires id, name, hidden, tags, credential_assignments)
curl -s -X PUT "$API/hosts/{id}" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"id":"...","name":"...","hidden":false,"tags":["tag-uuid"],"credential_assignments":[],"hostname":"...","description":"..."}'

# Note: management_url is NOT settable via API — use direct DB update
```

### Services

```bash
# Create service with port binding
curl -s -X POST "$API/services" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"...","service_definition":"...","host_id":"...","network_id":"639ba72b-...","bindings":[{"type":"Port","port_id":"...","network_id":"639ba72b-...","interface_id":"..."}]}'

# Delete service (frees port bindings)
curl -s -X DELETE "$API/services/{id}" -H "Authorization: Bearer $TOKEN"

# Note: Ports bound to one service cannot be re-bound without deleting the service first
```

### Tags

```bash
# Create tag
curl -s -X POST "$API/tags" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"...","color":"Blue","description":"...","organization_id":"7867ae84-a9fa-4add-bd27-fdb37907e12b"}'

# Colors: Blue, Purple, Orange, Red, Green (named strings, not hex)
# Tags are assigned via the host PUT endpoint (tags field = array of tag UUIDs)
```

### Groups

```bash
# Create group
curl -s -X POST "$API/groups" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"...","network_id":"639ba72b-...","description":"...","color":"Blue","group_type":"HubAndSpoke","bindings":[]}'

# group_type: "HubAndSpoke" or "RequestPath"
# Bindings must be added via direct DB insert into group_bindings table (API doesn't populate them)
```

### Direct DB Access

```bash
# Connect to Scanopy PostgreSQL
ssh claude@192.168.0.151 "sudo pct exec 121 -- docker exec -i scanopy-postgres-1 psql -U postgres -d scanopy"

# Key tables: hosts, services, bindings, ports, interfaces, tags, entity_tags, groups, group_bindings
```

## Adding a New Host

New hosts are discovered automatically by the daemon's network scan. To manually configure after discovery:

1. **Name it**: `PUT /hosts/{id}` with friendly name, hostname, description
2. **Tag it**: Include tag UUIDs in the PUT payload
3. **Name its services**: Delete "Unclaimed Open Ports", create named services with correct port bindings
4. **Set management_url**: Direct DB update (`UPDATE hosts SET management_url = '...' WHERE id = '...'`)
5. **Add to a group**: Insert into `group_bindings` table if it belongs to a service group
6. **Alphabetize**: `UPDATE services SET position = sub.rn - 1 FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY host_id ORDER BY name) as rn FROM services) sub WHERE services.id = sub.id`

## Troubleshooting

- **Daemon not discovering hosts**: Check daemon container is running with `--network host` on Komodo
- **Duplicate host entries**: Hide the duplicate via `PUT /hosts/{id}` with `hidden: true`
- **"Unclaimed Open Ports" service**: Daemon lumps unknown ports here — delete it and create named services
- **API 500 on hosts list**: Check `service_definition` column — bare strings (without JSON quotes) break deserialization. Fix: `UPDATE services SET service_definition = '"Name"' WHERE service_definition = 'Name'`
- **management_url not saving via API**: Known limitation — use direct DB update instead
- **Group bindings empty after creation**: API accepts `bindings` field but doesn't populate `group_bindings` table — insert directly via SQL

## Known Issues

- **Daemon self-host bloat**: The daemon running on Komodo registers itself as a host and accumulates all Docker bridge network interfaces (72+). This entry is hidden.
- **service_definition format**: Must be a JSON-quoted string in the database (e.g., `"Frigate"` not `Frigate`). The API handles this correctly for POST, but direct DB updates must include quotes.
- **Network ID**: All hosts share a single network `639ba72b-a20a-473e-ba62-c4e55bce9d80`. This is required for all service and group creation calls.
