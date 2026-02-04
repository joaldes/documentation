# BirdNET Deployment Guide

**Last Updated**: 2026-02-04
**Related Systems**: Raspberry Pi (192.168.0.136), Komodo CT 128 (192.168.0.179), Home Assistant VM 100 (192.168.0.154)

---

## Architecture

```
USB Mic → Raspberry Pi (192.168.0.136) → mediamtx RTSP → BirdNET-Go (Komodo CT 128)
              (gazebo, Wi-Fi)                                 (192.168.0.179:8060)
```

Two components:
1. **Raspberry Pi 4** in the gazebo — captures audio from a USB mic and serves it as an RTSP stream via mediamtx
2. **BirdNET-Go** on Komodo (CT 128) — consumes the RTSP stream, runs the BirdNET AI model, detects bird species

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
| **BirdNET-Go Data** | /mnt/birdnet/birdnet-go |
| **Location** | 32.4107, -110.9361 (Tucson, AZ) |
| **MQTT** | Disabled (can enable to 192.168.0.154:1883) |
| **Equalizer** | HighPass 500Hz + LowPass 12kHz (filters pool/traffic noise) |

---

## Part 1: Raspberry Pi Audio Stream

The Pi's only job is to capture USB mic audio and serve it as an RTSP stream.

### Hardware

- **Raspberry Pi 4** (arm64), Raspberry Pi OS Bookworm, Wi-Fi
- **USB Microphone**: UAC 1.0 device at ALSA `hw:3,0` (natively stereo, downmixed to mono)
  - Movo M1 USB Lavalier (20ft cable, recommended) or NowTH USB Lavalier (6.5ft cable)

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

