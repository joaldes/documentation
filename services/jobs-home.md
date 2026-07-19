# jobs.home — Ambient Job Progress Visibility

**Last Updated**: 2026-07-19 (v2)
**Related Systems**: CT 128 (Komodo, 192.168.0.179), CT 124 (Claude AI), CT 102 (Emby), Shipyard (PVE host), CT 101 (AdGuard DNS)

---

## Quick Reference

| Item | Value |
|------|-------|
| **Host** | CT 128 (Komodo, 192.168.0.179) |
| **Port** | 8077 |
| **DNS** | `jobs.home → 192.168.0.179` (AdGuard rewrite) |
| **Direct URL** | `http://192.168.0.179:8077` |
| **Container** | `jobsd` (Docker, built from `/mnt/docker/jobsd/`) |
| **Compose** | `/mnt/docker/jobsd/compose.yaml` |
| **Data** | `/mnt/docker/jobsd/data/jobs.db` (SQLite, WAL) + `/mnt/docker/jobsd/data/logs/` (per-run logs) |
| **Token file** | `~/.jobsrc` per-host, mode 600 |
| **Helper script** | `/usr/local/bin/jobctl` (POSIX sh) — source of truth `/mnt/docker/jobsd/jobctl` |
| **Hosts with jobctl** | CT 124 (claudeai), CT 128 (komodo), CT 102 (emby), Shipyard, magazine container (bind-mounted) |
| **Watchdog seed** | `/mnt/docker/jobsd/seed-schedules.sh` (idempotent, re-run after edits) |
| **PVE poller** | `/mnt/docker/jobsd/pve-poller.py`, cron `/etc/cron.d/pve-poller` (*/10), env `/root/.pve-poller.env` |

---

## What it does

Live progress dashboard for every job on the homelab — ad-hoc scripts, wrapped crons, and Proxmox backups. Any host with `jobctl` + `~/.jobsrc` POSTs job state to jobsd; the page auto-refreshes every 2 s via htmx.

**v2 (2026-07-19)** added:
- **Unique run ids** — every run is its own row (`name@host.epoch-pid`); history is never overwritten, concurrent same-name runs coexist.
- **Per-run logs** — `jobctl run` captures stdout+stderr and streams it to the server; view/tail from the dashboard, failures show their last lines inline.
- **Missed-run watchdog** — registered schedules (crons, backups) get a MISSED state when a run doesn't check in on time. Dead crons are no longer silent.
- **Attention panel** — failures, stalls, and missed schedules at the top of the page; collapses to a green "all clear" line.
- **Proxmox backup ingestion** — vzdump/PBS results appear as jobs via a poller; the fileshares timer reports through a systemd drop-in.
- **Robust rate/ETA** — median-of-gaps rate (reset-tolerant) + EMA-smoothed ETA; `--unit items` for non-byte jobs.
- **Stall lifecycle** — stalled jobs revive on any sign of life; auto-close to failed after 24 h so amber is always actionable.

Alerting is **dashboard-only** by design (no push/Telegram/email).

---

## Run ids (v2)

- `jobctl start|run|track-file|pipe-progress` mint `slug(name)@host.epoch-pid`, e.g. `screener-nightly@komodo.1752897000-8841`, and print it.
- `name` stays the series key: sparklines, history queries, and watchdog matching are by name (+host).
- Update commands (`progress`, `phase`, `done`, `waiting`) resolve their target in this order:
  1. `--id RUN_ID` flag
  2. `$JOBCTL_RUN_ID` env var
  3. state file written by `start` (`/tmp/jobctl-<uid>/<slug>.run`, deleted by `done`)
  4. legacy bare `name@host` (v1 compatibility)
- Limitation: two concurrent same-name `start`…`done` pairs from *separate scripts* share the state file — pass `--id "$(jobctl start NAME)"` in that case. `jobctl run` is immune (id held internally).
- Docker containers must set `JOBS_HOST` (in `.jobsrc` or env) or they report hex container ids as hostnames. The magazine container does this via its entrypoint-generated `.jobsrc`.

---

## Quick-start examples (common tools)

