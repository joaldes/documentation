#!/bin/bash
# Time Team Complete Downloader
# Downloads ALL videos from Time Team Official YouTube channel
# Organizes into Emby-friendly folder structure

set -euo pipefail
export PATH="$HOME/.deno/bin:$HOME/.local/bin:$PATH"

BASE_DIR="/mnt/hometheater/Time Team YouTube"
LOG_FILE="$BASE_DIR/download-log.txt"
ARCHIVE_FILE="$BASE_DIR/.downloaded_ids"
VIDEO_LIST="$BASE_DIR/video-list.txt"

# Create folder structure
mkdir -p "$BASE_DIR/Classic Specials"
mkdir -p "$BASE_DIR/S21 - Boden Fogou (Cornwall)"
mkdir -p "$BASE_DIR/S21 - Broughton Roman Villa (Oxfordshire)"
mkdir -p "$BASE_DIR/S21 - Feature Length"
mkdir -p "$BASE_DIR/S22 - Knights Hospitaller"
mkdir -p "$BASE_DIR/S22 - Anglo-Saxon Cemetery (Norfolk)"
mkdir -p "$BASE_DIR/S22 - Feature Length"
mkdir -p "$BASE_DIR/S23 - Band of Brothers"
mkdir -p "$BASE_DIR/S23 - Wytch Farm (Dorset)"
mkdir -p "$BASE_DIR/S23 - Modbury (Devon)"
mkdir -p "$BASE_DIR/S23 - Feature Length"
mkdir -p "$BASE_DIR/S24 - Norton Disney"
mkdir -p "$BASE_DIR/S24 - Cerne Abbas (Dorset)"
mkdir -p "$BASE_DIR/S24 - Brancaster (Norfolk)"
mkdir -p "$BASE_DIR/Specials"
mkdir -p "$BASE_DIR/Sutton Hoo"
mkdir -p "$BASE_DIR/X Crew"
mkdir -p "$BASE_DIR/Expedition Crew"
mkdir -p "$BASE_DIR/Time Team Plus"
mkdir -p "$BASE_DIR/Teatime"
mkdir -p "$BASE_DIR/Time Team News"
mkdir -p "$BASE_DIR/Interviews"
mkdir -p "$BASE_DIR/Commentary"
mkdir -p "$BASE_DIR/Behind the Scenes"
mkdir -p "$BASE_DIR/Dig Watch Clips"
mkdir -p "$BASE_DIR/Dig Village Masterclass"
mkdir -p "$BASE_DIR/Podcasts"
mkdir -p "$BASE_DIR/Promos"
mkdir -p "$BASE_DIR/Patreon Exclusive"

# Initialize log
if [ ! -f "$LOG_FILE" ]; then
    echo "Time Team Download Log" > "$LOG_FILE"
    echo "Created: $(date)" >> "$LOG_FILE"
    echo "========================================" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
fi

# Initialize archive file
touch "$ARCHIVE_FILE"

