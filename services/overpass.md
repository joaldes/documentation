# Overpass-NA — Self-Hosted OSM Query API

**Last Updated**: 2026-05-04
**Related Systems**: CT 128 (Komodo, 192.168.0.179), CT 124 (tPlan, future consumer), CT 101 (AdGuard DNS)

---

## Quick Reference

| Item | Value |
|------|-------|
| **Host** | CT 128 (Komodo, 192.168.0.179) |
| **Port** | 12345 (Caddy CORS sidecar; overpass internal :80 only) |
| **DNS** | `overpass.home → 192.168.0.179` (AdGuard rewrite) |
| **Direct URL** | `http://192.168.0.179:12345` (use this in code; not all browsers resolve `.home`) |
| **Containers** | `overpass` (`wiktorn/overpass-api:v0.7.62.9`), `overpass-caddy` (`caddy:2-alpine`) |
| **Compose** | `/mnt/docker/overpass/compose.yaml` |
| **Data dir** | `/mnt/docker/overpass/db` (~50–60 GB after import) |
| **Caddyfile** | `/mnt/docker/overpass/caddy/Caddyfile` (CORS reverse-proxy) |
| **Source PBF** | `https://download.geofabrik.de/north-america-latest.osm.pbf` (~17.6 GB) |
| **Diff URL** | `https://download.geofabrik.de/north-america-updates/` (hourly polled, daily-published) |

---

## What it does

Overpass-API queries the raw OSM database. Returns every tagged feature in a bounding box — restaurants, shops, gas stations, trailheads, viewpoints, hotels, monuments, etc. Far denser than rendered tile labels because the query touches the data directly, not a pre-styled tile.

In tplan: drives the (planned) clickable POI overlay. User pans/zooms → tplan queries `/api/interpreter` for `amenity=*`, `shop=*`, `tourism=*`, `leisure=*` in the viewport → renders POI markers → click "Add as stop".

---

## Compose file

`/mnt/docker/overpass/compose.yaml`:

```yaml
name: overpass

services:
  overpass:
    image: wiktorn/overpass-api:v0.7.62.9
    container_name: overpass
    restart: unless-stopped
    expose:
      - "80"
    volumes:
      - /mnt/docker/overpass/db:/db
    environment:
      TZ: America/Phoenix
      OVERPASS_MODE: init
      OVERPASS_PLANET_URL: https://download.geofabrik.de/north-america-latest.osm.pbf
      OVERPASS_DIFF_URL: https://download.geofabrik.de/north-america-updates/
      OVERPASS_UPDATE_SLEEP: "3600"
      OVERPASS_META: "no"
      OVERPASS_RULES_LOAD: "50"
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: "2.0"
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- 'http://localhost/api/interpreter?data=[out:json];node(1);out;' >/dev/null || exit 1"]
      interval: 60s
      timeout: 15s
      retries: 3
      start_period: 28800s
    networks:
      - overpass-net

  caddy:
    image: caddy:2-alpine
    container_name: overpass-caddy
    restart: unless-stopped
    ports:
      - "12345:80"
    depends_on:
      - overpass
    volumes:
      - /mnt/docker/overpass/caddy/Caddyfile:/etc/caddy/Caddyfile:ro
    networks:
      - overpass-net

networks:
  overpass-net:
```

`Caddyfile`:

```
:80 {
    encode gzip
    @options method OPTIONS
    handle @options {
        header Access-Control-Allow-Origin "*"
        header Access-Control-Allow-Methods "GET, POST, OPTIONS"
        header Access-Control-Allow-Headers "Content-Type"
        respond 204
    }
    handle {
        header Access-Control-Allow-Origin "*"
        reverse_proxy overpass:80
    }
}
```

