# Seedbox Fast-Pull & Syncthing Tuning

**Last Updated**: 2026-06-26
**Related Systems**: CT 103 (Syncthing, 192.168.0.45), CT 128 (fast-pull scripts + action service, 192.168.0.179), Ultra.cc seedbox (`beryl.usbx.me`), Trailhead, jobs.home

## Summary
Completed downloads on the Ultra.cc seedbox sync home via Syncthing (CT 103) into
`/mnt/hometheater/processingnzb`, where Radarr/Sonarr import them. Pulls were slow (~20 MiB/s
against a ~762 Mbps WAN) and new files were sometimes picked up hours late. This documents the
fixes: a stuck-connection repair, throughput benchmarking, an on-demand multi-stream "Turbo Pull"
tool (~90 MiB/s) with a Trailhead button, and a seedbox scan-delay fix.

## Pipeline
`SABnzbd/qBittorrent on seedbox → ~/downloads/sabnzbd/complete (+ /qbittorrent)` →
**Syncthing folder `oih7u-aikvq` "Home Theater Processing"** (seedbox `642TA7A` → home CT 103) →
`/mnt/hometheater/processingnzb/<rel>` → Radarr/Sonarr import to the library.

Key facts: WAN ~762 Mbps (~91 MiB/s) down; RTT to seedbox ~153 ms; Syncthing GUI on CT 103
`http://192.168.0.45:8384`.

## Problem 1 — pulls collapsed to a single stream (~20 MiB/s)
Syncthing was configured for 32 parallel connections to the seedbox, but they decayed to **1**.
Root cause: the router (192.168.0.1) kept **refusing to renew the NAT-PMP port mapping**, and all
connections are inbound (`tcp-server`, seedbox dials in), so once the lease lapsed they couldn't
re-establish. A single TCP stream over the 153 ms link caps ~150 Mbps.

**Fix:** static inbound port-forward **TCP/UDP 22000 → 192.168.0.45** on the router (rule
"Syncthing Ultra<>HomeLab"). Connections now persist (30+ streams). Also raised, on the home
folder `oih7u-aikvq`: `pullerMaxPendingKiB=262144`, `copiers=8`, `maxConcurrentWrites=8`.

**The real ~20 MiB/s cause (corrected 2026-06-27):** NOT architectural. The **seedbox** Syncthing had a
configured bandwidth limit `maxSendKbps=20000` (= 19.5 MiB/s) in its global `<options>` *and* on every
`<device>` (`~/.apps/syncthing/config.xml`); the home side (CT 103) was already `0`. That 20000 KiB/s cap
is exactly why pulls plateaued at ~20 MiB/s, while `ssh|dd` hit 90 — it bypasses Syncthing, so the cap
never applied. **Fix:** zero the limits in the seedbox Syncthing UI -> Actions -> Settings -> Connections
-> Incoming/Outgoing Rate Limit = `0` (and each device's Advanced rate limit). With the cap removed,
Syncthing now pulls at **~92 MiB/s = full WAN ceiling** (measured 2026-06-26 on a live 56.8 GiB pull;
ramps 47->92 as the connection warms). It matches raw `ssh|dd`, so **Turbo Pull (below) is now redundant**
— Syncthing saturates the link on its own; the button/tooling can stay as a fallback but isn't needed. (A leftover `<defaults><device>` template on the seedbox still carries
20000; it is inert and only affects future device additions.)

## Throughput benchmark (2026-06-26, 4 GiB test file, sequential, encrypted only)
| Method | Streams | MiB/s |
|---|---|---|
| **`ssh -c aes128-gcm \| dd`** | **24** | **90.1** (= WAN ceiling) |
| `ssh \| dd` | 16 | 81.7 |
| `ssh \| dd` (chacha20) | 16 | 82.9 |
| `ssh \| dd` | 8 | 59.3 |
| lftp `pget` (sftp) | 24 | 48.4 |
| rclone (sftp, multi-thread) | 16 | 38.7 |
| Syncthing (**throttled** — old cap) | 30+ | ~20 |
| **Syncthing (cap removed, 2026-06-26)** | 30+ | **~92** (= WAN ceiling) |

