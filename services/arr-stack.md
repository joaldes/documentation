# *arr Media Stack (Jellyseerr → Radarr/Sonarr → Emby)

**Last Updated**: 2026-06-30
**Related Systems**: CT 113 Jellyseerr, CT 107 Radarr, CT 110 Sonarr, CT 115 Bazarr, CT 102 Emby,
remote seedbox (ultra.cc / beryl.usbx.me), CT 128 Trailhead (Request Tracker)

## Summary

The home media automation pipeline: users request titles in **Jellyseerr**, which hands approved
requests to **Radarr** (movies) / **Sonarr** (TV). Those grab releases via a **Prowlarr** instance
hosted on the seedbox, download them on the seedbox (usenet + torrent), sync the completed files
home, import them into the library at `/mnt/hometheater`, and **Emby** serves them. **Bazarr** adds
subtitles. Per-request status across this whole chain is surfaced on the Trailhead **Request
Tracker** (`services/trailhead.md`).

## Pipeline

```
 Jellyseerr (CT113, request + approve)
      │  approved request → arr
      ▼
 Radarr (CT107, movies) / Sonarr (CT110, TV)
      │  search indexers (Prowlarr on seedbox) → send to a download client
      ▼
 Seedbox download clients (both ENABLED):
   • SABnzbd_ultra.cc  — usenet  (primary active path observed) → seedbox …/sabnzbd/complete/
   • qBittorrent       — torrent (seedbox 46.232.211.159)      → seedbox …/qbittorrent/
      │  seedbox completed dirs synced home + translated by arr remote path mappings:
      │    …/sabnzbd/complete/  → /mnt/hometheater/processingnzb/
      │    …/qbittorrent/       → /mnt/hometheater/processingtorrent/
      ▼
 Radarr/Sonarr IMPORT → /mnt/hometheater/Movies  |  /mnt/hometheater/TV Shows
      │                         └─ ⚠ can stall here: "Manual Import required" (see Failure Modes)
      ▼
 Emby (CT102)  →  playable   (Bazarr CT115 adds subtitles)
```

Both arrs share the same client + mapping config. Seedbox → home sync tuning is documented
separately in `services/seedbox-syncthing.md`.

### Remote path mappings (Radarr + Sonarr, identical)

The download clients run on the seedbox, so the arrs translate seedbox paths to the local mounts:

| Client host | Seedbox path | Local path |
|---|---|---|
| `45.86.221.138` (SABnzbd_ultra.cc) | `/home/bigalpha/downloads/sabnzbd/complete/` | `/mnt/hometheater/processingnzb/` |
| `46.232.211.159` (qBittorrent) | `/home/bigalpha/downloads/qbittorrent/` | `/mnt/hometheater/processingtorrent/` |

## Components

| Role | Service | CT | Address | Local library / notes |
|------|---------|----|---------|-----------------------|
| Requests front-end | Jellyseerr | 113 | `192.168.0.43:5055` · `jellyseerr.1701.me` | wired to Jellyfin/Emby + Radarr + Sonarr |
| Movies | Radarr | 107 | `192.168.0.42:7878` · `radarr.1701.me` | root `/mnt/hometheater/Movies` |
| TV | Sonarr | 110 | `192.168.0.24:8989` · `sonarr.1701.me` | root `/mnt/hometheater/TV Shows` |
| Subtitles | Bazarr | 115 | `192.168.0.48:6767` · `bazarr.1701.me` | — |
| Media server | Emby | 102 | `192.168.0.13:8096` · `emby.1701.me` | library on `/mnt/hometheater` (~17 TB) |
| Indexers | Prowlarr | (seedbox) | `https://bigalpha.beryl.usbx.me/prowlarr/…` | proxied into Radarr/Sonarr as per-tracker indexers |
| Download (usenet) | SABnzbd_ultra.cc | (seedbox) | `45.86.221.138:17357` | **enabled**, active path |
| Download (torrent) | qBittorrent | (seedbox) | `46.232.211.159:17391` | enabled; categories `radarr` / `tv-sonarr` |
| Status dashboard | Request Tracker | 128 | `trailhead.1701.me/requests.html` | see `services/trailhead.md` |

