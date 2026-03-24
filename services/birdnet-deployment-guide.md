# BirdNET Deployment Guide

**Last Updated**: 2026-03-23
**Related Systems**: Raspberry Pi (192.168.0.136), Komodo CT 128 (192.168.0.179), Home Assistant VM 100 (192.168.0.154)

---

## Quick Reference

| Item | Value |
|------|-------|
| **Pi Model** | Raspberry Pi 4 (arm64) |
| **Pi IP** | 192.168.0.136 |
| **Pi SSH** | `ssh alec@192.168.0.136` (pw: 9773) |
| **Pi Location** | Gazebo (outdoor, Wi-Fi) |
| **RTSP Stream URL** | `rtsp://192.168.0.136:8554/birdmic` |
| **Stream Format** | Opus, 48kHz, Mono, 96kbps |
| **mediamtx Binary** | /root/mediamtx |
| **mediamtx Config** | /root/mediamtx.yml |
| **mediamtx Version** | v1.16.0 (as of 2026-02-04) |
| **mediamtx Service** | `systemctl status mediamtx` |
| **BirdNET-Go UI** | http://192.168.0.179:8060 |
| **BirdNET-Go Host** | Komodo CT 128 (192.168.0.179) |
| **BirdNET-Go Image** | `ghcr.io/tphakala/birdnet-go:nightly` |
| **BirdNET-Go Config** | /mnt/docker/birdnet-go/config/config.yaml |
| **BirdNET-Go Data** | /mnt/docker/birdnet-go/data |
| **Location** | 32.4107, -110.9361 (Tucson, AZ) |
| **Prometheus Metrics** | http://192.168.0.179:7828/metrics |
| **HA Iframe URL** | http://birds.1701.me/ui/dashboard |
| **MQTT** | Disabled (can enable to 192.168.0.154:1883) |
| **Mic Gain** | 6/15 (~9dB) via ALSA card 3 numid=3 — card can shift after reboot, check `arecord -l` |

---

## Architecture

```
USB Mic → Raspberry Pi (192.168.0.136) → mediamtx RTSP → BirdNET-Go (Komodo CT 128)
              (gazebo, Wi-Fi)                                 (192.168.0.179:8060)
```

Two components:
1. **Raspberry Pi 4** in the gazebo — captures audio from USB mic, serves RTSP stream via mediamtx
2. **BirdNET-Go** on Komodo (CT 128) — consumes RTSP stream, runs BirdNET AI model, detects bird species

BirdNET-Go is the sole bird detection system. BirdNET-Pi (CT 122) was deprecated and destroyed on 2026-02-03.

---

## Part 1: Raspberry Pi Audio Stream

The Pi's only job is to capture USB mic audio and serve it as an RTSP stream.

### Hardware

- **Raspberry Pi 4** (arm64), Raspberry Pi OS Bookworm, Wi-Fi
- **USB Microphone**: UAC 1.0 device at ALSA `hw:3,0` (natively stereo, downmixed to mono)
  - Movo M1 USB Lavalier (20ft cable, recommended) or NowTH USB Lavalier (6.5ft cable)
  - **Mic gain**: 6/15 (~9dB) — ALSA `Mic Capture Volume` (numid=3 on card 3, range 0-15, 0-22.39dB)
  - **Card number can shift** after reboot — always verify with `arecord -l` first
  - Default gain (15/15) is way too hot — causes clipping and amplifies electrical hum
  - Gain is persisted with `sudo alsactl store 3` on the Pi

| Spec | NowTH USB Lavalier | Movo M1 USB Lavalier |
|------|---------------------|----------------------|
| Amazon ASIN | B0929CQSX4 | B0176NRE1G |
| Frequency Response | 50Hz - 16kHz | 35Hz - 18kHz |
| Sensitivity | -32dB ±3dB | -30dB ±3dB |
| SNR | 84dB | 78dB |
| Cable Length | 6.56ft (2m) | 20ft (6m) |

**Recommendation**: Use the **Movo M1** — the 20ft cable is far more useful for outdoor mic placement. Audio quality difference is negligible for bird detection (most bird songs are 1-12kHz).

### Software Stack

