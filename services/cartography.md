# Cartography (LXC 131)

**Last Updated**: 2026-05-07
**Container**: LXC 131 (`cartography`) — 192.168.0.229
**Managed By**: Komodo (source of truth) — Server entry `cartography` (id `69ddced4735ae27880b55726`), four stacks: `map`, `gis`, `proxy`, `gis-tools`. Periphery on `https://192.168.0.229:8120`. Compose files at `/mnt/docker/<name>/compose.yaml` are read by Komodo on each deploy (`files_on_host: true`).

## Summary

Cartography hosts two unrelated workloads on one LXC, separated into three Docker compose stacks on a shared external network:

- **`map`** stack — backs the tplan road-trip planner (Photon search, Overpass POIs, Valhalla routing)
- **`gis`** stack — photogrammetry / drone GIS workstation (PostGIS, Martin vector tiles, TiTiler raster tiles)
- **`proxy`** stack — single-IP front door (`proxy-nginx`) that fronts the gis stack and serves static assets

The split makes the host self-documenting: anyone landing on cartography can see at a glance from `/mnt/docker/{map,gis,proxy}/` and `docker ps` which workload owns which container and which data dir.

History: the LXC was previously named `gis-stack` with a single mixed compose. Reorganized 2026-05-07 — see `mapping-stack-audit-2026-05-07.md` for the decision log.

---

## Stack overview

All containers run on the external Docker network `cartography_net` (created with `docker network create cartography_net`).

### `map` stack (`/mnt/docker/map/compose.yaml`, project name `map`)

| Container | Image | Public port | Data |
|---|---|---|---|
| `map-photon` | rtuszik/photon-docker:latest | `2322` | `/mnt/docker/map/photon/data` (~88 GB Lucene index) |
| `map-overpass` | wiktorn/overpass-api:v0.7.62.9 | (internal `80`) | `/mnt/docker/map/overpass/db` (~35 GB) |
| `map-overpass-caddy` | caddy:2-alpine | `12345` (CORS reverse-proxy in front of overpass) | `/mnt/docker/map/overpass/caddy/Caddyfile` |
| `map-valhalla` | ghcr.io/nilsnolde/docker-valhalla/valhalla:latest | `8002` | `/mnt/docker/map/valhalla` (~19 GB tar + tiles; **full USA incl. AK/HI**, live 2026-06-11) |

Used by tplan (CT 128). DNS hostname: `gis.home` (legacy from pre-rename) covers all of these.

### `gis` stack (`/mnt/docker/gis/compose.yaml`, project name `gis` — pinned)

| Container | Image | Internal port | Data |
|---|---|---|---|
| `gis-postgis` | postgis/postgis:17-3.5 | `5432` (exposed for QGIS) | named volume `gis_postgis_data` (`/var/lib/docker/volumes/gis_postgis_data/_data`) |
| `gis-martin` | ghcr.io/maplibre/martin:latest | `3000` (proxied) | `/mnt/docker/gis/martin/config.yaml` (read-only) |
| `gis-titiler` | ghcr.io/developmentseed/titiler:0.26.0 | `80` (proxied) | `/mnt/docker/gis/rasters` (read-only) |

> **Project name pinned** to `gis` so the named volume `gis_postgis_data` stays bound across compose restarts. Don't change `name: gis` in `compose.yaml`.

PostGIS extensions active: `postgis 3.5.2`, `postgis_raster`, `postgis_topology`, `postgis_tiger_geocoder`. Password in `/mnt/docker/gis/.env`.

### `proxy` stack (`/mnt/docker/proxy/compose.yaml`, project name `proxy`)

| Container | Image | Public port |
|---|---|---|
| `proxy-nginx` | nginx:alpine | `8200` |

Single shared front door. Reverse-proxies the gis stack and serves static assets:

