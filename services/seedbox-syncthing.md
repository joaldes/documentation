# Seedbox → Home Syncthing Tuning

**Last Updated**: 2026-06-27
**Related Systems**: CT 103 (Syncthing, 192.168.0.45), Ultra.cc seedbox (`beryl.usbx.me`), router (192.168.0.1)

## Summary
Completed downloads on the Ultra.cc seedbox sync home via Syncthing (CT 103) into
`/mnt/hometheater/processingnzb`, where Radarr/Sonarr import them. Two problems were fixed: pulls were
slow (~20 MiB/s against a ~762 Mbps WAN) and new files were sometimes picked up hours late. Root
causes turned out to be a **configured bandwidth limit on the seedbox** plus a stale Syncthing scan
schedule — both now resolved, and Syncthing pulls at the full WAN ceiling (~92 MiB/s).

## Pipeline
`SABnzbd/qBittorrent on seedbox → ~/downloads/sabnzbd/complete (+ /qbittorrent)` →
**Syncthing folder `oih7u-aikvq` "Home Theater Processing"** (seedbox `642TA7A` → home CT 103) →
`/mnt/hometheater/processingnzb/<rel>` → Radarr/Sonarr import to the library.

Key facts: WAN ~762 Mbps (~91 MiB/s) down; RTT to seedbox ~153 ms; Syncthing GUI on CT 103
`http://192.168.0.45:8384`; seedbox Syncthing config `~/.apps/syncthing/config.xml` (GUI behind the
Ultra.cc panel proxy, so use the panel, not a direct port).

## Problem 1 — slow pulls (~20 MiB/s on a ~91 MiB/s WAN)
Two separate issues compounded here:

**1a. Connections collapsed to a single stream.** Syncthing was configured for 32 parallel
connections to the seedbox, but they decayed to **1**. Root cause: the router (192.168.0.1) kept
**refusing to renew the NAT-PMP port mapping**, and all connections are inbound (`tcp-server`, seedbox
dials in), so once the lease lapsed they couldn't re-establish. A single TCP stream over the 153 ms
link caps ~150 Mbps.
**Fix:** static inbound port-forward **TCP/UDP 22000 → 192.168.0.45** on the router (rule
"Syncthing Ultra<>HomeLab"). Connections now persist (30+ streams).

**1b. The actual ~20 MiB/s ceiling was a configured RATE LIMIT on the seedbox** (the real culprit, found
2026-06-27). The seedbox Syncthing had `maxSendKbps=20000`/`maxRecvKbps=20000` (= 19.5 MiB/s) set in the
global `<options>` **and** on every `<device>`; the home side (CT 103) was already `0`. A 20000 KiB/s cap
produces exactly a ~20 MiB/s plateau — it was never an "architectural" Syncthing limit.
**Fix:** zero the limits in the seedbox Syncthing UI → Actions → Settings → Connections →
Incoming/Outgoing Rate Limit = `0` (and each device's Advanced rate limit). After removal, Syncthing
pulls at **~92 MiB/s = full WAN ceiling** (measured on a live 56.8 GiB pull; ramps ~47→92 as the
connection warms).
*Leftover:* a `<defaults><device>` template on the seedbox still carries 20000 — inert, but it would
seed the old cap onto any **newly added** device; clear it via Advanced Configuration if you ever
re-add a device.

Home-folder tuning applied along the way (minor; not the bottleneck): `pullerMaxPendingKiB=262144`,
`copiers=8`, `maxConcurrentWrites=8` on `oih7u-aikvq`.

## Problem 2 — delay before Syncthing notices a finished download
Seedbox Syncthing had both source folders at `rescanIntervalS=86400` (24h) with
`fsWatcherEnabled=false` → completed downloads weren't indexed (and so not announced to home) for up
to a day.
**Fix (via the Ultra.cc Syncthing web UI):** folders `oih7u-aikvq` and `4bxjt-krgq3` set to
**`fsWatcherEnabled=true` + `rescanIntervalS=60`** → near-instant pickup, 60 s fallback.

## Verification
- Syncthing connection count to the seedbox stays well above 1 (CT 103 `:8384` → Connections).
- Seedbox "This Device" shows **no rate limit**; a live pull sustains ~90 MiB/s (not ~20).
- Seedbox folders show `fsWatcherEnabled=true` / `rescanIntervalS=60`; new downloads appear in home
  Syncthing within seconds–minutes.

## Troubleshooting
- **Slow again / single stream** — re-check the 22000 port-forward and that Syncthing rebuilt multiple
  connections after any restart.
- **Back to ~20 MiB/s** — check the seedbox rate limits haven't been re-applied (Ultra.cc may ship a
  default cap; the `<defaults>` template still holds 20000 for new devices).
- Config edits via the seedbox Syncthing **Advanced tree editor** are error-prone (once created a stray
  `id="" path="~"` folder); prefer the folder Edit dialog.

## Notes
- This is a **shared Ultra.cc box** — the 20 MB/s cap may be their fair-use default; removing it is fine
  for bursty pulls, but be aware they could re-impose it.
- Seedbox SSH/SFTP: `beryl.usbx.me:22` user `bigalpha` (FTP `:21` also open but unused — plaintext).
- Seedbox password was shared during setup; rotation deferred by owner.
