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
1. Generate new: `openssl rand -hex 32`
2. Edit `/mnt/docker/jobsd/.env`, restart jobsd
3. Edit `~/.jobsrc` on every host

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

**Job "stuck" running** — track-file watcher process died (e.g. shell closed). Manually `jobctl done NAME` to mark complete, or restart the watcher.

**`401` from POSTs** — `~/.jobsrc` token doesn't match `/mnt/docker/jobsd/.env`. Re-sync.

**DNS doesn't resolve `jobs.home` from a host** — that host isn't using AdGuard for DNS. Use `192.168.0.179:8077` directly.
