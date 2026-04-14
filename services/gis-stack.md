# GIS Stack

**Last Updated**: 2026-04-14
**Container**: LXC 131 (gis-stack) — 192.168.0.229
**Managed By**: Komodo (192.168.0.179:9120)

## Summary

Self-hosted GIS platform running on LXC 131. Provides a PostGIS spatial database, vector tile server (Martin), cloud-optimized raster tile server (TiTiler), and Potree point cloud viewer — all proxied through Nginx on a single port. Includes a MapLibre GL JS web frontend for browsing layers. Designed to support photogrammetry workflows (point clouds, rasters, spatial data).

---

## Services

| Service | Image | Version | Access |
|---------|-------|---------|--------|
| **Web Map UI** | (static, served by Nginx) | — | `http://gis.home:8200/` |
| PostGIS | postgis/postgis | 17-3.5 | `gis.home:5432` (QGIS, psql) |
| Martin | ghcr.io/maplibre/martin | latest | `http://gis.home:8200/martin/` |
| TiTiler | ghcr.io/developmentseed/titiler | 0.26.0 | `http://gis.home:8200/titiler/` |
| Nginx | nginx:alpine | latest | `http://gis.home:8200/` |
| Komodo Periphery | ghcr.io/moghtech/komodo-periphery | latest | `https://192.168.0.229:8120` |

**DNS**: `gis.home → 192.168.0.229` configured in AdGuard (LXC 101)

**Health check**: `http://gis.home:8200/health` → returns `GIS stack OK`

---

## Web Map Frontend

**URL**: `http://gis.home:8200/`

MapLibre GL JS frontend served as a static file by Nginx. Source at `/opt/gis/nginx/www/index.html`.

**Features:**
- OSM basemap
- **Vector Layers panel** — auto-fetches Martin's catalog on load, lists all PostGIS tables. Toggle any layer on/off; geometry type (polygon/line/point) is detected automatically from TileJSON and rendered with the appropriate MapLibre layer type.
- **Raster Layers panel** — lists all `.tif` files from `/mnt/rasters/` via the `/files/rasters/` endpoint. Toggle on/off with per-layer opacity slider; map auto-zooms to raster bounds on first enable.
- Live coordinate display (mousemove)

To add a raster: drop a GeoTIFF into `/mnt/rasters/` on LXC 131 and refresh the page.

---

## Infrastructure

- **LXC**: 131
- **IP**: 192.168.0.229 (DHCP)
- **OS**: Ubuntu
- **CPU**: 4 cores
- **RAM**: 8GB
- **Disk**: 32GB (`littlestorage:vm-131-disk-0`)
- **AppArmor**: `unconfined` (required for Docker — set in `/etc/pve/lxc/131.conf`)
- **Features**: `nesting=1,keyctl=1`

---

## Compose Files

All config lives in `/opt/gis/` on LXC 131.

```
/opt/gis/
├── docker-compose.yml          # Main stack (PostGIS, Martin, TiTiler, Nginx)
├── docker-compose.pdal.yml     # Processing tools (GDAL, PDAL) — run on-demand
├── .env                        # Secrets
├── martin/
│   └── config.yaml             # Martin tile server config
└── nginx/
    ├── nginx.conf              # Reverse proxy + file listing config
    └── www/
        └── index.html          # MapLibre GL JS web map frontend
```

### Main Stack (`docker-compose.yml`)

Four services on a shared `gis_net` bridge network:

- **postgis**: 1GB shared_buffers, 8GB effective_cache_size, 50 max connections. Data persisted in `postgis_data` Docker volume.
- **martin**: Connects to PostGIS via `DATABASE_URL`. Auto-publishes all tables and functions as tile sources. Listens on internal port 3000.
- **titiler**: Serves Cloud Optimized GeoTIFFs from `/mnt/rasters`. CORS open (`*`). No port exposed directly — proxied via Nginx.
- **nginx**: Exposes port 8200. Serves frontend, routes `/martin/`, `/titiler/`, `/potree/`, `/files/rasters/`, and `/health`.

### Processing Stack (`docker-compose.pdal.yml`)

On-demand containers sharing the main `gis_gis_net` network:

