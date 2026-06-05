# Homelab URL / Service-Naming Standard

**Last Updated**: 2026-06-04
**Related Systems**: AdGuard (CT 101), NPM (CT 112), Caddy (CT 124), all Komodo Docker stacks, all LXC containers

## Summary

Standard for how services in the OV House homelab are named, addressed, and called by other services. Adopts split-horizon DNS on `*.1701.me` + `*.home` LAN-only short-aliases (live 2026-06-04). Applies to NEW services and refactors of existing ones; legacy raw-IP patterns are grandfathered but should migrate over time.

## TL;DR — when to use what

| Caller | Target | URL pattern | Why |
|---|---|---|---|
| Browser, mobile, bookmarks | Any user-facing service | `https://<svc>.1701.me` | Single URL works at home AND remote (split-horizon) |
| Type-it-fast at home | Any user-facing service | `https://<svc>.home` | Short typing alias; LAN-only |
| Service-to-service across hosts (LXC/VM/host boundary) | Backend API on another host | `http://<svc>.home/path` via **env var** (NO port — NPM dispatches to backend port). Only include port when `<svc>.home` has a specific AdGuard entry pointing at the backend IP directly. | Hides IP; centrally renameable via AdGuard. See "The port rule" section below. |
| Service-to-service within same Docker network | Sibling container in compose | `http://<containername>:<port>` | Zero DNS dependency, Docker-native |
| Bypass NPM (service has own reverse proxy on :80/:443) | That service | Specific AdGuard `<svc>.home → <IP>` | Avoids unnecessary NPM hop |
| One-off scripts, debugging | Anywhere | Raw IP:port acceptable | Pragmatic; don't bake into application code |

**Never** put raw IPs in application code. Always wrap in an env var, even if the value is a hostname.

## The port rule (critical — do not forget)

When you write a URL like `http://<svc>.home/path`, **what port the browser/code uses depends on which routing tier handles `<svc>.home`**:

| Tier resolving `<svc>.home` | Port in URL? | Example |
|---|---|---|
| **Wildcard `*.home → NPM (192.168.0.30)`** | **DROP THE PORT** — NPM only listens on :80 and :443. Including the actual backend port hits NPM on a port it doesn't serve, connection refused. | `http://magazine.home/api/today` ✓ <br> `http://magazine.home:8089/api/today` ✗ |
| **Specific AdGuard entry `<svc>.home → backend IP`** | **INCLUDE THE PORT** — DNS sends you straight to the backend, which serves on its own port (not :80/:443). | `http://overpass.home:12345/api/interpreter` ✓ <br> `http://overpass.home/api/interpreter` ✗ (port 80 on .229 has no listener) |
| **No special handling (just `*.home → NPM` and NPM has the entry)** | Same as wildcard row — DROP THE PORT. NPM dispatches by Host header to the correct backend port internally. | `http://ollama-api.home/api/embed` ✓ |

