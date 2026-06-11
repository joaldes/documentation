# tPlan — Self-Hosted Road-Trip Planner

**Last Updated**: 2026-06-10
**Related Systems**: CT 128 (Komodo / Docker host, 192.168.0.179), CT 104 (Samba, static-asset writes), LXC 131 (Valhalla + Photon + Overpass, 192.168.0.229), Ollama (smart-search embeddings)

---

## Quick Reference (Dockerized on CT 128 since 2026-05-08)

| Item | Live | Dev |
|------|------|-----|
| **URL** | http://192.168.0.179:8084/ (`tplan.home`) | http://192.168.0.179:8085/ (`tplan-dev.home`) |
| **Container** | `tplan-live` | `tplan-dev` |
| **Code (shared!)** | `/mnt/docker/tplan/code/` (bind-mounted `:ro` into BOTH — app.py changes hit live on its restart) | same |
| **Static dir** | `/mnt/docker/tplan/static-live/` | `/mnt/docker/tplan/static-dev/` |
| **Data dir** | `/mnt/docker/tplan/data/` (`trips.db`, `amtrak.db` when promoted) | `/mnt/docker/tplan/data-dev/` |
| **Compose** | `/etc/komodo/stacks/tplan/compose.yaml` | same file |
| **Restart** | `docker restart tplan-live` | `docker restart tplan-dev` |
| **Cache-busting** | service worker `sw.js` — shell cache is **cache-first**: bump `VERSION` on ANY static change or browsers serve stale files | same |

---

## Amtrak Rail Legs (✅ LIVE as of 2026-06-10 — promoted on explicit user approval)

Real train legs mixed with car/POI stops: a leg whose **both endpoints have the train icon** (`mdi-train`) routes via Amtrak GTFS — actual track geometry, real schedule times in each **station's local timezone**, `+Nd` badge for overnight/multi-day trains. One train icon alone = still a driving leg (blue 🚆 warn glyph flags orphans).

