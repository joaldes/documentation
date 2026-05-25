# Standardize Photogrammetry Logging Categories

## Goal
Standardize 333 log calls to use consistent `[CATEGORY]` prefixes.

## Standard Categories

| Category | Use For |
|----------|---------|
| `[SESSION]` | Session lifecycle (start, stop, resume, pause) |
| `[THREAD]` | Background thread operations |
| `[CAPTURE]` | Camera trigger, photo capture |
| `[PHONE]` | ADB/phone communication |
| `[SYNC]` | File sync, Syncthing, waiting for files |
| `[STACK]` | Focus stacking operations |
| `[CROP]` | Auto-crop and unified crop |
| `[ORGANIZE]` | File/folder organization |
| `[CLEANUP]` | Cleanup operations |
| `[API]` | HTTP request logging |
| `[ERROR]` | Error conditions |
| `[WARN]` | Warnings |

## Changes Needed

### 1. Fix number-based categories
- `[0]`, `[-1]`, `[1]`, `[7]`, `[8]` → Identify context and rename

### 2. Consolidate STACK variants
- `[STACK-ERROR]` → `[STACK] ERROR:`
- `[STACK-WARN]` → `[STACK] WARN:`
- `[STACK-COMPLETE]` → `[STACK]`
- `[STACK-TIMEOUT]` → `[STACK] TIMEOUT:`
- `[STACK-WAIT]` → `[STACK]`

### 3. Consolidate CROP variants
- `[AUTO-CROP]` → `[CROP]`
- `[UNIFIED-CROP]` → `[CROP]`
- `[CROP-REF]` → `[CROP]`

### 4. Other consolidations
- `[TRIGGER-xxx]` → `[CAPTURE]`
- `[FINALIZE]` → `[SESSION]`
- `[RESET]` → `[SESSION]`
- `[STARTUP]` → `[SESSION]`
- `[STRAGGLER]` → `[SYNC]`
- `[SYNCTHING]` → `[SYNC]`
- `[REQUEST]` → `[API]`
- `[TIMING]` → `[SESSION]` or remove
- `[ARCHIVE]` → `[ORGANIZE]`
- `[STEP 1]`, `[STEP 3]`, `[STEP 4]` → relevant category
- `[POSITION xxx]` → `[CAPTURE]`

### 5. Add prefix to unprefixed logs
Find logs without `[CATEGORY]` and add appropriate prefix.

### 6. Remove emojis
- ✅ ✓ 📸 → remove
- ⚠️ → `WARN:`

## File to Modify
- `/opt/photogrammetry/photogrammetry.py` (on 192.168.0.176)

## Format Standard
```
[CATEGORY] Message here
[CATEGORY] WARN: Warning message
[CATEGORY] ERROR: Error message
```

## Real-World Before/After (from Dec 16 02:51 logs)

### BEFORE:
```
[SYNC] ✅ VALIDATION PASSED
[SYNC] ✓ Count: 10/10
[ARCHIVE] ✓ 10 photos archived to pos112/
[TIMING] Photo detection + archive took 50.7s
[STEP 3] Starting stack for position 112 (10 photos)...
[STACK-COMPLETE] Position 111 (ODD slot) finished in 52.4s
[STEP 4] Rotating turntable...
[TIMING] Position 112 TOTAL: 52.4s
[TRIGGER-95d1f3e6] ========== BEFORE SUBPROCESS ==========
[TRIGGER-95d1f3e6] Camera triggered successfully
[PHONE] 📸 SNAPSHOT CAPTURED - This count is ground truth
[REQUEST] GET /api/devices/status 200
```

### AFTER:
```
[SYNC] VALIDATION PASSED
[SYNC]   Count: 10/10
[ORGANIZE] 10 photos archived to pos112/
[SESSION] Photo detection + archive took 50.7s
[STACK] Starting stack for position 112 (10 photos)...
[STACK] Position 111 (ODD slot) finished in 52.4s
[SESSION] Rotating turntable...
[SESSION] Position 112 TOTAL: 52.4s
[CAPTURE] ========== BEFORE SUBPROCESS ==========
[CAPTURE] Camera triggered successfully
[PHONE] SNAPSHOT CAPTURED - This count is ground truth
[API] GET /api/devices/status 200
```

## Key Changes
- `[AUTO-CROP]`, `[UNIFIED-CROP]`, `[CROP-REF]` → `[CROP]`
- `[TRIGGER-xxx]` → `[CAPTURE]` (removed dynamic ID)
- `[REQUEST]` → `[API]`
- `WARNING -` → `WARN:`
- `ERROR` in message → `ERROR:` after category
- Remove emojis (✓ ✅ 📸)
- Continuation lines use `[CATEGORY]   ` (category + indent)
- `×` → `x` (ASCII only)

## Note
~333 log calls to update. Do in batches to verify correctness.
