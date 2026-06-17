# Proxmox Backup Server (PBS)

**Last Updated**: 2026-06-17
**Related Systems**: CT 134 (pbs), Proxmox host Shipyard (192.168.0.151), datastore on `sdg2` (IronWolf), storage `pbs-homelab`

## Summary
Proxmox Backup Server provides deduplicated, incremental-forever, verifiable backups of all Proxmox
guests. It runs in **privileged LXC CT 134** (`192.168.0.134`) with its datastore on a new **thick-LVM**
volume carved from the empty tail of the `sdg` IronWolf. Backups run nightly at **05:00** to the
`pbs-homelab` storage, in parallel with the legacy 04:00 vzdump job during a soak period.

## Access
- **Web UI:** `https://192.168.0.134:8007` — login `root` / `password`, realm **"Linux PAM standard authentication"**.
  (Self-signed cert → accept once. The "No valid subscription" nag is normal for the no-subscription repo.)
- **Trailhead:** Infrastructure tab → "Proxmox Backup Server".
- LAN-only by design (a backup server holding every guest's snapshots — no public `.1701.me`, no NPM).
  Remote access if ever needed: via the WireGuard VPN (CT 133).

## Architecture
| Layer | Detail |
|---|---|
| Guest | CT 134 `pbs`, **privileged** LXC, 4 cores / 4 GB / 2 GB swap, rootfs on `ssd` pool |
| Datastore disk | `sdg2` → PV → VG **`pbs`** → LV **`pbs-store`** (7 TiB thick ext4 `-m 0`) → `/mnt/pbs` |
| Datastore | PBS datastore **`homelab`** at `/mnt/pbs` (bind-mounted into CT; privileged so `backup:backup` can write) |
| PVE storage | **`pbs-homelab`** (type `pbs`) → server 192.168.0.134, datastore `homelab` |
| Auth | PBS user `pve@pbs` + API token `pve@pbs!pve-token` (roles `DatastoreBackup`+`DatastoreAudit` on the user AND the token — privsep intersection). **Token secret stored in Vaultwarden.** |

## Backup job
- New job (id `de1877fb-…`): **schedule 05:00, mode snapshot, all guests, exclude 106 (XP) + 134 (PBS itself)**.
- VM 119's raw USB passthrough (`scsi1`) set `backup=0` so it isn't dumped.
- Legacy vzdump `backup-220f568d-ade5` (04:00 → `container-backups`) left running in parallel during the soak.

## Retention / maintenance (on the `homelab` datastore)
- **Prune** `homelab-prune`: keep-daily 14, keep-weekly 8, keep-monthly 6 — daily 21:00.
- **Garbage collection:** daily 23:00.
- **Verify** `homelab-verify`: weekly, Sun 02:00.

## Restores
- **Full guest restore** and **CT file-level restore**: from the PBS UI.
- **VM file-level restore:** must be launched from the **PVE host's "File Restore"** button (PBS-in-LXC has no KVM for the restore-VM).

## Verification
- `pvesm status | grep pbs-homelab` → active. PBS UI → Datastore `homelab` → Content shows per-guest snapshots.
- A test backup of CT 132 succeeded (2026-06-17): 3.8 GiB → 1.8 GiB compressed, ~30 MiB/s.

## Notes / gotchas
- **Datastore on USB (`sdg`)** — after a host reboot the `pbs` VG may need `vgchange -ay pbs && mount /mnt/pbs` (USB enumeration race; fstab uses `nofail`).
- **Thin-overcommit warning** during snapshot backups of guests on the `ssd` pool is benign (virtual sizes exceed pool, actual usage ~21%).
- **Backup-failure alerts** not yet wired (mail target has no recipient) — TODO.
- Privileged CT trade-off accepted (less isolation) so the bind-mounted datastore works without uid-mapping.

## Open follow-ups
- Wire up backup-failure notifications (PVE notification target).
- Back up CT 134 itself (rootfs) via urbackup or an offsite rsync of `/mnt/pbs` — don't leave the backup server unrecoverable.
- After soak + a successful test restore: optionally retire the legacy 04:00 vzdump job. (`sde1`/container-backups left untouched for now.)
- Optional: add `pbs.home` rewrite in the AdGuard web UI (direct → 192.168.0.134); wildcard `*.home`→NPM doesn't serve :8007.