**Quick decision tree when writing a new URL:**
1. Does the service have its OWN reverse proxy on the target IP (Caddy, nginx) that listens on :80/:443? → use bare `<svc>.home` (no port)
2. Does NPM have a `proxy_host` entry for this hostname? → use bare `<svc>.home` (no port), NPM dispatches internally
3. Does AdGuard have a specific entry pointing `<svc>.home → backend_IP` (not NPM's .30)? → include `:port` because you're talking to the backend directly

The wildcard `*.home → 192.168.0.30` is option #2 (NPM). It's the default path for any name without a more specific entry.

## The architecture

```
                                       ┌──────────────────────────┐
  Browser at home                      │ AdGuard DNS (CT 101)     │
  https://immich.1701.me     ──────▶   │  wildcards:              │
                                       │   *.1701.me  → NPM IP    │ ───┐
                                       │   *.home     → NPM IP    │    │
                                       │  specific overrides      │    │
                                       │   claude.home → CT 124   │    │
                                       │   overpass.home → CT 131 │    │
                                       └──────────────────────────┘    │
                                                                       │
  Browser on cellular                                                  │
  https://immich.1701.me  ──▶  Google Domains (wildcard *.1701.me) ──▶ │
                                  → public IP 76.159.199.214           │
                                  → router port-forward 80/443         │
                                                                       │
                                                                       ▼
                                                      ┌────────────────────────┐
                                                      │ NPM (CT 112)           │
                                                      │ reads Host header,     │
                                                      │ dispatches by service  │
                                                      └───────────┬────────────┘
                                                                  │
                                                                  ▼
                                                       internal service IP:port
```

**Two wildcards in AdGuard** send everything to NPM by default. **Specific entries override** the wildcard for exceptions (services with their own reverse proxy, or backends called with explicit ports).

## The four layers of naming

### 1. Public DNS (Google Domains, `1701.me`)

- Wildcard `*.1701.me → 76.159.199.214` (your WAN IP)
- **No per-service records needed.** Wildcard catches everything.
- Specific records only if you have a reason to NOT have a service publicly resolvable (rare — NPM 404 already handles "doesn't exist publicly").

### 2. Internal DNS (AdGuard, CT 101 at 192.168.0.11)

Two wildcards:
- `*.1701.me → 192.168.0.30` (NPM) — split-horizon for the owned domain
- `*.home → 192.168.0.30` (NPM) — LAN-only short alias

Specific overrides (use sparingly):
- When the target IP has its own reverse proxy on standard ports. E.g., `claude.home → 192.168.0.180` (Caddy on CT 124).
- When a backend API is called by JS/code with an explicit port baked into the URL. E.g., `overpass.home → 192.168.0.229` (tplan's service worker calls `http://overpass.home:12345/...`).

**Never** add a specific override that points at NPM (192.168.0.30) — that's redundant with the wildcard.

### 3. Reverse proxy (NPM, CT 112 at 192.168.0.30, admin at :81)

Every user-facing service has ONE proxy_host entry with `domain_names: [<svc>.1701.me, <svc>.home]` and forward to internal IP:port.

For services on docker stacks, the forward host is the host CT's IP (usually `192.168.0.179` for Komodo) and the port is whatever the service publishes.

NPM uses the Host header to dispatch. Same URL pattern works for LAN-internal traffic (arrives from .30 side) and remote traffic (arrives from router port-forward).

### 4. Caddy (CT 124 at 192.168.0.180) — special case

Only for the claude / claude-new browser consoles. Caddy on CT 124 listens on 443 and handles `claude.home, claude.1701.me, claude-new.home, claude-new.1701.me`. Bypasses NPM entirely because Caddy is already a reverse proxy serving these specific services.

Don't add new services to Caddy unless they have a similar in-CT-124 architecture.

## Building a new service — checklist

Suppose you're building `widgets`, a Python web app on a new container CT 140 at 192.168.0.140 serving on port 5000.

1. **Compose file**: define the service with an env var pattern:
   ```yaml
   services:
     widgets:
       image: widgets:latest
       ports:
         - "5000:5000"
       environment:
         BASE_URL: http://widgets.1701.me   # for any self-referential URLs the app generates
         AUTH_URL: http://auth.home         # if it calls Authentik
         OVERPASS_URL: http://overpass.home:12345   # if it calls a backend
       dns:
         - 192.168.0.11  # AdGuard, so .home and .1701.me resolve inside the container
   ```

2. **NPM**: add a proxy_host entry via the admin UI (192.168.0.30:81):
   - Domain Names: `widgets.1701.me, widgets.home`
   - Forward Hostname / IP: `192.168.0.140`
   - Forward Port: `5000`
   - Scheme: `http`
   - SSL: (see HTTPS section below)

3. **No DNS changes needed**: wildcards `*.1701.me` and `*.home` already cover the new name.

4. **Test**: at home, `curl -I https://widgets.home` and `https://widgets.1701.me` both return 200 (or your service's status).

5. **Add to Trailhead**: `/mnt/docker/trailhead/trailhead.yaml` gets a new card with `local: http://widgets.home` and `remote: https://widgets.1701.me`.

6. **Add to spreadsheet**: `/mnt/documents/personal/alec/claudeai/IP and Ports.xlsx` Current Services sheet.

7. **Document**: GitHub repo `services/widgets.md` describes deployment, config, gotchas.

## Service-to-service calls

When `widgets` needs to talk to `overpass` (which lives on CT 131:12345), there are three valid patterns:

### Pattern A — hostname via env var (recommended for cross-host)

```yaml
# in widgets' compose.yaml
services:
  widgets:
    environment:
      OVERPASS_URL: http://overpass.home:12345
    dns:
      - 192.168.0.11
```

```python
# in widgets' app.py
OVERPASS_URL = os.getenv("OVERPASS_URL")
requests.get(f"{OVERPASS_URL}/api/interpreter", ...)
```

**Why**: IP changes are AdGuard edits, not code+rebuild+redeploy. Grepping the codebase for "overpass" finds every caller.

### Pattern B — container name via env var (recommended for same-network)

If `widgets` and `overpass` are sibling containers in the same docker-compose stack:

```yaml
services:
  widgets:
    environment:
      OVERPASS_URL: http://overpass:80   # container name
  overpass:
    image: wiktorn/overpass-api
```

**Why**: Docker's built-in DNS resolves the container name on the shared network. Zero AdGuard dependency. Fastest path. Works across container restarts even if container IPs change.

### Pattern C — raw IP via env var (acceptable fallback)

```yaml
environment:
  OVERPASS_URL: http://192.168.0.229:12345
```

**When**: AdGuard might not be reachable (network setup, container can't use AdGuard for some reason), or you explicitly want to bypass DNS for performance / reliability.

**Avoid**: hardcoding IPs in application code WITHOUT the env var wrapper. The env var lets you swap to A or B later without touching code.

## The Docker container DNS gotcha

By default, Docker containers do NOT use AdGuard for DNS. They use Docker's embedded resolver, which falls back to the host's `/etc/resolv.conf` (often `8.8.8.8` on Proxmox CTs). So `<svc>.home` returns NXDOMAIN inside the container.

**Fix per service in compose** (recommended, scoped):
```yaml
services:
  widgets:
    dns:
      - 192.168.0.11
```

**Fix host-wide** (CT 128 Komodo, affects every container on that host):
```json
// /etc/docker/daemon.json
{
  "dns": ["192.168.0.11"]
}
```
Then `systemctl restart docker`.

Prefer per-service config — explicit and reviewable per stack.

## HTTPS / TLS strategy

| Hostname | Cert source | Notes |
|---|---|---|
| `<svc>.1701.me` | Let's Encrypt via NPM | Either per-service HTTP-01 challenge or one wildcard `*.1701.me` DNS-01 challenge (preferred). Real browser-trusted cert. |
| `<svc>.home` | **mkcert local CA** (live as of 2026-06-05) | Local CA on CT 112 issues an explicit-SAN cert covering every `<svc>.home` name in NPM. Browser-trusted on any device with the root CA installed. |

### mkcert setup (live state)

- Root CA on CT 112 at `/root/.local/share/mkcert/rootCA.pem`
- Cert covers explicit SAN list of every `<svc>.home` in NPM (re-issued whenever the list changes)
- Bound in NPM as cert id=27 to ~45 proxy_host entries that didn't already have an LE cert
- Root CA distributed via Samba: `\\<server>\documents\personal\alec\claudeai\rootCA-home.pem`

**Why explicit SANs instead of `*.home` wildcard**: OpenSSL and modern browsers reject `*.home` as too-broad because `home` isn't a registrable public suffix. Wildcards only work one level deep within a registrable domain.

### Adding a new `.home` service to the mkcert cert

```bash
# On CT 112
ssh claude@192.168.0.151 'sudo pct exec 112 -- bash -c "
export PATH=/usr/local/bin:\$PATH
cd /data/custom_ssl/mkcert
# Re-issue cert with all current .home names from NPM + the new one
NAMES=\$(sqlite3 /data/database.sqlite ... | python3 ...)   # collect from NPM
mkcert -cert-file home.crt -key-file home.key \$NAMES
cp home.crt /data/custom_ssl/npm-27/fullchain.pem
cp home.crt /data/custom_ssl/npm-27/chain.pem
cp home.key /data/custom_ssl/npm-27/privkey.pem
chmod 600 /data/custom_ssl/npm-27/privkey.pem
nginx -s reload
"'
```

### Installing the root CA on a device

| Platform | Steps |
|---|---|
| **Windows** | Double-click `rootCA-home.pem` → Install Certificate → Local Machine → "Trusted Root Certification Authorities" → restart browsers |
| **macOS** | Double-click → Keychain Access → drag to "System" keychain → expand cert → Trust → "Always Trust" → restart browsers |
| **Linux** | `sudo cp rootCA-home.pem /usr/local/share/ca-certificates/mkcert-rootCA.crt && sudo update-ca-certificates`. For Firefox: about:preferences → Privacy → Certificates → Authorities → Import |
| **iOS** | AirDrop to phone → install profile in Settings → Settings → General → About → Certificate Trust Settings → enable trust for mkcert |
| **Android** | Copy to phone storage → Settings → Security → Encryption & credentials → Install certificate → CA certificate |

### Bad patterns to avoid

- Per-service LE certs via HTTP-01 — each renewal needs the public endpoint reachable; if a service is internal-only via wildcard `*.1701.me → public IP`, renewals can fail silently.
- Letting certs expire and not noticing — set a monitoring alert. NPM has built-in renewal but the alarms don't fire to anywhere visible.
- Using `*.home` wildcard certs — rejected by browsers/OpenSSL. Use explicit SANs.
- Storing mkcert root CA PRIVATE KEY (`rootCA-key.pem`) outside CT 112 — the `.pem` (public cert) is OK to distribute; the `-key.pem` is the entire trust root for your `.home` zone.

## Specific patterns for common service types

### Web app with frontend + backend in one stack

```yaml
services:
  app:
    environment:
      PUBLIC_URL: https://app.1701.me
      DB_URL: postgresql://db:5432/app
    dns:
      - 192.168.0.11
  db:
    image: postgres
```

NPM entry: `app.1701.me, app.home → 192.168.0.<host>:<app port>`

### Pure backend API (no human visits)

Two sub-patterns:

**B1**: API has its own LXC, called from across the network:
- AdGuard specific entry: `api.home → <api IP>` (NOT NPM, because callers will include the port in their URLs)
- No NPM entry needed
- Callers: `http://api.home:<port>` via env var

**B2**: API is in a docker stack with its caller as a sibling:
- No DNS at all — caller uses Docker container name
- `http://api:<port>` via env var

### IoT / Home Assistant integration

HA can resolve `.home` if pointed at AdGuard (it usually is, via DHCP). Use `<svc>.home` in REST sensors, MQTT brokers, etc.

For internal MQTT/MQTT bridges, prefer container name or raw IP since HA's container might not always honor AdGuard.

## Anti-patterns to avoid

1. **Hardcoded IPs in application code.** Use an env var that holds the hostname. The env var is the seam where infrastructure meets code.
2. **Different URLs for LAN vs remote in user-facing bookmarks.** Use `<svc>.1701.me` everywhere — split-horizon handles the LAN-fast path automatically.
3. **`.local` TLD anywhere.** mDNS/Bonjour reserves it; some clients (especially Apple) misbehave.
4. **Specific AdGuard entries that point at NPM (.30).** Redundant with the wildcard. Just delete.
5. **NPM proxy_host with `domain_names` containing only `.lan`.** Already retired 2026-06-04. New entries should be `.home` + `.1701.me`.
6. **Letting an AdGuard specific entry override a wildcard with a dead backend IP.** The user appears to navigate to `<svc>.home`, browser tries `:443` on the dead backend, connection refused. Either delete the specific entry (wildcard → NPM works) or fix the IP.

## Related files / where things live

- AdGuard config: `/opt/AdGuardHome/AdGuardHome.yaml` on CT 101 (`filtering.rewrites[]`)
- NPM database: `/data/database.sqlite` on CT 112 (`proxy_host`, `certificate` tables)
- NPM nginx configs: `/data/nginx/proxy_host/<id>.conf` on CT 112 — auto-generated from DB by NPM admin via API
- Caddy: `/etc/caddy/Caddyfile` on CT 124
- Public DNS: Google Domains UI for `1701.me`
- Trailhead bookmarks: `/mnt/docker/trailhead/trailhead.yaml` on CT 128
- Service inventory: `/mnt/documents/personal/alec/claudeai/IP and Ports.xlsx`, Current Services sheet

## Quick verification commands

```bash
# Does <svc>.home resolve to NPM via wildcard?
dig +short widgets.home @192.168.0.11        # expect 192.168.0.30

# Does NPM serve <svc>.home correctly?
curl -sI -H "Host: widgets.home" http://192.168.0.30/

# Does <svc>.1701.me resolve internally via AdGuard?
dig +short widgets.1701.me @192.168.0.11     # expect 192.168.0.30 (split-horizon)

# Does <svc>.1701.me resolve publicly via Google Domains?
dig +short widgets.1701.me @1.1.1.1          # expect 76.159.199.214 (wildcard)

# End-to-end browser test, on LAN:
curl -sI https://widgets.1701.me/            # expect 200 if cert is set up, ERR_SSL_UNRECOGNIZED_NAME_ALERT if not
```

## See also

- Memory `home_split_horizon.md` — current architecture state and exceptions list
- Memory `trailhead_bookmark_ip.md` — historical note about why Trailhead bookmarks use raw IPs
- Memory `feedback_komodo_stacks.md` — where Komodo stack files live
