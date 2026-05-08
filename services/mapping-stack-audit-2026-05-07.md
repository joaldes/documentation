# tPlan Mapping Stack Audit — 2026-05-07

**Status**: Audit complete; swaps in execution
**Reviewers**: 3 parallel multi-agent passes (component fitness / integration seams / flexibility & scaling)
**Plan file**: `/home/claudeai/.claude/plans/i-was-concerned-about-gleaming-iverson.md`

---

## Why this audit
After spending an hour fighting Protomaps custom paint_rules to get an OSM-Carto look, asked: "is the whole stack actually fit-for-purpose, or are there other components similarly mismatched?" Three agents in parallel reviewed component fitness, integration seams, and future flexibility.

## Pre-audit state (LXC 131 / 192.168.0.229)
| Service | Status | Coverage | Used by tplan? |
|---|---|---|---|
| Photon (`:2322`)               | ✅ healthy   | planet            | yes — name search, reverse-geocode, smart-search |
| Overpass (`:12345` via Caddy)  | ✅ healthy   | USA-wide (rebuilt today) | yes — POI chip strip, smart-search |
| Valhalla (`:8002`)             | ❌ unhealthy | **US-West only**  | yes — route polylines, drive-time |
| Protomaps PMTiles (`:8200/tiles`) | ✅ deployed today | USA continental | yes — newest base layer (custom theming hard) |
| Martin / TiTiler / PostGIS     | ✅ running   | n/a (empty)       | **no** — vestigial / future infra |

---

## Findings

### 🔴 Tier 1 — must-fix to deliver quality + flexibility