- **Data**: `build_amtrak.py` (in `code/`) downloads Amtrak GTFS → sidecar `amtrak.db` next to `trips.db` (534 rail-served stations, 49 routes; shape-completeness checked; >24h overnight times parsed as raw seconds; agency-TZ→station-TZ conversion server-side). Re-run manually to refresh: `docker exec tplan-dev python3 /app/build_amtrak.py --gtfs /data/gtfs.zip --out /data/amtrak.db` (atomic replace; omit `--gtfs` to download fresh).
- **Endpoints** (file-guarded — return `{ok:false, reason:"amtrak_unavailable"}` until `amtrak.db` exists in that env's data dir): `GET /api/amtrak/stations?q=` / `?all=1`, `POST /api/amtrak/route {from:{stop_id|lat,lng}, to:{...}}`. Same-station pair → `{ok:true, transfer:true}` (zero-length transfer leg, not an error).
- **Frontend** (live + dev, identical as of the 2026-06-10 promote): rail branch in `recalcRoutes`; rail-aware `cascadeArriveTimes` anchors arrivals to the absolute GTFS time (survives force-recalc); rail miles excluded from drive-distance/fuel totals (fare still counts via Cost); via-inserts rejected on rail legs; station search merged into the search dropdown (🚆 rows); **Amtrak Stations map chip** (last chip row) shows all stations, pin click → add-stop popup carrying `amtrakStopId`; warn glyphs: red 🚆 no-direct-route (add the transfer station as its own stop), amber 🚆 approximate geometry, blue 🚆 orphan train icon.
- **Transfers (2026-06-10, sw `v3.4-transfer`)**: two consecutive 🚆 rows at the **same station** (alight train A, board train B) = quiet zero-length leg — blank Dist/Drive, nothing drawn, blue ⇄ info glyph. Detected client-side on matching `amtrakStopId` (no fetch) or server-side via the `transfer:true` response. The transfer row's arrive cascades from the previous row's depart; set its Depart/Duration to the connection time; the next train re-anchors from its real schedule.
- **Rendering (Phase 3, 2026-06-10)**: one polyline **per leg** (`mapPolylines: Map<dayId, Polyline[]>`, painted by `_paintDayPolylines`) — **rail legs dashed** in the day color (dash symbols on an opacity-0 stroke, `clickable:false` so they don't swallow via-drags on crossing road legs), road legs solid. Car-train-car = solid/dashed/solid in one day. Reuse invariant: unchanged leg count + rail flags → `setPath` only, never `setMap` (keeps edit-location's hidden lines hidden, no blink during live pin drag). Leg arrays are keyed by **active-stop index** (matches `_routeCoords`/`_routeIsRail`); `js/undo.js` + `js/edit-location.js` iterate the arrays.
- **Promoted to live 2026-06-11 (v3.5 + v3.6 + v3.7)**: `static-dev/{planner.html, sw.js, js/edit-location.js}` → `static-live/` (backups `*.bak-pre-v37-promote-20260611`); `tplan-live` restarted to pick up the shared-app.py phantom-booking fix. Verified: planner md5 == dev, sw `v3.7-linkfix`, trips/rail/transfer/route APIs green. Live and dev frontends are identical as of this date.
- **Overnight rail = lodging (2026-06-11, sw `v3.5-rail-overnight`)**: sleeping aboard is treated like a lodging stop — `mdi-train` is a mirror-trigger icon, so a day ending at a station auto-seeds the next day's linked 🚆 head (same machinery as hotel/camp mirroring; `amtrakStopId` mirrors along). Layout: boarding station = last stop of day N, arrival station = first real stop of day N+1 → GTFS-anchored arrival, dashed track on day N+1. The `+Nd` badge is now **day-relative** (`_railDayOffsetShown`): a 1-night train split across days shows no badge (the day split already says it), the same leg within one day still shows `+1d`. Boarding stop's blank Depart auto-fills from the schedule (same-day legs only; never overwrites a user-set time). Train-linked heads get an "Overnight aboard the train" tooltip.
- **Mirror/link fix pass (2026-06-11, sw `v3.6-mirror-fixes`)**: hardening from a multi-agent review of the overnight-rail feature. Train tails only auto-mirror **boarding** stations (a tail that's itself a same-day rail *arrival* no longer seeds a phantom "aboard" row; rode-in-then-reboard → right-click → Insert mirrored start). New per-day `mirrorOptOut`: deleting a linked mirror head, dragging its pin, changing its icon, or relocating it via edit-location now breaks the link AND stops auto re-mirroring of that day (re-enable via Insert mirrored start). Cell edits (times/cost) no longer break the link — only name flags an override. After delete-day/delete-tail/reorder, linked heads that no longer match their new prev tail are unlinked + recalced instead of silently morphing. `+Nd` badge falls back to the raw GTFS offset on pre-v3.5 trips. Mirror stubs no longer emit `reservation: null`, and `_migrate_stop` in shared `code/app.py` no longer converts a null reservation into a phantom *confirmed* lodging booking (**live picks this up at its next container restart**; existing phantom bookings in saved trips are NOT auto-removed). Backups `*.bak-pre-mirrorfix-20260611` (planner.html, sw.js, edit-location.js, app.py).
- **v3.7-linkfix (2026-06-11, sw `v3.7-linkfix`)**: follow-up from a multi-agent review of v3.6. Edit-location Save now distinguishes moves from rename-only edits (rename keeps the mirror link + `amtrakStopId`; a coord-less stop gaining its first pin counts as moved); any change to a day's tail (pin drag, icon, edit-location) now re-routes a linked next day via shared `_recalcLinkedNextDayIfTail`; localStorage draft conflict handling hardened (`_writeDraft` preserves the draft's base `serverUpdatedAt` so stale drafts can't silently overwrite another device's save; overwrite-resolution clears the draft; older-than-server drafts are pruned on load); mirror migration on load now runs after draft-restore and id-seeding (fixes a latent id-collision); bulk delete/move and table row-drags get the same unlink-don't-morph treatment as single deletes. Backups `*.bak-pre-v37-20260611`.
- **Limitations (v1)**: single-route legs only — transfers are modeled as explicit same-station stop pairs; schedule indicative as-of-feed-date.
- **Promoted 2026-06-10**: `static-dev/{planner.html,sw.js}`, `js/{time,search,overpass,undo,edit-location}.js`, `css/{map,components}.css`, `vendor/tplan/import.js` → `static-live/` (backups `*.bak-pre-amtrak-promote-20260610` in place); `data-dev/amtrak.db` → `data/`. No restart needed (shared app.py already current; amtrak.db guard is per-request). Verified: live `/api/trips` intact, DEN→CHI dep 18:59 MT / arr 14:39 CT `+1d`, CHI→CHI `transfer:true`, sw `v3.4-transfer`, stations chip live. **GTFS refresh on live**: `docker exec tplan-live python3 /app/build_amtrak.py --out /data/amtrak.db`.

---

## Architecture

```
Browser
  ↓
FastAPI (uvicorn, CT 124, port 8080)
  ├── /api/trips* (CRUD)
  └── / (StaticFiles → /mnt/documents/.../tplan/)
        ├── index.html       (trip list)
        ├── mockup-dev.html  (the planner SPA)
        ├── css/             (8 modular files)
        └── vendor/          (Tabulator, Leaflet, MDI, custom import.js)

External services used by the planner:
  ├── Photon (192.168.0.179:2322)  — search + reverse-geocode
  ├── Valhalla (gis.home:8002)     — routing
  └── Stadia/Esri/OSM tiles        — basemap (TODO: self-host TileServer-GL)
```

**Data flow on a trip edit:**

1. User edits a cell → Tabulator `cellEdited` fires
2. `autoFillTimeField` recomputes any related arrive/duration/depart cell
3. `commitMutation` syncs Tabulator's row data back into in-memory `tripData`
4. `cascadeArriveTimes` propagates arrival times forward through the day
5. `scheduleSave` debounced 1s → PUT `/api/trips/<id>` with full `tripData`
6. Server applies `ensure_v2_schema` (idempotent) → SQLite UPDATE wrapped in `BEGIN IMMEDIATE` (staging only — TODO live)
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

The Samba share `/mnt/documents/personal/alec/claudeai/tplan/` is owned by CT 104 (`claudeai:nogroup`). CT 124's uvicorn runs as root which maps to `nobody` (LXC user namespace) and falls into "other" perms. Direct writes from other containers create files that uvicorn can't read.

**Always edit via CT 104**:

```bash
# Single-file edit:
cp /mnt/documents/personal/alec/claudeai/tplan/mockup-dev.html /tmp/
# ... edit /tmp/mockup-dev.html ...
scp -q /tmp/mockup-dev.html claude@192.168.0.151:/tmp/
ssh claude@192.168.0.151 'sudo pct push 104 /tmp/mockup-dev.html /mnt/documents/personal/alec/claudeai/tplan/mockup-dev.html'

# Direct in-place edit via Python on CT 104:
ssh claude@192.168.0.151 'sudo pct exec 104 -- python3 - << "PYEOF"
... open/replace/write ...
PYEOF'

# After creating new files in css/ (or any subdir), chmod traversable:
ssh claude@192.168.0.151 'sudo pct exec 104 -- bash -c "chmod 2777 /mnt/documents/personal/alec/claudeai/tplan/css && chmod 666 /mnt/documents/personal/alec/claudeai/tplan/css/*.css"'
```

### Backend (`app.py`) edits

```bash
# Edit + restart:
ssh claude@192.168.0.151 'sudo pct exec 124 -- python3 -c "
src=open(\"/opt/tplan/app.py\").read()
src=src.replace(...)
open(\"/opt/tplan/app.py\",\"w\").write(src)
"'
ssh claude@192.168.0.151 'sudo pct exec 124 -- systemctl restart tplan'
```

### Cache-busting

Live currently relies on the `?v=YYYYMMDDx` query string on each `<link href="css/...?v=...">` tag. Bump the version when CSS changes. Alternative: copy the `no_cache_dev_assets` middleware from staging's `app.py` (~10 lines, sets `Cache-Control: no-cache` on `/css/*` + `*.html`).

---

## Schema Migration

`ensure_v2_schema(data)` runs on every GET and PUT. Idempotent (uses `if k not in s` for defaults, so it never overwrites existing values). Adds:

**Stop-level v2 fields**: `priority`, `status`, `flags`, `closure`, `hours`, `notes`, `link`, `rolloverFrom`, `alternateTo`, `activityType`, `costEst`, `costPerPerson`, `booked`, `bookings`, `_autoArrive`. Legacy `reservation` → `booking` migration also folds into `bookings: [booking]` + `booked: bool(confirmed)`.

**Trip-level**: `columns` defaults seeded from `DEFAULT_COLUMNS`.

To force a migration sweep over all trips:
```bash
ssh claude@192.168.0.151 "sudo pct exec 124 -- /opt/tplan/.venv/bin/python -c '
import sqlite3, json, importlib.util, sys
sys.path.insert(0, \"/opt/tplan\")
spec = importlib.util.spec_from_file_location(\"app\", \"/opt/tplan/app.py\")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
con = sqlite3.connect(\"/opt/tplan/data/trips.db\"); cur = con.cursor()
for tid, dj in cur.execute(\"SELECT id,data FROM trips\").fetchall():
    d = json.loads(dj)
    _, mut = m.ensure_v2_schema(d)
    if mut: cur.execute(\"UPDATE trips SET data=? WHERE id=?\", (json.dumps(d), tid))
con.commit(); con.close()
'"
```

---

## Backups

- **Cron**: daily 3am at `/etc/cron.d/tplan-backup` → `sqlite3 .backup` to `/opt/tplan/data/backups/`. 14-day retention.
- **Pre-CSS-split snapshot**: `/mnt/documents/personal/alec/claudeai/tplan.preCSS-20260504-1747` — full live static-dir copy. Safe to delete after a week of CSS-split stability.
- **Browser-side**: every `scheduleSave()` writes `localStorage[tplan.draft.<tripId>]`. On load, if newer than server's `updated_at`, silently auto-restored and re-PUT.

---

## Open Audit Items (deferred 2026-05-04)

| Item | Severity | Notes |
|---|---|---|
| Importer still uses Nominatim (1.1s throttle) | High UX | Switch `vendor/tplan/import.js geocodeTrip()` to Photon `192.168.0.179:2322/api?q=` with 8-way parallel. ~100× speedup on imports. |
| Live missing `BEGIN IMMEDIATE` on PUT | Medium | Staging has it. Concurrent PUTs (rare in single-user) can lose updates without it. |
| Live missing `no-cache` middleware | Low | Use `?v=...` cache-buster instead. |
| 4000-line `mockup-dev.html` JS still monolith | Medium | Native `<script type="module">` ESM is the right next step. Bigger commitment than CSS. |
| No automated tests | Medium | Playwright visual-regression smoke test was sketched, never built. |
| Hard-delete on trips, no undo | Low | DB backup is the recovery path. |
| No auth on `/api/` | Low (LAN-only) | Revisit if exposed externally. |

---

## Verification

After any deploy, check:

1. **Live**: http://192.168.0.180:8080/ loads trip list; click a trip → Tabulator + map render
2. **Staging**: http://192.168.0.180:8081/ loads identically
3. **CSS**: `for f in base layout map tabulator-overrides timeline components modals utilities; do curl -s -o /dev/null -w "${f}: %{http_code}\n" "http://192.168.0.180:8080/css/${f}.css"; done` → all `200`
4. **Photon**: `curl "http://192.168.0.179:2322/api?q=fossil+butte&limit=1"` → returns JSON with `Fossil Butte National Monument`
5. **Save round-trip**: edit a stop name → wait 2s → reload page → name persisted

## Troubleshooting

**CSS rule not winning**: check load order (`base → layout → map → tabulator-overrides → timeline → components → modals → utilities`). Selectors with equal specificity win on later source order. Use `utilities.css` as escape hatch with `!important`.

**Browser caching old CSS**: bump `?v=YYYYMMDDx` on every `<link>` in `mockup-dev.html`, OR install the no-cache middleware (~10 lines copied from staging).

**uvicorn 401 on `/css/...`**: file permissions. CT 104's umask creates dirs without world-execute. Fix: `chmod 2777 css/ && chmod 666 css/*.css` via CT 104.

**Stop ID collision after undo**: confirmed fixed 2026-05-04 with `_seedNextId()` called from both load and `undo()`. If seen again, suspect a new mutation path that doesn't reseed.

**Save failing repeatedly**: localStorage draft auto-restores on next load. Check `_saveState.errored` in DevTools console. Backoff is exponential 5s/10s/30s/60s.
