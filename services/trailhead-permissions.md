# Trailhead — Per-User Access Control via Authentik SSO

**Last Updated**: 2026-03-03
**Status**: Implemented and deployed
**Related Systems**: Trailhead (192.168.0.179:8076), Authentik (192.168.0.179:9000)

## Summary

Per-user access filtering on the Trailhead weather dashboard using Authentik SSO forward auth. A single `index.html` is generated every 5 minutes with ALL cards. Client-side JavaScript filters cards based on the authenticated user's group memberships. The main content (weather, charts, birds, sky, park, synopsis) is identical for all users. The sidebar supports multiple tabs (Bookmarks, Cameras) with per-card group-based access control.

## Architecture

```
Browser → NPM (192.168.0.30) → trailhead-web (:8076)
  nginx auth_request → Authentik embedded outpost (192.168.0.179:9000)
    401 → redirect to http://home.1701.me/outpost.goauthentik.io/start (hardcoded domain)
    200 → auth_request_set captures $authentik_username
         → sub_filter injects username into TWO placeholders (dropdown + JS var)
         → sub_filter injects $network_type (Local/Remote) from X-Forwarded-For
         → try_files /index.html (single file for all users)
         → JS reads TRAILHEAD_USERNAME + TRAILHEAD_USER_GROUPS (case-insensitive lookup)
         → JS hides cards where data-access doesn't match user's groups
```

**Domain routing**: AdGuard DNS (192.168.0.11) rewrites `*.1701.me → 192.168.0.30` (NPM reverse proxy). NPM proxies `home.1701.me → 192.168.0.179:8076`. Users must access via `home.1701.me`, not the IP:port directly.

## Access Groups

Defined in `trailhead.yaml`:

```yaml
access_groups:
  admin:  [alec, akadmin]
  media:  [alec, akadmin]
  family: [alec]
```

Each card has an `access` field:
- `access: [admin]` — visible only to users in the `admin` group
- `access: [admin, media]` — visible to users in `admin` OR `media`
- `access: [admin, family]` — visible to users in `admin` OR `family`

At generation time, access_groups is inverted to `user_groups` with **lowercase keys**:
```json
{"alec": ["admin", "media", "family"], "akadmin": ["admin", "media"]}
```

This JSON is embedded in the HTML. At serve time, nginx injects the username, and JS filters cards using a **case-insensitive** lookup (`TRAILHEAD_USERNAME.toLowerCase()`).

## Sidebar Tabs

| Tab | Content | Source |
|-----|---------|--------|
| Bookmarks | 4 groups, ~36 service cards | `trailhead.yaml → tabs[bookmarks].groups` |
| Cameras | Camera snapshot cards | `trailhead.yaml → tabs[cameras].cards` |

Empty tabs (all cards hidden) are automatically hidden by JS.

## Authentik Configuration

Configured via API. Components created:

- **Proxy Provider**: `trailhead` — forward auth single application, external host `http://home.1701.me`
- **Application**: `Trailhead`, slug `trailhead`, pk `4c8c0fb6-c9ab-4ca2-aa19-4a17e4a21087`
  - `launch_url`: `http://home.1701.me` (must match external host, not IP:port)
- **Embedded outpost**: Trailhead provider assigned
- **Brand**: UUID `e137649b-f669-43e7-abdf-6e52a6b7e952` (default brand, customized)
- **Authentication flow**: `default-authentication-flow` — title "Welcome, please login", identification + password on one page
- **API token**: `BVcngz0VAdh81uKFTOd93NHHD2sXF5624hml3LLFuYTSQMYyd7vA8pOLDLgx` (for programmatic brand/flow changes)
- **Users**: `alec`, `akadmin` (default admin)

To add a new user:
1. Create user in Authentik admin: http://192.168.0.179:9000/if/admin/#/identity/users
2. Add username to the appropriate groups in `trailhead.yaml` under `access_groups`
3. Rebuild: `cd /etc/komodo/stacks/trailhead && docker compose build generator && docker compose up -d`

## Login Page Branding

The Authentik login page is styled to match the NPS design of the Trailhead homepage. Branding is applied via the Authentik Brand API (`/api/v3/core/brands/{uuid}/`).

### Brand Settings

| Field | Value |
|-------|-------|
| `branding_title` | Trailhead |
| `branding_logo` | `/static/dist/assets/icons/trailhead-logo.svg` |
| `branding_default_flow_background` | `/static/dist/assets/images/blank.png` |
| `branding_custom_css` | NPS-themed CSS (see below) |

### TRAILHEAD Logo

SVG text logo at `/web/dist/assets/icons/trailhead-logo.svg` inside the `authentik-server` container. Also backed up at `/mnt/docker/authentik/media/custom/trailhead-logo.svg` on Komodo host.

