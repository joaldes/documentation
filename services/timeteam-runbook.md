# Time Team Library - Processing Runbook

**Last Updated**: 2026-04-13 (post Phase F)
**Library**: `/mnt/hometheater/TV Shows/` — 5 separate Emby shows for Time Team content
**Project Files**: `/mnt/documents/personal/alec/claudeai/timeteam/`

## Emby Series IDs

| Series | ID | Purpose |
|--------|---:|---------|
| Time Team | 90020 | Classic S01-S20 + new-era S21-S24 mains + S491-S500 per-dig extras + S00 Specials |
| Time Team Crews | 92442 | Expedition Crew + X Crew + Time Team Plus dig projects |
| Time Team Digs | 92441 | 2011 Dig 01-12 + standalone digs (Princely Burial, Mortar Wreck, etc.) |
| Time Team - Sutton Hoo | 92443 | Multi-part Sutton Hoo Dig miniseries + Ship Rebuilding |
| Time Team Online | 88728 | Catch-all: BTS, Commentary, Interviews, Teatime, Promos, Podcasts, News, Masterclass, Specials |

## Current library structure (post Phase F)

```
/mnt/hometheater/TV Shows/

Time Team/                          (90020)
├── S00                    28   Specials (Phase E)
├── S01–S10, S17, S20     ~138   Classic Channel 4
├── S15                     1   +1 Classic Special Rerelease (Blitzkrieg)
├── S19                     1   +1 Classic Special Rerelease (Earl of Essex)
├── S21–S24                32   New-era mains
└── S491–S500             236   New-era extras per-dig (10 seasons)

Time Team Crews/                    (92442)
├── S01 Broughton Sarcophagus       3
├── S02 Sherwood Pines              2
├── S03 Mapperton                   3
├── S04 Standing Stone              3
├── S05 Vlochos Greece              7   (+1 Greece file moved from generic Expedition Crew)
├── S06 Operation Cobra             3
├── S07 Student Dig                 3
├── S08 Swandro                     2
└── S09 Waterloo                    4

Time Team Digs/                     (92441 — name locked; auto-matches to "...A History Of Britain")
├── S01                            317   2011 Digs 01-12 mega-season (3-digit E### padding)
├── S02 Princely Burial, Cotswolds  14
├── S03 Mortar Wreck, Dorset         4
├── S04 Little Boy Blue              3
└── S05 Poverty Point                2

Time Team - Sutton Hoo/             (92443) — reorganized 2026-04-17
├── S01 The Dig                      5   Main dig episodes (Parts 1-4 + compilation)
│   ├── behind the scenes/          7   BTS clips
│   ├── interviews/                 5   QNA, PUB, John Preston interview
│   ├── specials/                   3   Standalone documentaries
│   ├── featurettes/                2   Weekly highlights
│   └── trailers/                  10   Previews and trailers
├── S02 The Ship                     6   Ship rebuild project
├── S03 The Return                   9   Series 2 dig content
├── S04 Livestreams                 11   Daily livestream coverage
└── S00 (4 remaining)               4   360-cam and specs-cam clips

Time Team Online/                   (88728) — catch-all
├── Behind the Scenes/             117
├── Commentary/                     63
├── Dig Village Masterclass/        31
├── Interviews/                     57
├── Podcasts/                       23
├── Promos/                         50   (+2 Site-Wrestle redirects E59/E60 from Phase F)
├── Specials/                        8   (existing 8-file folder, not Classic Specials)
├── Teatime/                        68
└── Time Team News/                 29
```

## Filename conventions

### Main seasons (S21-S24, S491-S500)
`Time Team - S{season}E{num:02d} - [Dig] - [Detail].mp4`

Examples:
- `Time Team - S22E01 - Knights Hospitaller Preceptory - Day 1.mp4`
- `Time Team - S493E14 - Knights Hospitaller Preceptory - Preview.mp4`

### Time Team Online folders
`E##/X## - Title.mp4` (self-contained numbering per folder)

Example: `E01 - The Sutton Hoo Ship - Rebuilding a Legend (Part 1) with Tony Robinson.mp4`

### Approved filename characters
Letters a-z A-Z, digits 0-9, spaces, dashes `-`, parens `( )`, brackets `[ ]`, accented Latin.

### Category abbreviations
Used as prefix tags in filenames: `S00E01 - BTS - Jimmys GPR Diary.mp4`

