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

**Important**: inotify file monitoring may miss files due to network filesystem delays, atomic moves, or other edge cases.

**Recommended settings** (in Settings > Library):
- **Enable inotify**: Yes (catches most file changes)
- **Enable Library Scanner**: Yes (periodic full scan as backup)
- **Schedule full scan**: 30 minutes (catches files inotify missed)

Without periodic scans, files can be missed and processing stops silently.

## Worker Configuration
- **Worker Group**: Zoljin
- **Number of Workers**: 1 (increase for faster processing if CPU allows)

## Troubleshooting

### Processing stopped / No new tasks
1. Check pending queue in web UI
2. Verify worker count > 0 in Settings > Workers
3. Trigger manual library scan in Settings > Library
4. Check logs: `/root/.unmanic/logs/unmanic.log`

### Files not being detected
- Enable periodic library scans (inotify can miss files)
- Check library path is correct and accessible
- Verify mounts are working inside container

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

Updated: 2026-02-10
