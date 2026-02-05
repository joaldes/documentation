# BirdNET-Go Docker Setup

**Created**: 2026-02-03
**Updated**: 2026-02-05
**Status**: Complete and operational

## Summary

BirdNET-Go running as a Docker container on Komodo (CT 128), providing bird detection with a simpler, more modern interface than BirdNET-Pi.

## Configuration

| Setting | Value |
|---------|-------|
| Host Container | CT 128 (Komodo) |
| Host IP | 192.168.0.179 |
| Web UI Port | 8060 |
| Web UI URL | http://192.168.0.179:8060 |
| Image | `ghcr.io/tphakala/birdnet-go:nightly` |
| Data Storage | /mnt/birdnet/birdnet-go |
| Location | 32.4107, -110.9361 (Tucson, AZ) |

BirdNET-Go is the sole bird detection system. BirdNET-Pi (CT 122) was deprecated and destroyed on 2026-02-03. BirdNET-Pi was also removed from the Raspberry Pi on 2026-02-04 during the audio stream rebuild.

---

## Installation

### Prerequisites

- Docker host (Komodo CT 128 in this setup)
- RTSP audio stream available
- Shared storage partition mounted (optional)

### Create Data Directories

```bash
mkdir -p /mnt/birdnet/birdnet-go/config
mkdir -p /mnt/birdnet/birdnet-go/data
chown -R 1000:1000 /mnt/birdnet/birdnet-go
```

### Deploy Container

```bash
docker run -d --name birdnet-go \
  --restart unless-stopped \
  -p 8060:8080 \
  -e BIRDNET_LATITUDE=32.4107 \
  -e BIRDNET_LONGITUDE=-110.9361 \
  -e BIRDNET_LOCALE=en-uk \
  -e TZ=America/Phoenix \
  -v /mnt/birdnet/birdnet-go/config:/config \
  -v /mnt/birdnet/birdnet-go/data:/data \
  ghcr.io/tphakala/birdnet-go:nightly
```

### Verify Running

```bash
docker ps | grep birdnet-go
```

---

## Environment Variables

| Variable | Value | Description |
|----------|-------|-------------|
| BIRDNET_LATITUDE | 32.4107 | Location latitude |
| BIRDNET_LONGITUDE | -110.9361 | Location longitude |
| BIRDNET_LOCALE | en-uk | Bird name language |
| TZ | America/Phoenix | Timezone |
| BIRDNET_UID | 1000 | User ID for file permissions |
| BIRDNET_GID | 1000 | Group ID for file permissions |

---

## Volume Mounts

| Container Path | Host Path | Purpose |
|----------------|-----------|---------|
| /config | /mnt/birdnet/birdnet-go/config | Configuration files |
| /data | /mnt/birdnet/birdnet-go/data | Detection clips and database |

---

## Shared Storage Setup

BirdNET-Go data lives on a dedicated partition:

```
/mnt/birdnet (250GB partition - /dev/sde5)
└── birdnet-go/      # Used by Docker in CT 128
    ├── config/
    └── data/
```

### Host Mount Configuration

On Proxmox host (`/etc/fstab`):
```
LABEL=birdnet-data /mnt/birdnet ext4 defaults 0 2
```

In Komodo container config (`/etc/pve/lxc/128.conf`):
```conf
mp5: /mnt/birdnet/birdnet-go,mp=/mnt/birdnet
```

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
docker pull ghcr.io/tphakala/birdnet-go:nightly
docker stop birdnet-go
docker rm birdnet-go
# Re-run the docker run command above
```

### Stop Container
```bash
docker stop birdnet-go
```

### Remove Container
```bash
docker stop birdnet-go
docker rm birdnet-go
```

---

## Web Interface

Access at: **http://192.168.0.179:8060**

### Features
- Real-time spectrogram
- Detection list with confidence scores
- Audio playback of detected clips
- Species statistics
- Settings configuration

### Configuration via Web UI
1. Navigate to Settings
2. Configure audio input (RTSP stream)
3. Set detection thresholds
4. Configure notification options (if desired)

---

## RTSP Audio Configuration

BirdNET-Go can use the same RTSP feed as BirdNET-Pi:
```
rtsp://192.168.0.136:8554/birdmic
```

Configure in the web UI under Settings → Audio Input.

---

## Audio Normalization

Normalization is **disabled** (as of 2026-02-05). It was boosting the quiet nighttime noise floor to -23 LUFS, which amplified the Pi's cooling fan buzz and mic self-noise.

```yaml
normalization:
  enabled: false
