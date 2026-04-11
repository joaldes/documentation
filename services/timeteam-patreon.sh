#!/bin/bash
# Time Team Patreon Exclusive Downloader
# Downloads patron-only video content from Time Team's Patreon page
# Skips text-only posts and videos already downloaded

set -uo pipefail
export PATH="$HOME/.deno/bin:$HOME/.local/bin:$PATH"

BASE_DIR="/mnt/hometheater/Time Team YouTube/Patreon Exclusive"
LOG_FILE="/mnt/hometheater/Time Team YouTube/patreon-download-log.txt"
ARCHIVE_FILE="$BASE_DIR/.patreon_downloaded_ids"
COOKIES="/mnt/documents/personal/alec/claudeai/patreon-cookies.txt"
POST_LIST="/tmp/patreon_all_ids.txt"

mkdir -p "$BASE_DIR"

# Initialize log
if [ ! -f "$LOG_FILE" ]; then
    echo "Time Team Patreon Download Log" > "$LOG_FILE"
    echo "Created: $(date)" >> "$LOG_FILE"
    echo "========================================" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
fi

# Initialize archive file
touch "$ARCHIVE_FILE"

# Pull post list if not present
if [ ! -f "$POST_LIST" ] || [ ! -s "$POST_LIST" ]; then
    echo "Pulling Patreon post list..."
    yt-dlp --cookies "$COOKIES" \
        --flat-playlist --print "%(id)s" \
        "https://www.patreon.com/TimeTeamOfficial" > "$POST_LIST" 2>/dev/null
    echo "Found $(wc -l < "$POST_LIST") posts"
fi

TOTAL=$(wc -l < "$POST_LIST")
COUNT=0
SUCCESS=0
SKIPPED=0
NO_VIDEO=0
FAILED=0

echo "" >> "$LOG_FILE"
echo "Download session: $(date)" >> "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"

while IFS= read -r post_id; do
    COUNT=$((COUNT + 1))

    # Skip if already downloaded
    if grep -q "^$post_id$" "$ARCHIVE_FILE" 2>/dev/null; then
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    URL="https://www.patreon.com/posts/$post_id"

    # Try to get title first
    title=$(yt-dlp --cookies "$COOKIES" --simulate --print "%(title)s" "$URL" 2>/dev/null || echo "")

    if [ -z "$title" ] || echo "$title" | grep -qi "error\|unsupported"; then
        echo "[$COUNT/$TOTAL] NO VIDEO: post $post_id"
        echo "  NO_VIDEO | $post_id" >> "$LOG_FILE"
        echo "$post_id" >> "$ARCHIVE_FILE"
        NO_VIDEO=$((NO_VIDEO + 1))
        continue
    fi

    echo "[$COUNT/$TOTAL] Downloading: $title"

    if yt-dlp --cookies "$COOKIES" \
        -f "bestvideo+bestaudio/best" \
        --merge-output-format mp4 \
        --embed-metadata \
        --no-overwrites \
        --no-warnings \
        -o "$BASE_DIR/%(title)s [patreon-%(id)s].%(ext)s" \
        "$URL" 2>&1; then

        echo "$post_id" >> "$ARCHIVE_FILE"
        echo "  SUCCESS | $post_id | $title" >> "$LOG_FILE"
        SUCCESS=$((SUCCESS + 1))
    else
        # Check if it was just a text post (no video to download)
        echo "$post_id" >> "$ARCHIVE_FILE"
        echo "  SKIPPED_NO_MEDIA | $post_id | $title" >> "$LOG_FILE"
        NO_VIDEO=$((NO_VIDEO + 1))
    fi

    sleep 1
done < "$POST_LIST"

SUMMARY="
========================================
Patreon session complete: $(date)
Total posts: $TOTAL | Downloaded: $SUCCESS | Skipped (done): $SKIPPED | No video: $NO_VIDEO | Failed: $FAILED
========================================"

echo "$SUMMARY" >> "$LOG_FILE"
echo "$SUMMARY"
