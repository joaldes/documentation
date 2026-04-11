# Time Team Library - Processing Runbook

**Last Updated**: 2026-04-11
**Library**: `/mnt/hometheater/Time Team YouTube/`
**Project Files**: `/mnt/documents/personal/alec/claudeai/timeteam/`

## Overview

This library contains all Time Team content from YouTube (756 videos) and Patreon (465 videos). Files are organized by dig/project with E## (episodes) and X## (extras) naming. This runbook covers downloading new content and integrating it into the library.

---

## Step 1 - Download New Content

### YouTube

```bash
# 1. Refresh the video list from the channel
yt-dlp --flat-playlist --print "%(id)s;;;%(title)s;;;%(duration)s" \
    "https://www.youtube.com/@TimeTeamOfficial/videos" \
    > "/mnt/hometheater/Time Team YouTube/video-list.txt"

# 2. Run the download script (skips already-downloaded via .downloaded_ids)
screen -dmS timeteam bash ~/timeteam-download.sh

# 3. Monitor
tail -f "/mnt/hometheater/Time Team YouTube/download-log.txt"
```

### Patreon

Requires valid session cookie. If downloads fail with 401, re-export cookie:
1. Open Chrome, go to patreon.com (logged in via Google)
2. F12 → Console → `document.cookie` → find `session_id` value
3. Update `/mnt/documents/personal/alec/claudeai/timeteam/patreon-cookies.txt`

```bash
screen -dmS patreon bash ~/timeteam-patreon.sh
```

**Note**: The download scripts sort files into temporary category folders (the old structure). New files need to be processed through Steps 2-5 below.

---

## Step 2 - Update Master CSV

After downloading, extract metadata from new files and add them to the master CSV.

```bash
python3 -c "
import csv, subprocess, json, re, os
from pathlib import Path

BASE = Path('/mnt/hometheater/Time Team YouTube')
MASTER = Path('/mnt/documents/personal/alec/claudeai/timeteam/timeteam-master.csv')

# Load existing entries
existing = set()
rows = []
with open(MASTER) as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)
    existing = {r['original_filename'] for r in rows}

# Find new mp4 files not in master
new_count = 0
for mp4 in BASE.rglob('*.mp4'):
    if mp4.name in existing:
        continue
    
    rel = mp4.relative_to(BASE)
    folder = str(rel.parent)
    
    m = re.search(r'\[(patreon-)?([^\]]+)\]', mp4.name)
    vid_id = m.group(2) if m else ''
    source = 'patreon' if m and m.group(1) else 'youtube'
    
    srt = mp4.with_suffix('.en.srt')
    has_subs = 'yes' if srt.exists() else 'no'
    size_mb = mp4.stat().st_size / (1024 * 1024)
    
    # Extract metadata via ffprobe
    tags = {}
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json',
             '-show_entries', 'format_tags,format=duration', str(mp4)],
            capture_output=True, text=True, timeout=5
        )
        parsed = json.loads(result.stdout)
        tags = parsed.get('format', {}).get('tags', {})
        dur = float(parsed.get('format', {}).get('duration', 0))
    except:
        dur = 0
    
    mins = int(dur // 60)
    secs = int(dur % 60)
    
    desc = tags.get('description', '')
    desc_first = desc.split(chr(10))[0].strip()[:200] if desc else ''
    
    rows.append({
        'folder': folder,
        'original_filename': mp4.name,
        'video_id': vid_id,
        'source': source,
        'upload_date': tags.get('date', ''),
        'duration': f'{mins}:{secs:02d}',
        'duration_secs': int(dur),
        'size_mb': f'{size_mb:.1f}',
        'has_subtitles': has_subs,
        'title': tags.get('title', ''),
        'artist': tags.get('artist', ''),
        'genre': tags.get('genre', ''),
        'source_url': tags.get('comment', ''),
        'description_preview': desc_first,
        'new_filename': '',
        'status': 'keep',
    })
    new_count += 1

with open(MASTER, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

print(f'Added {new_count} new files to master CSV')
print(f'Total: {len(rows)} entries')
"
```

---

## Step 3 - Generate Rename Mapping

Run the reorganize script to classify new files into dig/category folders and generate clean filenames.

```bash
python3 ~/timeteam-reorganize.py
```

This produces:
- `rename-review.txt` — human-readable before/after listing
- `rename-mapping.csv` — machine-readable mapping

**Review the output.** Check:
- New files assigned to correct dig folders
- E/X classification is correct (episodes vs extras)
- No broken titles, orphaned words, or unapproved characters
- No duplicates

---

## Step 4 - Review

Open `\\192.168.0.176\documents\personal\alec\claudeai\timeteam\rename-review.txt` and scan for issues.

