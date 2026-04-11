#!/usr/bin/env python3
"""
Time Team Library Reorganizer
Reads master CSV, assigns each file to a dig/category folder,
generates clean E## filenames, outputs review document.
"""

import csv
import re
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime

BASE = Path("/mnt/hometheater/Time Team YouTube")
MASTER = Path("/mnt/documents/personal/alec/claudeai/timeteam/timeteam-master.csv")
REVIEW_OUT = Path("/mnt/documents/personal/alec/claudeai/timeteam/rename-review.txt")
MAPPING_OUT = Path("/mnt/documents/personal/alec/claudeai/timeteam/rename-mapping.csv")

# ─── DIG ASSIGNMENT RULES ───────────────────────────────────────
# Maps keywords/patterns → target folder
# Checked in order; first match wins

DIG_RULES = [
    # 2011 Dig Watch by TT code
    (r'^TT[- ]*03', 'title', 'Dig 03 - Badgers Hill (2011)'),
    (r'^TT[- ]*04', 'title', 'Dig 04 (2011)'),
    (r'^TT[- ]*05', 'title', 'Dig 05 (2011)'),
    (r'^TT[- ]*06', 'title', 'Dig 06 - Dunwich (2011)'),
    (r'^TT[- ]*07', 'title', 'Dig 07 (2011)'),
    (r'^TT[- ]*08', 'title', 'Dig 08 (2011)'),
    (r'^TT[- ]*09', 'title', 'Dig 09 (2011)'),
    (r'^TT[- ]*10', 'title', 'Dig 10 (2011)'),
    (r'^TT[- ]*11', 'title', 'Dig 11 - Trerice (2011)'),
    (r'^TT[- ]*12', 'title', 'Dig 12 - Oxford Workshop (2011)'),

    # New series digs (keyword in title or description)
    (r'boden.*fogou|boden iron age|iron age settlement in cornwall', 'any', 'S21 - Boden Fogou, Cornwall'),
    (r'broughton.*villa|broughton.*oxfordshire|roman villa.*oxfordshire|dig 2.*roman villa|dig two.*oxfordshire', 'any', 'S21 - Broughton Roman Villa, Oxfordshire'),
    (r'roman sarcophagus|return to broughton|broughton sarcophagus', 'any', 'Expedition Crew - Broughton Sarcophagus'),
    (r'princely burial|cotswolds.*dig|cherington|sword in the stones', 'any', 'Princely Burial, Cotswolds'),
    (r'knights? hospitaller|preceptory|halston', 'any', 'S22 - Knights Hospitaller, Shropshire'),
    (r'anglo.saxon cemetery|winfarthing', 'any', 'S22 - Anglo-Saxon Cemetery, Norfolk'),
    (r'band of brothers|operation nightingale|aldbourne|ramsbury 506', 'any', 'S23 - Band of Brothers, Aldbourne'),
    (r'wytch farm|iron age.*dorset.*2023', 'any', 'S23 - Wytch Farm, Dorset'),
    (r'modbury', 'any', 'S23 - Modbury, Devon'),
    (r'norton disney|digging for disney', 'any', 'S24 - Norton Disney, Lincolnshire'),
    (r'cerne abbas|lost abbey.*dorset', 'any', 'S24 - Cerne Abbas, Dorset'),
    (r'sutton hoo|bromeswell', 'any', 'Sutton Hoo'),
    (r'mapperton', 'any', 'X Crew - Mapperton'),
    (r'brancaster|branodunum|geofizz', 'any', 'S24 - Brancaster, Norfolk'),
    (r'mortar wreck|oldest shipwreck', 'any', 'Mortar Wreck, Dorset'),
    (r'little boy blue', 'any', 'Little Boy Blue'),
    (r'poverty point|mystery mounds', 'any', 'Poverty Point'),
    (r'sherwood pines|forest to front', 'any', 'Expedition Crew - Sherwood Pines'),
    (r'vlochos|greek dig|ancient greek', 'any', 'X Crew - Vlochos, Greece'),
    (r'standing stone.*x crew|mystery.*standing stone', 'any', 'X Crew - Standing Stone'),
    (r'cottage core|500 years of life', 'any', 'Specials'),
    (r'saving swandro|swandro.*orkney', 'any', 'Time Team Plus - Swandro'),
    (r'waterloo uncovered', 'any', 'Time Team Plus - Waterloo'),
    (r'operation cobra|normandy.*2024', 'any', 'Time Team Plus - Operation Cobra'),
    (r'student dig|unearthing roman villa.*plus', 'any', 'Time Team Plus - Student Dig'),
    (r'vikings.*real northmen', 'any', 'Specials'),
]