```

If re-enabled, the settings were: target -23 LUFS, loudness range 7, true peak -2.

---

## Audio Equalizer

An equalizer is enabled to filter environmental noise before analysis:

```yaml
equalizer:
  enabled: true
  filters:
    - type: HighPass
      frequency: 500
      q: 0.1
    - type: LowPass
      frequency: 12000
      q: 0.1
```

- **HighPass 500Hz**: Filters pool water trickling, traffic rumble, HVAC
- **LowPass 12kHz**: Filters ultrasonic noise above BirdNET's analysis range

Config location: `/mnt/birdnet/birdnet-go/config/config.yaml` → `realtime.audio.equalizer`

Restart after changes: `docker restart birdnet-go`

---

## Troubleshooting

### Container Shows "unhealthy"
This is normal during startup while the model loads. Check logs:
```bash
docker logs birdnet-go | tail -20
```

### No Detections
1. Verify RTSP stream is configured
2. Check audio input in web UI
3. Verify location coordinates are correct

### Permission Denied on Data Directory
```bash
chown -R 1000:1000 /mnt/birdnet/birdnet-go
```

### Container Won't Start
```bash
# Check for port conflicts
netstat -tlnp | grep 8060

# Check Docker logs
docker logs birdnet-go
```

### Update Container After Config Change
```bash
docker restart birdnet-go
```

---

## Health Check

The container includes a built-in health check. View status:
```bash
docker inspect birdnet-go --format='{{.State.Health.Status}}'
```

---

## API Reference (v2)

Base URL: `http://192.168.0.179:8060`

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health, version, uptime |

### App

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/app/config` | Application configuration |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/analytics/species/daily?date=&limit=` | Daily species summary |
| GET | `/api/v2/analytics/species/daily/batch?dates=&limit=` | Batch daily data |
| GET | `/api/v2/analytics/species/detections/new` | New species detections |
| GET | `/api/v2/analytics/species/summary` | Species summary |
| GET | `/api/v2/analytics/species/thumbnails` | Species thumbnails |
| GET | `/api/v2/analytics/time/daily` | Daily time analytics |
| GET | `/api/v2/analytics/time/daily/batch` | Batch daily time analytics |
| GET | `/api/v2/analytics/time/distribution/hourly` | Hourly distribution |
| GET | `/api/v2/analytics/time/hourly/batch` | Batch hourly analytics |

### Audio

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/audio/{detectionId}` | Download detection audio clip |

### Detections

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/detections` | List detections (filtered) |
| GET | `/api/v2/detections/recent?limit=&includeWeather=` | Recent detections |
| GET | `/api/v2/detections/{id}` | Single detection detail |
| POST | `/api/v2/detections/ignore` | Ignore/unignore a species |
| POST | `/api/v2/detections/{id}/lock` | Lock/unlock a detection |
| DELETE | `/api/v2/detections/{id}` | Delete a detection |
| SSE | `/api/v2/detections/stream` | Real-time detection stream |

### Media

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/media/species-image?name={scientificName}` | Species image |
| GET | `/api/v2/media/audio/{id}` | Audio media file |
| GET | `/api/v2/spectrogram/{id}?size=md&raw=true` | Spectrogram image |

### Species

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/species?scientific_name=` | Species info |
| GET | `/api/v2/species/taxonomy?scientific_name=` | Taxonomy lookup |

### Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/search` | Search detections |

