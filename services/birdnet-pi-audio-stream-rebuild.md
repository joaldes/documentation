# BirdNET Pi Audio Stream Rebuild

> **This is a historical reference document.** For the current deployment guide, see [birdnet-deployment-guide.md](birdnet-deployment-guide.md).

**Created**: 2026-02-04
**Status**: Completed - 2026-02-04
**Related Systems**: Raspberry Pi (192.168.0.136), Komodo CT 128 (BirdNET-Go), Home Assistant VM 100 (MQTT)

---

## Overview

On 2026-02-04, the Raspberry Pi in the gazebo was rebuilt from a cluttered state (BirdNET-Pi, BirdNET-Go Docker, 76GB of recordings, full desktop environment) down to a minimal audio streaming appliance. This document records the research, decisions, and steps taken.

**Result**: Pi disk usage went from 98% → 18%. Only mediamtx + ffmpeg remain. PCM was tried initially but caused RTP errors — switched to Opus at 96kbps which is stable. BirdNET-Go on Komodo receives the stream and is detecting birds successfully.

---

## Architecture

```
USB Mic → Raspberry Pi (192.168.0.136) → mediamtx RTSP → BirdNET-Go (Komodo CT 128)
              (gazebo)                                        (192.168.0.179:8060)
                                                                    ↓
                                                              MQTT → Home Assistant
                                                          (192.168.0.154:1883)
```

---

## Hardware

### Raspberry Pi
- **Model**: Raspberry Pi 4 (arm64)
- **IP**: 192.168.0.136
- **Location**: Gazebo (outdoor)
- **OS**: Raspberry Pi OS Bookworm
- **Connection**: Wi-Fi to home network

### USB Microphone (one of these two)
Both are budget USB omnidirectional lavalier mics. Real-world bird detection performance is nearly identical between them. The main differentiator is cable length.

| Spec | NowTH USB Lavalier | Movo M1 USB Lavalier |
|------|---------------------|----------------------|
| **Amazon ASIN** | B0929CQSX4 | B0176NRE1G |
| **Frequency Response** | 50Hz - 16kHz | 35Hz - 18kHz |
| **Sensitivity** | -32dB ±3dB | -30dB ±3dB |
| **SNR** | 84dB | 78dB |
| **Pattern** | Omnidirectional | Omnidirectional |
| **Cable Length** | 6.56ft (2m) | 20ft (6m) |
| **Connector** | USB | USB |

**Recommendation**: Use the **Movo M1** if available — the 20ft cable is far more useful for outdoor mic placement than the NowTH's 6.56ft. Audio quality difference is negligible for bird detection (most bird songs are 1-12kHz, well within both mics' range).

---

## BirdNET-Go Audio Requirements

The BirdNET AI model has fixed audio requirements (hardcoded in source):

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Sample Rate** | 48,000 Hz | Required |
| **Bit Depth** | 16-bit signed (S16_LE) | Required |
| **Channels** | 1 (Mono) | Recommended — BirdNET-Go accepts stereo and downmixes internally, but sending mono is optimal (less bandwidth, no phase issues) |
| **Capture Length** | ~3 seconds per analysis segment | Typical — based on the underlying BirdNET model's analysis window |

All audio input is converted to this format regardless of source. Sending audio in this exact format (PCM S16 48kHz mono) avoids unnecessary encoding/decoding and preserves maximum quality.

---

## Audio Stream Type Decision

### Options Evaluated

| Stream Type | Latency | CPU on Pi | Audio Quality | Reliability | Bird Detection Quality |
|-------------|---------|-----------|---------------|-------------|----------------------|
| **RTSP + PCM** | Moderate | Low | Excellent (lossless) | Good (TCP) | **Best possible** |
| **RTSP + Opus** | Moderate | Low | Very good | Good (TCP) | Excellent |
| **RTSP + MP3** | Moderate | Low-Med | Good (lossy) | Good (TCP) | Good |
| **RTSP + AAC** | Moderate | Low-Med | Good (lossy) | Good (TCP) | Good |
| **UDP/RTP + PCM** | Very low | Very low | Excellent | Poor (no error correction) | Best if no packet drops |
| **HTTP stream** | Mod-High | Moderate | Varies | Moderate | Good |
| **HLS** | High (2-10s) | Moderate | Varies | Good | Poor (too much delay) |
| **RTMP** | Low-Mod | Moderate | Good | Moderate | Good |

### Detailed Pros/Cons

