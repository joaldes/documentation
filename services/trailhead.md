# Trailhead — Weather & Wildlife Dashboard

**Last Updated**: 2026-02-27
**Related Systems**: Komodo (CT 128), BirdNET-Go, Ecowitt Weather Station, Frigate NVR, AdGuard (CT 101), NPM (CT 112)

## Summary

A static weather dashboard styled after the National Park Service design system. A Python generator fetches live weather data from an Ecowitt station, bird detections from BirdNET-Go, sun/moon events via the astral library, NWS radar imagery, a Frigate camera snapshot, visible planet data, NWS forecast synopsis, and a daily NPS park — every 5 minutes. It renders a Jinja2 HTML template with matplotlib charts and serves the result through nginx. The header displays a live JavaScript clock. Runs as a Docker Compose stack on Komodo.

Previously called "neighborhood-page" — renamed to "trailhead" on 2026-02-27.

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
│  │    ├─ NWS AFD/TWC     → forecast synopsis (1h TTL)  │  │
│  │    ├─ Frigate API     → driveway camera snapshot    │  │
│  │    ├─ N2YO API        → ISS pass predictions        │  │
│  │    ├─ Launch Library  → Vandenberg launches (1h TTL) │  │
│  │    ├─ NPS API         → park of the day (daily TTL) │  │
│  │    ├─ matplotlib      → temp + wind 24h charts      │  │
│  │    └─ Jinja2 render   → /output/index.html          │  │
│  └─────────────────────────────────────────────────────┘  │
│         │ writes to                                       │
│         ▼                                                 │
│  [ trailhead_page-output named volume ]                   │
│    /output/index.html           (rendered page)           │
│    /output/temp-chart.png       (24h temperature chart)   │
│    /output/wind-chart.png       (24h wind speed chart)    │
│    /output/radar.gif            (NWS KEMX radar loop)     │
│    /output/driveway.jpg         (Frigate camera snapshot) │
│    /output/nps_parks_cache.json (daily park cache)        │
│    /output/launch_cache.json    (1h launch cache)         │
│    /output/synopsis_cache.json  (1h NWS synopsis cache)   │
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
| astral (Python lib) | Local calculation | Sun events + moon phase/illumination | None (every 5 min) |
| NWS KEMX | HTTPS | Radar loop GIF (Tucson region) | None (every 5 min) |
| NWS AFD/TWC | HTTPS | Area Forecast Discussion synopsis | 1 hour |
| Frigate (local) | HTTP | Driveway camera snapshot + today's event count | None (every 5 min) |
| N2YO API | HTTPS | Next visible ISS pass | None (every 5 min) |
| Launch Library 2 | HTTPS | Next Vandenberg launch (non-Starlink) | 1 hour |
| NPS API | HTTPS | Park of the day (name, description, image) | Daily |

## Access

| Method | URL |
|--------|-----|
| Direct IP | `http://192.168.0.179:8076` |
| Local domain | `http://weather.home` |
| External domain | `http://weather.1701.me` |
| Health check | `http://192.168.0.179:8076/health` |

## File Layout

### On Komodo (192.168.0.179)

```
/mnt/docker/trailhead/
├── .env                 # API keys + coordinates (loaded by compose env_file)
├── .dockerignore        # Excludes output/ and nginx.conf from build
├── Dockerfile           # python:3.12-slim + matplotlib
├── entrypoint.sh        # Font copy + sleep loop (runs generate.py every 5 min)
├── generate.py          # Main generator script (~500 lines)
├── template.html        # Jinja2 HTML template (~1780 lines, NPS design)
├── requirements.txt     # Python dependencies
├── nginx.conf           # Cache headers + health endpoint
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
├── index.html           # Rendered HTML page
├── temp-chart.png       # 24h temperature line chart
├── wind-chart.png       # 24h wind speed + gust chart
├── radar.gif            # NWS KEMX radar loop
├── driveway.jpg         # Frigate camera snapshot
├── nps_parks_cache.json # Daily park cache (avoids repeated API calls)
├── launch_cache.json    # 1h Vandenberg launch cache
├── synopsis_cache.json  # 1h NWS synopsis cache
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

### Docker Compose

- **Port**: 8076
- **Memory limits**: Generator 512MB, nginx 128MB
- **Health checks**:
  - Generator: `find /output/index.html -mmin -20` (file updated within 20 min, covers 5-min interval with margin)
  - Web: `wget --spider http://127.0.0.1:80/health` (uses 127.0.0.1, not localhost — see Lessons Learned)
- **Logging**: json-file driver, max 10MB x 3 files per container
- **Restart policy**: `unless-stopped`
- **Network**: Isolated `page-net` bridge
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

### History Endpoint

`GET https://api.ecowitt.net/api/v3/device/history?cycle_type=5min`

Returns dict of `{unix_timestamp_string: value_string}` per metric, ~288 points per 24h window.

```python
data['outdoor']['temperature']['list']
# → {"1771857600": "49.4", "1771857900": "49.2", ...}
```

Today's high/low are derived as `max()`/`min()` of the temperature history values — there is no dedicated realtime high/low endpoint.

