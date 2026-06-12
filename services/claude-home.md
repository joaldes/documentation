# claude.home — Browser-based Claude Code Console

**Last Updated**: 2026-06-12
**Related Systems**: LXC 124 (Claude AI, 192.168.0.180), NPM (LXC 112, 192.168.0.30), AdGuard (192.168.0.11), tinyauth (CT 128)

## Summary
Persistent shared `claude` CLI session reachable at `http://claude.home/` (LAN) or `https://claude.1701.me/` (anywhere, tinyauth login). Single tmux-backed session that survives browser closes, network drops, and ttyd restarts. Lost only on container reboot.

> **2026-06-12**: Caddy decommissioned. NPM is now the only proxy for all three Claude web UIs (claude / claude-new / claude-dev). `.1701.me` hostnames are gated by tinyauth forward-auth; previously they were internet-reachable with **no auth**.

## Architecture

Three decoupled lifetimes:

1. **tmux server** (`-L claude` socket, owned by `claudeai`) — holds the session and the `claude` process. Started once at boot by `claude-tmux.service`. Survives everything except container reboot or explicit `kill-server`.
2. **ttyd** (`0.0.0.0:7681`) — thin attach-client. `Restart=on-failure` is safe because it never spawns claude, only attaches to the existing tmux. Multiple browsers can attach simultaneously (multi-writer).
3. **NPM** (LXC 112) — hostname routing + real Let's Encrypt TLS on `.1701.me`. Proxy hosts forward straight to the app ports with WebSocket upgrade headers:

| NPM host | Domain | Upstream | Auth |
|---|---|---|---|
| 105 | `claude.home` | `http://192.168.0.180:7681` | none (LAN-only DNS) |
| 104 | `claude.1701.me` | `http://192.168.0.180:7681` | tinyauth |
| 200 | `claude-new.home` | `http://192.168.0.180:3003` | none |
| 199 | `claude-new.1701.me` | `http://192.168.0.180:3003` | tinyauth |
| 207 | `claude-dev.home` | `http://192.168.0.180:3013` | none |
| 206 | `claude-dev.1701.me` | `http://192.168.0.180:3013` | tinyauth |

```
Browser → claude.home / claude.1701.me → NPM (192.168.0.30) → ttyd 0.0.0.0:7681 → tmux -L claude → claude
```

tinyauth on the `.1701.me` hosts lives in the NPM `advanced_config` (auth_request → `http://192.168.0.179:3005/api/auth/nginx`, 401 → 302 to `auth.1701.me`), same pattern as trips/tplan. `.home` variants stay open — they only resolve on LAN DNS.