Only two things run on the Pi:
1. **mediamtx** v1.16.0 — RTSP server ([GitHub](https://github.com/bluenviron/mediamtx))
2. **ffmpeg** — captures ALSA audio, feeds to mediamtx (launched automatically by mediamtx)

### Install mediamtx

```bash
ssh alec@192.168.0.136  # pw: 9773

# Download mediamtx (check https://github.com/bluenviron/mediamtx/releases for latest)
sudo bash -c 'cd /root && wget -q https://github.com/bluenviron/mediamtx/releases/download/v1.16.0/mediamtx_v1.16.0_linux_arm64.tar.gz -O mediamtx.tar.gz && tar -xzf mediamtx.tar.gz && rm mediamtx.tar.gz'
```

### Configure mediamtx.yml

Write to `/root/mediamtx.yml`:

```yaml
###############################################
# BirdNET Pi Audio Stream - mediamtx config
# Only serves RTSP audio from USB mic
###############################################

# Disable protocols we don't need
hls: no
webrtc: no
srt: no
record: no
rtmp: no

# RTSP settings
rtsp: yes
rtspAddress: :8554

# Path configuration with auto-starting ffmpeg
paths:
  birdmic:
    runOnInit: >
      ffmpeg -nostdin
      -f alsa -acodec pcm_s16le -ac 1 -ar 48000 -i hw:3,0
      -ac 1 -acodec libopus -b:a 96k
      -f rtsp -rtsp_transport tcp
      rtsp://localhost:$RTSP_PORT/$MTX_PATH
    runOnInitRestart: yes
```

**Key details**:
- `-ac 1` on both input and output — the USB mic is natively stereo; this forces mono
- `-ar 48000` — 48kHz sample rate (what BirdNET requires)
- `-acodec libopus -b:a 96k` — Opus encoding at 96kbps (nearly lossless for bird audio)
- `runOnInitRestart: yes` — auto-restarts ffmpeg if it crashes
- `hw:3,0` — must match actual USB mic device (verify with `arecord -l`)

### Why Opus over PCM

Raw PCM (`pcm_s16be`) was tried first but caused frequent RTP errors and stream cutouts due to mediamtx compatibility issues ([GitHub #1350](https://github.com/bluenviron/mediamtx/issues/1350)). Opus at 96kbps is nearly lossless for bird audio frequencies (1-12kHz), uses ~1/8th the bandwidth of PCM (96kbps vs 768kbps), and is rock-solid over RTSP.

### Create systemd Service

```bash
sudo tee /etc/systemd/system/mediamtx.service > /dev/null << 'EOF'
[Unit]
Description=mediamtx RTSP Server
Wants=network.target
After=network.target

[Service]
ExecStart=/root/mediamtx /root/mediamtx.yml
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable mediamtx
sudo systemctl start mediamtx
```

### Verify Stream

```bash
# Check service status
sudo systemctl status mediamtx

# Check logs — should show "is publishing to path" and "Opus"
sudo journalctl -u mediamtx --no-pager -n 15

# Verify stream format from any machine on the network
ffprobe rtsp://192.168.0.136:8554/birdmic
# Expected: opus, 48000 Hz, mono

# Check CPU (should be <10% each)
top -b -n 2 -d 2 | grep -E 'mediamtx|ffmpeg'
```

### USB Device Numbering

The ALSA device number (`hw:3,0`) can change between reboots. To prevent this:

```bash
# Find device name
arecord -l  # Look for card name like "HIDMediak"
# Use: -i plughw:CARD=HIDMediak,DEV=0 instead of hw:3,0
```

Or create a udev rule:
```bash
udevadm info -a /dev/snd/controlC3 | grep -E 'idVendor|idProduct'
sudo tee /etc/udev/rules.d/99-usb-mic.rules >/dev/null << EOF
SUBSYSTEM=="sound", ATTRS{idVendor}=="XXXX", ATTRS{idProduct}=="YYYY", ATTR{id}="birdmic"
EOF
sudo udevadm control --reload-rules
# Then use: -i plughw:CARD=birdmic,DEV=0
```

---

## Part 2: BirdNET-Go on Komodo

BirdNET-Go runs as a Docker container on Komodo (CT 128), managed as a Komodo stack.

### Docker Compose

Located at `/etc/komodo/stacks/birdnet-go/compose.yaml`:

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
          cpus: "2.0"
    healthcheck:
      test: ["CMD-SHELL", "wget --no-verbose --tries=1 -O /dev/null http://localhost:8080/ || exit 1"]
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

### Detection Settings

Config path: `/mnt/docker/birdnet-go/config/config.yaml`

Settings tuned 2026-03-23 based on multi-agent research, Cornell Lab recommendations, BirdNET-Go community best practices, and Tucson-specific testing.

#### Core BirdNET Settings

```yaml
birdnet:
  sensitivity: 1.0      # Default; validated as optimal for desert environment
  threshold: 0.75        # Balanced — within recommended 0.7-0.8 range per peer-reviewed research
  overlap: 1.0           # Samples every 2s; sufficient with FP filter disabled. Bump to 2.0 for cicada season
  threads: 2             # Limits TFLite to 2 threads on shared server (CT 128 runs Frigate, Immich, etc.)
  latitude: 32.4107
  longitude: -110.9361
  locale: en-uk
  usexnnpack: true       # CPU acceleration via TensorFlow Lite delegate
  rangefilter:
    model: latest
    threshold: 0.01      # Default; inclusive for Tucson migration corridor
```

#### Deduplication Interval

```yaml
realtime:
  interval: 60           # 60s between same-species detections (prevents database flood)
```

#### Dynamic Threshold

```yaml
dynamicthreshold:
  enabled: true
  trigger: 0.9           # Only very high-confidence triggers lowering
  min: 0.35              # Safety floor; catches owls but cuts garbage
  validhours: 12         # Covers a full night or morning cycle
```

#### False Positive Filter

```yaml
falsepositivefilter:
  level: 0               # Disabled — dynamic threshold (0.35) + confidence (0.75) provide sufficient gating
```

**Rationale**: FP filter level 1 cut overall detections in half (2026-03-12 incident). The dynamic threshold + confidence threshold combination is sufficient. Re-enable at level 1-2 for cicada season (requires overlap >= 2.0).

#### Equalizer

```yaml
equalizer:
  enabled: true
  filters:
    - type: HighPass
      frequency: 350     # Cuts wind/traffic/HVAC; preserves GHO fundamental (300-400Hz)
      q: 0.1             # Gentle rolloff (overdamped)
    - type: LowPass
      frequency: 15000   # Cuts ultrasonic artifacts; no bird vocalizations above ~12kHz
      q: 0.1
```

**Why 350Hz, not 500Hz**: Great Horned Owl fundamental is 300-400Hz. BirdNET uses a dual spectrogram (0-3kHz and 500Hz-15kHz). A 500Hz HighPass would remove the GHO fundamental from the first spectrogram. 350Hz preserves it while still cutting sub-bass noise.

#### Privacy Filter

```yaml
privacyfilter:
  enabled: true
  confidence: 0.05       # Aggressively filters human speech in residential yard
```

#### Dog Bark Filter

```yaml
dogbarkfilter:
  enabled: true
  confidence: 0.8        # High confidence required to trigger
  remember: 1            # Short suppression window
  species: []            # Empty — adding owls would SUPPRESS their detections when dogs bark
```

#### Species Exclude List

```yaml
species:
  exclude:
    - Common Loon        # Inland desert — impossible
    - Gadwall            # No permanent water habitat nearby
    - Canada Goose       # Rare in Tucson residential areas
    - Downy Woodpecker   # Absent from southern Arizona (Ladder-backed is the local equivalent)
    - Siren              # Emergency vehicle noise
    - Gun                # Gunfire / backfire noise
    - Engine             # Mechanical noise
```

**Not excluded**: Mallard (year-round AZ resident), Painted Redstart (possible during migration from nearby sky islands).

#### Settings Rationale

| Setting | Value | Rationale |
|---------|-------|-----------|
| sensitivity 1.0 | Default | Validated as optimal; 1.25 could be tested for quieter desert in future |
| threshold 0.75 | Down from 0.8 | Within recommended 0.7-0.8 range per peer-reviewed ornithology research |
| overlap 1.0 | Down from 2.0 | 2.0 was needed for FP filter level 1 (now disabled); 1.0 halves inference load |
| threads 2 | Down from 0 (auto=8) | Reduces CPU on shared server; 2 threads handles 3s analysis window easily |
| rangefilter 0.01 | Default | Inclusive — captures migrants; Tucson is a major migration corridor |
| dedup interval 60s | Up from 15s default | Prevents database flood without losing species data |
| dynamic min 0.35 | Up from default 0.3 | Catches nocturnal owls while cutting low-quality detections |
| validhours 12 | Down from default 24 | Resets before evening; prevents stale afternoon phantom detections |
| privacy filter 0.05 | Very aggressive | 0.5 was too lenient for residential yard with regular conversation |
| dog bark species empty | Correct | Adding owls to bark filter SUPPRESSES their detections when dogs bark |
| FP filter level 0 | Disabled | Was cutting detections in half; dynamic threshold + confidence sufficient |
| equalizer HP 350Hz | Enabled | Cuts noise below bird range; 350Hz safe for owl fundamentals (300-400Hz) |
| cpus 2.0 | Docker limit | Prevents starving other services; matches threads=2 |

### Audio Configuration

#### Normalization

**Disabled** (since 2026-02-05). Was boosting quiet nighttime noise floor to -23 LUFS, amplifying the Pi's cooling fan buzz and mic self-noise.

#### RTSP Source

```yaml
rtsp:
  streams:
    - name: rPi in Gazebo
      url: rtsp://192.168.0.136:8554/birdmic
      type: rtsp
      transport: tcp
  health:
    healthydatathreshold: 60
    monitoringinterval: 30
```

### Seasonal Notes

- **June-September (cicada season)**: Raise `falsepositivefilter.level` to 1-2 and set `overlap` to 2.0. Cicadas produce broadband noise that degrades afternoon detection quality. Revert in October.
- **April-May (spring migration)**: Peak species diversity. Current settings are optimized for this — 0.01 rangefilter captures migrants.
- **Nocturnal detection**: Working well — GHO and Barn Owl detected regularly. Keep 24/7 recording enabled.

---

## Part 3: Monitoring & Integrations

### Prometheus Telemetry

Enabled on port 7828. Exposes 80+ metrics including:
- Detection counts per species
- Model prediction performance
- Audio levels and octave band analysis
- Weather data (via yr.no)
- Disk usage, database statistics

Scraped by Prometheus with job `birdnet-go` (see prometheus-config.yaml).

#### Known Issue: Suncalc Metrics

As of nightly-20260118, `suncalc_*` metrics are registered but always return 0 (cache_size=0). Weather metrics work fine. A newer build may fix this.

### Home Assistant Iframe

BirdNET-Go dashboard embedded in HA via Nginx Proxy Manager:
- **NPM Proxy Host**: `birds.1701.me` → `192.168.0.179:8060`
- **Custom Nginx Directive**: `proxy_hide_header X-Frame-Options;` (required — BirdNET-Go hardcodes `X-Frame-Options: SAMEORIGIN`)
- **HA Iframe URL**: `http://birds.1701.me/ui/dashboard`

### Web UI & API Reference

Access at: **http://192.168.0.179:8060**

#### API Endpoints (v2)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health, version, uptime |
| GET | `/api/v2/analytics/species/daily?date=&limit=` | Daily species summary |
| GET | `/api/v2/analytics/species/daily/batch?dates=&limit=` | Batch daily data |
| GET | `/api/v2/analytics/species/detections/new` | New species detections |
| GET | `/api/v2/analytics/species/summary` | Species summary |
| GET | `/api/v2/analytics/time/daily` | Daily time analytics |
| GET | `/api/v2/analytics/time/distribution/hourly` | Hourly distribution |
| GET | `/api/v2/detections` | List detections (filtered) |
| GET | `/api/v2/detections/recent?limit=&includeWeather=` | Recent detections |
| GET | `/api/v2/detections/{id}` | Single detection detail |
| POST | `/api/v2/detections/ignore` | Ignore/unignore a species |
| DELETE | `/api/v2/detections/{id}` | Delete a detection |
| SSE | `/api/v2/detections/stream` | Real-time detection stream |
| GET | `/api/v2/audio/{detectionId}` | Download detection audio clip |
| GET | `/api/v2/media/species-image?name={scientificName}` | Species image |
| GET | `/api/v2/spectrogram/{id}?size=md&raw=true` | Spectrogram image |
| GET | `/api/v2/settings` | Full settings (JSON) |
| GET | `/api/v2/system/info` | System information |
| GET | `/api/v2/system/resources` | Resource usage |
| GET | `/api/v2/system/database/stats` | Database stats |
| GET | `/api/v2/dynamic-thresholds?limit=` | List dynamic thresholds |
| GET | `/api/v2/range/species/list` | Species in range filter |

> Extracted from frontend JS bundles (nightly-20260118). Additional endpoints may exist.

---

## Troubleshooting

### Pi: No RTSP Stream

```bash
ssh alec@192.168.0.136

# Check service
sudo systemctl status mediamtx

# Check logs
sudo journalctl -u mediamtx -f

# Verify mic is detected
arecord -l
# Should show: card 3: HIDMediak [UAC 1.0 Microphone & HID-Mediak]

# Test mic directly
arecord -D hw:3,0 -f S16_LE -r 48000 -c 1 -d 5 test.wav && aplay test.wav

# Restart service
sudo systemctl restart mediamtx
```

### Pi: USB Mic Device Number Changed

If `hw:3,0` stops working after reboot, the USB device number may have shifted. Run `arecord -l` to find the new number and update mediamtx.yml. See [USB Device Numbering](#usb-device-numbering) above for permanent fix.

### Pi: Audio Buzzing / Crackling

Root cause (investigated 2026-02-05): Pi's mechanical cooling fan vibrating near the USB mic, plus gain set too high.

**Fixes applied:**
1. Mic gain lowered from 15/15 to 6/15: `amixer -c 3 cset numid=3 6 && sudo alsactl store 3`
2. BirdNET-Go normalization disabled

**To adjust gain remotely:**
```bash
# Verify card number first (can shift after reboot!)
SSHPASS='9773' sshpass -e ssh alec@192.168.0.136 "arecord -l"

# Set gain (0-15, currently 6, on card 3)
SSHPASS='9773' sshpass -e ssh alec@192.168.0.136 "amixer -c 3 cset numid=3 <VALUE> && sudo alsactl store 3"
```

If buzzing returns, consider physically separating the mic from the Pi's fan or replacing with a passive heatsink case.

### BirdNET-Go: No Detections

1. Check stream health in the web UI (http://192.168.0.179:8060)
2. Verify RTSP stream is reachable: `docker exec birdnet-go ffprobe rtsp://192.168.0.136:8554/birdmic`
3. Check logs: `docker logs --tail 30 birdnet-go`

### BirdNET-Go: High Restart Count / Backoff

If ffmpeg accumulates restarts (e.g., stream was down during maintenance), it enters exponential backoff. Fix by restarting:
```bash
docker restart birdnet-go
```

### BirdNET-Go: Container "Unhealthy"

Normal during startup while the model loads (~30 seconds). If it persists:
```bash
docker logs birdnet-go | tail -30
```

### General: Test Stream

```bash
# Quick format check
ffprobe rtsp://192.168.0.136:8554/birdmic

# Listen test
ffplay rtsp://192.168.0.136:8554/birdmic

# Or in VLC: File > Open Network Stream > rtsp://192.168.0.136:8554/birdmic
```

---

## Management Commands

```bash
# View logs
docker logs -f birdnet-go

# Restart container
docker restart birdnet-go

# Update to latest version
cd /etc/komodo/stacks/birdnet-go
docker compose pull
docker compose up -d

# Health check
docker inspect birdnet-go --format='{{.State.Health.Status}}'

# Check Prometheus metrics
curl -s http://192.168.0.179:7828/metrics | grep birdnet_detections

# CPU/memory usage
docker stats --no-stream birdnet-go
```

---

## Audio Technical Notes

### BirdNET Audio Requirements

| Parameter | Value | Notes |
|-----------|-------|-------|
| Sample Rate | 48,000 Hz | Required |
| Bit Depth | 16-bit signed | Required |
| Channels | Mono | Recommended (stereo accepted, downmixed internally) |

### Volume Mounts

| Container Path | Host Path | Purpose |
|----------------|-----------|---------|
| /config | /mnt/docker/birdnet-go/config | Configuration files |
| /data | /mnt/docker/birdnet-go/data | Detection clips, database, logs |

---

## Related Incidents

- [Owl Detection Drop After Config Change](../incidents/2026-03-12-birdnet-owl-detection-drop.md) — FP filter + overlap mismatch caused 90% owl detection loss
- [Iframe Blocked in Home Assistant](../incidents/2026-02-18-birdnet-iframe-blocked.md) — X-Frame-Options header fix via NPM

---

## Sources

- [tphakala/birdnet-go](https://github.com/tphakala/birdnet-go) — Official repository
- [BirdNET-Go Wiki](https://github.com/tphakala/birdnet-go/wiki) — Configuration guide
- [bluenviron/mediamtx](https://github.com/bluenviron/mediamtx) — RTSP server
- [Cornell Lab BirdNET](https://birdnet.cornell.edu/) — Original research
