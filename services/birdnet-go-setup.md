# BirdNET-Go Docker Setup

**Created**: 2026-02-03
**Updated**: 2026-03-12
**Status**: Complete and operational

## Summary

BirdNET-Go running as a Docker container on Komodo (CT 128), providing bird detection with a simpler, more modern interface than BirdNET-Pi. Managed as a Komodo stack.

## Configuration

| Setting | Value |
|---------|-------|
| Host Container | CT 128 (Komodo) |
| Host IP | 192.168.0.179 |
| Web UI Port | 8060 |
| Web UI URL | http://192.168.0.179:8060 |
| Prometheus Metrics | http://192.168.0.179:7828/metrics |
| Image | `ghcr.io/tphakala/birdnet-go:nightly` |
| Config Path | /mnt/docker/birdnet-go/config/config.yaml |
| Data Path | /mnt/docker/birdnet-go/data |
| Location | 32.4107, -110.9361 (Tucson, AZ) |

BirdNET-Go is the sole bird detection system. BirdNET-Pi (CT 122) was deprecated and destroyed on 2026-02-03. BirdNET-Pi was also removed from the Raspberry Pi on 2026-02-04 during the audio stream rebuild.

---

## Compose File (Komodo Stack)

Located at `/etc/komodo/stacks/birdnet-go/compose.yaml` on Komodo:

```yaml
name: birdnet-go

services:
  birdnet-go:
    image: ghcr.io/tphakala/birdnet-go:nightly
    container_name: birdnet-go
    restart: unless-stopped
    ports:
      - "8060:8080"
      - "7828:7828"
    volumes:
      - /mnt/docker/birdnet-go/config:/config
      - /mnt/docker/birdnet-go/data:/data
    environment:
      TZ: America/Phoenix
      BIRDNET_UID: 1000
      BIRDNET_GID: 1000
      BIRDNET_LATITUDE: 32.4107
      BIRDNET_LONGITUDE: -110.9361
      BIRDNET_LOCALE: en-uk
    tmpfs:
      - /config/hls:exec,size=50M,uid=1000,gid=1000,mode=0755
    extra_hosts:
      - "host.docker.internal:host-gateway"
    deploy:
      resources:
        limits:
          memory: 2G
    healthcheck:
      test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:8080 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    networks:
      - birdnet-net

networks:
  birdnet-net:
    driver: bridge
```

---

## Detection Settings (Tuned 2026-03-05)

Settings optimized based on multi-agent research review of BirdNET literature, Cornell Lab recommendations, and Tucson-specific considerations. Config path: `/mnt/docker/birdnet-go/config/config.yaml`

### Core BirdNET Settings

```yaml
birdnet:
  sensitivity: 1.0      # Cornell recommended sweet spot
  threshold: 0.75        # Balanced — cuts low-confidence floods, keeps real mid-confidence birds
  overlap: 2.0           # Required for false positive filter level 1 (was 1.5, caused owl detection drop)
  latitude: 32.4107
  longitude: -110.9361
  locale: en-us
  rangefilter:
    model: latest
    threshold: 0.01      # Inclusive — captures migrants; excellent eBird coverage for Tucson
```

### Deduplication Interval

```yaml
realtime:
  interval: 60           # 60s between same-species detections (was 15s default)
```

### Dynamic Threshold

```yaml
dynamicthreshold:
  enabled: true
  trigger: 0.9           # Only very high-confidence triggers lowering
  min: 0.35              # Raised from 0.2 — still catches owls but cuts garbage
  validhours: 12         # Covers a full night or morning cycle without stale unlocks
```

### False Positive Filter

```yaml
falsepositivefilter:
  level: 1               # Light filtering; requires overlap >= 2.0 to work correctly
```

### Privacy Filter

```yaml
privacyfilter:
  enabled: true
  confidence: 0.05       # Aggressively filters human speech in residential yard
```

### Dog Bark Filter

```yaml
dogbarkfilter:
  enabled: true
  confidence: 0.8        # High confidence required to trigger
  remember: 1            # Short suppression window
  species: []            # Empty — NOT adding owls (would suppress real GHO/WSO detections)
```

### Species Exclude List

Non-bird sounds and impossible species:

```yaml
species:
  exclude:
    - Common Loon        # Inland desert — impossible
    - Siren              # Emergency vehicle noise
    - Gun                # Gunfire / backfire noise
    - Engine             # Mechanical noise
```

### Settings Rationale

| Setting | Value | Rationale |
|---------|-------|-----------|
| threshold 0.75 | Down from 0.8 | BirdNET-Go balanced default is 0.8; 0.75 preserves mid-confidence real birds |
| rangefilter 0.01 | Inclusive | Tucson is a major migration corridor — captures legitimate rare visitors |
| dedup interval 60s | Up from 15s | Prevents database flood (306 goldfinch/day → ~70) without losing species data |
| dynamic min 0.35 | Up from 0.2 | 0.2 let garbage through; 0.35 preserves nocturnal owls (525 GHO detections in Feb) |
| validhours 12 | Down from 24 | Morning trigger resets before evening; prevents stale afternoon phantom detections |
| privacy filter 0.05 | Down from 0.5 | Aggressively rejects speech — 0.5 was too lenient for residential yard |
| dog bark species empty | Cleared | Adding owls to bark filter suppresses real owl detections when dogs bark nearby |
| overlap 2.0 | Up from 1.5 | Required for FP filter level 1; 1.5 caused 90% owl detection drop (2026-03-12) |
| FP filter level 1 | Light | Requires overlap >= 2.0; reserve level 2 for June-Sept cicada season |
| exclude list | 4 items | Non-bird noise classes + impossible species |