# Category rules for non-dig content
CATEGORY_RULES = [
    (r'^Time Team Commentary|^Commentary|^Post Dig Analysis|^Extra Commentary', 'title', 'Commentary'),
    (r'masterclass|dig village|stuck at home', 'any', 'Dig Village Masterclass'),
    (r'^Teatime|^Time Team Teatime|Teatime \d+|Teatime Session', 'any', 'Teatime'),
    (r'^Time Team Podcast|^Time Team podcast', 'title', 'Podcasts'),
    (r'Time Team News|archaeology news|amazing.*archaeology|dazzling discoveries|epic finds.*lost', 'any', 'Time Team News'),
    (r'huge announcement.*classic specials', 'any', 'Promos'),
    (r'classic special|full episode.*s\d+e\d+|Classic \(\d{4}\)|classic rerelease', 'any', 'Classic Specials'),
    (r'meets time team|interview|in conversation|time team memories', 'any', 'Interviews'),
    (r'aftershow|big dome|first look|assemble|books of year|2022 in archaeology|dig countdown|digital dig|year ahead', 'any', 'Behind the Scenes'),
    (r'merchandise|flag of fame|black friday|membership|trailer$|teaser$|coming soon|announcement|welcome to time team|channel trailer|pimp tony|competition|name.*bus', 'any', 'Promos'),
]

# Date-based assignment for uncoded 2011 clips
def assign_by_date(upload_date):
    """Assign uncoded 2011 clips to digs by date."""
    if not upload_date:
        return None
    d = upload_date
    if '20110406' <= d <= '20110412':
        return 'Dig 01 (2011)'
    if '20110413' <= d <= '20110503':
        return 'Dig 02 (2011)'
    if '20110504' <= d <= '20110516':
        return 'Dig 03 - Badgers Hill (2011)'
    if '20110517' <= d <= '20110601':
        return 'Dig 04 (2011)'
    if '20110602' <= d <= '20110613':
        return 'Dig 05 (2011)'
    if '20110614' <= d <= '20110706':
        return 'Dig 06 - Dunwich (2011)'
    if '20110707' <= d <= '20110718':
        return 'Dig 07 (2011)'
    if '20110719' <= d <= '20110805':
        return 'Dig 08 (2011)'
    if '20110806' <= d <= '20110812':
        return 'Dig 09 (2011)'
    if '20110813' <= d <= '20111030':
        return 'Dig 10 (2011)'
    if '20111030' <= d <= '20111210':
        return 'Dig 11 - Trerice (2011)'
    if '20111211' <= d <= '20120301':
        return 'Dig 12 - Oxford Workshop (2011)'
    return None


