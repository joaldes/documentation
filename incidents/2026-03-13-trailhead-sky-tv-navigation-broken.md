# Trailhead: Sky Events & TV Calendar Pages Not Loading

**Last Updated**: 2026-03-13
**Related Systems**: Komodo (CT 128), Trailhead Dashboard (192.168.0.179:8076)

## Summary

The Sky Events (`/sky`) and TV Calendar (`/tv`) pages stopped loading — clicking them in the sidebar refreshed the homepage instead. Root cause was a URL mismatch between `trailhead.yaml` bookmark URLs (`/sky.html`, `/tv.html`) and the nginx location regex which only matched `/sky` and `/tv`. Fixed by updating the nginx regex to accept both forms. This is a recurring issue — the yaml URLs had been corrected before but reverted during a later edit.

## Problem

Clicking "Sky Events" or "TV Calendar" in the Trailhead sidebar appeared to reload the homepage. No error was shown — the pages silently served `index.html` instead of `sky.html` or `tv.html`.

**Root cause**: The nginx config had a regex location block:
```nginx
location ~ ^/(sky|tv)$ {
    try_files /$1.html =404;
}
```

The bookmark URLs in `trailhead.yaml` were set to `/sky.html` and `/tv.html`. These didn't match `^/(sky|tv)$` — they fell through to `location /` which has `try_files /index.html =404`, silently serving the homepage.

## Solution

### Immediate fix
Corrected `trailhead.yaml` URLs from `/sky.html` → `/sky` and `/tv.html` → `/tv`. Required a generator container restart (bind mount didn't reflect changes without restart).

### Permanent fix
Updated the nginx regex to accept both URL forms so the yaml URLs don't matter:

```nginx
# Before
location ~ ^/(sky|tv)$ {

# After
location ~ ^/(sky|tv)(\.html)?$ {
```

Now `/sky`, `/sky.html`, `/tv`, and `/tv.html` all route correctly. The `$1` capture still resolves to `sky` or `tv` for the `try_files` directive.

## Implementation Details

### Steps Performed
1. Diagnosed by checking nginx response codes — `/tv.html` returned `index.html` content
   ```bash
   docker exec trailhead-web curl -s -o /dev/null -w '%{http_code}' http://localhost/tv.html
   # 302 → auth redirect, but after auth, served index.html (wrong page)
   ```

2. Fixed `trailhead.yaml` bookmark URLs (immediate fix)
   ```bash
   sed -i 's|url: /sky.html|url: /sky|;s|url: /tv.html|url: /tv|' /mnt/docker/trailhead/trailhead.yaml
   docker restart trailhead-generator
   ```

3. Updated nginx regex to accept `.html` extension (permanent fix)
   ```bash
   # Line 81 of /mnt/docker/trailhead/nginx.conf
   # ^/(sky|tv)$  →  ^/(sky|tv)(\.html)?$
   docker restart trailhead-web
   ```

### Key Files Modified
- `/mnt/docker/trailhead/trailhead.yaml` — bookmark URLs corrected (`/sky.html` → `/sky`, `/tv.html` → `/tv`)
- `/mnt/docker/trailhead/nginx.conf` — location regex updated to accept optional `.html` extension

## Verification
```bash
# All four should return 302 (auth redirect to correct page)
docker exec trailhead-web curl -s -o /dev/null -w '%{http_code}' http://localhost/tv
docker exec trailhead-web curl -s -o /dev/null -w '%{http_code}' http://localhost/tv.html
docker exec trailhead-web curl -s -o /dev/null -w '%{http_code}' http://localhost/sky
docker exec trailhead-web curl -s -o /dev/null -w '%{http_code}' http://localhost/sky.html
```

## Lesson Learned
When nginx uses a regex to strip extensions and serve files (`try_files /$1.html`), the regex must accept both forms of the URL. Otherwise, any upstream config that references the natural filename breaks silently — no 404, no error, just the wrong page served.