| URL path | Backed by |
|---|---|
| `/` | `/mnt/docker/proxy/nginx/www/index.html` (MapLibre GL JS web map) |
| `/martin/` | `proxy_pass http://gis-martin:3000/` (lazy-resolved via Docker DNS) |
| `/titiler/` | `proxy_pass http://gis-titiler:80/` (lazy-resolved) |
| `/potree/` | static alias for `/mnt/docker/gis/potree/` |
| `/files/rasters/` | JSON directory listing of `/mnt/docker/gis/rasters/` |
| `/tiles/` | static alias for `/mnt/docker/map/tiles/` (PMTiles vector basemap) |
| `/health` | returns `GIS stack OK` |

Uses `resolver 127.0.0.11 valid=10s ipv6=off` + variable-form `proxy_pass` so upstreams are resolved lazily — survives upstream restarts and doesn't crash at startup if an upstream is briefly down.

### `gis-tools` stack (on-demand, `/mnt/docker/gis-tools/compose.yaml`)

Not auto-started. Containers for ad-hoc data processing:

- `gis-gdal` (gdal:alpine-small-3.12.2): bind-mounts `/mnt/docker/gis/rasters` and `/mnt/docker/gis/pointclouds`
- `gis-pdal` (pdal/pdal:latest): bind-mounts `/mnt/docker/gis/{pointclouds,potree,rasters}`

Run with:
```sh
docker compose -f /mnt/docker/gis-tools/compose.yaml run --rm gdal <command>
docker compose -f /mnt/docker/gis-tools/compose.yaml run --rm pdal <command>
```

---

## Disk layout

```
/mnt/docker/                        # mp5 passthrough from host (only LXC mountpoint)
├── map/                            (~135 GB — tplan stack)
│   ├── compose.yaml
│   ├── photon/data/                (88 GB Lucene index, UID 9011)
│   ├── overpass/db/                (35 GB Overpass DB)
│   ├── overpass/caddy/Caddyfile
│   ├── valhalla/                   (full-USA: 19 GB tar + 19 GB tiles + 12 GB us-latest.osm.pbf rebuild source; valhalla-old/ = pre-swap US-West rollback)
│   └── tiles/                      (~8 GB PMTiles vector basemap)
├── gis/                            (~16 GB — photogrammetry)
│   ├── compose.yaml
│   ├── .env                        (POSTGRES_PASSWORD)
│   ├── martin/config.yaml
│   ├── pointclouds/                (drone-scan raw inputs)
│   ├── potree/                     (Potree viewer tiled output)
│   ├── rasters/                    (DEMs, orthos, USGS LPC lidar — 13 GB)
│   └── projects/                   (workflow scratch)
├── proxy/                          (~40 KB)
│   ├── compose.yaml
│   └── nginx/{nginx.conf,www/}
└── gis-tools/compose.yaml          (on-demand processing)
```

> **Historical note**: prior to 2026-05-07 the LXC config had four bind-mount aliases (`mp0–mp3`) presenting `/mnt/docker/gis/{pointclouds,rasters,potree,valhalla}` at convenience paths `/mnt/{pointclouds,rasters,potree,valhalla}` inside the container. Those aliases have been removed. Always use the canonical `/mnt/docker/gis/...` and `/mnt/docker/map/...` paths.

---

## Networking

```
[ tplan (CT 128) ]                          [ QGIS Desktop ]
        │                                          │
        ▼                                          ▼
 gis.home:2322  → map-photon                gis.home:5432 → gis-postgis
 gis.home:12345 → map-overpass-caddy → map-overpass
 gis.home:8002  → map-valhalla
 gis.home:8200  → proxy-nginx ─┬─ /martin/  → gis-martin
                               ├─ /titiler/ → gis-titiler
                               ├─ /potree/  → /mnt/docker/gis/potree (file)
                               ├─ /files/rasters/ → /mnt/docker/gis/rasters (dir listing)
                               ├─ /tiles/   → /mnt/docker/map/tiles (PMTiles)
                               └─ /health
```

DNS rewrites (AdGuard on CT 101): `gis.home`, `cartography.home`, `photon.home`, `overpass.home` → `192.168.0.229`.