def classify_file(row):
    """Determine which folder a file belongs in."""
    title = row.get('title', '')
    desc = row.get('description_preview', '')
    orig = row.get('original_filename', '')
    search_text = f"{title} {desc} {orig}"

    # Check dig rules first (title match)
    for pattern, field, folder in DIG_RULES:
        if field == 'title':
            if re.search(pattern, title, re.I) or re.search(pattern, orig, re.I):
                return folder
        else:  # 'any'
            if re.search(pattern, search_text, re.I):
                return folder

    # Check date-based assignment for 2011 content
    date_folder = assign_by_date(row.get('upload_date', ''))
    if date_folder:
        return date_folder

    # Check category rules
    for pattern, field, folder in CATEGORY_RULES:
        if field == 'title':
            if re.search(pattern, title, re.I) or re.search(pattern, orig, re.I):
                return folder
        else:
            if re.search(pattern, search_text, re.I):
                return folder

    # Fallback: if already in a known category folder, keep it there
    current = row.get('folder', '')
    known_categories = {
        'Commentary', 'Teatime', 'Podcasts', 'Time Team News', 'Classic Specials',
        'Dig Village Masterclass', 'Interviews', 'Behind the Scenes', 'Promos',
        'Time Team Plus', 'Specials', 'Expedition Crew', 'X Crew',
    }
    if current in known_categories:
        return current

    # Patreon content: most remaining general stuff is behind-the-scenes
    if row.get('source') == 'patreon':
        t = (title + ' ' + desc + ' ' + orig).lower()
        # Check for dig-specific content one more time with looser matching
        if 'broughton' in t and 'sarcophagus' not in t:
            return 'S21 - Broughton Roman Villa, Oxfordshire'
        if 'dig two' in t or 'dig 2' in t:
            return 'S21 - Broughton Roman Villa, Oxfordshire'
        if 'dig one' in t or 'dig 1' in t:
            return 'S21 - Boden Fogou, Cornwall'
        if any(x in t for x in ['extended commentary', 'post dig analysis', 'post-dig analysis']):
            return 'Commentary'
        if any(x in t for x in ['classic (', 'classic rerelease', 'full episode']):
            return 'Classic Specials'
        if re.search(r'\bs\d+e\d+\b', t) or re.search(r'\bs\d+ ep\d+\b', t):
            return 'Classic Specials'
        if any(x in t for x in ['site wrestle', 'site suggestion']):
            return 'Behind the Scenes'
        if any(x in t for x in ['eanswythe', 'finding eanswythe']):
            return 'Interviews'
        # Everything else from Patreon goes to Behind the Scenes
        return 'Behind the Scenes'

    # Last resort — general dig watch promos and misc YouTube
    return 'Promos'


