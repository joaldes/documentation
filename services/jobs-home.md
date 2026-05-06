# jobs.home — Ambient Job Progress Visibility

**Last Updated**: 2026-05-05
**Related Systems**: CT 128 (Komodo, 192.168.0.179), CT 124 (Claude AI), CT 102 (Emby), CT 101 (AdGuard DNS)

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
| **Data** | `/mnt/docker/jobsd/data/jobs.db` (SQLite, WAL mode) |
| **Token file** | `~/.jobsrc` per-host, mode 600 |
| **Helper script** | `/usr/local/bin/jobctl` (POSIX sh) |

---

## What it does

Live progress dashboard for ad-hoc scripts running anywhere on the homelab. Any host with `jobctl` installed and `~/.jobsrc` configured can `POST` job state to jobsd and have it surface on `jobs.home` immediately. Page auto-refreshes every 2 sec via htmx.

Solves the problem of "I run scripts everywhere" — wget on CT 128, Python audits on CT 124, ad-hoc operations on the laptop, etc. — and previously had no single place to glance and see "what's running, how is it doing, when will it finish."

---

## Architecture

- **`jobsd`**: FastAPI service in a single container. SQLite for state + history. ~250 LOC.
- **`jobctl`**: POSIX-sh helper deployed per-host. ~180 LOC. Calls jobsd via curl.
- **No Pushgateway, no AlertManager rules, no Authentik**: deferred to v2 if needed.

Bearer-token auth on writes (`POST /jobs/.../{start,progress,done}`); reads (`GET /api/jobs`, `/`, `/_partial/jobs`) are open on LAN. Service is bound to LAN; no external exposure.

---

## Quick-start examples (common tools)

```sh
# wget — pipe progress
wget --progress=dot:giga "$URL" 2>&1 | jobctl pipe-progress iso-dl --total 12G --re '[0-9]+%'

# curl — wrap with track-file
jobctl track-file iso-dl /tmp/file.iso --total 12G --interval 30 &
curl -fSL -o /tmp/file.iso "$URL"
wait    # track-file auto-completes when file size goes flat

# yt-dlp batch (the Time Team pattern)
jobctl run yt-batch -- yt-dlp -a urls.txt -o "%(title)s.%(ext)s" --write-info-json

# rsync (incremental backup)
jobctl run backup-photos -- rsync -avh --info=progress2 /src /dst

# ffmpeg encode of a single file (track output growth)
jobctl track-file encode-foo /tmp/out.mp4 --total 2G &
ffmpeg -i in.mkv -c:v libx264 -crf 22 /tmp/out.mp4
wait

# Large dir backup (track recursive size)
jobctl track-file tar-snapshot /mnt/backups/snap.tar --total 50G --interval 60 &
tar -cf /mnt/backups/snap.tar /mnt/photos

# Custom Python script reporting progress
# (in your script:)
#   from urllib.request import Request, urlopen
#   import json
#   def progress(name, current, total=None, msg=None):
#       body = json.dumps({"current": current, "total": total, "msg": msg}).encode()
#       Request(f"http://192.168.0.179:8077/jobs/{name}/progress",
#               data=body, headers={"Authorization": f"Bearer {TOKEN}",
#                                   "Content-Type": "application/json"})
```

---

## API

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /jobs/{id}/start` | bearer | mark job started |
| `POST /jobs/{id}/progress` | bearer | update current progress + msg |
| `POST /jobs/{id}/done` | bearer | mark succeeded/failed (by exit_code) |
| `GET /api/jobs` | none | JSON list of running + recent jobs |
| `GET /` | none | HTML auto-refresh dashboard |
| `GET /_partial/jobs` | none | htmx fragment (cards) |
| `GET /jobs/{id}/tail` | none | last ~50 lines of `log_path` if provided |
| `GET /metrics` | none | Prometheus exposition (for future AlertManager) |
| `GET /healthz` | none | liveness probe |

---

## `jobctl` usage

```sh
# basic
jobctl start NAME [--total N] [--cmd "..."] [--log /path]
jobctl progress NAME CURRENT [--msg "..."]
jobctl done NAME [--exit-code N]

# automatic
jobctl track-file NAME PATH [--total N] [--interval 30]
  # foreground polling loop, stops when file size flat for 5 polls

jobctl pipe-progress NAME [--total N] [--re REGEX]
  # consume stdin, parse out a number per line as current

jobctl run NAME -- <cmd...>
  # wraps a command: start, exec, capture exit, done
```

### Examples

```sh
# Backup a directory and track size growth
jobctl track-file backup-photos /mnt/backups/photos.tar --total 50G &
tar -cf /mnt/backups/photos.tar /mnt/photos
wait
# track-file daemon detects size flat → marks done

