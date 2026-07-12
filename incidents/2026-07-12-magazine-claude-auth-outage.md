# Magazine (The Curious) — 15-Day Nightly Publishing Outage (Claude Auth)

**Last Updated**: 2026-07-12
**Related Systems**: CT 128 (Komodo/Docker), `magazine` container, magazine.home:8089, jobs.home
**Duration**: 2026-06-28 → 2026-07-12 (15 missed nightly articles)

## Summary
The magazine's nightly Claude pipeline failed every night for 15 days with
`401 Invalid authentication credentials`. Root cause had two layers: the container's
dedicated Claude Max OAuth session died (~Jun 27), and the Jul 6 remediation — a
long-lived `CLAUDE_CODE_OAUTH_TOKEN` in the stack env — never reached the nightly job
because **in-container cron strips docker environment variables**. Interactive tests
passed while every cron run kept failing, so the outage looked fixed on Jul 6 but wasn't.
Fully resolved 2026-07-12; all 15 stuck articles requeued.

## Timeline (Phoenix time)
| When | What |
|------|------|
| 2026-06-27 | Last successful publish (#47, "Egyptian Blue"). Max OAuth session dies afterward. |
| 06-28 → 07-06 | Nightly runs #48–58 all fail at agent turn 1 → `auth_expired` (11 articles). |
| 2026-07-06 | Partial fix deployed: `CLAUDE_CODE_OAUTH_TOKEN` added to compose + `.env` (backups `*.bak-2026-07-06`). Manually triggered runs #59–61 authenticate fine (spiked later by fact-check — unrelated quality issue), so the fix *appears* to work. |
| 07-09 → 07-12 | Nightly **cron** runs #62–65 keep failing 401 — cron never sees the env token. |
| 2026-07-12 ~2:10 PM | Diagnosed: `claude -p "say hi"` via `docker exec` succeeds (inherits env) while `/data/cron.log` shows nightly 401s; `/etc/cron.d/magazine` contained no token. |
| 2026-07-12 ~2:20 PM | Fix deployed (entrypoint cron-env injection), container recreated, 15 articles requeued, backlog resume running. |

## Root Cause
1. **Original failure**: the dedicated in-container Claude Max login (`claude-home/.credentials.json`)
   stopped refreshing ~Jun 27; the CLI returned `API Error: 401 Invalid authentication credentials`.
2. **Why the Jul 6 fix didn't take**: the nightly job is launched by cron *inside* the container
   (`/etc/cron.d/magazine`, written by `entrypoint.sh`). Cron jobs get only the env declared in the
   cron file (`SHELL/PATH/HOME/TZ`) — not the container's docker `environment:` — so the orchestrator's
   `claude` subprocess fell back to the dead credentials file. Anything run via `docker exec` or the
   FastAPI `/run/nightly` endpoint inherited the token and worked, which masked the problem.
3. **Why it lasted 15 days**: the failure was silent — `auth_expired` rows only surface on the
   `/queue` page, and no alerting watches the magazine's publish cadence.

## Resolution
1. `entrypoint.sh` now re-declares `${CLAUDE_CODE_OAUTH_TOKEN}` inside `/etc/cron.d/magazine`
   (conditional — omitted if unset). Also removed a `crontab /etc/cron.d/magazine` line that had been
   installing a malformed duplicate (system-crontab format fed to a user crontab) — harmless but confusing.
2. Dead credentials parked: `claude-home/.credentials.json` → `.credentials.json.bak-2026-07-12`.
   Auth is now solely the env token (~1-year lifetime; regenerate with `claude setup-token`).
3. Container force-recreated (`docker compose up -d --force-recreate` from
   `/etc/komodo/stacks/magazine/`) so the new entrypoint rewrote the cron file.
4. All 15 `auth_expired` rows requeued. **Two traps** (now in the service doc):
   - `orchestrator.py --resume` deliberately skips `auth_expired` rows — they must be UPDATEd back to `'picking'`.
   - `janitor()` fails any non-terminal row with `updated_at` >12h old, so the requeue must also set
     `updated_at=datetime('now')`. (First requeue attempt omitted this and all 15 were insta-failed.)
   ```bash
   docker exec magazine python -c "import sqlite3; c=sqlite3.connect('/data/magazine.db'); \
   c.execute(\"UPDATE articles SET status='picking', owner=NULL, lease_until=NULL, \
   spike_reason=NULL, updated_at=datetime('now') WHERE status='auth_expired'\"); c.commit()"
   docker exec -d magazine sh -c 'cd /app && python orchestrator.py --resume >> /data/cron.log 2>&1'
   ```

## Verification
- `/etc/cron.d/magazine` contains the `CLAUDE_CODE_OAUTH_TOKEN=` line after recreate.
- `docker exec magazine claude -p "say hi"` completes.
- Backlog resume observed working end-to-end: first requeued article progressed
  pick → research → draft → fact-check → revision under the new auth.
- Full drain of the 15-article backlog was still in progress at time of writing
  (serialized, ~25–70 agent turns each); tonight's 2:00 AM cron will also exercise the fixed path.

## Key Files Modified
- `/mnt/docker/magazine/code/entrypoint.sh` (CT 128) — cron-env token injection; `.bak-2026-07-12` kept.
- `/mnt/docker/magazine/claude-home/.credentials.json` → parked as `.bak-2026-07-12`.
- `magazine.db` — 15 rows requeued.
- Docs synced same pass: `services/magazine.md` (auth model, cron-env trap, requeue SQL) +
  build-copy `compose.yaml`/`env`/`magazine.md` on CT 124.

## Lessons / Prevention
- **Cron ≠ container env.** Any in-container cron job needing a secret must have it re-declared in
  the cron file (or sourced from a file). Verify fixes through the *same execution path* that failed —
  a `docker exec` test does not validate a cron job.
- The token is long-lived but not eternal (~1 year). Re-auth runbook is in `services/magazine.md`.
- Open gap: no alerting on missed publishes — `auth_expired`/silent-failure states are only visible
  on `/queue`. A cheap watchdog (e.g. morning Telegram flag when `/api/today` is stale >2 days) would
  have caught this on day 2 instead of day 15. Not implemented; noted as an option.