## NWS Synopsis (AFD)

The NWS Area Forecast Discussion (AFD) synopsis is a short paragraph summarizing the weather outlook for the Tucson region. Fetched from the NWS API (no key needed), cached for 1 hour.

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

Rendered as a left-aligned static text block on a warm gray background (`var(--nps-warm-gray)`) above the Night Sky / Park row. Large italic serif font (1.15rem) for the forecast text. Small uppercase sans-serif attribution link to the [NWS Tucson AFD page](https://forecast.weather.gov/product.php?site=TWC&issuedby=TWC&product=AFD). Hidden if API fails (`{% if synopsis %}`).

**Note**: A scrolling ticker version (`.synopsis-ticker-*` CSS) is preserved in the template but unused — available for future reuse.

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

- **Black band header** with white arrowhead logo
- **Semi-transparent black identification band** (matching NPS website style) with sunrise/sunset and current temperature
- **Left bookmark sidebar**: fixed-position left-edge panel with dark background (`#3D3D3C`, matching the ident band's computed color). A 40px dark tab strip with vertical "Bookmarks" label expands to a 280px scrolling panel with a black header bar. 40 service bookmark cards across 4 groups — Home & Automation, Media, Documents & Files, Infrastructure. Cards are compact horizontal rows: title/category + Local/Remote links stacked vertically in a fixed-width column (color-coded overbars removed for cleaner look). White card backgrounds on dark panel surround. Group labels are sticky at the top while scrolling. Includes A-Z/Grouped toggle. Auto-opens on screens wider than 900px; click outside to close. On mobile (≤700px), transforms to a bottom-anchored tab expanding upward.
- **NWS Synopsis block**: left-aligned italic serif forecast text (1.15rem) on a warm gray background. Attribution links to the NWS Tucson AFD page. Hidden gracefully if the NWS API is unavailable. A scrolling ticker variant (CSS preserved but unused) is available for future use.
- **Night Sky + Park of the Day**: two side-by-side cards at the bottom of the page below bookmarks. Night Sky shows current moon phase (emoji + name + illumination %), visible planets as tags, and next sky event (ISS pass or Vandenberg launch with twilight visibility indicator). Park of the Day shows a different NPS park each day with photo, description, and link (cached daily via NPS API).
- **Right-side collapsible drawer** with 4 tabs:
  - Weather Station: all 12 metric cells
  - 24-Hour Charts: temperature and wind/gust line charts
  - Radar: NWS KEMX radar loop GIF
  - Camera: Frigate driveway snapshot (links to frigate.home) + today's event count
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
| `--font-serif` | Lora → Georgia → system serif | Content: titles, descriptions, body text meant to be read |

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

Use the warm NPS palette. Avoid neutral grays (#666, #888, #999) — they clash with the warm brown tones.

| Role | Color | Hex |
|---|---|---|
| **Primary text** | near-black | `--nps-black` (#000) or `#333` |
| **Secondary text** | warm dark gray | `#4a4035` |
| **Tertiary / metadata** | warm mid-gray | `#6a5a4a` or `--nps-brown-light` (#6F4930) |
| **Disabled / empty state** | warm light gray | `--nps-warm-gray` (#E0DDD8) |
| **Reversed (on dark bg)** | white/cream | `--nps-white` or `--nps-cream` |

### Color Coding (Overbars & Groups)

| Color | CSS Class | Meaning |
|---|---|---|
| Green (`--nps-green-dark`) | `.green` | Home & Automation |
| Copper (`--nps-copper`) | `.copper` | Media |
| Brown (`--nps-brown`) | `.brown` | Documents & Files |
| Blue (`--nps-blue-dark`) | `.blue` | Infrastructure |
| Red (`--nps-red`) | `.red` | Alerts / safety (unused currently) |

### Spacing & Layout

- **Grid gap**: `2px` between cards (tight, Unigrid-style)
- **Card padding**: `10–16px` — compact but readable
- **Section header margin**: `40px` top, `16px` bottom
- **Bottom-row cards**: two-column grid, stacks on mobile (<700px)
- **Right side drawer**: fixed right edge, `min(620px, calc(100vw - 60px))` wide
- **Left bookmark sidebar**: fixed left edge, 40px tab + 280px panel; z-index 85 (below weather drawer 90, header 100)

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

### NPM Proxy Hosts (CT 112, 192.168.0.30:81)

| Domain | Forward To | ID |
|--------|------------|-----|
| `weather.1701.me` | `192.168.0.179:8076` (HTTP) | 74 |
| `weather.home` | `192.168.0.179:8076` (HTTP) | 75 |

Both have block-exploits enabled, no SSL (internal only).

### Request Flow (Local Network)

```
Browser → weather.1701.me
  → AdGuard DNS: *.1701.me → 192.168.0.30
    → NPM: weather.1701.me → 192.168.0.179:8076
      → nginx container → static files from page-output volume
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

```bash
docker exec trailhead-generator python3 /app/generate.py
```

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

Charts are matplotlib PNGs generated server-side. If missing:
- Check generator logs for matplotlib errors
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
