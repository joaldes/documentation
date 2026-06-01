# tPlan — Self-Hosted Road-Trip Planner

**Last Updated**: 2026-06-01
**Related Systems**: CT 128 (Komodo / Docker host, 192.168.0.179), CT 104 (Samba, exports `[docker]` share for static-asset edits), LXC 131 (cartography: Photon search at `photon.home:2322`, Valhalla routing at `gis.home:8002`, Overpass POI overlay at `overpass.home:12345`), Google Maps Platform (basemap tiles + Places API via backend proxy)

## Migration to Docker (2026-05-08)

Moved from native systemd on CT 124 (`/opt/tplan/`) to Dockerized stack on Komodo CT 128 (`/mnt/docker/tplan/`). Rationale: fits homelab convention (data in `/mnt/docker/<name>/`, compose in `/etc/komodo/stacks/<name>/`), unified backup story, Komodo manages restart/redeploy.

## Recent additions (2026-05-08 → 2026-05-14)

- **Staging → dev rename** (2026-05-08) — the second stack is now `tplan-dev` (`tplan-dev.home:8085`), code path `/mnt/docker/tplan/static-dev/`, db `/mnt/docker/tplan/data-dev/trips.db`. It's a live development environment, not a frozen pre-promote snapshot.
- **Google Maps frontend** (2026-05-08 → 2026-05-09) — short-lived experimental `tplan-gmaps` stack on `:8086` rebased the planner onto the Google Maps JS SDK, then promoted to live + dev and retired. The retired service is preserved (commented out) in `compose.yaml`; `static-gmaps/` + `data-gmaps/` left on disk as archive. Backend additions that landed in prod:
  - `POST /api/places/text-search` — Google Places Text Search proxy
  - `POST /api/places/lookup` — Place ID details, used by importer fallback when Photon misses
  - `GET /api/config` — exposes the Google Maps key (referrer-restricted) to the browser without hard-coding it in static HTML
  - `POST /api/route` — Valhalla wrapper kept (Google Directions not used)
  - `POST /api/overpass` — POI proxy (rate-limit + ETag cache)
  - `gplaces_cache` SQLite table — dedupes Place ID lookups across imports
  - Env var: `TPLAN_GOOGLE_KEY` in `/etc/komodo/stacks/tplan/.env`
- **Note rows** (2026-05-14) — stops now carry a `kind` field, default `"stop"`. `kind: "note"` rows render as a single-cell note instead of the full schedule row. `_migrate_stop` in `app.py` handles upgrade.
- **Schema reconcile** (2026-05-14, the "stroll" fix) — `ensure_v2_schema` now reconciles core-column `options` against `DEFAULT_COLUMNS` on every load, so dropdown choices added to the canonical schema propagate to existing trips that were saved before the new option existed.
- **Trip sharing** (2026-05) — read-only public share links: `POST /api/trips/{tid}/shares` mints a slug; viewer at `GET /s/{slug}` + `/s/{slug}/data` + `/s/{slug}/meta`. List/revoke via the `shares` endpoints.

## Recent additions (2026-05-06)

- **Overpass POI overlay** — `js/overpass.js` (~280 LOC IIFE module). Six-chip strip next to the search box (Food / Fuel / Lodging / Sights / Shopping / Other). At zoom ≥ 13, debounced bbox query against `overpass.home:12345/api/interpreter`, renders results as small color-coded teardrop pins (14×19 px, black outline, hover-scale 1.4×). Click pin → popup with name + Add to day picker / Add to ideas. localStorage cache by rounded-bbox tile, 24h TTL. RenderToken guards prevent stale fetches from over-painting fresh results. CSS in `css/map.css`.
- **Photon migration** — backend moved from CT 128 to LXC 131. URL references in `js/search.js`, `js/edit-location.js`, `vendor/tplan/import.js` (live + dev) updated from `192.168.0.179:2322` → `photon.home:2322`.

---

## Quick Reference