def clean_title(title):
    """Clean a title for use as a filename."""
    t = title

    # Strip fluff prefixes
    for pat in [
        r'^NEW[!| ]+', r'^New Episode[!| ]+', r'^EXCLUSIVE[!|: ]+',
        r'^TRAILER[|: -]+', r'^Coming Soon[!|: -]+', r'^Coming Up[!|: -]+',
        r'^BRAND NEW[!| ]+', r'^WATCH[!|: ]+', r'^LISTEN[!|: ]+',
        r'^FIRST LOOK[!|: ]+', r'^DIG PREVIEW[!|: -]+',
        r'^MEMBERS PRE-RELEASE[!|: -]+', r'^EARLY ACCESS[!|: -]+',
        r'^EPISODE[!|: ]+', r'^FEATURE LENGTH[|: ]+',
        r'^TEASER[|: ]+', r'^TODAY[|: ]+', r'^FULL LENGTH[|: ]+',
    ]:
        t = re.sub(pat, '', t, flags=re.I)

    # Remove Time Team and Patreon variations
    t = re.sub(r'\s*\(Time Team\)', '', t, flags=re.I)
    t = re.sub(r'\s*\(Patreon exclusive\)', '', t, flags=re.I)
    t = re.sub(r'\s*\(Patreon\)', '', t, flags=re.I)
    t = re.sub(r'\s*\(ad-free\)', '', t, flags=re.I)
    t = re.sub(r'\s*\(Full Episode\)', '', t, flags=re.I)
    t = re.sub(r'\s*[-–]\s*Patreon exclusive\s*$', '', t, flags=re.I)
    t = re.sub(r'\s*[-–]\s*Patreon\s*$', '', t, flags=re.I)
    t = re.sub(r'\s*on Patreon\s*$', '', t, flags=re.I)
    t = re.sub(r'\s*[-–]\s*on Patreon\b', '', t, flags=re.I)
    t = re.sub(r'\bPatreon exclusive\b', '', t, flags=re.I)
    t = re.sub(r'\bPatreon\b', '', t, flags=re.I)
    t = re.sub(r'^Time Team[\'s]*\s*[|:\-]+\s*', '', t, flags=re.I)
    t = re.sub(r'^TIME TEAM[\'S]*\s*[|:\-]+\s*', '', t, flags=re.I)
    t = re.sub(r'\s*[|]\s*Time Team.*$', '', t, flags=re.I)
    t = re.sub(r'\s*[|]\s*TIME TEAM.*$', '', t, flags=re.I)
    t = re.sub(r'\s*[-]\s*Time Team\s*(Podcast|News|Special|Classic)?\s*$', '', t, flags=re.I)
    t = re.sub(r'^Time Team (Commentary|Teatime|Podcast|News|Special|Classic|Plus|Digital)[: |]+', '', t, flags=re.I)
    t = re.sub(r"^Time Team's Dig Village\s+", '', t, flags=re.I)
    t = re.sub(r"^Time Team's\s+", '', t, flags=re.I)
    t = re.sub(r"^Time Team\s+", '', t, flags=re.I)
    t = re.sub(r'\s*[|]\s*Classic Special.*$', '', t, flags=re.I)
    t = re.sub(r'\s*Classic\s*\(Full Episode\s*S\d+E\d+\)', '', t, flags=re.I)
    t = re.sub(r'\s*Classic\s*\(Full Episode\)', '', t, flags=re.I)
    t = re.sub(r'\s*[-]\s*FULL EPISODE$', '', t, flags=re.I)
    t = re.sub(r'FEATURE LENGTH SPECIAL$', '', t, flags=re.I)
    t = re.sub(r'EXPEDITION CREW$', '', t, flags=re.I)
    t = re.sub(r'\s*[-]\s*BRAND NEW DIG$', '', t, flags=re.I)
    t = re.sub(r'\s*[|]\s*JOIN US on Patreon.*$', '', t, flags=re.I)
    t = re.sub(r'\s*[|+]\s*PLUS\s+.*$', '', t, flags=re.I)

    # Normalize pipes and colons to dashes
    t = t.replace(' | ', ' - ').replace('| ', '- ').replace(' |', ' -')
    t = re.sub(r':\s+', ' - ', t)
    t = re.sub(r':$', '', t)

    # Sanitize to approved characters only
    t = t.replace('&', ' and ')
    t = t.replace('–', '-').replace('—', '-')
    # Remove all unapproved punctuation
    t = re.sub(r"[',':?!#\+@%£\"\"\"'''\*…]", '', t)
    # Remove emojis and other unicode symbols
    t = re.sub(r'[^\x00-\x7F\xC0-\xFF]', '', t)  # keep ASCII + accented latin

    # Preserve years - restore any 4-digit year that was in the original
    # (years sometimes get stripped as part of longer strings)

    # Clean empty parens and artifacts
    t = re.sub(r'\s*\(\s*\)', '', t)
    t = re.sub(r'\s*-\s*-\s*', ' - ', t)
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r'^[\s\-|:]+', '', t)
    t = re.sub(r'[\s\-|:]+$', '', t)

    # Title case ALL CAPS words (2+ chars, keep known acronyms)
    acronyms = {'GPR', 'BBC', 'BTS', 'DNA', 'WWI', 'WWII', 'UK', 'BST', 'GMT', '3D', 'QA', 'II'}
    def tc(m):
        w = m.group(0)
        if w in acronyms:
            return w
        return w.title()
    t = re.sub(r'\b[A-Z]{2,}\b', tc, t)

    # Fix orphaned words from "Time Team"/"Patreon" stripping
    t = re.sub(r'^on -\s*', '', t)
    t = re.sub(r'^on\s+$', '', t)
    t = re.sub(r'^on\s+(News|Time)', r'\1', t)  # "on News" -> "News"
    t = re.sub(r'^at\s+', '', t, flags=re.I)
    t = re.sub(r'^to\s+', '', t, flags=re.I)
    t = re.sub(r'^is\s+', '', t, flags=re.I)
    t = re.sub(r'^vs\s+', '', t, flags=re.I)
    t = re.sub(r'^members\s+', '', t, flags=re.I)
    t = re.sub(r'^creator\s+', '', t, flags=re.I)
    t = re.sub(r'^episodes?\s+', '', t, flags=re.I)
    t = re.sub(r' on for ', ' for ', t)  # "on Patreon for" -> "on for" -> "for"
    t = re.sub(r'\bon\s*$', '', t)  # trailing "on"

    # Remove leftover fluff in middle of title
    t = re.sub(r'\bTime Teams?\b', '', t, flags=re.I)
    t = re.sub(r'\bNew Episode\b', '', t, flags=re.I)
    t = re.sub(r'\bBrand New\b', '', t, flags=re.I)
    t = re.sub(r'\bExclusive\b', '', t, flags=re.I)
    t = re.sub(r'\bHuge Announcement\b', '', t, flags=re.I)

    # Capitalize first letter of title
    if t and t[0].islower():
        t = t[0].upper() + t[1:]

    # Final cleanup
    t = re.sub(r'\s*-\s*-\s*', ' - ', t)
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r'^[\s\-|:]+', '', t)
    t = re.sub(r'[\s\-|:.]+$', '', t)
    t = re.sub(r'\s*\(\s*\)', '', t)

    return t.strip()