### Notifications

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/notifications?limit=&status=` | List notifications |
| PUT | `/api/v2/notifications/{id}/read` | Mark as read |
| POST | `/api/v2/notifications/{id}/acknowledge` | Acknowledge notification |
| DELETE | `/api/v2/notifications/{id}` | Delete notification |
| POST | `/api/v2/notifications/test/new-species` | Test notification |
| SSE | `/api/v2/notifications/stream` | Real-time notification stream |

### Streams (Live Audio)

| Method | Endpoint | Description |
|--------|----------|-------------|
| SSE | `/api/v2/streams/audio-level` | Audio level meter |
| POST | `/api/v2/streams/hls/{source}/start` | Start HLS stream |
| POST | `/api/v2/streams/hls/{source}/stop` | Stop HLS stream |
| GET | `/api/v2/streams/hls/{source}/playlist.m3u8` | HLS playlist |
| POST | `/api/v2/streams/hls/heartbeat` | Keep stream alive |
| GET | `/api/v2/streams/health` | Stream health check |
| SSE | `/api/v2/streams/health/stream` | Stream health SSE |
| SSE | `/api/v2/soundlevels/stream` | Sound level SSE |

### Weather

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/weather/sun/{location}` | Sunrise/sunset times |
| GET | `/api/v2/weather/hourly/{location}` | Hourly forecast |
| GET | `/api/v2/weather/detection/{id}` | Weather at detection time |

### Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/settings/dashboard` | Dashboard settings |
| GET | `/api/v2/settings/locales` | Available locales |
| GET | `/api/v2/settings/imageproviders` | Image providers |
| GET | `/api/v2/settings/notification` | Notification settings |
| GET | `/api/v2/settings/systemid` | System ID |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/system/info` | System information |
| GET | `/api/v2/system/resources` | Resource usage |
| GET | `/api/v2/system/disks` | Disk info |
| GET | `/api/v2/system/processes` | Process list (`?all=true` for all) |
| GET | `/api/v2/system/temperature/cpu` | CPU temperature |
| GET | `/api/v2/system/audio/devices` | Audio devices |
| GET | `/api/v2/system/audio/equalizer/config` | Equalizer config |
| GET | `/api/v2/system/database/stats` | Database stats |
| GET | `/api/v2/support/generate` | Generate support bundle |

### Dynamic Thresholds

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/dynamic-thresholds?limit=` | List thresholds |
| GET | `/api/v2/dynamic-thresholds/stats` | Threshold stats |
| DELETE | `/api/v2/dynamic-thresholds/{species}` | Delete threshold |
| POST | `/api/v2/dynamic-thresholds?confirm=true` | Update thresholds |

### Range Filter

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/range/species/count` | Species count in range |
| GET | `/api/v2/range/species/list` | List species in range |
| GET | `/api/v2/range/species/csv` | CSV export |
| POST | `/api/v2/range/species/test` | Test range filter |

### Integrations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v2/integrations/birdweather/test` | Test BirdWeather connection |
| POST | `/api/v2/integrations/mqtt/test` | Test MQTT connection |
| POST | `/api/v2/integrations/mqtt/homeassistant/discovery` | Trigger HA MQTT discovery |
| POST | `/api/v2/integrations/weather/test` | Test weather integration |

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v2/auth/login` | Login |
| POST | `/api/v2/auth/logout` | Logout |
| GET | `/auth/google` | Google OAuth |
| GET | `/auth/github` | GitHub OAuth |
| GET | `/auth/microsoftonline` | Microsoft OAuth |
| GET | `/auth/kakao` | Kakao OAuth |
| GET | `/auth/line` | LINE OAuth |

> **Note**: Extracted from frontend JS bundles (nightly-20260118). Server-side-only endpoints may exist beyond what the UI calls.

---

## Sources

- [tphakala/birdnet-go](https://github.com/tphakala/birdnet-go) - Official repository
- [Docker Hub / GHCR](https://ghcr.io/tphakala/birdnet-go) - Container images
