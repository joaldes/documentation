# Time Team Complete Download System

**Last Updated**: 2026-04-13
**Related Systems**: Emby (Container 102), Samba (Container 104), Claude AI (Container 124)

## Summary

Automated download, classification, and organization of ALL Time Team content — classic Channel 4 era through new-era Series 24, plus dig-specific miniseries and companion content — into five Emby TV shows rooted at `/mnt/hometheater/TV Shows/`.

Current state (post Phase F, 2026-04-13):

| Emby show | Series ID | Files | Seasons | Purpose |
|-----------|-----------|------:|--------:|---------|
| Time Team | 90020 | 502 | 29 | Main show: S01-S20 classics, S21-S24 new-era mains, S491-S500 new-era extras, S00 Specials (Phase E) |
| Time Team Crews | 92442 | 30 | 9 | Expedition Crew + X Crew + Time Team Plus dig projects (Phase F) |
| Time Team Digs | 92441 | 340 | 5 | 2011 Dig 01-12 (S01 mega-season, 317 files) + standalone digs S02-S05 (Phase F) |
| Time Team - Sutton Hoo | 92443 | 62 | 1 | Multi-part Sutton Hoo Dig + Ship Rebuilding content (Phase F) |
| Time Team Online | 88728 | 446 | folders | Catch-all companion content: BTS, Commentary, Interviews, Teatime, Promos, Podcasts, News, Masterclass, Specials |

**Total**: ~1,380 files across 5 shows.

## Architecture

```
Sources                    Processing                   Destination (post Phase F)
─────────                  ──────────                   ─────────────────────────
YouTube Channel ─┐
(@TimeTeamOfficial, ~756)
                 ├→ timeteam-download.sh ─→ classify ─→ /mnt/hometheater/TV Shows/
Patreon (~465) ──┘  timeteam-patreon.sh    rename
                                           Phases 1-F     Time Team/              (series 90020)
                                                           ├── S00                  28  Specials
                                                           ├── S01–S10, S15, S17,
                                                           │   S19, S20           ~138  Classic Channel 4
                                                           ├── S21–S24             32  New-era mains
                                                           └── S491–S500          236  New-era extras (per-dig)

                                                         Time Team Crews/         (series 92442)
                                                           └── S01–S09             30  Dig projects (Expedition/X/Plus)

                                                         Time Team Digs/          (series 92441)
                                                           ├── S01                317  2011 Digs 01-12 (mega-season)
                                                           └── S02–S05             23  Standalone digs

                                                         Time Team - Sutton Hoo/  (series 92443)
                                                           └── S01                 62  Sutton Hoo miniseries + extras

                                                         Time Team Online/        (series 88728) — catch-all
                                                           ├── Behind the Scenes/ 117
                                                           ├── Commentary/         63
                                                           ├── Dig Village Masterclass/ 31
                                                           ├── Interviews/         57
                                                           ├── Podcasts/           23
                                                           ├── Promos/             50
                                                           ├── Specials/            8  (existing, not Classic Specials)
                                                           ├── Teatime/            68
                                                           └── Time Team News/     29
```

## Emby Library Structure

After Phase F, the Time Team content is split across **5 Emby TV shows**:

### Time Team (series 90020)
Main show: classics + new-era + specials + per-dig extras seasons.

