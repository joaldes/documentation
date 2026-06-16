# Service Account & Credential Standard

**Last Updated**: 2026-06-15
**Related Systems**: Vaultwarden (CT 128, `vault.1701.me`), lldap + tinyauth (CT 128), all service stacks

## Summary

How every account on every homelab service is named, scoped, and stored. The human/SSO layer (lldap + tinyauth) was already consistent; per-service accounts were not (`admin/admin123`, `settling/friends`, `password` everywhere). This standardizes them around an **admin triad** and a single **source of truth for secrets** (Vaultwarden). It is **forward-looking**: follow it for every new service; existing weak creds are migrated opportunistically (see Appendix).

## TL;DR

| You need… | Use | Where the secret lives |
|---|---|---|
| Your own day-to-day access | `alec` via **SSO** (`*.1701.me`) | lldap (one identity) |
| A service's owner / break-glass admin | `[service]admin` (e.g. `embyadmin`) | **Vaultwarden** |
| Claude / automation access | `claudeai` | **Vaultwarden** + stack `.env` |
| One app to talk to another | `svc-<consumer>` (e.g. `svc-tplan`) | stack `.env` (+ Vaultwarden) |

**The one rule that makes it all work: every account gets a _unique, random_ password per service.** Same username across services is fine; same *password* is not.

## The admin triad

Three accounts split by **who uses them** — for revocability (kill one without losing the others) and attribution (logs show who acted). All three are full admin; scoping is deliberately skipped on the triad for a single-admin homelab.

### 1. `alec` — your daily driver
- Reached via **tinyauth SSO** at the service's `*.1701.me` name. One lldap identity fronts every SSO-capable app; no per-app human login to maintain.
- Fall back to `[service]admin` only for apps that can't sit behind SSO.

### 2. `[service]admin` — break-glass owner
- Username **encodes the service** (`embyadmin`, `grafanaadmin`, `tplanadmin`) because it's a *local* account and must be unambiguous.
- Full admin. Used for first-time setup and when SSO/everything is down. Rarely touched.
- **Never handed to automation** — that separation is what lets you revoke `claudeai` independently.

### 3. `claudeai` — Claude / automation
- One consistent username everywhere (so you can answer "what can automation touch?" at a glance).
- Full admin (pragmatic choice). Its containment comes from being a *separate* account with a *unique* password, not from scoping.

### Beside the triad: `svc-<consumer>` binds
App-to-app credentials (DB users, API tokens, LDAP binds like `tinyauth-observer`). These **are** scoped — usually read-only — because scoping is cheap to set at creation. Named after the consuming service.

## The five fields, standardized

| Field | Human (`alec`) | `[service]admin` / `claudeai` | `svc-<consumer>` |
|---|---|---|---|
| Username | `alec` | `embyadmin` / `claudeai` | `svc-tplan` |
| Email (if required) | `alec.desantis@gmail.com` | `<name>@1701.me` (non-deliverable, unique) | `<name>@1701.me` |
| Display name | `Alec` | `Emby admin` / `Claude automation` | descriptive ("tPlan DB read-only") |
| Password | n/a (SSO) | `openssl rand -base64 24`, unique, in Vaultwarden | random/token, in `.env` + Vaultwarden |
| Role | lldap groups | full admin | least-privilege (read-only where it only reads) |

## Secret storage

- **Source of truth = Vaultwarden** (`vault.1701.me`). Every triad account gets an entry. Master password is held **offline only** — never inside the vault or a backup.
- **Operational copy of service tokens** lives in the stack's `/mnt/docker/<svc>/.env` (chmod 600), referenced from `compose.yaml` as `${VAR}` — never inline, never the literal value in the compose file.
- **`.env` never goes in git.** Commit a `.env.example` with placeholder keys instead. The docs repo is a live GitHub remote — a committed secret is leaked permanently (history), even after deletion.
- **Record it**: each account gets a Vaultwarden entry and a line in `system-inventory.json` so the set is enumerable.

## New service — account checklist

1. Front it with **tinyauth SSO** (forward-auth or `add-oidc-app`) so `alec` gets in without a local human login. *(API-only services that break on forward-auth — e.g. Vaultwarden itself — are the exception; rely on their own auth.)*
2. Create **`[service]admin`** — full admin, `openssl rand -base64 24` password → **Vaultwarden**.
3. Create **`claudeai`** — full admin, unique password → **Vaultwarden** (+ `.env` if automation uses it programmatically).
4. Create any **`svc-<consumer>`** binds — least-privilege, in the consumer's `.env`.
5. **Change/disable the app's shipped default** (`admin/admin`, setup wizard) — never leave it.
6. Add a Trailhead bookmark and a `system-inventory.json` credential line.

## Anti-patterns

- **Shared password across services** — the single thing that turns one leak into total compromise. Unique-per-service is non-negotiable; it's what keeps a full-admin `claudeai` contained.
- **Readable/guessable passwords** (`claude<svc>password`) — knowing one predicts the rest. Generate random.
- **Default creds left in place** (`admin/admin`, `admin/admin123`).
- **Handing `[service]admin` to automation** — breaks independent revocation.
- **Secrets in git** — `.env` belongs in `.gitignore`.
- The universal `password` (per global notes) is an **emergency LAN console fallback only** — never an app's front-door auth.

## Verification

- New account's password exists **only** in Vaultwarden (and `.env` if a service token) — not in git, not in a chat, not in a doc.
- `alec` reaches the service via its `*.1701.me` name through SSO; `[service]admin` works as local fallback.
- A leaked-credential drill: revoking `claudeai` on one service leaves `alec`, `[service]admin`, and every other service unaffected.

## Related files

- `infrastructure/url-naming-standard.md` — the naming/URL side (this is the identity side)
- `services/tinyauth.md` — SSO + lldap (the `alec` path, `add-oidc-app`, `svc` binds like `tinyauth-observer`)
- `infrastructure/lxc-onboarding.md` — container-level access (root password, SSH keys)
- `system-inventory.json` — the credential/account register

---

## Appendix — weak-cred remediation backlog (forward-only)

Known defaults/weak creds to rotate to this standard **when next touching each service** (not a flag-day):

| Service | Current | Target |
|---|---|---|
| Grafana | `admin/admin123` | `grafanaadmin` + random → Vaultwarden |
| Reyday | `settling/friends` | `reydayadmin` + random |
| rtl433 / HA | `hassio/hassiopassword` | rotate, store in Vaultwarden |
| VPN (wg-easy / Grafana) | `admin/password` | `[service]admin` + random |
| scanopy / cartography Postgres | `postgres` / `password` | `svc-<consumer>` scoped + random |
