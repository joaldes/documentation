# Immich Frozen UI / "Server Offline"

**Last Updated**: 2026-03-08
**Related Systems**: Container 128 (Komodo), Immich, NPM (Container 112)

## Summary
Immich web UI was completely unresponsive — page loaded but showed "server offline," no photos displayed, and nothing was clickable. Root cause was a frontend bug in the outdated v2.2.3. Resolved by upgrading to v2.5.6.

## Problem
- Immich web UI at 192.168.0.179:2283 loaded HTML but the JavaScript froze the page
- "Server offline" message displayed despite the backend being fully operational
- No photos or thumbnails loaded, UI elements unclickable
- Issue persisted in incognito/private browsing windows
- All 5 Immich containers reported healthy, API responded correctly to curl

## Investigation
1. Verified all containers running and healthy (5 days uptime)
2. Confirmed API endpoints working (`/api/server/ping` → 200, `/api/server/version` → 200)
3. Database healthy — 145,882 assets, 3 users, 2 GB database size
4. Disk space adequate (7.2 TB free on pictures mount)
5. Resource usage normal across all services
6. Ruled out IPv6 binding issue — server was correctly bound to `::` (all interfaces), the `[::1]` in logs was a cosmetic bug in v2.2.3
7. Frontend JS assets served correctly (HTTP 200, correct file sizes)
8. No CORS issues detected
9. Concluded: frontend JavaScript bug in v2.2.3 causing page freeze, likely triggered by data volume (145K+ assets) or corrupt file processing

## Solution
Upgraded Immich from v2.2.3 (November 2025) to v2.5.6 (latest stable). Direct upgrade path confirmed safe — no intermediate version stops required, no breaking changes.

### Steps Performed
1. Updated version in environment file
   ```bash
   ssh claude@192.168.0.151 "sudo pct exec 128 -- sed -i 's/IMMICH_VERSION=v2.2.3/IMMICH_VERSION=v2.5.6/' /etc/komodo/stacks/immich/.env"
   ```

2. Pulled new images
   ```bash
   ssh claude@192.168.0.151 "sudo pct exec 128 -- bash -c 'cd /etc/komodo/stacks/immich && docker compose pull'"
   ```

3. Restarted the stack
   ```bash
   ssh claude@192.168.0.151 "sudo pct exec 128 -- bash -c 'cd /etc/komodo/stacks/immich && docker compose up -d'"
   ```

4. All 5 containers recreated and started successfully
5. Database migrations and geodata import ran automatically on first startup

### Key Files Modified
- `/etc/komodo/stacks/immich/.env` — changed `IMMICH_VERSION=v2.2.3` to `IMMICH_VERSION=v2.5.6`

## Verification
- API returns v2.5.6: `curl -s http://192.168.0.179:2283/api/server/version`
- Web UI loads and is interactive
- No errors in server or microservices logs post-upgrade
- Photos load and display correctly

## Troubleshooting
- **If UI freezes again after future updates**: Check browser DevTools console for JS errors, try incognito, and consider upgrading to latest version
- **"Server offline" with working API**: Usually a frontend/browser issue, not backend. Check websocket connectivity and browser cache
- **Slow startup after upgrade**: Normal — database migrations and geodata imports run on first boot. Allow 2-5 minutes.

## Lessons Learned
- Immich v2.2.3's `[::1]` binding log message is cosmetic — verify actual binding via `/proc/net/tcp6` before assuming a network issue
- Backend health checks (container status, API curl, database queries) can all pass while the frontend is completely broken
- Don't let Immich fall too far behind on versions — 4+ months of missed updates led to this issue
