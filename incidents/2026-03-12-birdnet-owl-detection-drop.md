# BirdNET-Go: Owl Detection Drop After Config Change

**Last Updated**: 2026-03-12
**Related Systems**: BirdNET-Go (Komodo CT 128, 192.168.0.179:8060)

## Summary
After changing BirdNET-Go detection settings on March 10, owl detections dropped ~90% (from ~17/day to ~2/day). Root cause was a mismatch between the false positive filter level and the overlap setting. Fixed by increasing overlap from 1.5 to 2.0.

## Problem
User noticed owls were no longer being detected after configuration changes made on March 10, 2026. Investigation revealed:

- **Great Horned Owl**: dropped from 647 detections to 4 (only high-confidence >0.75 survived)
- **All owl species affected**: Barn Owl, Long-eared Owl, Western Screech-Owl
- **Other species less affected**: House Finch still detected at healthy rates since their calls are higher confidence
- BirdNET UI showed warning: *"Filter Level May Not Work Optimally — Level 1 (Lenient) filtering requires overlap 2.0 or higher, but current overlap is 1.5"*

## Root Cause
The false positive filter (`falsepositivefilter.level: 1`) works by cross-checking detections across overlapping audio analysis windows. It requires `overlap >= 2.0` to have enough overlapping windows for comparison. With overlap at 1.5, the filter couldn't properly verify detections and was incorrectly discarding them.

Owl calls are disproportionately affected because they're quieter, lower-frequency, and more spaced out — resulting in lower confidence scores (many in the 0.35–0.75 range) that the malfunctioning filter rejected.

### Detection confidence breakdown (Great Horned Owl, before change)
| Confidence Range | Count |
|-----------------|-------|
| below 0.35 | 25 |
| 0.35–0.50 | 73 |
| 0.50–0.75 | 173 |
| 0.75+ | 376 |

After the change, only the 0.75+ bucket had any detections (4 total).

## Solution
Changed `overlap` from 1.5 to 2.0 in BirdNET-Go settings via the web UI, so the false positive filter level 1 can function correctly.

```yaml
birdnet:
    overlap: 2.0    # was 1.5
```

### Alternative considered
Initially chose to fix the overlap to keep the FP filter active. However, on 2026-03-13, overall detections remained at ~350/day (down from ~700/day) because the FP filter — now working correctly with overlap 2.0 — was aggressively filtering borderline detections. Disabled the FP filter (`level: 0`) since dynamic threshold (0.35) + confidence threshold (0.75) provide sufficient quality gating.

## Key Config File
`/mnt/docker/birdnet-go/config/config.yaml` on Komodo (192.168.0.179)

## Verification
- Check owl detections after 24 hours — should return toward ~17/day baseline
- BirdNET UI warning about filter/overlap mismatch should disappear
- Query: `sqlite3 /mnt/docker/birdnet-go/data/birdnet.db "SELECT date(detected_at, 'unixepoch') as day, COUNT(*) FROM detections d JOIN labels l ON d.label_id = l.id WHERE l.scientific_name = 'Bubo virginianus' AND d.detected_at > strftime('%s', '2026-03-12') GROUP BY day;"`

## Lesson Learned
When changing BirdNET detection settings, check for dependency warnings in the UI. The false positive filter level and overlap settings are coupled — changing one without the other can silently degrade detection quality without producing errors in the logs.