| Season | Emby display name | Content | Count |
|--------|------------------|---------|------:|
| 0 | Specials | 28 Classic Specials migrated from Time Team Online (Phase E) | 28 |
| 1-10, 15, 17, 19, 20 | Season N | Classic Channel 4 episodes (pre-existing) | ~138 |
| 15 | (same) | +1 Classic Special Rerelease: Blitzkrieg on Shooters Hill | +1 |
| 19 | (same) | +1 Classic Special Rerelease: The Only Earl Is Essex | +1 |
| 21 | Series 21 | Boden Fogou + Broughton Roman Villa main | 8 |
| 22 | Series 22 | Knights Hospitaller + Anglo-Saxon Cemetery main | 8 |
| 23 | Series 23 | Modbury + Wytch Farm + Band of Brothers main | 10 |
| 24 | Series 24 | Norton Disney + Cerne Abbas + Brancaster main | 6 |
| 491 | Boden Fogou (Extras) | S21 dig 1 extras | 63 |
| 492 | Broughton Roman Villa (Extras) | S21 dig 2 extras | 41 |
| 493 | Knights Hospitaller Preceptory (Extras) | S22 dig 1 extras | 28 |
| 494 | Anglo-Saxon Cemetery (Extras) | S22 dig 2 extras | 30 |
| 495 | Band of Brothers (Extras) | S23 dig 1 extras | 24 |
| 496 | Wytch Farm (Extras) | S23 dig 2 extras | 5 |
| 497 | Modbury (Extras) | S23 dig 3 extras | 9 |
| 498 | Norton Disney (Extras) | S24 dig 1 extras | 16 |
| 499 | Cerne Abbas (Extras) | S24 dig 2 extras | 5 |
| 500 | Brancaster (Extras) | S24 dig 3 extras | 15 |

### Time Team Crews (series 92442)
Dig-project miniseries from Expedition Crew, X Crew, and Time Team Plus (Phase F).

| Season | Content | Count |
|--------|---------|------:|
| 1 | Broughton Sarcophagus (Expedition Crew) | 3 |
| 2 | Sherwood Pines (Expedition Crew) | 2 |
| 3 | Mapperton (X Crew) | 3 |
| 4 | Standing Stone (X Crew) | 3 |
| 5 | Vlochos, Greece (X Crew + misfiled Greece file) | 7 |
| 6 | Operation Cobra (Time Team Plus) | 3 |
| 7 | Student Dig (Time Team Plus) | 3 |
| 8 | Swandro (Time Team Plus) | 2 |
| 9 | Waterloo (Time Team Plus) | 4 |

