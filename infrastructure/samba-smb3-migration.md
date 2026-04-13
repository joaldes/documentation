# Samba SMB3 Minimum Protocol Migration

**Last Updated**: 2026-04-13
**Related Systems**: Container 104 (Samba, 192.168.0.176)

## Summary
Tightened Samba server config on container 104 to require SMB3 minimum protocol and reject legacy authentication (LANMAN, NTLMv1). Removed the Samba server's exposure to SMB1-class vulnerabilities (the WannaCry protocol family) and weak password hashing. Migration was zero-impact — single connected client (Windows laptop "Hydrofoil") was already negotiating SMB3.1.1, so a graceful `smbd` reload kept its open shares mounted with no re-authentication.

## Problem / Goal
Container 104's `smb.conf` had three security weaknesses inherited from default Debian Samba configuration:

```
min protocol = NT1     # allows SMB1 clients (deprecated, WannaCry-era exploit surface)
ntlm auth = yes        # default behavior permits NTLMv1 (weak)
lanman auth = yes      # LANMAN hashes use DES, 7-char chunks, no salt — cracked in seconds
```

There was no documented reason for these settings — they were defaults, not deliberate compatibility holds. Since the Samba server holds shares for `documents`, `backups`, and `pictures` (containing personal data), the blast radius if `sambauser`'s credential were captured off the wire was unacceptable for what should be a 3-line config change.

Goal: raise minimum protocol to SMB3 and disable LANMAN/NTLMv1 auth, without disrupting any active client or dependent process.

## Solution
Three-line change to `/etc/samba/smb.conf` followed by graceful reload (not restart) of `smbd`. Pre-flight investigation confirmed:

- Only one active SMB client (Hydrofoil, 192.168.0.34) and it was already negotiating **SMB3_11** with AES-128-GMAC signing — already at the target protocol level
- All 11 LXC containers consuming the shared mounts (Plex/Emby, Frigate, Radarr/Sonarr, Bazarr, Syncthing, Komodo stacks, ClaudeAI, etc.) use **bind mounts**, never SMB — restarting `smbd` cannot affect them
- HA VM 100's `core_samba` add-on is a separate Samba *server*, not a client of container 104
- Zero historical SMB1 negotiations in any Samba log file (live or rotated)
- No script, container fstab, Komodo stack, or documentation anywhere on the homelab pinned SMB1 / NT1 / lanman / ntlmv1

## Implementation Details

### Steps Performed

1. Snapshot `smbstatus` before the change (for after-comparison):
   ```bash
   pct exec 104 -- smbstatus -p > /tmp/smbstatus-before.txt
   pct exec 104 -- smbstatus > /tmp/smbstatus-before-full.txt
   ```

2. Backup the config:
   ```bash
   pct exec 104 -- cp /etc/samba/smb.conf /etc/samba/smb.conf.bak.smb3-migration
   ```

3. Apply the three-line change with idempotent `sed`:
   ```bash
   pct exec 104 -- sed -i \
       -e 's/^\s*min protocol = NT1/    min protocol = SMB3/' \
       -e 's/^\s*ntlm auth = yes/    ntlm auth = ntlmv2-only/' \
       -e 's/^\s*lanman auth = yes/    lanman auth = no/' \
       /etc/samba/smb.conf
   ```

4. Validate config syntax before activating:
   ```bash
   pct exec 104 -- testparm -s
   # Expected: "Loaded services file OK"
   # Confirms: server min protocol = SMB3, lanman auth = No, ntlm auth = ntlmv2-only
   ```
   Note: `testparm` emits `WARNING: The "lanman auth" option is deprecated`. This is benign — the option name itself is going away in a future Samba version, but our value (`no`) is correct regardless.

5. Graceful reload of `smbd` (not restart — preserves open client handles):
   ```bash
   pct exec 104 -- systemctl reload smbd
   ```

6. Verified the active client (Hydrofoil) was unaffected — same PID, same dialect, same locked files, no re-authentication.

### Key Files Modified
- `/etc/samba/smb.conf` (container 104) — three lines changed
- `/etc/samba/smb.conf.bak.smb3-migration` (container 104) — pre-change backup, retained for rollback