| Item | Live | Dev |
|------|------|-----|
| **URL** | http://tplan.home:8084/ | http://tplan-dev.home:8085/ |
| **Direct IP** | http://192.168.0.179:8084/ | http://192.168.0.179:8085/ |
| **Container** | `tplan-live` | `tplan-dev` |
| **Code dir** (shared) | `/mnt/docker/tplan/code/` (app.py, smart_search.py, requirements.txt, Dockerfile) — bind-mounted ro |
| **Static dir** | `/mnt/docker/tplan/static-live/` | `/mnt/docker/tplan/static-dev/` |
| **SQLite DB** | `/mnt/docker/tplan/data/trips.db` | `/mnt/docker/tplan/data-dev/trips.db` |
| **Compose** | `/etc/komodo/stacks/tplan/compose.yaml` (single stack, both services) |
| **No-cache headers** | yes (middleware in `app.py`) | yes |
| **Backups** | `/mnt/docker/tplan/backups/` daily 3am via `/etc/cron.d/tplan-backup` on CT 128, 14d retention. Both DBs covered. |
| **Image rebuild** | `cd /etc/komodo/stacks/tplan && docker compose up -d --build` (after `requirements.txt` changes) |
| **Env file** | `/etc/komodo/stacks/tplan/.env` — currently holds `TPLAN_GOOGLE_KEY` for the Maps JS SDK + Places API |

> **Edit workflow**: change `static-dev/` first, verify on `tplan-dev.home:8085`, then promote: `rsync -a --delete /mnt/docker/tplan/static-dev/ /mnt/docker/tplan/static-live/`. Code in `/mnt/docker/tplan/code/` is shared by both containers — restart both after a code change: `docker compose -f /etc/komodo/stacks/tplan/compose.yaml restart tplan-live tplan-dev`.

---

## Architecture

```
Browser → tplan.home:8084 (or tplan-dev.home:8085)
  ↓
Docker container (tplan-live | tplan-dev on CT 128)
  ↓
FastAPI (uvicorn, container port 8080)
  ├── /api/trips*               (CRUD + soft-delete + restore + duplicate)
  ├── /api/trips/{id}/shares    (mint/list/revoke read-only public slugs)
  ├── /s/{slug}, /s/{slug}/data, /s/{slug}/meta  (anonymous viewer surfaces)
  ├── /api/smart-search         (LLM-assisted POI search via Ollama 192.168.0.130)
  ├── /api/photon/{path}        (Photon proxy — search + reverse)
  ├── /api/route                (Valhalla proxy — routing)
  ├── /api/overpass             (Overpass proxy + ETag cache)
  ├── /api/places/text-search,  (Google Places — gplaces_cache dedupes lookups)
  │   /api/places/lookup,
  │   /api/places/stats
  ├── /api/trail-info, /api/gas-price  (external enrichment endpoints)
  ├── /api/config               (exposes Google Maps key to browser)
  └── / (StaticFiles → /static = bind-mount of /mnt/docker/tplan/static-{live,dev}/)
        ├── index.html       (trip list)
        ├── planner.html    (the planner SPA — Google Maps SDK basemap; `/mockup-dev.html` is a back-compat alias)
        ├── css/             (8 modular files)
        ├── js/              (10 IIFE modules)
        └── vendor/          (Tabulator, MDI, custom import.js — Leaflet retired with gmaps promotion)

External services used by the planner:
  ├── Photon (photon.home:2322 on LXC 131)         — search + reverse-geocode
  ├── Valhalla (gis.home:8002 on LXC 131)          — routing
  ├── Overpass (overpass.home:12345 on LXC 131)    — POI overlay
  ├── Ollama (192.168.0.130:11434 on CT 130)       — smart-search LLM
  └── Google Maps Platform                          — basemap tiles + Places API
```

**Data flow on a trip edit:**

1. User edits a cell → Tabulator `cellEdited` fires
2. `autoFillTimeField` recomputes any related arrive/duration/depart cell
3. `commitMutation` syncs Tabulator's row data back into in-memory `tripData`
4. `cascadeArriveTimes` propagates arrival times forward through the day
5. `scheduleSave` debounced 1s → PUT `/api/trips/<id>` with full `tripData`
6. Server applies `ensure_v2_schema` (idempotent, reconciles dropdown `options` against `DEFAULT_COLUMNS`) → SQLite UPDATE wrapped in `BEGIN IMMEDIATE` on both stacks
7. Browser also writes a localStorage draft on every dirty mark; cleared on successful PUT

---

## CSS Architecture (split 2026-05-04)

The single inline `<style>` block was extracted into 8 modular files. Loaded in this exact order in `<head>` (vendored CSS first):