### Time Team Digs (series 92441)
Standalone dig content (Phase F). S01 is a consolidated mega-season of all 12 × 2011 Digs (all X##-prefixed extras: Dig Watches, Site Wrestles, Q&As). 3-digit E### padding in S01.

| Season | Content | Count |
|--------|---------|------:|
| 1 | 2011 Digs 01-12 combined | 317 |
| 2 | Princely Burial, Cotswolds | 14 |
| 3 | Mortar Wreck, Dorset | 4 |
| 4 | Little Boy Blue | 3 |
| 5 | Poverty Point | 2 |

**Series name gotcha**: Emby auto-matches this folder against TVDB to "Time Team Digs - A History Of Britain". Name is locked to "Time Team Digs" via `/Items/92441` POST with `LockedFields=['Name','SortName','Overview']` + `LockData=true` + `ProviderIds={}`.

### Time Team - Sutton Hoo (series 92443)
Own standalone show for the 62-file multi-part Sutton Hoo Dig miniseries + Ship Rebuilding feature + 56 extras (Phase F). Single season S01.

### Time Team Online (series 88728)
Slimmed catch-all after Phase E/F extractions. 9 category folders remain: Behind the Scenes, Commentary, Dig Village Masterclass, Interviews, Podcasts, Promos, Specials, Teatime, Time Team News. ~446 files total.

## Files & Locations

| File | Path | Purpose |
|------|------|---------|
| YouTube download script | `/home/claudeai/timeteam-download.sh` | Main download + sorting logic |
| Patreon download script | `/home/claudeai/timeteam-patreon.sh` | Patreon downloads with cookie auth |
| Audit builder | `/home/claudeai/timeteam-build-audit.py` | Rebuilds full rename-history CSV |
| Force Emby names (main) | `/tmp/force_emby_names_v2.py` | Syncs episode Name ← filename (Time Team series 90020) |
| Force Emby names (Phase F) | `/tmp/force_emby_names_phase_f.py` | Same but scoped to Crews/Digs/Sutton Hoo (series 92441-92443) |
| Fix Emby IndexNumbers | `/tmp/fix_index_numbers.py` | Force-sets E## on 3-digit-season files |
| Emby ghost cleanup | `/tmp/ghost_cleanup_phase_d.py` | Removes stale DB entries |
| Set season titles | `/tmp/set_season_names.py` | Custom display names for S491-S500 |
| Phase E Specials migrator | `/tmp/phase_e_specials.py` | Classic Specials → Time Team/S00 + merges |
| Phase F TTO restructure | `/tmp/phase_f.py` | TTO split → Crews/Digs/Sutton Hoo shows |
| Video list (YouTube) | `/mnt/hometheater/TV Shows/Time Team/.video-list.txt` | YouTube channel video IDs |
| Download archive | `/mnt/hometheater/TV Shows/Time Team/.downloaded_ids` | Completed-download tracker |
| Patreon cookies | `/mnt/documents/personal/alec/claudeai/timeteam/patreon-cookies.txt` | Patreon session cookie |
| Master CSV | Samba `timeteam/timeteam-master.csv` | Original per-video metadata |
| Audit CSV | Samba `timeteam/timeteam-audit.csv` | Consolidated rename history |

## Phase History

The library has been through 10 rename/reorganization passes. Each pass is audited via its own CSV in the `timeteam/` samba folder. Full audit trail in `AUDIT.md`.

| Pass | Date | What | Mapping CSV |
|------|------|------|-------------|
| 1 - Original | 2026-04-11 | Big reorganization: category → dig folders, E/X split | `rename-mapping.csv` |
| 2 - [YT]/[P] strip | 2026-04-11 | Removed `[YT]`/`[P]` tags from filenames | (deterministic) |
| 2.5 - Season merge | 2026-04-11 | Merged S21-S24 per-dig folders into season folders | (inferred) |
| 3 - Standardize | 2026-04-11 | Canonical dig names, category order, fix typos | `s21-s24-rename-mapping.csv` |
| A | 2026-04-11 | Move 103 dig-tied BTS/Promos/Patreon into S21-S24 | `phase-a-rename-history.csv` |
| B | 2026-04-11 | Clean 29 filenames in standalone dig folders | `phase-b-rename-history.csv` |
| C | 2026-04-11 | Renumber `S##X##` → `S##E##` (fixes Emby parser collision) | `phase-c-rename-history.csv` |
| D | 2026-04-12 | Main/extras split: S21-S24 main, S491-S500 extras | `phase-d-rename-history.csv` |
| E (Specials) | 2026-04-13 | Migrate Classic Specials → Time Team/S00 (28) + S15E06 + S19E07 + Promos/E58 | `phase-e-specials-history.csv` |
| **F (TTO Restructure)** | **2026-04-13** | **Split TTO → Time Team Crews (30), Time Team Digs (340), Time Team - Sutton Hoo (62) + 2 Promos redirects** | **`phase-f-history.csv`** |

## Running the Downloads

### First-time setup
```bash
pip install --user yt-dlp
sudo apt-get install -y screen

# Pull video list from YouTube channel
yt-dlp --flat-playlist --print "%(id)s;;;%(title)s;;;%(duration)s" \
    "https://www.youtube.com/@TimeTeamOfficial/videos" \
    > "/mnt/hometheater/TV Shows/Time Team/.video-list.txt"
```

### Start YouTube downloads
```bash
screen -dmS timeteam bash ~/timeteam-download.sh
screen -r timeteam        # attach
# Ctrl+A, D to detach
```

### Patreon downloads
```bash
# Requires valid session cookie in patreon-cookies.txt
screen -dmS patreon bash ~/timeteam-patreon.sh
```

### Integrating new downloads into the library
See `timeteam-runbook.md` for the full processing workflow. Summary:
1. Classify file as main or extra
2. Determine which dig (canonical name)
3. Target folder = `S{21-24}` (main) or `S{491-500}` (extras)
4. Rename to `Time Team - S{NN}E{NN} - [Dig] - [Detail].mp4`
5. Move via `sudo ssh` + record in new `phase-X-rename-history.csv`
6. Trigger Emby scan
7. Run `force_emby_names_v2.py` to sync filename → Emby title
8. Run `fix_index_numbers.py` if any files are in S491-S500
9. Run `ghost_cleanup_phase_d.py` to remove stale DB entries

## Emby Integration

### API access
- Base URL: `http://192.168.0.13:8096`
- API token (homeassistant, admin-level): `90e3c63887224026ac615faca79c9731`
- Series ID: `90020` (Time Team)
- Admin user ID: `6a4bd2171f154052a9ff885ddf0d979a`

### Library configuration
TV shows library options.xml at `/var/lib/emby/root/default/TV shows/options.xml` (inside container 102) has Episode metadata fetchers CLEARED. This prevents Emby from overriding filename titles with TVDB/TMDB scraped names.

### Trigger library scan via API
```bash
TOKEN="90e3c63887224026ac615faca79c9731"
curl -s -X POST "http://192.168.0.13:8096/Library/Refresh?api_key=$TOKEN"
```

### Force episode Names from filenames (after scan)
```bash
python3 /tmp/force_emby_names_v2.py
```

### Fix IndexNumber for 3-digit seasons
Emby's filename parser fails to extract episode numbers for `S491E01` format. Run:
```bash
python3 /tmp/fix_index_numbers.py
```

### Known Emby quirks
- 3-digit season numbers (S491-S500): Emby parses the season number from folder name correctly but not the episode number from filename. Use `fix_index_numbers.py`.
- Custom season titles: set via `POST /Items/{season_id}` with `Name`, `LockedFields=[Name]`, `LockData=true`. See `/tmp/set_season_names.py`.
- Classic TVDB match (Time Team ID 77043, TheMovieDb 2863): Emby matched Time Team to classic TVDB entry which only has S01-S20. For new-era seasons (21+) and fake extras seasons (491+), TMDB returns 404 on metadata lookups. This is fine since we cleared Episode fetchers anyway.

## Audit Trail

Each rename pass is recorded in a dedicated CSV under `/mnt/documents/personal/alec/claudeai/timeteam/`. The consolidated audit at `timeteam-audit.csv` chains them together — for each video_id, tracks: original YouTube title → pass-1 folder + filename → pass-2 (strip tags) → pass-2.5 (merge) → pass-3 (standardize) → pass-A (move) → pass-B (cleanup) → current disk path.

Rebuild via:
```bash
python3 /home/claudeai/timeteam-build-audit.py
```

**Note**: Current audit builder handles passes 1-5 (through Phase B). Phase C (X→E renumber), Phase D (main/extras split), Phase E (Specials migration), and Phase F (TTO restructure) path changes are NOT yet chained in the audit builder. For full trace-back, extend `timeteam-build-audit.py` with mapping constants for each phase. Each phase has its own complete `phase-X-history.csv` that records the exact src→dst for every file.

## Troubleshooting

### Downloads stuck or failing
```bash
yt-dlp --update
df -h /mnt/hometheater/  # check disk space
```

### Video classified to wrong dig/folder
Title pattern matching may miss new dig sites. Update classification logic in `/tmp/phase_d.py` DIG_TO_EXTRAS_SEASON (or future Phase E equivalent) with new patterns.

### Emby not showing new content
```bash
TOKEN="90e3c63887224026ac615faca79c9731"
curl -s -X POST "http://192.168.0.13:8096/Library/Refresh?api_key=$TOKEN"
```
Wait 1-10 minutes for scan to complete (slow due to per-file ffprobe + thumbnail extract).

### Emby shows wrong titles after scan
Clear metadata fetchers + run force_emby_names_v2.py (see Emby Integration section).

### Ghost entries in Emby after move
```bash
python3 /tmp/ghost_cleanup_phase_d.py
```

### Patreon 401 errors
Session cookie expired. Re-export via Chrome dev tools (see runbook Step 1).

## Estimated Storage

| Content | Files | Size |
|---------|------:|------|
| Time Team S00 Specials + S21-S24 mains + S491-S500 extras | 296 | ~55-65 GB |
| Time Team Crews | 30 | ~4-6 GB |
| Time Team Digs (2011 Digs + standalones) | 340 | ~40-55 GB |
| Time Team - Sutton Hoo | 62 | ~10-15 GB |
| Time Team Online catch-all (BTS + Commentary + Interviews + etc.) | 446 | ~55-70 GB |
| Classic Channel 4 S01-S20 (pre-existing) | ~138 | ~60 GB |
| **Total** | **~1,312** | **~224-271 GB** |