| Abbr | Category | Emby Subfolder |
|------|----------|----------------|
| DIG | Main dig episodes | *(main folder)* |
| HLT | Weekly highlights | `featurettes` |
| QNA | Q and A sessions | `interviews` |
| LVS | Livestream coverage | `specials` |
| DGW | Dig Watch | `scenes` |
| SIT | Site Tour | `behind the scenes` |
| BTS | Behind the Scenes | `behind the scenes` |
| PRV | Preview or teaser | `trailers` |
| TRL | Trailer | `trailers` |
| PUB | Pub Chat | `interviews` |
| BKC | Book Club | `featurettes` |
| 360 | 360-degree camera | `shorts` |
| SPC | Specs-Cam | `shorts` |
| FNF | Fun Fact | `shorts` |
| MST | Masterclass | `featurettes` |
| DEL | Deleted or Cut content | `deleted scenes` |
| --- | Catch-all | `extras` |

Emby extras subfolders are placed inside season folders. All extras appear in a single "Extras" row in the Emby detail view regardless of subfolder name. Supported subfolder names: `extras`, `specials`, `shorts`, `scenes`, `featurettes`, `behind the scenes`, `deleted scenes`, `interviews`, `trailers`.

### NOT allowed
Commas, apostrophes, quotes, colons, question marks, exclamation marks, ampersands (use "and"), hash, plus, at, percent, asterisks, emojis.

---

## Step 1 - Download New Content

### YouTube

```bash
# 1. Refresh the video list from the channel
yt-dlp --flat-playlist --print "%(id)s;;;%(title)s;;;%(duration)s" \
    "https://www.youtube.com/@TimeTeamOfficial/videos" \
    > "/mnt/hometheater/TV Shows/Time Team/.video-list.txt"

# 2. Run the download script (skips already-downloaded via .downloaded_ids)
screen -dmS timeteam bash ~/timeteam-download.sh

# 3. Monitor
tail -f "/mnt/hometheater/TV Shows/Time Team/.download-log.txt"
```

### Patreon

Requires valid session cookie. If downloads fail with 401, re-export cookie:
1. Open Chrome, go to patreon.com (logged in via Google)
2. F12 → Console → `document.cookie` → find `session_id` value
3. Update `/mnt/documents/personal/alec/claudeai/timeteam/patreon-cookies.txt`

```bash
screen -dmS patreon bash ~/timeteam-patreon.sh
```

**Note**: Download scripts drop files into temporary sorting folders. New files need to be processed through Steps 2-5 below to integrate into the library.

---

## Step 2 - Classify and Assign to Target Folder

For each newly-downloaded file:

1. **Determine if it's main content or an extra**:
   - Main = the Time Team show itself (Day 1/2/3 of a dig, feature-length Days 1-3 cut, single-feature special like "Cerne Abbas: Secrets Beneath The Giant")
   - Extra = everything else (Dig Watch clips, Q&As, Morning Briefings, Site Wrestles, previews, BTS, etc.)

2. **Determine the dig**:
   - S21-S24 new era → match against canonical dig names in the classifier
   - Standalone dig (Sutton Hoo, Princely Burial, etc.) → use its dedicated folder
   - Show series (Teatime, News, Podcasts, Masterclass) → use its category folder under `Time Team Online/`

3. **Target folder**:
   - Main episodes → `TV Shows/Time Team/S{21-24}/`
   - Extras → `TV Shows/Time Team/S{491-500}/` (per dig)
   - Standalone digs → `TV Shows/Time Team Online/{Dig Name}/`
   - Show series → `TV Shows/Time Team Online/{Category}/`

4. **Filename format** (see conventions above)

---

## Step 3 - Move & Rename

Execute the move with `sudo mv` via the Proxmox host:

```bash
ssh claude@192.168.0.151 'sudo mv "/path/to/source.mp4" "/path/to/target.mp4"'
# Don't forget the .en.srt sidecar
ssh claude@192.168.0.151 'sudo mv "/path/to/source.en.srt" "/path/to/target.en.srt"'
```

Record the move in a rename-history CSV (for audit). Current history files:
- `phase-a-rename-history.csv` — Phase A Time Team Online → S21-S24 merges (103 files)
- `phase-b-rename-history.csv` — Phase B in-place cleanup (29 files)
- `phase-c-rename-history.csv` — Phase C X→E renumber (229 files)
- `phase-d-rename-history.csv` — Phase D main/extras split (236 files)
- `phase-e-specials-history.csv` — Phase E Classic Specials → Time Team/S00 + merges (31 files)
- `phase-f-history.csv` — Phase F TTO restructure → Crews/Digs/Sutton Hoo (434 files)
- `sutton-hoo-reorganize-history.csv` — Sutton Hoo S01 split into 5 seasons (62 files)
- `sutton-hoo-master.csv` — Comprehensive Sutton Hoo file tracker (62 files): filename, Emby ID, display name, overview status, subtitle status, category, subfolder