#### RTSP + PCM (Uncompressed) — TRIED, FAILED
- **Pros**: Zero codec artifacts, best possible audio fidelity, no CPU wasted on encoding on the Pi, audio arrives in the exact format BirdNET needs (48kHz/16-bit/mono)
- **Cons**: Higher bandwidth (~768kbps for 48kHz/16-bit/mono), slightly more sensitive to network issues than compressed streams
- **Bandwidth note**: 768kbps is trivial on a LAN — less than 1Mbps. Even over Wi-Fi this is nothing.
- **FFmpeg command**: `-acodec pcm_s16be -f rtsp -rtsp_transport tcp`
- **Known issue**: mediamtx has documented compatibility concerns with raw PCM audio ([GitHub #1350](https://github.com/bluenviron/mediamtx/issues/1350)). `pcm_s16be` works (big-endian is correct for RTP per RFC 3551), but `pcm_s16le` does NOT. If any stability or CPU issues arise, switch to Opus immediately (see fallback below).

#### RTSP + Opus — SELECTED (was runner-up, now primary)
- **Pros**: Excellent quality at very low bitrates, very CPU efficient encoder, much lower bandwidth, no known mediamtx compatibility issues
- **Cons**: Still lossy compression, marginal quality loss vs PCM, adds encoding CPU on Pi
- **When to use**: If PCM has any issues (mediamtx errors, high CPU, Wi-Fi dropouts), Opus at 96kbps is the immediate fallback
- **FFmpeg command**: `-acodec libopus -b:a 96k -f rtsp -rtsp_transport tcp`

#### RTSP + MP3 (Previous Setup — Not Recommended)
- **Pros**: Universal compatibility, proven working in the old setup
- **Cons**: The old config used 45kbps which is far too low — cuts off high-frequency bird detail. Even at 128kbps, MP3 introduces artifacts that PCM avoids entirely.
- **Old FFmpeg command**: `-acodec libmp3lame -b:a 45k -ac 2 -content_type 'audio/mpeg'`
- **Problems with old config**: 45kbps bitrate too low, `-ac 2` (stereo) wastes bandwidth and can introduce phase errors, `-content_type` unnecessary for RTSP

#### UDP/RTP + PCM
- **Pros**: Absolute lowest latency, zero compression
- **Cons**: Packet drops = audio gaps = missed bird detections, no recovery mechanism
- **Not recommended**: Outdoor Wi-Fi to a gazebo will have packet loss

---

## Original Pi Setup (Reference)

This documents how the Pi was originally configured, for context during the rebuild.

### Software Stack (Original)
1. **Raspberry Pi OS Bookworm** — base OS
2. **mediamtx v1.0.0** — RTSP server, installed to `/root/`
3. **ffmpeg** — captures USB mic audio, feeds to mediamtx
4. **BirdNET-Pi** (Nachtzuster fork) — bird detection (no longer needed, BirdNET-Go runs on Komodo)
5. **BirdNET-Go** (Docker) — was also running on Pi on port 8085 (no longer needed)

### mediamtx Configuration (Original)
- Binary and config at `/root/mediamtx` and `/root/mediamtx.yml`
- Ran as root via systemd service
- HLS was disabled in mediamtx.yml to avoid port 8888 conflict
- ffmpeg path was added to the `runOnInit` section of mediamtx.yml so the audio stream auto-starts with the service

### Original mediamtx systemd service
```ini
[Unit]
Wants=network.target
[Service]
ExecStart=/root/mediamtx /root/mediamtx.yml
[Install]
WantedBy=multi-user.target
```

### Original ffmpeg command
```bash
ffmpeg -report -v verbose -nostdin -f alsa -ac 1 -i hw:3 \
  -acodec libmp3lame -b:a 45k -ac 2 \
  -content_type 'audio/mpeg' \
  -f rtsp rtsp://192.168.0.136:8554/birdmic -rtsp_transport tcp
```

**Problems with original command**:
- `-b:a 45k` — bitrate far too low, loses high-frequency detail
- `-ac 2` — stereo is wasteful and can cause phase errors (BirdNET works best with mono)
- `-content_type 'audio/mpeg'` — unnecessary for RTSP
- `hw:3` — may change if USB devices are reordered after reboot

### Original BirdNET-Pi Settings
- Installed from: https://github.com/Nachtzuster/BirdNET-Pi
- Audio Card set to "Card2" (dummy — not actually used, RTSP was used instead)
- Web UI at: http://birdnetpi.local/ or http://192.168.0.136

### Original BirdNET-Go (Docker on Pi)
```bash
docker run -ti -d -p 8085:8080 --name birdnetgo \
  --env ALSA_CARD=3 --env TZ="America/Phoenix" \
  --device /dev/snd --restart unless-stopped \
  -v $HOME/birdnetgo/config:/config \
  -v $HOME/birdnetgo/data:/data \
  ghcr.io/tphakala/birdnet-go:latest
```

### Original BirdNET-Go Settings
- Threshold: 0.7
- Latitude: 32.465
- Longitude: -110.8922
- Thumbnails on Daily Summary: enabled
- Audio Capture: RTSP URL
- MQTT Broker: tcp://192.168.0.154:1883
- MQTT Topic: birdnet
- MQTT Username: birdnet
- MQTT Password: birdnet

### Reference Links Used in Original Setup
- mediamtx RTSP setup: https://github.com/mcguirepr89/BirdNET-Pi/discussions/1006#discussioncomment-6747450
- mediamtx systemd service: https://github.com/bluenviron/mediamtx?tab=readme-ov-file#linux
- ffmpeg auto-start via mediamtx.yml: https://github.com/tphakala/birdnet-go/discussions/224
- BirdNET-Pi install: https://github.com/Nachtzuster/BirdNET-Pi

---

## Rebuild Plan

### Phase 1: Remote Deep Clean of the Pi

Since physical access to the gazebo is inconvenient, we'll do an aggressive remote cleanup over SSH rather than re-flashing the SD card. The goal is to get the Pi as close to a fresh install as possible.

#### 1a. Inventory what's running
```bash
# See all running services
systemctl list-units --type=service --state=running

# Check for Docker containers
docker ps -a

# Check for BirdNET-Pi services
systemctl list-units --type=service | grep -i birdnet

# Check disk usage
df -h
du -sh /root/* /home/* /opt/* 2>/dev/null
```

#### 1b. Stop and disable all non-essential services
```bash
# Stop BirdNET-Pi services
sudo systemctl stop birdnet*
sudo systemctl disable birdnet*

# Stop old mediamtx (will reinstall fresh in Phase 2)
sudo systemctl stop mediamtx
sudo systemctl disable mediamtx

# Stop any other experimental services found in 1a
# sudo systemctl stop <service> && sudo systemctl disable <service>
```

#### 1c. Remove Docker entirely
```bash
# Stop all containers and remove them
docker stop $(docker ps -aq) 2>/dev/null
docker rm $(docker ps -aq) 2>/dev/null

# Remove all images, volumes, and networks
docker system prune -a --volumes -f

# Uninstall Docker engine (covers both official repo and distro package names)
sudo apt purge -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin docker.io containerd runc 2>/dev/null
sudo rm -rf /var/lib/docker /var/lib/containerd /etc/docker
sudo groupdel docker 2>/dev/null
```

#### 1d. Remove BirdNET-Pi
```bash
# Check for uninstall script first
ls /usr/local/share/birdnet/ 2>/dev/null
ls /home/*/BirdNET-Pi/ 2>/dev/null

# If uninstall script exists:
# sudo /usr/local/share/birdnet/uninstall.sh
# Otherwise manually remove:
sudo rm -rf /usr/local/share/birdnet /home/*/BirdNET-Pi /opt/birdnet* 2>/dev/null

# Remove BirdNET-Pi config and data
sudo rm -rf /home/*/birdnetgo 2>/dev/null
```

#### 1e. Remove old mediamtx and leftover files
```bash
# Remove old mediamtx binary and config
sudo rm -f /root/mediamtx /root/mediamtx.yml
sudo rm -f /etc/systemd/system/mediamtx.service
sudo systemctl daemon-reload

# Clean up other experiment leftovers in /root
ls -la /root/
# Remove anything that's not a dotfile (review before deleting)
```

#### 1f. Purge unnecessary packages and update OS
```bash
# Remove packages no longer needed
sudo apt purge -y $(dpkg -l | grep '^rc' | awk '{print $2}') 2>/dev/null
sudo apt autoremove -y --purge
sudo apt autoclean

# Update base OS to current
sudo apt update && sudo apt upgrade -y
```

#### 1g. Clean up old cron jobs and configs
```bash
# Check for experiment cron jobs
sudo crontab -l
crontab -l

# Remove any that aren't needed
# sudo crontab -e  (or crontab -e)

# Check /etc/cron.d/ for leftover jobs
ls /etc/cron.d/
```

#### 1h. Verify clean state
```bash
# Confirm only essential services remain
systemctl list-units --type=service --state=running

# Confirm Docker is gone
which docker  # should return nothing

# Confirm disk space is freed
df -h

# Verify USB mic is still detected
arecord -l
# Note the card and device number (e.g., hw:3,0)
# IMPORTANT: This number can change between reboots if USB devices change
```

### Phase 2: Install/Update mediamtx

#### 2a. Download latest mediamtx
```bash
cd /root
# Remove old version
rm -f mediamtx mediamtx.yml

# Download latest stable release (check https://github.com/bluenviron/mediamtx/releases)
# Pi 4/5 (arm64):
wget -c https://github.com/bluenviron/mediamtx/releases/download/v1.16.0/mediamtx_v1.16.0_linux_arm64.tar.gz -O - | sudo tar -xz
```
**NOTE**: v1.16.0 is current as of 2026-02-04. Check https://github.com/bluenviron/mediamtx/releases for newer versions before running.

#### 2b. Configure mediamtx.yml

Edit `/root/mediamtx.yml` with these key settings:

```yaml
# Disable protocols we don't need
hls: no          # Prevents port 8888 conflict
webrtc: no       # Not needed

# RTSP settings
rtsp: yes
rtspAddress: :8554

# Path configuration with auto-starting ffmpeg
paths:
  birdmic:
    runOnInit: >
      ffmpeg -nostdin
      -f alsa -acodec pcm_s16le -ac 1 -ar 48000 -i hw:3,0
      -ac 1 -acodec pcm_s16be
      -f rtsp -rtsp_transport tcp
      rtsp://localhost:$RTSP_PORT/$MTX_PATH
    runOnInitRestart: yes
```

**Key changes from original**:
- `-acodec pcm_s16le` — capture as PCM (was implicit before)
- `-ac 1` on input — request mono capture
- `-ac 1` on output — force mono output (the USB mic is natively stereo, so this downmixes to mono)
- `-ar 48000` — explicit 48kHz sample rate (matches BirdNET requirement exactly)
- `-acodec pcm_s16be` — output as PCM (was `libmp3lame` at 45kbps)
- No `-b:a` bitrate — PCM is uncompressed, bitrate doesn't apply
- Uses `$RTSP_PORT` and `$MTX_PATH` variables (mediamtx auto-substitutes these)
- `runOnInitRestart: yes` — auto-restarts ffmpeg if it crashes

**IMPORTANT**: The `hw:3,0` device number must match the actual USB mic. Run `arecord -l` to verify. Consider using a udev rule to pin the device name if it changes between reboots.

#### 2c. Create systemd service

```bash
sudo tee /etc/systemd/system/mediamtx.service >/dev/null << EOF
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

#### 2d. Test the RTSP stream (PCM checkpoint)

PCM over RTSP has known mediamtx compatibility concerns ([GitHub #1350](https://github.com/bluenviron/mediamtx/issues/1350)). Run these checks immediately after starting the service — if any fail, switch to Opus (see Fallback section below).

**Step 1: Check mediamtx logs for errors (immediate)**
```bash
sudo journalctl -u mediamtx --no-pager -n 30
# PASS: No errors, shows "is publishing to path" or similar
# FAIL: Codec errors, connection refused, crash/restart loops
```

**Step 2: Check CPU usage (wait 1-2 minutes)**
```bash
top -b -n 3 -d 2 | grep -E 'mediamtx|ffmpeg'
# PASS: Each process under 10% CPU
# FAIL: Sustained >20% CPU on either process → switch to Opus
```

**Step 3: Verify stream format with ffprobe**
```bash
# From the Pi:
ffprobe rtsp://localhost:8554/birdmic

# From another machine:
ffprobe rtsp://192.168.0.136:8554/birdmic
```
Expected output: `pcm_s16be, 48000 Hz, mono, s16, 768 kb/s`

**Step 4: Listen test (optional)**
```bash
# From another machine with speakers:
ffplay rtsp://192.168.0.136:8554/birdmic

# Or test with VLC: File > Open Network Stream > rtsp://192.168.0.136:8554/birdmic
```

**If any check fails → immediately switch to Opus** (see Fallback section below). Don't spend time debugging PCM issues — Opus at 96kbps is nearly lossless and has no known mediamtx compatibility problems.

### Phase 3: Configure BirdNET-Go on Komodo

Update BirdNET-Go's RTSP stream configuration to use the new clean stream.

**BirdNET-Go location**: Komodo CT 128 (192.168.0.179:8060)
**Web UI**: http://192.168.0.179:8060

#### Settings to verify/update:
- **Settings → Audio Capture → RTSP URL**: `rtsp://192.168.0.136:8554/birdmic`
- **Settings → Audio Capture → Transport**: TCP
- **Settings → Main → Threshold**: 0.7
- **Settings → Main → Latitude**: 32.4107
- **Settings → Main → Longitude**: -110.9361

#### Optional quality improvements in BirdNET-Go:
- **Enable High-Pass filter at ~500Hz** — removes wind/traffic rumble below bird song range (BirdNET-Go docs recommend 300-800Hz; 500-700Hz is a good default for road rumble)
- **Enable Low-Pass filter at ~12000Hz** — removes ultrasonic noise

**Note**: Verify the exact UI path for these equalizer settings in the BirdNET-Go web interface — the menu structure may vary by version.

### Phase 4: Verify End-to-End

1. **Check stream is running**: `ffprobe rtsp://192.168.0.136:8554/birdmic`
2. **Check BirdNET-Go is receiving**: Web UI at http://192.168.0.179:8060 should show the stream as healthy
3. **Check MQTT messages arriving**: Use MQTT Explorer add-on in HA to monitor the `birdnet` topic
4. **Wait for a detection**: Depending on time of day and bird activity, may take minutes to hours
5. **Compare detection rate**: After a day, compare detection count to previous setup

---

## Fallback: Switch to Opus (If PCM Has Issues)

If the PCM stream has any problems — mediamtx errors, high CPU, Wi-Fi stuttering, or dropouts — switch to Opus. This is the immediate fallback and should be tried before any other troubleshooting:

```yaml
# In mediamtx.yml, change the ffmpeg command:
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

Opus at 96kbps provides near-lossless audio quality at ~1/8th the bandwidth of PCM. This is the best compromise if network reliability is an issue.

---

## Potential Issue: USB Audio Device Numbering

The ALSA device number (`hw:3,0`) can change between reboots if USB devices are plugged in a different order. To prevent this:

### Option A: Use device name instead of number
```bash
# Find the device name
arecord -l
# Look for the card name, e.g., "USB Audio Device"
# Then use: -i plughw:CARD=Device,DEV=0 instead of hw:3,0
```

### Option B: Create a udev rule to pin the device
```bash
# Find the USB device attributes
udevadm info -a /dev/snd/controlC3 | grep -E 'idVendor|idProduct|serial'

# Create a udev rule
sudo tee /etc/udev/rules.d/99-usb-mic.rules >/dev/null << EOF
SUBSYSTEM=="sound", ATTRS{idVendor}=="XXXX", ATTRS{idProduct}=="YYYY", ATTR{id}="birdmic"
EOF

sudo udevadm control --reload-rules

# Then use: -i plughw:CARD=birdmic,DEV=0
```

---

## Quick Reference After Rebuild

| Item | Value |
|------|-------|
| **Pi Model** | Raspberry Pi 4 (arm64) |
| **Pi IP** | 192.168.0.136 |
| **Pi Location** | Gazebo |
| **RTSP Stream URL** | rtsp://192.168.0.136:8554/birdmic |
| **Stream Format** | Opus, 48kHz, Mono, 96kbps |
| **mediamtx Binary** | /root/mediamtx |
| **mediamtx Config** | /root/mediamtx.yml |
| **mediamtx Version** | v1.16.0 (as of 2026-02-04) |
| **mediamtx Service** | systemctl status mediamtx |
| **BirdNET-Go UI** | http://192.168.0.179:8060 |
| **BirdNET-Go Host** | Komodo CT 128 (192.168.0.179) |
| **MQTT** | Disabled (broker at 192.168.0.154:1883 if needed) |
| **Location** | 32.4107, -110.9361 (Tucson, AZ) |

### Troubleshooting Commands
```bash
# Check mediamtx service
sudo systemctl status mediamtx

# Check mediamtx logs
sudo journalctl -u mediamtx -f

# List audio devices
arecord -l

# Test mic recording directly
arecord -D hw:3,0 -f S16_LE -r 48000 -c 1 -d 5 test.wav
aplay test.wav

# Test RTSP stream
ffprobe rtsp://localhost:8554/birdmic

# Check what's using CPU
top -b -n 1 | head -20

# Check running services
systemctl list-units --type=service --state=running
```