### Seasonal Notes

- **June-September (cicada season)**: Raise `falsepositivefilter.level` to 2. Cicadas produce broadband noise that degrades afternoon detection quality. Revert to 1 in October.
- **April-May (spring migration)**: Peak species diversity. Current settings are optimized for this — 0.01 rangefilter captures migrants.
- **Nocturnal detection**: Working well — 525 Great Horned Owl, 60 Barn Owl detections in February. Keep 24/7 recording enabled.

---

## Audio Configuration

### Normalization

**Disabled** (as of 2026-02-05). It was boosting the quiet nighttime noise floor to -23 LUFS, which amplified the Pi's cooling fan buzz and mic self-noise.

### Equalizer

**Enabled** with two filters:

```yaml
equalizer:
  enabled: true
  filters:
    - type: HighPass
      frequency: 500     # Cuts wind, traffic, HVAC rumble; owl harmonics above 500Hz preserved
      q: 0.1
    - type: LowPass
      frequency: 15000   # Cuts ultrasonic artifacts
      q: 0.1
```

### RTSP Source

```yaml
rtsp:
  streams:
    - name: rPi in Gazebo
      url: rtsp://192.168.0.136:8554/birdmic
      type: rtsp
      transport: tcp
```

---

## Prometheus Telemetry

Enabled on port 7828. Exposes 80+ metrics including:
- Detection counts per species
- Model prediction performance
- Audio levels and octave band analysis
- Weather data (via yr.no)
- Disk usage
- Database statistics

Scraped by Prometheus with job `birdnet-go` (see prometheus-config.yaml).

Grafana dashboard includes a dedicated BirdNET-Go section with weather, audio, and detection panels.

### Known Issue: Suncalc Metrics

As of nightly-20260118, `suncalc_*` metrics are registered but always return 0 (cache_size=0). This is a bug in the nightly build — the suncalc calculation code is never triggered. Weather metrics work fine. A newer build may fix this.

---

## Volume Mounts

| Container Path | Host Path | Purpose |
|----------------|-----------|---------|
| /config | /mnt/docker/birdnet-go/config | Configuration files |
| /data | /mnt/docker/birdnet-go/data | Detection clips and database |

---

## Management Commands

### View Logs
```bash
docker logs -f birdnet-go
```

### Restart Container
```bash
docker restart birdnet-go
```

### Update to Latest Version
```bash
# Via Komodo UI, or:
cd /etc/komodo/stacks/birdnet-go
docker compose pull
docker compose up -d
```

### Health Check
```bash
docker inspect birdnet-go --format='{{.State.Health.Status}}'
```

---

## Web Interface

Access at: **http://192.168.0.179:8060**

### Features
- Real-time spectrogram
- Detection list with confidence scores
- Audio playback of detected clips
- Species statistics and tracking
- Settings configuration
- Weather data display

---

## API Reference (v2)

Base URL: `http://192.168.0.179:8060`

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health, version, uptime |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/analytics/species/daily?date=&limit=` | Daily species summary |
| GET | `/api/v2/analytics/species/daily/batch?dates=&limit=` | Batch daily data |
| GET | `/api/v2/analytics/species/detections/new` | New species detections |
| GET | `/api/v2/analytics/species/summary` | Species summary |
| GET | `/api/v2/analytics/time/daily` | Daily time analytics |
| GET | `/api/v2/analytics/time/distribution/hourly` | Hourly distribution |

### Detections

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/detections` | List detections (filtered) |
| GET | `/api/v2/detections/recent?limit=&includeWeather=` | Recent detections |
| GET | `/api/v2/detections/{id}` | Single detection detail |
| POST | `/api/v2/detections/ignore` | Ignore/unignore a species |
| DELETE | `/api/v2/detections/{id}` | Delete a detection |
| SSE | `/api/v2/detections/stream` | Real-time detection stream |

### Audio & Media

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/audio/{detectionId}` | Download detection audio clip |
| GET | `/api/v2/media/species-image?name={scientificName}` | Species image |
| GET | `/api/v2/spectrogram/{id}?size=md&raw=true` | Spectrogram image |

### Settings & System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/settings` | Full settings (JSON) |
| GET | `/api/v2/system/info` | System information |
| GET | `/api/v2/system/resources` | Resource usage |
| GET | `/api/v2/system/database/stats` | Database stats |
| GET | `/api/v2/dynamic-thresholds?limit=` | List dynamic thresholds |
| GET | `/api/v2/range/species/list` | Species in range filter |

### Integrations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v2/integrations/weather/test` | Test weather integration |
| POST | `/api/v2/integrations/mqtt/test` | Test MQTT connection |

> **Note**: Extracted from frontend JS bundles (nightly-20260118). Additional endpoints may exist.

---

## Sources

- [tphakala/birdnet-go](https://github.com/tphakala/birdnet-go) - Official repository
- [Docker Hub / GHCR](https://ghcr.io/tphakala/birdnet-go) - Container images