**1. Tile server is the wrong tool for the styling we want.**
- Protomaps PMTiles + protomaps-leaflet has NO built-in OSM-Carto theme. Custom `paint_rules` requires reading their schema and hand-coding (we tried; it didn't render due to wrong field assumptions).
- **TileServer-GL + OpenMapTiles** ships **OSM Bright** out of box — that IS OSM Carto in vector form. Plus Klokantech Basic, Fiord Color, Dark Matter, OSM Liberty. Five themes, zero custom code.
- Decision: **swap to TileServer-GL**.

**2. Valhalla is broken outside US-West.**
- Tucson → NYC fails silently in tplan: distance & driveTime cells stay null, no polyline, console-only error.
- Three options evaluated:
  - Rebuild Valhalla USA-wide (4-6 hr build, 20 GB tiles, no code change)
  - Swap to OSRM (~2-3 hr build, 5-8 GB graph, ~2 hr code rewrite, 3-4× lighter on RAM)
  - Use OpenRouteService.org API (rate-limited, internet-dependent)
- Decision: **OSRM** — 3× lighter on every operational axis, half the build time, plus a free **Trip endpoint** for future "auto-reorder day's stops" feature. Tradeoffs accepted: no truck profiles, no isochrones, no time-of-day costing (tplan doesn't use any of those).

**3. Hardcoded `192.168.0.229` everywhere; importer uses different DNS.**
- All four service URLs hardcoded as raw IP in tplan code. LAN renumber = stack dies.
- Importer (`vendor/tplan/import.js:677`) uses `photon.home` while frontend uses raw IP — inconsistent.
- Decision: **unify on `gis.home`** (already in AdGuard rewrites, points to 192.168.0.229).

### 🟡 Tier 2 — defer

- **Default base layer**: still public OSM tiles, not self-hosted (1-line fix, do during Step A)
- **Failure surfacing**: Valhalla 400 silently leaves null cells; Overpass timeout shows "err" with no context. 8-item resilience punchlist from agent 2 (defer)
- **Vestigial Martin/TiTiler/PostGIS**: ~4 GB reclaim if removed; keep for future raster-overlay use

### 🔵 Tier 3 — captured for future

- **International expansion**: Overpass + OSRM both USA-locked. Re-extending to Canada/Mexico/Europe is hours of rebuild on external storage (`/mnt/docker` is 1.8 TB so disk-fine; effort is the gate).
- **Mobile / off-LAN access**: requires Tailscale subnet route + URL refactor.
- **Missing data layers**: elevation (SRTM tiles for trail planning), traffic (OSRM/Valhalla support exists, needs feed), weather overlay (NWS API), tolls.
- **Switch CSV importer to Photon batch** (~30× speedup over Nominatim 1.1s throttle).

---

## Decisions made

| Decision | Rationale | Effort |
|---|---|---|
| Swap Protomaps → TileServer-GL | OSM Bright pre-built; ends custom-theme rabbit hole | 90 min |
| Swap Valhalla → OSRM | 3× lighter, half build time, free Trip endpoint, current Valhalla broken anyway | ~3 hr active + 2-3 hr unattended |
| Unify URLs on `gis.home` | LAN renumber resilience; consistency with importer | 30 min |
| Keep Photon | Right tool, planet-wide, working | — |
| Keep Overpass | Heavy (31 GB) but works; Martin migration is operational risk for marginal gain | — |
| Keep Martin/TiTiler/PostGIS running | Future raster overlays + spatial DB; ~4 GB cost is acceptable | — |

## Tradeoffs accepted

- **OSRM lacks truck profiles, isochrones, time-of-day costing** — tplan doesn't use any of these. Future: revisit if road-trip planning needs grow into cargo / multi-modal.
- **TileServer-GL uses ~500 MB-2 GB RAM** vs Protomaps' <50 MB. LXC 131 has 24 GB; not a constraint.
- **Both new tile + routing data are USA-only**. International trips require future rebuild.
- **No automated diff-update for OSRM** — quarterly re-extract from Geofabrik is the refresh path. Same as Valhalla had.

## Empirical anchors

- Hetzner CCX23 → Tucson (sustained transfer): ~120 Mbps observed
- thinkbroadband UK → Tucson with `aria2 -x 8`: 309 Mbps
- Protomaps planet PMTiles extract (USA bbox): 8.6 GB, 4 min via range requests
- Overpass USA build: 8 hr unattended on Hetzner
- Estimated OSRM USA build: 2-3 hr unattended on Hetzner

## Stack post-swap (target state)

| Service | Status | Coverage | URL |
|---|---|---|---|
| Photon (geocoder)         | unchanged | planet | `gis.home:2322` |
| Overpass (POIs)           | unchanged | USA    | `gis.home:12345` |
| OSRM (routing) **NEW**    | replacing Valhalla | USA | `gis.home:8002` |
| TileServer-GL **NEW**     | replacing Protomaps | USA | `gis.home:8200/styles/*` |
| Martin / TiTiler / PostGIS| unchanged | n/a    | future raster overlays |

## Open questions (post-execution)

- Verify NYC ↔ Chicago ↔ Austin routes return reasonable distance/time after OSRM swap
- Compare TileServer-GL OSM Bright pixel-by-pixel against tile.openstreetmap.org for visual fidelity
- Measure OSRM RAM under realistic concurrent load (single user is trivial; might matter if mobile + multi-user)

## Decision log

- 2026-05-07 morning: Hetzner build for Overpass USA — completed, deployed, healthy ✓
- 2026-05-07 afternoon: Protomaps PMTiles extracted + deployed; styling fight surfaced
- 2026-05-07 evening: Multi-agent stack audit
- 2026-05-07: This document. Plan approved. Execution beginning with Step A (TileServer-GL swap).

## References
- `/home/claudeai/.claude/plans/i-was-concerned-about-gleaming-iverson.md` — full execution plan with copy-paste commands
- `/mnt/documents/personal/alec/claudeai/github/services/selfhost_maps_stack.md` — original maps-stack notes
- `/mnt/documents/personal/alec/claudeai/github/services/cartography.md` — LXC 131 GIS stack docs
- `/mnt/documents/personal/alec/claudeai/github/infrastructure/tcp-window-tuning.md` — earlier audit of network throughput

---

## Update: 2026-05-07 evening — LXC reorg complete

The Tier-1 swaps (Protomaps → TileServer-GL, Valhalla → OSRM) were paused after multi-agent review. Pivoted instead to a **namespace + folder reorganization** of LXC 131:

- LXC 131 hostname: `gis-stack` → `cartography`
- AdGuard rewrite added: `cartography.home → 192.168.0.229`
- Docker stacks split into three on shared external network `cartography_net`:
  - `map/` — `map-photon`, `map-overpass`, `map-overpass-caddy`, `map-valhalla` (tplan stack)
  - `gis/` — `gis-postgis`, `gis-martin`, `gis-titiler` (photogrammetry workstation)
  - `proxy/` — `proxy-nginx` (shared front door)
- Disk layout: `/mnt/docker/{map,gis,proxy}/` — atomic `mv` for photon (88 GB), overpass (35 GB), valhalla (4 GB), tiles (8 GB) (all on same `/dev/sde3`, ms-scale renames)
- LXC `mp0–mp3` aliases dropped (data already canonical under `/mnt/docker/gis/` on host)
- nginx switched to resolver+variable pattern for lazy-resolved upstreams (resilient to upstream restarts)

Original Tier-1 swaps (TileServer-GL, OSRM) remain shelved. The reorg made the existing stack self-documenting; further component swaps are not currently a priority.
