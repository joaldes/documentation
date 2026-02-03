# BirdNET-Pi LXC Installation Guide

**Created**: 2026-02-02
**Updated**: 2026-02-03
**Status**: Complete and operational

## Summary

BirdNET-Pi installed in a Proxmox LXC container (CT 122) using RTSP audio input. This documents the complete installation process, including LXC-specific workarounds discovered during setup.

## Final Configuration

| Setting | Value |
|---------|-------|
| Container ID | 122 |
| Hostname | birdnet-pi |
| IP Address | 192.168.0.52 |
| Storage | littlestorage (20GB root) |
| Memory | 4GB |
| Cores | 2 |
| OS | Debian 12 Bookworm 64-bit |
| RTSP Feed | `rtsp://192.168.0.136:8554/birdmic` |
| Location | 32.4107, -110.9361 (Tucson, AZ) |
| Web UI | http://192.168.0.52 |
| Data Partition | /dev/sde5 (250GB) mounted at /mnt/birdnet |

## Why LXC + RTSP (Not USB Passthrough)

- RTSP avoids complex USB audio passthrough to unprivileged containers
- Network-based audio is simpler and more reliable in LXC
- Existing RTSP microphone feed was already available
- Lower overhead than a full VM

---

## Phase 1: Create LXC Container

### 1.1 Download Debian 12 Template (on Proxmox host)
```bash
pveam update
pveam download local debian-12-standard_12.7-1_amd64.tar.zst
```

### 1.2 Create Container
```bash
pct create 122 local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst \
  --hostname birdnet-pi \
  --storage littlestorage \
  --rootfs littlestorage:20 \
  --cores 2 \
  --memory 4096 \
  --swap 2048 \
  --net0 name=eth0,bridge=vmbr0,gw=192.168.0.1,ip=192.168.0.52/24 \
  --onboot 1 \
  --start 0 \
  --unprivileged 1 \
  --features nesting=1
```

### 1.3 Configure Container
Add to `/etc/pve/lxc/122.conf`:
```conf
# AppArmor disabled (per infrastructure standard)
lxc.apparmor.profile: unconfined

# CPU capabilities for TensorFlow SSE4.1
lxc.cgroup2.devices.allow: a
lxc.cap.drop:
```

### 1.4 Add Shared Storage Mount (optional)
If using a dedicated data partition:
```conf
mp0: /mnt/birdnet/birdnet-pi,mp=/mnt/birdnet
```

### 1.5 Start Container
```bash
pct start 122
```

---

## Phase 2: Prepare Container Environment

### 2.1 Initial Setup (inside container via `pct exec 122 -- bash`)
```bash
# Set root password (standard: password)
echo "root:password" | chpasswd

# Update system
apt update && apt upgrade -y

# Install prerequisites
apt install -y curl git sudo python3-venv ffmpeg alsa-utils unattended-upgrades apt-listchanges

# Create birdnet user
useradd -m -s /bin/bash birdnet
echo "birdnet:password" | chpasswd
usermod -aG sudo birdnet

# Enable passwordless sudo (required for installer)
echo "birdnet ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/birdnet

# Enable SSH
systemctl enable ssh
systemctl start ssh

# Configure auto-updates
echo -e 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";' > /etc/apt/apt.conf.d/20auto-upgrades
```

---

## Phase 3: Install BirdNET-Pi

### 3.1 Clone Repository (as birdnet user)
```bash
su - birdnet
git clone https://github.com/Nachtzuster/BirdNET-Pi.git ~/BirdNET-Pi
```

### 3.2 Run Installer
```bash
~/BirdNET-Pi/scripts/install_birdnet.sh
```

**Note**: The installer takes 15-30 minutes and installs:
- TensorFlow Lite (x86_64 wheel)
- Python dependencies (numpy, scipy, librosa, etc.)
- Caddy web server
- PHP 8.2 with FPM
- Icecast2 for audio streaming
- All BirdNET-Pi systemd services

### 3.3 Reboot After Installation
```bash
sudo reboot
```

---

## Phase 4: Post-Installation Fixes (LXC-Specific)

### 4.1 Fix Caddy Service Conflict (CRITICAL)

BirdNET-Pi installs **two** Caddy services that conflict:
- `caddy.service` - Loads from `/etc/caddy/Caddyfile` (correct)
- `caddy-api.service` - Uses `--resume` flag with cached config (incorrect)

**Problem**: `caddy-api` sometimes wins the race to port 80, showing "Caddy works!" default page instead of BirdNET-Pi.

