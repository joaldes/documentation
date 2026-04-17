# Lizard Tank Overheating — Aux Heat Stuck ON 5 Hours

**Date**: 2026-04-16
**Related Systems**: Home Assistant (VM 100), Node-RED, Z-Wave JS (LXC 108), Zooz ZEN20 Power Strip
**Duration**: ~5 hours (21:52 UTC – 02:59 UTC)

## Summary

The aux heat lamp ran continuously for ~5 hours because the old Node-RED flow's turn-off command was permanently blocked by a stuck binary sensor. Tank hit 122°F hot side. Night mode finally cut everything when the sun went below the horizon. No harm to lizard — resolved by completing the v2 cutover.

## Problem

The old "Lizard" NR flow (tab `fe65fd29.0f28b`) was still active — v2 had been built and tested but not yet cut over. The old flow's aux turn-off path uses `binary_sensor.lizard_tank_temperature_upper_operating_range_normal` with a `halt_if: "on"` gate. When that binary sensor was stuck ON from 20:01–22:12 UTC, every aux turn-off command was blocked at the gate. Aux ran from 21:52 UTC until 02:59 UTC when night mode cut all lamps.

## Root Cause

The old NR flow's architecture gates lamp commands through binary sensors using `halt_if`. When the binary sensor reports an unexpected value or gets stuck, the command is silently swallowed. The new v2 flow reads raw temperature from `sensor.lizard_tank_new` and has no binary sensor dependencies — it would have caught this.

## Resolution

Completed the v2 cutover (previously ~90% done):

1. **Old "Lizard" tab**: disabled in NR
2. **Lizard Tank v2 tab**: already enabled, took over lamp control
3. **HA template fix**: lowered basking cutoff from `avg < 115` to `avg < 110` so basking + UV turn off when Warning-Tank-Hot fires (both thresholds now align at 110°F)
4. **Daily report migration**: updated Daily Messages "lizard tank" function to read `sensor.lizard_tank_new` with correct attribute mapping
5. **Stuck-switch alert**: added 10-minute stuck-switch detection to lz2-ctrl — if aux stays ON after being commanded OFF for 10 min during Warning/Critical states, fires a Telegram alert

## Verification

- Two rounds of multi-agent error checks (3 agents each, checking different aspects) — no bugs found
- Checks covered: template consistency, NR code logic, wiring integrity, stale references, Telegram delivery path, trigger flow, switch entity health, template eval consistency
- Sensor confirmed live: `Healthy - Night`, 75°F, all lamps off, template reload clean (30ms blip)

## Lessons Learned

- **Don't leave old flows active during cutover** — the v2 flow was ready for days before this incident. Completing the cutover earlier would have prevented it.
- **`halt_if` gates are a silent failure mode** — commands are swallowed with no error, no log, no alert. The v2 architecture (sensor computes expected state, NR compares expected vs actual) is fundamentally safer.
- **Align thermal thresholds** — the old design had basking turning off at 115°F but Warning firing at 110°F, leaving a 5°F gap where basking stayed on during a warning state. Now both trigger at 110°F.
