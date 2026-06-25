# Komodo Periphery (non-Core hosts)

**Last Updated**: 2026-06-25

Deployment template for the Komodo Periphery agent on hosts that run periphery **without** Komodo Core —
currently **CT 130 (foundry)** and **CT 131 (cartography)**, deployed from `/opt/komodo-periphery/`.
CT 128 runs periphery as part of Komodo Core's own compose (`/opt/komodo/compose.yaml`) and is NOT covered here.

## Why this exists
On 130/131 periphery was originally a bare `docker run` (no compose/systemd/labels), so its config — and the
`apparmor=unconfined` fix below — lived only in the running container and would be lost on any recreate/update.
This codifies it so the fix is durable.

## The `apparmor=unconfined` requirement
Periphery bind-mounts `/proc` and reads other processes' `/proc/<pid>/*` for host stats. Under Docker's
default AppArmor profile that read is mediated as `ptrace` and **denied + audited** (~70+/min per agent),
flooding the kernel audit log (`kauditd_printk_skb: callbacks suppressed`, `audit: backlog limit exceeded`).
Running periphery with `security_opt: [apparmor=unconfined]` lets the same-uid read succeed silently.
periphery already holds the docker socket (it manages all containers), so this is not a meaningful extra privilege.

## Deploy / update (per host)
```bash
mkdir -p /opt/komodo-periphery
# copy compose.yaml here; create periphery.env (chmod 600) from periphery.env.example with the real
# PERIPHERY_PASSKEYS (Vaultwarden: "komodo-periphery")
cd /opt/komodo-periphery
docker compose config                 # validate first
docker rm -f komodo-periphery         # remove any bare docker-run container first (name collision)
docker compose up -d
# later updates:
docker compose pull && docker compose up -d
```

## Footgun
Do **NOT** re-run the upstream Komodo periphery installer — it `docker run`s a fresh bare container and
reverts `apparmor=unconfined`, bringing the audit flood back. Always manage these hosts via this compose.

## Secret
`periphery.env` holds `PERIPHERY_PASSKEYS` (shared across all periphery agents; source of truth = Vaultwarden).
It is `chmod 600` on-host and **must never be committed**. Only `periphery.env.example` lives in git.
