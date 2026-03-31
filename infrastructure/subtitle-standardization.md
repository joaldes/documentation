# Subtitle Filename Standardization

**Last Updated**: 2026-03-30
**Related Systems**: Samba (Container 104), Emby (Container 102), Radarr (Container 107), Sonarr (Container 110)

## Summary

Standardized ~8,759 subtitle files across the home theater library (`/mnt/hometheater/` on CT 104) to follow Emby naming conventions. Renamed 5,278 files, deleted 1,723 (906 duplicates + 16 junk files), leaving 7,036 clean subtitle files. Zero unrecognized patterns remaining.

## Problem

Subtitle filenames had inconsistent naming conventions causing Emby to misidentify languages, show duplicate subtitle tracks, or miss files entirely. Issues included:

| Issue | Count |
|-------|-------|
| 2-letter language codes (`.en.` instead of `.eng.`) | 3,841 |
| Inconsistent tag casing (`.SDH.` vs `.sdh.`) | 1,027 |
| Duplicate subtitles (both `.en` and `.eng` versions) | 906 |
| Redundant labels (`.eng.English.`) | 810 |
| Pipe characters in filenames (`-\|-`) | 180 |
| Non-standard tags (`.Dialog.Sdh.`, `.eng.British.`, etc.) | ~100 |
| Junk test files in Movies root | 16 |
| Double spaces, uppercase extensions, other oddities | ~25 |

## Standard Applied

```
Movie Name (Year) Quality.lang.tag.srt
```

- **Language**: 3-letter ISO 639-2/B codes (`eng`, `swe`, `nor`, `fin`, `dan`, `isl`, `por`)
- **Tags**: lowercase (`sdh`, `forced`, `commentary`, `full`)
- **No** pipes, redundant labels, double extensions, or dialect codes
- **One** subtitle per language/tag combo (no duplicates)

## Implementation

### Script

`/home/claudeai/fix-subtitles.py` — Python script with `--dry-run` (default) and `--execute` modes.

Applies rename rules in dependency order:
1. Delete junk files (`cross_container_test*`)
2. Fix double extensions (`.SRT.srt` → `.srt`)
3. Fix pipe patterns (`.Dub-|-SDH` → `.eng.sdh`)
4. Fix dialect codes (`.en-us.` → `.eng.`)
5. Fix non-standard tags (`.Dialog.Sdh.` → `.eng.sdh.`, `.eng.British.` → `.eng.sdh.`, `.eng.English.` → `.eng.`)
6. Fix regional tags (`.eng.Canadian-(SDH)` → `.eng.sdh.`, `.eng.United-States` → `.eng.`)
7. Fix source/format tags (`.eng.Anglais-(SDH)-SRT` → `.eng.sdh`, `.eng.SRT` → `.eng.`)
8. Fix commentary variants (`.eng.Commentary-by-Director-*` → `.eng.commentary`)
9. Lowercase all tags (`.SDH.` → `.sdh.`, `.Forced.` → `.forced.`)
10. Convert 2-letter → 3-letter language codes (`.en.` → `.eng.`, `.sv.` → `.swe.`, etc.)
11. Lowercase extension (`.SRT` → `.srt`)
12. Fix double spaces

Conflict handling: if rename target already exists, the source file is deleted (it's a duplicate).

### Execution

```bash
# Must run from CT 104 (Samba) — /mnt/hometheater is read-only via mergerfs on CT 124
# Copy script to CT 104
ssh claude@192.168.0.151 "sudo pct exec 104 -- tee /tmp/fix-subtitles.py" < /home/claudeai/fix-subtitles.py > /dev/null

# Dry run first
ssh claude@192.168.0.151 "sudo pct exec 104 -- python3 /tmp/fix-subtitles.py --dry-run"

# Execute
ssh claude@192.168.0.151 "sudo pct exec 104 -- python3 /tmp/fix-subtitles.py --execute"
```

## Results

| Metric | Before | After |
|--------|--------|-------|
| Total .srt files | 8,759 | 7,036 |
| Files with `.en.` code | 3,841 | 0 |
| Files with pipe characters | 180 | 0 |
| Duplicate subtitle pairs | 906 | 0 |
| Junk test files | 16 | 0 |
| Unrecognized patterns | 0 | 0 |

## Troubleshooting

- **Emby still shows old subtitle names**: Trigger a library rescan in Emby (Settings → Library → Scan All Libraries)
- **Subtitle not detected after rename**: Verify the subtitle filename base matches the video filename base exactly (everything before the `.lang.tag.srt` portion)
- **New downloads have wrong naming**: Radarr/Sonarr subtitle naming profiles may need updating to use `eng` instead of `en`
- **Script can't write files**: Must run from CT 104 directly — the mergerfs mount on CT 124 is read-only for the claudeai user
