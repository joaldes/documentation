# Runaway `grep` Saturating Data Disk (28-hour Read Storm)

**Last Updated**: 2026-07-03
**Related Systems**: Proxmox host Shipyard, CT 124 (Claude AI), `data` VG on disk `sdd`, Frigate (CT 128)

## Summary
A stray `grep -r frigate/config /` left running inside CT 124 crawled the entire filesystem — including every large media share mounted into the container — for 28 hours straight, reading ~142 MB/s and pinning the `sdd` spinning disk at ~81% utilization (queue depth 169). This starved everything else sharing that disk (Docker databases, photos, Frigate recordings). Killing the process dropped disk utilization from ~81% to ~5% instantly. No data was affected — it was pure read load.

## Problem / Goal
The `data` VG (disk `sdd`) showed sustained high I/O and sluggish performance that "started around 10:30 the previous day" and had never been seen before. Initial suspicion fell on Frigate (a 24/7 NVR) or a backup job copying recordings. Neither was the cause.

## Root Cause
During Frigate config-relocation maintenance on 2026-07-02 (moving Frigate's config into `/mnt/docker/frigate/config` so it rides in the nightly `docker.pxar` backup), a search command was run to find references to the config path:

```
lxc-attach -n 124 --keep-env -- grep -r frigate/config /
```

- **Started**: Thu Jul 2 10:05:26 → still running 1 day 4 hours later (PID 2082133, parent `lxc-attach` 2082127).
- **Unscoped**: `cwd = /`, so it recursed the entire CT 124 root filesystem.
- CT 124 has all the big media shares bind-mounted (`/mnt/pictures` ~2.6 TB, `/mnt/frigate` ~581 GB, `/mnt/documents`, and the 17 TB `/mnt/hometheater` pool). The grep read every byte of video and photos looking for a text match, so it never finished.

The reason it looked like "Frigate" at first glance: Frigate *was* restarted at 10:32:57 that same morning as part of the same maintenance, and it does write continuously (~1 GB/hr of recordings). But `docker stats` and `pidstat -d` showed Frigate at only ~2 MB/s while the grep was reading ~142 MB/s — two orders of magnitude larger.

## Diagnosis (how it was found)

### Evidence
1. `iostat -dx` — `sdd` at 81% util, `aqu-sz` 169; the read side (not write) was saturated → pointed at a reader, not a recorder.
2. Mapped the busy device-mapper LVs to shares: `dm-59 = data-pictures`, `dm-58 = data-frigate`, `dm-60 = data-docker` (all on `sdd`).
3. `pidstat -d 5 1` — ranked processes by disk I/O; one `grep` (uid 100000, i.e. an unprivileged-LXC root) was reading **142,881 kB/s**, dwarfing everything else.
4. Traced the PID:
   ```bash
   ps -o pid,ppid,lstart,etime,args -p 2082133
   #  grep -r frigate/config /   (elapsed 1-04:00:05)
   cat /proc/2082133/cgroup      # -> lxc/124
   ```

## Solution
Kill the runaway grep and its `lxc-attach` parent. It is a read-only search — terminating it carries zero data risk.

```bash
# From the Proxmox host (Shipyard)
sudo kill 2082133 2082127
```

## Verification
`sdd` calmed immediately after the kill:

| Metric | Before | After |
|--------|--------|-------|
| `sdd` utilization | ~81% | ~5% |
| Queue depth (`aqu-sz`) | 169 | 0.09 |
| Read rate | ~142 MB/s | ~1 MB/s |

`pidstat -d` afterward showed only normal background I/O: Emby (~860 kB/s), Frigate recording (~2 MB/s write), and Proxmox `pvestatd`/`pvedaemon` monitoring. Frigate logs were clean throughout (`frigate.record.maintainer Copied ...mp4` every ~10s, no errors).

## Prevention / Lessons
- **CT 124 mounts every large media share at `/`.** Any recursive filesystem command run from `/` inside CT 124 (`grep -r`, `find /`, `du -sh /`, `tar` from root) will traverse terabytes — including the 17 TB `hometheater` pool — and can run for days. **Always scope such commands to a specific path.**
- When chasing disk I/O, rank by **actual bytes/sec** (`pidstat -d`, `iotop -o`, `docker stats` cumulative BlockIO) before blaming the "obvious" heavy service. Here the obvious suspect (Frigate) was a red herring; the real hog was 70x larger.
- Read vs. write in `iostat` is a fast triage signal: a *read*-saturated disk points at a scanner/backup/copy, not a recorder.
- The `data` VG lives on a single spinning disk (`sdd`). Frigate recordings, Docker databases, and photos all compete for it, so any rogue reader degrades all three at once. (Longer-term mitigation: move Frigate recordings off `sdd`, e.g. onto the `hometheater` mergerfs pool.)
