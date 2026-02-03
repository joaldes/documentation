# BirdNET-Go Docker Setup

**Created**: 2026-02-03
**Updated**: 2026-02-03
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

## BirdNET-Go vs BirdNET-Pi

| Feature | BirdNET-Go | BirdNET-Pi |
|---------|------------|------------|
| Deployment | Docker container | Native LXC install |
| Complexity | Simple | Complex |
| Web UI | Modern, minimal | Full-featured, classic |
| Maintenance | Actively maintained | Community fork |
| Setup Time | ~5 minutes | 30-45 minutes |
| Resource Usage | Lower | Higher |
| Container | CT 128 (Komodo) | CT 122 (dedicated) |
| Port | 8060 | 80 |

Both are running simultaneously, sharing the same RTSP audio feed and storing data on the shared `/mnt/birdnet` partition.

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

BirdNET-Go and BirdNET-Pi share a dedicated partition:

```
/mnt/birdnet (250GB partition - /dev/sde5)
├── birdnet-pi/      # Mounted in CT 122
│   ├── By_Date/
│   ├── Charts/
│   └── ...
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

## Sources

- [tphakala/birdnet-go](https://github.com/tphakala/birdnet-go) - Official repository
- [Docker Hub / GHCR](https://ghcr.io/tphakala/birdnet-go) - Container images
