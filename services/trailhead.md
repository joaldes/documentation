# Trailhead — Weather & Wildlife Dashboard

**Last Updated**: 2026-03-23

**Related Systems**: Komodo (CT 128), BirdNET-Go, Ecowitt Weather Station, Sonarr (CT 110), Frigate NVR, AdGuard (CT 101), NPM (CT 112), Authentik SSO (192.168.0.179:9000)

## Summary

A static weather dashboard styled after the National Park Service design system. A Python generator fetches live weather data from an Ecowitt station, bird detections from BirdNET-Go, sun/moon events via the astral library, NWS radar imagery, a Frigate camera snapshot, sky event data (ISS passes, launches, meteor showers, eclipses), NWS forecast synopsis, upcoming TV episodes from Sonarr, and a daily NPS park — every 5 minutes. It renders three Jinja2 HTML templates (dashboard, sky events reference page, and TV calendar) with matplotlib charts and serves the result through nginx. The header displays a live JavaScript clock. Runs as a Docker Compose stack on Komodo.

Previously called "neighborhood-page" — renamed to "trailhead" on 2026-02-27.

## Quick Reference

### Stack

Two-service Docker Compose on Komodo (CT 128, 192.168.0.179:8076). Python generator runs every 5 minutes via `while true; sleep 300` loop, writes static HTML + charts to a shared volume. nginx serves the output.

| Service | Image | Role | Limits |
|---------|-------|------|--------|
| `generator` | python:3.12-slim | Fetches data, renders HTML + charts every 5 min | 1 CPU / 512MB |
| `web` | nginx:alpine | Static file server on :8076 with Authentik forward auth | 0.5 CPU / 128MB |

### Source Files (`/mnt/docker/trailhead/`)

| File | Purpose |
|------|---------|
| `generate.py` | Main Python generator — fetches all data, renders Jinja2, generates matplotlib charts |
| `template.html` | Jinja2 template for main dashboard |
| `sky-events.html` | Jinja2 template for `/sky` reference page |
| `tv-calendar.html` | Jinja2 template for `/tv` TV calendar page |
| `trailhead.yaml` | Access groups + sidebar tab/card definitions |
| `.env` | API keys (Ecowitt, NPS, N2YO, etc.) + coordinates |
| `entrypoint.sh` | Font copy + generator loop (5s trigger check) + regen HTTP server on :8077 |
| `regen-server.py` | Tiny HTTP server — `POST /regen` touches trigger file for immediate regeneration |
| `alerts.json` | Alert banner data — array of `{message, type, expires}` objects (bind-mounted into container) |
| `Dockerfile` | Python 3.12-slim, runs as non-root `appuser` |
| `nginx.conf` | Static server + Authentik forward auth + security headers |
| `logged-out.html` | Static logout landing page with 5s redirect countdown |
| `requirements.txt` | Pinned Python dependencies |
| `fonts/` | NPS typefaces (Frutiger, National Park, NPS 1935, NPS 1945 signage) |

Compose file: `/etc/komodo/stacks/trailhead/compose.yaml`

### Data Sources

| Source | Data | Cache |
|--------|------|-------|
| Ecowitt API v3 (realtime) | Temp, humidity, wind, pressure, UV, PM2.5, rain | 5 min |
| Ecowitt API v3 (history) | 24h rolling temp + wind (288 points) | 5 min |
| BirdNET-Go (local) | Top 20 bird species detected today | 5 min |
| astral (Python lib) | Sun events + moon phase/illumination | 5 min |
| NWS KEMX | Radar loop GIF (Tucson region) | 5 min |
| NWS AFD/TWC | Area Forecast Discussion synopsis | 3 hours |
| NWS Forecast | 7-day high/low/rain% | 3 hours |
| Frigate (local) | Driveway camera snapshot + event count | 5 min |
| N2YO API | ISS passes (filtered: maxEl>=40°, mag<=-1.5) | 6 hours |
| Launch Library 2 | Next Vandenberg launch (non-Starlink) | 6 hours |
| Meteor showers | 8 major annual showers (±3 days from peak) | Static |
| Curated sky events | Eclipses, conjunctions, supermoons, oppositions | Static |
| NPS API | Park of the day (name, description, image) | Daily |
| Sonarr API (local) | Upcoming TV episodes (calendar endpoint, 90-day window) | 5 min |

### Generated Output (`/output/` shared volume)

`index.html`, `sky.html`, `tv.html`, `temp-chart.png`, `wind-chart.png`, `radar.gif`, `driveway.jpg`, `nps_parks_cache.json`, `iss_cache.json`, `launch_cache.json`, `synopsis_cache.json`, `forecast_cache.json`, `fonts/*.woff2`

### Quick Commands

```bash
# Code change (no rebuild needed — source is bind-mounted)
scp generate.py template.html root@192.168.0.179:/mnt/docker/trailhead/
ssh root@192.168.0.179 "docker restart trailhead-generator"

# Full rebuild (only for Dockerfile/requirements.txt/entrypoint.sh)
cd /etc/komodo/stacks/trailhead && docker compose build --no-cache && docker compose up -d

# Logs & status
docker logs trailhead-generator --tail 30
docker ps --filter name=trailhead

# Force immediate regeneration
docker exec trailhead-generator python3 /app/generate.py
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Komodo Stack: trailhead (CT 128, 192.168.0.179)         │
│                                                          │
│  ┌─ generator (python:3.12-slim) ─────────────────────┐  │
│  │  entrypoint.sh:                                     │  │
│  │    1. Copy fonts to /output/fonts/                  │  │
│  │    2. while true: run generate.py, sleep 300        │  │
│  │                                                     │  │
│  │  generate.py (every 5 min via sleep loop):          │  │
│  │    ├─ Ecowitt API v3  → current weather + 24h hist  │  │
│  │    ├─ BirdNET-Go API  → today's bird detections     │  │
│  │    ├─ astral library  → sun events + moon phase     │  │
│  │    ├─ NWS KEMX        → radar loop GIF              │  │
│  │    ├─ NWS AFD/TWC     → forecast synopsis (3h TTL)  │  │
│  │    ├─ NWS Forecast    → 7-day high/low/rain% (3h)  │  │
│  │    ├─ Frigate API     → driveway camera snapshot    │  │
│  │    ├─ N2YO API        → ISS pass predictions (6h TTL)│  │
│  │    ├─ Launch Library  → Vandenberg launches (6h TTL) │  │
│  │    ├─ Meteor showers  → hardcoded annual calendar    │  │
│  │    ├─ Curated events  → eclipses, conjunctions, etc. │  │
│  │    ├─ NPS API         → park of the day (daily TTL) │  │
│  │    ├─ Sonarr API      → upcoming TV episodes         │  │
│  │    ├─ matplotlib      → temp + wind 24h charts      │  │
│  │    ├─ Jinja2 render   → /output/index.html          │  │
│  │    ├─ Jinja2 render   → /output/sky.html            │  │
│  │    └─ Jinja2 render   → /output/tv.html             │  │
│  └─────────────────────────────────────────────────────┘  │
│         │ writes to                                       │
│         ▼                                                 │
│  [ trailhead_page-output named volume ]                   │
│    /output/index.html           (rendered dashboard)      │
│    /output/sky.html             (sky events ref page)     │
│    /output/tv.html              (TV calendar page)        │
│    /output/temp-chart.png       (24h temperature chart)   │
│    /output/wind-chart.png       (24h wind speed chart)    │
│    /output/radar.gif            (NWS KEMX radar loop)     │
│    /output/driveway.jpg         (Frigate camera snapshot) │
│    /output/iss_cache.json       (6h ISS pass cache)       │
│    /output/forecast_cache.json  (3h NWS forecast cache)   │
│    /output/nps_parks_cache.json (daily park cache)        │
│    /output/launch_cache.json    (6h launch cache)         │
│    /output/synopsis_cache.json  (3h NWS synopsis cache)   │
│    /output/fonts/*.woff2        (NPS typefaces)           │
│         │ read by                                         │
│         ▼                                                 │
│  ┌─ web (nginx:alpine) ── port 8076 ──────────────────┐  │
│  │  Static file server with cache headers              │  │
│  │  HTML: no-cache | PNG/GIF: 5min | fonts: 1 year     │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### Data Flow

| Source | Protocol | Data | Cache |
|--------|----------|------|-------|
| Ecowitt API v3 (realtime) | HTTPS | Temperature, humidity, wind, pressure, UV, PM2.5, rain | None (every 5 min) |
| Ecowitt API v3 (history) | HTTPS | 24h rolling temperature + wind speed/gust series | None (every 5 min) |
| BirdNET-Go (local) | HTTP | Today's detected bird species (top 20) | None (every 5 min) |
| astral (Python lib) | Local calculation | Sun events + moon phase/illumination/trend | None (every 5 min) |
| NWS KEMX | HTTPS | Radar loop GIF (Tucson region) | None (every 5 min) |
| NWS AFD/TWC | HTTPS | Area Forecast Discussion synopsis | 3 hours |
| NWS Forecast | HTTPS | 7-day forecast (high, low, rain%) | 3 hours |
| Frigate (local) | HTTP | Driveway camera snapshot + today's event count | None (every 5 min) |
| N2YO API | HTTPS | ISS passes filtered for excellent viewing (maxEl>=40°, mag<=-1.5) | 6 hours |
| Launch Library 2 | HTTPS | Next Vandenberg launch (non-Starlink) | 6 hours |
| Meteor showers | Hardcoded | 8 major annual showers, shown ±3 days from peak | Static |
| Curated sky events | Hardcoded | Eclipses, conjunctions, supermoons, oppositions (2026-2027) | Static |
| NPS API | HTTPS | Park of the day (name, description, image) | Daily |
| Sonarr API (local) | HTTP | TV episode calendar (series, episode titles, air dates, status) | None (every 5 min) |

## Access

| Method | URL |
|--------|-----|
| Direct IP | `http://192.168.0.179:8076` |
| Sky events page | `http://192.168.0.179:8076/sky` |
| TV calendar page | `http://192.168.0.179:8076/tv` |
| Local domain | `http://weather.home` |
| External domain | `https://home.1701.me` (SSL via NPM, Force SSL enabled) |
| Health check | `http://192.168.0.179:8076/health` |

