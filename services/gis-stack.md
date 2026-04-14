# GIS Stack

**Last Updated**: 2026-04-13
**Container**: LXC 131 (gis-stack) — 192.168.0.229
**Managed By**: Komodo (192.168.0.179:9120)

## Summary

Self-hosted GIS platform running on LXC 131. Provides a PostGIS spatial database, vector tile server (Martin), cloud-optimized raster tile server (TiTiler), and Potree point cloud viewer — all proxied through Nginx on a single port. Designed to support photogrammetry workflows (point clouds, rasters, spatial data).

---

## Services

| Service | Image | Version | Access |
|---------|-------|---------|--------|
| PostGIS | postgis/postgis | 17-3.5 | `gis.home:5432` (QGIS, psql) |
| Martin | ghcr.io/maplibre/martin | latest | `http://gis.home:8200/martin/` |
| TiTiler | ghcr.io/developmentseed/titiler | 0.26.0 | `http://gis.home:8200/titiler/` |
| Nginx | nginx:alpine | latest | `http://gis.home:8200/` |
| Komodo Periphery | ghcr.io/moghtech/komodo-periphery | latest | `https://192.168.0.229:8120` |

**DNS**: `gis.home → 192.168.0.229` configured in AdGuard (LXC 101)

**Health check**: `http://gis.home:8200/health` → returns `GIS stack OK`

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
    └── nginx.conf              # Reverse proxy config
```

### Main Stack (`docker-compose.yml`)

Four services on a shared `gis_net` bridge network:

- **postgis**: 1GB shared_buffers, 8GB effective_cache_size, 50 max connections. Data persisted in `postgis_data` Docker volume.
- **martin**: Connects to PostGIS via `DATABASE_URL`. Auto-publishes all tables and functions as tile sources. Listens on internal port 3000.
- **titiler**: Serves Cloud Optimized GeoTIFFs from `/mnt/rasters`. CORS open (`*`). No port exposed directly — proxied via Nginx.
- **nginx**: Exposes port 8200. Routes `/martin/`, `/titiler/`, `/potree/`, and `/health`.

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

## Data Directories

| Path (on LXC 131) | Purpose |
|-------------------|---------|
| `/mnt/rasters` | GeoTIFF / COG raster files served by TiTiler |
| `/mnt/potree` | Potree point cloud viewer output (served by Nginx at `/potree/`) |
| `/mnt/docker` | Docker working data |

PostGIS data is stored in the `postgis_data` Docker named volume (not a host mount).

---

## Credentials

| Service | Detail |
|---------|--------|
| PostGIS | DB: `gis`, User: `gis`, Password: in `/opt/gis/.env` on LXC 131 |
| Komodo Periphery passkey | Shared with Komodo core — see periphery env on LXC 128 |

---

## Nginx Routing

| Path | Proxies To |
|------|-----------|
| `/martin/` | `http://martin:3000/` |
| `/titiler/` | `http://titiler:80/` |
| `/potree/` | `/mnt/potree/` (static files) |
| `/health` | Returns `GIS stack OK` |

---

## Komodo Integration

Periphery agent runs as a Docker container on LXC 131 and is registered in Komodo as:

- **Address**: `https://192.168.0.229:8120`
- Periphery uses a self-signed SSL cert (auto-generated on first start)
- The passkey is shared with Komodo Core via environment variable — no manual entry needed in UI

To add the server in Komodo UI: **Servers → Add Server → address above → Enable**.

---

## Common Operations

### Connect with QGIS
- Host: `gis.home` (or `192.168.0.229`)
- Port: `5432`
- Database: `gis`
- User: `gis`
- Password: from `/opt/gis/.env`

### Restart stack
```bash
ssh claude@192.168.0.151 'sudo pct exec 131 -- docker compose -f /opt/gis/docker-compose.yml restart'
```

### Check logs
```bash
ssh claude@192.168.0.151 'sudo pct exec 131 -- docker logs gis-martin'
ssh claude@192.168.0.151 'sudo pct exec 131 -- docker logs gis-postgis'
```

### Load a raster for TiTiler
Drop a COG `.tif` into `/mnt/rasters/` — TiTiler serves it immediately at:
```
http://gis.home:8200/titiler/cog/info?url=/data/rasters/yourfile.tif
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