### Diff
```diff
-    min protocol = NT1
+    min protocol = SMB3
-    ntlm auth = yes
+    ntlm auth = ntlmv2-only
-    lanman auth = yes
+    lanman auth = no
```

`max protocol = SMB3` was already set — no change needed.

## Verification

After the reload, all of the following held true:

- `systemctl reload smbd` → exit code 0
- `testparm -s` reports:
  - `server min protocol = SMB3`
  - `lanman auth = No`
  - `ntlm auth = ntlmv2-only`
- `smbstatus -p` shows Hydrofoil still connected — **same PID** (`3578999`), same IP (`192.168.0.34`), same dialect (`SMB3_11`), same signing (`partial(AES-128-GMAC)`)
- `smbstatus` shows all 6 shares (`backups`, `docker`, `hometheater`, `frigate`, `documents`, `pictures`) still mounted with their **original** connect timestamps — confirming the reload was transparent and no re-authentication happened
- `tail /var/log/samba/log.smbd` shows no errors
- All 11 LXC consumers of the bind-mounted paths continued operating with no impact (verified by their continued normal operation; bind mounts are kernel-level and independent of the smbd process)

## Rollback
Single command if anything ever needs reverting:
```bash
pct exec 104 -- cp /etc/samba/smb.conf.bak.smb3-migration /etc/samba/smb.conf
pct exec 104 -- systemctl reload smbd
```
Graceful reload means rollback is also non-disruptive to active clients.

## Troubleshooting

**A client suddenly can't connect after the migration.**
The client is trying to negotiate SMB1 or SMB2 and is being refused. To identify it:
```bash
pct exec 104 -- tail -f /var/log/samba/log.smbd
# Look for lines mentioning the client IP and "negotiate" or "protocol"
```
Then either upgrade the client's SMB stack, or — if it's a legacy device that genuinely needs older protocols — relax `min protocol` to `SMB2_10` (covers Windows Vista+ / Linux kernel 3.x+) instead of `SMB3`.

**`testparm` shows a "lanman auth deprecated" warning.**
Benign. The option name is being phased out of Samba but our value (`no`) is still respected. No action needed.

**Need to also enable wire encryption.**
A natural follow-up would be `smb encrypt = auto` (encrypts SMB traffic when the client supports it). Hydrofoil supports it via SMB3_11. Worth doing as a *separate* change after this one is validated, so any compatibility quirks can be isolated.

## Background — Why This Was Safe

A pre-migration investigation ran three parallel audits before any change was made:

| Audit | Finding |
|---|---|
| Active SMB clients via `smbstatus` | Single client: Hydrofoil (Windows laptop, 192.168.0.34) on SMB3_11 |
| Historical SMB1 negotiations (full grep across `/var/log/samba/`) | Zero found |
| Bind-mount vs SMB consumers across all containers/VMs | All 11 container consumers use bind mounts; no SMB clients besides Hydrofoil |
| Documentation/scripts pinning SMB1 anywhere on homelab | None found |
| HA Samba add-on dependency | Independent Samba *server*, not a client of container 104 |

Result: the migration target (`SMB3`) was already what the only active client used. The change was a config tightening with no functional surface area for breakage.

## Non-Security Benefits (For Reference)

The bigger jump from SMB1 → SMB2 (which is implicit in raising minimum to SMB3) also delivers performance and compatibility wins beyond security:

- **Folder browsing**: SMB1 is famously chatty (100+ round-trips per directory listing). SMB2/3 batch metadata, noticeably faster on large photo/music libraries.
- **Throughput**: SMB2/3 use larger I/O sizes than SMB1, easier to saturate gigabit.
- **Modern OS compatibility**: Windows 10/11, macOS 11+, recent Linux kernels prefer SMB2/3 and may refuse to negotiate SMB1 by default.
- **Server-side copy (SMB3 ODX)**: when moving files between folders within the same share via Explorer/Finder, data stays on the server instead of bouncing through the client.
- **Wire encryption available** (not enabled here, but accessible via `smb encrypt = auto` if desired).