Conclusion: **multi-stream `ssh|dd` ≈ 2× any SFTP client**, and saturates the WAN at 16–24 streams.
Cipher choice is irrelevant at these speeds. NOTE: the Syncthing ~20 row was the **rate-limited** state (see Problem 1's correction); once the
cap was removed Syncthing itself hit ~92 MiB/s, equal to `ssh|dd` — i.e. the cap was the entire gap.

## Solution — on-demand "Turbo Pull"
For an urgent/large file, pull it with parallel `ssh|dd` instead of waiting on Syncthing.

**Scripts (CT 128 host, `/usr/local/bin/`):**
- `fastpull.sh <remote_path> <dest> [streams]` — generic N-stream (default 24) byte-offset puller.
- `fastpull-turbo.sh` — reads Syncthing's need-list for `oih7u-aikvq`, **pauses** the folder,
  multi-stream pulls the in-flight file to `/mnt/hometheater/processingnzb/<rel>`, then **resumes**
  so Syncthing re-scans, sees matching bytes, and marks it synced (no re-download). jobctl-wrapped
  (progress on jobs.home). No-op if nothing is pending.

**Auth:** CT 128 `~/.ssh/config` `Host beryl` → `beryl.usbx.me` via key `/root/.ssh/seedbox_key`
(public key in the seedbox's `~/.ssh/authorized_keys`). Cipher `aes128-gcm@openssh.com`.

**Button:** Trailhead **Media → "⚡ Turbo Pull"** → `http://192.168.0.179:8096/`. Backed by a tiny
host action service `/opt/fastpull/server.py` (systemd `fastpull-action.service`, ThreadingHTTPServer
on `0.0.0.0:8096`). `GET /` = info+button page, `POST /turbo` = launch script, `GET /health` = json.
Runs on the CT 128 **host** (not a container) so it has the ssh key, the `/mnt/hometheater` mount,
and the scripts. Log: `/var/log/fastpull.log`.

## Problem 2 — delay before Syncthing notices a finished download
Seedbox Syncthing (`~/.apps/syncthing/config.xml`, GUI `127.0.0.1:8384`) had both source folders at
`rescanIntervalS=86400` (24h) with `fsWatcherEnabled=false` → completed downloads weren't indexed
(and so not announced to home) for up to a day.

**Fix (via Ultra.cc Syncthing web UI):** folders `oih7u-aikvq` and `4bxjt-krgq3` set to
**`fsWatcherEnabled=true` + `rescanIntervalS=60`** → near-instant pickup, 60 s fallback.

## Verification
- Syncthing connection count to the seedbox stays well above 1 (CT 103 `:8384` → Connections).
- Turbo Pull: `curl http://192.168.0.179:8096/health` → `{"ok":true}`; clicking the button (or
  `fastpull-turbo.sh`) on a live transfer shows ~90 MiB/s on jobs.home, then Syncthing marks synced.
- Seedbox folders show `fsWatcherEnabled=true` / `rescanIntervalS=60`; new downloads appear in
  home Syncthing within seconds–minutes.

## Troubleshooting
- **Button page won't load but `curl` works** — server must be `ThreadingHTTPServer` (single-threaded
  hangs on browser keep-alive). Also `192.168.0.179` is LAN-only.
- **Turbo says "nothing to pull"** — Syncthing hasn't indexed the file yet (see Problem 2) or the
  transfer already finished.
- **Slow again / single stream** — re-check the 22000 port-forward and that Syncthing rebuilt
  multiple connections after any restart.
- Config edits via the seedbox Syncthing **Advanced tree editor** are error-prone (once created a
  stray `id="" path="~"` folder); prefer the folder Edit dialog or the REST API.

## Notes
- Seedbox SSH/SFTP: `beryl.usbx.me:22` user `bigalpha` (FTP `:21` also open but unused — plaintext).
- Seedbox password was shared during setup; rotation deferred by owner.