---

## Step 4 - Emby Sync

### Trigger library scan
```bash
TOKEN="90e3c63887224026ac615faca79c9731"  # API token for homeassistant
curl -s -X POST "http://192.168.0.13:8096/Library/Refresh?api_key=$TOKEN"
```

### Force Emby to use filename titles (not TVDB)

After scan, episodes may have incorrect TVDB-scraped titles. Two scripts depending on which series:
- `/tmp/force_emby_names_v2.py` — Time Team (series 90020): covers S21-S24 + S491-S500 + S00/S15/S19 (Phase E). Edit the `SEASONS` list for scope.
- `/tmp/force_emby_names_phase_f.py` — Covers Time Team Crews (92442), Time Team Digs (92441), Time Team - Sutton Hoo (92443).

Both parse filename → `Name`, set `LockedFields=['Name', 'SortName', 'Overview']` + `LockData=true`.

### Lock series name on new shows (Phase F gotcha)

### Metadata push (per-show)

After organizing files, push metadata via Emby API for each show:

1. **Show level**: Name, Overview, Genres, Tags, Year, Studio, Rating. Lock data.
2. **Season level**: GET full object, update Name and Overview, POST back. Lock data.
3. **Episode level**: GET full object, update Name (strip filename prefix) and Overview (clean YouTube descriptions — strip promo links, social media, merchandise). Lock data.

Pattern (GET-modify-POST):


Track results in per-show master CSV (e.g. ): Emby ID, display name, overview status, subtitle status, locked status.

When adding a new show folder (e.g., `Time Team Digs/`), Emby's scanner may auto-match against TVDB and apply a wrong name. Phase F hit this: `Time Team Digs` auto-matched to "Time Team Digs - A History Of Britain". Fix via API:

```bash
curl -s -X POST "http://192.168.0.13:8096/Items/<SERIES_ID>?api_key=$TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary '{"Name":"Time Team Digs","SortName":"Time Team Digs","LockedFields":["Name","SortName","Overview"],"LockData":true,"ProviderIds":{},"Overview":""}'
```

Post-edit, `LockData=true` + `ProviderIds={}` together prevent re-matching on future scans.

### Fix IndexNumber for 3-digit seasons (S491-S500)

Emby's parser fails to extract episode numbers from 3-digit season filenames. Run `/tmp/fix_index_numbers.py` to force-set IndexNumber/ParentIndexNumber from filename via API.

### Remove ghost DB entries

Emby sometimes keeps stale DB rows after file moves. Detect + cleanup with `/tmp/ghost_cleanup_phase_d.py`:
1. Queries all S21-S24 + S491-S500 items from Emby
2. For each, checks if the file exists on disk
3. If not, SQL-deletes the row from `library.db` (stops Emby, deletes, starts Emby)

### Custom season display names

Extras seasons (S491-S500) should display their dig name. Run `/tmp/set_season_names.py` to set via API.

---

## Step 5 - Update Audit Trail

Rebuild the consolidated audit CSV:

```bash
python3 /home/claudeai/timeteam-build-audit.py
```

This walks all disk files + chains through `rename-mapping.csv`, `s21-s24-rename-mapping.csv`, `phase-a-rename-history.csv`, `phase-b-rename-history.csv` to produce `timeteam-audit.csv` — one row per video_id with full rename history + current disk path.

**Note**: Audit builder currently handles passes 1-5 (through Phase B). Phase C, D, E, and F chaining is deferred — update the builder if you need full chain. Each phase has its own `phase-X-history.csv` that records the exact src→dst for every file as a workaround.

---

## Naming Convention Reference

### Main seasons format
`Time Team - S{NN}E{NN} - [Dig] - [Day N | Days 1-3 | Feature name].mp4`

### Extras seasons format
`Time Team - S{NNN}E{NN} - [Dig] - [Category] - [Detail].mp4`
- Categories: `Dig Watch`, `Site Wrestle`, `Site Walkabout`, `Morning Brief`, `Recap`, `Q and A`, `Trailer`, `Preview`, `Behind the Scenes`, `Masterclass`, `Aerial Tour`, `Malta Archives`, `Fun Fact`, `Day Zero`

