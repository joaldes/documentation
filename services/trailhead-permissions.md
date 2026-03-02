# Trailhead — Per-User Bookmarks via Authentik SSO

**Last Updated**: 2026-03-01
**Status**: Implemented and deployed
**Related Systems**: Trailhead (192.168.0.179:8076), Authentik (192.168.0.179:9000)

## Summary

Added per-user bookmark filtering to the Trailhead weather dashboard using Authentik SSO forward auth. Each user sees only the bookmarks assigned to their role. The main content (weather, charts, birds, sky, park, synopsis) is identical for all users. Static HTML files are pre-generated per role every 5 minutes, with nginx serving the correct file based on the authenticated username.

## Architecture

```
Browser → trailhead-web (:8076)
  nginx auth_request → Authentik embedded outpost (192.168.0.179:9000)
    401 → redirect to Authentik login page
    200 → auth_request_set captures $authentik_username
         → map $authentik_username → $user_role
         → try_files /$user_role.html (fallback: media.html)
```

## Roles

| Role | Bookmarks | Users |
|------|-----------|-------|
| admin | All 36 | alec, akadmin |
| apps | Manyfold, Reyday, Sander, Stirling PDF | (assign in nginx map) |
| media_request | Emby, Jellyseerr | (assign in nginx map) |
| media | Emby | default for unknown users |

User-to-role mapping lives **only** in the nginx map block in `nginx.conf` (single source of truth).

## Authentik Configuration

Configured via API. Components created:

- **Proxy Provider**: `trailhead` — forward auth single application, external host `http://192.168.0.179:8076`
- **Application**: `Trailhead`, slug `trailhead`
- **Embedded outpost**: Trailhead provider assigned
- **Users**: `alec` (password: `password` — change via Authentik admin), `akadmin` (default admin)

To add a new user:
1. Create user in Authentik admin: http://192.168.0.179:9000/if/admin/#/identity/users
2. Add username to nginx map in `/mnt/docker/trailhead/nginx.conf`
3. Reload nginx: `docker exec trailhead-web nginx -s reload`

## Files Modified

All files live in `/mnt/docker/trailhead/` on Komodo (192.168.0.179).

| File | Change |
|------|--------|
| `trailhead.yaml` | **New** — all 36 bookmarks in 4 groups + 4 role definitions |
| `generate.py` | Added `import yaml`, `filter_bookmarks()`, per-role HTML render loop. Removed dead UV/AQI code. |
| `template.html` | Replaced 36 hardcoded bookmark cards with Jinja loop. Added logout link. Removed `.status-pill` CSS. |
| `nginx.conf` | Complete rewrite for Authentik forward auth |
| `requirements.txt` | Added `pyyaml==6.0.2` |
| `Dockerfile` | Added `COPY trailhead.yaml` |
| `compose.yaml` | Healthcheck changed from `index.html` to `admin.html` |

## nginx.conf — Key Details

```nginx
map $authentik_username $user_role {
    default    media;
    alec       admin;
    akadmin    admin;
}
```

Critical deployment fixes discovered during implementation:

- **`absolute_redirect off`** — Required because nginx inside Docker listens on :80 but is exposed as :8076. Without this, redirects go to port 80 and break.
- **`Host 192.168.0.179:8076`** (hardcoded in outpost location) — The Authentik outpost routes by host matching. Using `$host` would fail when the request arrives with `localhost:8076` or other variants.
- **Cookie passthrough** — `auth_request_set $auth_cookie` + `add_header Set-Cookie $auth_cookie` on every auth-protected location. Without this, Authentik's session cookie is discarded and users get an infinite login loop.
- **`$authentik_username` from `$upstream_http_x_authentik_username`** — Reads from the outpost's response headers, NOT the client request headers. Cannot be spoofed.

## generate.py — Per-Role Rendering

```python
def filter_bookmarks(groups, allowed):
    if allowed == 'all':
        return groups
    filtered = []
    for group in groups:
        cards = [c for c in group['cards'] if c['id'] in allowed]
        if cards:
            filtered.append({**group, 'cards': cards})
    return filtered
```

Renders one HTML file per role: `admin.html` (36 cards), `apps.html` (4), `media_request.html` (2), `media.html` (1). No `index.html` is generated.

## Security

- **Header spoofing safe**: `$authentik_username` comes from `$upstream_http_` (outpost response only)
- **Direct file access safe**: `try_files` uses `$user_role` from the map, not the request URI. Requesting `/admin.html` directly still serves your role's file.
- **Static assets protected**: Camera snapshot (`driveway.jpg`) requires auth
- **Default least-privilege**: Unknown authenticated users get `media` role (Emby only)
- **Health check open**: `/health` has no auth (required for Docker healthcheck)

## Troubleshooting

### User sees wrong bookmarks
Check which username Authentik is sending. The nginx map in `nginx.conf` controls role assignment. Add/change the username→role mapping there and reload nginx.

### Infinite login loop
Cookie passthrough is missing or broken. Ensure `auth_request_set $auth_cookie $upstream_http_set_cookie` and `add_header Set-Cookie $auth_cookie` are present on every auth-protected location block.

### 502 or 500 errors
Authentik may be down or the outpost may not have the provider assigned. Check:
```bash
docker logs authentik-server --tail 20
curl -s -o /dev/null -w '%{http_code}' -H 'Host: 192.168.0.179:8076' http://192.168.0.179:9000/outpost.goauthentik.io/auth/nginx
# Should return 401 (unauthenticated) or 200 (authenticated)
```

### Adding a new user
1. Authentik admin → create user with password
2. Add to nginx map: `username    role;`
3. `docker exec trailhead-web nginx -s reload`

### Regenerating HTML after config change
Edit `trailhead.yaml`, rebuild generator: `cd /mnt/docker/trailhead && docker compose build generator && docker compose up -d generator`
