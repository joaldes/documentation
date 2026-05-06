# Photon — Self-Hosted Geocoder

**Last Updated**: 2026-05-04
**Related Systems**: CT 128 (Komodo, 192.168.0.179), CT 124 (tPlan, consumes), CT 101 (AdGuard DNS)

---

## Quick Reference

| Item | Value |
|------|-------|
| **Host** | CT 128 (Komodo, 192.168.0.179) |
| **Port** | 2322 |
| **DNS** | `photon.home → 192.168.0.179` (AdGuard rewrite) |
| **Direct URL** | `http://192.168.0.179:2322` (use this in code; not all browsers resolve `.home`) |
| **Container** | `photon` (Docker, image `rtuszik/photon-docker:latest`) |
| **Compose** | `/mnt/docker/photon/compose.yaml` |
| **Data dir** | `/mnt/docker/photon/data` (~92 GB extracted index) |
| **Index** | Komoot planet build (~57 GB compressed → ~92 GB extracted), monthly auto-refresh |
| **Source mirror** | `https://r2.koalasec.org/public/photon-db-planet-1.0-latest.tar.bz2` |

---

## What it does

Photon is an OSM-backed geocoder. It supports:
- **Forward search**: `/api?q=<text>&limit=N&bbox=...&lat=&lon=` → JSON GeoJSON
- **Reverse geocode**: `/reverse?lat=&lon=&limit=1` → nearest named feature
- **OSM tag filtering** (POI bias): `&osm_tag=tourism:attraction&osm_tag=highway:trailhead&...`

LAN-fast: queries return in ~20–50 ms vs ~300–800 ms for komoot.io public Photon. No rate limits.

---

## Compose file

> **Track progress on jobs.home**: initial 92 GB index extract takes ~1 hr. Wrap with `jobctl track-file photon-extract /mnt/docker/photon/data --total 100000000000 --interval 60 &`. Live at `http://jobs.home:8077`.

`/mnt/docker/photon/compose.yaml`:

```yaml
name: photon

services:
  photon:
    image: rtuszik/photon-docker:latest
    container_name: photon
    restart: unless-stopped
    ports:
      - "2322:2322"
    volumes:
      - /mnt/docker/photon/data:/photon/data
    environment:
      TZ: America/Phoenix
      UPDATE_STRATEGY: PARALLEL
      PHOTON_PARAMS: "-cors-any"
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: "2.0"
    healthcheck:
      test: ["CMD-SHELL", "wget --no-verbose --tries=1 -O /dev/null http://localhost:2322/api?q=test || exit 1"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 3600s
    networks:
      - photon-net

networks:
  photon-net:
```

**Critical settings:**
- `UPDATE_STRATEGY: PARALLEL` — keeps the container responsive during monthly index refreshes (builds new index alongside live one).
- `PHOTON_PARAMS: "-cors-any"` — makes Photon emit `Access-Control-Allow-Origin: *` so browsers can fetch directly from the planner SPA.
- Volume mount is at `/photon/data` (NOT `/photon/photon_data` — the image expects `DATA_DIR=/photon/data` and creates the `photon_data/` and `temp/` subdirectories itself).
- `start_period: 3600s` because the first boot downloads ~57 GB and extracts to ~92 GB.

---

## Deployment notes

### Disk requirements
- **Download**: 57 GB (`.tar.bz2`)
- **Temp during extract**: ~150 GB peak
- **Final index**: ~92 GB

CT 128's root LXC volume is only ~70 GB, so the data must live on `/mnt/docker` (a 1.8 TB ext4 partition mounted at `/dev/sde3`). The compose file's volume mount handles this. Initial setup mistake: mounting at `/photon/photon_data` instead of `/photon/data` — the image then used the LXC root for temp space and fail with "Insufficient temp space".

### Permissions
The image's process runs as **uid 9011** (`photon`) inside the container. The host data dir must be owned/traversable by that uid:

```bash
ssh root@192.168.0.179 'chown -R 9011:9011 /mnt/docker/photon'
```