> **Why Opus instead of PCM?** Raw PCM (`pcm_s16be`) was tried first but caused frequent RTP errors and stream cutouts due to mediamtx compatibility issues ([GitHub #1350](https://github.com/bluenviron/mediamtx/issues/1350)). Opus at 96kbps is nearly lossless for bird audio frequencies (1-12kHz) and is rock-solid over RTSP.

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

---

## Part 2: BirdNET-Go on Komodo

BirdNET-Go runs as a Docker container on Komodo (CT 128).

### Deploy Container

```bash
ssh root@192.168.0.179  # pw: password

# Create data directories
mkdir -p /mnt/birdnet/birdnet-go/config /mnt/birdnet/birdnet-go/data
chown -R 1000:1000 /mnt/birdnet/birdnet-go

# Run container
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

### Configure via Web UI

1. Open http://192.168.0.179:8060
2. Go to **Settings**
3. Configure RTSP source: `rtsp://192.168.0.136:8554/birdmic` with TCP transport
4. Set threshold: 0.7
5. Verify location: 32.4107, -110.9361

### Key Settings in config.yaml

The config lives at `/mnt/birdnet/birdnet-go/config/config.yaml` (or `/config/config.yaml` inside the container). Key sections:

```yaml
birdnet:
  threshold: 0.7
  latitude: 32.4107
  longitude: -110.9361
realtime:
  audio:
    equalizer:
      enabled: true
      filters:
        - type: HighPass
          frequency: 500
          q: 0.1
        - type: LowPass
          frequency: 12000
          q: 0.1
  rtsp:
    streams:
      - name: Birdmic
        url: rtsp://192.168.0.136:8554/birdmic
        type: rtsp
        transport: tcp
```

### Audio Equalizer

The equalizer filters environmental noise before BirdNET analysis. Currently configured with:

- **HighPass 500Hz** — filters out low-frequency noise (pool water trickling, traffic rumble, HVAC). Most bird vocalizations are above 1kHz.
- **LowPass 12000Hz** — filters out ultrasonic noise. BirdNET analyzes up to ~12kHz.

To adjust, edit `/mnt/birdnet/birdnet-go/config/config.yaml` (the `equalizer` section under `realtime.audio`) and restart:
```bash
docker restart birdnet-go
```

> **Warning**: When editing config.yaml by hand, be careful with `sed` — the file has many `enabled:` fields. Always use line-number-specific edits or edit via the web UI to avoid accidentally enabling unrelated features.

### Shared Storage

BirdNET-Go data lives on a dedicated 250GB partition:

```
/mnt/birdnet/birdnet-go/
├── config/    # config.yaml
└── data/      # clips/, birdnet.db, logs/
```

Host mount in `/etc/pve/lxc/128.conf`:
```conf
mp5: /mnt/birdnet/birdnet-go,mp=/mnt/birdnet
```

### Management Commands

```bash
# View logs
docker logs -f birdnet-go

# Restart
docker restart birdnet-go

# Update
docker pull ghcr.io/tphakala/birdnet-go:nightly
docker stop birdnet-go && docker rm birdnet-go
# Re-run the docker run command above

# Health check
docker inspect birdnet-go --format='{{.State.Health.Status}}'
```

---

## Troubleshooting

### Pi: No RTSP stream

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

### Pi: USB mic device number changed

If `hw:3,0` stops working after a reboot, the USB device number may have shifted. Run `arecord -l` to find the new number and update mediamtx.yml.

To prevent this, use the device name instead:
```bash
# Find device name
arecord -l  # Look for card name like "HIDMediak"
# Use: -i plughw:CARD=HIDMediak,DEV=0 instead of hw:3,0
```

### BirdNET-Go: No detections

1. Check stream health in the web UI (http://192.168.0.179:8060)
2. Check audio logs: `docker exec birdnet-go tail -20 /data/logs/audio.log`
3. Verify RTSP stream is reachable from Komodo: `docker exec birdnet-go ffprobe rtsp://192.168.0.136:8554/birdmic`

### BirdNET-Go: High restart count / backoff

If BirdNET-Go's ffmpeg process accumulates restarts (e.g., stream was down during maintenance), it enters exponential backoff. Fix by restarting the container:
```bash
docker restart birdnet-go
```

### BirdNET-Go: Container "unhealthy"

Normal during startup while the model loads (~30 seconds). If it persists:
```bash
docker logs birdnet-go | tail -30
```

### General: Test stream from any machine

```bash
# Quick format check
ffprobe rtsp://192.168.0.136:8554/birdmic

# Listen test
ffplay rtsp://192.168.0.136:8554/birdmic

# Or in VLC: File > Open Network Stream > rtsp://192.168.0.136:8554/birdmic
```

---

## Audio Technical Notes

### BirdNET Audio Requirements

| Parameter | Value | Notes |
|-----------|-------|-------|
| Sample Rate | 48,000 Hz | Required |
| Bit Depth | 16-bit signed | Required |
| Channels | Mono | Recommended (stereo is accepted, downmixed internally) |

### Why Opus over PCM?

Raw PCM (`pcm_s16be`) was initially selected for zero-loss audio, but in practice it caused frequent RTP errors and stream cutouts due to mediamtx compatibility issues ([GitHub #1350](https://github.com/bluenviron/mediamtx/issues/1350)).

Opus at 96kbps is the production choice:
- Nearly lossless for bird audio frequencies (1-12kHz)
- Rock-solid RTSP transport — no RTP errors
- ~1/8th the bandwidth of PCM (96kbps vs 768kbps)
- Minimal CPU overhead on the Pi

### USB Microphone

The current mic (UAC 1.0 "HID-Mediak") is natively stereo at ALSA level. The ffmpeg command uses `-ac 1` on both input and output to force mono, which halves bandwidth and avoids phase issues.

---

## Related Documents

- [birdnet-go-setup.md](birdnet-go-setup.md) — BirdNET-Go Docker container details
- [birdnet-pi-audio-stream-rebuild.md](birdnet-pi-audio-stream-rebuild.md) — Historical: 2026-02-04 rebuild of the Pi (research, decisions, original setup reference)
- [birdnet-pi-lxc-setup.md](birdnet-pi-lxc-setup.md) — DEPRECATED: old BirdNET-Pi LXC setup (CT 122, destroyed)