def format_filename(prefix, title, is_patreon):
    """Build final filename."""
    tag = ' [P]' if is_patreon else ' [YT]'
    name = f"{prefix} - {title}{tag}.mp4"
    # Sanitize
    name = name.replace('/', '-').replace('\\', '-')
    return name


# ─── MAIN ────────────────────────────────────────────────────────

rows = []
with open(MASTER) as f:
    rows = list(csv.DictReader(f))

# Deduplicate: same video_id in both YouTube and Patreon — keep YouTube (has subs)
from collections import Counter
id_counts = Counter(r['video_id'] for r in rows if r['video_id'])
dupe_ids = {vid for vid, count in id_counts.items() if count > 1}
deduped = []
removed = []
for row in rows:
    vid = row['video_id']
    if vid in dupe_ids and row['source'] == 'patreon':
        # Check if a YouTube version exists
        yt_exists = any(r['video_id'] == vid and r['source'] == 'youtube' for r in rows)
        if yt_exists:
            removed.append(row)
            continue
    deduped.append(row)
print(f"Deduped (same ID): removed {len(removed)} Patreon duplicates of YouTube videos")
rows = deduped

# Second dedup pass: content duplicates (same title + similar duration, different IDs)
# e.g. Patreon ad-free version vs YouTube version
from itertools import combinations
title_groups = defaultdict(list)
for row in rows:
    # Normalize title for comparison
    t = re.sub(r'\s*\[.*?\]', '', row.get('title', '')).lower().strip()
    t = re.sub(r'[^a-z0-9 ]', '', t)
    title_groups[t].append(row)

content_dupes = []
for t, group in title_groups.items():
    if len(group) <= 1 or not t:
        continue
    # Check if durations are within 10% of each other
    for a, b in combinations(group, 2):
        da = int(a.get('duration_secs', 0))
        db = int(b.get('duration_secs', 0))
        if da > 0 and db > 0 and abs(da - db) < max(da, db) * 0.1:
            # Keep YouTube version (has subs), remove Patreon
            if a['source'] == 'patreon' and b['source'] == 'youtube':
                content_dupes.append(a)
            elif b['source'] == 'patreon' and a['source'] == 'youtube':
                content_dupes.append(b)

if content_dupes:
    dupe_ids_set = {id(r) for r in content_dupes}
    rows = [r for r in rows if id(r) not in dupe_ids_set]
    print(f"Deduped (same content): removed {len(content_dupes)} content duplicates")

# Classify each file
for row in rows:
    row['target_folder'] = classify_file(row)

# Group by target folder and sort chronologically
by_folder = defaultdict(list)
for row in rows:
    by_folder[row['target_folder']].append(row)

for folder in by_folder:
    by_folder[folder].sort(key=lambda r: r.get('upload_date', '99999999'))

# Dig folders get E/X split; category folders get straight E##
DIG_FOLDERS = {f for f in by_folder.keys() if any([
    f.startswith('Dig 0') or f.startswith('Dig 1'),  # Dig 01-12 only
    f.startswith('S21'), f.startswith('S22'),
    f.startswith('S23'), f.startswith('S24'), f.startswith('Expedition'),
    f.startswith('X Crew'), f == 'Sutton Hoo',
    'Princely Burial' in f, 'Mortar Wreck' in f, 'Little Boy Blue' in f,
    'Poverty Point' in f,
    'Time Team Plus' in f,
])}