# wget with parsed progress
wget --progress=dot:giga ... 2>&1 | jobctl pipe-progress wget-foo --total 12G --re '[0-9]+%'

# Wrap any one-shot command
jobctl run nightly-rsync -- rsync -av /src /dst
```

### Mid-flight tracking (no job restart needed)

```sh
# Started Overpass index manually 30 min ago, want to track it now
jobctl track-file overpass-indexing /mnt/docker/overpass/db/db --total 32G --interval 60 &
```

---

## Compose file

`/mnt/docker/jobsd/compose.yaml`:

```yaml
name: jobsd

services:
  jobsd:
    build:
      context: /mnt/docker/jobsd
      dockerfile: Dockerfile
    container_name: jobsd
    restart: unless-stopped
    ports:
      - "8077:8077"
    volumes:
      - /mnt/docker/jobsd/data:/data
    environment:
      JOBS_DB: /data/jobs.db
      JOBS_TOKEN: ${JOBS_TOKEN:?JOBS_TOKEN must be set in .env}
      TZ: America/Phoenix
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: "0.5"
```

`Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn[standard] jinja2 python-multipart
COPY app /app
EXPOSE 8077
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8077"]
```

`.env`:
```
JOBS_TOKEN=<32-byte hex>
```

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
2. Create `~/.jobsrc` with `JOBS_URL=http://192.168.0.179:8077` and `JOBS_TOKEN=<token>` (chmod 600)
3. Smoke test: `ssh host 'jobctl start hello; jobctl done hello'`

### Rotate token
Tokens are 32-byte hex (256-bit). Distribute via secure channel only.
1. **Generate**: `NEW=$(openssl rand -hex 32); echo "$NEW"`
2. **Server**: edit `/mnt/docker/jobsd/.env` → `JOBS_TOKEN=$NEW`, restart with `docker compose restart jobsd`
3. **Each host**: update `~/.jobsrc` (mode 600) with the new `JOBS_TOKEN=...`
4. **Smoke**: from each host run `jobctl start rotate-test; jobctl done rotate-test --exit-code 0` — appears + completes on dashboard
5. **Rollback** if anything breaks: revert `.env` to old value + restart, revert each `~/.jobsrc`

---

## Disaster recovery

If `/mnt/docker/jobsd/data/jobs.db` is wiped or corrupted, the service rebuilds an empty DB on next start (the `init_db()` function in `app/main.py` runs `CREATE TABLE IF NOT EXISTS`). Just restart:

```bash
ssh root@192.168.0.179 'rm -f /mnt/docker/jobsd/data/jobs.db
cd /mnt/docker/jobsd && docker compose restart jobsd'
```

Historical jobs are lost; running jobs (those with active `jobctl track-file` watchers or that subsequently call `progress`) re-register on their next POST. Existing `~/.jobsrc` tokens stay valid.

If the entire `/mnt/docker/jobsd/` dir is wiped (compose, app, data), restore from git: the source-of-truth for `app/main.py`, `Dockerfile`, `compose.yaml`, and `app/templates/*.html` lives at the runbook reference paths above. Rebuild from those + a fresh `.env` with a new token + run `docker compose up -d --build`.

---

## Querying history (SQLite)

The DB is at `/mnt/docker/jobsd/data/jobs.db` on CT 128. WAL mode, safe to query while service is running.

```sh
# last 7 days of finished jobs
ssh root@192.168.0.179 "sqlite3 /mnt/docker/jobsd/data/jobs.db \
  \"SELECT name, host, status, duration FROM jobs
    WHERE ended_at > strftime('%s','now','-7 days')
    ORDER BY started_at DESC\""

# slowest jobs ever (top 20)
ssh root@192.168.0.179 "sqlite3 /mnt/docker/jobsd/data/jobs.db \
  \"SELECT name, ROUND(duration/60,1) AS mins, status FROM jobs
    WHERE duration IS NOT NULL ORDER BY duration DESC LIMIT 20\""

# rate-over-time for a specific job (for plotting)
ssh root@192.168.0.179 "sqlite3 /mnt/docker/jobsd/data/jobs.db \
  \"SELECT ts, current FROM progress_events
    WHERE job_id = 'overpass-indexing@komodo' ORDER BY ts\""

# how many runs of each named job, success rate
ssh root@192.168.0.179 "sqlite3 /mnt/docker/jobsd/data/jobs.db \
  \"SELECT name, COUNT(*) AS runs,
           SUM(status='succeeded') AS ok,
           SUM(status='failed')    AS fail,
           AVG(duration)           AS avg_sec
    FROM jobs WHERE status<>'running'
    GROUP BY name ORDER BY runs DESC\""
```

