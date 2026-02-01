# RTL-433 Honeywell 5800-Series Sensor Integration

**Last Updated**: 2026-01-31
**Related Systems**: Home Assistant, RTL-SDR, MQTT

## Overview

Integration of Honeywell 5800-series wireless security sensors (door/window sensors) with Home Assistant using RTL-SDR dongles and the rtl_433 add-on.

## Hardware

### RTL-SDR Dongles
Two RTL-SDR dongles connected via powered USB hub to Proxmox host (192.168.0.151), passed through to Home Assistant VM:

| Serial Number | Frequency | Purpose | Antenna |
|---------------|-----------|---------|---------|
| 00000001 | 345 MHz | Honeywell 5800-series | 20cm (longer) |
| 00000002 | 915 MHz | Ecowitt WH51 soil moisture | 13cm (shorter) |

**Important**: Device index (0, 1) can change after reboot. Always use serial number format (`:00000001`) in configs.

### Antennas
- **345 MHz**: Requires ~21.7cm quarter-wave antenna (20cm is close enough)
- **915 MHz**: Requires ~8.2cm quarter-wave antenna (13cm works)
- Antenna length matters but mismatched antennas will still receive (just reduced efficiency)
- Different connector types on dongles - can swap whip portions but not bases

### Sensors
- **Honeywell 5816WMWH**: Door/window sensors on 345 MHz
- Transmit on open/close events (multiple burst transmissions per event)
- Supervisory heartbeat every 70-90 minutes
- Protocol 70 in rtl_433
- **No visible LED** - cannot visually confirm transmission (verify via control panel or rtl_433 logs)

## Infrastructure

### Home Assistant
- **Type**: KVM VM on Proxmox with USB passthrough
- **IP**: 192.168.0.154:8123
- **Credentials**: hassio / hassiopassword
- **USB Passthrough**: Both RTL-SDR dongles passed through to VM

### Proxmox Host
- **IP**: 192.168.0.151
- **DVB Modules**: Must be blacklisted (see setup below)

## Proxmox Host Setup

### Blacklist DVB Kernel Modules (Required)
The Linux kernel loads DVB-T TV tuner drivers that claim RTL-SDR devices. Blacklist them:

```bash
cat >> /etc/modprobe.d/blacklist-rtl.conf << 'EOF'
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2832_sdr
blacklist dvb_usb_v2
blacklist dvb_core
EOF

update-initramfs -u
reboot
```

**Verify modules not loaded:**
```bash
lsmod | grep -E 'dvb|rtl28'
```

### Verify Dongles Detected
```bash
lsusb | grep RTL
lsusb -v -d 0bda:2838 2>/dev/null | grep -E "Bus|iSerial"
```

## Configuration

### Honeywell 345 MHz Config
File: `/config/rtl/rtl_433_honeywell_5816wmwh.conf`
```
# Honeywell 5800-series door/window sensors

device            :00000001
frequency         345M
sample_rate       250000
gain              40

protocol          70
report_meta       level,time:iso:utc

output            mqtt://core-mosquitto:1883,user=mqtt,pass=mqtt,retain=1
output            kv
```

**Broader frequency coverage** (catches 345.000 and 345.875 MHz variants):
```
frequency         345M
sample_rate       2048000         # 2 MHz bandwidth covers 344-346 MHz
```

### WH51 915 MHz Config
File: `/config/rtl/rtl_433_ecowitt_wh51_soil.conf`
```
# ECOWITT WH51 soil moisture sensors

device            :00000002
frequency         915000000
sample_rate       250000

protocol          142
report_meta       time

output            mqtt://core-mosquitto:1883,user=mqtt,pass=mqtt,retain=1,devices=rtl_433[/model][/id]
output            kv
```

### Single-Dongle Frequency Hopping (Backup)
If one dongle fails, use frequency hopping on the working dongle:
```
device            :00000002
frequency         345M
frequency         915M
hop_interval      30
protocol          70
protocol          142
gain              40
sample_rate       250000
output            mqtt://core-mosquitto:1883,user=mqtt,pass=mqtt,retain=1
output            kv
```

## Troubleshooting

### "usb_claim_interface error -6"
**Cause**: Something else is claiming the USB device
**Checks**:
1. DVB kernel modules loaded: `lsmod | grep dvb`
2. Device in use by VM: `fuser -v /dev/bus/usb/003/*`
3. HA add-ons still running

**Fix**: Blacklist DVB modules (see Proxmox Host Setup above)

### "Could not find device with serial 'XXXXXXXX'"
**Cause**: Trailing spaces in config file after serial number
**Fix**: Remove all trailing whitespace from the `device` line

### "PLL not locked!" Warning
**Cause**: R820T tuner at 345 MHz (lower edge of comfortable range)
**Impact**: Usually benign, clears after startup
**Fix**: If persistent, try 344.9M or 345.1M

### Sensors Work Intermittently
**Causes**:
- Gain too low (try `gain 40`)
- Device index changed after reboot (use serial number)
- Weak signal / distance

**Diagnosis - Analyzer mode**:
```
protocol          0
analyze_pulses    true
```

### One Dongle Not Receiving
**Test dongle hardware** on Windows laptop:
1. Install SDR# from https://airspy.com/download/
2. Install Zadig drivers: https://zadig.akeo.ie/
3. Run SDR#, select RTL-SDR USB, tune to FM radio (100 MHz)
4. Working dongle shows signals in waterfall

**Test on Proxmox host** (stop HA first):
```bash
rtl_test -d 0 -t
rtl_test -d 1 -t
```

### Verify USB Passthrough
Check what's using USB devices:
```bash
fuser -v /dev/bus/usb/003/*
```
Should show `kvm` if passed through to HA VM.

## Frequency Reference

| Frequency | Bandwidth | Coverage |
|-----------|-----------|----------|
| 345M + 250k sample | ±125 kHz | 344.875 - 345.125 MHz |
| 345M + 1024k sample | ±512 kHz | 344.5 - 345.5 MHz |
| 345M + 2048k sample | ±1 MHz | 344 - 346 MHz |

| Sensor Type | Frequency | Protocol |
|-------------|-----------|----------|
| Honeywell 5800-series | 345.000 MHz | 70 |
| Honeywell (alt) | 345.875 MHz | 70 |
| Ecowitt WH51 | 915.000 MHz | 142 |

## Known Sensor IDs

| Location | Sensor ID (hex) | Sensor ID (dec) | Status |
|----------|-----------------|-----------------|--------|
| Laundry room | 60afe | 396030 | Working |
| Front door | TBD | TBD | Not transmitting |

## MQTT Topics
- Events: `rtl_433/9b13b3f4-rtl433/events`
- Devices: `rtl_433/9b13b3f4-rtl433/devices/...`
- States: `rtl_433/9b13b3f4-rtl433/states`

## References
- rtl_433 protocols: https://github.com/merbanan/rtl_433
- Honeywell 5800 protocol: Protocol 70
- R820T tuner range: 24-1766 MHz (works best 50-1500 MHz)
- Zadig USB drivers: https://zadig.akeo.ie/
- SDR# software: https://airspy.com/download/