# Function to determine output folder based on title
get_folder() {
    local title="$1"
    local ltitle=$(echo "$title" | tr '[:upper:]' '[:lower:]')

    # Classic Specials (rereleased full classic episodes)
    if echo "$ltitle" | grep -q "classic special"; then
        echo "Classic Specials"
        return
    fi

    # S21 - Boden Fogou
    if echo "$ltitle" | grep -q "boden.*fogou\|boden iron age\|iron age settlement in cornwall"; then
        if echo "$ltitle" | grep -q "feature length"; then
            echo "S21 - Feature Length"
        else
            echo "S21 - Boden Fogou (Cornwall)"
        fi
        return
    fi

    # Roman Sarcophagus (Expedition Crew at Broughton) - MUST be before Broughton Villa
    if echo "$ltitle" | grep -q "roman sarcophagus\|return to broughton"; then
        echo "Expedition Crew"
        return
    fi

    # S21 - Broughton Roman Villa
    if echo "$ltitle" | grep -q "broughton.*villa\|broughton.*oxfordshire\|dig 2.*roman villa\|roman villa.*dig 2\|dig two.*oxfordshire\|new dig 2"; then
        if echo "$ltitle" | grep -q "feature length"; then
            echo "S21 - Feature Length"
        else
            echo "S21 - Broughton Roman Villa (Oxfordshire)"
        fi
        return
    fi

    # S22 - Knights Hospitaller
    if echo "$ltitle" | grep -q "knights hospitaller"; then
        if echo "$ltitle" | grep -q "feature length"; then
            echo "S22 - Feature Length"
        else
            echo "S22 - Knights Hospitaller"
        fi
        return
    fi

    # S22 - Anglo-Saxon Cemetery
    if echo "$ltitle" | grep -q "anglo-saxon cemetery\|winfarthing"; then
        if echo "$ltitle" | grep -q "feature length"; then
            echo "S22 - Feature Length"
        else
            echo "S22 - Anglo-Saxon Cemetery (Norfolk)"
        fi
        return
    fi

    # S23 - Band of Brothers / Operation Nightingale / Aldbourne
    if echo "$ltitle" | grep -q "band of brothers\|operation nightingale\|aldbourne"; then
        echo "S23 - Band of Brothers"
        return
    fi

    # S23 - Wytch Farm
    if echo "$ltitle" | grep -q "wytch farm"; then
        if echo "$ltitle" | grep -q "feature length"; then
            echo "S23 - Feature Length"
        else
            echo "S23 - Wytch Farm (Dorset)"
        fi
        return
    fi

    # S23 - Modbury
    if echo "$ltitle" | grep -q "modbury"; then
        if echo "$ltitle" | grep -q "feature length"; then
            echo "S23 - Feature Length"
        else
            echo "S23 - Modbury (Devon)"
        fi
        return
    fi

    # S24 - Norton Disney
    if echo "$ltitle" | grep -q "norton disney\|digging for disney"; then
        echo "S24 - Norton Disney"
        return
    fi

    # S24 - Cerne Abbas
    if echo "$ltitle" | grep -q "cerne abbas"; then
        echo "S24 - Cerne Abbas (Dorset)"
        return
    fi

    # S24 - Brancaster / Geofizz / Branodunum / Mapperton
    if echo "$ltitle" | grep -q "brancaster\|geofizz\|branodunum\|mapperton"; then
        if echo "$ltitle" | grep -q "full episode.*s[0-9]\+e[0-9]"; then
            echo "Classic Specials"
        else
            echo "S24 - Brancaster (Norfolk)"
        fi
        return
    fi

    # Sutton Hoo
    if echo "$ltitle" | grep -q "sutton hoo"; then
        echo "Sutton Hoo"
        return
    fi

    # X Crew / Vlochos / Greek dig
    if echo "$ltitle" | grep -q "x crew\|x-crew\|vlochos\|greek dig"; then
        echo "X Crew"
        return
    fi

    # Expedition Crew / Sherwood Pines
    if echo "$ltitle" | grep -q "expedition crew\|hidden city\|mortar wreck.*crew\|sherwood pines\|forest to front"; then
        echo "Expedition Crew"
        return
    fi

    # Time Team Plus
    if echo "$ltitle" | grep -q "time team plus\|saving swandro\|waterloo uncovered\|operation cobra\|student dig"; then
        echo "Time Team Plus"
        return
    fi

    # Dig Watch Clips (short on-site updates with TT-## or TT ## codes, dig watch day clips)
    if echo "$ltitle" | grep -q "^tt-[0-9]\|^tt [0-9]\|^tt - [0-9]\|^tt d[0-9]\|^tt- [0-9]\|^tt- d\|^d[0-9].*trench\|^d7 \|^day [0-9].*time lapse\|^day [0-9].*breaking\|trench update\|trench 1 extension\|trench phil\|geophys overlay\|^timelapse\|^time lapse day\|morning.*brief\|morning.*strategy\|^tracey\|^cassie$\|^alison.*deborah\|^jimmy day\|^ian.*vlog\|^ian.*coin\|^alex langlands\|^mat vlog\|^little ian\|^phil.*pub\|^phil.*box\|^phil.*scan\|^phil.*lithics\|^phil.*spade\|^phil.*jacket\|^phils intro\|^mick talk\|^mick on\|^mick.*tim.*phil\|^paul.*pottery\|^paul.*community\|^paul on \|^kate.*lithics\|^naomi on\|^mary-ann\|^tim.*intro\|^tim.*wrap\|^tims intro\|^test pit\|^end of dig\|^lord of the trowel\|bag of plenty\|fleece of the lamb\|^what.*in phil\|mickmobile\|dig watch.*back\|dig watch.*join\|dig watch.*this\|dig watch.*meet\|^s19 e[0-9]\|^a stroll\|^a chat with kerry\|raksha.*tool\|raksha.*new\|lifelong friend\|jimmy.*magnetometer\|matt.*wall.*quandary\|^trench 3$\|starting trench\|deciding where\|plotting out"; then
        echo "Dig Watch Clips"
        return
    fi

    # Dig Village Masterclass
    if echo "$ltitle" | grep -q "masterclass\|dig village\|stuck at home"; then
        echo "Dig Village Masterclass"
        return
    fi

    # Classic full episodes (not already caught as specials)
    if echo "$ltitle" | grep -q "full episode.*s[0-9]\+e[0-9]"; then
        echo "Classic Specials"
        return
    fi

    # Podcasts
    if echo "$ltitle" | grep -q "podcast\|christmas quiz"; then
        echo "Podcasts"
        return
    fi

    # Teatime series
    if echo "$ltitle" | grep -q "teatime"; then
        echo "Teatime"
        return
    fi

    # Time Team News
    if echo "$ltitle" | grep -q "time team news\|best of.*news\|archaeology news\|amazing.*archaeology\|dazzling discoveries\|incredible.*discoveries.*news\|epic finds.*lost worlds"; then
        echo "Time Team News"
        return
    fi

    # Commentary (episode commentaries and Q&As on specific episodes)
    if echo "$ltitle" | grep -q "commentary.*s[0-9]\|q&a on.*series\|q&a on.*s[0-9]\|q&a on fetlar\|john gater.*syon\|john gater.*element"; then
        echo "Commentary"
        return
    fi

    # Interviews (author/expert interviews)
    if echo "$ltitle" | grep -q "meets time team\|interview\|in conversation\|tony robinson.*memories\|tony robinson.*best\|victor ambrus\|kate mosse\|philippa gregory\|bernard cornwell\|robert harris\|neil macgregor\|john preston\|philip reeve\|morpurgo\|ken follett\|suzannah lipscomb\|natalie haynes\|cat jarman\|miles russell\|helena hamerow\|henry chapman\|gabor thomas\|david jacques\|guy de la\|jonathan foyle\|neil emmanuel\|raysan\|kerry ely\|matt williams.*digger\|stewart ainsworth.*rivers\|blick mead\|saxon queen\|stonehenge discovery\|eanswythe"; then
        echo "Interviews"
        return
    fi

    # Behind the Scenes (previews, aftershows, announcements, compilations, best-of)
    if echo "$ltitle" | grep -q "first look\|aftershow\|big dome\|best moments\|assemble\|books of year\|mindful\|wellbeing\|2022 in archaeology\|world cup.*football\|year ahead\|vision 2024\|2021 in archaeology\|new presenters\|10 amazing\|5 amazing\|dig countdown\|time team digital\|incredible.*discoveries.*compilation\|best of 202\|year of incredible\|2025.*year\|meet the.*inspiring\|geophys.*understand\|amazing new geophys\|syon house.*geophys\|how geophysics"; then
        echo "Behind the Scenes"
        return
    fi

    # New era specials
    if echo "$ltitle" | grep -q "time team special\|mortar wreck\|bringing home\|princely burial\|little boy blue\|poverty point\|cottage core\|vikings.*real\|mary rose\|battle.*north gate\|phil harding.*present\|fossils.*finds\|virtual dartmoor\|musing on mosaics\|archaeology tour\|farmhouse.*archaeology\|incredible historic\|horrible histories"; then
        echo "Specials"
        return
    fi

    # Promos (merch, membership, announcements, short ads)
    if echo "$ltitle" | grep -q "merchandise\|merch\|flag of fame\|membership\|black friday\|name.*bus\|pimp tony\|save on\|competition\|help us bring\|are you ready\|get involved\|announcement\|exclusive.*news\|exclusive.*chat\|exclusive.*celebrate\|exclusive.*carenza\|join time team\|join the team\|welcome to time team\|channel trailer\|why should\|what was time team\|more time team\|coming soon\|teaser\|trailer\|premieres\|time with tim\|tony.*club\|tony\.mov\|^6pm\|^10:30\|^10:40\|^11:00\|^16:00\|wall of fame\|newsletter\|sign up\|site contenders\|new.*site.*details\|help us develop\|message from tim\|rip peter green\|remembrance sunday\|secret santa\|christmas\|dig school\|time team games\|volunteer.*time team\|carenza.*answers\|few questions answered\|phil needs"; then
        echo "Promos"
        return
    fi

    # Catch-all for anything remaining
    echo "Specials"
}

