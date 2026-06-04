# LXC USB Passthrough — Stable Device Mapping

**Last Updated**: 2026-06-03
**Related Systems**: All Proxmox LXC containers using USB devices (Z-Wave, Zigbee, RTL-SDR, etc.)

## Summary

LXC containers that pass through USB devices via the `dev0:` config option (which pins to a specific bus/device number like `/dev/bus/usb/003/014`) will fail to start after any reboot or hot-replug, because USB bus/device numbers are not stable. The fix is to remove the `dev0:` line and rely on `lxc.mount.entry` bindings to stable paths under `/dev/serial/by-id` and the `/dev/ttyACMx` device, which the container already gets.

This is a recurring class of failure — see [incidents/2026-02-16-zwave-usb-passthrough-stale.md](../incidents/2026-02-16-zwave-usb-passthrough-stale.md) for the first occurrence (which was "fixed" by updating the stale number rather than removing it). That workaround guaranteed the recurrence on 2026-06-03. This guide documents the **permanent** fix.

## Problem / Goal

After the Proxmox host rebooted on 2026-06-02, CT 108 (`zwave-js-ui`, 192.168.0.153:8091) failed to start. `pct start 108` reported:

```
Device /dev/bus/usb/003/014 does not exist
```

The Zooz 800 Z-Wave Stick had moved from bus 003 device 014 to bus 003 device 007 on reboot, and the container config was pinned to the old path.

## Solution

Remove the stale `dev0:` line from the container config. The container already had correct stable passthrough configured via `lxc.mount.entry` lines bound to `/dev/serial/by-id` and `/dev/ttyACM0`, which **do** survive renumbering. The `dev0:` line was redundant and harmful.

## Implementation Details

### Diagnosis

1. Confirm the container is stopped and check the config:
   ```bash
   sudo pct status 108
   sudo pct config 108
   ```

   Look for a `dev0:` line that references `/dev/bus/usb/<bus>/<device>`.

2. Find the actual USB device path (stable form):
   ```bash
   ls /dev/serial/by-id/
   # e.g. usb-Zooz_800_Z-Wave_Stick_533D004242-if00 -> ../../ttyACM0

   lsusb | grep -iE "silicon labs|nortek|aeotec|zooz|qinheng"
   ```

3. Confirm the config already has stable mount entries:
   ```
   lxc.mount.entry: /dev/serial/by-id  dev/serial/by-id  none bind,optional,create=dir
   lxc.mount.entry: /dev/ttyACM0       dev/ttyACM0       none bind,optional,create=file
   ```

   If these are present, the `dev0:` line is redundant — proceed to remove.

### Fix

```bash
sudo pct set 108 --delete dev0
sudo pct start 108
sudo pct status 108
```

Verify inside the container:
```bash
sudo pct exec 108 -- ls -l /dev/ttyACM0 /dev/serial/by-id/
```

Verify the service:
```bash
curl -o /dev/null -w "%{http_code}\n" http://<container-ip>:<port>/
```

## Why This Works

USB bus/device numbers are assigned by enumeration order at boot, which depends on hub/port detection timing and isn't deterministic. The same physical stick can be `/dev/bus/usb/003/007` after one boot and `/dev/bus/usb/003/014` after another.

The kernel provides stable identifiers:
- `/dev/serial/by-id/usb-<vendor>_<product>_<serial>-if00` — symlink keyed on USB vendor/product/serial, stable across reboots and replugs.
- `/dev/ttyACMx` / `/dev/ttyUSBx` — numerical but assigned per-device-class; usually stable on systems with one device of each type, but not guaranteed.

The `lxc.mount.entry` approach binds these stable paths into the container's namespace. The `dev0:` shortcut in `/etc/pve/lxc/<CTID>.conf` only pins the raw USB bus/device path and offers no stability benefit.

## Verification

After applying the fix:
- `pct start <CTID>` succeeds
- The service inside the container starts and is reachable on its network port
- The device exists at the expected path inside the container (`ls -l /dev/ttyACM0` returns a character device)
- Reboot the host and confirm the container auto-starts (`onboot: 1`) without intervention

## Troubleshooting

**Container still won't start after removing `dev0:`**: check that the `lxc.mount.entry` lines reference the correct device name for your stick. Some sticks show as `ttyUSB0` (USB-serial) instead of `ttyACM0` (CDC ACM). Update the mount entry to match. Run `dmesg | tail` after plugging the stick to see which device file the kernel created.

**Multiple devices of the same model**: bind `/dev/serial/by-id` instead of a fixed `/dev/ttyACMx` and have the service inside the container pick by serial number from the by-id symlinks.

**Container started but the service doesn't see the device**: ensure the container has `lxc.cgroup2.devices.allow: c 166:* rwm` (ACM) or `c 188:* rwm` (USB-serial) in the config. These device-class allowances are separate from the mount entry and both are required.

## Prevention

When creating any LXC that needs a USB device:
1. Use `lxc.mount.entry` for the device path (`/dev/ttyACMx` or `/dev/ttyUSBx`)
2. Also bind `/dev/serial/by-id` so the container has the stable symlinks
3. Add the appropriate `lxc.cgroup2.devices.allow` for the device class major number
4. **Do NOT use `dev0:` for USB devices** — only safe for PCI passthrough where bus/device IS stable

## Affected Containers (audit checklist)

Any LXC with USB passthrough should be checked for stale `dev0:` lines after a host reboot:

```bash
ssh claude@192.168.0.151 'for ct in $(sudo pct list | tail -n +2 | awk "{print \$1}"); do
  grep -l "^dev[0-9]*:.*bus/usb" /etc/pve/lxc/$ct.conf 2>/dev/null && echo "  ↑ CT $ct has bus/usb dev passthrough"
done'
```

Known containers using USB passthrough (verify after each host reboot):
- CT 108 — `zwave-js-ui` — Zooz 800 Z-Wave Stick (fixed 2026-06-03)