**Solution**: Disable and mask caddy-api:
```bash
systemctl stop caddy-api
systemctl disable caddy-api
systemctl mask caddy-api
systemctl restart caddy
```

### 4.2 Install phpSysInfo (optional, for Tools → System Info)
```bash
apt install -y phpsysinfo
ln -sf /usr/share/phpsysinfo /home/birdnet/BirdSongs/Extracted/phpsysinfo
```

### 4.3 Verify Services Running
```bash
systemctl status birdnet_analysis birdnet_recording birdnet_log birdnet_stats caddy php8.2-fpm icecast2
```

All should show `active (running)`.

---

## Phase 5: Configure RTSP Audio

### 5.1 Access Web UI
- URL: http://192.168.0.52
- Default login: birdnet / (empty password)

### 5.2 Configure RTSP Stream
1. Go to **Tools** → **Settings** → **Advanced Settings**
2. Find **RTSP Stream** field
3. Enter: `rtsp://192.168.0.136:8554/birdmic`
4. Click **Update Settings**
5. Go to **Tools** → **Services** → **Restart Core Services**

### 5.3 Configure Location
1. Go to **Tools** → **Settings**
2. Set Latitude: `32.4107`
3. Set Longitude: `-110.9361`
4. Save settings

---

## Phase 6: Shared Storage Setup (Optional)

To store bird detection data on a dedicated partition shared with BirdNET-Go:

### 6.1 Create Partition (on Proxmox host)
```bash
# Create 250GB partition on sde (adjust as needed)
parted /dev/sde --script mkpart primary ext4 15.3TB 15.55TB
partprobe /dev/sde

# Format and label
mkfs.ext4 -L birdnet-data /dev/sde5

# Create mount point and fstab entry
mkdir -p /mnt/birdnet
echo 'LABEL=birdnet-data /mnt/birdnet ext4 defaults 0 2' >> /etc/fstab
mount /mnt/birdnet

# Create subdirectories
mkdir -p /mnt/birdnet/birdnet-pi /mnt/birdnet/birdnet-go
chown -R 100000:100000 /mnt/birdnet/birdnet-pi  # For unprivileged CT 122
```

### 6.2 Add Mount to Container
Add to `/etc/pve/lxc/122.conf` (in main section, NOT in [vzdump]):
```conf
mp0: /mnt/birdnet/birdnet-pi,mp=/mnt/birdnet
```

### 6.3 Configure BirdNET-Pi to Use Shared Storage

**Important**: Keep web files at original location, symlink only data directories.

Inside container:
```bash
# Create data directory symlinks to shared storage
mkdir -p /mnt/birdnet/Extracted /mnt/birdnet/Processed /mnt/birdnet/StreamData /mnt/birdnet/By_Date /mnt/birdnet/Charts
chown -R birdnet:birdnet /mnt/birdnet

# Symlink data directories (NOT web files)
ln -sf /mnt/birdnet/By_Date /home/birdnet/BirdSongs/Extracted/By_Date
ln -sf /mnt/birdnet/Charts /home/birdnet/BirdSongs/Extracted/Charts
```

**Why not move everything?** The PHP web files use relative includes (`scripts/common.php`) that break when the web root changes. Keeping web files at `/home/birdnet/BirdSongs/Extracted` with symlinks to data directories is the cleanest solution.

---

## Directory Structure

```
/home/birdnet/
├── BirdNET-Pi/              # Application code (git repo)
│   ├── birdnet.conf         # Main configuration
│   ├── homepage/            # Web UI files
│   │   ├── index.php
│   │   ├── views.php
│   │   ├── style.css
│   │   └── images/
│   └── scripts/             # PHP scripts and utilities
│       ├── common.php
│       ├── birdnet_analysis.py
│       └── ...
└── BirdSongs/               # Data directory (RECS_DIR)
    ├── Extracted/           # Web root for Caddy
    │   ├── index.php → ../BirdNET-Pi/homepage/index.php
    │   ├── views.php → ../BirdNET-Pi/homepage/views.php
    │   ├── scripts → ../BirdNET-Pi/scripts
    │   ├── images → ../BirdNET-Pi/homepage/images
    │   ├── static → ../BirdNET-Pi/homepage/static
    │   ├── style.css → ../BirdNET-Pi/homepage/style.css
    │   ├── phpsysinfo → /usr/share/phpsysinfo
    │   ├── By_Date/         # Detection clips by date (or symlink to /mnt/birdnet)
    │   └── Charts/          # Generated charts (or symlink to /mnt/birdnet)
    ├── Processed/           # Processed audio files
    └── StreamData/          # Live stream temporary data
```

