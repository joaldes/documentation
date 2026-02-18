# Z-Wave USB Passthrough Stale Device Number

**Last Updated**: 2026-02-16
**Related Systems**: Container 108 (zwave-js-ui, 192.168.0.153), Proxmox Host (Shipyard)

## Summary
Container 108 (zwave-js-ui) was stopped and couldn't access the Zooz 800 Z-Wave Stick because the `dev0` USB passthrough in the LXC config pointed to a stale USB device number (`003/007` instead of `003/014`). Updated the config and started the container.

## Problem
The Z-Wave JS UI container (108) was stopped and the USB passthrough was misconfigured. The LXC config had `dev0: /dev/bus/usb/003/007`, but the Zooz 800 Z-Wave Stick had been re-enumerated to Bus 003 Device 014. USB device numbers are dynamic and change on replug or reboot.

## Root Cause
USB device numbers assigned by the kernel (`/dev/bus/usb/BBB/DDD`) are not stable — they increment each time a device is connected. The `dev0` line in the Proxmox LXC config uses this unstable path, so it goes stale whenever the stick gets a new device number.

## Solution
Updated the `dev0` line in `/etc/pve/lxc/108.conf` to the current device number and started the container.

## Implementation Details

### Steps Performed
1. Identified the Z-Wave stick on the host:
   ```bash
   lsusb
   # Bus 003 Device 014: ID 1a86:55d4 QinHeng Electronics 800 Z-Wave Stick

   ls -la /dev/serial/by-id/
   # usb-Zooz_800_Z-Wave_Stick_533D004242-if00 -> ../../ttyACM0
   ```

2. Updated LXC config:
   ```bash
   sed -i 's|dev0: /dev/bus/usb/003/007|dev0: /dev/bus/usb/003/014|' /etc/pve/lxc/108.conf
   ```

3. Started the container:
   ```bash
   pct start 108
   ```

### Key Files Modified
- `/etc/pve/lxc/108.conf` — updated `dev0` from `/dev/bus/usb/003/007` to `/dev/bus/usb/003/014`

### Existing Stable Passthrough (Already Configured)
The config also has bind mounts that use stable paths — these were already correct and didn't need changes:
```
lxc.mount.entry: /dev/serial/by-id  dev/serial/by-id  none bind,optional,create=dir
lxc.mount.entry: /dev/ttyACM0       dev/ttyACM0       none bind,optional,create=file
```

## Verification
```bash
# Device visible inside container
pct exec 108 -- ls -la /dev/ttyACM0
# crw-rw---- 1 root dialout 166, 0 Feb 17 16:59 /dev/ttyACM0

# Stable symlink present
pct exec 108 -- ls -la /dev/serial/by-id/
# usb-Zooz_800_Z-Wave_Stick_533D004242-if00 -> ../../ttyACM0

# Web UI responding
curl -s -o /dev/null -w '%{http_code}' http://192.168.0.153:8091/
# 200
```

## Troubleshooting
- **Container fails to start after reboot**: The `dev0` device number may have changed again. Run `lsusb` on the host to find the current device number for the Z-Wave stick (ID `1a86:55d4`) and update `dev0` in `/etc/pve/lxc/108.conf`.
- **Z-Wave stick not responding inside container**: The bind mounts (`/dev/ttyACM0`, `/dev/serial/by-id`) are more reliable than `dev0`. Configure zwave-js-ui to use `/dev/serial/by-id/usb-Zooz_800_Z-Wave_Stick_533D004242-if00` as the serial port path for maximum stability.
