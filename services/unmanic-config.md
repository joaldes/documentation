# Unmanic Configuration

## Container Info
- **Container**: LXC 105 (unmanic)
- **IP**: 192.168.0.207
- **Web UI**: http://192.168.0.207:8888
- **Version**: 0.3.0
- **Library Path**: /library (mergerfs mount from host, 29TB total)
- **Cache Path**: /cache (28GB tmpfs for processing temp files)
- **Plugins Path**: /root/.unmanic/plugins/
- **Service**: unmanic.service (Restart=always, 30s delay)

## Goal
Process media files for audio/subtitle standardization:
- Keep English audio tracks only
- Add AAC stereo track for compatibility/mobile
- Extract English subtitles to external .srt files
- Remove all embedded subtitles
- Strip attachment streams (fonts, text files) to prevent muxer errors

**Note**: Video codec is NOT changed (no HEVC transcoding)

## Hardware
- **CPU**: 5 cores allocated
- **RAM**: 32GB allocated
- **GPU**: Intel Iris Xe passthrough (available for future use)
  - /dev/dri/card0, /dev/dri/renderD128

## Storage
- **Root**: 3.9GB (ext4)
- **Library**: 29TB mergerfs union mount (16TB used, 14TB free) — Movies + TV Shows
- **Cache**: 28GB tmpfs (`/etc/fstab`: `tmpfs /cache tmpfs size=28G,mode=1777 0 0`)

## Worker - Processing File Flow (in order)
1. **remove_stream_by_language** - Remove non-English audio/subtitle streams
2. **remove_all_subtitles** - Strip all embedded subtitles
3. **remove_all_attachments** - Strip attachment streams (custom plugin, see below)
4. **add_extra_stereo_audio** - Create AAC stereo from best English audio
5. **encoder_audio_aac** - Re-encode audio to AAC
6. **extract_srt_subtitles_to_files** - Extract English SRT subs to external files
7. **convert_subtitle_streams_ass_to_srt** - Convert ASS/SSA subs to SRT
8. **postprocessor_script** - Runs `check_no_audio.sh` on successful completion
9. **notify_sonarr** - Notify Sonarr of processed TV files
10. **notify_radarr** - Notify Radarr of processed movie files

## Plugin Configuration

### remove_stream_by_language
- Remove audio languages: spa,fra,deu,ita,por,jpn,kor,zho,chi,rus,ara,hin,tha,vie,pol,nld,swe,nor,dan,fin,tur,ces,hun,ron,ukr,heb,ind,msa,fil,ben,tam,tel,mar,guj,kan,mal,pan,per,urd,fas
- Keep: English (eng, en)