```html
<link href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link href="https://cdn.jsdelivr.net/npm/@mdi/font@7.4.47/css/materialdesignicons.min.css">
<link href="vendor/tabulator/tabulator.min.css">
<link href="vendor/tabulator/tabulator_midnight.min.css">
<link href="css/base.css?v=20260504b">                  <!-- :root vars, reset, body -->
<link href="css/layout.css?v=20260504b">                <!-- header, main, panes, resize -->
<link href="css/map.css?v=20260504b">                   <!-- search, legend, leaflet, popup -->
<link href="css/tabulator-overrides.css?v=20260504b">   <!-- generic Tabulator dark skin -->
<link href="css/timeline.css?v=20260504b">              <!-- .tg-grid, day-banner, drag handles -->
<link href="css/components.css?v=20260504b">            <!-- row-warn, status, btn-toolbar, resv-cards -->
<link href="css/modals.css?v=20260504b">                <!-- .modal-bg/.modal scaffold, btn-modal, day-color picker -->
<link href="css/utilities.css?v=20260504b">             <!-- escape-hatch (currently empty) -->
```

**Load order matters** — many rules have equal specificity; source order decides cascade.

### Class systems introduced during the split

- `.modal-bg` + `.modal` + `.modal__title/__hint/__input/__textarea/__actions` — shared scaffold for legend/link/booking modals
- `.btn-modal--primary/--secondary/--danger/--ghost` — shared button system across all modals + edit-location banner
- `.bk-card`, `.bk-row`, `.bk-row__label/__input/__textarea`, `.bk-card__head/__remove` — booking modal internals
- `.resv-card`, `.resv-card__head/__body/__icon/__vendor/__type`, `.resv-section`, `.resv-line__label/__value` — Reservations panel cards
- `.btn-toolbar` — header toolbar buttons (`#recalcAllBtn`, `#addDayBtn`)
- `.edit-loc-banner` — Edit Location floating banner

### Inline styles still by design

After the split, ~30 inline `style="..."` attributes remain. All are intentional:
- Runtime-positioned popups/menus (`menu.style.left = e.clientX`)
- Leaflet `divIcon` HTML (Leaflet renders the wrapper itself)
- Toast positioning math
- `style.opacity` transition triggers
- `element.style.setProperty('--col-*', ...)` runtime CSS-var writers (correct pattern, not a smell)

---

## Deploy Patterns

### Static file edits (HTML, JS, CSS)

Static files live in `/mnt/docker/tplan/static-{live,dev}/` on CT 128 — exposed via the Samba `[docker]` share. Edit via `\\samba.home\docker\tplan\static-dev\` (or `static-live` to promote). The container bind-mounts these read-only; edits show up on the next request, no restart needed.

```bash
# From CT 124 (where Claude runs), accessible via SSHFS at /mnt/komodo/docker/tplan/static-live/:
# (read-only via that mount; write via samba or via ssh root@192.168.0.179)

