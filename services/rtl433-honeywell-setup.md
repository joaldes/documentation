# RTL-433 Honeywell 5800-Series Sensor Integration

**Last Updated**: 2026-01-30
**Related Systems**: Home Assistant, RTL-SDR, MQTT

## Overview

Integration of Honeywell 5800-series wireless security sensors (door/window sensors) with Home Assistant using RTL-SDR dongles and the rtl_433 add-on.

## Hardware

### RTL-SDR Dongles
Two RTL-SDR dongles connected via powered USB hub to Proxmox host (192.168.0.151):

| Serial Number | Frequency | Purpose | Antenna |
|---------------|-----------|---------|---------|
| 00000001 | 345 MHz | Honeywell 5800-series | 20cm (longer) |
| 00000002 | 915 MHz | Ecowitt WH51 soil moisture | 13cm (shorter) |

**Important**: Device index (0, 1) can change after reboot. Always use serial number format (`:00000001`) in configs.

### Antennas
- **345 MHz**: Requires ~21.7cm quarter-wave antenna (20cm is close enough)
- **915 MHz**: Requires ~8.2cm quarter-wave antenna (13cm works)
- Antenna length matters significantly for weak signal reception

### Sensors
- **Honeywell 5816WMWH**: Door/window sensors on 345 MHz
- Transmit on open/close events
- Supervisory heartbeat every 60-70 minutes
- Protocol 70 in rtl_433

## Software Stack

### Home Assistant Add-ons
- **rtl_433** - Main RF decoder
- **rtl_433 Auto Discovery** - MQTT auto-discovery for HA

### Config File Locations (in HA)
- `/config/rtl/rtl_433_honeywell_5816wmwh.conf`
- `/config/rtl/rtl_433_ecowitt_wh51_soil.conf`

## Configuration

### Honeywell 345 MHz Config
```
# RTL-SDR Device Selection (use serial number, not index)
device            :00000001

# Frequency
frequency         345M
sample_rate       250000

# Gain (40 recommended for weak signals, 0 = auto)
gain              40

# Protocol 70 = Honeywell Security
protocol          70

# Metadata
report_meta       level,time:iso:utc

# MQTT Output
output            mqtt://core-mosquitto:1883,user=mqtt,pass=mqtt,retain=1
output            kv
```

### WH51 915 MHz Config
```
device            :00000002
frequency         915000000
sample_rate       250000
gain              0
protocol          142
report_meta       time
output            mqtt://core-mosquitto:1883,user=mqtt,pass=mqtt,retain=1
output            kv
```

## Troubleshooting

### Common Issues

#### 1. "Could not find device with serial 'XXXXXXXX'"
**Cause**: Trailing spaces in config file after serial number
**Fix**: Remove all trailing whitespace from the `device` line

#### 2. "PLL not locked!" Warning
**Cause**: R820T tuner struggling at 345 MHz (lower edge of range)
**Impact**: Usually benign, clears after startup
**Fix**: If persistent, try slightly different frequency (344.9M or 345.1M)

#### 3. Sensors Work Intermittently
**Causes**:
- Wrong antenna on 345 MHz dongle (need longer 20cm antenna)
- Gain too low (try `gain 40` instead of `gain 0`)
- Device index changed after reboot (use serial number instead)

**Diagnosis**: Use analyzer mode to verify RF reception:
```
device            :00000001
frequency         345M
gain              40
protocol          0
analyze_pulses    true
output            kv
```

#### 4. No Pulses in Analyzer Mode
**Cause**: Wrong dongle has the 345 MHz antenna
**Fix**: Try the other serial number, or physically swap antennas

#### 5. Sensors Not Registering After Reboot
**Cause**: Device enumeration order changed
**Fix**: Always use serial number format (`:00000001`) not device index (`device 0`)

### Verify Hardware Serials
From Proxmox host:
```bash
lsusb -v 2>/dev/null | grep -A15 'RTL2838' | grep -E 'Bus|iSerial'
```

Or with sshpass:
```bash
SSHPASS='claudepassword' sshpass -e ssh claude@192.168.0.151 "lsusb -v 2>/dev/null | grep -A10 'RTL2838'"
```

### Check Add-on Logs
Look for:
- `Found Rafael Micro R820T tuner` - dongle detected
- `[SDR] Using device X: ... SN: XXXXXXXX` - confirms which serial is in use
- `Analyzing pulses...` - RF being received (analyzer mode)

### MQTT Topics
- Events: `rtl_433/9b13b3f4-rtl433/events`
- Devices: `rtl_433/9b13b3f4-rtl433/devices/...`
- States: `rtl_433/9b13b3f4-rtl433/states`

## Frequency Reference

| Sensor Type | Frequency | Protocol | Notes |
|-------------|-----------|----------|-------|
| Honeywell 5800-series | 345.000 MHz | 70 | US security sensors |
| Honeywell (alt) | 345.875 MHz | 70 | Some variants |
| Ecowitt WH51 | 915.000 MHz | 142 | ISM band soil sensors |

## Known Working Sensor IDs
- Sensor 1: ID 396030 (front door)
- Sensor 2: ID [TBD]

## USB Passthrough

The RTL-SDR dongles are passed through from Proxmox host to Home Assistant VM/container. If dongles stop working:

1. Check USB hub power
2. Verify passthrough in Proxmox VM/LXC config
3. Restart Home Assistant
4. Check `dmesg` on host for USB disconnect messages

## References
- rtl_433 protocols: https://github.com/merbanan/rtl_433
- Honeywell 5800 protocol: Protocol 70 in rtl_433
- R820T tuner range: 24-1766 MHz (works best 50-1500 MHz)
