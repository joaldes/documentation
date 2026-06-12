# tinyauth + lldap — Lightweight Forward-Auth / SSO / User Management

**Last Updated**: 2026-06-11
**Related Systems**: CT 128 (Komodo/Docker), NPM (CT 112), Trailhead (`home.1701.me`), lldap (`lldap.home`)

> **User guide** (non-ops, with screenshots): `documents samba > personal/alec/claudeai/auth-user-guide/auth-user-guide.md`
> **Note**: the login UI lives on `.1701.me` names only — the login redirect and
> `.1701.me` SSO cookie require the canonical public name.

## Summary
tinyauth is a single ~20 MB forward-auth container that gates self-hosted apps with a login page,
replacing Authentik for Trailhead. It uses the same nginx `auth_request` pattern Authentik did, but
is one container with env-var config (no postgres/redis/worker). Login UI at `auth.1701.me`;
session cookie is scoped to `.1701.me` so one login is SSO across all `*.1701.me` apps placed behind
it. Deployed 2026-06-11 because Authentik's 4-container stack was overkill for a personal dashboard.

## Problem / Goal
Authentik (server + worker + postgres + redis) was too heavy for protecting a personal dashboard.
Goal: keep `home.1701.me` / `trailhead.1701.me` behind a login, reachable publicly, with far less to
run and maintain — while preserving the dashboard's username display and (optional) group filtering.

## Solution
Deploy tinyauth v5 on CT 128, expose its login UI at `auth.1701.me` via NPM, and point
`trailhead-web`'s nginx `auth_request` at tinyauth instead of the Authentik outpost. Authentik is
left running for `trips.1701.me` (not migrated).

## Implementation Details

### Stack (CT 128)
- **Image**: `ghcr.io/tinyauthapp/tinyauth:v5` (migrated from the deprecated
  `ghcr.io/steveiliop56/tinyauth` path 2026-06-12 — old path stopped at v5.0.7; all future
  releases incl. security fixes publish only under the new org).
- **Compose**: `/etc/komodo/stacks/tinyauth/compose.yaml` — published host port **3005**→3000,
  data volume `/mnt/docker/tinyauth/data:/data`, `env_file: /mnt/docker/tinyauth/.env`, joined to
  the external `auth_net` docker network (created with explicit subnet `172.99.0.0/24` because the
  default address pools on CT 128 are exhausted) to reach lldap privately.
- **Env** (`/mnt/docker/tinyauth/.env`, **chmod 600** — it holds every auth-stack secret):
  - `TINYAUTH_APPURL=https://auth.1701.me`
  - `TINYAUTH_AUTH_USERS=breakglass:<bcrypt cost 10>` — local break-glass user only; real users
    live in lldap. Format `user:bcrypt[:totp]`.
  - `TINYAUTH_SECRET=<32-char>` — cookie/session signing
  - `TINYAUTH_AUTH_SECURECOOKIE=true` — adds the `Secure` attribute to the domain-wide SSO cookie
    (NOT `TINYAUTH_SECURE_COOKIE`; the var nests under AuthConfig like AUTH_USERS)
  - ⚠️ **Trap**: bcrypt hashes contain `$`; in a Compose `env_file` you must write each `$` as `$$`
    or `docker compose` interpolates it and silently corrupts the hash (login then fails with no
    clear error). Symptom in `docker compose up`: `The "..." variable is not set`.

### NPM (CT 112)
- Proxy host **id 209**: `auth.1701.me` + `tinyauth.1701.me` (both serve the login UI; canonical
  APPURL is `auth.1701.me`) → `http://192.168.0.179:3005`, LE cert **88** (SANs: auth, tinyauth,
  homepage — issued 2026-06-12 via certbot webroot as `npm-88`). `homepage.1701.me` (the original
  login URL) and `auth.home`/`tinyauth.home` all 302 to `https://auth.1701.me`. Renamed from
  `homepage.1701.me` 2026-06-12 on user request; Authentik's old hosts were renamed to free the
  names: host 94 → `authentik.1701.me`, host 95 → `authentik.home` (still reachable for rollback).