### Canonical dig names (per series)
| Series | Digs |
|--------|------|
| S21 (2022) | Boden Fogou, Broughton Roman Villa |
| S22 (2023) | Knights Hospitaller Preceptory, Anglo-Saxon Cemetery |
| S23 (2024) | Band of Brothers, Wytch Farm, Modbury |
| S24 (2025-2026) | Norton Disney, Cerne Abbas, Brancaster |

### Extras season numbering (descending preference)
| Season | Dig | Files |
|--------|-----|------:|
| S491 | Boden Fogou | 63 |
| S492 | Broughton Roman Villa | 41 |
| S493 | Knights Hospitaller Preceptory | 28 |
| S494 | Anglo-Saxon Cemetery | 30 |
| S495 | Band of Brothers | 24 |
| S496 | Wytch Farm | 5 |
| S497 | Modbury | 9 |
| S498 | Norton Disney | 16 |
| S499 | Cerne Abbas | 5 |
| S500 | Brancaster | 15 |

---

## Phase History

| Phase | Date | What | Files affected |
|-------|------|------|---------------|
| Original | 2026-04-11 | Big reorganization: category-based → dig-based folders, E/X split | ~1,175 |
| Pass 2 | 2026-04-11 | Strip `[YT]`/`[P]` tags from all filenames | ~1,175 |
| Pass 2.5 | 2026-04-11 | Merge S21-S24 per-dig folders into single season folders | 165 |
| Phase 3 (S21-S24) | 2026-04-11 | Standardize S21-S24 filenames (canonical dig names, fixed category order) | 156 |
| Phase A | 2026-04-11 | Move dig-tied content from BTS/Promos/Patreon into S21-S24 | 103 |
| Phase B | 2026-04-11 | Clean up filenames in standalone dig folders (Sutton Hoo, Princely Burial, etc.) | 29 |
| Phase C | 2026-04-11 | Renumber `S##X##` extras to `S##E##` with offset (fixes Emby parsing collision) | 229 |
| Phase D | 2026-04-12 | Split main content from extras: main stays in S21-S24, extras move to S491-S500 | 236 |
| Phase E (Specials) | 2026-04-13 | Migrate Classic Specials → Time Team/S00 (28) + S15E06 Blitzkrieg + S19E07 Earl of Essex + 1 preview to Promos/E58 | 31 |
| **Phase F (TTO)** | **2026-04-13** | **Split Time Team Online into Time Team Crews (30, 9 seasons) + Time Team Digs (340, 5 seasons) + Time Team - Sutton Hoo (62, 1 season) + 2 Promos redirects** | **434** |
| **Sutton Hoo reorg** | **2026-04-17** | **Split 62-ep S01 into S00 Extras (24) + S01 The Dig (12) + S02 The Ship (6) + S03 The Return (9) + S04 Livestreams (11). Added 3-char category abbreviations (BTS, PRV, QNA, LVS, DGW, etc.). Emby extras subfolders (behind the scenes, interviews, specials, featurettes, trailers, shorts). Metadata push via API: show overview/genres/year, season names/overviews, episode display names and cleaned overviews** | **62** |

---

## Key File Locations

