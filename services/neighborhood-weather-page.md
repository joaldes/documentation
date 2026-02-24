# Neighborhood Weather & Wildlife Page

**Last Updated**: 2026-02-24
**Related Systems**: Komodo (CT 128), BirdNET-Go, Ecowitt Weather Station, AdGuard (CT 101), NPM (CT 112)

## Summary

A static weather dashboard for the neighborhood, styled after the National Park Service design system. A Python generator fetches live weather data from an Ecowitt station, bird detections from BirdNET-Go, sun events via the astral library, and NWS radar imagery every 5 minutes. It renders a Jinja2 HTML template with matplotlib charts and serves the result through nginx. The header displays a live JavaScript clock. Runs as a Docker Compose stack on Komodo.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Komodo Stack: neighborhood-page (CT 128, 192.168.0.179) │
│                                                          │
│  ┌─ generator (python:3.12-slim) ─────────────────────┐  │
│  │  entrypoint.sh:                                     │  │
│  │    1. Copy fonts to /output/fonts/                  │  │
│  │    2. while true: run generate.py, sleep 300        │  │
│  │                                                     │  │
│  │  generate.py (every 5 min via sleep loop):          │  │
│  │    ├─ Ecowitt API v3  → current weather + 24h hist  │  │
│  │    ├─ BirdNET-Go API  → today's bird detections     │  │
│  │    ├─ astral library  → dawn/sunrise/sunset/dusk    │  │
│  │    ├─ NWS KEMX        → radar loop GIF              │  │
│  │    ├─ matplotlib      → temp + wind 24h charts      │  │
│  │    └─ Jinja2 render   → /output/index.html          │  │
│  └─────────────────────────────────────────────────────┘  │
│         │ writes to                                       │
│         ▼                                                 │
│  [ page-output named volume ]                             │
│    /output/index.html      (rendered page)                │
│    /output/temp-chart.png  (24h temperature chart)        │
│    /output/wind-chart.png  (24h wind speed chart)         │
│    /output/radar.gif       (NWS KEMX radar loop)          │
│    /output/fonts/*.woff2   (NPS typefaces)                │
│         │ read by                                         │
│         ▼                                                 │
│  ┌─ web (nginx:alpine) ── port 8076 ──────────────────┐  │
│  │  Static file server with cache headers              │  │
│  │  HTML: no-cache | PNG/GIF: 5min | fonts: 1 year     │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### Data Flow

| Source | Protocol | Data | Update Frequency |
|--------|----------|------|-----------------|
| Ecowitt API v3 (realtime) | HTTPS | Temperature, humidity, wind, pressure, UV, PM2.5, rain | Every 5 min |
| Ecowitt API v3 (history) | HTTPS | 24h rolling temperature + wind speed/gust series | Every 5 min |
| BirdNET-Go (local) | HTTP | Today's detected bird species (top 20) | Every 5 min |
| astral (Python lib) | Local calculation | Dawn, sunrise, noon, sunset, dusk, day length | Every 5 min |
| NWS KEMX | HTTPS | Radar loop GIF (Tucson region) | Every 5 min |

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
/mnt/docker/neighborhood-page/
├── .env                 # API keys + coordinates (loaded by compose env_file)
├── .dockerignore        # Excludes output/ and nginx.conf from build
├── Dockerfile           # python:3.12-slim + matplotlib
├── entrypoint.sh        # Font copy + sleep loop (runs generate.py every 5 min)
├── generate.py          # Main generator script (~280 lines)
├── template.html        # Jinja2 HTML template (~1450 lines, NPS design)
├── requirements.txt     # Python dependencies
├── nginx.conf           # Cache headers + health endpoint
└── fonts/
    ├── frutiger.woff2
    ├── nationalpark.woff2
    ├── nps1935.woff2
    └── nps-signage-1945.woff2

/etc/komodo/stacks/neighborhood-page/
└── compose.yaml         # Docker Compose (generator + nginx)
```

### Generated Output (inside container volume)

```
/output/
├── index.html           # Rendered HTML page
├── temp-chart.png       # 24h temperature line chart
├── wind-chart.png       # 24h wind speed + gust chart
├── radar.gif            # NWS KEMX radar loop
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

### Docker Compose

- **Port**: 8076 (port 8075 is taken by fragments-web)
- **Memory limits**: Generator 512MB, nginx 128MB
- **Health checks**:
  - Generator: `find /output/index.html -mmin -20` (file updated within 20 min, covers 5-min interval with margin)
  - Web: `wget --spider http://localhost:80/health`
- **Logging**: json-file driver, max 10MB x 3 files per container
- **Restart policy**: `unless-stopped`
- **Network**: Isolated `page-net` bridge

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
- **Main content**: 12-cell weather grid (temperature, humidity, wind, pressure, UV, air quality, rain, solar, sun events, high/low)
- **Right-side collapsible drawer** with 3 tabs:
  - Weather Station: all 12 metric cells
  - 24-Hour Charts: temperature and wind/gust line charts
  - Radar: NWS KEMX radar loop GIF
- **Bottom bird drawer**: horizontal scroll strip of today's detected species with Wikipedia thumbnails, detection counts, and "New" badges for first-time species
- **Live clock**: JavaScript updates "Current Time" in the header every 15 seconds using the browser's local time. The "Updated" timestamp in the identification band stays static — it shows when the *data* was last refreshed server-side.
- **Font switcher**: toggles between historical NPS typefaces (1935 style, 1945 signage, 2026 modern)
- **Responsive**: works on mobile at 375px width

### Fonts

| Font | Usage | Source |
|------|-------|--------|
| Frutiger | Primary sans-serif (modern NPS) | Local woff2 |
| NationalPark | Variable-weight NPS typeface | Local woff2 |
| NPS1935 | Historical 1935-era style | Local woff2 |
| NPSSignage1945 | Historical highway signage style | Local woff2 |
| Cabin | Google Fonts fallback sans | Google Fonts CDN |
| Lora | Serif for accent text | Google Fonts CDN |

## DNS & Reverse Proxy

### DNS (AdGuard — CT 101, 192.168.0.11)

| Rewrite | Target | Purpose |
|---------|--------|---------|
| `*.1701.me` | `192.168.0.30` | Wildcard — all `.1701.me` domains resolve locally to NPM, bypassing hairpin NAT |
| `weather.home` | `192.168.0.30` | Local `.home` domain → NPM |

The `*.1701.me` wildcard was added during this deployment. It benefits all services using `.1701.me` domains, not just this one.

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
echo "[$(date)] Starting neighborhood-page generator (every 300s)..."
while true; do
    python3 /app/generate.py || echo "[$(date)] generate.py failed (exit $?)" >&2
    sleep 300
done
```

The `|| echo` prevents `set -e` from killing the loop if generate.py fails — it logs the error and retries in 5 minutes. `restart: unless-stopped` is the outer safety net.

## Operations

### Rebuild & Redeploy

```bash
# From Komodo (192.168.0.179)
cd /etc/komodo/stacks/neighborhood-page
docker compose build --no-cache
docker compose up -d
```

### Check Status

```bash
# Container health
docker ps --filter name=neighborhood-page

# Generator logs
docker logs neighborhood-page-generator --tail 30

# Verify output freshness
docker exec neighborhood-page-generator ls -la /output/index.html

# Test endpoints
curl http://192.168.0.179:8076/health
curl -s http://192.168.0.179:8076/ | grep -oE '\d+\.\d+°F'
```

### Edit Config and Redeploy

Files live at `/mnt/docker/neighborhood-page/` on Komodo. After editing:

```bash
cd /etc/komodo/stacks/neighborhood-page

# If you changed generate.py, template.html, Dockerfile, or entrypoint.sh:
docker compose build --no-cache && docker compose up -d

# If you only changed compose.yaml, nginx.conf, or .env:
docker compose up -d
```

### Force Immediate Regeneration

```bash
docker exec neighborhood-page-generator python3 /app/generate.py
```

## Troubleshooting

### Containers Show "unhealthy"

**Check generator logs first:**
```bash
docker logs neighborhood-page-generator --tail 20
```

**Common causes:**

| Error | Cause | Fix |
|-------|-------|-----|
| `KeyError: 'ECOWITT_APP_KEY'` | Missing env vars in .env file | Check `/mnt/docker/neighborhood-page/.env` has all required keys |
| `Ecowitt error 40000: wind_speed_unitid must between 6 - 11` | Wrong v3 unit ID | Use IDs from the unit table above — v3 IDs differ from v2 |
| `Ecowitt error {code}: {msg}` | API auth or rate limit | Check .env keys, wait for rate limit reset |
| `BirdNET-Go unavailable` | BirdNET-Go container down | Check `docker ps` for birdnet-go on Komodo |
| `Radar download failed` | NWS outage or timeout | Non-fatal — page still generates, just no radar.gif |

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