```sh
# One command, everything tracked: progress + full log capture
jobctl run dl -- curl -o /tmp/file.iso "$URL"

# yt-dlp batch (the Time Team pattern)
jobctl run yt-batch -- yt-dlp -a urls.txt -o "%(title)s.%(ext)s" --write-info-json

# rsync (incremental backup)
jobctl run backup-photos -- rsync -avh --info=progress2 /src /dst

# Item-based work instead of bytes
jobctl run tt-classify --unit items --total 1226 -- python3 classify.py

# ffmpeg encode of a single file (track output growth)
jobctl track-file encode-foo /tmp/out.mp4 --total 2G &
ffmpeg -i in.mkv -c:v libx264 -crf 22 /tmp/out.mp4
wait

# wget with parsed progress + log streaming
wget --progress=dot:giga "$URL" 2>&1 | jobctl pipe-progress iso-dl --total 12G --re '[0-9]+%' --log

# Manual start/progress/done from a script (state file threads the run id)
jobctl start audit --total 500 --unit items
...
jobctl progress audit 250
...
jobctl done audit --exit-code 0
```

### Mid-flight tracking (no job restart needed)

```sh
# Started Overpass index manually 30 min ago, want to track it now
jobctl track-file overpass-indexing /mnt/docker/map/overpass/db/db --total 32G --interval 60 &
```

---

## API

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /jobs/{id}/start` | bearer | create a run (renames aside any existing row under the same id — legacy protection) |
| `POST /jobs/{id}/progress` | bearer | update current/total/msg/phase/unit; revives a stalled run |
| `POST /jobs/{id}/phase` | bearer | set phase (milestone recorded on change) |
| `POST /jobs/{id}/done` | bearer | mark succeeded/failed (by exit_code) |
| `POST /jobs/{id}/log` | bearer | append a raw text chunk to the run's stored log (5 MB cap/run) |
| `POST /runs/report` | bearer | one-shot report of an already-finished run with historical timestamps (used by pve-poller) |
| `POST /schedules` | bearer | upsert a watchdog schedule |
| `DELETE /schedules/{id}` | bearer | remove a schedule |
| `GET /api/schedules` | none | schedules + missed state + next expected |
| `GET /api/jobs` | none | JSON list of running + recent (24 h) jobs; `?name=X` for one series' full history |
| `GET /jobs/{id}/log?tail=N` | none | last N lines of the stored log (default 100, max 2000) |
| `GET /jobs/{id}/tail` | none | legacy alias of the above |
| `GET /` | none | HTML dashboard |
| `GET /_partial/jobs` | none | htmx fragment |
| `GET /metrics` | none | Prometheus exposition incl. `jobsd_schedule_missed` |
| `GET /healthz` | none | liveness probe |

---

## `jobctl` usage

```sh
jobctl start NAME [--total N] [--unit items|bytes] [--cmd "..."] [--log /path] [--phase P] [--msg M]
jobctl progress NAME CURRENT [--total N] [--unit U] [--msg "..."] [--id RUN_ID]
jobctl phase NAME PHASE [--msg "..."] [--id RUN_ID]
jobctl done NAME [--exit-code N] [--id RUN_ID]

jobctl run NAME [--total N] [--unit U] [--phase P] [--msg M] [--no-log] -- <cmd...>
  # The default wrapper. Start → run → capture exit → done. In v2 it also:
  #  - captures merged stdout+stderr and streams it to jobsd every ~3 s
  #    (client stops past 2 MB, then sends the last 64 KB at the end so
  #    failure context is always the tail; --no-log opts out)
  #  - still auto-sniffs download output files (wget -O, curl -o, aria2c -o)
  #    and HEADs the URL for Content-Length → real bar + rate + ETA
  #  - traps INT/TERM/HUP → exactly one done post (4 retry attempts)
  #  - its background watcher exits when the main process dies (kill -9 safe)

jobctl track-file NAME PATH [--total N] [--interval 30] [--auto-done]
  # Polls file/dir size. --auto-done stays OFF by default (false-success risk
  # on bursty workloads). v2: ctrl-C posts done(130) instead of stalling.

jobctl pipe-progress NAME [--total N] [--re REGEX] [--log]
  # Parse a number per stdin line as progress. --log also streams the lines.