The Caddy sidecar adds `Access-Control-Allow-Origin: *` so browsers can call the API directly. `wiktorn/overpass-api` does not ship CORS headers (unlike Photon's `-cors-any` flag).

---

## Sample queries

**Restaurants in Jackson Hole, WY:**
```bash
curl 'http://192.168.0.179:12345/api/interpreter?data=[out:json];node["amenity"="restaurant"](43.40,-110.85,43.65,-110.65);out;'
```

**Mixed POIs — eat / fuel / lodging in a bbox:**
```
[out:json][timeout:25];
(
  node["amenity"~"^(restaurant|cafe|bar|fast_food|fuel|biergarten)$"](43.4,-110.85,43.65,-110.65);
  node["tourism"~"^(hotel|motel|guest_house|hostel|viewpoint|attraction)$"](43.4,-110.85,43.65,-110.65);
  node["shop"](43.4,-110.85,43.65,-110.65);
);
out body;
```

CORS preflight check:
```bash
curl -i -X OPTIONS -H "Origin: http://example.com" http://192.168.0.179:12345/api/interpreter
# → 204 + Access-Control-Allow-Origin: *
```

---

## Operations

**Container status:**
```bash
ssh root@192.168.0.179 'docker ps --filter name=overpass --format "{{.Names}} {{.Status}}"'
```

**Live logs (import progress):**
```bash
ssh root@192.168.0.179 'docker logs -f overpass'
```

**Restart:**
```bash
ssh root@192.168.0.179 'cd /mnt/docker/overpass && docker compose restart'
```

**Force re-index from scratch (rare — destroys ~50 GB of indexed data):**
```bash
ssh root@192.168.0.179 'cd /mnt/docker/overpass && docker compose down && rm -rf /mnt/docker/overpass/db/* && docker compose up -d'
```

---

## Initial bring-up (2026-05-04)

> **Track progress on jobs.home**: PBF→bz2-XML preprocess + index build is multi-hour. Track index dir growth via `jobctl track-file overpass-index /mnt/docker/overpass/db/db --total 32212254720 --interval 60 &`. Live progress at `http://jobs.home:8077`.

1. Compose + data colocated at `/mnt/docker/overpass/` (compose.yaml, db/, caddy/) — durable layout that survives CT 128 rebuilds. See `feedback_komodo_stacks.md` for the periphery `/mnt/docker` bind mount that makes this Komodo-manageable.
2. Pulled images (`wiktorn/overpass-api:v0.7.62.9`, `caddy:2-alpine`).
3. `docker compose up -d` — stack came up; Overpass began downloading the NA PBF (~17.6 GB) and indexing.
4. Registered in Komodo via `CreateStack` API on Local server (`server_id 696a12253d02f3852224737f`, files_on_host=true, run_directory=`/mnt/docker/overpass`, auto_pull=false).
5. AdGuard rewrite added (`overpass.home → 192.168.0.179`).
6. Trailhead bookmark added (Infrastructure group, "Geo Data" category) — generator image rebuilt to bake new `trailhead.yaml`.

Initial import expected to take 4–8 hours. Healthcheck `start_period: 28800s` (8 h) tolerates this.

---

## Troubleshooting

**Container restarting / healthcheck fails after 8+ h:**
- Check `docker logs overpass` for the import status. If still importing, increase `start_period`. If errored, check for OOM (Memory limit is 8 GB; spikes during init can exceed). Comment out `deploy.resources.limits`, restart, and let it complete unbounded.

**CORS error from browser:**
- Caddy might be down. `docker ps --filter name=overpass-caddy`. Restart if needed.
- If your browser hits Overpass directly on `:80` instead of `:12345`, update the URL — port 80 is internal only.

**Stale data:**
- `OVERPASS_DIFF_URL` polled every `OVERPASS_UPDATE_SLEEP` seconds (3600 = 1 h). Geofabrik publishes diffs daily, so most polls are no-ops. Logs show `applied diff sequence ...` on successful update.

**Komodo shows stack as "down" but containers are running:**
- Komodo only shows a stack as "deployed by it" if Komodo did the deploy. After import finishes, redeploy via Komodo UI to adopt management.