## File Layout

### On Komodo (192.168.0.179)

```
/mnt/docker/trailhead/
├── .env                 # API keys + coordinates (loaded by compose env_file)
├── .dockerignore        # Excludes output/ and nginx.conf from build
├── Dockerfile           # python:3.12-slim + matplotlib, non-root user
├── entrypoint.sh        # Font copy + sleep loop (runs generate.py every 5 min)
├── generate.py          # Main generator script
├── template.html        # Jinja2 HTML template (NPS design)
├── sky-events.html      # Jinja2 template for /sky reference page
├── requirements.txt     # Python dependencies
├── trailhead.yaml       # Access groups + sidebar tab/card definitions
├── nginx.conf           # Authentik forward auth + reference page routing + security headers
├── logged-out.html      # Static logout page with 5s redirect countdown
└── fonts/
    ├── frutiger.woff2
    ├── nationalpark.woff2
    ├── nps1935.woff2
    └── nps-signage-1945.woff2

/etc/komodo/stacks/trailhead/
└── compose.yaml         # Docker Compose (generator + nginx)
```

### Generated Output (inside container volume)

```
/output/
├── index.html           # Rendered dashboard page
├── sky.html             # Rendered sky events reference page
├── tv.html              # Rendered TV calendar page
├── temp-chart.png       # 24h temperature line chart
├── wind-chart.png       # 24h wind speed + gust chart
├── radar.gif            # NWS KEMX radar loop
├── driveway.jpg         # Frigate camera snapshot
├── nps_parks_cache.json # Daily park cache (avoids repeated API calls)
├── iss_cache.json       # 6h N2YO ISS pass cache
├── launch_cache.json    # 6h Vandenberg launch cache
├── synopsis_cache.json  # 3h NWS synopsis cache
├── forecast_cache.json  # 3h NWS 7-day forecast cache
└── fonts/               # Copied from build at startup
    └── *.woff2
```

## Configuration

### Environment Variables (.env)

| Variable | Description | Example |
|----------|-------------|---------|
| `ECOWITT_APP_KEY` | Ecowitt API application key | `4397FB1490D72B9B42998F6BDD0C4DAF` |
| `ECOWITT_API_KEY` | Ecowitt API secret key | `651ead9a-e21d-...` |
| `ECOWITT_MAC` | Weather station MAC address | `98:CD:AC:22:C2:EA` |
| `BIRDNET_URL` | BirdNET-Go base URL | `http://192.168.0.179:8060` |
| `LATITUDE` | Station latitude | `32.4107` |
| `LONGITUDE` | Station longitude | `-110.9361` |
| `TIMEZONE` | IANA timezone | `America/Phoenix` |
| `FRIGATE_URL` | Frigate base URL | `http://192.168.0.179:5000` |
| `NPS_API_KEY` | NPS Developer API key (free) | `zNb7hFy...` |
| `N2YO_API_KEY` | N2YO satellite tracking API key | `abc123...` |
| `SONARR_URL` | Sonarr base URL | `http://192.168.0.24:8989` |
| `SONARR_API_KEY` | Sonarr API key | `abc123...` |

### Docker Compose

- **Port**: 8076
- **Resource limits**: Generator 1 CPU / 512MB, nginx 0.5 CPU / 128MB
- **Health checks**:
  - Generator: `find /output/index.html -mmin -20` (file updated within 20 min, covers 5-min interval with margin)
  - Web: `wget --spider http://127.0.0.1:80/health` (uses 127.0.0.1, not localhost — see Lessons Learned)
- **Logging**: json-file driver, max 10MB x 3 files per container
- **Restart policy**: `unless-stopped`
- **Network**: Isolated `page-net` bridge
- **Security**: Generator runs as non-root `appuser` (not root). Jinja2 autoescape enabled. NWS product URL validated. nginx returns `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`, and hides server version (`server_tokens off`). Python dependencies pinned to exact versions.
- **Volume mounts**: Source files (generate.py, template.html, fonts, entrypoint.sh, nginx.conf) are bind-mounted from `/mnt/docker/trailhead/` — no rebuild needed for code changes, just restart the generator

## Ecowitt API v3 Reference

### Unit IDs (CRITICAL)

v3 unit IDs are different from v2. These were verified 2026-02-24:

| Measurement | Unit ID | Unit | Valid Range |
|-------------|---------|------|-------------|
| Temperature | `temp_unitid=2` | Fahrenheit | 1=C, **2=F** |
| Pressure | `pressure_unitid=4` | inHg | 3=hPa, **4=inHg**, 5=mmHg |
| Wind Speed | `wind_speed_unitid=9` | mph | 6=m/s, 7=km/h, 8=knots, **9=mph**, 10=BFT, 11=fpm |
| Rainfall | `rainfall_unitid=13` | inches | 12=mm, **13=inches** |

### Realtime Endpoint

`GET https://api.ecowitt.net/api/v3/device/real_time?call_back=all`

All values are **strings** — must cast to `float()` or `int()` before use. Each field has `{time, unit, value}`.

| Data | JSON Path |
|------|-----------|
| Temperature | `data['outdoor']['temperature']['value']` |
| Feels Like | `data['outdoor']['feels_like']['value']` |
| Dew Point | `data['outdoor']['dew_point']['value']` |
| Humidity | `data['outdoor']['humidity']['value']` |
| Wind Speed | `data['wind']['wind_speed']['value']` |
| Wind Gust | `data['wind']['wind_gust']['value']` |
| Wind Direction | `data['wind']['wind_direction']['value']` (degrees) |
| Pressure | `data['pressure']['relative']['value']` |
| UV Index | `data['solar_and_uvi']['uvi']['value']` |
| Solar Radiation | `data['solar_and_uvi']['solar']['value']` |
| Rain Today | `data['rainfall']['daily']['value']` |
| Rain Monthly | `data['rainfall']['monthly']['value']` |
| Rain Yearly | `data['rainfall']['yearly']['value']` |
| PM2.5 | `data['pm25_ch1']['pm25']['value']` |

**Error handling**: API always returns HTTP 200. Check `response['code'] == 0` before accessing `response['data']`. On error, `data` is `[]` (empty list), not a dict.

**Crash protection**: Both the realtime and history fetches are wrapped in try-except. If either fails, the generator continues with empty dicts. All weather values in the template context are extracted via the `_wx()` safe accessor helper:

```python
def _wx(data, *keys, default='--'):
    """Safely traverse nested Ecowitt data dict."""
    val = data
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return default
    return val if val is not None else default

# Usage: 'temp': _wx(wx, 'outdoor', 'temperature', 'value')
```