| File | Path | Purpose |
|------|------|---------|
| Download script (YT) | `~/timeteam-download.sh` | Downloads from YouTube channel |
| Download script (Patreon) | `~/timeteam-patreon.sh` | Downloads from Patreon |
| Audit builder | `~/timeteam-build-audit.py` | Rebuilds consolidated audit CSV |
| Force Emby names (main) | `/tmp/force_emby_names_v2.py` | Time Team series 90020 |
| Force Emby names (Phase F) | `/tmp/force_emby_names_phase_f.py` | Crews/Digs/Sutton Hoo series 92441-92443 |
| Fix IndexNumbers | `/tmp/fix_index_numbers.py` | Fixes S491-S500 episode numbers |
| Ghost cleanup | `/tmp/ghost_cleanup_phase_d.py` | Detects+removes stale DB entries |
| Season name setter | `/tmp/set_season_names.py` | Custom display names for S491-S500 |
| Phase E migrator | `/tmp/phase_e_specials.py` | Classic Specials → S00 + merges |
| Phase F migrator | `/tmp/phase_f.py` | TTO split → Crews/Digs/Sutton Hoo |
| Master CSV | Samba `timeteam/timeteam-master.csv` | Original per-video metadata |
| Audit CSV | Samba `timeteam/timeteam-audit.csv` | Consolidated rename history |
| AUDIT.md | Samba `timeteam/AUDIT.md` | Human-readable audit trail for all phases |
| Pass 1 mapping | Samba `timeteam/rename-mapping.csv` | Original reorganization |
| Pass 3 mapping | Samba `timeteam/s21-s24-rename-mapping.csv` | S21-S24 standardization |
| Phase A mapping | Samba `timeteam/phase-a-rename-history.csv` | BTS/Promos → dig folders |
| Phase B mapping | Samba `timeteam/phase-b-rename-history.csv` | Dig folder filename cleanup |
| Phase C mapping | Samba `timeteam/phase-c-rename-history.csv` | X→E renumber |
| Phase D mapping | Samba `timeteam/phase-d-rename-history.csv` | Main/extras split |
| Phase E mapping | Samba `timeteam/phase-e-specials-history.csv` | Classic Specials migration |
| Phase F mapping | Samba `timeteam/phase-f-history.csv` | TTO restructure (434 files) |
| Patreon cookies | Samba `timeteam/patreon-cookies.txt` | Auth for Patreon downloads |

---

## Emby Integration Notes

### Series IDs & API token
- Time Team: `90020` | Time Team Crews: `92442` | Time Team Digs: `92441` | Time Team - Sutton Hoo: `92443` | Time Team Online: `88728`
- TV shows library: `/mnt/hometheater/TV Shows`
- API token (homeassistant integration, admin-level): `90e3c63887224026ac615faca79c9731`
- Admin user ID: `6a4bd2171f154052a9ff885ddf0d979a`
- Base URL: `http://192.168.0.13:8096`

### Library configuration
- File: `/var/lib/emby/root/default/TV shows/options.xml`
- **Episode metadata fetchers CLEARED** — no TVDB/TMDB lookup for episodes so filename-based titles stick
- Image fetchers CLEARED for episodes too

### Season display names (set via API)
Stored in Emby DB with `LockData=true`. Can be updated via `POST /Items/{season_id}` with `Name`, `LockedFields`.

---

## Troubleshooting

### Emby shows wrong episode titles (e.g., TVDB names instead of filenames)
Clear Episode metadata fetchers in `options.xml`, restart Emby, then run `force_emby_names_v2.py`:
```bash
ssh claude@192.168.0.151 'sudo pct exec 102 -- systemctl restart emby-server'
python3 /tmp/force_emby_names_v2.py
```

### Emby shows wrong episode numbers (IndexNumber None) for 3-digit seasons
Emby's parser fails on S491-S500. Run `fix_index_numbers.py` to force-set from filename.

### Ghost items in Emby (file moved, DB entry still points to old path)
Run `ghost_cleanup_phase_d.py` — SQL-deletes stale rows.

### yt-dlp errors
```bash
pip install --user --upgrade yt-dlp
```

### Patreon 401 errors
Cookie expired. Re-export `session_id` from browser (see Step 1).

### Download script stops mid-run
Re-run it. The `.downloaded_ids` file tracks what's done — it will skip completed files.

### Emby library scan stuck
Scan can take 5-15 minutes for full library due to ffprobe + thumbnail generation per file. Monitor via Emby dashboard → Scheduled Tasks → "Scan media library" progress.

### Classic rereleases in wrong era
Some Brancaster files are 2013 Classic rereleases (not new-era). They currently live in S500 (Brancaster Extras). If you want them in their proper classic season, manually move to S20 based on the embedded `S20E##` marker in the filename.

### S24E01 vs S24E02 Norton Disney Day 1 duplicate
Unresolved — both files exist in Series 24 main. One is Patreon preview, one is YouTube final. Compare durations via ffprobe and delete the shorter (preview) via Emby DELETE /Items.

---

## Deferred work (Phase E candidates)

1. **Classify Time Team Online content** into further sub-seasons (Sutton Hoo as S489, 2011 Digs as S478-S489, etc.) — would bring the 1,000+ companion files into the same Emby-browsable season structure
2. **Move classic rereleases** (S500 Brancaster classics, any other classic-era reuploads) into their proper classic season folders (S01-S20)
3. **Resolve duplicates** (S24 Norton Day 1 × 2)
4. **Audit builder Phase C/D chain** — extend `timeteam-build-audit.py` to handle Phase C and D rename passes