# Direct in-place edit via Python on CT 128:
ssh claude@192.168.0.151 'sudo pct exec 128 -- python3 -c "
src=open(\"/mnt/docker/tplan/static-live/index.html\").read()
src=src.replace(...)
open(\"/mnt/docker/tplan/static-live/index.html\",\"w\").write(src)
"'
```

### Backend (`app.py`) edits

```bash
# Edit + restart container (uvicorn doesn't auto-reload on bind-mount changes):
ssh claude@192.168.0.151 'sudo pct exec 128 -- python3 -c "
src=open(\"/mnt/docker/tplan/code/app.py\").read()
src=src.replace(...)
open(\"/mnt/docker/tplan/code/app.py\",\"w\").write(src)
"'
ssh claude@192.168.0.151 'sudo pct exec 128 -- docker compose -f /etc/komodo/stacks/tplan/compose.yaml restart tplan-live'
```

### Adding Python deps

Edit `/mnt/docker/tplan/code/requirements.txt`, then rebuild + redeploy:
```bash
ssh claude@192.168.0.151 'sudo pct exec 128 -- bash -c "cd /etc/komodo/stacks/tplan && docker compose up -d --build"'
```

### Cache-busting

`no_cache_dev_assets` middleware in `app.py` sets `Cache-Control: no-cache` on `/css/*`, `/js/*`, `*.html`, `/`. The `?v=YYYYMMDDx` query strings on `<link>` tags are belt-and-suspenders against any future proxy that ignores `Cache-Control`.

---

## Schema Migration

`ensure_v2_schema(data)` runs on every GET and PUT. Idempotent (uses `if k not in s` for defaults, so it never overwrites existing values). Adds:

**Stop-level v2 fields**: `kind` (default `"stop"`; `"note"` renders as a single-cell note row), `priority`, `status`, `flags`, `closure`, `hours`, `notes`, `link`, `rolloverFrom`, `alternateTo`, `activityType`, `costEst`, `costPerPerson`, `booked`, `bookings`, `_autoArrive`. Legacy `reservation` → `booking` migration also folds into `bookings: [booking]` + `booked: bool(confirmed)`. `_migrate_stop` (`app.py:243`) is the single upgrade path.

**Trip-level**: `columns` defaults seeded from `DEFAULT_COLUMNS`. As of the 2026-05-14 "stroll" fix, `ensure_v2_schema` also **reconciles** the `options` array on every core column against canonical `DEFAULT_COLUMNS` — so when a new dropdown choice is added to the schema, existing trips pick it up on next load without a manual migration.

To force a migration sweep over all trips on the live DB:
```bash
ssh claude@192.168.0.151 'sudo pct exec 128 -- docker exec tplan-live python -c "
import sqlite3, json, sys
sys.path.insert(0, \"/app\")
from app import ensure_v2_schema
con = sqlite3.connect(\"/data/trips.db\"); cur = con.cursor()
for tid, dj in cur.execute(\"SELECT id,data FROM trips\").fetchall():
    d = json.loads(dj)
    _, mut = ensure_v2_schema(d)
    if mut: cur.execute(\"UPDATE trips SET data=? WHERE id=?\", (json.dumps(d), tid))
con.commit(); con.close()
"'
```
Swap `tplan-live` → `tplan-dev` for the dev DB.

---

## Long-running ops

For Time Team migration / bulk dig folder reorg / large CSV regenerate / mass NFO writeback, wrap with `jobctl run` so progress surfaces at `http://jobs.home:8077`. Future Photon-batch importer kicks (1000+ stops) should also wrap with `jobctl run tplan-import -- python3 import.py …`. See `services/jobs-home.md`.

## Backups

- **Cron**: daily 3am at `/etc/cron.d/tplan-backup` on CT 128 → `sqlite3 .backup` to `/mnt/docker/tplan/backups/`. 14-day retention. Both `trips.db` (live) and `data-dev/trips.db` covered.
- **Off-disk**: rely on whatever covers `/mnt/docker/` at the host level (urbackup CT 111).
- **Pre-migration snapshot**: `/mnt/documents/personal/alec/claudeai/tplan-data/tplan-postmigration-snapshot-20260508.tgz` — 14MB tgz of code + data + data-staging at the Docker cutover moment. Kept for reference.
- **Pre-refactor snapshots from 2026-05-04 era**: cleaned up. CT 124 `/opt/tplan/` directory was wiped during the 2026-05-08 Docker migration; the `tplan.preCSS-...` snapshot under CT 104 documents has also been removed.
- **Archive of obsolete prototypes**: `/mnt/documents/personal/alec/claudeai/tplan-archive/2026-05-04/` — `mockup.html` + `icon-test.html` (live + dev copies). Indefinite retention; outside the served static tree so not reachable via HTTP.
- **Retired gmaps stack**: `/mnt/docker/tplan/static-gmaps/` + `data-gmaps/` left on disk after the 2026-05-09 promotion; container is commented out in `compose.yaml`. Safe to delete once you're confident the merged code path is stable.
- **Browser-side**: every `scheduleSave()` writes `localStorage[tplan.draft.<tripId>]`. On load, if newer than server's `updated_at`, silently auto-restored and re-PUT.

---

## Soft-delete + Restore (shipped 2026-05-04)

Trip deletion is now recoverable. `DELETE /api/trips/{id}` sets `deleted_at = <ISO timestamp>` instead of dropping the row. Trips remain restorable for 30 days, then a sweep on `tplan` lifespan startup hard-deletes them.

| Endpoint | Behavior |
|---|---|
| `GET /api/trips` | Live trips only (default) |
| `GET /api/trips?deleted_only=true` | Trash view |
| `GET /api/trips?include_deleted=true` | Both |
| `GET /api/trips/{id}` | 404 if soft-deleted (unless `?include_deleted=true`) |
| `PUT` / `PATCH /api/trips/{id}` | 410 Gone if soft-deleted (must restore first) |
| `DELETE /api/trips/{id}` | Soft-delete (default); `?permanent=true` for hard |
| `POST /api/trips/{id}/restore` | Clears `deleted_at`, returns the trip |

Schema: `deleted_at TEXT` column + partial index `idx_trips_deleted_at_live ON trips(deleted_at) WHERE deleted_at IS NULL` (live queries hit only the small live-row index).

Frontend (`index.html`): optimistic delete + Undo toast (5s); collapsed "Recently deleted" section with countdown ("Deletes in N days", red < 7); Restore + Delete-forever buttons per deleted card.

API responses omit `deleted_at` when null (live trips don't carry the field; only soft-deleted trips include it). Keeps the wire format clean.

---

## JS modular layout (shipped 2026-05-04)

`planner.html`'s inline `<script>` was reduced from **3996 → 2823 lines** (-1173) on 2026-05-04 by extracting 10 cluster modules into `js/`. Pattern: each file is an IIFE (`(function(global){ 'use strict'; ... global.tplanX = {...}; })(window)`) — same precedent as `vendor/tplan/import.js`. Bare-name back-compat shims (e.g. `global.pushHistory = pushHistory`) so existing call sites in core remain unchanged. (File was named `mockup-dev.html` at the time of the split; renamed to `planner.html` during the 2026-05-09 Google Maps promotion. `/mockup-dev.html` is still a back-compat route.)

Load order (in `<body>`, after the body DOM, before the inline `<script>`):
```
js/toast.js          (Phase 1 — shared toast helper, used by undo + booking)
js/time.js           (Phase 2 — clock parse/format, intra-row + cascade)
js/undo.js           (Phase 2 — _history/_redo + Ctrl+Z/Y listener)
js/day-color.js      (Phase 3 — DEFAULT_DAY_COLORS palette + picker modal)
js/reservations.js   (Phase 3 — Reservations side panel renderer)
js/search.js         (Phase 4 — Photon search bar + add-popup)
js/edit-location.js  (Phase 4 — drag-pin Edit Location banner + Regen name)
js/booking-modal.js  (Phase 5 — BOOKING_TYPES/_FIELDS + showBookingModal)
js/day-renderer.js   (Phase 5 — renderDayGroupHeader + preserveScroll)
js/day-sortable.js   (Phase 5 — wireDaySortable, day-banner reorder)
```

**Hub globals** that stayed in the inline script: `tripData`, `_tripMeta`, `_saveState`, `_table`, `map`, `mapMarkers`, `mapPolylines`. Their declarations are `var` (not `let`/`const`) so modules can read/write via `window`. Top-level function declarations (`renderAll`, `pushHistory`, `findStop`, etc.) auto-attach to `window` and are accessed by modules ambiently.

**Snapshots** at `tplan-archive/2026-05-04/jsmod-phase{1..5}/` capture each phase's verified state for clean rollback.

All three regressions surfaced during the Phase 5 verification ("Clear all reservations" stale panel, day drag-reorder skipping recalc, Add Day flicker) were fixed on 2026-05-04 — see the Open Audit Items table for the resolutions.

---

## Open Audit Items (deferred 2026-05-04)

| Item | Severity | Notes |
|---|---|---|
| ~~Importer uses Nominatim (1.1s throttle)~~ | DONE 2026-05-04 | Switched to Photon (`192.168.0.179:2322/api`) with 8-way parallel batches. Importer now does a 30-stop import in ~1 s instead of ~33 s. Min 800 ms display + demoted-count message in `index.html commitImport`. Known imperfection: ambiguous POI names without location bias may resolve to the wrong match (post-commit "fix locations" UI handles it). |
| ~~Live missing `BEGIN IMMEDIATE` on PUT~~ | DONE 2026-05-04 | Rode along with soft-delete promotion (`put_trip` wraps the UPDATE in `BEGIN IMMEDIATE`). |
| ~~Live missing `no-cache` middleware~~ | DONE 2026-05-04 | Middleware now deployed; cache-buster query strings still in place as belt-and-suspenders. |
| ~~Hard-delete on trips, no undo~~ | DONE 2026-05-04 | Soft-delete + 30-day Recently-deleted section live. See section above. |
| ~~4000-line `mockup-dev.html` JS monolith~~ | DONE 2026-05-04 | Split into 10 IIFE modules under `js/`. 3996 → 2823 lines. See "JS modular layout" section above. (File later renamed to `planner.html` in the 2026-05-09 gmaps promotion.) |
| ~~Reservations panel stale after "Clear all"~~ | DONE 2026-05-04 | Removed `display==='none'` early-return in `js/reservations.js renderReservationsPanel`. Always builds; cost is sub-ms. |
| ~~Day drag-reorder doesn't auto-recalc routes~~ | DONE 2026-05-04 | After `renderAll()` in `js/day-sortable.js onEnd`, iterate days and call `global.recalcRoutes(d.id)` when `global.autoRoute` is on. (Required `let autoRoute` → `var autoRoute` in core for window access.) |
| ~~Add Day briefly shows previous day's stops~~ | DONE 2026-05-04 | Removed premature `setGroupValues` from `addDay`. `replaceData()` sets groups via `_dayId`. (Sibling `reorderDays`/`deleteDay` unchanged — not reported broken.) |
| No automated tests | Won't fix (2026-05-04) | Playwright design done; declined to add test infra for a single-user app. Manual verification on dev before promote remains the workflow. |
| No auth on `/api/` | **Blocks road access** | Open `/api/trips*` + `/api/places/*` would let anyone on the public internet read/write your trip DB and burn your Google Places quota. Must solve before exposing outside the LAN. Three viable approaches: (1) VPN-only access via CT 133 WireGuard — done today, zero code change; (2) Cloudflare Tunnel + Cloudflare Access in front of `tplan-live` — TLS + SSO at the edge, no app changes; (3) shared-secret/basic-auth middleware in `app.py` — cheap but uglier. Trip-sharing `/s/{slug}` viewer is already read-only and slug-scoped, so it's safe to expose even without auth on `/api/`. |
| Frontend hits LAN hostnames directly | Blocks road access (browser) | `js/search.js`, `js/edit-location.js`, `js/overpass.js`, importer all reference `photon.home`, `overpass.home`, `gis.home` from the browser. These don't resolve from cellular. Either route every call through the existing backend proxies (`/api/photon/{path}`, `/api/overpass`, `/api/route`) or ensure the road-access path tunnels DNS too (WireGuard does; Cloudflare Tunnel doesn't). |
| No offline mode | Optional (road access nice-to-have) | localStorage drafts already buffer edits during save failures. Full offline would need a service-worker pre-caching the active trip JSON + map tiles for a bbox. Defer until road testing shows it's needed. |

---

## Verification

After any deploy, check:

1. **Live**: http://192.168.0.179:8084/ (or `tplan.home:8084`) loads trip list; click a trip → Tabulator + Google Maps render
2. **Dev**: http://192.168.0.179:8085/ (or `tplan-dev.home:8085`) loads identically
3. **CSS**: `for f in base layout map tabulator-overrides timeline components modals utilities; do curl -s -o /dev/null -w "${f}: %{http_code}\n" "http://192.168.0.179:8084/css/${f}.css"; done` → all `200`
4. **Photon**: `curl "http://photon.home:2322/api?q=fossil+butte&limit=1"` → returns JSON with `Fossil Butte National Monument`
5. **Google config**: `curl "http://192.168.0.179:8084/api/config"` → returns `{"googleMapsKey":"..."}` (referrer-restricted; safe to expose)
6. **Save round-trip**: edit a stop name → wait 2s → reload page → name persisted

## Troubleshooting

**CSS rule not winning**: check load order (`base → layout → map → tabulator-overrides → timeline → components → modals → utilities`). Selectors with equal specificity win on later source order. Use `utilities.css` as escape hatch with `!important`.

**Browser caching old CSS**: bump `?v=YYYYMMDDx` on every `<link>` in `planner.html`. The no-cache middleware is already active on both stacks; the version query is belt-and-suspenders against any future proxy that ignores `Cache-Control`.

**Google Maps tiles blank / SDK silently fails**: check `GET /api/config` returns a key, and that the requesting hostname is on the referrer-allow-list in Google Cloud Console for that API key. As of 2026-06-01 the allowed referrers are `tplan.home/*` and `tplan-dev.home/*` (and historically `tplan-gmaps.home/*` from the experimental stack). Any new external hostname must be added before tiles will load.

**Adding a new hostname (e.g. for road access)**: tplan code itself is hostname-agnostic — FastAPI doesn't care. Three things need updating outside the app:
1. AdGuard rewrite (or whatever resolves the new name to `192.168.0.179`)
2. Google Maps API key referrer list (Cloud Console → APIs & Services → Credentials)
3. Reverse proxy / tunnel terminating TLS, if exposed externally

**uvicorn 401 on `/css/...`**: file permissions. CT 104's umask creates dirs without world-execute. Fix: `chmod 2777 css/ && chmod 666 css/*.css` via CT 104.

**Stop ID collision after undo**: confirmed fixed 2026-05-04 with `_seedNextId()` called from both load and `undo()`. If seen again, suspect a new mutation path that doesn't reseed.

**Save failing repeatedly**: localStorage draft auto-restores on next load. Check `_saveState.errored` in DevTools console. Backoff is exponential 5s/10s/30s/60s.
