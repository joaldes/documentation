# tPlan — Self-Hosted Road-Trip Planner

**Last Updated**: 2026-05-04
**Related Systems**: CT 124 (Claude AI / FastAPI host, 192.168.0.180), CT 104 (Samba, static-asset writes), CT 128 (Photon search, 192.168.0.179:2322), LXC 131 (Valhalla routing, gis.home:8002)

---

## Quick Reference

| Item | Live | Staging |
|------|------|---------|
| **URL** | http://192.168.0.180:8080/ | http://192.168.0.180:8081/ (also `tplan-staging.home:8081`) |
| **Code dir** | `/opt/tplan/` | `/opt/tplan-staging/` |
| **Static dir** | `/mnt/documents/personal/alec/claudeai/tplan/` | `/mnt/documents/personal/alec/claudeai/tplan-staging/` |
| **SQLite DB** | `/opt/tplan/data/trips.db` | `/opt/tplan-staging/data/trips.db` (frozen snapshot) |
| **systemd unit** | `tplan.service` | `tplan-staging.service` |
| **No-cache headers** | not set (use `?v=...` cache-buster) | yes (middleware in `app.py`) |
| **Backups** | `/opt/tplan/data/backups/` daily 3am, 14d retention | none |

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
- **Pre-refactor snapshots (delete after 2026-05-11 if stable)**:
  - `/mnt/documents/personal/alec/claudeai/tplan.preCSS-20260504-1747/` — full live static-dir copy before CSS split (~936 KB)
  - `/opt/tplan/app.py.preSoftDelete-20260504` + `/opt/tplan/data/backups/trips-preSoftDelete-20260504.db` — before soft-delete (~11 MB)
  - `/opt/tplan/app.py.preLivePort-20260504` + `/opt/tplan/data/backups/trips-preLivePort-20260504.db` — purpose not recorded; same retention (~11 MB)
  - `/mnt/documents/personal/alec/claudeai/tplan-archive/2026-05-04/index.html.prePhotonImporter-20260504` + `import.js.prePhotonImporter-20260504` — before Photon importer swap
- **Archive of obsolete prototypes**: `/mnt/documents/personal/alec/claudeai/tplan-archive/2026-05-04/` — `mockup.html` + `icon-test.html` (live + staging copies). Indefinite retention; outside the served static tree so not reachable via HTTP.
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

`mockup-dev.html`'s inline `<script>` was reduced from **3996 → 2823 lines** (-1173) by extracting 10 cluster modules into `tplan/js/`. Pattern: each file is an IIFE (`(function(global){ 'use strict'; ... global.tplanX = {...}; })(window)`) — same precedent as `vendor/tplan/import.js`. Bare-name back-compat shims (e.g. `global.pushHistory = pushHistory`) so existing call sites in core remain unchanged.

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

**Known regressions surfaced during Phase 5 verification (pre-existing — filed for follow-up):**
1. "Clear all reservations" leaves the Reservations panel stale until tab switch (`renderReservationsPanel` early-returns when panel is `display:none`)
2. Day drag-reorder doesn't trigger Valhalla recalc (only `renderAll`, no `recalcRoutes` call)
3. Add Day briefly shows previous day's stops until `replaceData()` resolves (premature `setGroupValues` call in `addDay`)

---

## Open Audit Items (deferred 2026-05-04)

| Item | Severity | Notes |
|---|---|---|
| ~~Importer uses Nominatim (1.1s throttle)~~ | DONE 2026-05-04 | Switched to Photon (`192.168.0.179:2322/api`) with 8-way parallel batches. Importer now does a 30-stop import in ~1 s instead of ~33 s. Min 800 ms display + demoted-count message in `index.html commitImport`. Known imperfection: ambiguous POI names without location bias may resolve to the wrong match (post-commit "fix locations" UI handles it). |
| ~~Live missing `BEGIN IMMEDIATE` on PUT~~ | DONE 2026-05-04 | Rode along with soft-delete promotion (`put_trip` wraps the UPDATE in `BEGIN IMMEDIATE`). |
| ~~Live missing `no-cache` middleware~~ | DONE 2026-05-04 | Middleware now deployed; cache-buster query strings still in place as belt-and-suspenders. |
| ~~Hard-delete on trips, no undo~~ | DONE 2026-05-04 | Soft-delete + 30-day Recently-deleted section live. See section above. |
| ~~4000-line `mockup-dev.html` JS monolith~~ | DONE 2026-05-04 | Split into 10 IIFE modules under `tplan/js/`. mockup-dev.html: 3996 → 2823 lines. See "JS modular layout" section above. |
| ~~Reservations panel stale after "Clear all"~~ | DONE 2026-05-04 | Removed `display==='none'` early-return in `js/reservations.js renderReservationsPanel`. Always builds; cost is sub-ms. |
| ~~Day drag-reorder doesn't auto-recalc routes~~ | DONE 2026-05-04 | After `renderAll()` in `js/day-sortable.js onEnd`, iterate days and call `global.recalcRoutes(d.id)` when `global.autoRoute` is on. (Required `let autoRoute` → `var autoRoute` in core for window access.) |
| ~~Add Day briefly shows previous day's stops~~ | DONE 2026-05-04 | Removed premature `setGroupValues` from `addDay`. `replaceData()` sets groups via `_dayId`. (Sibling `reorderDays`/`deleteDay` unchanged — not reported broken.) |
| No automated tests | Won't fix (2026-05-04) | Playwright design done; declined to add test infra for a single-user app. Manual verification on staging before promote remains the workflow. |
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