---

## Troubleshooting

### "Caddy works!" Page Instead of BirdNET-Pi
**Cause**: `caddy-api.service` is overriding `caddy.service`
```bash
systemctl stop caddy-api
systemctl mask caddy-api
systemctl restart caddy
```

### 500 Internal Server Error
**Cause**: PHP can't find included files
```bash
# Ensure scripts symlink exists in web root
ls -la /home/birdnet/BirdSongs/Extracted/scripts
# Should point to /home/birdnet/BirdNET-Pi/scripts

# If missing:
ln -sf /home/birdnet/BirdNET-Pi/scripts /home/birdnet/BirdSongs/Extracted/scripts
```

### Page Loads Nested/Recursive
**Cause**: Missing PHP symlinks in Extracted directory

All these files must exist in `/home/birdnet/BirdSongs/Extracted/`:
```bash
cd /home/birdnet/BirdSongs/Extracted
ln -sf /home/birdnet/BirdNET-Pi/homepage/index.php index.php
ln -sf /home/birdnet/BirdNET-Pi/homepage/views.php views.php
ln -sf /home/birdnet/BirdNET-Pi/homepage/images images
ln -sf /home/birdnet/BirdNET-Pi/homepage/static static
ln -sf /home/birdnet/BirdNET-Pi/homepage/style.css style.css
ln -sf /home/birdnet/BirdNET-Pi/scripts scripts
ln -sf /home/birdnet/BirdNET-Pi/scripts/overview.php overview.php
ln -sf /home/birdnet/BirdNET-Pi/scripts/history.php history.php
ln -sf /home/birdnet/BirdNET-Pi/scripts/spectrogram.php spectrogram.php
ln -sf /home/birdnet/BirdNET-Pi/scripts/todays_detections.php todays_detections.php
ln -sf /home/birdnet/BirdNET-Pi/scripts/stats.php stats.php
ln -sf /home/birdnet/BirdNET-Pi/scripts/play.php play.php
ln -sf /home/birdnet/BirdNET-Pi/scripts/weekly_report.php weekly_report.php
```

### TensorFlow "invalid opcode" Error
**Cause**: CPU doesn't support SSE4.1
```bash
# Check CPU flags
grep -o 'sse4_1' /proc/cpuinfo
```
If missing, need to configure Proxmox CPU model with SSE4.1 support.

### RTSP Stream Not Working
```bash
# Test RTSP manually
ffmpeg -rtsp_transport tcp -i rtsp://192.168.0.136:8554/birdmic -t 5 -f wav test.wav
```

### dpkg Interrupted
```bash
dpkg --configure -a
apt install -f
```

### Apt Lock Files
```bash
pkill -9 apt
rm -f /var/lib/dpkg/lock-frontend /var/lib/apt/lists/lock
dpkg --configure -a
```

---

## Services Reference

| Service | Purpose | Command |
|---------|---------|---------|
| birdnet_analysis | Bird detection AI | `systemctl status birdnet_analysis` |
| birdnet_recording | Audio capture | `systemctl status birdnet_recording` |
| birdnet_log | Logging service | `systemctl status birdnet_log` |
| birdnet_stats | Statistics | `systemctl status birdnet_stats` |
| caddy | Web server | `systemctl status caddy` |
| php8.2-fpm | PHP processor | `systemctl status php8.2-fpm` |
| icecast2 | Audio streaming | `systemctl status icecast2` |

Restart all core services:
```bash
systemctl restart birdnet_analysis birdnet_recording caddy php8.2-fpm
```

---

## Key Files

| File | Purpose |
|------|---------|
| `/home/birdnet/BirdNET-Pi/birdnet.conf` | Main configuration (RECS_DIR, location, etc.) |
| `/etc/caddy/Caddyfile` | Web server configuration |
| `/etc/systemd/system/birdnet_*.service` | Systemd service files |
| `/var/log/php8.2-fpm.log` | PHP error logs |

---

## Sources

- [Nachtzuster/BirdNET-Pi](https://github.com/Nachtzuster/BirdNET-Pi) - Active fork used for this install
- [x86 and VMs Discussion](https://github.com/mcguirepr89/BirdNET-Pi/discussions/251)
- [RTSP Stream Configuration](https://github.com/mcguirepr89/BirdNET-Pi/wiki/Using-an-internet-stream-as-input-(RTSP-and-HTTP))