# Download each video
TOTAL=$(wc -l < "$VIDEO_LIST")
COUNT=0
SUCCESS=0
SKIPPED=0
FAILED=0

echo "" >> "$LOG_FILE"
echo "Download session: $(date)" >> "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"

while IFS= read -r line; do
    vid_id=$(echo "$line" | awk -F';;;' '{print $1}')
    title=$(echo "$line" | awk -F';;;' '{print $2}')
    duration=$(echo "$line" | awk -F';;;' '{print $3}')
    COUNT=$((COUNT + 1))

    # Skip if already downloaded
    if grep -q "^$vid_id$" "$ARCHIVE_FILE" 2>/dev/null; then
        echo "[$COUNT/$TOTAL] SKIP (already downloaded): $title"
        echo "  SKIPPED | $vid_id | $title" >> "$LOG_FILE"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    FOLDER=$(get_folder "$title")
    OUTPUT_DIR="$BASE_DIR/$FOLDER"
    mkdir -p "$OUTPUT_DIR"

    echo "[$COUNT/$TOTAL] Downloading to '$FOLDER': $title"

    if yt-dlp \
        -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best" \
        --merge-output-format mp4 \
        --write-auto-subs \
        --sub-langs "en" \
        --convert-subs srt \
        --embed-metadata \
        --no-overwrites \
        -o "$OUTPUT_DIR/%(title)s [%(id)s].%(ext)s" \
        "https://www.youtube.com/watch?v=$vid_id" 2>&1; then

        echo "$vid_id" >> "$ARCHIVE_FILE"
        echo "  SUCCESS | $vid_id | $FOLDER | $title" >> "$LOG_FILE"
        SUCCESS=$((SUCCESS + 1))
    else
        echo "  FAILED  | $vid_id | $FOLDER | $title" >> "$LOG_FILE"
        FAILED=$((FAILED + 1))
        echo "  *** FAILED: $title"
    fi

    # Small delay to be polite to YouTube
    sleep 2
done < "$VIDEO_LIST"

# Summary
SUMMARY="
========================================
Session complete: $(date)
Total: $TOTAL | Downloaded: $SUCCESS | Skipped: $SKIPPED | Failed: $FAILED
========================================"

echo "$SUMMARY" >> "$LOG_FILE"
echo "$SUMMARY"
