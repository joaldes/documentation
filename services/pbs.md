# Proxmox Backup Server (PBS)

**Last Updated**: 2026-07-02
**Related Systems**: CT 134 (pbs), Proxmox host Shipyard (192.168.0.151), datastore disk in USB bay D, storage `pbs-homelab`

## Summary
Proxmox Backup Server provides deduplicated, incremental-forever, verifiable backups. It runs in
**privileged LXC CT 134** (`192.168.0.134`) with its 7 TiB datastore on a thick-LVM volume (VG `pbs`).
Two backup flows feed it nightly:
1. **Guest backups** (04:00) — every container + VM via the PVE vzdump→PBS job.
2. **Fileshares backups** (02:48) — host file-level backup of the data shares
   (`/mnt/pictures`, `/mnt/documents`, `/mnt/docker`) via `proxmox-backup-client`.

**Backup posture (decided 2026-07-01): no offsite.** Live data (sdd, bay C) and the PBS datastore
(bay D) are two separate physical disks — that is the accepted bar. Residual risk (shared enclosure,
same location) is known and accepted.

## Access
- **Web UI:** `https://192.168.0.134:8007` — login `root` / `password`, realm **"Linux PAM standard authentication"**.
  (Self-signed cert → accept once. The "No valid subscription" nag is normal for the no-subscription repo.)
- **Trailhead:** Infrastructure tab → "Proxmox Backup Server"; "Backup Status" card → `http://192.168.0.179:8079`.
- LAN-only by design (no public `.1701.me`, no NPM). Remote access if ever needed: via the WireGuard VPN (CT 133).

## Architecture
| Layer | Detail |
|---|---|
| Guest | CT 134 `pbs`, **privileged** LXC, 4 cores / 4 GB / 2 GB swap, rootfs on `ssd` pool |
| Datastore disk | Bay-D disk → PV → VG **`pbs`** → LV **`pbs-store`** (7 TiB thick ext4 `-m 0`) → `/mnt/pbs` (~43% used) |
| Datastore | PBS datastore **`homelab`** at `/mnt/pbs` (bind-mounted into CT; privileged so `backup:backup` can write) |
| PVE storage | **`pbs-homelab`** (type `pbs`) → server 192.168.0.134, datastore `homelab` |
| Auth (guests) | PBS user `pve@pbs` + token `pve@pbs!pve-token`, role **`DatastorePowerUser`** on `/datastore/homelab` (secret in Vaultwarden) |
| Auth (fileshares) | Token `pve@pbs!fileshares` (Backup+Audit), secret in `/etc/pbs-fileshares.env` (0600) on the host |

## Guest backup job (04:00)
- PVE job `de1877fb-…` ("PBS nightly all guests"): **schedule 04:00, mode snapshot, all guests,
  exclude 106 (XP), 119 (WinTiny10), 134 (PBS itself)**, storage `pbs-homelab`.
- Job-side retention: keep-last 5, keep-weekly 1, keep-monthly 2 (pruned per guest after each run).
- VM 119's raw USB passthrough (`scsi1`) has `backup=0` so the physical disk isn't dumped.
- The legacy vzdump job `backup-220f568d` (→ `container-backups`) is **disabled** (soak complete).
- **Prune-ACL fix (2026-06-30):** the job's prune step needs `Datastore.Prune`, which the original
  Backup+Audit roles lacked → granted **`DatastorePowerUser`** (= Audit+Backup+Prune) to BOTH the
  user `pve@pbs` AND the token (privsep = intersection of the two). Note: `DatastorePrune` is NOT a
  valid role name in this PBS version — use `DatastorePowerUser`.

## Fileshares backup (02:48) — host file-level
- **Timer:** `pbs-backup-fileshares.timer` (host) → wrapper **`/usr/local/bin/pbs-fileshares-backup.sh`**.
- **Command:** `proxmox-backup-client backup pictures.pxar:/mnt/pictures documents.pxar:/mnt/documents
  docker.pxar:/mnt/docker --ns fileshares --backup-id fileshares --change-detection-mode=metadata --skip-lost-and-found`