jobctl ls [--running]   # list jobs known to jobsd
jobctl id NAME          # echo the name-scoped id prefix (series key)
```

Environment knobs (in `~/.jobsrc` or env): `JOBS_URL`, `JOBS_TOKEN`, `JOBS_HOST` (hostname override, required in containers), `JOBS_LOG_CLIENT_MAX` (default 2097152).

---

## Watchdog schedules

Registered in `schedules` (SQLite) via `POST /schedules`; the sweeper flags a schedule MISSED when no matching run (`name` + optional `host`) has started within the last cron slot (or interval) + grace. MISSED and failed-last-run schedules go to the attention panel; `/metrics` exposes `jobsd_schedule_missed`.

Seeded set (2026-07-19) — edit + re-run `/mnt/docker/jobsd/seed-schedules.sh`:

| Schedule | Cadence | TZ | Source |
|---|---|---|---|
| claude-backup@claudeai | every 30 min | — | CT124 crontab |
| claude-health@claudeai | every 15 min | — | CT124 crontab |
| night-info-refresh@claudeai | every 30 min | — | CT124 crontab |
| screener-nightly@komodo | 03:30 Tue–Sat | UTC | CT128 cron.d |
| vaultwarden-backup@komodo | 02:00 daily | UTC | CT128 cron.d |
| tplan-backup@komodo | 03:00 daily | UTC | CT128 cron.d |
| docker-prune@komodo | 03:00 Sun | UTC | CT128 cron.d |
| magazine-nightly@magazine | 02:00 daily | America/Phoenix | in-container cron |
| magazine-weekly@magazine | 17:00 Fri | America/Phoenix | in-container cron |
| system-inventory@Shipyard | hourly | UTC | Shipyard cron.d |
| pbs-nightly@Shipyard | 04:00 daily | **America/Phoenix** | `/etc/pve/jobs.cfg` via pve-poller |
| pbs-fileshares@Shipyard | 02:30 daily (+20 m jitter) | **America/Phoenix** | systemd timer; script-internal jobctl |

⚠ **Shipyard timers/PVE schedules fire in host-local time (Phoenix), not UTC** — discovered 2026-07-19 after first seeding them as UTC. Container crons on CT128 really are UTC.

**Cron TZ rule**: the jobsd container runs `TZ=America/Phoenix` but most host crons are UTC — every cron-type schedule carries an explicit `tz`, and the server evaluates the cron grid in that zone (croniter).

All previously-unmonitored crons were jobctl-wrapped on 2026-07-19: CT124 crontab (all 3), CT128 `/etc/cron.d/{tplan-backup,docker-prune}`, Shipyard `/etc/cron.d/system-inventory`. Wrapped crons redirect local output to `/dev/null` where a local log file used to exist — the job log in jobsd replaces it. Backup copies of the original cron files: `/root/cron-bak-*.2026-07-19` on each host, `/tmp/crontab.bak.2026-07-19` on CT124.

---

## Proxmox backup ingestion

- **pve-poller** (`/mnt/docker/jobsd/pve-poller.py`, cron `*/10` on CT128) reads finished `vzdump` tasks from the PVE API (`claude@pam!api` token, config `/root/.pve-poller.env` mode 600) and one-shot-reports each unseen UPID via `POST /runs/report` as job `pbs-nightly@Shipyard.<hex>` with the task's real start/end times. Failed tasks get the last 100 lines of the PVE task log attached. Seen-UPID state: `/var/lib/pve-poller/seen.upids`.
- The poller is deliberately **not** jobctl-wrapped: if it dies, `pbs-nightly` goes MISSED on the dashboard — that *is* the alarm.
- **pbs-backup-fileshares** (systemd oneshot on Shipyard) needs no drop-in: `/usr/local/bin/pbs-fileshares-backup.sh` already wraps the backup in `jobctl run pbs-fileshares --total <bytes>` with a sidecar progress reporter (`pbs-progress-reporter.sh`) — job name **pbs-fileshares**, which is what the watchdog schedule matches. (A redundant drop-in added 2026-07-19 was removed the same day. The sidecar reporter depends on jobctl `run` writing its state file — v2 ≥ 2026-07-19 does.) The service's `HOME=/root` override is required for jobctl.

---

## Compose file

`/mnt/docker/jobsd/compose.yaml` — v2 additions to `environment`:

```yaml
      JOBS_STALL_THRESHOLD_SEC: "600"   # running → stalled after 10 min quiet
      JOBS_STALL_FAIL_SEC: "86400"      # stalled → failed (auto-close) after 24 h
      JOBS_SWEEP_INTERVAL_SEC: "60"
      JOBS_PRUNE_DAYS: "30"             # rows, events, and stored logs
      JOBS_BUSY_TIMEOUT_MS: "5000"
      JOBS_LOG_DIR: /data/logs
      JOBS_LOG_MAX_BYTES: "5242880"     # 5 MB server cap per run log
      JOBS_LOG_DIR_MAX_MB: "500"        # total log dir cap (oldest deleted first)
      TZ: America/Phoenix