---

## Extending the service

To add a new endpoint or change behavior:
1. Source on CT 128 at `/mnt/docker/jobsd/app/main.py` (FastAPI) and `/mnt/docker/jobsd/app/templates/*.html` (Jinja2 + htmx)
2. Edit in place via SSH or scp from a working copy
3. Rebuild + redeploy:
   ```sh
   ssh root@192.168.0.179 'cd /mnt/docker/jobsd && docker compose up -d --build --force-recreate jobsd'
   ```
4. Container logs show import errors immediately if Python is broken: `docker logs jobsd --tail 30`

The dependencies are in `Dockerfile` (`fastapi uvicorn[standard] jinja2 python-multipart`); to add packages, edit Dockerfile and rebuild.

Existing extensions worth wiring later:
- `/metrics` already emits Prometheus exposition; add a Prometheus scrape config + AlertManager rule for `jobsd_job_status==0` to get phone-pingable failure alerts
- Per-job log tail UI panel (the `/jobs/{id}/tail` endpoint exists; just needs frontend wiring)
- Webhook-out on done (POST to ntfy / Discord / etc on completion) — single function in `done()` handler

---

## Schema (SQLite)

```sql
CREATE TABLE jobs (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  host        TEXT,
  cmd         TEXT,
  log_path    TEXT,
  total       REAL,
  current     REAL DEFAULT 0,
  msg         TEXT,
  status      TEXT DEFAULT 'running',     -- 'running' | 'succeeded' | 'failed'
  exit_code   INTEGER,
  started_at  REAL,                        -- unix epoch
  updated_at  REAL,
  ended_at    REAL,
  duration    REAL                         -- seconds
);

CREATE TABLE progress_events (
  job_id   TEXT NOT NULL,
  ts       REAL NOT NULL,
  current  REAL NOT NULL
);
```

`progress_events` is pruned to most-recent 200 per job to keep DB compact.

Job ID convention: `<slug-of-name>@<short-hostname>` (host-scoped). `jobctl id NAME` echoes it.

---

## UI features

- Mobile-first responsive (single column, big bars)
- Auto-refresh every 2 sec via htmx
- Progress bar color: blue=running, green=succeeded, red=failed, amber=stalled (>10 min no update)
- Per-job: rate (B/s, MB/s), ETA, last-N-runs sparkline (history of completed runs of same `name`)
- Recent succeeded jobs visible for 24 hr then drop off

---

## Future work

- AlertManager → ntfy webhook for failed/stalled jobs (AlertManager has empty receivers; would also light up MountRO/DiskSpace/etc rules)
- Per-job log tail panel inline (currently a separate `/jobs/{id}/tail` endpoint)
- Authentik SSO if exposing externally
- Grafana dashboards via the `/metrics` endpoint for "this job vs historical runs" graphs

---

## Troubleshooting

**`jobctl: command not found` from `pct exec`** — `/usr/local/bin` not in non-login shell PATH. Use `/usr/local/bin/jobctl` explicitly.

**500 on `/_partial/jobs`** — likely a Jinja template error. `docker logs jobsd` shows the trace. Templates are server-rendered and cached; rebuild with `docker compose up -d --build`.

**Job "stuck" running** — usually because the `jobctl track-file` watcher process died (shell closed before it auto-completed). Two fixes:
- Manual close: `jobctl done NAME --exit-code 0` from any host (host-scoped IDs — use `jobctl id NAME` to confirm exact ID)
- Find + kill orphan watcher: `ps -ef | grep "jobctl track-file NAME"; kill <pid>` then `jobctl done NAME`
- For long jobs that outlive a shell: run watchers in `tmux new-session -d -s "watch-NAME" 'jobctl track-file NAME …'` so they survive disconnection

**Watcher detached too early** — `track-file` exits when file size is flat for 5 polls. For jobs with long pauses (e.g., osmium fileinfo phase between steps), use longer interval: `--interval 120`.

**Wrong size on directory tracking** — confirm that path is a directory; `jobctl track-file` uses `du -sb` for dirs vs `stat` for files. If you see flat 4096 bytes for a dir, the version of jobctl is pre-fix; redeploy from `/mnt/docker/jobsd/jobctl`.

**`401` from POSTs** — `~/.jobsrc` token doesn't match `/mnt/docker/jobsd/.env`. Re-sync.

**DNS doesn't resolve `jobs.home` from a host** — that host isn't using AdGuard for DNS. Use `192.168.0.179:8077` directly.
