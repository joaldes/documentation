# Photogrammetry Automation System - Complete Reference

**Version:** 5.24
**Last Updated:** 2026-05-16
**System Status:** Active and Operational
**Backend Version:** inline-2026-05-16e

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Component Locations](#3-component-locations)
4. [Backend API (Container 104)](#4-backend-api-container-104)
5. [Home Assistant Integration](#5-home-assistant-integration)
6. [Storage & Folder Structure](#6-storage--folder-structure)
7. [Photo Transfer (ADB-Pull)](#7-photo-transfer-adb-pull)
8. [Session Lifecycle](#8-session-lifecycle)
9. [Key Features](#9-key-features)
10. [Dashboard Reference](#10-dashboard-reference)
11. [API Reference](#11-api-reference)
12. [Troubleshooting](#12-troubleshooting)
13. [Configuration Files Reference](#13-configuration-files-reference)
14. [Version History](#14-version-history)

---

## 1. System Overview

Automated photogrammetry capture system that controls a Samsung phone via ADB to capture burst photos at different rotation positions, then processes them using focus stacking (`focus-stack` CLI) and optional auto-cropping (PIL). Supports a **single-shot mode** (burst=1) that bypasses stacking via a copy-through for non-macro subjects — see "Single-Shot Mode" below.

### Workflow Summary
1. User configures session in Home Assistant (object name, angular distance, auto-crop)
2. User starts session via dashboard toggle
3. Backend connects to phone via ADB wireless
4. For each position (0° to 360°):
   - Phone captures burst photos (configurable count, typically 10; 1 = single-shot, no stacking)
   - Backend pulls the burst directly off the phone via `adb pull`
   - Backend focus-stacks images via `focus-stack` CLI (or copy-through when burst=1)
   - Optional auto-crop applied with consistent dimensions
   - Turntable rotates to next position
5. Session completes with all stacked/cropped images saved

### Key Components
- **Backend API:** Flask REST API on Container 104 (192.168.0.176:5000)
- **Home Assistant:** Dashboard, sensors, automations, controls
- **ADB:** Wireless Android Debug Bridge — used for phone control AND photo transfer (direct `adb pull`, per-session). Replaced Syncthing as of v5.17.
- **Storage:** Samba share for photos and documentation

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     HOME ASSISTANT (Container 110)               │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐   │
│  │  Dashboard  │  │  Automations │  │  REST Sensors (3x)   │   │
│  │  - Control  │  │  - Auto-start│  │  - Session (5s poll) │   │
│  │  - Status   │  │  - Auto-stop │  │  - ADB Info (10s)    │   │
│  │  - Stats    │  │              │  │  - Statistics (60s)  │   │
│  └─────────────┘  └──────────────┘  └───────────────────────┘   │
│         │                │                     │                 │
│         └────────────────┼─────────────────────┘                 │
│                          │ REST Commands                         │
└──────────────────────────┼───────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              SAMBA CONTAINER 104 (192.168.0.176)                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Flask API (/opt/photogrammetry/photogrammetry.py:5000)    │ │
│  │  - Session management with threading                       │ │
│  │  - ADB control (Samsung S10/S24)                           │ │
│  │  - Focus stacking (OpenCV)                                 │ │
│  │  - Auto-cropping (PIL)                                     │ │
│  │  - Dual stacking pipeline (odd/even)                       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                          │ adb pull (per-position)               │
│                          ▼                                       │
│                      ┌───────────────────────────────────────┐  │
│                      │  /mnt/pictures/photogrammetry/        │  │
│                      │  - coin_X/ (session folders)          │  │
│                      │  - coin_X/_session_N/posNNN/ (bursts) │  │
│                      │  - _lifetime_stats.json               │  │
│                      └───────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                           ▲
                           │ adb pull / adb shell
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  SAMSUNG S10 PHONE (Wireless ADB)                │
│  - OpenCamera app for burst capture                              │
│  - DCIM/OpenCamera/ — bursts pulled + deleted per position       │
│  - mDNS: adb-RF8M20STA5T-rIxgXQ._adb-tls-connect._tcp           │
│  - (Syncthing app retired as of v5.17 — must NOT run)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Locations

### Backend (Container 104 - Samba)
| Component | Path |
|-----------|------|
| Main Script | `/opt/photogrammetry/photogrammetry.py` |
| Service File | `/etc/systemd/system/photogrammetry.service` |
| Requirements | `/opt/photogrammetry/requirements.txt` |
| Photo Storage | `/mnt/pictures/photogrammetry/` |
| Statistics | `/mnt/pictures/photogrammetry/_lifetime_stats.json` |

### Documentation (Samba Share)
| File | Description |
|------|-------------|
| `/mnt/documents/personal/alec/claudeai/photogrammetry.md` | Main documentation |
| `/mnt/documents/personal/alec/claudeai/photogrammetry-config.yaml` | Combined HA config (legacy) |
| `/mnt/documents/personal/alec/claudeai/photogrammetry-dashboard.yaml` | Dashboard YAML |
| `/mnt/documents/personal/alec/claudeai/photogrammetry/` | Split HA package files (v4.2.3) |

### Home Assistant Package Files (Samba: /claudeai/photogrammetry/)
| File | Version | Purpose |
|------|---------|---------|
| `inputs.yaml` | 4.2.3 | Input controls (booleans, numbers, text) |
| `rest_commands.yaml` | 4.2.3 | API calls to backend |
| `scripts.yaml` | 4.2.3 | Helper scripts for dynamic session_id |
| `automations.yaml` | 4.2.3 | Auto-start/stop with threading |
| `sensors.yaml` | 4.2.3 | REST sensors + Template sensors |

### Older Package Files (Samba: /claudeai/photogrammetry package sensor/)
| File | Version | Status |
|------|---------|--------|
| Various .yaml files | 4.2 | Outdated - has `json_attributes_path` bug |

**Note:** The `/photogrammetry/` folder contains the latest v4.2.3 files with fixes for JSON parsing errors.

---

## 4. Backend API (Container 104)

### Service Configuration

```ini
[Unit]
Description=Photogrammetry Automation API
After=network.target

[Service]
Type=simple
User=sambauser
Group=sambauser
WorkingDirectory=/opt/photogrammetry
Environment=PYTHONUNBUFFERED=1
Environment=OPENCV_CACHE_DIR=/opt/photogrammetry/.opencv_cache
ExecStart=/usr/bin/python3 -u /opt/photogrammetry/photogrammetry.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Python Dependencies
```
Flask==2.2.2
requests==2.28.1
requests-toolbelt==0.10.1
```

Also uses: PIL (Pillow), NumPy, OpenCV

### Backend Configuration (Hardcoded)
```python
# Device Configuration
AVAILABLE_DEVICES = [
    {"name": "Samsung S10", "ip": "adb-RF8M20STA5T-rIxgXQ._adb-tls-connect._tcp", "active": True},
    {"name": "Samsung S24", "ip": "192.168.0.17:34971", "active": False},
]

# Paths
ADB_PATH = "/opt/platform-tools/adb"
DCIM_PATH = "/sdcard/DCIM/OpenCamera"
BASE_PHOTO_DIR = "/mnt/pictures/photogrammetry"
# (v5.17) SYNCTHING_* constants removed — transport is now direct adb pull

# Home Assistant
HA_API_URL = "http://192.168.0.154:8123/api"

# Processing
ROTATION_COOLDOWN_SECONDS = 1.5
ADB_POLL_TIMEOUT_SECONDS = 300
STACKING_QUALITY = 98
STACKING_THREADS = 4

# Auto-Crop
UNIFIED_CROP_ENABLED = False   # post-session unified crop pass (v5.16)
AUTO_CROP_ENABLED = True
AUTO_CROP_MARGIN_PX = 20
AUTO_CROP_THRESHOLD = 95
```

### Service Management
```bash
# Check status
sudo pct exec 104 -- systemctl status photogrammetry.service

# View logs
sudo pct exec 104 -- journalctl -u photogrammetry.service -f

# Restart
sudo pct exec 104 -- systemctl restart photogrammetry.service
```

---

## 5. Home Assistant Integration

### Input Controls

| Entity | Type | Purpose |
|--------|------|---------|
| `input_boolean.photogrammetry_active` | Boolean | Master session toggle |
| `input_boolean.photogrammetry_auto_crop` | Boolean | Enable auto-cropping |
| `input_text.photogrammetry_object_name` | Text | Object/folder name |
| `input_number.photogrammetry_angular_distance` | Number | Degrees between positions (1-45) |
| `input_number.turntable_stepper_speed` | Number | Motor speed (100-2000 steps/s) |

### REST Commands

| Command | Endpoint | Purpose |
|---------|----------|---------|
| `photogrammetry_start` | POST /api/session/start | Start new session |
| `photogrammetry_pause` | POST /api/session/{id}/pause | Pause processing |
| `photogrammetry_resume` | POST /api/session/{id}/resume | Resume paused session |
| `photogrammetry_stop` | POST /api/session/{id}/stop | Stop session |
| `photogrammetry_reset` | POST /api/session/{id}/reset | Reset/cleanup session |
| `photogrammetry_select_s10` | POST /api/devices/select | Select S10 phone |
| `photogrammetry_select_s24` | POST /api/devices/select | Select S24 phone |
| `photogrammetry_disconnect_devices` | POST /api/devices/disconnect | Disconnect all devices |
| `turntable_rotate` | POST /api/turntable/rotate | Manual rotation |
| `turntable_stop` | POST /api/turntable/stop | Emergency stop |

### REST Sensors (3 Total)

| Sensor | Endpoint | Poll Rate | Purpose |
|--------|----------|-----------|---------|
| `sensor.photogrammetry_session` | /api/session/current | 10s | Main session data |
| `sensor.photogrammetry_adb_info` | /api/devices/status | 10s | ADB connection status |
| `sensor.photogrammetry_statistics` | /api/statistics | 10s | Lifetime statistics |

### Template Sensors (30+ Total)

**Progress Tracking:**
- `sensor.photogrammetry_progress` - Percentage complete
- `sensor.photogrammetry_current_position` - Current position number
- `sensor.photogrammetry_total_positions` - Total positions
- `sensor.photogrammetry_remaining_positions` - Positions left
- `sensor.photogrammetry_completed_count` - Completed count
- `sensor.photogrammetry_completed_stacks` - Stacks completed
- `sensor.photogrammetry_estimated_time_remaining` - Seconds remaining
- `sensor.photogrammetry_estimated_completion_time` - ETA timestamp
- `sensor.photogrammetry_started_at` - Start time

**Stacking Pipeline:**
- `sensor.photogrammetry_odd_slot_stacking` - Odd slot status
- `sensor.photogrammetry_even_slot_stacking` - Even slot status
- `sensor.photogrammetry_stacks_processing` - Active stacking count
- `sensor.photogrammetry_odd_slot_position` - Latest odd position
- `sensor.photogrammetry_even_slot_position` - Latest even position

**Session Details:**
- `sensor.photogrammetry_status_text` - Human-readable status
- `sensor.photogrammetry_session_id` - Current session ID
- `sensor.photogrammetry_can_resume` - Is paused?
- `sensor.photogrammetry_photos_per_burst` - Photos per position

**Crop Status:**
- `sensor.photogrammetry_crop_progress` - Crop percentage
- `sensor.photogrammetry_crop_status` - Crop status text
- `sensor.photogrammetry_total_cropped` - Cropped count
- `sensor.photogrammetry_crop_failures` - Failed crops

**Error Tracking:**
- `sensor.photogrammetry_error_message` - Last error
- `sensor.photogrammetry_consecutive_failures` - Failure count
- `sensor.photogrammetry_retry_count` - Retry attempts

**ADB Status:**
- `sensor.photogrammetry_adb_server_status` - Server running
- `sensor.photogrammetry_adb_device_status` - Connected devices
- `sensor.photogrammetry_s10_adb_status` - S10 status
- `sensor.photogrammetry_s24_adb_status` - S24 status

### Automations

| Automation | Trigger | Action |
|------------|---------|--------|
| `photogrammetry_auto_start_threading` | Toggle ON | Start session |
| `photogrammetry_auto_stop_threading` | Toggle OFF | Stop session |
| `photogrammetry_immediate_update_on_start` | Toggle ON | Force sensor update |

---

## 6. Storage & Folder Structure

### Base Path
`/mnt/pictures/photogrammetry/` (Container 104)

### Session Structure (Multi-Session Support)
```
/mnt/pictures/photogrammetry/
├── _processing/               # NOT used by the automated process (v5.17+). KEEP — it is the user's manual-testing Syncthing landing zone. Do NOT delete.
├── _lifetime_stats.json       # Lifetime statistics
├── coin_1/
├── coin_2/
├── ...
└── coin_9/                    # Example session
    ├── session.json           # Session metadata
    ├── _session_1/            # First orientation (raw photos only)
    │   ├── pos001/            # Raw burst photos (10 images)
    │   ├── pos002/
    │   └── ...
    ├── _session_2/            # Second orientation (flipped coin)
    │   ├── pos001/
    │   ├── pos002/
    │   └── ...
    ├── _stacked_session_1/        # Focus-stacked images (session 1) — single-shot mode stores the originals copied through
    ├── _stacked_session_2/        # Focus-stacked images (session 2)
    ├── _stacked_cropped_session_1/  # Cropped images (uniform size)
    └── _stacked_cropped_session_2/
```

### Multi-Session Feature
When rescanning the same object at a different orientation:
1. System detects existing `_session_N` folders
2. Automatically creates `_session_N+1`
3. Stacked images stored in `_stacked_session_N/`
4. Cropped images stored in `_stacked_cropped_session_N/`

### Permissions
All session folders created as `sambauser:sambauser` with mode `775/664` for Samba accessibility.

---

## 7. Photo Transfer (ADB-Pull)

**As of v5.17, photo transfer is direct `adb pull` — Syncthing is retired.** Measured ~15 MB/s vs Syncthing's ~4.5 MB/s, and the transport is now self-contained (no background daemon; transfer happens only during an active session).

### How it works (per position, inside `_process_single_position`)
1. Resolve the ADB device once; `snapshot_phone_burst_prefixes()` records the burst prefixes already on the phone ("the leftovers").
2. `trigger_camera()` fires the burst.
3. `poll_phone_dcim_stability()` confirms the fresh burst on the phone (count + prefix + max suffix).
4. **Guard:** the selected burst prefix must NOT be in the pre-trigger snapshot — if it is, the trigger produced no new burst (dropped capture) → the position fails and retries.
5. `delete_stale_phone_bursts(keep_prefix=burst_prefix)` — clears every leftover, keeping only the fresh batch (the phone is a dedicated rig; nothing else on DCIM matters).
6. `adb_pull_burst()` pulls the burst into a per-position staging dir, verifies it (count, continuous suffixes, non-truncated), retries on failure (re-resolving the device each retry).
7. Archive staging → `posNNN/`.
8. `delete_burst_from_phone()` — only if the full burst archived cleanly. Phone DCIM is then empty.

### Phone Setup (Samsung S10)
- OpenCamera app saves to `/sdcard/DCIM/OpenCamera/`
- **Syncthing must NOT be running on the phone** — it would race the `adb pull` (delete bursts mid-transfer). `start_session` runs a `pidof syncthing` guard and refuses to start if it is up.
- The phone DCIM is wholly managed by the backend during a session: stale bursts cleared, fresh burst pulled + deleted.

### Syncthing — removed from the automated process, but RETAINED for manual testing
The **automated photogrammetry process** no longer uses Syncthing at all (the `SYNCTHING_*` constants, `wait_for_server_sync()`, and `wait_for_syncthing_completion()` were deleted from `photogrammetry.py`).

**Syncthing is NOT decommissioned, though** — the user keeps it for manual testing (manually trigger the phone, let Syncthing sync the photos to `/mnt/pictures/photogrammetry/_processing/`). So:
- The phone Syncthing app (`com.github.catfriend1.syncthingandroid`) and CT 103's folder `5grgy-q8shx` → `_processing/` **stay in place**. Do NOT uninstall/decommission them.
- `/mnt/pictures/photogrammetry/_processing/` is the manual-testing landing zone — **do NOT delete it**.
- **The only rule:** the phone's Syncthing app must NOT be running when an *automated* session runs (it would race the `adb pull`). The `start_session` `pidof syncthing` guard enforces this. Toggle Syncthing OFF before an automated run, back ON for manual testing.

---

## 8. Session Lifecycle

> **v5.15 — INLINE-SYNCHRONOUS.** The async-capture model (v5.9–v5.14: separate
> capture + reconciler threads, `pending_archives` state machine) was reverted.
> One processing thread per session does everything serially. See §14 v5.15.

### Session States (v5.15 inline)
| State | Description |
|-------|-------------|
| `idle` | Ready to start |
| `active` | Processing thread running |
| `paused` | Processing paused by user between positions |
| `stopped` | User stopped the session |
| `retrying` | Phone burst detection retry in progress |
| `blocked` | Capture-side failure (phone unresponsive) — user must resume |
| `complete` | All positions captured, archived, stacked. Zero failures. |
| `complete_with_failures` | Session finished but ≥1 position failed (capture or stack). See `failed_positions`. |
| `complete_with_errors` | Legacy alias of `complete_with_failures` (kept for backward compat) |
| `error` | Critical error in the processing thread |
| `interrupted` | Service died with session in flight |

### Processing Flow (v5.17 — inline synchronous, single thread, ADB-pull transport)
```
1. POST /api/session/start
   - Resolve ADB device via get_active_adb_device()
   - Wi-Fi link snapshot (v5.18): one preflight log line via `cmd wifi status` on the phone —
     band (2.4/5/6 GHz), frequency MHz, RSSI dBm, link speed Mbps, SSID. Non-fatal on failure.
   - 2.4GHz detection + slow-link mode (v5.22 — detection-only, rolled back from v5.19–v5.21):
     if the preflight reports band `2.4GHz`, the session sets module-level
     `SLOW_LINK_ACTIVE=True` (reset every session start) and emits a loud warning:
     `[WIFI] WARNING: phone is on 2.4GHz -- extended timeouts active for this session; move phone closer to AP or switch to 5GHz SSID to recover throughput`.
     While the flag is set, `adb_pull_burst` scales its subprocess timeout 120s → 180s and
     `poll_phone_dcim_stability` scales its deadline 30s → 45s via
     `SLOW_LINK_MULTIPLIER = 1.5`. No automated Wi-Fi cycle is attempted — see v5.22 in
     §14 for why the v5.19–v5.21 self-heal was removed. Recovery to 5GHz requires manual
     phone-side action (move the phone, switch SSID, or fix AP band steering); the session
     itself will still run to completion on 2.4GHz, just slower.
   - pidof-syncthing guard (refuses to start if Syncthing is up on the phone)
   - Creates session folder
   - Spawns ONE processing thread

2. PROCESSING THREAD — for each position (1 to N), fully serial:
   a. Snapshot existing phone burst prefixes ("the leftovers")
   b. Trigger camera via ADB (keyevent 27)
   c. Confirm burst on phone via poll_phone_dcim_stability (ground truth: prefix + count)
   d. Guard: selected burst prefix must NOT be a pre-trigger leftover (else fail+retry)
   e. delete_stale_phone_bursts — clear every leftover, keep only the fresh batch
   f. adb_pull_burst — pull the burst into a staging dir, verify, retry on failure
   g. Archive staging → coin_XXX/_session_N/posNNN/
   h. delete_burst_from_phone — only if the full burst archived cleanly
   i. Launch focus-stack subprocess in dual odd/even slot (burst=1 short-circuits to a copy-through, see Single-Shot Mode)
   j. Rotate turntable by angular_distance
   The next position does not start until step (h) for this one returns.

   When all N positions done:
     - Wait for remaining stacks
     - Run unified crop analysis → _stacked_cropped_session_N/
       (ONLY if UNIFIED_CROP_ENABLED — currently False, so this is SKIPPED; see v5.16)
     - Set status to 'complete' or 'complete_with_failures'

3. Pause behavior:
   - Pause takes effect between positions; the in-flight position finishes first.

4. Restart recovery (check_interrupted_sessions on startup):
   - Any session left 'active'/'retrying' is marked 'interrupted'.
   - Resume via /api/session/<id>/resume re-spawns the processing thread.
```

### Dual Stacking Pipeline
- Odd positions (1, 3, 5...) stack in parallel with even positions (2, 4, 6...)
- The processing thread launches the stack subprocess and moves on to rotate +
  capture the next position; it waits on the previous odd/even stack only when
  that slot is needed again.
- **Bypassed in single-shot mode (burst=1)** — see next section.

### OpenCamera filename schemas (v4.3.1)

OpenCamera writes file names in one of two schemas, depending on whether the
shutter event was a burst or a single shot:

| Mode | Pattern | Example |
|---|---|---|
| Burst (≥2 photos) | `IMG_YYYYMMDD_HHMMSS_<N>.jpg` | `IMG_20260518_125426_0.jpg` ... `_9.jpg` |
| Single-shot | `IMG_YYYYMMDD_HHMMSS.jpg` (no trailing `_N`) | `IMG_20260518_125426.jpg` |

A single shared parser handles both: `parse_opencamera_filename()` in
`photogrammetry.py` returns `(prefix, suffix)` where single-shot suffix is
synthesised as `0`. Used by `poll_phone_dcim_stability`,
`snapshot_phone_burst_prefixes`, and `delete_stale_phone_bursts`. Globs in
`adb_pull_burst` and `delete_burst_from_phone` match both
`{burst_prefix}_*.jpg` and `{burst_prefix}.jpg`.

### Pre-trigger auto-cleanup (v4.3.1)

`_process_single_position` snapshots leftover burst prefixes on the phone
before each trigger. If any are found they are **automatically deleted** via
`delete_burst_from_phone()` before `trigger_camera` fires. Safe because the
rig is photogrammetry-only and the post-pull cleanup already wipes
non-archived files. Eliminates the failure loop where each retry inherits an
orphan from the previous attempt and the burst detector rejects it as
"non-continuous" or "stale."

### Single-Shot Mode (v4.3.0 / burst=1, added 2026-05-18)

For non-macro subjects (anything roughly ≥ 4 in deep where the phone's natural
DOF covers the model at standard working distance), focus stacking is
unnecessary. Setting `photos_per_burst = 1` switches the pipeline to a
copy-through path:

- **`stack_photos()`** and **`stack_photos_async()`** (photogrammetry.py
  lines ~1619/1649) detect `len(photos) == 1` and short-circuit. The single
  source image is `shutil.copy`-ed to the `_stacked_session_N/` output path
  synchronously, then a placeholder `Popen(['true'])` is returned so the
  dual-slot caller pipeline (`check_and_crop_completed_stack`,
  `wait_and_log_stack_process`) sees a normal "completed quickly" process.
- The `focus-stack` CLI binary is never invoked.
- Output filenames are identical to the stacked path
  (`pos{N:03d}_stacked.jpg`), so Meshroom / Postshot / SuperSplat consume the
  same way.
- **EXIF is preserved** by the copy (the focus-stack binary strips most EXIF).
  Downstream tools that read focal length / aperture from EXIF get richer
  metadata than they would on stacked outputs. Mild plus.

**Known cosmetic quirks** (deferred to a later cleanup):

- The dashboard's odd/even **Stacking** slot indicators stay `idle` for the
  whole session — accurate but visually confusing next to the position
  progress bar.
- Lifetime stats rollups iterate `[10, 20, 30, 40, 50]` photo-count buckets
  (`photogrammetry.py:2796,2913`). Burst=1 sessions are silently excluded
  from `metrics_by_photo_count`, `stacking_stats.by_photo_count`, and the
  per-burst-count dashboard cards. They DO count in `successful_stacks` and
  per-session timings.
- Throughput estimator at line 2761 uses a hardcoded default of 30 if
  `photos_per_burst` is not yet set — during position 1 of a burst=1 session
  (before auto-detect lands at line 2348), throughput briefly reports 30x
  reality. Self-corrects after position 1.

**When to use it:** subjects roughly ≥ 4 in deep where you can stand ~12–18 in
away at f/8–f/11. For coin-scale macro work, leave at the standard burst=10.

**Auto-crop warning:** the unified-crop heuristic (`bg_std < 20` → UNIFORM
threshold, else VARIABLE; `>95%-of-min-dim` rejection) was tuned on
10-image-stacked coin frames. A single raw phone JPG of a larger subject has
different background variance and fills more of the frame — likely to
mis-classify or reject. **Set `auto_crop_enabled: false` per-session when
running burst=1**, or rely on Meshroom's own crop step downstream.

### Restart / Resume Semantics (v5.15 inline)
- On service restart, `check_interrupted_sessions()` marks any in-flight session
  `interrupted`. It is NOT auto-resumed — the user resumes it explicitly.
- `/api/session/<id>/resume` re-spawns the single processing thread, continuing
  from `current_position`. Already-archived `posNNN/` folders are left in place;
  archive is idempotent.
- `get_active_session()` surfaces any session whose status is active/error/
  blocked/paused/interrupted/stopped/retrying so it stays visible in HA.

### Performance Expectations (v5.15 inline)
| Phase | Time |
|---|---|
| Camera trigger | ~0.2 s |
| Phone burst detection | ~5 s |
| Sync + archive (blocking) | ~22 s |
| Rotation | ~1.5 s |
| **Per-position TOTAL** | **~25–30 s** |
| **360-position session** | **~2.5–3 hr** |

The async model claimed ~7 s/position, but that was *capture-phase only* — the
downloads still had to drain afterward, so true session-completion time was
similar. Inline trades the misleading headline number for reliability: it paces
the phone (capture is idle while each burst downloads), which is why inline
sessions ran clean and async sessions did not.

---

## 9. Key Features

### Unified Crop Analysis (v5.4)
Post-session analysis ensures consistent crop box across all images:

**Algorithm:**
1. After all images stacked, analyze ALL images together
2. Detect object bounds in each image
3. Calculate rotation center using robust median (filters outliers)
4. Size crop to fit maximum object extent + 15% padding
5. Apply IDENTICAL crop box to all images

**Benefits for Photogrammetry:**
- Fixed viewpoint (turntable axis preserved)
- Consistent scale across all angles
- Geometrically correct for 3D reconstruction

**Data Stored in session.json:**
```json
"unified_crop_params": {
  "1": {
    "rotation_center": [1844, 1616],
    "crop_size": 2257,
    "confidence": 0.595,
    "max_object_dims": [1228, 1963]
  }
}
```

### Notifications (v5.5)
Real-time notifications via Home Assistant:

**Channels:**
- Browser: HA persistent_notification (shows in sidebar)
- Mobile: notify.mobile_app (Companion app push)

**Triggers:**
- Session complete - notifies when all positions processed
- Errors/failures - notifies on validation errors, sync failures, etc.
- Manual intervention - critical errors requiring attention

**Implementation:**
- Notifications handled by Home Assistant automations monitoring `sensor.photogrammetry_session`
- Old notifications automatically cleared on new session start


### Error Handling
- Global error handlers return JSON (never HTML)
- All endpoints return HTTP 200 (errors in JSON body)
- Auto-retry on stack failures (max 3 attempts)
- Circuit breaker after 3 consecutive failures

### Session Persistence
Sessions survive service restarts via JSON files:
- `/mnt/pictures/photogrammetry/{object_name}/session.json`
- Contains all state: status, positions, timings, stats

### Backend-Controlled Polling
HTTP Cache-Control headers tell Home Assistant when to poll:
- `idle` state: 60 second cache (slow polling)
- `active/paused/retrying` states: 5 second cache (fast polling)

---

## 9.5 Subject Prep for Downstream Reconstruction

This pipeline produces images; **how you present the subject** determines whether Reality Capture / Meshroom / Postshot can actually align them. Lessons from real attempts:

### The turntable trap

Because the camera is fixed and the subject rotates, photogrammetry tools default to the wrong assumption ("camera moves, subject is static"). They lock onto static-background features (rug, sweep curtain, table edge) and conclude the camera barely moved → alignment fails (in our satellite test, RC aligned 3/30 frames).

Two ways out, in increasing order of robustness:

### Option A — Mask out the static background (post-capture fix)

For each stacked image, write a per-frame mask that includes ONLY the rotating subject + base + turntable disc. Tools tested:

- **rembg with U2Net** — drops the rod and base, only keeps the satellite body. Useless for this case.
- **Pixel-variance mask** (compute std across all frames, threshold) — works but produces a "halo" of swept-through background pixels. Coverage ~35% with shared mask, ~24% with per-frame hybrid (median-diff + variance shared region intersected).
- **GrabCut seeded by variance mask** — cleanest per-frame boundaries, slower (~3-5 s/frame).

Reference batch script lives at `/home/claudeai/wtc_pair/` style — adapt the variance-hybrid pattern. Output: 4-channel PNGs (alpha = mask). RC reads alpha as mask automatically.

### Option B — Add markers to the turntable surface (capture-stage fix, much better)

Print coded fiducial markers and stick them on the white turntable disc around the subject's footprint. They rotate WITH the subject, giving the photogrammetry tool unambiguous, sub-pixel-accurate, identity-tracked feature anchors that move in the same plane as the subject. Forces the correct "object-fixed, camera-moves" interpretation without any masking step.

**For Reality Capture: use RC's own coded marker system.** RC ships with native CCTag-style detection (`Alignment → Detect markers`). AprilTag/ArUco are detectable but need external Python+OpenCV → CSV import. Stick with native if you're on RC.

Layout:
- 6-12 unique markers in a ring around the subject's footprint
- Each marker ~30-50 mm so it occupies ~50-100 px per phone frame
- Distributed enough that the subject occludes only a few from any angle
- If marker spacing is measured (calipers), RC's `control point distance` constraint produces metrically-accurate reconstruction

**Cheapest alternative if you don't want to set up coded markers:** print any chaotic high-contrast pattern (calibration mat, even a newspaper page) and lay it on the turntable. Gives the matcher tons of arbitrary features — no scale calibration but alignment works.

### When the turntable surface is too small for a marker ring

If the subject fills the turntable and there's no room for a surrounding ring of markers, use one of:

- **Stick small markers (15-25 mm) on the subject's base/plinth itself.** The plinth rotates with the subject, so markers on its top edge or side faces work identically. 4 small ones on the side faces of a rectangular plinth + 1-2 on the top edge gives 3-5 visible per frame as it rotates.
- **Build a marker tower.** Print markers on a paper cylinder (or wrap on a soda can / small dowel), stand it vertically next to the subject at roughly the same height, glue it to the turntable so it rotates together. Different markers face the camera at each rotation. Useful when the subject is too irregularly shaped to stick markers directly.
- **Cheap-and-fast option:** 4-6 distinct high-contrast stickers (different shapes/colors, easy for a human to distinguish) on visible faces of the plinth or base. No RC marker-detector flow needed — they just register as strong arbitrary features. No scale calibration, but alignment works.

You don't need 12 markers. RC's matcher only needs 2-3 visible per frame, and they don't even need to be the *same* 2-3 across consecutive frames as long as there's overlap. 6-8 markers total distributed across plinth + tower is plenty.

If the subject itself has high-contrast geometric features (panel patterns, decals, structured surfaces), markers are *supplementing* not replacing — feature-rich subjects need fewer markers than smooth/monochrome ones.

### Markers > masking when both are available

Markers solve the same problem at capture time that masking solves at post time, with better precision and no per-session computation. Default to markers for new scans; only fall back to masking for legacy/uncaptured-with-markers data.

### Coverage tips orthogonal to markers/masking

- **One elevation alone reconstructs only the equatorial belt of the subject.** For complete coverage, run 2-3 sessions at different camera tilts (horizon / ~30-45° looking down / ~30-45° looking up).
- **Specular/metallic surfaces** (thin metal rods, mirror-finish parts) reconstruct poorly. Matte-spray treatment (AESUB Blue, washable, evaporates in hours) fixes most of it.
- **Single-shot mode (burst=1)** is fine for subjects ≥4 in deep where the phone's natural DOF covers everything. Smaller subjects (coins, jewelry) need burst+stack to extend DOF.

---

## 10. Dashboard Reference

### Dashboard Views
1. **Control Panel** - Main session control, status, configuration
2. **ADB Dashboard** - Device connection management
3. **Performance Stats** - Lifetime statistics and metrics

### Dashboard File
`/mnt/documents/personal/alec/claudeai/photogrammetry-dashboard.yaml`

### Key Dashboard Cards
- Session control buttons (START/PAUSE/STOP/RESUME/RESET)
- Progress bar with gradient color
- Session status entities
- Configuration inputs
- Dual stacking pipeline status
- Crop status card
- Manual turntable rotation buttons

---

## 11. API Reference

### Session Endpoints

```bash
# Start session
curl -X POST http://192.168.0.176:5000/api/session/start \
  -H "Content-Type: application/json" \
  -d '{
    "object_name": "coin_9",
    "total_positions": 36,
    "angular_distance": 10.0,
    "auto_crop_enabled": true
  }'

# Get current session
curl http://192.168.0.176:5000/api/session/current

# Pause session
curl -X POST http://192.168.0.176:5000/api/session/{id}/pause

# Resume session
curl -X POST http://192.168.0.176:5000/api/session/{id}/resume

# Stop session
curl -X POST http://192.168.0.176:5000/api/session/{id}/stop

# Reset session
curl -X POST http://192.168.0.176:5000/api/session/{id}/reset
```

### Device Endpoints
```bash
# Get ADB status
curl http://192.168.0.176:5000/api/devices/status

# Select device
curl -X POST http://192.168.0.176:5000/api/devices/select \
  -H "Content-Type: application/json" \
  -d '{"device_ip": "adb-RF8M20STA5T-rIxgXQ._adb-tls-connect._tcp"}'

# Disconnect all
curl -X POST http://192.168.0.176:5000/api/devices/disconnect
```

### Statistics Endpoint
```bash
curl http://192.168.0.176:5000/api/statistics
```

### Response Format
All endpoints return JSON with HTTP 200:
```json
{
  "session_id": "20251203_033457",
  "status": "active",
  "progress_percent": 75.0,
  "current_position": 27,
  "total_positions": 36,
  "error": null
}
```

---

## 12. Troubleshooting

### Phone Not Connecting
1. Check ADB status: `curl http://192.168.0.176:5000/api/devices/status`
2. Enable Wireless Debugging on Samsung S10
3. Restart ADB server on container 104
4. Check mDNS resolution: `systemctl status avahi-daemon`

### Stacking Failures
- Check photos exist in position folder
- Verify OpenCV can read images
- Check for corrupted/empty image files
- Review stacking error in session.json

### Session won't start — "Syncthing is still running on the phone"  *(v5.17)*
- `start_session` runs a `pidof syncthing` guard and refuses to start if Syncthing is up on the phone (it would race the `adb pull`).
- Fix: stop the Syncthing app on the phone (don't uninstall — it's kept for manual testing), then start the session again. With the phone app stopped, CT 103's folder can be left as-is.

### ADB-pull failure — a position's burst won't transfer  *(v5.17)*
- `adb_pull_burst` retries internally (re-resolving the device each retry). If it still fails, the position is marked failed (`failed_positions`) and capture continues.
- What to do:
  1. Check the burst on the phone via ADB: `adb shell ls /sdcard/DCIM/OpenCamera/ | grep <prefix>`. Count the files.
  2. **If the phone has the full burst** → transport problem (ADB-over-WiFi dropped, phone re-associated). Check `adb devices`; re-shoot the failed position.
  3. **If the phone is short or empty** → OpenCamera produced an incomplete/no burst (trigger-arming race, phone load). No transport fix recovers photos never captured — re-shoot that position. (A trigger that produced *no* new burst is caught by the pre-trigger snapshot guard and fails fast.)
- Recovery: re-shoot the failed positions in a short follow-up session. The `pos{NNN}/` folder is left in place; a re-shoot overwrites it cleanly.

### Phone offline / unreachable after a Wi-Fi event  *(v5.22)*
- Symptom: `adb devices` shows the phone as offline or missing entirely after the phone's Wi-Fi was disabled/re-enabled, the AP cycled, or the phone roamed.
- Cause: Android does NOT auto-restart the Wireless Debugging service when Wi-Fi comes back up. The radio is on and the phone has an IP, but `adbd` is not listening, so the host has no way to reconnect from CT 104.
- **Fix (must be done on the phone, by hand):** Settings → Developer Options → Wireless Debugging → toggle OFF then ON. Re-verify with `adb devices` from CT 104.
- This was confirmed empirically on 2026-05-16 during v5.19–v5.21 self-heal testing — the host-driven `svc wifi disable/enable` cycle left the phone in exactly this state and was unrecoverable without the manual toggle. The automated cycle was removed in v5.22; see §14.

### `complete_with_failures` Status  *(v5.15 inline)*
- The session captured all positions but ≥1 failed — either capture/transfer (in `failed_positions`) or focus-stacking.
- See `failed_positions` for which positions need a re-shoot.

### Home Assistant Errors
- Check REST sensor states for `unavailable`
- Verify API endpoints return HTTP 200
- Reload REST integration after config changes
- Check for `json_attributes_path` in old config (remove it)

### Service Issues
```bash
# Check service status
sudo pct exec 104 -- systemctl status photogrammetry.service

# View logs
sudo pct exec 104 -- journalctl -u photogrammetry.service -f

# Restart service
sudo pct exec 104 -- systemctl restart photogrammetry.service
```

### Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| 25% idle CPU | Duplicate instances | Fix systemd Restart= setting |
| JSON parsing errors | `json_attributes_path: "$"` | Remove from REST sensors |
| Crops off-center | Position 1 poor detection | Restart session |
| Session won't start | Syncthing still running on phone | Stop Syncthing app on phone (v5.17 guard) |
| Slow transfer | (n/a — adb pull ~15 MB/s) | Check `adb devices` / WiFi if pulls retry |
| Buttons not working | Missing automations | Ensure automations.yaml deployed |

---

## 13. Configuration Files Reference

### Complete File List

| Location | File | Version | Purpose |
|----------|------|---------|---------|
| Container 104 | `/opt/photogrammetry/photogrammetry.py` | inline-2026-05-16e | Backend API — inline-synchronous single processing thread; direct ADB-pull transport (no Syncthing); unified crop disabled; Wi-Fi link preflight log + 2.4GHz **detection-only** warning & slow-link mode (1.5× timeouts). v5.19–v5.21 automated self-heal removed in v5.22 — see v5.22 in §14. See v5.15/v5.16/v5.17/v5.18/v5.22 |
| Container 104 | `/etc/systemd/system/photogrammetry.service` | - | Systemd service |
| Samba /claudeai/ | `photogrammetry.md` | v5.22 | Main documentation |
| Samba /claudeai/ | `photogrammetry-config.yaml` | v4.2 | Combined HA config (legacy, deprecated) |
| Samba /claudeai/photogrammetry/ | `photogrammetry-dashboard.yaml` | - | Dashboard YAML (+ Time Breakdown + Pipeline Completion cards) |
| Samba /claudeai/photogrammetry/ | `inputs.yaml` | v4.2.6 | Input controls |
| Samba /claudeai/photogrammetry/ | `rest_commands.yaml` | v4.2.6 | API commands |
| Samba /claudeai/photogrammetry/ | `scripts.yaml` | v4.2.6 | Helper scripts |
| Samba /claudeai/photogrammetry/ | `automations.yaml` | v4.2.6 | Auto-start/stop |
| Samba /claudeai/photogrammetry/ | `sensors.yaml` | v4.2.6 | All sensors (+ 3 time-breakdown + 4 completion-rate sensors) |
| Samba /claudeai/photogrammetry/ | `photogrammetry-tab-title.js` | v5.24 | Lovelace custom element. Drop into HA `/config/www/`, register as a JS module resource, place a card on the dashboard. Drives `document.title` from `sensor.photogrammetry_progress`. See v5.24 in §14. |
| Samba /claudeai/ | `connect-phone.cmd` | v5.23 | Windows helper: resolves phone address via SSH to CT 104, `adb connect`s, launches scrcpy. Keeps cmd window open + prints exit code + hints on scrcpy failure. Lives at the documents-share claudeai root (NOT under `photogrammetry/` and NOT on the pictures share — see v5.23 note). |

### Deprecated/Archive Locations
- `Samba /claudeai/photogrammetry package sensor/` - Old v4.2 files (has bugs)
- `Samba /claudeai/archive/photogrammetry-backups/` - Historical backups
- `Samba /claudeai/archive/documentation-backups/` - Old documentation

---

## 14. Version History

### v5.24 (2026-05-24) — Live capture % in the Chrome tab title

**Scope:** Dashboard / Lovelace only. Backend unchanged (still `inline-2026-05-16e`). HA package YAMLs untouched.

**What:** The Chrome tab title (and OS taskbar entry) now reflects live session progress while a capture is running, e.g. `42% • Photogrammetry`, so the user can monitor progress without focusing the dashboard tab. Reverts to `Photogrammetry` when idle.

**Entity:** `sensor.photogrammetry_progress` (the well-established 0–100 sensor that reads `progress_percent` directly from the backend `get_current_session()` response, already used elsewhere on the dashboard). **Not** `sensor.photogrammetry_overall_completion` — a multi-agent review flagged that one as defined-but-empty: the template depends on a `pipeline_progress` attribute the backend does not publish, so it reads `0` forever. If/when the backend grows `pipeline_progress`, the card's `entity:` swaps with no code change.

**How:** A ~50-line custom Lovelace element (`photogrammetry-tab-title.js`) registered as a JS-module resource. It subscribes via the standard Lovelace `hass` setter and writes `document.title` reactively. Zero visual footprint (`display:none`). Snapshots/restores prior `document.title` on connect/disconnect so navigating away cleans up — review caught a lifecycle bug in an earlier draft where saving the prior title in `setConfig` would corrupt sibling-tab titles; fixed by moving the snapshot into `connectedCallback`.

**Deployment** (done live via Samba + ha-mcp on 2026-05-24):

1. JS file uploaded to `\\192.168.0.154\config\www\photogrammetry-tab-title.js`. Served as `/local/photogrammetry-tab-title.js`.
2. Lovelace resource registered via `ha_config_set_dashboard_resource` (resource_id `975e5d459a5a461182db152676946c84`, type `module`).
3. Card prepended to `dashboard-photogrammetry` view 0, section 0, via `ha_config_set_dashboard` python_transform.
4. User-side action remaining: **hard-refresh** the dashboard (Ctrl+Shift+R) so the browser fetches the new resource.

The repo copy at `Samba /claudeai/photogrammetry/photogrammetry-dashboard.yaml` is the doc snapshot; the live storage-mode dashboard is `.storage/lovelace.dashboard_photogrammetry`. They're in sync as of v5.24 deploy.

**Verification:**
- Set `sensor.photogrammetry_progress` to `42` via Developer Tools → States — tab title should change to "42% • Photogrammetry" within ~1 s.
- Set it back to `0` / unknown — title reverts to "Photogrammetry".
- Open the dashboard in two tabs, navigate one away — surviving tab's title stays correct (lifecycle-bug fix verification).

### v5.23 (2026-05-24) — `connect-phone.cmd` keep-open + filed under `photogrammetry/`

**Scope:** Windows-side phone-connection helper only. Backend unchanged (still `inline-2026-05-16e`).

**What changed:**
- `connect-phone.cmd` **stays at `Samba /claudeai/connect-phone.cmd`** (documents-share claudeai root). v5.23 attempted to relocate it twice — first into `Samba /claudeai/photogrammetry/`, then into `Samba /pictures/photogrammetry/` — and both broke the user's working setup. The pictures-share copy failed to execute under Windows (the `.lnk` shortcuts that live in that folder work because they target *local* `.bat` files — they don't execute anything off the share). The documents/photogrammetry/ copy was just an unnecessary move. The original claudeai-root location is the source of truth; do not relocate it again without a specific reason.
- Final block of the script now captures scrcpy's exit code, prints a one-line summary (clean exit vs. failure) plus a short list of common fixes (re-accept USB-debug prompt, `adb kill-server`+`start-server`, Wireless Debugging toggle, wired-USB fallback), and `pause`s so the cmd window stays open. Previously, any scrcpy launch error scrolled past and the window closed before the user could read it.

**Why:** intermittent scrcpy failures (e.g. ADB authorisation dropped after a phone reboot) were invisible because the message and cmd window vanished together. Manual workaround was to open a cmd window first and run `scrcpy.exe` by hand; this change makes the .cmd self-diagnosing.

**Path:** `\\<samba>\documents\personal\alec\claudeai\connect-phone.cmd` (typically `Y:\personal\alec\claudeai\connect-phone.cmd`). Desktop shortcut path unchanged from before v5.23.

**Line-endings trap (`.cmd` files):** Windows `cmd.exe` needs CRLF on `.cmd`/`.bat` files. Linux-side editors (including the Claude Code Edit tool) normalise to LF on save, which silently breaks the script (errors range from `'^@echo'` to access-denied-looking failures). After any Linux-side edit of `connect-phone.cmd`, re-CRLF it before saving back to the samba share:
```
sed -i 's/$/\r/' /mnt/pictures/photogrammetry/connect-phone.cmd
od -c <file> | head -1   # verify lines end \r\n, not just \n
```

### v5.22 (2026-05-16) — Rolled back v5.19–v5.21 Wi-Fi self-heal — detection-only
**Backend version: inline-2026-05-16e**

**This is a revert.** The v5.19–v5.21 automated 2.4GHz self-heal was empirically proven non-functional on this phone during live testing on 2026-05-16 and has been removed. **Do not re-attempt the same `svc wifi disable/enable` cycle approach** — it does not recover ADB on this device.

**Why it failed (the lesson for future-you):**
- Cycling Wi-Fi via `adb shell svc wifi disable/enable` (even as one detached on-phone shell, as in v5.20+) successfully re-enables the radio and re-associates the phone to the AP. But Android does **NOT** auto-restart the Wireless Debugging service after a Wi-Fi cycle. `adbd` never re-listens, so the host has nothing to reconnect to — by any strategy, ever.
- The 2026-05-16 test left the phone with Wi-Fi up and an IP, but ADB completely dead. Recovery required physically picking up the phone and toggling Settings → Developer Options → Wireless Debugging off/on.
- Independently, the v5.21 Strategy 1 (`adb connect <prior_id>`) was broken when `prior_id` was an mDNS-form id like `adb-RF8M20STA5T-rIxgXQ._adb-tls-connect._tcp` — `adb connect` resolves the argument via DNS, not mDNS, so the call fails fast. Strategies 2 and 3 then ran against an already-dead `adbd` and timed out.
- Net: there is no host-side workaround. The cycle approach is a dead end on this phone/Android version.

**Removed (the other agent owns the .py edits):**
- `cycle_wifi_and_recheck()`
- `reconnect_adb()`
- `reconnect_adb_via_mdns()`
- `_verify_device_present()`
- `_extract_serial_from_device_id()`
- The cycle/reconnect call site in `start_session`

**Kept (detection + slow-link mode only):**
- `get_wifi_link_info()` — band/freq/RSSI/link-speed parsed from `cmd wifi status` at session start
- `[WIFI]` preflight log line (band, freq, RSSI, link speed, SSID)
- `SLOW_LINK_MULTIPLIER = 1.5` and module-level `SLOW_LINK_ACTIVE` flag (reset each session start)
- 1.5× multiplier applied to `adb_pull_burst` subprocess timeout (120 → 180s) and `poll_phone_dcim_stability` deadline (30 → 45s) when band is 2.4GHz at session start
- Loud `[WIFI] WARNING: phone is on 2.4GHz ...` log line at session start telling the user to act

**2.4GHz recovery is now MANUAL.** If the preflight reports 2.4GHz, the session will still run to completion with extended timeouts, but to actually restore 5GHz throughput the user must: move the phone closer to the AP, switch to a 5GHz-only SSID, or fix AP band-steering. There is no automation behind this — see Troubleshooting §12 ("Phone offline / unreachable after a Wi-Fi event") for the related manual Wireless-Debugging re-enable step.

### v5.21 (2026-05-16) — Belt-and-braces reconnect: 3 strategies, mDNS-empty resilient
**Backend version: inline-2026-05-16d**

The v5.20 self-heal relied solely on `adb mdns services` to rediscover adbd after a Wi-Fi
cycle. Observed on the live CT 104: that command can return an empty service list even when
the phone is reachable and advertising as `adb-RF8M20STA5T-rIxgXQ._adb-tls-connect._tcp` —
in which case the reconnect would time out and self-heal would fail despite the phone
having re-associated successfully.

`reconnect_adb_via_mdns` is replaced by `reconnect_adb(prior_device_id, timeout_seconds=20)`
which tries three strategies in order, each with its own short budget so the total stays
within `timeout_seconds`:

1. **Prior-id direct (~3s)**: `adb connect <prior_device_id>`. Works when adb has cached
   the mdns-name→host:port resolution, or when `prior_device_id` is already a host:port.
   Verified-live test: returned same id, `adb devices` shows `device`.
2. **mDNS poll (remainder)**: existing logic — poll `adb mdns services` for
   `_adb-tls-connect._tcp` rows, prefer same-serial entries, `adb connect <host>:<port>`.
3. **Post-hoc scan (~3s)**: re-run `adb devices` and accept the phone if it re-appeared
   on its own with any id as `device`.

Each strategy logs its attempt and outcome with `[WIFI]` prefix; on success the winning
strategy is named (e.g. `[WIFI] reconnected via prior-id (strategy 1) as <id>`). The
`cycle_wifi_and_recheck` call site snapshots the incoming `device_id` as `prior_id` and
passes it into `reconnect_adb`. `reconnect_adb_via_mdns` is kept as a thin compat alias.

### v5.20 (2026-05-16) — Bugfix: v5.19 Wi-Fi self-heal was non-functional
**Backend version: inline-2026-05-16c**

Fixes the `cycle_wifi_and_recheck` helper introduced in v5.19. The original implementation issued `adb shell svc wifi disable` and `adb shell svc wifi enable` as two separate adb invocations — but `disable` kills the adb-over-wifi transport, so the second invocation never reached the phone. The cycle was a no-op (a one-way disable) and the self-heal never actually re-associated anything.

The fix:
- The disable/enable is now run as ONE detached on-phone shell so the re-enable executes locally on the phone after the host loses its link:
  `adb shell "nohup sh -c 'svc wifi disable; sleep 3; svc wifi enable' >/dev/null 2>&1 &"`
- After each cycle, the host rediscovers adbd via mDNS (`adb mdns services`, looking for `_adb-tls-connect._tcp`) because adbd's port changes on every Wi-Fi reassoc on Android 11+. Entries whose serial matches the prior device are preferred, then `adb connect <host>:<port>`.
- Settle timer bumped 8s → 12s to absorb the on-phone 3s sleep + reassoc time.
- If the adb connection can't be re-established after all retries, the session logs a warning but does NOT abort.
- `start_session` now updates its `device_id` from the helper's return value, since the post-reconnect id (`host:port`) may differ from the original.

Slow-link mode, threshold logic, and "never abort" semantics from v5.19 are unchanged.

### v5.19 (2026-05-16) — 2.4GHz Wi-Fi self-heal + slow-link mode
**Backend version: inline-2026-05-16b**

Extended the v5.18 preflight: if the phone reports band `2.4GHz`, the new `cycle_wifi_and_recheck(device_id, max_retries=3, settle_seconds=8)` helper toggles `adb shell svc wifi disable/enable` up to 3 times in hopes the phone re-associates on a 5/6GHz BSSID (consumer router, no AP-side API). On recovery logs `[WIFI] recovered to <band> after N cycle(s)`. If still 2.4GHz after 3 cycles, logs `[WIFI] WARNING: still on 2.4GHz after 3 cycles -- enabling extended timeouts for this session` and sets module-level `SLOW_LINK_ACTIVE=True`. While active, `adb_pull_burst` scales its `adb pull` subprocess timeout (120s → 180s) and `poll_phone_dcim_stability` scales its deadline (30s → 45s) by `SLOW_LINK_MULTIPLIER=1.5`. Flag is reset at every session start; never aborts a session (even total wifi-info read failure logs `[WIFI] band unknown -- proceeding with defaults` and continues).

### v5.18 (2026-05-16) — Wi-Fi link-info preflight logging
**Backend version: inline-2026-05-16a**

Added Wi-Fi link-info preflight logging (band/freq/RSSI/link-speed/SSID) at session start. New helper `get_wifi_link_info(device_id)` parses `adb shell cmd wifi status` (falls back to `dumpsys wifi`); called once in `/api/session/start` right after the device is resolved, before the pidof-syncthing guard. Emits a single `[WIFI] ...` log line (e.g. `[WIFI] 5GHz freq=5765MHz rssi=-58dBm link=520Mbps ssid="Storm_Mesh"`). Best-effort: failure logs a warning and never aborts the session. Useful for correlating slow ADB-pulls / burst-stability issues with link quality.

### v5.17 (2026-05-14) — Photo transfer: Syncthing → direct ADB-pull
**Backend version: inline-2026-05-14c**

Photo transfer switched from Syncthing to the backend doing `adb pull` directly off the phone DCIM. Measured **~15 MB/s vs Syncthing's ~4.5 MB/s** (3.3× — same phone, same WiFi; Syncthing's per-file hashing/protocol overhead was the bottleneck, not the network). The transport is now **self-contained**: transfer happens only inside `_process_single_position`, i.e. only during an active session — no background daemon.

**New functions** (`photogrammetry.py`, near `poll_phone_dcim_stability`):
- `snapshot_phone_burst_prefixes(device_id)` — records burst prefixes already on the phone, pre-trigger ("the leftovers").
- `delete_stale_phone_bursts(device_id, keep_prefix)` — deletes every DCIM burst except the fresh one (phone is a dedicated rig). Non-fatal on error.
- `adb_pull_burst(device_id, burst_prefix, expected_count, expected_max_suffix, dest_folder, max_retries=2)` — multi-source `adb pull` into a staging dir, verifies (count / continuous suffixes / non-truncated), retries with device re-resolve. Returns `(paths, pull_duration)`.
- `delete_burst_from_phone(device_id, burst_prefix)` — deletes the pulled burst from the phone. Non-fatal.

**`_process_single_position` STEP 2** rewritten: resolve device once → snapshot leftovers → trigger → poll → **fresh-vs-stale guard** (selected prefix must not be a pre-trigger leftover, else fail+retry — catches dropped captures) → `delete_stale_phone_bursts` → `adb_pull_burst` to staging → archive to `posNNN/` → `delete_burst_from_phone` (only if the full burst archived) → remove staging. `device_id` is resolved once and threaded through `trigger_camera()` / `poll_phone_dcim_stability()` (both gained an optional `device_id` param). New `transfer_time` field in the per-position timing record.

**`start_session` guard:** runs `adb shell ps -A | grep -i syncthing` before spawning the thread; refuses to start if Syncthing is still running on the phone (it would race the pull).

**Retired:** `wait_for_server_sync()`, `wait_for_syncthing_completion()`, all `SYNCTHING_*` constants, the module-load `_processing/` mkdir, and the `_processing/` cleanup sweeps in `start_session` / `resume_session` / `reset_session` / the cleanup endpoint (response keys kept inert for API-shape stability). HA package files are unaffected (no sensor references any retired field — verified by grep).

**Operating rule (per run):** the phone's Syncthing app must be **stopped** before an automated session (the `start_session` guard enforces it). It does not need to be uninstalled — Syncthing is **retained for the user's manual testing**. Toggle it OFF for automated runs, ON for manual testing.

**Do NOT decommission or delete:** Syncthing on the phone, CT 103's folder `5grgy-q8shx`, or `/mnt/pictures/photogrammetry/_processing/` — that whole path is the user's manual-testing landing zone. The automated process simply ignores it. (This corrects an earlier draft of this entry that called `_processing/` "orphaned, safe to rm -rf" — it is not.)

### v5.16 (2026-05-14) — Unified crop disabled
**Backend version: inline-2026-05-14b**

Post-session unified crop is disabled. Added the `UNIFIED_CROP_ENABLED` master switch (default `False`) near the auto-crop config block, and gated the `unified_crop_session()` call in `_finalize_session_internal` behind it — finalize now logs `Unified crop skipped (UNIFIED_CROP_ENABLED=False)` and returns immediately. **All crop code is left fully intact** (`analyze_session_for_unified_crop`, `apply_unified_crop`, `unified_crop_session`); only the finalize-time call is bypassed. Flip the constant to `True` to re-enable.

Why: the restored inline base (`...024313`) predated this switch, so unified crop ran unconditionally on every session. On the first post-revert run (coin_005 session 1) it added a ~2.3-minute analysis tail after stacking — during which the session still showed `active` and the `_stacked_cropped_session_N/` folder didn't yet exist, which read as "stuck / didn't finish." Capture and stacking themselves were fine (60/60 each). Disabling the crop removes the confusing tail; cropping can be done separately when wanted.

Backup before this change: `photogrammetry.py.backup-20260514-pre-cropdisable`.

### v5.15 (2026-05-14) — REVERT to inline-synchronous capture
**Backend version: inline-restore-2026-05-14**

The entire async-capture line (v5.9 / v2.0 through v5.14 / v2.4) was reverted. The backend was restored from `photogrammetry.py.backup-20260514-024313` — the last snapshot before the async refactor began.

**Why.** The async model split capture into a fast capture thread + a background reconciler. It was faster on paper (~7 s/position) but that number was capture-phase only — downloads still had to drain afterward. More importantly, it was unreliable in practice. The session record is unambiguous:

| Session | Architecture | Result |
|---|---|---|
| coin_001 | inline | ✅ 60/60, 0 failed |
| coin_002 | inline | ✅ 30/30, 0 failed |
| coin_003 | async | ⚠️ came up 27/30 |
| coin_004 | async | ⚠️ 30/30 but needed manual recovery |
| coin_005 | async | ❌ blocked at 43/360, 11 bad bursts |

Inline: 2/2 clean. Async: 3/3 troubled. The async cadence (capture racing ahead while Syncthing transfers prior bursts) overloaded the phone — OpenCamera dropped frames (coin_005: 6 bursts missing frame 0, 4 bursts entirely missing; the phone's DCIM matched `_processing/` byte-for-byte, confirming the photos were never captured, not a transfer loss). Inline paces the phone: capture sits idle while each burst downloads.

**What changed.**
- Restored single processing thread per session: trigger → confirm burst on phone → `wait_for_server_sync` (blocking) → archive → launch focus-stack → rotate → next. No reconciler, no `pending_archives` state machine.
- `coin_005`'s `session.json` was retired to `session.json.scrapped-20260514` (photos disposable, to be re-shot).
- Previous live file backed up as `photogrammetry.py.backup-20260514-pre-revert`.

**What was lost in the revert** (all were async-era additions; can be re-grafted onto the stable inline base later as separate work):
- 3-part time breakdown (`compute_time_breakdown`) and pipeline completion rates (`compute_pipeline_progress`) — and their HA sensors.
- The `UNIFIED_CROP_ENABLED` gate — unified crop runs unconditionally again in the inline build.

**HA package note:** the 6 async-only template sensors in `sensors.yaml` v4.2.6 (3 time-breakdown + 3/4 completion-rate) and the `time_breakdown` / `pipeline_progress` `json_attributes` now read empty → they display flat `0`. They should be stripped from the package files in a follow-up. Core dashboard sensors are unaffected.

### v5.14 (2026-05-14) — Completion-driven reconciler (NO deadlines)
**Backend version: async-capture-2.4**
*(Superseded by v5.15 — the entire async line was reverted. Retained below for history.)*

The reconciler no longer fails positions on a timer. The old design carried a per-position sync deadline (`RECONCILER_POSITION_DEADLINE_S`, 600 s) plus an overall drain timeout (`RECONCILER_DRAIN_TIMEOUT_S`, 20 min) inherited from the synchronous era. On a slow or lossy Wi-Fi link those timers fired against bursts that were merely *slow*, not broken — producing contiguous blocks of false `sync_timeout_600s` "failures" (the coin_005 incident: 11 false-failed positions). v2.3.1's process-any-ready change fixed FIFO head-of-line blocking but still kept a stall-timeout that could fail a position.

v2.4 removes deadline-based failure entirely:

- **Sole readiness signal:** a position is archived only when its burst is *complete* — `count == expected_count` and all suffixes present (`validate_burst`). Nothing is processed early.
- **No failure-on-timer:** a slow or stalled burst stays `pending` and waits — for its files to arrive, or for the user to intervene. It is never moved to `failed`. `RECONCILER_POSITION_DEADLINE_S` and `RECONCILER_DRAIN_TIMEOUT_S` are gone.
- **Soft warning instead:** a position with zero new files in `_processing/` for `RECONCILER_STALL_WARNING_S` (15 min) gets `stall_warning: true` + `stall_detail` (e.g. `"6/10"`) on its `pending_archives` entry, and its number is added to session `stalled_positions`. The flag self-clears the instant a new file appears. It is a warning, not a failure.
- **Finalize only on clean finish:** the reconciler finalizes *only* when capture is complete AND every position is archived AND stacks are done. There is no timeout-driven finalize. If a position never completes, the session stays in progress with that position visibly waiting — honest, instead of a fabricated failure.
- **`complete_with_failures` narrowed:** now means only that ≥1 focus-stack subprocess failed (`failed_stacks`). A slow/incomplete download can no longer produce it. `_reconciler_finalize`'s `force_failures` parameter removed.

Rationale (user): "All that's happening is we are loading pictures in a folder… just let pictures build up until the whole position is done." Deadlines were the entire false-failure bug class; removing them is a net deletion of code.

### v5.13 (2026-05-14) — Pipeline completion rates
**Backend version: async-capture-2.3**

`progress_percent` only ever reflected **capture** — a position counts as "completed" the instant the capture thread enqueues it, before download or stacking. New `compute_pipeline_progress(session)` reports four honest rates:

- **`capture_pct`** — burst confirmed on phone + enqueued (= `len(completed_positions)/total`, same as `progress_percent`)
- **`download_pct`** — burst archived to `posNNN/` (pending_archives status `archived`/`stacking`/`done`)
- **`processing_pct`** — focus-stack finished (pending_archives status `done`)
- **`overall_pct`** — mean of the three = fraction of all pipeline steps completed

Plus a `counts` block (`captured`/`downloaded`/`processed`/`failed`/`total`). Failed positions count toward capture but not download/processing — they're genuinely unfinished.

Exposed as `pipeline_progress` on both `/api/session/current` and `/api/session/<id>/status`. HA: `pipeline_progress` added to `sensor.photogrammetry_session` attributes; 4 new template sensors (Capture/Download/Processing/Overall Completion %); a "Pipeline Completion" card on the Control Panel dashboard.

`progress_percent` is left unchanged (capture-only) for backward compatibility — `overall_pct` is the new honest end-to-end number.

### v5.12 (2026-05-14) — 3-part time breakdown
**Backend version: async-capture-2.2**

Each position's time is now tracked as three phases, exposed in the API, as HA sensors, and on the dashboard:

- **`capture_s`** — capture thread work (camera trigger + phone burst confirmation + turntable rotation). Source: `position_timings[].total_time`.
- **`download_s`** — server-side transfer window of the burst, measured as the **ctime spread** of the burst's files in `_processing/` (`max(ctime) − min(ctime)`). ctime is used because Syncthing preserves the source file's *mtime*, so mtime reflects when the photo was taken, not when it landed. Computed by the reconciler just before archiving; stored on the `pending_archives` entry (reconciler-owned → merge-safe).
- **`processing_s`** — focus-stack subprocess duration. Source: `position_timings[].stack_duration`.

`capture_s + download_s + processing_s` = the full per-position photo lifecycle (shutter → stacked image).

**New helper** `compute_time_breakdown(session)` produces per-position rows + per-phase aggregates (`sum`/`mean`/`median`, computed over non-None values only). Exposed as:
- `/api/session/<id>/status` → `time_breakdown` (full: positions + aggregates)
- `/api/session/current` → `time_breakdown` (aggregates only — keeps the 5 s-polled payload small)

**HA**: `time_breakdown` added to `sensor.photogrammetry_session` attributes; 3 new template sensors (`Photogrammetry Avg Capture/Download/Processing Time`); a "Time Breakdown" card on the Control Panel dashboard.

**Bugs fixed in the same change**:
- `wait_and_log_stack_process` gated `stack_duration` persistence on `stack_status == 'pending'`, but the async-capture refactor made the capture thread write `'pending_reconciler'` — so `stack_duration` was never persisted and `stack_status` never advanced. Now accepts both.
- `update_lifetime_stats` read `detect_sync_time` from `position_timings`, but the capture thread writes `detect_time` — so lifetime detect/sync stats were always 0. Fixed at all 3 read sites.
- **Concurrency hardening (data-loss fix)**: `wait_and_log_stack_process`, `check_and_crop_completed_stack`, and the reconciler-finalize path all saved a long-lived (stale) `session` dict *after* a blocking stack wait (up to 300 s). During that wait the capture thread writes new positions; the stale save reverted them — silently dropping `pending_archives` entries and `position_prefixes` (a likely contributor to the coin_004 positions-13/25/26 loss). All these sites now do a fresh `load_session` → merge → `save_session` under `session_lock`. Reconciler `failed_stacks` appends are now durably persisted instead of being lost with the stale dict.

**Caveat**: `download_s` measures the *transfer window* (first-to-last file finalized on the server), not wait-to-start. With `maxConcurrentWrites=8`, a burst whose files all finalize near-simultaneously can read `download_s ≈ 0` even if it waited in Syncthing's queue first. It answers "how fast did the burst transfer," not "how long was the lag."

### v5.11 (2026-05-14) — Unified crop disabled
**Backend version: async-capture-2.1**

- Added `UNIFIED_CROP_ENABLED` master switch in `photogrammetry.py` config block, default **False**.
- Post-session unified crop pass is now skipped in both finalize paths (`_reconciler_finalize` and `_finalize_session_internal`). Finalize logs `Unified crop skipped (UNIFIED_CROP_ENABLED=False)`.
- All crop code (`unified_crop_session`, `analyze_session_for_unified_crop`, `apply_unified_crop`, `auto_crop_stacked_image`) remains in place and fully callable — only the automatic trigger is gated.
- To re-enable: set `UNIFIED_CROP_ENABLED = True` and restart the service.
- Sessions now finish at `_stacked_session_N/` with no `_stacked_cropped_session_N/` output.

### v5.10 (2026-05-14) — ASYNC CAPTURE REFACTOR
**Backend version: async-capture-2.0**

Splits the per-session processing into two cooperating threads:

- **Capture thread**: triggers camera, confirms burst on phone, enqueues a `pending_archives` entry, rotates. Never waits for Syncthing.
- **Reconciler thread** (new): polls `/_processing/`, archives matched bursts to `posNNN/`, launches focus-stack subprocesses in dual odd/even slots, owns terminal session state.

**Why**: capture loop was blocked ~22s per position waiting for Syncthing to deliver files. With 360 positions that's ~2 hours of pure sync wait. Phone confirmation gives ground truth; sync can happen in the background.

**Performance**: per-position wall time drops from ~25s to ~7s. 360-position session: ~150min → ~42min (~3.5× speedup).

**New session.json fields (schema v2)**:
- `pending_archives`: list of capture entries with status (`pending`/`archiving`/`archived`/`stacking`/`done`/`failed`)
- `capture_complete`: bool, set when capture thread finishes all positions
- `reconciler_active`: bool, while reconciler is running
- `partial_failures`: count of positions in `failed_positions`
- `schema_version`: 2

**Per-position deadline**: 10 minutes (600s). If files don't arrive in `_processing/` within that window, position is marked failed; capture continues. Late arrivals still get routed to `posNNN/` via straggler logic for manual recovery.

**Pause behavior**: pause stops capture only; reconciler keeps draining to prevent `_processing/` fill.

**Restart safety**: `load_session` now applies schema-v2 defaults on every load. Transient `archiving`/`stacking` statuses get reset on load. Idempotent re-archive check: if `posNNN/` already has expected file count, entry is marked done.

**New status**: `complete_with_failures` (final state if any position timed out).

**Backward compat**: old session.json files load with defaults applied; existing flow paths preserved. The legacy `wait_for_server_sync` function is kept available but no longer called by the capture loop.

**Files updated**:
- `photogrammetry.py` → async-capture-2.0
- `photogrammetry.md` → v5.10
- `inputs.yaml`, `rest_commands.yaml`, `scripts.yaml`, `automations.yaml`, `sensors.yaml` → v4.2.4 lockstep

### v5.8e (2025-12-15)- Fixed HA "Can Resume" sensor to recognize blocked/interrupted/stopped statuses- Dashboard now correctly shows Resume button for blocked sessions
### v5.8d (2025-12-14)
- Fixed session state visibility after ADB disconnection
- get_active_session() now recognizes blocked/paused/interrupted/stopped statuses
- HA dashboard correctly shows Resume button for interrupted sessions

### v5.8c (2025-12-14)
- Fixed unified crop centering using midpoint of centroid range
- Face-on and edge-on positions now balanced (neither cut off)
- X center = midpoint between min and max detected centroids
- Addresses holder offset causing different centroids at different rotation angles
### v5.9 (2025-12-14)- Fixed critical bug in unified crop centering- Bug: Morphological cleanup eroded more from face-on coins (large perimeter) than edge-on (compact)- This reversed "widest position" ranking, selecting wrong positions for center- Fix: Added get_raw_object_width() to get pre-morphology width for sorting- Result: X center accuracy improved from ~2315 to ~1944 (correct)- center_std_x improved from 190.1 to 46.0 (4x more stable)

### v5.8 (2025-12-13)
- Improved cropping accuracy using weighted centroid from face-on positions only
- Uses top 30% widest positions for center (excludes edge-on where holder shifts centroid)
- Reduced center position standard deviation from ~185px to ~50px
- Added morphological cleanup to remove noise before object detection
- Implemented adaptive thresholding (70 for uniform backgrounds, 100 for variable)
- Changed size calculation from max to 90th percentile (better outlier handling)
- New config parameters: AUTO_CROP_CORNER_SIZE, AUTO_CROP_THRESHOLD_UNIFORM/VARIABLE
- AUTO_CROP_PADDING_PERCENT, AUTO_CROP_MORPH_ITERATIONS, AUTO_CROP_USE_CENTROID
- Enhanced logging with center_std metrics and detection method info

### v5.7 (2025-12-14)
- Improved ETA calculation using rolling median of last 5 positions
- Better outlier resistance - one slow position no longer skews estimates
- Simpler code: 50 lines of complex logic replaced with 15 lines
- Still skips position 1 (startup overhead)
### v5.6 (2025-12-13)- Fixed retry logic to BLOCK instead of skip on failure- When a position fails after 2 retries, system now blocks and waits- Turntable stays in place - position angle is recoverable- User gets notification to fix issue and click Resume- New "blocked" status visible in dashboard- Prevents data loss from USB disconnects, phone going offline, etc.

### v5.5 (2025-12-12)
- Added notification system via Home Assistant
- Browser notifications (persistent_notification in HA sidebar)
- Mobile push notifications (notify.mobile_app for Companion app)
- Triggers: Session complete, errors/failures, manual intervention needed
- Automatic notification clearing on new session start
- Python notification code removed - HA automations preferred for flexibility

### v5.1 (2025-12-03)
- Moved stacked folder from `_session_N/stacked/` to root level as `_stacked_session_N/`
- Matches naming pattern of `_stacked_cropped_session_N/`
- Cleaner folder organization at object root level

### v5.0 (2025-12-03)
- Consolidated all documentation into single reference
- Identified all component locations
- Current working version

### v4.2.4 (2025-11-28)
- Crop consistency: All cropped images use identical dimensions from position 1
- Reference stored in session: `crop_reference.crop_size`, `crop_reference.source_position`

### v4.2.3 (2025-11-27)
- Fixed: Removed `json_attributes_path: "$"` causing REST errors
- Fixed: All sensor parsing errors (250+ occurrences eliminated)
- Added: `sensor.photogrammetry_completed_stacks`
- Split HA config into 5 package files

### v4.2 (2025-11-27)
- Multi-session support: `_session_N` subfolders
- Automatic session number detection and increment
- Backward compatible with single-session folders

### v4.1 (2025-11-26)
- File permissions fix: All folders as `sambauser:sambauser`
- mDNS resolution improvements
- Dashboard button fixes

### v4.0 (2025-11-24)
- Threading system: Background thread auto-processes all positions
- Dual stacking pipeline: Odd/even positions process in parallel
- Removed manual process_position endpoint
- Added pause/resume/stop thread control

### v3.0 (2025-11-22)
- Auto-crop feature: PIL-based edge detection
- Crop status dashboard card
- Crop statistics tracking

### v2.0 (2025-10-31)
- REST sensor architecture: 3 REST sensors + 30+ template sensors
- Focus stacking with OpenCV
- Session persistence via JSON

### v1.0 (2025-09-27)
- Initial implementation
- Basic ADB control and photo capture
- Syncthing integration

---

## Quick Reference

### Start a Session
1. Open Home Assistant dashboard
2. Set Object Name (e.g., "coin_10")
3. Set Angular Distance (e.g., 10.0 for 36 positions)
4. Enable/disable Auto-Crop
5. Click START button

### Monitor Progress
- Progress bar shows completion percentage
- Current position / Total positions
- Estimated completion time
- Dual stacking status (odd/even slots)

### Common Operations
```bash
# Check service
sudo pct exec 104 -- systemctl status photogrammetry.service

# View live logs
sudo pct exec 104 -- journalctl -u photogrammetry.service -f

# API health check
curl http://192.168.0.176:5000/api/session/current

# ADB status
curl http://192.168.0.176:5000/api/devices/status
```

---

*This document consolidates all photogrammetry system documentation. Keep this file updated when making changes to any component.*