This means the page renders with `--` fallback values if Ecowitt is completely unavailable, instead of crashing the generator.

### Rate Limit Handling (api_get wrapper)

All external HTTP requests go through `api_get()`, a wrapper around `requests.get()` that:
- Checks HTTP status and raises on 4xx/5xx errors (`raise_for_status()`)
- On **429 Too Many Requests**: sets a 30-minute per-domain cooldown, respects `Retry-After` header if present
- During cooldown: raises `APIOnCooldown` (caught by existing `except Exception` blocks — dashboard renders with fallback values)
- Cooldowns are in-memory (reset on container restart) — file-based caches (ISS 6hr, launches 6hr, NPS daily, NWS 3hr) cover restart scenarios

### History Endpoint

`GET https://api.ecowitt.net/api/v3/device/history?cycle_type=5min`

Returns dict of `{unix_timestamp_string: value_string}` per metric, ~288 points per 24h window.

```python
data['outdoor']['temperature']['list']
# → {"1771857600": "49.4", "1771857900": "49.2", ...}
```

Today's high/low are derived as `max()`/`min()` of the temperature history values — there is no dedicated realtime high/low endpoint.

## NWS Synopsis (AFD)

The NWS Area Forecast Discussion (AFD) synopsis is a short paragraph summarizing the weather outlook for the Tucson region. Fetched from the NWS API (no key needed), cached for 3 hours (AFDs issued ~4x/day).

### API Flow

1. `GET https://api.weather.gov/products/types/AFD/locations/TWC` → list of recent AFD products
2. `GET https://api.weather.gov/products/{id}` → `productText` field
3. Parse `.SYNOPSIS...` section from the text

### Parsing

AFD sections are separated by `&&`. The synopsis regex:
```python
re.search(r'\.SYNOPSIS\.\.\.\s*(.*?)\s*(?=&&|\.\w+\.\.\.)', text, re.DOTALL)
```
Whitespace is normalized with `' '.join(match.group(1).split())`.

### Display

