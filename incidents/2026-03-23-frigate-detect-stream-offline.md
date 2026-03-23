# Frigate Detect Stream Offline — PID Limit Not Applied After Redeploy

**Last Updated**: 2026-03-23
**Related Systems**: Container 128 (Komodo), Frigate Docker stack

## Summary

Frigate's detect stream stopped working on March 22, 2026 after the container was recreated with a newer image (0.17). The compose file specified `pids: 1024` but the container was running with a limit of 300, causing FFmpeg thread creation failures. A full `docker compose down` + `up` (not just restart) resolved the issue.

## Problem / Goal

Frigate reported the detect stream as offline with no frames detected, while the main camera stream was visible and working normally in the UI. Detection events stopped occurring entirely.

## Root Cause

The Frigate container was recreated on March 22 with a newer image (`ghcr.io/blakeblackshear/frigate:stable`, built 2026-03-19, version 0.17). The new version uses more threads for detection/embedding pipelines. The compose file had `pids: 1024` in `deploy.resources.limits`, but the container was actually running with a **300 PID limit** — the compose change had not been properly applied.

At 297/300 PIDs (99% full), FFmpeg could not create worker threads for the detect stream, producing a repeating error loop:

```
pthread_create() failed: Resource temporarily unavailable
No frames received from Driveway in 20 seconds. Exiting ffmpeg...
```

The main stream worked because it acquired its threads first; the detect stream lost the race for remaining PIDs.

## Solution

A full redeploy (`docker compose down` + `up`) was required — a simple container restart does not apply Docker resource limit changes.

## Implementation Details

### Steps Performed

1. Identified the error via Frigate logs:
   ```bash
   ssh claude@192.168.0.151 'sudo pct exec 128 -- docker logs --tail 200 frigate 2>&1'
   ```

2. Confirmed PID limit mismatch:
   ```bash
   # Compose file says 1024, but container had 300
   ssh claude@192.168.0.151 'sudo pct exec 128 -- docker exec frigate cat /sys/fs/cgroup/pids.max'
   # Output: 300
   ssh claude@192.168.0.151 'sudo pct exec 128 -- docker exec frigate cat /sys/fs/cgroup/pids.current'
   # Output: 297
   ```

3. Full redeploy via Komodo (docker compose down + up)

4. Verified fix:
   ```bash
   ssh claude@192.168.0.151 'sudo pct exec 128 -- docker exec frigate cat /sys/fs/cgroup/pids.max'
   # Output: 1024
   ssh claude@192.168.0.151 'sudo pct exec 128 -- docker exec frigate cat /sys/fs/cgroup/pids.current'
   # Output: 301
   ```

### Key Files

- `/etc/komodo/stacks/frigate/compose.yaml` on CT 128 — already had correct `pids: 1024`, just needed reapplication
- `/mnt/frigate/config/config.yaml` on CT 128 — no changes needed

## Verification

- PID limit reads `1024` (not `300`)
- No `pthread_create` errors in Frigate logs after redeploy
- Detect stream shows as online in Frigate UI
- Detection events resume normally

## Troubleshooting

### Key Lesson: Restart vs Redeploy

A `docker restart` or `docker compose restart` does **not** apply changes to resource limits (`pids`, `memory`, `cpus`). These require a full `docker compose down` + `up` to recreate the container with the new limits.

### Known Frigate Version Issues

- **0.16.x**: Known memory leak in FFmpeg (grows ~1MB/sec until OOM) — can cause gradual thread exhaustion
- **0.17.0**: Includes thread-safety fixes but uses more threads; may have Intel QSV decode issues
- **0.15.x**: Last stable baseline without these issues

### Monitoring

To check PID health going forward:
```bash
# Current PID usage vs limit
docker exec frigate cat /sys/fs/cgroup/pids.current
docker exec frigate cat /sys/fs/cgroup/pids.max
```

If PIDs creep toward the limit over days, the 0.16/0.17 memory leak may be at play — consider pinning to a specific stable version rather than the `:stable` rolling tag.