`depends_on` does NOT cross stack boundaries. Cold-start order if everything's down: `gis` → `map` → `proxy` (nginx tolerates briefly missing upstreams thanks to lazy DNS resolver).

---

## LXC config

- **ID**: 131 (locked)
- **Hostname**: `cartography`
- **IP**: 192.168.0.229 (DHCP)
- **CPU/RAM**: 4 cores / 24 GB
- **Disk**: 32 GB rootfs (`littlestorage:vm-131-disk-0`) + `/mnt/docker` passthrough
- **AppArmor**: `unconfined` (required for nested Docker; set in `/etc/pve/lxc/131.conf`)
- **Features**: `nesting=1,keyctl=1`
- **Mountpoints**: only `mp5: /mnt/docker,mp=/mnt/docker` remains (mp0–mp3 dropped)

---

## Common operations

### Open the GIS web map
`http://gis.home:8200/`

### Connect QGIS to PostGIS
- Host: `gis.home` · Port: `5432` · Database: `gis` · User: `gis` · Password: `/mnt/docker/gis/.env`

### Add a raster to the web UI
```sh
scp myfile.tif root@192.168.0.229:/mnt/docker/gis/rasters/
# refresh http://gis.home:8200/ — file appears in Raster Layers panel
```

### Restart a stack
```sh
ssh claude@192.168.0.151 'sudo pct exec 131 -- bash -c "cd /mnt/docker/gis && docker compose restart"'
ssh claude@192.168.0.151 'sudo pct exec 131 -- bash -c "cd /mnt/docker/map && docker compose restart photon"'
```

### Check logs
```sh
ssh claude@192.168.0.151 'sudo pct exec 131 -- docker logs proxy-nginx'
ssh claude@192.168.0.151 'sudo pct exec 131 -- docker logs gis-martin'
ssh claude@192.168.0.151 'sudo pct exec 131 -- docker logs map-photon'
```

### Run a PDAL pipeline
```sh
ssh claude@192.168.0.151 'sudo pct exec 131 -- docker compose -f /mnt/docker/gis-tools/compose.yaml run --rm pdal pipeline /data/pointclouds/pipeline.json'
```

---

## Troubleshooting

**Photon stuck "health: starting" for 10+ minutes after restart**
- Cause: rtuszik/photon-docker entrypoint runs `chown -R photon:photon /photon` on every start. Overlayfs copy-up makes this pathologically slow on the 88 GB index even though files are already UID 9011.
- Fix: `docker exec map-photon kill -9 11` (chown PID is always 11 — the entrypoint forks it as the second process). process_manager continues immediately and Photon comes online in <60 sec. Data ownership stays correct.

**Martin stuck restarting after container reboot**
- Cause: PostGIS hasn't finished its health check yet
- Fix: Wait ~30 s — Martin uses `condition: service_healthy` and will come up automatically

**proxy-nginx returns 502 on `/martin/` or `/titiler/`**
- Cause: gis stack is down, or `gis-martin`/`gis-titiler` container_name doesn't match what nginx.conf references
- Check: `docker ps --filter name=gis-` and `docker network inspect cartography_net` to confirm both proxy + gis are on the same network

**Docker containers won't start (AppArmor error)**
- Cause: `lxc.apparmor.profile: unconfined` missing from `/etc/pve/lxc/131.conf`
- Fix: add line, then reboot LXC

**Komodo shows server "not ok"**
- Cause: Address entered as `http://` instead of `https://` (periphery uses self-signed SSL)
- Fix: Use `https://192.168.0.229:8120`

**Raster Layers panel shows empty**
- Cause: No `.tif` files in `/mnt/docker/gis/rasters/`
- Fix: Copy GeoTIFFs in and refresh

**`docker compose down` on `gis` says "network gis_gis_net resource still in use"**
- Cause: legacy from when `gis_net` was an in-stack network; should be gone since 2026-05-07 reorg
- If it reappears: `docker network rm gis_gis_net` (verify nothing references it first)
