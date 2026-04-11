#!/usr/bin/env python3
"""Execute the Time Team library reorganization.
Reads rename-mapping.csv and moves/renames all files."""

import csv
import os
import shutil
from pathlib import Path
from collections import defaultdict

BASE = Path("/mnt/hometheater/Time Team YouTube")
MAPPING = Path("/mnt/documents/personal/alec/claudeai/timeteam/rename-mapping.csv")
MASTER = Path("/mnt/documents/personal/alec/claudeai/timeteam/timeteam-master.csv")

# Read mapping
with open(MAPPING) as f:
    rows = list(csv.DictReader(f))

print(f"Loaded {len(rows)} file mappings")

# Read master to find duplicates to remove
with open(MASTER) as f:
    master = list(csv.DictReader(f))
dupes = [r for r in master if r.get('status') == 'duplicate-remove']
print(f"Found {len(dupes)} duplicates to remove")

# Step 1: Create all target folders
folders = set(r['target_folder'] for r in rows)
for folder in sorted(folders):
    target = BASE / folder
    target.mkdir(parents=True, exist_ok=True)
print(f"Created {len(folders)} target folders")

# Step 2: Move and rename files
moved = 0
skipped = 0
errors = []

for row in rows:
    old_path = BASE / row['old_folder'] / row['old_filename']
    new_path = BASE / row['target_folder'] / row['new_filename']

    # Skip if source doesn't exist
    if not old_path.exists():
        skipped += 1
        continue

    # Skip if target already exists
    if new_path.exists() and old_path != new_path:
        errors.append(f"TARGET EXISTS: {new_path}")
        continue

    # Move the mp4
    try:
        shutil.move(str(old_path), str(new_path))
        moved += 1
    except Exception as e:
        errors.append(f"MOVE FAILED: {old_path} -> {new_path}: {e}")
        continue

    # Move matching .srt file if it exists
    old_srt = old_path.with_suffix('.en.srt')
    if old_srt.exists():
        new_srt = new_path.with_suffix('.en.srt')
        try:
            shutil.move(str(old_srt), str(new_srt))
        except Exception as e:
            errors.append(f"SRT MOVE FAILED: {old_srt}: {e}")

    if moved % 100 == 0:
        print(f"  Moved {moved}...")

print(f"Moved: {moved}, Skipped (not found): {skipped}, Errors: {len(errors)}")

# Step 3: Remove duplicates
removed = 0
for row in dupes:
    dup_path = BASE / row['folder'] / row['original_filename']
    if dup_path.exists():
        dup_path.unlink()
        removed += 1
        # Also remove srt
        dup_srt = dup_path.with_suffix('.en.srt')
        if dup_srt.exists():
            dup_srt.unlink()

print(f"Removed {removed} duplicate files")

# Step 4: Clean up empty old folders
empty_removed = 0
for d in sorted(BASE.iterdir()):
    if d.is_dir() and not any(d.iterdir()):
        d.rmdir()
        empty_removed += 1
        print(f"  Removed empty folder: {d.name}")

print(f"Removed {empty_removed} empty folders")

# Report errors
if errors:
    print(f"\n{len(errors)} ERRORS:")
    for e in errors[:20]:
        print(f"  {e}")
    if len(errors) > 20:
        print(f"  ...and {len(errors) - 20} more")

# Final count
remaining = sum(1 for _ in BASE.rglob("*.mp4"))
folder_count = sum(1 for d in BASE.iterdir() if d.is_dir())
print(f"\nFinal: {remaining} mp4 files in {folder_count} folders")