```

`Dockerfile` deps: `fastapi uvicorn[standard] jinja2 python-multipart croniter==2.0.5`.

---

## Operations

### Restart
```bash
ssh root@192.168.0.179 'cd /mnt/docker/jobsd && docker compose restart jobsd'
```

### Rebuild after code change
```bash
ssh root@192.168.0.179 'cd /mnt/docker/jobsd && docker compose up -d --build --force-recreate jobsd'
```

### View live logs
```bash
ssh root@192.168.0.179 'docker logs -f jobsd'
```

### Add a new host
1. `scp /mnt/docker/jobsd/jobctl host:/usr/local/bin/jobctl && ssh host "chmod 755 /usr/local/bin/jobctl"`
2. Create `~/.jobsrc` with `JOBS_URL=http://192.168.0.179:8077` and `JOBS_TOKEN=<token>` (chmod 600). In a docker container also add `JOBS_HOST=<meaningful-name>`.
3. Smoke test: `ssh host 'jobctl start hello; jobctl done hello'`

### Add/adjust a watchdog schedule
Edit `/mnt/docker/jobsd/seed-schedules.sh` and re-run it (upsert by id). One of `cron` (+ explicit `tz`!) or `interval_sec`; `grace_sec` should absorb the job's normal duration + jitter.

### Rotate token
1. **Generate**: `NEW=$(openssl rand -hex 32); echo "$NEW"`
2. **Server**: edit `/mnt/docker/jobsd/.env` → `JOBS_TOKEN=$NEW`, `docker compose restart jobsd`
3. **Each host**: update `~/.jobsrc`; also `/root/.pve-poller.env` (JOBS_TOKEN) and the magazine stack `.env` on CT128
4. **Smoke**: from each host `jobctl start rotate-test; jobctl done rotate-test`
5. **Rollback**: revert `.env` + restart, revert each `~/.jobsrc`

---

## Disaster recovery

If `/mnt/docker/jobsd/data/jobs.db` is wiped or corrupted, the service rebuilds an empty DB on next start (`init_db()` is `CREATE TABLE IF NOT EXISTS` + idempotent ALTERs). Re-run `seed-schedules.sh` afterwards to restore the watchdog registry:

```bash
ssh root@192.168.0.179 'rm -f /mnt/docker/jobsd/data/jobs.db
cd /mnt/docker/jobsd && docker compose restart jobsd && ./seed-schedules.sh'
```

Pre-v2 backups from the 2026-07-19 upgrade: `data/jobs.db.bak.2026-07-19`, `app.bak.2026-07-19/`, `jobctl.bak-fleet.2026-07-19` (all under `/mnt/docker/jobsd/`), plus `/usr/local/bin/jobctl.bak.2026-07-19` on each host.

---

## Querying history (SQLite)

The DB is at `/mnt/docker/jobsd/data/jobs.db` on CT 128 (192.168.0.179). WAL mode, safe to query while running.

```sh
# last 7 days of finished jobs
ssh root@192.168.0.179 "sqlite3 /mnt/docker/jobsd/data/jobs.db \
  \"SELECT name, host, status, duration FROM jobs
    WHERE ended_at > strftime('%s','now','-7 days')
    ORDER BY started_at DESC\""

# success rate per named job
ssh root@192.168.0.179 "sqlite3 /mnt/docker/jobsd/data/jobs.db \
  \"SELECT name, COUNT(*) runs, SUM(status='succeeded') ok,
           SUM(status='failed') fail, ROUND(AVG(duration),1) avg_sec
    FROM jobs WHERE status<>'running' GROUP BY name ORDER BY runs DESC\""

# watchdog state
ssh root@192.168.0.179 "sqlite3 /mnt/docker/jobsd/data/jobs.db \
  \"SELECT id, cron, interval_sec, tz, last_run_status,
           datetime(last_run_at,'unixepoch') last_run, missed_since IS NOT NULL missed
    FROM schedules ORDER BY id\""
```

Note on old rows: v1 (pre-2026-07-19) used name-scoped ids with `INSERT OR REPLACE`, so pre-v2 history has at most one row per name and many `failed`/`stalled` rows are auto-closed orphans of the old id-collision bug, not real failures.

---

## Schema (SQLite)