> There is also a **disabled** local SABnzbd (`192.168.0.81:7777`) in the config — legacy, not used.

**API keys** are NOT stored in this repo. They live in each app's config
(`/var/lib/{radarr,sonarr}/config.xml`, Jellyseerr `settings.json`, Bazarr `config.yaml`, Emby →
Dashboard → API Keys) and, for the Request Tracker, in `/mnt/docker/trailhead/.env` on CT 128.

## Storage & mounts

The whole stack shares **one library filesystem** so imports are same-filesystem hardlink/instant-moves
(no cross-device copies):

- Host `Shipyard` `/mnt/hometheater` = a **mergerfs pool (~29 TB, ~17 TB used)**, bind-mounted into each
  guest at the same path via LXC `mp` entries — **not** SMB/NFS between containers:
  - CT 107 Radarr `mp0`, CT 110 Sonarr `mp1`, CT 115 Bazarr `mp0`, CT 102 Emby `mp0`, CT 103 Syncthing `mp0`.
- **Seedbox → home transport:** Syncthing (CT 103) pulls the seedbox completed dirs into
  `/mnt/hometheater/processingnzb/` (usenet) and `/mnt/hometheater/processingtorrent/` (torrent).
  Tuning in `services/seedbox-syncthing.md`.
- Radarr/Sonarr import from those `processing*` dirs (via the remote path mappings above) into
  `/mnt/hometheater/Movies` and `/mnt/hometheater/TV Shows`, which Emby serves.
- (Samba CT 104 also exports `hometheater` for file access; not part of the import path.)

Per-app tuning (quality profiles, naming, media-management/hardlink settings) lives in each app's own
config, not here — reachable at each service's URL below.

## Request status / lifecycle

Authoritative source per stage (do NOT trust Jellyseerr's cache for download/import state — it is
blind to import failures):

| Stage | Authoritative source |
|-------|----------------------|
| Requested / requester / approval | Jellyseerr `/api/v1/request` (`X-Api-Key` header) |
| Grabbed / wanted / monitored | Radarr `/api/v3/movie` · Sonarr `/api/v3/series` (`statistics`) |
| Downloading % · import state | Radarr/Sonarr `/api/v3/queue` → `trackedDownloadState` |
| Actually playable | Emby provider-id index (`/emby/Items?…Fields=ProviderIds`) |

The **Request Tracker** page correlates all of the above into one status per title; full design in
`services/trailhead.md`.

## Failure modes

- **⚠ Import blocked ("Manual Import required")** — the most common silent failure. The download
  finishes (`sizeleft:0`) but the arr can't auto-import it (e.g. "matched to movie by ID"),
  `trackedDownloadState = importBlocked`. It sits in the queue until someone does a manual import in
  Radarr/Sonarr. **Jellyseerr does not show this** — the Request Tracker surfaces it at the top.
- **Orphaned request** — Jellyseerr still lists a request as "processing" but the series/movie was
  removed from the arr. Shows on the Request Tracker as "not in library".
- **No release yet** — approved but nothing grabbed (unreleased title, or indexer issue). Informational.

## Notifications (existing)

- **Sonarr → Node-RED** ("Webhook to Node Red", onGrab…onImport) — the one webhook push wired;
  Radarr has **no** webhook.
- Both arrs: **Emby/Jellyfin** library sync (MediaBrowser, on grab+import), **Telegram** (on import),
  and a **Custom Script** (post-import file-ownership fix).
- **Available but unused:** Radarr/Sonarr `onManualInteractionRequired` webhook fires on import-blocked
  — the intended hook for future proactive "stuck download" alerts (Request Tracker v2).

## Verification

- Requests view: `jellyseerr.1701.me` → Requests.
- Live queue / import state: `radarr.1701.me` and `sonarr.1701.me` → Activity → Queue (look for
  `Manual Import required`).
- One-glance pipeline status for every request: `trailhead.1701.me/requests.html`.
- Library truth: `emby.1701.me`.