- **gdal** (3.12.2): Access to `/mnt/rasters` and `/mnt/pointclouds`
- **pdal** (2.10.1): Access to `/mnt/pointclouds`, `/mnt/potree`, `/mnt/rasters`

Run with:
```bash
docker compose -f /opt/gis/docker-compose.pdal.yml run --rm pdal <command>
docker compose -f /opt/gis/docker-compose.pdal.yml run --rm gdal <command>
```

---

## Nginx Routing

| Path | Serves |
|------|--------|
| `/` | MapLibre web map frontend (`/var/www/html/index.html`) |
| `/martin/` | Martin tile server (`http://martin:3000/`) |
| `/titiler/` | TiTiler raster tile server (`http://titiler:80/`) |
| `/potree/` | Potree point cloud viewer (`/mnt/potree/` static files) |
| `/files/rasters/` | JSON directory listing of `/mnt/rasters/` (used by frontend) |
| `/health` | Returns `GIS stack OK` |

---

## Data Directories

| Path (on LXC 131) | Purpose |
|-------------------|---------|
| `/mnt/rasters` | GeoTIFF / COG raster files served by TiTiler and listed in web UI |
| `/mnt/potree` | Potree point cloud viewer output (served at `/potree/`) |
| `/mnt/docker` | Docker working data |

PostGIS data is stored in the `postgis_data` Docker named volume (not a host mount).

---

## Credentials

| Service | Detail |
|---------|--------|
| PostGIS | DB: `gis`, User: `gis`, Password: in `/opt/gis/.env` on LXC 131 |
| Komodo Periphery passkey | Shared with Komodo core — see periphery env on LXC 128 |

---

## Komodo Integration

Periphery agent runs as a Docker container on LXC 131 and is registered in Komodo as:

- **Address**: `https://192.168.0.229:8120`
- Periphery uses a self-signed SSL cert (auto-generated on first start)
- The passkey is shared with Komodo Core via environment variable — no manual entry needed in UI

To add the server in Komodo UI: **Servers → Add Server → address above → Enable**.

---

## Common Operations

### Open the map
`http://gis.home:8200/`

### Connect with QGIS
- Host: `gis.home` (or `192.168.0.229`)
- Port: `5432`
- Database: `gis`
- User: `gis`
- Password: from `/opt/gis/.env`

### Add a raster to the web UI
```bash
# Copy a GeoTIFF into the rasters mount on LXC 131
scp myfile.tif root@192.168.0.229:/mnt/rasters/
# Refresh http://gis.home:8200/ — file appears in Raster Layers panel
```

### Restart stack
```bash
ssh claude@192.168.0.151 'sudo pct exec 131 -- docker compose -f /opt/gis/docker-compose.yml restart'
```

### Check logs
```bash
ssh claude@192.168.0.151 'sudo pct exec 131 -- docker logs gis-martin'
ssh claude@192.168.0.151 'sudo pct exec 131 -- docker logs gis-postgis'
ssh claude@192.168.0.151 'sudo pct exec 131 -- docker logs gis-nginx'
```

### Run PDAL pipeline
```bash
ssh claude@192.168.0.151 'sudo pct exec 131 -- docker compose -f /opt/gis/docker-compose.pdal.yml run --rm pdal pipeline /data/pointclouds/pipeline.json'
```

---

## Troubleshooting

**Martin stuck restarting after container reboot**
- Cause: PostGIS hasn't finished its health check yet
- Fix: Wait ~30s — Martin depends on `service_healthy` from PostGIS and will come up automatically

**Docker containers won't start (AppArmor error)**
- Cause: `lxc.apparmor.profile: unconfined` missing from LXC config
- Fix: `echo "lxc.apparmor.profile: unconfined" >> /etc/pve/lxc/131.conf` then reboot LXC

**Komodo shows server "not ok"**
- Cause: Address entered as `http://` instead of `https://`
- Fix: Use `https://192.168.0.229:8120` — periphery runs with self-signed SSL by default

**Raster layers panel shows empty**
- Cause: No `.tif` files in `/mnt/rasters/` on LXC 131
- Fix: Copy GeoTIFFs into `/mnt/rasters/` and refresh the page