### Why Caddy was removed
Caddy predated NPM + split-horizon DNS. Once DNS pointed all hostnames at NPM, Caddy was a redundant second hop, and its LAN-only IP guard was ineffective (all proxied traffic arrives from NPM's LAN IP). Its last two jobs — exposing the localhost-bound ttyd/claude-ui and direct-IP HTTPS — were replaced by binding those services to 0.0.0.0 and by the `.home`/`.1701.me` names.

**Rollback**: `/etc/caddy/` is intact on CT 124. `systemctl enable --now caddy`, rebind ttyd/claude-ui to 127.0.0.1, and repoint the six NPM hosts to `https://192.168.0.180:443`. NPM DB backups on CT 112: `/data/database.sqlite.bak-20260612` and `…20260612b`.

## Files

| Path | Purpose |
|---|---|
| `/etc/systemd/system/claude-tmux.service` | Oneshot, creates tmux session at boot |
| `/etc/systemd/system/claude-ttyd.service` | Runs ttyd (`-i 0.0.0.0`), requires claude-tmux |
| `/etc/systemd/system/claude-ui.service` | claude-new UI (`HOST=0.0.0.0`, port 3003) |
| `/etc/systemd/system/claude-dev.service` | claude-dev UI (port 3013) |
| CT 112 `/data/nginx/proxy_host/{104,105,199,200,206,207}.conf` | NPM proxy configs |
| `/home/claudeai/.tmux.conf` | Scrollback, status bar (clients counter). **Mouse mode OFF** — interferes with browser typing/selection. |
| `/etc/caddy/Caddyfile` | DECOMMISSIONED — kept for rollback only |

## Operations

### Status
```bash
sudo systemctl status claude-tmux claude-ttyd
sudo -u claudeai tmux -L claude list-sessions
sudo ss -tlnp | grep -E ':(7681|3003|3013)'
```

### Attach from CLI (debug)
```bash
sudo -u claudeai tmux -L claude attach -t claude
```
Detach: `Ctrl-b d`. Do NOT exit the shell — that kills the window.

### Restart pieces independently
```bash
sudo systemctl restart claude-ttyd     # safe, never duplicates claude
sudo systemctl restart claude-tmux     # DESTROYS the session — kills claude conversation
```

### Recover when claude exits inside tmux
Window drops to bash by design (no auto-restart). From browser:
```bash
claude --continue   # resumes transcript; in-memory tool state is lost
```

### View what's on screen without attaching
```bash
sudo -u claudeai tmux -L claude capture-pane -t claude -pS - | tail -40
```

## Reliability

**Survives**: browser close, WiFi drop, ttyd crash, NPM reload, hours of idle, multiple attached clients.

**Does NOT survive**: container reboot (kernel updates, host maintenance). Claude CLI has no resumable agent state — `claude --continue` recovers transcript but not active tool execution. Same loss profile as the Proxmox console.

No idle timeout. tmux does not garbage-collect sessions.

## Decisions
- **2026-06-12: tinyauth on `.1701.me`, none on `.home`** — public hostnames get the SSO wall; LAN names stay frictionless. ttyd/claude-ui now bind 0.0.0.0, so raw `http://192.168.0.180:7681/3003/3013` also works on LAN.
- **Multi-writer** — all attached browsers can type. tmux status bar shows `clients:N`. Self-discipline against typing from two devices simultaneously.
- **Drop to bash on claude exit** — no auto-restart loop (avoids the prior `Restart=always` duplicate-instance footgun).

## DNS
AdGuard rewrites: `claude.home`, `claude-new.home`, `claude-dev.home` and the `.1701.me` equivalents all → `192.168.0.30` (NPM). Split-horizon makes `.1701.me` work both on and off LAN.

## Troubleshooting

**White screen / empty page**: NPM upstream wrong. Hosts must forward to the app ports above. (Historical bug: they pointed at Caddy's per-IP listeners :8443/:8453, where no site matched the forwarded Host header — Caddy answered an unmatched host with an empty 200.)

**Terminal loads but never connects (spinner/black)**: WebSocket upgrade headers missing in the NPM conf's `location /` (`proxy_http_version 1.1` + `Upgrade`/`Connection`). Hosts 104/105 shipped without them once already.

**Clipboard copy doesn't work**: the OSC52 shim (`-I /home/claudeai/ttyd/index.html`, patch source `/home/claudeai/ttyd/osc52-patch.html`) needs a **secure context** — use `https://claude.1701.me`, not `http://claude.home`.

**`claude.home` doesn't resolve**: device not using AdGuard DNS — use `claude.1701.me` instead (resolves anywhere).

**Browser shows blank black screen**: ttyd up but tmux session gone. Check `claude-tmux.service`; restart will recreate.

**Want a fresh claude conversation**: inside the session, exit claude (`/exit`), then run `claude` (no `--continue`). Window stays alive; agent state resets.

**Can't type / can't highlight to copy**: tmux mouse mode was on. With `set -g mouse on`, scrolling drops you into copy-mode (intercepts keystrokes) and drag-select goes to tmux instead of the browser. Mouse mode is now **off** — keep it that way for shared-console use.