If perms are wrong, the disk-space check sees the wrong filesystem and fails with `Insufficient temp space: need 149.10 GB, have 69.21 GB`.

### CORS
Browsers block cross-origin without `Access-Control-Allow-Origin`. The `-cors-any` Photon flag (passed via `PHOTON_PARAMS`) emits `*` for all origins. Verify:

```bash
curl -sI -H "Origin: http://example" "http://192.168.0.179:2322/api?q=test" | grep -i access-control
# Access-Control-Allow-Origin: *
```

---

## DNS

`/opt/AdGuardHome/AdGuardHome.yaml` on CT 101 (AdGuard) has a rewrite:

```yaml
rewrites:
  ...
  - domain: photon.home
    answer: 192.168.0.179
```

Restart AdGuard after edits: `sudo pct exec 101 -- systemctl restart AdGuardHome`.

**Important**: the planner SPA uses the **direct IP** (`192.168.0.179:2322`) in code, not the hostname. Reason: not every device on the LAN points its DNS at AdGuard, so `.home` resolution can fail in the browser. The IP works for everyone.

---

## Consumers (in tPlan)

- **Search bar** in the planner — `mockup-dev.html` `searchPhoton()` → `/api?q=&bbox=&lat=&lon=&osm_tag=...` for POI-biased search (trailheads, NPS sites, peaks, viewpoints, hot springs, etc.)
- **Live-drag add-stop popup** — drags the popup tip across the map; debounced `/reverse` call updates the name input
- **Auto-name new stops** — `reverseFillName(stop)` fires when a stop is created without a user-entered name, fills with nearest named feature
- **"Regen name" button** in Edit Location mode — force-overwrites name from current pin coords
- **Trip importer (`vendor/tplan/import.js`)** — currently still uses public Nominatim with 1.1s throttle. **TODO**: switch to Photon for ~100× speedup.

---

## Operations

### Check status
```bash
ssh root@192.168.0.179 'docker ps --filter name=photon --format "{{.Status}}"; docker logs photon --tail 5'
curl -s "http://192.168.0.179:2322/api?q=fossil+butte&limit=1" | head -c 300
```

### Restart
```bash
ssh root@192.168.0.179 'cd /mnt/docker/photon && docker compose restart photon'
```

### Force a re-pull of the index (rare; auto-updates monthly)
Set `FORCE_UPDATE=True` in the compose env, restart, then unset. Or delete `/mnt/docker/photon/data/photon_data/` and restart — the container will re-download.

### Disk check
```bash
ssh root@192.168.0.179 'du -sh /mnt/docker/photon/data; df -h /mnt/docker'
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Insufficient temp space` on first boot | Image extracts to LXC root (70 GB) instead of `/mnt/docker` | Confirm volume mount is `/mnt/docker/photon/data:/photon/data` (NOT `/photon/photon_data`) |
| Permission denied during setup | Host data dir not owned by uid 9011 | `chown -R 9011:9011 /mnt/docker/photon` |
| Browser CORS error fetching `/api` | `-cors-any` flag not passed to Photon | Add `PHOTON_PARAMS: "-cors-any"` to compose env, recreate container |
| `ERR_NAME_NOT_RESOLVED` for `photon.home` | Browser DNS not pointed at AdGuard | Use IP `192.168.0.179:2322` in code; AdGuard rewrite is convenience-only |
| 404 on `/api?q=...` after months | Index update failed silently | `docker logs photon` for the parallel-update task; check for download errors |
| Health check failing | JVM warm-up window or index rebuild in progress | First boot: wait up to 1 hour. Subsequent: usually transient — `docker restart photon` |

---

## What it's NOT

- **Not a routing engine** — that's Valhalla (`gis.home:8002`)
- **Not a tile server** — basemap tiles still come from Stadia/Esri/OSM (TODO: self-host TileServer-GL)
- **Not a place-info source** — Photon's index is stripped to indexable fields (name, address, type). For phone/website/hours we'd need Overpass; not currently deployed.