def is_episode(row):
    """Determine if a file is a main episode (E) or extra (X) for dig folders."""
    title = (row.get('title', '') + ' ' + row.get('original_filename', '')).lower()
    dur = int(row.get('duration_secs', 0))

    # Explicitly NOT episodes — always extras regardless of duration
    extra_keywords = [
        'trailer', 'teaser', 'preview', 'coming soon', 'coming up',
        'dig watch', 'site wrestle', 'spoil heap',
        'walkabout', 'walk about', 'morning brief', 'trench update',
        'behind the scenes', 'behind-the-scenes',
        'data mapping', '3d model', '360 video', '360-cam',
        'livestream', 'live stream', 'live session', 'replay',
        'announcement', 'competition', 'merch', 'merchandise',
        'flag of fame', 'first look', 'sneak peek',
        'meet the', 'meet meg', 'meet derek',
        'podcast', 'news', 'aerial tour',
        'breaking news', 'big news', 'needs you', 'help reconstruct',
        'exclusive update', 'message from', 'gets ready for',
        'extended interview', 'extended commentary',
        'post dig', 'post-dig', 'post ex',
        'q&a', 'q and a', 'answers your questions',
        'malta archive', 'just for fun',
        'mystery find', 'originals discuss',
    ]
    if any(kw in title for kw in extra_keywords):
        return False

    # Main episodes: produced dig content, 15+ min
    episode_keywords = [
        'day 1', 'day 2', 'day 3', 'day 4', 'day 5',
        'feature length', 'full episode', 'full length',
        'days 1-3', 'days 1 - 3',
        'rebuilding a legend',
        'searching for the origins', 'another buried boat',
        'lost treasure rescued', 'bromeswell bucket',
        'hidden city', 'big ancient greek',
        'mystery of the standing stone',
        'forest to front line', 'roman sarcophagus',
        'mortar wreck', 'little boy blue', 'poverty point',
        'cottage core', 'vikings', 'real northmen',
        'saving swandro', 'waterloo uncovered', 'operation cobra',
        'student dig', 'unearthing roman villa',
        'secrets beneath the giant', 'digging for disney',
        'secrets of wytch farm', 'modbury community dig',
        'band of brothers', 'boden iron age', 'broughton roman villa',
        'anglo-saxon cemetery', 'knights hospitaller',
        'geofizz challenge', 'brancaster',
        'princely burial', 'sword in the stones',
    ]
    if dur >= 900 and any(kw in title for kw in episode_keywords):
        return True

    # Feature lengths are always episodes
    if dur >= 2400 and any(kw in title for kw in ['feature', 'full', 'series 1']):
        return True

    return False