### nginx integration (in the protected app)
In `trailhead-web` (`/mnt/docker/trailhead/nginx.conf`):
```nginx
# internal forward-auth endpoint
location /tinyauth {
    internal;
    proxy_pass         http://192.168.0.179:3005/api/auth/nginx;
    proxy_set_header   X-Forwarded-Proto https;
    proxy_set_header   X-Forwarded-Host  $http_host;   # auto per-host return URL
    proxy_set_header   X-Forwarded-Uri   $request_uri;
}
# on each protected location:
auth_request        /tinyauth;
auth_request_set    $redirection_url $upstream_http_x_tinyauth_location;
auth_request_set    $tinyauth_user   $upstream_http_remote_user;
error_page          401 403 =302 $redirection_url;
```
tinyauth returns the login redirect in the `X-Tinyauth-Location` header (auto-derives the correct
per-host `redirect_uri`), so there is **no hardcoded redirect URL** — this avoids the class of bug
the old Authentik config had (a hardcoded `rd=http://…` that tripped NPM's block-exploits → 403).
The authenticated username comes back in the `Remote-User` header.

### SSO
The session cookie is set on the parent domain `.1701.me`, so logging in once at `auth.1701.me`
authorizes every `*.1701.me` app behind tinyauth. Live behind tinyauth: `home.1701.me`,
`trailhead.1701.me`, and (since 2026-06-12) **`trips.1701.me`** (tPlan).

**Protected apps are `.1701.me`-only.** Because the cookie is domain-scoped, a `.home` hostname can
never carry the session — visiting e.g. `home.home` made tinyauth show an "Untrusted redirect"
warning, and even continuing would loop forever. Fix (2026-06-12): the `.home` NPM hosts for
protected apps (**179** trips.home, **197** home.home/trailhead.home) carry one line of
`advanced_config`:

```nginx
if ($host ~* ^(.+)\.home$) { return 302 https://$1.1701.me$request_uri; }
```

so `.home` stays a typing shortcut that lands you on the canonical URL. This also closed a LAN
header-spoof hole (trips.home previously forwarded a client-supplied `X-authentik-username`
unfiltered). Apply the same snippet to the `.home` twin of any future tinyauth-protected host.
Backups: `database.sqlite.bak-pre-home-redirect`, `179.conf/197.conf .bak-pre-home-redirect`.

**trips.1701.me migration notes** (NPM host 178, CT 112): the Authentik outpost/forward-auth blocks
were replaced with the tinyauth pattern, but the **request header names stay authentik-flavored**
(`X-authentik-username/groups/email`, filled from tinyauth's `Remote-User/Groups/Email`) because
tPlan's `share_mode_guard` middleware keys its anonymous-lockdown on the presence of
`X-authentik-username` — zero app changes needed. The public share locations (`/s/…` + pretty-slug
regex) remain unauthenticated; `/api/` still returns a bare 401 (SPA contract) while browser routes
302 to the login. Backups: `database.sqlite.bak-pre-trips-tinyauth` + `178.conf.bak-authentik-*`.

**Authentik is now fully unused** — left installed and running on CT 128 by deliberate choice
(instant rollback), but nothing routes auth through it. It is reachable at `authentik.1701.me` /
`authentik.home` (NPM hosts 94/95, renamed 2026-06-12 when `auth.*` was given to tinyauth).

### OIDC provider (enabled 2026-06-11)
tinyauth v5 also acts as a full OIDC identity provider. **Gotcha: the OIDC service silently skips
initialization unless ≥1 client is registered** — with zero clients the well-known endpoints return
an empty issuer and the JWKS handler nil-pointer panics. Setup:

1. Env (in `.env`): `TINYAUTH_DATABASE_PATH=/data/tinyauth.db`,
   `TINYAUTH_OIDC_PRIVATEKEYPATH=/data/tinyauth_oidc_key`,
   `TINYAUTH_OIDC_PUBLICKEYPATH=/data/tinyauth_oidc_key.pub`.
   Don't pre-generate keys — tinyauth creates its own (PKCS#1 `BEGIN RSA PRIVATE KEY`; a hand-made
   PKCS#8 key fails to parse).
2. **Register apps with the `add-oidc-app` helper** (multi-agent built + live-tested 2026-06-12) —
   replaces the manual register/env-edit/restart dance:
   - On CT 128: `/usr/local/bin/add-oidc-app add <name> <callback-url> [more-urls...]` /
     `list` / `remove <name>`. Validates input, backs up the env (`.env.bak-oidc-helper`),
     registers the client, appends the env block, recreates the stack, verifies the
     "Registered OIDC client" log line (ANSI-stripped) + discovery 200, **auto-restores the env
     backup on any failure**, and prints a paste-block (client ID/secret, discovery URL, endpoints,
     scopes) for the app's settings page.
   - From Windows: double-click `add-oidc-app.bat` on the documents samba
     (`personal/alec/claudeai/`) — menu-driven (Add/List/Remove), SSHes to CT 128 as root
     (standard container password), shows the paste-block, pauses.
   - Helper's `docker run` uses the image path in its `TINYAUTH_IMAGE` variable — keep it in
     sync with the compose file (both on `ghcr.io/tinyauthapp/tinyauth:v5` since 2026-06-12).
   - (Manual fallback: `docker run --rm <image> oidc create <name>` then add
     `TINYAUTH_OIDC_CLIENTS_<NAME>_CLIENTID/CLIENTSECRET/TRUSTEDREDIRECTURIS/NAME` to `.env`
     and recreate.)

Live config: client `homelab` (ID `c429c456-3802-4540-bb14-fcf3e2eb501b`, secret in `.env`).
App-facing discovery URL: `https://auth.1701.me/.well-known/openid-configuration` (RS256).

## User Management — lldap (added 2026-06-11)
Users live in **lldap** (Rust LDAP server, <10 MB RAM, SQLite) with a web UI — no more env-var editing.

- **Web UI**: `http://lldap.home` (aliases: `ldap.home`, `users.home` — NPM host 211, renamed
  2026-06-12 on user request; HTTP-only per the `.home`=http / `.1701.me`=https
  convention; the mkcert `*.home` cert was removed from NPM entirely 2026-06-12) — **LAN/VPN only,
  deliberately NOT internet-facing** (it's the root of trust for all SSO; security review
  2026-06-11). The earlier public `users.1701.me` (NPM host 210 + LE cert npm-87) was removed the
  same day — soft-deleted in the NPM DB and `certbot delete`d on CT 112.
  Admin login: user `admin` (password in `/mnt/docker/lldap/.env`, `LLDAP_LDAP_USER_PASS`).
  alec is in `lldap_admin` so his own login can manage users too.
- **Stack**: `/etc/komodo/stacks/lldap/compose.yaml`, data/env `/mnt/docker/lldap/` (`.env` chmod 600,
  `data/users.db` chmod 600). Image `lldap/lldap:stable`. Port 17170 (UI) published; LDAP **3890 is
  NOT published** — tinyauth reaches it as `ldap://lldap:3890` over the shared external `auth_net`
  docker network, so nothing on the LAN can touch the directory protocol.
- **Add a user**: lldap UI → Create user (+ add to groups) → done. tinyauth picks it up instantly,
  no restart. Deleting works the same way (login 401 immediately).
- **Directory**: base DN `dc=1701,dc=me`. Users: `alec` (groups: `admin`, `lldap_admin`),
  `tinyauth-observer` (read-only bind account, member of `lldap_strict_readonly`).
- **tinyauth wiring** (in `/mnt/docker/tinyauth/.env`): `TINYAUTH_LDAP_ADDRESS=ldap://lldap:3890` (via `auth_net`),
  `TINYAUTH_LDAP_BINDDN=uid=tinyauth-observer,ou=people,dc=1701,dc=me`, `TINYAUTH_LDAP_BINDPASSWORD`,
  `TINYAUTH_LDAP_BASEDN=dc=1701,dc=me`, `TINYAUTH_LDAP_SEARCHFILTER=(uid=%s)`, `TINYAUTH_LDAP_INSECURE=true`.
- **Break-glass**: `TINYAUTH_AUTH_USERS=breakglass:<bcrypt>` remains — a *local* tinyauth user that works
  even when lldap is down. ⚠️ The local username must NOT collide with an LDAP username: tinyauth
  matches local users first, and local logins get **no groups header** (this bit alec until he was
  renamed out of the env var).
- **Groups → apps**: LDAP logins return `Remote-Groups` (comma-joined, e.g. `admin,lldap_admin`).
  Trailhead consumes it via `auth_request_set $tinyauth_groups $upstream_http_remote_groups` +
  `sub_filter '<!--AUTHENTIK_GROUPS-->' $tinyauth_groups;` (template.html group split accepts `|` and `,`).
- **Login API**: `POST /api/user/login` `{ "username": "...", "password": "..." }`. Repeated failures
  rate-limit to 429 for a few minutes.
- ⚠️ **Single-file bind-mount trap**: `nginx.conf`, `template.html`, `trailhead.yaml` are file mounts —
  `sed -i`/`mv` replaces the inode and the container keeps the OLD file. Restart the container after
  editing, then regen (`docker exec trailhead-generator touch /tmp/regen`).

## Verification
```bash
# unauthenticated → 302 to the login page
curl -sk -o /dev/null -w "%{http_code} %{redirect_url}\n" https://home.1701.me/ \
  --resolve home.1701.me:443:192.168.0.30
# login, then the cookie authorizes a different subdomain (proves .1701.me SSO)
curl -sk -c j.txt -X POST https://auth.1701.me/api/user/login \
  -H 'Content-Type: application/json' -d '{"username":"alec","password":"..."}' \
  --resolve auth.1701.me:443:192.168.0.30
curl -sk -b j.txt https://home.1701.me/ --resolve home.1701.me:443:192.168.0.30 | grep user-dropdown-name
```

## Troubleshooting
- **Login always fails / `variable is not set` on deploy** → bcrypt `$` not doubled to `$$` in `.env`.
- **403 on the login redirect** → a full-URL `redirect_uri=http://…` in the query (block-exploits).
  tinyauth URL-encodes it, so this shouldn't occur; if it does, ensure `X-Forwarded-Proto https`.
- **Revert to Authentik**: restore `/mnt/docker/trailhead/nginx.conf.bak-authentik-*` and reload
  `trailhead-web`.

## Notes / Follow-ups
- Stack was deployed via `docker compose` directly; **not yet adopted in the Komodo UI**.
- Renaming the login URL again needs the cert + APPURL + helper dance done 2026-06-12, then
  update `TINYAUTH_APPURL`.