### remove_all_attachments (Custom Plugin)
- **Why**: The `add_extra_stereo_audio` plugin uses `-map 0` which maps all streams including attachments. MKV files with attachment streams (fonts, .txt chapter files) cause the matroska muxer to fail with "Invalid argument". This is a [known upstream issue](https://github.com/Unmanic/unmanic/issues/249).
- **How**: Custom plugin using StreamMapper with `['attachment']` stream type. Returns empty mapping for all attachment streams, stripping them before the stereo audio step runs.
- **Location**: `/root/.unmanic/plugins/remove_all_attachments/` (plugin.py, info.json, lib/)
- **Based on**: `remove_all_subtitles` plugin pattern
- **Safe because**: All subtitles are already stripped (font attachments useless), real MKV chapters are container metadata (not attachments), cover art comes from Emby metadata providers

### add_extra_stereo_audio
- Source language: eng
- Use libfdk_aac: false (uses native aac)
- Keep original audio: yes
- Make stereo default: no

### extract_srt_subtitles_to_files
- Languages: eng,en
- Include title in filename: no

### postprocessor_script
- Script: `/usr/local/bin/check_no_audio.sh`
- Run on success: yes
- Run on failure: no

## Custom Scripts

### /usr/local/bin/check_no_audio.sh
Detects and logs media files that end up with no audio tracks after processing (e.g., a file had only a non-English audio track that was stripped). Logs to `/library/.unmanic_logs/no_audio.log`.

### /usr/local/bin/verify_media.sh
Comprehensive library-wide media validation. Scans all files in `/library/Movies` and `/library/TV Shows` and checks:
- Has video track
- Has audio track
- Audio language is eng/en/und/empty
- No embedded subtitles

Reports:
- `/library/.unmanic_logs/verification_report.txt` — summary stats
- `/library/.unmanic_logs/non_conforming_files.txt` — list of files that failed checks

### /usr/local/bin/fix_eng_tags.sh
Remuxes a hardcoded list of movie files that had malformed "eng," language tags. Uses ffmpeg to fix metadata. One-time use script.

### /usr/local/bin/subtitle_standardizer.py (not currently in plugin flow)
Post-processor for subtitle filename standardization. Converts extracted subtitle files to Emby-compliant naming (`{videoname}.{lang}.srt`). Detects and appends `.sdh`, `.forced` suffixes. Supports 20+ languages. Logs to `/var/log/unmanic/subtitle_standardizer.log`.

## Logs
- **Application**: `/root/.unmanic/logs/unmanic.log`
- **No-audio files**: `/library/.unmanic_logs/no_audio.log`
- **Verification report**: `/library/.unmanic_logs/verification_report.txt`
- **Non-conforming files**: `/library/.unmanic_logs/non_conforming_files.txt`
- **Subtitle standardizer**: `/var/log/unmanic/subtitle_standardizer.log`

## Library Monitoring

### inotify Limitations on mergerfs
The library path `/library` is a mergerfs FUSE mount (host: `/mnt/hometheater`, two ext4 disks merged). inotify has a **known limitation**: FUSE does not propagate `IN_CREATE` events for `link()` (hardlink) operations. Since Sonarr/Radarr hardlink `.mkv` files during import, Unmanic's watchdog never sees them. Small files like `.nfo` and `.jpg` are written fresh and trigger events normally.

### Sonarr/Radarr API Notify (Fix for Hardlink Issue)
Post-import scripts on Sonarr (CT 110) and Radarr (CT 107) call Unmanic's REST API to add files directly to the pending queue, bypassing inotify.

**Flow:**
```
Sonarr/Radarr imports file (hardlink on mergerfs)
  → Custom Script Connect fires /scripts/fix-ownership.sh
  → Script translates path: /mnt/hometheater → /library
  → POST to Unmanic API: /unmanic/api/v2/pending/create
  → File appears in Unmanic pending queue
```

**Path translation** (containers mount the same host path differently):

| Container | Mount Path |
|-----------|-----------|
| Sonarr (CT 110, 192.168.0.24) | `/mnt/hometheater` |
| Radarr (CT 107, 192.168.0.42) | `/mnt/hometheater` |
| Unmanic (CT 105, 192.168.0.207) | `/library` |

**Sonarr script** — `/scripts/fix-ownership.sh` on CT 110:
```bash
#!/bin/bash
[ "$sonarr_eventtype" != "Download" ] && exit 0
UNMANIC_API="http://192.168.0.207:8888/unmanic/api/v2/pending/create"
notify_unmanic() {
    local UNMANIC_PATH="${1/\/mnt\/hometheater/\/library}"
    curl -s -X POST "$UNMANIC_API" \
      -H "Content-Type: application/json" \
      -d "{\"path\": \"$UNMANIC_PATH\"}" \
      --max-time 10 >/dev/null 2>&1 &
}
if [ -n "$sonarr_episodefile_path" ]; then
    chown 1000:1000 "$sonarr_episodefile_path"
    chown 1000:1000 "$(dirname "$sonarr_episodefile_path")"
    notify_unmanic "$sonarr_episodefile_path"
elif [ -n "$sonarr_episodefile_paths" ]; then
    IFS='|' read -ra FILES <<< "$sonarr_episodefile_paths"
    for f in "${FILES[@]}"; do
        chown 1000:1000 "$f"
        chown 1000:1000 "$(dirname "$f")"
        notify_unmanic "$f"
    done
fi
```

**Radarr script** — `/scripts/fix-ownership.sh` on CT 107:
```bash
#!/bin/bash
UNMANIC_API="http://192.168.0.207:8888/unmanic/api/v2/pending/create"
if [ -n "$radarr_moviefile_path" ]; then
    chown 1000:1000 "$radarr_moviefile_path"
    chown 1000:1000 "$(dirname "$radarr_moviefile_path")"
    UNMANIC_PATH="${radarr_moviefile_path/\/mnt\/hometheater/\/library}"
    curl -s -X POST "$UNMANIC_API" \
      -H "Content-Type: application/json" \
      -d "{\"path\": \"$UNMANIC_PATH\"}" \
      --max-time 10 >/dev/null 2>&1 &
fi
```

**Connect entries** (pre-existing, no config changes needed):
- Sonarr: Notification ID 4 → `/scripts/fix-ownership.sh` (onDownload, onUpgrade)
- Radarr: Notification ID 3 → `/scripts/fix-ownership.sh` (onDownload, onUpgrade)

### inotify Settings
- **Enable inotify**: Yes (catches direct writes and Samba copies)
- **Library Scanner**: Available but scans the entire library — use only as a last resort

## Worker Configuration
- **Worker Group**: Zoljin
- **Number of Workers**: 1 (increase for faster processing if CPU allows)

## Troubleshooting

### Processing stopped / No new tasks
1. Check pending queue in web UI
2. Verify worker count > 0 in Settings > Workers
3. Trigger manual library scan in Settings > Library
4. Check logs: `/root/.unmanic/logs/unmanic.log`

### Files not being detected after Sonarr/Radarr import
- Verify `/scripts/fix-ownership.sh` exists and is executable on CT 110 (Sonarr) and CT 107 (Radarr)
- Test API connectivity: `curl -s -o /dev/null -w '%{http_code}' http://192.168.0.207:8888/unmanic/api/v2/pending/create -X POST -H 'Content-Type: application/json' -d '{"path":"/tmp/test"}'` — expect 400
- Check path translation: the script replaces `/mnt/hometheater` with `/library`
- Add a file manually via API to verify Unmanic processes it
- Root cause is likely mergerfs + hardlinks — see Library Monitoring section above

### Files not being detected (general)
- Check library path is correct and accessible
- Verify mounts are working inside container
- For non-Sonarr/Radarr sources (Samba copies), inotify should work — check watchdog is running in logs

### Muxer errors on files with attachments
- Symptom: `[matroska] Received a packet for an attachment stream` / `Error submitting a packet to the muxer: Invalid argument`
- Cause: `add_extra_stereo_audio` plugin uses `-map 0` which includes attachment streams
- Fix: `remove_all_attachments` plugin must be in the flow BEFORE `add_extra_stereo_audio`

### Queue a single file for reprocessing (API)
```bash
curl -s -X POST http://192.168.0.207:8888/unmanic/api/v2/pending/create \
  -H "Content-Type: application/json" \
  -d '{"path": "/library/TV Shows/Show Name/Season 1/file.mkv"}'
```

### Check worker status (API)
```bash
curl -s http://192.168.0.207:8888/unmanic/api/v2/workers/status | python3 -m json.tool
```

### Pause/resume workers (API)
```bash
# Pause all
curl -s -X POST http://192.168.0.207:8888/unmanic/api/v2/workers/worker/pause/all

# Resume all
curl -s -X POST http://192.168.0.207:8888/unmanic/api/v2/workers/worker/resume/all

# Terminate worker (kills current task)
curl -s -X DELETE http://192.168.0.207:8888/unmanic/api/v2/workers/worker/terminate \
  -H "Content-Type: application/json" -d '{"worker_id": "Zoljin-0"}'
```

Updated: 2026-02-16
