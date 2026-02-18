# Uptime Kuma Iframe Blocked in Home Assistant Dashboard

**Last Updated**: 2026-02-18
**Related Systems**: Uptime Kuma (Container 114, 192.168.0.44), Home Assistant (VM 100)

## Summary
Uptime Kuma could not load in a Home Assistant iframe panel due to the `X-Frame-Options: SAMEORIGIN` header. Resolved by setting the built-in `UPTIME_KUMA_DISABLE_FRAME_SAMEORIGIN` environment variable — no reverse proxy needed.

## Problem
Embedding Uptime Kuma in a Home Assistant dashboard iframe was blocked by the browser. Uptime Kuma sends `X-Frame-Options: SAMEORIGIN` by default, preventing cross-origin iframe embedding.

## Solution
Uptime Kuma supports a native environment variable to disable this header. Added it to the systemd service file and restarted.

## Implementation Details

### Steps Performed
1. Identified Uptime Kuma runs as a systemd service (not Docker) on LXC 114:
   ```
   /etc/systemd/system/uptime-kuma.service
   ```

2. Added the environment variable to the `[Service]` section:
   ```ini
   [Service]
   Environment=UPTIME_KUMA_DISABLE_FRAME_SAMEORIGIN=true
   ```

3. Reloaded and restarted:
   ```bash
   systemctl daemon-reload
   systemctl restart uptime-kuma
   ```

4. Used the direct local URL in Home Assistant iframe — no proxy required:
   ```
   http://192.168.0.44:3001/dashboard
   ```

### Key Files Modified
- `/etc/systemd/system/uptime-kuma.service` — added `Environment=UPTIME_KUMA_DISABLE_FRAME_SAMEORIGIN=true`

## Verification
Uptime Kuma dashboard loads correctly inside the Home Assistant iframe panel using the direct local IP.

## Troubleshooting
- Unlike BirdNET-Go, Uptime Kuma has a native env var for this — no reverse proxy needed
- If the header persists after restart, verify the env var is in the `[Service]` section and `systemctl daemon-reload` was run
- For Docker deployments, pass `-e UPTIME_KUMA_DISABLE_FRAME_SAMEORIGIN=true` instead