Rendered as a left-aligned static text block on a warm gray background (`var(--nps-warm-gray)`) above the Night Sky / Park row. Large italic serif font (1.15rem) for the forecast text. Right-aligned attribution line: link to the [NWS Tucson AFD page](https://forecast.weather.gov/product.php?site=TWC&issuedby=TWC&product=AFD) followed by a pipe separator and the issued date/time (converted to local Arizona time, e.g., "3/1 1:35 PM"). Hidden if API fails (`{% if synopsis %}`).

**Note**: A scrolling ticker version (`.synopsis-ticker-*` CSS) is preserved in the template but unused — available for future reuse.

## NWS 7-Day Forecast

A horizontal strip showing 7-day high/low temperatures and rain probability, rendered between the weather tabs and the bottom-row cards.

### API

`GET https://api.weather.gov/gridpoints/TWC/91,49/forecast` — no key needed. Returns 14 periods (day/night pairs). The generator pairs them into 7 day objects with `name`, `high`, `low`, and `rain` (precipitation probability).

Cached for 3 hours at `/output/forecast_cache.json` (NWS grid forecasts update ~4x/day).

### Display

Translucent black strip (`rgba(0,0,0,0.75)`) with a thin black top border separating it from the weather tabs. Each day shows:
- 3-letter day abbreviation (or "Today") — left-justified, fixed-width
- High/low temperatures separated by `/`
- Rain % in italic sky-blue — only shown if ≥5%

Hidden gracefully if the NWS API is unavailable (`{% if forecast %}`).

## Sky Events

### Dashboard Card

The Night Sky card shows the moon on the left (SVG disc with computed arc geometry) and a list of upcoming sky events on the right. Events are sorted by time and stacked vertically with thin separators.

**Event sources:**
- **ISS passes** (N2YO API): Filtered for excellent viewing — only passes with maxEl >= 40° AND magnitude <= -1.5. Shows "Visible" badge.
- **Meteor showers** (hardcoded): 8 major annual showers (Quadrantids, Lyrids, Eta Aquariids, Delta Aquariids, Perseids, Orionids, Leonids, Geminids). Appear on the dashboard ±3 days from peak date.
- **Launches** (Launch Library 2): Next non-routine Vandenberg launch. Skips Starlink/OneWeb/Kuiper. Shows "Visible" badge during twilight windows.
- **Curated events** (hardcoded): Eclipses, conjunctions, supermoons, oppositions, planet parades. Appear on the dashboard within their configured `days_before` window.

### Reference Page (`/sky`)

A standalone NPS-styled page at `/sky` listing all tracked astronomical events. Accessible via the "View all" link in the Night Sky card header.

**Sections:**
- **Moon**: Current phase with SVG disc, illumination %, and trend
- **Coming Up**: Active dashboard events (anything currently within its display window)
- **Meteor Showers [year]**: All 8 major showers with peak dates, ZHR rates, and visual intensity bars. Past showers grayed out, active showers highlighted with "Active" badge.
- **Sky Events [year]**: Curated events grouped by year (2026, 2027). Past events grayed out, imminent events highlighted with "Soon" badge. Each links to its source.

**Adding events**: Edit `_CURATED_SKY_EVENTS` in `generate.py`, add a dict with `label`, `detail`, `date` (ISO), `url`, and `days_before` (how many days before the event to show it on the dashboard). Rebuild with `docker compose build generator && docker compose up -d`.

**Adding meteor showers**: Edit `_METEOR_SHOWERS` in `generate.py`. These are the 8 major annual showers — they repeat every year automatically.

## TV Calendar (`/tv`)

A standalone NPS-styled page showing upcoming TV episodes from Sonarr. Accessible via the TV Calendar bookmark card in the sidebar or directly at `/tv`.

### Data Source

Sonarr API calendar endpoint: `GET /api/v3/calendar?start=YYYY-MM-DD&end=YYYY-MM-DD`

The generator fetches episodes from the 1st of the current month through 60 days out, grouped by air date. Each episode includes series name, season/episode numbers, and download status.

### Layout

Two-column layout (CSS Grid `3fr 2fr`, max-width 1400px):

- **Left column**: Month navigation (prev/next arrows), calendar grid with numbered episode-count circles per day, and a day detail panel that shows episodes for the selected day
- **Right column**: Scrollable chronological episode list grouped by date, auto-scrolls to today on load. Past days dimmed at 50% opacity.

**Interactivity** (client-side JavaScript):
- Clicking a calendar day with episodes selects it and shows its episodes below the calendar
- Today is auto-selected on page load (or first day with episodes in current month)
- Month navigation auto-selects the first episode day in the new month
- Days with episodes get `cursor: pointer` and a selected highlight (blue outline)

**Responsive**: On screens narrower than 850px, columns stack vertically.

### Episode Display

Each episode row shows:
- Status dot (green `#4CAF50` = downloaded, copper = monitored/missing, gray = unmonitored)
- Series name (bold serif)
- Season/episode code (sans-serif, e.g. S01 E03)

Calendar day cells show a small numbered circle indicating episode count (green-tinted if all downloaded, copper-tinted if some missing).

### nginx Routing

Reference pages (`/sky`, `/tv`) share a single regex location block in `nginx.conf`:

```nginx
location ~ ^/(sky|tv)(\.html)?$ {
    auth_request        /outpost.goauthentik.io/auth/nginx;
    error_page          401 = @goauthentik_proxy_signin;
    auth_request_set    $auth_cookie $upstream_http_set_cookie;
    add_header          Set-Cookie $auth_cookie;
    add_header X-Content-Type-Options "nosniff" always;
    try_files /$1.html =404;
}
```

New reference pages can be added by placing a `<name>.html` template in the source directory — the regex captures the URL path and maps it to `<name>.html` automatically. No nginx config changes needed for additional pages.

## BirdNET-Go API Reference

### Daily Species

`GET /api/v2/analytics/species/daily?date=YYYY-MM-DD&limit=20`

Returns JSON array sorted by count descending:

```json
[{
    "common_name": "House Finch",
    "scientific_name": "Haemorhous mexicanus",
    "species_code": "houfin",
    "count": 52,
    "thumbnail_url": "https://upload.wikimedia.org/...",
    "first_heard": "06:08:09",
    "latest_heard": "18:08:09",
    "is_new_species": true
}]
```

**Important**: `is_new_species` key is **absent** (not false) when the species is not new. Template uses `bird.get('is_new_species')` to handle this.

Empty day returns `[]`.

## Template Design

The HTML template uses the National Park Service (NPS) design system:

- **Black band header** with white arrowhead logo and **user menu** (person icon → dropdown with username, Change Password, Log Out). Username injected at serve time via nginx `sub_filter` (see [trailhead-permissions.md](trailhead-permissions.md)).
- **Semi-transparent black identification band** (matching NPS website style) with sunrise/sunset and current temperature
- **Left multi-tab sidebar**: fixed-position left-edge panel with dark background (`var(--sidebar-bg)`), extends from header to footer (stops at footer top edge). A 40px icon tab strip (Bookmarks + Cameras) with copper left-border on active tab. Clicking a tab icon opens/toggles a 280px scrolling panel. **Bookmarks tab**: ~40 service bookmark cards across 4 groups — Home & Automation, Media, Documents & Files, Infrastructure. Cards separated by `2px solid var(--nps-brown-light)` dividers. Compact horizontal rows: title/category + Local/Remote links stacked vertically in a fixed-width column. White card backgrounds on dark panel surround. Group labels are sticky at the top while scrolling. Includes A-Z/Grouped toggle — **defaults to A-Z sort on page load**. **Cameras tab**: full-width camera snapshot cards with label and event count. Per-card access filtering via `data-access` attributes — client-side JS hides cards based on user's group memberships (see [trailhead-permissions.md](trailhead-permissions.md)). Empty tabs auto-hide. Auto-opens on screens wider than 900px; click outside to close. On mobile (≤700px), transforms to a bottom-anchored horizontal tab bar expanding upward.
- **NWS Synopsis block**: left-aligned italic serif forecast text (1.15rem) on a warm gray background. Right-aligned attribution line: `NWS Tucson Forecast Discussion | 3/1 1:35 PM` (link + issued date/time, converted to local Arizona time). Hidden gracefully if the NWS API is unavailable. A scrolling ticker variant (CSS preserved but unused) is available for future use.
- **Inline weather section**: a collapsible tabbed bar in the main content flow (below synopsis, above Night Sky / Park row). Dark blue (`var(--nps-blue-dark)`) tab bar with 3 tabs — Station, Charts, Radar. Clicking a tab expands the section and shows that tab's content; clicking the active tab collapses the section. Clicking outside the section also collapses it. Starts collapsed on page load. Content panels use `max-height` CSS transition for smooth expand/collapse animation.
  - **Station**: 6 weather metric cells in a 3x2 grid (Temperature, Humidity, Wind, Rain Today, Rain This Month, Rain This Year)
  - **Charts**: 24h temperature and wind/gust line charts (conditionally shown — hidden if chart generation failed)
  - **Radar**: NWS KEMX radar loop GIF
- **7-day forecast strip**: translucent black horizontal bar between weather tabs and bottom cards. Shows day abbreviation, high/low temps, and rain% (≥5% only, italic sky-blue). Hidden if NWS API unavailable.
- **Night Sky + Park of the Day**: two side-by-side cards at the bottom of the page. Night Sky shows an SVG moon disc (computed arc path with radial gradients, CSS `scaleX(-1)` flip for waning phases) on the left with name, illumination %, and trend arrow (copper ▲ brightening / gray ▼ dimming). On the right, multiple sky events stack vertically with thin separators: ISS passes (filtered for excellent viewing — maxEl>=40°, mag<=-1.5, shown with green "Visible" badge), Vandenberg launches (with twilight visibility indicator), meteor showers (shown ±3 days from peak), and curated astronomical events (eclipses, conjunctions, supermoons, oppositions). A "View all" link in the card header navigates to `/sky`. Park of the Day shows a different NPS park each day with photo, description, and link (cached daily via NPS API).
- **Bottom bird drawer**: horizontal scroll strip of today's detected species with Wikipedia thumbnails, detection counts, and "New" badges for first-time species. In normal document flow (not fixed-position) — stays anchored at the bottom of the page and scrolls with content. Translucent black background (`rgba(0, 0, 0, 0.75)`) matching the identification band.
- **Live clock**: JavaScript updates "Current Time" in the header every 15 seconds using the browser's local time. The "Updated" timestamp in the identification band stays static — it shows when the *data* was last refreshed server-side.
- **Font switcher**: toggles between historical NPS typefaces (1935 style, 1945 signage, 2026 modern)
- **Responsive**: works on mobile at 375px width

## Design Guidelines

This page is inspired by the NPS design system but is not a strict replica. We use the Unigrid system's visual language — black bands, colored overbars, structured grids — while keeping text readable and traditional. The key principle: **NPS structural elements for organization, normal readable typography for content.**

### NPS Design Heritage

The National Park Service design system has two lineages we draw from:

**The Unigrid System (1977)**: Created by Massimo Vignelli and Vincent Gleason for NPS brochures. Won the inaugural Presidential Design Award in 1985. Key elements we use:
- **Black band headers** — the signature 100-point black edge bar with white reversed type
- **Colored overbars** — 4px color bars above cards for category coding
- **Grid-based layouts** — modular, structured content areas
- **Black divider bars** — 25-point bars to separate sections

**NPS Typography (2001 update)**: The NPS replaced Helvetica and Clarendon with:
- **Frutiger** — sans-serif for identity elements (park names, labels, structural UI)
- **NPS Rawlinson** — serif for body/reading text (not publicly available; we substitute Lora)

The NPS's own rule: Frutiger for structural/identity text, serif for content meant to be read. We follow this principle.

### Font Families

| CSS Variable | Stack | Role |
|---|---|---|
| `--font-np` / `--font-sans` | Frutiger → Cabin → system sans | Structural: headers, labels, buttons, navigation |
| `--font-serif` | Lora → Georgia → system serif | **Default body font**. Content: titles, descriptions, body text meant to be read |

**When to use which:**
- **Sans-serif (`--font-np`)**: Section header bars, eyebrow labels, category tags, status pills, buttons, navigation tabs, footer text, weather stat labels — anything that organizes or identifies
- **Serif (`--font-serif`)**: Card titles (park name, moon phase name, service names), descriptions, body paragraphs — anything the user actually reads as content

| Font File | Era | Notes |
|---|---|---|
| `frutiger.woff2` | Modern NPS (2001+) | Primary sans-serif, used in current NPS brochures |
| `nationalpark.woff2` | 2020s display face | Variable-weight, inspired by NPS signage (not official NPS) |
| `nps1935.woff2` | 1935 CCC era | Evokes hand-carved Depression-era park signs |
| `nps-signage-1945.woff2` | 1945 highway signs | Pre-Interstate highway signage style |
| Cabin (Google Fonts) | Fallback | Metric-compatible Frutiger substitute |
| Lora (Google Fonts) | Fallback | Serif for content text, substituting NPS Rawlinson |

### Type Scale

Use these sizes consistently. Avoid inventing new sizes.

| Role | Size | Weight | Example |
|---|---|---|---|
| **Site title** | `1.9rem` | 700 | "OV HOUSE" in black band |
| **Data value** | `1.65rem` | 700 | "72°F", "4.2 mph" |
| **Card/content title** | `1.15–1.2rem` | 700 | Park name, moon phase, service card name |
| **Section header bar** | `1.1rem` | 700 | "BOOKMARKS", "NIGHT SKY" |
| **Data value (text)** | `1.15rem` | 700 | "11h 42m" (day length) |
| **Body text** | `0.9–0.95rem` | 400 | Descriptions, paragraphs |
| **Label / metadata** | `0.85rem` | 600 | "Visible planets", stat labels, bird names |
| **Small label** | `0.8rem` | 600 | Footer text, chart captions, panel stat labels |
| **Eyebrow / category** | `0.68–0.72rem` | 600–700 | "BIRD ID", "CAMERAS", status pills |
| **Badge / micro** | `0.5–0.62rem` | 700 | "NEW" badge, detection counts |

### Capitalization Rules

**Use uppercase (`text-transform: uppercase`) for:**
- Section header bar titles ("BOOKMARKS", "NIGHT SKY")
- Eyebrow/category labels ("BIRD ID", "CAMERAS", "SUBTITLES")
- Status pills ("LOW", "MODERATE", "HIGH")
- Navigation buttons and tabs ("WEATHER STATION", "A–Z")
- Identification band location text
- Weather stat labels ("TEMPERATURE", "HUMIDITY")

**Use normal case for:**
- Card titles and content names (park names, moon phase, service names)
- Descriptions and body text
- Data values and units
- Links with readable text ("Visit NPS.gov")
- Supplementary metadata ("Visible planets", "62% illuminated")

**The rule**: Uppercase is for structural/organizational elements that label and categorize. Normal case is for content the user reads. This follows the actual NPS practice — park names on brochures are title case ("Acadia National Park"), not all-caps.

### Letter-Spacing

Three tiers only:

| Tier | Value | Use |
|---|---|---|
| **Wide** | `0.18–0.22em` | Eyebrows, category tags, tiny badges |
| **Medium** | `0.1–0.12em` | Section headers, buttons, navigation tabs |
| **None** | `0` (default) | All content text, titles, descriptions, links |

Never add letter-spacing to serif text or body text. Letter-spacing is only for uppercase sans-serif labels.

### Text Colors

Use the warm NPS palette via CSS custom properties defined in `:root`. Avoid hardcoded hex values — always use the semantic variables. Avoid neutral grays (#888, #999) — they clash with the warm brown tones.

| Role | Color | CSS Variable |
|---|---|---|
| **Primary text** | near-black (#333) | `var(--text-primary)` |
| **Secondary text** | warm dark gray (#4a4035) | `var(--text-secondary)` |
| **Muted text** | gray (#666) | `var(--text-muted)` |
| **Tertiary / metadata** | warm mid-gray | `var(--nps-brown-light)` (#6F4930) |
| **Disabled / empty state** | warm light gray | `var(--nps-warm-gray)` (#E0DDD8) |
| **Reversed (on dark bg)** | white/cream | `var(--nps-white)` or `var(--nps-cream)` |

### Color Coding (Overbars & Groups)

| Color | CSS Class | Meaning |
|---|---|---|
| Green (`--nps-green-dark`) | `.green` | Home & Automation |
| Copper (`--nps-copper`) | `.copper` | Media |
| Brown (`--nps-brown`) | `.brown` | Documents & Files |
| Blue (`--nps-blue-dark`) | `.blue` | Infrastructure |
| Red (`--nps-red`) | `.red` | Alerts / safety |
| Alert orange (`--nps-alert`) | `.alert-banner` | System notifications banner (`#FF8C00`) |

### Spacing & Layout

- **Grid gap**: `2px` between cards (tight, Unigrid-style)
- **Card padding**: `10–16px` — compact but readable
- **Section header margin**: `40px` top, `16px` bottom
- **Bottom-row cards**: two-column grid, stacks on mobile (<700px)
- **Inline weather section**: full-width in main content flow, `max-width: 1280px`, collapsible via `max-height` transition
- **Left multi-tab sidebar**: fixed left edge, 40px icon tab strip + 280px panel; z-index 85 (below header 100). Bottom edge stops at footer top (JS sets `bottom` to footer height)

### NPS Design System References

**Official NPS Sources:**
- [NPS Graphic Identity and Style Guides](https://www.nps.gov/subjects/hfc/nps-graphic-identity-and-style-guides.htm) — Harpers Ferry Center
- [A Brief History of the Unigrid](https://www.nps.gov/subjects/hfc/a-brief-history-of-the-unigrid.htm)
- [Unigrid Design Specifications (PDF)](https://npshistory.com/brochures/unigrid.pdf) — original 1977 Vignelli specs
- [HFC Editorial Style Guide](https://www.nps.gov/subjects/hfc/hfc-editorial-style-guide.htm)
- [NPS Arrowhead Artwork](https://www.nps.gov/subjects/hfc/arrowhead-artwork.htm)

**Typography History:**
- [NPS Rawlinson Roadway — Wikipedia](https://en.wikipedia.org/wiki/NPS_Rawlinson_Roadway) — typeface development, replacing Clarendon in 2001
- [Terminal Design: NPS Roadway](https://www.terminaldesign.com/customfonts/nps-roadway/) — the foundry that created NPS Rawlinson
- [Fonts In Use: US National Parks](https://fontsinuse.com/tags/975/us-national-parks)
- [Field Notes: "What Font is That?"](https://fieldnotesbrand.com/dispatches/what-font-is-that)
- [National Park Typeface](https://nationalparktypeface.com/) — the open-source display face we use

**Sign & Color Standards:**
- [NPS UniGuide Standards Manual (PDF)](https://cd3abd6beebec142023d-31d81c9257c2834bed6081c9f3253cbd.ssl.cf2.rackcdn.com/custom-signs/nps/national-park-service-uniguide-standards.pdf)
- [NPS UniGuide Color Standards (PDF)](https://www.generalstaff.org/BBOW/Colors/NPS_uniguide_standards_extracted_color.pdf)
- [NPS UniGuide Program — SEGD](https://segd.org/projects/nps-uniguide-program/)
- [Complete Guide to National Park Signs — Parks & Trips](https://parksandtrips.com/the-complete-guide-to-national-park-signs/)

**Design History:**
- [Best of Design: Vignelli NPS — Google Arts & Culture](https://artsandculture.google.com/story/best-of-design-vignelli-national-park-service/4wKi8PWDRfXQKQ)
- [Raising the Bar — NPCA](https://www.npca.org/articles/963-raising-the-bar)
- [Unigrids — Wikipedia](https://en.wikipedia.org/wiki/Unigrids)
- [Standards Manual: Parks](https://standardsmanual.com/products/parks)
- [Made in Figma: NPS Goes From Paper to Pixels](https://www.figma.com/blog/made-in-figma-the-national-park-service-goes-from-paper-to-pixels/)

## DNS & Reverse Proxy

### DNS (AdGuard — CT 101, 192.168.0.11)

| Rewrite | Target | Purpose |
|---------|--------|---------|
| `*.1701.me` | `192.168.0.30` | Wildcard — all `.1701.me` domains resolve locally to NPM, bypassing hairpin NAT |
| `weather.home` | `192.168.0.30` | Local `.home` domain → NPM |
| `auth.1701.me` | `192.168.0.30` | Authentik SSO (SSL cert 19 in NPM, proxy host #54) |

### NPM Proxy Hosts (CT 112, 192.168.0.30:81)

| Domain | Forward To | ID | SSL |
|--------|------------|-----|-----|
| `home.1701.me` | `192.168.0.179:8076` (HTTP) | 23 | Let's Encrypt (cert 18), Force SSL, HTTP/2 |
| `weather.home` | `192.168.0.179:8076` (HTTP) | 75 | None (internal only) |

### Request Flow (Local Network)

```
Browser → https://home.1701.me
  → AdGuard DNS: *.1701.me → 192.168.0.30
    → NPM: home.1701.me → 192.168.0.179:8076 (SSL termination at NPM)
      → nginx container (Authentik forward auth) → static files from page-output volume
```

## Scheduling

The generator uses a simple `while true; sleep 300` loop in entrypoint.sh instead of cron. This is intentional — cron inside Docker doesn't inherit env vars from `env_file`, which caused `KeyError` crashes. The sleep loop inherits Docker's env directly and logs to stdout (visible via `docker logs`).

```bash
# entrypoint.sh (complete)
#!/bin/bash
set -e
mkdir -p /output/fonts
cp -f /app/fonts/*.woff2 /output/fonts/ 2>/dev/null || true
echo "[$(date)] Starting trailhead generator (every 300s)..."
while true; do
    python3 /app/generate.py || echo "[$(date)] generate.py failed (exit $?)" >&2
    sleep 300
done
```

The `|| echo` prevents `set -e` from killing the loop if generate.py fails — it logs the error and retries in 5 minutes. `restart: unless-stopped` is the outer safety net.

## Operations

### Quick Code Change (no rebuild)

Source files are bind-mounted. To update generate.py or template.html:

```bash
# Copy updated files
scp generate.py template.html root@192.168.0.179:/mnt/docker/trailhead/

# Restart generator to pick up changes (web container stays up)
ssh root@192.168.0.179 "docker restart trailhead-generator"
```

No `docker compose build` needed — the bind mounts mean the container sees the new files immediately on restart.

### Full Rebuild & Redeploy

Only needed if Dockerfile, requirements.txt, or entrypoint.sh change:

```bash
# From Komodo (192.168.0.179)
cd /etc/komodo/stacks/trailhead
docker compose build --no-cache
docker compose up -d
```

### Check Status

```bash
# Container health
docker ps --filter name=trailhead

# Generator logs
docker logs trailhead-generator --tail 30

# Verify output freshness
docker exec trailhead-generator ls -la /output/index.html

# Test endpoints
curl http://192.168.0.179:8076/health
curl -s http://192.168.0.179:8076/ | grep -oE '\d+\.\d+°F'
```

### Force Immediate Regeneration

Click the **&#x21bb;** refresh button next to the "Updated" timestamp in the ident band. This POSTs to `/regen`, which triggers the generator within 5 seconds and reloads the page.

Or from CLI:
```bash
curl -X POST http://192.168.0.179:8076/regen
```

Or directly:
```bash
docker exec trailhead-generator python3 /app/generate.py
```

### Alert Banner

An orange notification banner below the ident band, controlled by `/mnt/docker/trailhead/alerts.json`. Max 2 rows, auto-hides when no alerts. Auto-expires based on the `expires` field.

**Format:**
```json
[
  {
    "message": "Download in progress — 50/756 (7%)",
    "type": "info",
    "expires": "2026-04-12T00:00:00"
  }
]
```

- **type**: `info` (blue dot), `warn` (copper dot), `error` (red dot), `success` (green dot)
- **expires**: ISO timestamp — alert auto-removed after this time
- **To clear all alerts**: write `[]` to the file
- Changes picked up on next 5-min generation cycle (or trigger a regen)

## Troubleshooting

### Containers Show "unhealthy"

**Check generator logs first:**
```bash
docker logs trailhead-generator --tail 20
```

**Common causes:**

| Error | Cause | Fix |
|-------|-------|-----|
| `KeyError: 'ECOWITT_APP_KEY'` | Missing env vars in .env file | Check `/mnt/docker/trailhead/.env` has all required keys |
| `Ecowitt error 40000: wind_speed_unitid must between 6 - 11` | Wrong v3 unit ID | Use IDs from the unit table above — v3 IDs differ from v2 |
| `Ecowitt error {code}: {msg}` | API auth or rate limit | Check .env keys, wait for rate limit reset |
| `BirdNET-Go unavailable` | BirdNET-Go container down | Check `docker ps` for birdnet-go on Komodo |
| `Radar download failed` | NWS outage or timeout | Non-fatal — page still generates, just no radar.gif |
| `NWS synopsis fetch failed` | NWS API outage or timeout | Non-fatal — synopsis bar hidden via `{% if synopsis %}` |

### Page Not Accessible via Domain

1. **Check DNS**: `dig weather.1701.me @192.168.0.11` should return `192.168.0.30`
2. **Check NPM**: `curl -H 'Host: weather.1701.me' http://192.168.0.30` should return the page
3. **Check container**: `curl http://192.168.0.179:8076/health` should return `ok`

### Charts Not Rendering

Charts are matplotlib PNGs generated server-side. Chart generation is wrapped in try-except with success tracking (`temp_chart_ok`, `wind_chart_ok` booleans). The template conditionally shows chart images only when generation succeeded (`{% if temp_chart_ok %}`), preventing broken image icons.

If charts are missing from the page:
- Check generator logs for matplotlib errors or "chart generation failed" warnings
- Verify history API returns data (may be empty if station was offline)
- Charts require the `Agg` backend (`matplotlib.use('Agg')`) — no display server needed

### nginx Returns 502

The web container starts only after the generator is healthy (`depends_on: condition: service_healthy`). If the generator never becomes healthy, the web container won't start. Fix the generator issue first.

## Lessons Learned

1. **Ecowitt API v3 unit IDs are NOT the same as v2.** The v2 docs say wind_speed unit 4 = mph, but v3 says unit 4 is invalid (valid range 6-11, where 9 = mph). Always verify against v3 docs or test empirically.

2. **Don't use cron inside Docker.** Cron spawns jobs with a clean environment that doesn't inherit Docker `ENV` or `env_file` vars. Forwarding env via `/etc/environment` is fragile. A simple `while true; sleep N` loop in the entrypoint inherits env directly and is the standard Docker-idiomatic pattern for periodic tasks.

3. **Ecowitt API always returns HTTP 200**, even on error. Must check `response['code'] == 0` before accessing data. On error, `data` is `[]`, not a dict — accessing dict keys on a list will raise a different error than expected.

4. **BirdNET-Go `is_new_species`** is a key that's absent, not false, when the species isn't new. Use `.get()` in templates.

5. **python:3.12-slim, not Alpine**, for matplotlib. Alpine uses musl libc and has no pre-built matplotlib wheels — building from source takes 10+ minutes. Debian slim has wheels available.

6. **Use `127.0.0.1`, not `localhost`, in Docker healthchecks.** Alpine-based containers (like nginx:alpine) resolve `localhost` to `::1` (IPv6) when no server is listening on IPv6, causing `wget --spider` to fail. Using `127.0.0.1` forces IPv4.

7. **NWS AFD sections are separated by `&&`**, not newlines or `$`. The regex must use `&&` as a section terminator. The `.SYNOPSIS...` header uses literal `...` (three dots) as part of the NWS format.

8. **`letter-spacing` breaks `justify-content: center`.** Letter-spacing adds trailing space after the last character, making centered text appear shifted left. Override `letter-spacing: 0` when precise centering matters (e.g., compact link buttons in the sidebar).

9. **Fixed-position overlays don't mix well with expandable page content.** The bird drawer was originally `position: fixed; bottom: 0` but overlapped collapsible bookmark sections. Moving it to normal document flow (removing fixed positioning entirely) and using `pointer-events: none/auto` for click-through solved the overlap issue cleanly.

10. **`datetime` objects are not JSON serializable.** The launch cache was logging `Object of type datetime is not JSON serializable` every 5 minutes. Fixed by excluding `sort_time` from the cached dict and storing it separately as an ISO string (`sort_time_iso`), then restoring it with `datetime.fromisoformat()` on cache read.

11. **Centralize colors as CSS custom properties early.** Hardcoded hex values like `#4a4035` and `#666` appeared in 13+ places. Adding semantic variables (`--text-primary`, `--text-secondary`, `--text-muted`, `--sidebar-bg`, `--sidebar-bg-hover`) to `:root` and replacing all hardcoded values makes future theming trivial and prevents color drift.

12. **Duplicate CSS variables cause confusion.** `--nps-gold` was identical to `--nps-copper` and `--nps-green-light` was identical to `--nps-green-mid`. Removed the duplicates and updated all references to use the canonical names.

13. **Run containers as non-root.** The generator initially ran as root (Docker default). Adding `USER appuser` to the Dockerfile required also pre-creating `/output` with correct ownership, setting `MPLCONFIGDIR=/tmp/matplotlib` (matplotlib needs a writable config dir), and fixing volume file ownership on first deploy (`docker exec -u root ... chown`).

14. **Jinja2 does NOT autoescape by default.** `Environment(loader=FileSystemLoader('/app'))` renders all `{{ var }}` unescaped. Must explicitly add `autoescape=select_autoescape(default_for_string=True, default=True)`. Unicode (emoji) passes through fine — autoescape only escapes `<>&"'`.

---

## Access Control (Authentik SSO)

Per-user access filtering using Authentik SSO forward auth. A single `index.html` is generated every 5 minutes with ALL cards. Client-side JavaScript filters cards based on the authenticated user's group memberships. The main content (weather, charts, birds, sky, park, synopsis) is identical for all users. The sidebar supports multiple tabs (Bookmarks, Cameras) with per-card group-based access control.

### Auth Architecture

```
Browser → NPM (192.168.0.30) → trailhead-web (:8076)
  nginx auth_request → Authentik embedded outpost (192.168.0.179:9000)
    401 → redirect to http://home.1701.me/outpost.goauthentik.io/start (hardcoded in nginx; NPM upgrades to HTTPS)
    200 → auth_request_set captures $authentik_username
         → sub_filter injects username into TWO placeholders (dropdown + JS var)
         → sub_filter injects $network_type (Local/Remote) from X-Forwarded-For
         → try_files /index.html (single file for all users)
         → JS reads TRAILHEAD_USERNAME + TRAILHEAD_USER_GROUPS (case-insensitive lookup)
         → JS hides cards where data-access doesn't match user's groups
```

**Domain routing**: AdGuard DNS (192.168.0.11) rewrites `*.1701.me → 192.168.0.30` (NPM reverse proxy). NPM proxies `home.1701.me → 192.168.0.179:8076`. Users must access via `home.1701.me`, not the IP:port directly.

### Access Groups

Each card in `trailhead.yaml` has an optional `access` field with a list of access tags:

```yaml
- id: mealie
  title: Mealie
  access:
    - apps-family
- id: grafana
  title: Grafana
  access:
    - apps-friends
```

Access tags currently used:
- `apps-family` — Mealie, Tandoor, Immich (family-only apps)
- `apps-friends` — BirdNET, Grafana, Paperless, Stirling PDF (shared with friends)
- `camera` — Driveway camera (cameras tab)

Cards without an `access` field are visible to all authenticated users. JS client-side filtering hides cards where the user's groups (from `TRAILHEAD_USER_GROUPS`) don't include any of the card's access tags. The lookup is **case-insensitive** (`TRAILHEAD_USERNAME.toLowerCase()`).

### Sidebar Tabs

| Tab | Content | Source |
|-----|---------|--------|
| Bookmarks | 4 groups, ~36 service cards | `trailhead.yaml → tabs[bookmarks].groups` |
| Cameras | Camera snapshot cards | `trailhead.yaml → tabs[cameras].cards` |

Empty tabs (all cards hidden) are automatically hidden by JS.

### Authentik Configuration

Configured via API. Components created:

- **Proxy Provider**: `trailhead` — forward auth single application, external host `https://home.1701.me`
- **Application**: `Trailhead`, slug `trailhead`, pk `4c8c0fb6-c9ab-4ca2-aa19-4a17e4a21087`
  - `launch_url`: `http://home.1701.me` (must match external host domain, not IP:port)
- **Embedded outpost**: `authentik_host` = `https://auth.1701.me`, `authentik_host_browser` = `https://auth.1701.me`
- **Brand**: UUID `e137649b-f669-43e7-abdf-6e52a6b7e952` (default brand, customized)
- **Authentication flow**: `default-authentication-flow` — title "Welcome, please login", identification + password on one page
- **API token**: `BVcngz0VAdh81uKFTOd93NHHD2sXF5624hml3LLFuYTSQMYyd7vA8pOLDLgx` (for programmatic brand/flow changes)
- **Users**: `alec` (type: `external`, `is_superuser: true`), `akadmin` (default admin, type: `internal`)
  - `alec` is set to `external` so that `RootRedirectView` redirects to `default_application` (Trailhead) instead of the admin dashboard when `next=/` is hit after logout. `is_superuser` remains `true`, so admin UI at `/if/admin/` is still accessible.

To add a new user:
1. Create user in Authentik admin: http://192.168.0.179:9000/if/admin/#/identity/users
2. Add username to the appropriate groups in `trailhead.yaml` under `access_groups`
3. Rebuild: `cd /etc/komodo/stacks/trailhead && docker compose build generator && docker compose up -d`

### Login Page Branding

The Authentik login page is styled to match the NPS design of the Trailhead homepage. Branding is applied via the Authentik Brand API (`/api/v3/core/brands/{uuid}/`).

#### Brand Settings

| Field | Value |
|-------|-------|
| `branding_title` | Trailhead |
| `branding_logo` | `/static/dist/assets/icons/trailhead-logo.svg` |
| `branding_default_flow_background` | `/static/dist/assets/images/blank.png` |
| `branding_custom_css` | NPS-themed CSS (see below) |

#### TRAILHEAD Logo

SVG text logo at `/web/dist/assets/icons/trailhead-logo.svg` inside the `authentik-server` container. Also backed up at `/mnt/docker/authentik/media/custom/trailhead-logo.svg` on Komodo host.

**Note**: This file lives inside the container image (not a volume mount). It will be lost on container rebuild/update and must be re-copied:
```bash
docker cp /mnt/docker/authentik/media/custom/trailhead-logo.svg authentik-server:/web/dist/assets/icons/trailhead-logo.svg
```

#### Flow Configuration

The identification stage (`default-authentication-identification`) has `password_stage` set to `default-authentication-password`, which shows both username and password fields on a single page.

The "Login to continue to Trailhead." subtitle was suppressed by editing `/web/dist/chunks/XROP4FSD.js` inside the container (changed `this.challenge.applicationPre?` to `false?`). This edit is lost on container rebuild.

The logout page (`/web/dist/src/flow/providers/chunks/52MQAQ3X.js`) was modified to auto-redirect to `http://home.1701.me/logged-out` using `connectedCallback()` (fires before `render()`). The `render()` method shows a "Logging out..." message as a brief fallback while the redirect executes. Uses `window.location.replace()` to avoid a back-button return to the session-end page. Backed up at `/mnt/docker/authentik/media/custom/52MQAQ3X.js`. This edit is lost on container rebuild.

#### Custom CSS

The brand CSS uses direct PatternFly class selectors (Authentik injects brand CSS into the Shadow DOM):

```css
@import url("https://fonts.googleapis.com/css2?family=Cabin:wght@400;600;700&family=Lora:ital,wght@0,400;0,600;0,700;1,400;1,600&display=swap");

:root {
  --ak-font-family-sans-serif: "Cabin", sans-serif !important;
  --ak-font-family-heading: "Cabin", sans-serif !important;
  --pf-global--primary-color--100: #5C462B !important;   /* NPS brown buttons */
  --pf-global--primary-color--200: #C56C39 !important;   /* Copper accent */
  --ak-global--background-image: none !important;
}

body { background-color: #F5F5F0 !important; }            /* Cream page bg */

.pf-c-login__main {                                       /* White card */
  background-color: #FFFFFF !important;
  border-bottom: 3px solid #6F4930 !important;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
}

.pf-c-title { color: #333333 !important; }                /* Dark text */
.pf-c-form__label-text { color: #333333 !important; opacity: 1 !important; }
.pf-c-form-control {                                       /* Input fields */
  background-color: #FFFFFF !important;
  border: 1px solid #D4C4A8 !important;
  color: #333333 !important;
}
.pf-c-button.pf-m-block,
.pf-c-button.pf-m-primary {                               /* Brown button */
  background-color: #5C462B !important;
  color: #FFFFFF !important;
}
.pf-c-list.pf-m-inline { visibility: hidden !important; } /* Hide footer */
.pf-c-login__main-footer-band { background-color: #FFFFFF !important; }
a { color: #C56C39 !important; }                           /* Copper links */
```

#### Things Lost on Container Rebuild

After an Authentik update/rebuild, re-apply:
1. **Logo SVG**: `docker cp /mnt/docker/authentik/media/custom/trailhead-logo.svg authentik-server:/web/dist/assets/icons/trailhead-logo.svg`
2. **Subtitle suppression**: Re-edit `XROP4FSD.js` (the chunk filename may change between versions)
3. **Logout page redirect**: `docker cp /mnt/docker/authentik/media/custom/52MQAQ3X.js authentik-server:/web/dist/src/flow/providers/chunks/52MQAQ3X.js` (chunk filename may change between versions — search for `ak-stage-session-end` to find the right file)
4. **Brand CSS + settings**: Persisted in the database, survives rebuilds
5. **Flow title + password_stage**: Persisted in the database, survives rebuilds

### Access Control Files

| File | Purpose |
|------|---------|
| `trailhead.yaml` | Access groups + tabs with per-card access fields |
| `generate.py` | Renders single `index.html` with all cards + user_groups JSON (lowercase keys) |
| `template.html` | Multi-tab sidebar, data-access attributes, JS filtering, Local/Remote badge |
| `nginx.conf` | Authentik forward auth, network type detection, `sub_filter_once off`, `try_files /index.html` |
| `logged-out.html` | Static "You've been logged out" page with 5s countdown + auto-redirect (no auth) |
| `compose.yaml` | Generator + nginx services, healthcheck on `index.html` |

### nginx.conf — Auth Details

#### Network Type Detection

A `map` block classifies clients as Local or Remote based on the `X-Forwarded-For` header set by NPM:

```nginx
map $http_x_forwarded_for $network_type {
    ~^192\.168\.  Local;
    ~^10\.        Local;
    default       Remote;
}
```

The `$network_type` variable is injected into HTML via `sub_filter`:

```nginx
sub_filter '<!--AUTHENTIK_USERNAME-->' $authentik_username;
sub_filter '<!--NETWORK_TYPE-->' $network_type;
sub_filter_once off;    # Multiple replacements: username (dropdown + JS var) + network type
try_files /index.html =404;
```

#### Auth Redirect (Hardcoded Domain)

The `@goauthentik_proxy_signin` location **must** hardcode `home.1701.me`:

```nginx
location @goauthentik_proxy_signin {
    internal;
    add_header Set-Cookie $auth_cookie;
    return 302 http://home.1701.me/outpost.goauthentik.io/start?rd=http://home.1701.me$request_uri;
}
```

**Why hardcoded**: If the user accesses via IP:port (`192.168.0.179:8076`) instead of `home.1701.me`, using `$http_host` would produce a redirect URL with the wrong domain. The outpost compares the redirect URI against `external_host` (`https://home.1701.me`) and rejects mismatches with "redirect URI did not contain external host". This caused callback failures (HTTP 400), session mismatches, and users ending up at the Authentik dashboard instead of Trailhead.

**Note**: The nginx.conf redirects use `http://` but NPM's Force SSL upgrades all external requests to HTTPS. The internal redirect from nginx to Authentik outpost stays HTTP (container-to-container on the same host).

#### Logout

Logout clears the proxy cookie and redirects to the OIDC end-session endpoint:

```nginx
location = /logout {
    add_header Set-Cookie 'authentik_proxy_ee210d03=; Path=/; Max-Age=0' always;
    return 302 http://192.168.0.179:9000/application/o/trailhead/end-session/?post_logout_redirect_uri=http://home.1701.me/;
}
```

The OIDC end-session endpoint triggers the `default-provider-invalidation-flow`, which has a **User Logout Stage** (`default-invalidation-logout`) at order 0. This stage calls `logout(request)` to destroy the Authentik server session.

**Known Authentik limitation** (GitHub #10430, #4248): The User Logout Stage destroys the Django session, which also destroys `SESSION_KEY_PLAN` containing the flow plan context. This means `post_logout_redirect_uri` is lost after session destruction. The Authentik SPA detects the session loss and redirects to the auth flow with `next=/`, which after re-login leads to the Authentik dashboard instead of Trailhead.

**Workaround — dual-path redirect:**

The `52MQAQ3X.js` file (session-end stage component) was modified to redirect to a static "logged out" page on Trailhead before the SPA's session-loss detection kicks in. As a safety net, user `alec` was changed to `external` type so `RootRedirectView` redirects to `default_application` (Trailhead) if the SPA redirect wins the race.

**Path A — JS redirect wins (primary):**
```
Logout → cookie cleared → OIDC end-session → invalidation flow
  → User Logout Stage kills session → 52MQAQ3X.js connectedCallback()
  → window.location.replace("http://home.1701.me/logged-out")
  → static "You've been logged out" page (5s countdown)
  → auto-redirect to home.1701.me → outpost OAuth → login → Trailhead
```

**Path B — SPA session-loss redirect wins (safety net):**
```
Logout → session killed → SPA detects session loss
  → redirects to auth flow with next=/ → user logs in
  → next=/ → RootRedirectView → external user type
  → redirect to default_application launch_url → home.1701.me → Trailhead
```

Both paths end at Trailhead.

#### Logged-Out Page

A static NPS-styled page served without auth at `/logged-out`:

```nginx
location = /logged-out {
    add_header X-Content-Type-Options "nosniff" always;
    alias /error-pages/logged-out.html;
}
```

The page shows "You've Been Logged Out" with a 5-second countdown timer and auto-redirect to `http://home.1701.me/`. A "Log Back In Now" button is available as an immediate fallback. The file is mounted into the container via `compose.yaml`:

```yaml
- /mnt/docker/trailhead/logged-out.html:/error-pages/logged-out.html:ro
```

**Why not other approaches**:
- `post_logout_redirect_uri` is lost when the User Logout Stage destroys the session (known Authentik bug)
- `?next=` on invalidation flows rejects external URLs ("Invalid next URL")
- The outpost `/sign_out` endpoint doesn't work for forward-auth mode (designed for proxy mode only)
- Brand CSS can't style the `ak-stage-session-end` component (shadow DOM doesn't adopt brand stylesheets)

#### Other Critical nginx Settings

- **`absolute_redirect off`** — Required because nginx inside Docker listens on :80 but is exposed as :8076.
- **`Host home.1701.me`** (hardcoded in outpost location) — The Authentik outpost routes by host matching. Internal DNS rewrite in AdGuard resolves `*.1701.me` → `192.168.0.30` (reverse proxy).
- **Cookie passthrough** — `auth_request_set $auth_cookie` + `add_header Set-Cookie $auth_cookie` on every auth-protected location.
- **`$authentik_username` from `$upstream_http_x_authentik_username`** — Reads from outpost response headers, NOT client request headers. Cannot be spoofed.

### Client-Side Filtering (JS)

```javascript
var TRAILHEAD_USER_GROUPS = {"alec": ["admin","media","family"], ...};  // embedded at generation (lowercase keys)
var TRAILHEAD_USERNAME = '<!--AUTHENTIK_USERNAME-->';  // replaced by nginx sub_filter

// On page load:
// 1. Look up user's groups using TRAILHEAD_USERNAME.toLowerCase() (case-insensitive)
// 2. Hide cards where data-access doesn't include any of user's groups
// 3. Hide empty group labels
// 4. Hide empty sidebar tabs
```

#### Network Badge

The template displays a "Local" or "Remote" badge in the header based on the `$network_type` variable injected by nginx. The badge is styled with green (Local) or orange (Remote) colors. This is purely informational — access control is not affected by network location.

### User Menu

A user icon in the black band header opens a dropdown with:

- **Username display** — injected at serve time by nginx `sub_filter`
- **Change Password** — links to Authentik user settings (`http://192.168.0.179:9000/if/user/`)
- **Log Out** — hits `/logout` which clears proxy cookie and redirects to Authentik invalidation flow

### Access Control Security Notes

- **Header spoofing safe**: `$authentik_username` comes from `$upstream_http_` (outpost response only)
- **Cards in source**: All cards are in the HTML source. Any authenticated user could view-source and see all URLs. This is fine because each service has its own auth — the access control here is UI cleanliness, not a security boundary.
- **Static assets protected**: Camera snapshot (`driveway.jpg`) requires auth
- **Logged-out page open**: `/logged-out` has no auth (static page shown after session destruction)
- **Health check open**: `/health` has no auth (required for Docker healthcheck)
- **Domain enforcement**: Auth redirect hardcodes `home.1701.me` to prevent OAuth callback failures when accessed via IP:port

### Access Control Troubleshooting

#### User sees wrong bookmarks
Check `access_groups` in `trailhead.yaml`. The user must be listed in a group that matches the card's `access` field. Usernames are matched case-insensitively. After changes, rebuild the generator.

#### Infinite login loop
Cookie passthrough is missing or broken. Ensure `auth_request_set $auth_cookie $upstream_http_set_cookie` and `add_header Set-Cookie $auth_cookie` are present on every auth-protected location block.

#### Post-login redirects to Authentik dashboard (not Trailhead)
**After normal login**: The user likely accessed via IP:port (`192.168.0.179:8076`) instead of `home.1701.me`. The OAuth callback fails because the redirect URI doesn't match `external_host`. Check:
1. `@goauthentik_proxy_signin` has hardcoded `home.1701.me` (not `$http_host`)
2. Authentik application `launch_url` is `http://home.1701.me` (not the IP:port)
3. User bookmarks point to `http://home.1701.me` (not the IP)

**After logout + re-login**: This is a known Authentik limitation (GitHub #10430, #4248). The User Logout Stage destroys the Django session including the flow plan, so `post_logout_redirect_uri` is lost. The SPA redirects to the auth flow with `next=/`, and after login `RootRedirectView` sends the user to the dashboard. The workaround has two parts:
1. `52MQAQ3X.js` redirects to `/logged-out` before the SPA can detect the session loss (primary path)
2. User `alec` is set to `external` type so `RootRedirectView` redirects to `default_application` (Trailhead) when `next=/` is hit (safety net)

If this stops working, check:
- `52MQAQ3X.js` is deployed in the Authentik container (may need re-copying after update)
- User `alec` is still `external` type with `is_superuser: true`
- Brand `default_application` is set to Trailhead (pk `4c8c0fb6-c9ab-4ca2-aa19-4a17e4a21087`)

#### Logout 502 error
The outpost `/sign_out` endpoint has a known bug (v2025.12.1) where it returns 502 when the browser has a valid proxy session cookie. The current workaround redirects to the invalidation flow directly instead. Do NOT attempt to proxy to `/outpost.goauthentik.io/sign_out` — it won't work.

#### 502 or 500 errors (general)
Authentik may be down or the outpost may not have the provider assigned. Check:
```bash
docker logs authentik-server --tail 20
curl -s -o /dev/null -w '%{http_code}' -H 'Host: home.1701.me' http://192.168.0.179:9000/outpost.goauthentik.io/auth/nginx
```