# Assign episode numbers and clean titles
results = []
for folder in sorted(by_folder.keys()):
    items = by_folder[folder]
    is_dig = folder in DIG_FOLDERS

    if is_dig:
        # Split into episodes and extras, each sorted chronologically
        episodes = [r for r in items if is_episode(r)]
        extras = [r for r in items if not is_episode(r)]

        ep_num = 1
        for row in episodes:
            title = clean_title(row.get('title', '') or row.get('original_filename', ''))
            if not title:
                title = 'Untitled'
            prefix = f"E{ep_num:02d}"
            ep_num += 1
            is_patreon = row['source'] == 'patreon'
            row['new_filename'] = format_filename(prefix, title, is_patreon)
            row['target_path'] = f"{folder}/{row['new_filename']}"
            row['content_type'] = 'episode'
            results.append(row)

        ex_num = 1
        for row in extras:
            title = clean_title(row.get('title', '') or row.get('original_filename', ''))
            if not title:
                title = 'Untitled'
            prefix = f"X{ex_num:02d}"
            ex_num += 1
            is_patreon = row['source'] == 'patreon'
            row['new_filename'] = format_filename(prefix, title, is_patreon)
            row['target_path'] = f"{folder}/{row['new_filename']}"
            row['content_type'] = 'extra'
            results.append(row)
    else:
        # Category folders: straight E## numbering
        ep = 1
        for row in items:
            title = clean_title(row.get('title', '') or row.get('original_filename', ''))

            # Classic Specials: add original air year
            if folder == 'Classic Specials':
                CLASSIC_YEARS = {
                    '1066': '2006', 'lost battlefield': '2006',
                    'bronze age mummies': '2009',
                    'castle of the saxon': '2005', 'saxon kings': '2005',
                    'boats that made': '2008',
                    'blitzkrieg': '2008', 'shooters hill': '2008',
                    'brancaster': '2013',
                    'boudica': '2011',
                    'dover castle': '2009',
                    'house in the loch': '2004', 'loch tay': '2004',
                    'journey to stonehenge': '2005', 'durrington': '2005',
                    'king of bling': '2005', 'prittlewell': '2005',
                    'lost submarines': '2013',
                    'nelson': '2010', 'haslar': '2010',
                    'rediscovering ancient': '2012',
                    'shakespeare': '2012', 'stratford': '2012',
                    'secrets of the stately': '2007', 'prior park': '2007',
                    'swords skulls': '2008', 'strongholds': '2008',
                    'god of gothic': '2007', 'pugin': '2007',
                    'real vikings': '2010',
                    'wars of the roses': '2002',
                }
                orig_title = (row.get('title', '') + ' ' + row.get('original_filename', '')).lower()
                year = None
                for kw, yr in CLASSIC_YEARS.items():
                    if kw in orig_title:
                        year = yr
                        break
                # Also check if year already in the cleaned title
                if not year:
                    yr_match = re.search(r'\b(19\d{2}|20[012]\d)\b', title)
                    if yr_match:
                        year = yr_match.group(1)
                # Also grab location from original title - between year and [videoID]
                orig = row.get('original_filename', '')
                loc_match = re.search(r'- \d{4}\s+([^[\]]+?)(?:\s*\[)', orig)
                loc = loc_match.group(1).strip().rstrip('.)') if loc_match else ''
                # Clean parens and commas from location
                loc = re.sub(r'[()]', '', loc).strip()
                loc = loc.replace(',', ' -')
                # Remove year/location already in title
                title = re.sub(r'\s*\(\d{4}[^)]*\)', '', title).strip()
                title = re.sub(r'\s*-?\s*\d{4}\s*', ' ', title).strip()
                title = re.sub(r'^-\s*', '', title).strip()
                title = re.sub(r'\s*-\s*$', '', title).strip()
                # Remove location from title if it'll be in the year suffix
                if loc:
                    title = re.sub(r'\s*-?\s*' + re.escape(loc) + r'\s*$', '', title, flags=re.I).strip()
                if year and loc:
                    title = f"{title} ({year} - {loc})"
                elif year:
                    title = f"{title} ({year})"

            # Commentary: preserve S##E## codes as prefix
            se_match = re.search(r'S(\d+)E(\d+)', row.get('title', ''), re.I)
            if se_match and folder == 'Commentary':
                prefix = f"S{int(se_match.group(1)):02d}E{int(se_match.group(2)):02d}"
                title = re.sub(r'\s*[-|]?\s*S\d+E\d+\s*[-|]?\s*', '', title, flags=re.I).strip()
                title = re.sub(r'\s*\(\s*\)', '', title)
                title = re.sub(r'^[\s\-|:]+', '', title)
                title = re.sub(r'[\s\-|:]+$', '', title)
            else:
                # Everything else: straight E## chronological
                prefix = f"E{ep:02d}"
                ep += 1

            if not title:
                title = 'Untitled'

            is_patreon = row['source'] == 'patreon'
            row['new_filename'] = format_filename(prefix, title, is_patreon)
            row['target_path'] = f"{folder}/{row['new_filename']}"
            row['content_type'] = 'episode'
            results.append(row)