- **Scope history:** pictures+documents from 2026-06-26; **docker added 2026-07-01** (245G actual;
  includes the regenerable 188G map data on purpose — Overpass rebuild takes weeks). **Frigate's
  config lives INSIDE this scope at `/mnt/docker/frigate/config` since 2026-07-02** (relocated off
  the ephemeral footage share; `/mnt/frigate` is now 100% disposable recordings/clips, not backed up).
- **`metadata` change-detection = fast nightlies:** only changed files are re-read (2.6T initial run
  ~11h; steady-state nightlies run in minutes — 71 s on 2026-07-01).
- **Status surfacing:** wrapper writes `/mnt/docker/backups-status/fileshares.json` → served at
  `http://192.168.0.179:8079` (nginx `backups-status` on CT 128) + Trailhead card; live progress via
  `jobctl` on jobs.home (`pbs-progress-reporter.sh` companion). An `OnFailure` notifier unit exists.
- **Restore:** `proxmox-backup-client restore` or FUSE `mount` from ns `fileshares`; snapshot group
  `host/fileshares`. A full restore test (16/16 sha256 spot-checks incl. 20–30 GB files) passed 2026-06-29.

## Retention / verification (datastore `homelab`)
| Job | Schedule | Detail |
|---|---|---|
| `homelab-prune` | daily 21:00 | keep-daily 14 / weekly 8 / monthly 6, `--max-depth 0` (root ns only — doesn't touch `fileshares`) |
| `fileshares-prune` | daily 20:30 | keep-daily 7 / weekly 4 / monthly 6 on ns `fileshares` |
| Garbage collection | daily 23:00 | |
| `homelab-verify` | Sun 02:00 | all snapshots |
| `fileshares-verify` | Sun 03:30 | ns `fileshares`, ignore-verified, re-verify after 30d |
- Snapshot `host/fileshares/2026-06-29T06:09:22Z` is **protected** (the post-heal verified legacy copy).

## Restores
- **Full guest restore** and **CT file-level restore**: from the PBS UI.
- **VM file-level restore:** must be launched from the **PVE host's "File Restore"** button (PBS-in-LXC has no KVM for the restore-VM).
- **Fileshares:** see section above.

## Notes / gotchas
- **jobctl-in-systemd `$HOME` footgun:** systemd oneshots have no `$HOME`; jobctl (dash, `set -u`)
  exited 2 before the backup ran — silent failure. Fixed 2026-06-30: jobctl line 7 hardened to
  `RC="${JOBSRC:-${HOME:-/root}/.jobsrc}"` on all installs + `Environment=HOME=/root` drop-ins on the
  backup units. Any new headless jobctl caller needs the same care.
- **Crash-consistency caveat:** the fileshares backup copies running database dirs (Postgres,
  Prometheus, Frigate SQLite under /mnt/docker) live — a restore behaves like post-power-loss
  recovery (WAL replay), and the copy is smeared over the run window. Accepted for a homelab
  disaster net; per-app dumps would be the upgrade.
- **Bay-D USB corruption history (2026-06-28):** 2 corrupt chunks traced to the datastore disk's
  USB link (UDMA_CRC=10), healed via a full `--change-detection-mode=legacy` re-read; CRC counter
  has been stable at 10 since. If it ever climbs again: apply the deferred UAS quirk
  `usb-storage.quirks=1e91:a4a7:u` + reboot.
- **Datastore on USB** — after a host reboot the `pbs` VG may need `vgchange -ay pbs && mount /mnt/pbs`
  (USB enumeration race; fstab uses `nofail`).
- **Never edit a running bash script** (the wrapper once re-read mid-run and false-failed its status JSON).
- **Thin-overcommit warning** during snapshot backups of guests on the `ssd` pool is benign.
- Privileged CT trade-off accepted (less isolation) so the bind-mounted datastore works without uid-mapping.

## Open follow-ups
- Wire up backup-failure notifications (PVE `mail-to-root` target has no recipient — errors cosmetically
  after each guest run; Telegram alerting via direct Bot API is the deferred plan).
- Back up CT 134 itself (rootfs) — don't leave the backup server unrecoverable.
- Optional: `pbs.home` rewrite in AdGuard (direct → 192.168.0.134); wildcard `*.home`→NPM doesn't serve :8007.
