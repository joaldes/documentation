# claude.home — Browser-based Claude Code Console

**Last Updated**: 2026-05-06
**Related Systems**: LXC 124 (Claude AI, 192.168.0.180), AdGuard (192.168.0.11), Caddy

## Summary
Persistent shared `claude` CLI session reachable from any LAN device at `https://claude.home/`. Replaces per-connection ttyd (which spawned a new claude process per browser hit) with a single tmux-backed session that survives browser closes, network drops, and ttyd/Caddy restarts. Lost only on container reboot.

## Architecture

Three decoupled lifetimes:

1. **tmux server** (`-L claude` socket, owned by `claudeai`) — holds the session and the `claude` process. Started once at boot by `claude-tmux.service`. Survives everything except container reboot or explicit `kill-server`.
2. **ttyd** (`127.0.0.1:7681`) — thin attach-client. `Restart=on-failure` is safe because it never spawns claude, only attaches to the existing tmux. Multiple browsers can attach simultaneously (multi-writer).
3. **Caddy** (`:443`) — terminates TLS with its local internal CA, reverse-proxies both `claude.home` and `192.168.0.180` (IP-bound site block, so it works before/without DNS) → ttyd. LAN-IP allowlist (RFC1918) as belt-and-suspenders. No auth (LAN-only, trusted). Use `systemctl restart caddy` (not reload) — `admin off` disables the reload endpoint.

```
Browser (LAN) → https://claude.home → Caddy :443 → ttyd 127.0.0.1:7681 → tmux -L claude → claude
```

## Files

| Path | Purpose |
|---|---|
| `/etc/systemd/system/claude-tmux.service` | Oneshot, creates tmux session at boot |
| `/etc/systemd/system/claude-ttyd.service` | Runs ttyd, requires claude-tmux |
| `/etc/caddy/Caddyfile` | TLS + reverse proxy |
| `/home/claudeai/.tmux.conf` | Scrollback, status bar (clients counter). **Mouse mode OFF** — interferes with browser typing/selection. |
| `/etc/systemd/system/ttyd.service.bak` | Backup of legacy unit (port 3000) |

## Operations

### Status
```bash
sudo systemctl status claude-tmux claude-ttyd caddy
sudo -u claudeai tmux -L claude list-sessions
sudo ss -tlnp | grep -E ':(443|7681)'
```

### Attach from CLI (debug)
```bash
sudo -u claudeai tmux -L claude attach -t claude
```
Detach: `Ctrl-b d`. Do NOT exit the shell — that kills the window.

### Restart pieces independently
```bash
sudo systemctl restart claude-ttyd     # safe, never duplicates claude
sudo systemctl restart caddy           # safe
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

**Survives**: browser close, WiFi drop, ttyd crash, Caddy restart, hours of idle, multiple attached clients.

**Does NOT survive**: container reboot (kernel updates, host maintenance). Claude CLI has no resumable agent state — `claude --continue` recovers transcript but not active tool execution. Same loss profile as the Proxmox console.

No idle timeout. tmux does not garbage-collect sessions.

## Decisions made (2026-05-06)
- **No auth** — LAN-only, trusted. Caddy LAN-IP allowlist + ttyd 127.0.0.1 bind only.
- **Multi-writer** — all attached browsers can type. tmux status bar shows `clients:N`. Self-discipline against typing from two devices simultaneously.
- **Drop to bash on claude exit** — no auto-restart loop (avoids the prior `Restart=always` duplicate-instance footgun).
- **Caddy on CT 124** — simpler than reusing remote reverse proxy.

## Cutover history (2026-05-06)
- Old `ttyd.service` on `:3000` ran `ttyd -W su - claudeai -c claude` — every browser hit spawned a new claude. Created duplicate-instance pile-up.
- New stack deployed in parallel; old service remains until manually retired:
  ```bash
  sudo systemctl disable --now ttyd.service
  ```
  This kills any claude session running through old ttyd. Port 3000 frees.

## DNS
AdGuard (192.168.0.11) → Filters → DNS rewrites:
- `claude.home` → `192.168.0.180`

Follows existing convention with `jobs.home`, `gis.home`, `tiles.home`.

## TLS
Caddy uses its local internal CA. To trust without per-device warnings, install:
```
/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt
```
on each client device. Otherwise accept the warning once per browser.

## Rollback
```bash
sudo systemctl disable --now claude-ttyd claude-tmux caddy
# Old ttyd on :3000 still works (was never stopped)
```

## Troubleshooting

**`https://claude.home/` doesn't resolve**: AdGuard rewrite missing or device using non-AdGuard DNS.

**Cert warning**: expected with `tls internal`. Either accept once or install Caddy local root CA.

**Browser shows blank black screen**: ttyd up but tmux session gone. Check `claude-tmux.service`; restart will recreate.

**Want a fresh claude conversation**: inside the session, exit claude (`/exit`), then run `claude` (no `--continue`). Window stays alive; agent state resets.

**Can't type / can't highlight to copy**: tmux mouse mode was on. With `set -g mouse on`, scrolling drops you into copy-mode (intercepts keystrokes) and drag-select goes to tmux instead of the browser. Mouse mode is now **off** — keep it that way for shared-console use.