**Note**: This file lives inside the container image (not a volume mount). It will be lost on container rebuild/update and must be re-copied:
```bash
docker cp /mnt/docker/authentik/media/custom/trailhead-logo.svg authentik-server:/web/dist/assets/icons/trailhead-logo.svg
```

### Flow Configuration

The identification stage (`default-authentication-identification`) has `password_stage` set to `default-authentication-password`, which shows both username and password fields on a single page.

The "Login to continue to Trailhead." subtitle was suppressed by editing `/web/dist/chunks/XROP4FSD.js` inside the container (changed `this.challenge.applicationPre?` to `false?`). This edit is also lost on container rebuild.

### Custom CSS

The brand CSS uses direct PatternFly class selectors (Authentik injects brand CSS into the Shadow DOM):

```css
@import url("https://fonts.googleapis.com/css2?family=Cabin:wght@400;600;700&family=Lora:ital,wght@0,400;0,600;0,700;1,400;1,600&display=swap");

:root {
  --ak-font-family-sans-serif: "Cabin", sans-serif !important;
  --ak-font-family-heading: "Cabin", sans-serif !important;
  --pf-global--primary-color--100: #5C462B !important;   /* NPS brown buttons */
  --pf-global--primary-color--200: #C56C39 !important;   /* Copper accent */
  --ak-global--background-image: none !important;
}

body { background-color: #F5F5F0 !important; }            /* Cream page bg */

.pf-c-login__main {                                       /* White card */
  background-color: #FFFFFF !important;
  border-bottom: 3px solid #6F4930 !important;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
}

.pf-c-title { color: #333333 !important; }                /* Dark text */
.pf-c-form__label-text { color: #333333 !important; opacity: 1 !important; }
.pf-c-form-control {                                       /* Input fields */
  background-color: #FFFFFF !important;
  border: 1px solid #D4C4A8 !important;
  color: #333333 !important;
}
.pf-c-button.pf-m-block,
.pf-c-button.pf-m-primary {                               /* Brown button */
  background-color: #5C462B !important;
  color: #FFFFFF !important;
}
.pf-c-list.pf-m-inline { visibility: hidden !important; } /* Hide footer */
.pf-c-login__main-footer-band { background-color: #FFFFFF !important; }
a { color: #C56C39 !important; }                           /* Copper links */
```

### Things Lost on Container Rebuild

After an Authentik update/rebuild, re-apply:
1. **Logo SVG**: `docker cp` the SVG back into the container
2. **Subtitle suppression**: Re-edit `XROP4FSD.js` (the chunk filename may change between versions)
3. **Brand CSS + settings**: Persisted in the database, survives rebuilds
4. **Flow title + password_stage**: Persisted in the database, survives rebuilds

## Files

All source files live in `/mnt/docker/trailhead/` on Komodo (192.168.0.179).
Compose file at `/etc/komodo/stacks/trailhead/compose.yaml`.

| File | Purpose |
|------|---------|
| `trailhead.yaml` | Access groups + tabs with per-card access fields |
| `generate.py` | Renders single `index.html` with all cards + user_groups JSON (lowercase keys) |
| `template.html` | Multi-tab sidebar, data-access attributes, JS filtering, Local/Remote badge |
| `nginx.conf` | Authentik forward auth, network type detection, `sub_filter_once off`, `try_files /index.html` |
| `compose.yaml` | Generator + nginx services, healthcheck on `index.html` |

## nginx.conf — Key Details

### Network Type Detection

A `map` block classifies clients as Local or Remote based on the `X-Forwarded-For` header set by NPM:

```nginx
map $http_x_forwarded_for $network_type {
    ~^192\.168\.  Local;
    ~^10\.        Local;
    default       Remote;
}
```

The `$network_type` variable is injected into HTML via `sub_filter`:

```nginx
sub_filter '<!--AUTHENTIK_USERNAME-->' $authentik_username;
sub_filter '<!--NETWORK_TYPE-->' $network_type;
sub_filter_once off;    # Multiple replacements: username (dropdown + JS var) + network type
try_files /index.html =404;
```

### Auth Redirect (Hardcoded Domain)

The `@goauthentik_proxy_signin` location **must** hardcode `home.1701.me`:

```nginx
location @goauthentik_proxy_signin {
    internal;
    add_header Set-Cookie $auth_cookie;
    return 302 http://home.1701.me/outpost.goauthentik.io/start?rd=http://home.1701.me$request_uri;
}
```

**Why hardcoded**: If the user accesses via IP:port (`192.168.0.179:8076`) instead of `home.1701.me`, using `$http_host` would produce a redirect URL with the wrong domain. The outpost compares the redirect URI against `external_host` (`http://home.1701.me`) and rejects mismatches with "redirect URI did not contain external host". This caused callback failures (HTTP 400), session mismatches, and users ending up at the Authentik dashboard instead of Trailhead.

### Logout

Logout clears the proxy cookie and redirects to Authentik's invalidation flow:

```nginx
location = /logout {
    add_header Set-Cookie 'authentik_proxy_ee210d03=; Path=/; Max-Age=0' always;
    return 302 http://192.168.0.179:9000/if/flow/default-invalidation-flow/?next=http://home.1701.me/;
}
```

The `?next=http://home.1701.me/` parameter tells Authentik where to redirect after session invalidation, so the user returns to the Trailhead login page.

**Known issue**: The outpost's `/sign_out` endpoint returns 502 when the browser has a valid proxy session cookie — the outpost prematurely closes the TCP connection. This is an Authentik outpost bug (tested on v2025.12.1), not a proxy configuration issue. The workaround is to use the direct invalidation flow URL instead.

### Other Critical Settings

- **`absolute_redirect off`** — Required because nginx inside Docker listens on :80 but is exposed as :8076.
- **`Host home.1701.me`** (hardcoded in outpost location) — The Authentik outpost routes by host matching. Internal DNS rewrite in AdGuard resolves `*.1701.me` → `192.168.0.30` (reverse proxy).
- **Cookie passthrough** — `auth_request_set $auth_cookie` + `add_header Set-Cookie $auth_cookie` on every auth-protected location.
- **`$authentik_username` from `$upstream_http_x_authentik_username`** — Reads from outpost response headers, NOT client request headers. Cannot be spoofed.

## Client-Side Filtering (JS)

```javascript
var TRAILHEAD_USER_GROUPS = {"alec": ["admin","media","family"], ...};  // embedded at generation (lowercase keys)
var TRAILHEAD_USERNAME = '<!--AUTHENTIK_USERNAME-->';  // replaced by nginx sub_filter

// On page load:
// 1. Look up user's groups using TRAILHEAD_USERNAME.toLowerCase() (case-insensitive)
// 2. Hide cards where data-access doesn't include any of user's groups
// 3. Hide empty group labels
// 4. Hide empty sidebar tabs
```

### Network Badge

The template displays a "Local" or "Remote" badge in the header based on the `$network_type` variable injected by nginx. The badge is styled with green (Local) or orange (Remote) colors. This is purely informational — access control is not affected by network location.

## User Menu

A user icon in the black band header opens a dropdown with:

- **Username display** — injected at serve time by nginx `sub_filter`
- **Change Password** — links to Authentik user settings (`http://192.168.0.179:9000/if/user/`)
- **Log Out** — hits `/logout` which clears proxy cookie and redirects to Authentik invalidation flow

## Security

- **Header spoofing safe**: `$authentik_username` comes from `$upstream_http_` (outpost response only)
- **Cards in source**: All cards are in the HTML source. Any authenticated user could view-source and see all URLs. This is fine because each service has its own auth — the access control here is UI cleanliness, not a security boundary.
- **Static assets protected**: Camera snapshot (`driveway.jpg`) requires auth
- **Health check open**: `/health` has no auth (required for Docker healthcheck)
- **Domain enforcement**: Auth redirect hardcodes `home.1701.me` to prevent OAuth callback failures when accessed via IP:port

## Troubleshooting

### User sees wrong bookmarks
Check `access_groups` in `trailhead.yaml`. The user must be listed in a group that matches the card's `access` field. Usernames are matched case-insensitively. After changes, rebuild the generator.

### Infinite login loop
Cookie passthrough is missing or broken. Ensure `auth_request_set $auth_cookie $upstream_http_set_cookie` and `add_header Set-Cookie $auth_cookie` are present on every auth-protected location block.

### Post-login redirects to Authentik dashboard (not Trailhead)
The user likely accessed via IP:port (`192.168.0.179:8076`) instead of `home.1701.me`. The OAuth callback fails because the redirect URI doesn't match `external_host`. Check:
1. `@goauthentik_proxy_signin` has hardcoded `home.1701.me` (not `$http_host`)
2. Authentik application `launch_url` is `http://home.1701.me` (not the IP:port)
3. User bookmarks point to `http://home.1701.me` (not the IP)

### Logout 502 error
The outpost `/sign_out` endpoint has a known bug (v2025.12.1) where it returns 502 when the browser has a valid proxy session cookie. The current workaround redirects to the invalidation flow directly instead. Do NOT attempt to proxy to `/outpost.goauthentik.io/sign_out` — it won't work.

### 502 or 500 errors (general)
Authentik may be down or the outpost may not have the provider assigned. Check:
```bash
docker logs authentik-server --tail 20
curl -s -o /dev/null -w '%{http_code}' -H 'Host: home.1701.me' http://192.168.0.179:9000/outpost.goauthentik.io/auth/nginx
```

### Adding a new user
1. Authentik admin → create user with password
2. Add username to appropriate groups in `trailhead.yaml`
3. Rebuild: `cd /etc/komodo/stacks/trailhead && docker compose build generator && docker compose up -d`

### Regenerating HTML after config change
```bash
cd /etc/komodo/stacks/trailhead && docker compose build generator && docker compose up -d
```