# ─── Post-process all results for final cleanup ─────────────────
for row in results:
    n = row['new_filename']
    # Extract title portion (between "E## - " and " [YT].mp4")
    m = re.match(r'^([EXS]\d+[E]?\d* - )(.*?)( \[(YT|P)\]\.mp4)$', n)
    if not m:
        continue
    prefix_part, title, tag_part = m.group(1), m.group(2), m.group(3)

    # Fix bare timestamps and too-short titles
    if re.match(r'^\d{3,4}$', title):
        title = f'Dig Watch {title}'
    if re.match(r'^\d+[ap]m$', title, re.I):
        title = f'Dig Watch {title}'
    if title.lower() in ('news', 'podcast', 'on', 'at', 'the'):
        title = f'Preview - {title}'

    # Fix orphaned parens
    title = re.sub(r'\(\s+', '(', title)
    title = re.sub(r'\s+\)', ')', title)
    title = re.sub(r'\(\s*\)', '', title)

    # Capitalize first letter
    if title and title[0].islower():
        title = title[0].upper() + title[1:]

    # Truncate overly long titles
    if len(title) > 80:
        title = title[:77]
        title = re.sub(r'\s+\S*$', '', title)  # break at word boundary

    # Final double-space and dash cleanup
    title = re.sub(r'  +', ' ', title)
    title = re.sub(r' - - ', ' - ', title)
    title = re.sub(r'^[\s\-]+', '', title)
    title = re.sub(r'[\s\-]+$', '', title)

    if not title:
        title = 'Untitled'

    row['new_filename'] = f"{prefix_part}{title}{tag_part}"
    row['target_path'] = f"{row['target_folder']}/{row['new_filename']}"

# ─── Write review document ──────────────────────────────────────

with open(REVIEW_OUT, 'w') as f:
    f.write("TIME TEAM LIBRARY REORGANIZATION - REVIEW DOCUMENT\n")
    f.write("=" * 80 + "\n")
    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    f.write(f"Total files: {len(results)}\n")
    f.write(f"Target folders: {len(by_folder)}\n\n")

    # Summary table
    f.write("FOLDER SUMMARY\n")
    f.write("-" * 80 + "\n")
    for folder in sorted(by_folder.keys()):
        items = [r for r in results if r['target_folder'] == folder]
        total_mins = sum(int(r.get('duration_secs', 0)) for r in items) // 60
        total_mb = sum(float(r.get('size_mb', 0)) for r in items)
        eps = sum(1 for r in items if r.get('content_type') == 'episode')
        exs = sum(1 for r in items if r.get('content_type') == 'extra')
        is_dig = folder in DIG_FOLDERS
        if is_dig:
            f.write(f"  {len(items):3d} files  {total_mins:4d} min  {total_mb/1024:5.1f} GB  "
                    f"(E:{eps} X:{exs})  {folder}\n")
        else:
            f.write(f"  {len(items):3d} files  {total_mins:4d} min  {total_mb/1024:5.1f} GB  "
                    f"          {folder}\n")

    f.write("\n\n")

    # Detailed per-folder listing
    for folder in sorted(by_folder.keys()):
        items = by_folder[folder]
        f.write(f"{'━' * 3} {folder} ({len(items)} files) {'━' * 3}\n\n")

        for row in items:
            old = row['original_filename']
            new = row['new_filename']
            date = row.get('upload_date', '')
            dur = row.get('duration', '')
            src = 'P' if row['source'] == 'patreon' else 'Y'
            old_folder = row['folder']

            # Truncate for readability
            if len(old) > 75:
                old = old[:72] + '...'
            if len(new) > 75:
                new = new[:72] + '...'

            f.write(f"  [{src}] {date}  {dur:>6s}  FROM: {old_folder}\n")
            f.write(f"  OLD: {old}\n")
            f.write(f"  NEW: {new}\n\n")

        f.write("\n")

# ─── Write mapping CSV ──────────────────────────────────────────

with open(MAPPING_OUT, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['old_folder', 'old_filename', 'target_folder', 'new_filename',
                'source', 'upload_date', 'duration', 'size_mb', 'video_id'])
    for row in results:
        w.writerow([
            row['folder'], row['original_filename'],
            row['target_folder'], row['new_filename'],
            row['source'], row['upload_date'],
            row['duration'], row['size_mb'], row['video_id']
        ])

print(f"Review document: {REVIEW_OUT}")
print(f"Mapping CSV: {MAPPING_OUT}")
print(f"Total: {len(results)} files -> {len(by_folder)} folders")
print()
print("Top folders:")
for folder in sorted(by_folder.keys(), key=lambda f: -len(by_folder[f]))[:15]:
    print(f"  {len(by_folder[folder]):3d}  {folder}")