```sql
CREATE TABLE jobs (
  id          TEXT PRIMARY KEY,   -- v2: <slug>@<host>.<epoch>-<pid>; legacy: <slug>@<host>
  name        TEXT NOT NULL,      -- series key (sparklines, watchdog matching)
  host        TEXT,
  cmd         TEXT,
  log_path    TEXT,               -- legacy optional pointer; v2 logs live server-side
  total       REAL,
  current     REAL DEFAULT 0,
  msg         TEXT,
  phase       TEXT,
  status      TEXT DEFAULT 'running',  -- running | succeeded | failed | stalled
  exit_code   INTEGER,
  started_at  REAL, updated_at REAL, ended_at REAL,
  duration    REAL,
  unit        TEXT,               -- 'items' | NULL (= bytes)
  log_bytes   INTEGER,            -- stored log size; NULL = no log
  log_truncated INTEGER DEFAULT 0,
  stalled_at  REAL
);

CREATE TABLE progress_events (job_id TEXT, ts REAL, current REAL);  -- capped 200/job
CREATE TABLE milestones      (job_id TEXT, ts REAL, phase TEXT, msg TEXT);

CREATE TABLE schedules (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, host TEXT,
  cron TEXT, interval_sec INTEGER,          -- exactly one set
  tz TEXT DEFAULT 'UTC', grace_sec INTEGER DEFAULT 1800,
  enabled INTEGER DEFAULT 1, created_at REAL,
  last_run_id TEXT, last_run_status TEXT, last_run_at REAL,
  missed_since REAL, note TEXT
);
```

Per-run logs: `/data/logs/<run_id>.log`, 5 MB/run server cap, 500 MB dir cap, pruned with their job rows (30 days).

---

## UI features

- **Attention panel** at top: MISSED schedules, failed-last-run schedules, current stalls, failed runs from the last 7 days (latest-per-name; compact rows, first 10). Collapses to a green "all clear" line.
- **Running** section: %, unit-aware rate (B/s or items/s), smoothed ETA, short run id, live log viewer (open state survives refresh via hx-preserve; "raw" link for full tail).
- **Recent (24 h)**: latest run per name with a ×N count badge (click → that name's full history via `/?name=X`).
- **Schedules** table: cadence, last run, next expected; missed rows highlighted.
- Failed cards render their last 15 log lines inline — zero-click failure context.
- Progress bar colors: blue=running, green=succeeded, red=failed, amber=stalled.

---

## Troubleshooting

**`jobctl: command not found` from `pct exec`** — `/usr/local/bin` not in non-login shell PATH. Use `/usr/local/bin/jobctl` explicitly.

**Job "stuck" running** — sweeper marks it `stalled` after 10 min quiet (log appends and progress posts both count as life). Stalled auto-closes to `failed` (exit −1, msg `[auto-closed after stall]`) after 24 h. Manual close: `jobctl done NAME` (uses the state file / legacy id) or `jobctl done NAME --id <run_id>` (run id shown on the card).

**A schedule shows MISSED but the cron ran** — check `host` on the schedule matches what the job reports (`jobctl id NAME` on that host shows the `@host` part; containers need `JOBS_HOST`). Also check the schedule's `tz` — cron-type schedules are evaluated in their declared zone, not the container's.

**Run id confusion in scripts** — `start` prints the run id and writes the state file; `done NAME` picks it up automatically in the common case. Concurrent same-name scripted runs must pass `--id`.

**`401` from POSTs** — `~/.jobsrc` token doesn't match `/mnt/docker/jobsd/.env`. Re-sync.

**500 on `/_partial/jobs`** — Jinja error; `docker logs jobsd` shows the trace; rebuild after fixing.

**Heartbeat noise** — `{}` progress posts bump `updated_at` only; they never enter `progress_events`, so rate/ETA math is unaffected.

**Watcher detached too early** — `track-file --auto-done` exits when size is flat for 5 polls; for jobs with long pauses use `--interval 120`.

**DNS doesn't resolve `jobs.home`** — that host isn't using AdGuard DNS (CT124 is one). Use `192.168.0.179:8077` directly.

**pve-poller silent** — check `/var/log/pve-poller.log` on CT128 and that `/root/.pve-poller.env` has all 5 keys. A dead poller surfaces as `pbs-nightly` MISSED within a few hours.

---

## Future work

- Grafana dashboards via `/metrics` (`jobsd_schedule_missed` is alert-rule-ready if push alerting is ever wanted)
- `jobctl log NAME` subcommand to tail a run's stored log from the CLI
- Retention knob per-name (e.g. keep claude-health only 7 days)
