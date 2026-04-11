# Time Team Complete Download System

**Last Updated**: 2026-04-10
**Related Systems**: Emby (Container 102), Samba (Container 104), Claude AI (Container 124)

## Summary

Automated download and organization of ALL Time Team content from YouTube (756 videos) and Patreon (patron-exclusive posts) into an Emby-friendly library at `/mnt/hometheater/Time Team YouTube/`.

## Architecture

```
Sources                    Processing                  Destination
─────────                  ──────────                  ───────────
YouTube Channel ──→  timeteam-download.sh  ──→  /mnt/hometheater/Time Team YouTube/
  (@TimeTeamOfficial)    (sorts by title)           ├── S21-S24 dig folders
  756 videos, ~153GB                                ├── Specials, Classics
                                                    ├── Teatime, Interviews
Patreon Posts ────→  timeteam-patreon.sh   ──→      ├── Dig Watch Clips
  (via Gmail MCP)       (cookies auth)              ├── Podcasts, News
  ~201 patron posts                                 └── Patreon Exclusive
```

## Emby Library Structure

Each folder appears as a browsable group in Emby (like seasons in a TV show):

| Folder | Content | ~Count |
|--------|---------|--------|
| **S21 - Boden Fogou (Cornwall)** | New era Season 21 dig episodes | 5 |
| **S21 - Broughton Roman Villa (Oxfordshire)** | Season 21 second dig | 7 |
| **S21 - Feature Length** | Season 21 full-length compilations | 2 |
| **S22 - Knights Hospitaller** | Season 22 dig episodes | 6 |
| **S22 - Anglo-Saxon Cemetery (Norfolk)** | Season 22 second dig | 6 |
| **S22 - Feature Length** | Season 22 full-length compilations | 2 |
| **S23 - Band of Brothers** | Op Nightingale / Aldbourne dig | 9 |
| **S23 - Wytch Farm (Dorset)** | Season 23 dig | 5 |
| **S23 - Modbury (Devon)** | Season 23 community dig | 4 |
| **S23 - Feature Length** | Season 23 full-length compilations | 2 |
| **S24 - Norton Disney** | Season 24 dig | 6 |
| **S24 - Cerne Abbas (Dorset)** | Secrets Beneath The Giant | 4 |
| **S24 - Brancaster (Norfolk)** | Brancaster/Branodunum/Mapperton/Geofizz | 4 |
| **Classic Specials** | Rereleased full classic episodes from Channel 4 era | 21 |
| **Specials** | New era standalone specials (Princely Burial, Mortar Wreck, Cottage Core, etc.) | 20 |
| **Sutton Hoo** | All Sutton Hoo content | 26 |
| **X Crew** | X Crew digs (Vlochos/Greece) | 7 |
| **Expedition Crew** | Expedition Crew content (Sherwood, Hidden City, Sarcophagus) | 9 |
| **Time Team Plus** | Swandro, Waterloo Uncovered, Op Cobra, Student Dig | 9 |
| **Teatime** | Q&A / chat sessions with the team | 62 |
| **Interviews** | Author and expert interviews | 39 |
| **Time Team News** | Monthly archaeology news show | 20 |
| **Commentary** | Episode commentaries and Q&As | 51 |
| **Behind the Scenes** | Previews, aftershows, compilations, best-of recaps | 20 |
| **Dig Watch Clips** | Short on-site update clips (TT-## format) | 318 |
| **Dig Village Masterclass** | Educational masterclass series | 16 |
| **Podcasts** | Video podcast episodes | 23 |
| **Promos** | Trailers, merch, membership, announcements | 53 |
| **Patreon Exclusive** | Patron-only content from Patreon | TBD |

## Files & Locations

| File | Path | Purpose |
|------|------|---------|
| YouTube download script | `/home/claudeai/timeteam-download.sh` | Main download + sorting logic |
| Video list (YouTube) | `/mnt/hometheater/Time Team YouTube/video-list.txt` | All 756 YouTube video IDs with titles |
| Download archive | `/mnt/hometheater/Time Team YouTube/.downloaded_ids` | Tracks completed downloads (skip on re-run) |
| Download log | `/mnt/hometheater/Time Team YouTube/download-log.txt` | SUCCESS/FAILED/SKIPPED per video |
| Patreon cookies | `/mnt/documents/personal/alec/claudeai/patreon-cookies.txt` | Auth for patron-only downloads |
| Downloaded content | `/mnt/hometheater/Time Team YouTube/` | Emby library root |

## How It Works

### YouTube Download Script (`timeteam-download.sh`)

The script reads `video-list.txt` (format: `videoID;;;title;;;duration`) and for each video:

1. Checks `.downloaded_ids` to skip already-downloaded videos
2. Runs the title through `get_folder()` which pattern-matches against ~30 rules to pick the right folder
3. Downloads with `yt-dlp` at best quality (mp4, embedded metadata, English subtitles)
4. Logs result to `download-log.txt`

**Sorting logic priority** (first match wins):
1. Classic Specials (title contains "classic special")
2. Dig site-specific (Boden Fogou, Broughton, Knights Hospitaller, etc.)
3. Sutton Hoo, X Crew, Expedition Crew, Time Team Plus
4. Dig Watch Clips (TT-## codes, on-site update patterns)
5. Dig Village Masterclass
6. Classic full episodes (S##E## format)
7. Podcasts, Teatime, Time Team News
8. Commentary, Interviews, Behind the Scenes
9. Named specials (Princely Burial, Mortar Wreck, etc.)
10. Promos (trailers, merch, announcements)
11. Fallback: Specials

### Patreon Downloads

Uses `yt-dlp` with Patreon session cookies to download patron-exclusive video content from post URLs extracted from Gmail notifications.

## Running the Downloads

### First-time setup
```bash
# Install dependencies
pip install --user yt-dlp
sudo apt-get install -y screen

# Pull video list from YouTube channel
yt-dlp --flat-playlist --print "%(id)s;;;%(title)s;;;%(duration)s" \
    "https://www.youtube.com/@TimeTeamOfficial/videos" \
    > "/mnt/hometheater/Time Team YouTube/video-list.txt"
```

### Start YouTube downloads
```bash
# Run in persistent screen session (survives disconnects)
screen -dmS timeteam bash ~/timeteam-download.sh

# Attach to watch progress
screen -r timeteam

# Detach: Ctrl+A, then D
```

### Monitor progress
```bash
# Check how many downloaded
wc -l "/mnt/hometheater/Time Team YouTube/.downloaded_ids"

# View recent log entries
tail -20 "/mnt/hometheater/Time Team YouTube/download-log.txt"

# Check if still running
screen -ls
ps aux | grep yt-dlp | grep -v grep
```

### Re-run after interruption
Just run the script again - it automatically skips everything in `.downloaded_ids`:
```bash
screen -dmS timeteam bash ~/timeteam-download.sh
```

### Refresh video list (new uploads)
```bash
# Re-pull from YouTube (gets any new uploads since last pull)
yt-dlp --flat-playlist --print "%(id)s;;;%(title)s;;;%(duration)s" \
    "https://www.youtube.com/@TimeTeamOfficial/videos" \
    > "/mnt/hometheater/Time Team YouTube/video-list.txt"

# Re-run - existing downloads auto-skip
screen -dmS timeteam bash ~/timeteam-download.sh
```

### Patreon downloads
```bash
# Requires valid session cookie in patreon-cookies.txt
# Cookie expires - re-export from browser if downloads fail with 401

yt-dlp --cookies /mnt/documents/personal/alec/claudeai/patreon-cookies.txt \
    -o "/mnt/hometheater/Time Team YouTube/Patreon Exclusive/%(title)s [%(id)s].%(ext)s" \
    "https://www.patreon.com/posts/SLUG-POSTID"
```

## Patreon Cookie Renewal

The Patreon session cookie expires periodically. To renew:

1. Open Chrome, go to patreon.com (logged in via Google auth)
2. F12 -> Console -> type `document.cookie` -> Enter
3. Find the `session_id` value
4. Update `/mnt/documents/personal/alec/claudeai/patreon-cookies.txt`:
   ```
   # Netscape HTTP Cookie File
   .patreon.com	TRUE	/	TRUE	0	session_id	YOUR_NEW_SESSION_ID_HERE
   ```

## Troubleshooting

### Downloads stuck or failing
```bash
# Check if yt-dlp needs updating
yt-dlp --update

# Check for rate limiting (YouTube throttles heavy downloads)
# The script has a 2-second delay between videos
# If persistent failures, increase sleep in the script

# Check disk space
df -h /mnt/hometheater/
```

### Video sorted into wrong folder
The `get_folder()` function in `timeteam-download.sh` uses title pattern matching. If a video lands in the wrong folder:
1. Move the .mp4 and .srt files manually
2. Optionally update `get_folder()` with a new pattern for future runs

### Re-download a specific video
```bash
# Remove its ID from the archive
sed -i '/VIDEO_ID_HERE/d' "/mnt/hometheater/Time Team YouTube/.downloaded_ids"
# Re-run the script - it will download that video again
```

### Emby not showing new content
1. Go to Emby dashboard -> Libraries
2. Click the Time Team YouTube library -> Refresh
3. Or wait for the scheduled scan

## Estimated Storage

| Content | Size |
|---------|------|
| YouTube (756 videos, 167 hours) | ~153 GB |
| Patreon exclusive | ~10-30 GB |
| **Total** | **~170-185 GB** |

## Library Reorganization (Completed 2026-04-11)

The library was reorganized from category-based folders into dig-based folders with E/X naming.

### New Folder Structure
- **48 folders**: 39 dig folders + 9 category folders
- **1,175 active files** (41 duplicates removed)
- **E## = Episodes** (main dig content), **X## = Extras** (clips, trailers, BTS)
- Category folders use straight E## numbering

### Workflow for New Downloads
1. Run `timeteam-download.sh` (downloads to temporary sorting folders)
2. Run `timeteam-reorganize.py` (generates rename-mapping.csv)
3. Review the mapping
4. Run `timeteam-execute.py` (moves and renames files)

### Key Files
| File | Location | Purpose |
|------|----------|---------|
| `timeteam-master.csv` | Samba timeteam/ | Master manifest of all files with metadata |
| `timeteam-reorganize.py` | Samba timeteam/ | Classification + naming script |
| `timeteam-execute.py` | Samba timeteam/ | Executes the moves/renames |
| `rename-mapping.csv` | Samba timeteam/ | Current mapping (old -> new) |
| `rename-review.txt` | Samba timeteam/ | Human-readable review |
| `reorganization-plan.md` | Samba timeteam/ | Full reorganization plan |