### What to look for
- Files in wrong dig folder (keyword matching may miss new dig sites)
- Extras classified as episodes (short clips with E## prefix)
- Broken titles (orphaned "on", "at", empty content)
- Missing [YT] or [P] tags
- Very long filenames (>100 chars)

### If issues found
Edit `~/timeteam-reorganize.py`:
- Add new dig site keywords to `DIG_RULES`
- Add new episode keywords to `is_episode()`
- Add new extra keywords to the exclusion list
- Re-run Step 3

---

## Step 5 - Execute

Once the mapping looks good:

```bash
python3 ~/timeteam-execute.py
```

This will:
1. Create any new target folders
2. Move and rename all mp4 + srt files
3. Remove any duplicates flagged in master CSV
4. Clean up empty old folders

---

## Naming Convention

### Dig folders (E/X split)
```
E01 - Day 1 Title [YT].mp4       (episode - main dig content, 15+ min)
E02 - Day 2 Title [YT].mp4
E03 - Day 3 Title [YT].mp4
E04 - Feature Length Days 1-3 [YT].mp4
X01 - Trailer [YT].mp4            (extra - supporting content)
X02 - Dig Watch Day 1 [P].mp4
X03 - Q and A [P].mp4
```

### Category folders (straight E##)
```
E01 - Title [YT].mp4
E02 - Title [P].mp4
```

### Approved filename characters
- Letters: a-z A-Z
- Numbers: 0-9
- Separators: `-` (dash), `.` (extension only)
- Grouping: `( )` `[ ]`
- Spaces
- Accented Latin: e a i o u with accents

### NOT allowed
Commas, apostrophes, quotes, colons, question marks, exclamation marks, ampersands (use "and"), hash, plus, at, percent, asterisks, emojis

---

## Folder Structure

### Dig Folders (39)
- `Dig 01 (2011)` through `Dig 12 - Oxford Workshop (2011)` — 2011 dig watch clips
- `S21 - Boden Fogou, Cornwall` through `S24 - Brancaster, Norfolk` — new series digs
- `Sutton Hoo` — multi-year project
- `Princely Burial, Cotswolds` — standalone special dig
- `Mortar Wreck, Dorset` / `Little Boy Blue` / `Poverty Point` — standalone specials
- `Expedition Crew - *` / `X Crew - *` — crew projects
- `Time Team Plus - *` — partner projects
- `Specials` — standalone specials (Cottage Core, Vikings, etc.)

### Category Folders (9)
- `Behind the Scenes` — general announcements, Patreon misc content
- `Classic Specials` — rereleased Channel 4 episodes (with year in filename)
- `Commentary` — classic episode commentaries (S##E## prefix)
- `Dig Village Masterclass` — educational series
- `Interviews` — author/expert interviews
- `Podcasts` — general archaeology podcast episodes + audio files
- `Promos` — general promotional content
- `Teatime` — Q&A chat sessions
- `Time Team News` — monthly archaeology news show

---

## Adding a New Dig Site

When Time Team starts a new dig (e.g. S25 - New Site):

1. Add keyword rule to `DIG_RULES` in `timeteam-reorganize.py`:
   ```python
   (r'new site|new location', 'any', 'S25 - New Site, Location'),
   ```

2. Add episode keywords to `is_episode()`:
   ```python
   'new site', 'new location',
   ```

3. Add folder to `DIG_FOLDERS` set if it doesn't match existing prefixes

4. Re-run Steps 3-5

---

## Deduplication

The script catches two types of duplicates:
1. **Same video ID** in both YouTube and Patreon — YouTube version kept (has subtitles)
2. **Same title + similar duration** — YouTube version kept

Duplicates are flagged `duplicate-remove` in the master CSV `status` column and deleted during execution.

---

## Key File Locations

| File | Path | Purpose |
|------|------|---------|
| Download script (YT) | `~/timeteam-download.sh` | Downloads from YouTube channel |
| Download script (Patreon) | `~/timeteam-patreon.sh` | Downloads from Patreon |
| Reorganize script | `~/timeteam-reorganize.py` | Classifies and names files |
| Execute script | `~/timeteam-execute.py` | Moves and renames files |
| Master CSV | Samba `timeteam/timeteam-master.csv` | Full metadata for all files |
| Mapping CSV | Samba `timeteam/rename-mapping.csv` | Current old→new mapping |
| Review doc | Samba `timeteam/rename-review.txt` | Human-readable preview |
| Plan | Samba `timeteam/reorganization-plan.md` | Full reorganization plan |
| Patreon cookies | Samba `timeteam/patreon-cookies.txt` | Auth for Patreon downloads |
| YT download archive | Library root `.downloaded_ids` | Tracks downloaded YouTube IDs |
| Patreon download archive | Library root `.patreon_downloaded_ids` | Tracks downloaded Patreon IDs |
| Video list | Library root `video-list.txt` | All YouTube channel video IDs |

---

## Troubleshooting

### Download script stops mid-run
Re-run it. The `.downloaded_ids` file tracks what's done — it will skip completed files.

### yt-dlp errors
```bash
pip install --user --upgrade yt-dlp
```

### Patreon 401 errors
Cookie expired. Re-export `session_id` from browser (see Step 1).

### File assigned to wrong folder
Edit `DIG_RULES` in `timeteam-reorganize.py`, add the missing keyword, re-run Steps 3-5. The execute script handles moves from any folder to any folder.

### Emby not showing changes
Trigger a library scan in Emby dashboard, or wait for the scheduled scan.
