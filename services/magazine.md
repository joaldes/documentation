# The Curious — Self-Writing Fun-Fact Magazine

**Last Updated**: 2026-07-14
**Related Systems**: CT 128 (Komodo/Docker), jobs.home, Trailhead, AdGuard (CT 101)

## Summary
A personal web magazine staffed by a four-agent Claude editorial team. Every night it
researches, writes, fact-checks, and publishes one well-sourced fun-fact article from a
user-authored taxonomy, and it accepts on-demand custom story requests. Live at
`http://magazine.home:8089` (also `192.168.0.179:8089`).

## Problem / Goal
Produce genuinely surprising, *trustworthy* fun-fact articles automatically — without the
"confident wrong fact" failure mode that plagues LLM content and the fun-fact genre.

## Solution
Four agents run sequentially per article (Claude Agent SDK driving the `claude` CLI as a
subprocess, authenticated with a **long-lived Claude Max setup-token** (`CLAUDE_CODE_OAUTH_TOKEN`
in the stack `.env`, generated with `claude setup-token`, ~1-year lifetime) — no API key):

1. **Editor (pick)** — chooses a topic + specific angle from `taxonomy.yaml`, avoiding recent topics.
2. **Researcher** — WebSearch; must surface a primary source, a disputed claim, a specific
   number/quote, and a non-empty "surprises" list.
3. **Writer** — drafts it; every factual sentence carries an inline `[S#]` source tag; no tools
   (can't invent sources); banned-phrase list; word budget set by the Editor.
4. **Editor (claim-freeze)** — extracts the central claims *before* fact-check so the verifier
   can't self-scope.
5. **Fact-Checker** — WebSearch; adversarially tries to **disprove** each central claim with
   fresh independent searches, myth-checks, provenance tracing, and a `trusted-sources.yaml`
   allowlist. 3-tier verdict (confirmed/unconfirmed/refuted).
6. **Editor (release)** — rubric score + independent payoff check, then publishes.

**Correct-first policy:** wrong peripheral claims are corrected (and re-verified), not discarded.
If the *core premise* is a myth, the piece **pivots** to a myth-buster when the debunk is itself
surprising, else it's **spiked**. Nothing unverified is ever published. Spiked pieces and the
Fact-Checker's reasoning are visible at `/spiked` (audit trail).

**Revision budget & convergence gate (`agents.MAX_REVISIONS`, default 4):** the correct→re-check
loop runs up to `MAX_REVISIONS` rounds. Because the adversarial Fact-Checker on a capable model
almost always finds *one more* minor nit on fact-dense topics (dates, dollar figures, sourcing to
non-allowlisted domains), a strict "zero corrections remaining" gate would spike nearly every
article. So after the budget is exhausted the pipeline applies one final correction round and then
**grace-exits to the Editor's release pass** (the holistic final gate) instead of spiking on the
Fact-Checker's residual nits — see the `revision_count > MAX_REVISIONS` grace-exit in
`orchestrator.py`. The Editor, not the nitpicky verifier, has the final say.

**Model is pinned (`agents.MODEL`):** the agents are launched with an explicit `model=` in
`ClaudeAgentOptions`. Left unset they inherit the bundled `claude` CLI's default, which silently
drifts on every CLI auto-update — a newer, stricter Fact-Checker is what stalled nightly publishing
right after the 2026-07-12 auth restore (2 weeks of blackout masked a model upgrade; the June
`MAX_REVISIONS=2` was calibrated for the older, less-pedantic model). Pin keeps fact-check
strictness and article quality reproducible; bump it deliberately when you want a newer model.

Sources are archived locally (the agent's actual search snippet as the authoritative record,
plus best-effort httpx HTML + Chromium full-page PDF) against link rot. Hero images are fetched
open-license (Wikimedia Commons → Unsplash) with attribution.

## Architecture
- **Stack**: `/etc/komodo/stacks/magazine/compose.yaml` (+ `.env`), built from `/mnt/docker/magazine/code/`.
- **Data**: `/mnt/docker/magazine/data/` — `magazine.db` (SQLite, WAL) + `articles/<slug>/`
  (markdown, `hero.*`, `sources/`).
- **Config (edit via Samba)**: `/mnt/docker/magazine/taxonomy.yaml`, `trusted-sources.yaml`.
- **Auth**: `CLAUDE_CODE_OAUTH_TOKEN` in `/etc/komodo/stacks/magazine/.env` (long-lived Max
  setup-token, ~1yr). `claude-home/` is still mounted at `/root/.claude` but only holds CLI
  settings/history — no credentials. ⚠ **Cron strips docker env**, so `entrypoint.sh` re-declares
  the token inside `/etc/cron.d/magazine`; without that line every nightly 401s while interactive
  `docker exec` works fine (the 2026-06-27→07-12 outage).
- **Port**: 8089 → `magazine.home` (AdGuard rewrite).
- **Schedule**: in-container cron at `NIGHTLY_HOUR` (TZ-aware), wrapped in `jobctl run magazine-nightly`.

### Key files
- `code/orchestrator.py` — pipeline, leasing, resume, revision loop, usage budget, auth detection.
- `code/agents.py` — the six system prompts + output JSON schemas; also `MODEL` (pinned model id)
  and `MAX_REVISIONS` (convergence budget).
- `code/archive.py` — background source archiving + hero image.
- `code/app.py` — FastAPI + server-rendered frontend.

## Operations
```bash
# Manually trigger an article (from CT 128):
curl -X POST http://localhost:8089/run/nightly

# One-off from CLI inside the container:
docker exec magazine python orchestrator.py --nightly
docker exec magazine python orchestrator.py --custom "Why is the speed of light what it is?"

# Re-auth if articles show 'auth_expired' (token revoked/expired, ~yearly):
#   1. claude setup-token   (any machine; approve in browser, copy sk-ant-oat01-...)
#   2. put it in /etc/komodo/stacks/magazine/.env as CLAUDE_CODE_OAUTH_TOKEN=...
#   3. docker compose up -d --force-recreate   (re-runs entrypoint -> new cron env)
# Then requeue the stuck rows — --resume skips 'auth_expired', and janitor() fails
# rows whose updated_at is >12h old, so the timestamp bump is REQUIRED:
docker exec magazine python -c "import sqlite3; c=sqlite3.connect('/data/magazine.db'); \
c.execute(\"UPDATE articles SET status='picking', owner=NULL, lease_until=NULL, \
spike_reason=NULL, updated_at=datetime('now') WHERE status='auth_expired'\"); c.commit()"
docker exec -d magazine sh -c 'cd /app && python orchestrator.py --resume >> /data/cron.log 2>&1'

# Logs / cron log:
docker logs magazine
docker exec magazine cat /data/cron.log
```

## Verification
- `docker exec magazine claude -p "say hi"` → completes (Max subprocess auth works).
- `POST /run/nightly` → watch phases on jobs.home; an article reaches `published`.
- `/spiked` shows rejected pieces + Fact-Checker reasons.

## Troubleshooting
- **`auth_expired` articles** → the setup-token was revoked/expired; regenerate per the
  Operations re-auth steps above. If `claude -p "say hi"` works interactively but nightlies
  still 401, the token is missing from `/etc/cron.d/magazine` (cron-env trap) — recreate the
  container so `entrypoint.sh` rewrites the cron file.
- **No hero images** → Wikimedia returned nothing and no `UNSPLASH_KEY` set; harmless (text-only).
- **Chromium/PDF failures** → archiving is best-effort and never blocks publishing; check
  `/dev/shm` (`shm_size: 512m` in compose) and `--no-sandbox` flags.
- **Empty magazine / lots of spikes** → tighten or loosen `trusted-sources.yaml`; review `/spiked`.
- **Spikes reading `fact-check corrections did not converge`** → the adversarial Fact-Checker keeps
  returning `recommendation:"correct"` with residual nits until the revision budget runs out. First
  confirm it's *not* auth (interactive `docker exec magazine claude -p "hi"` returns text, and
  `cron.log` has no fresh `AuthError` — the jobctl "spiked" message can mask a 401). If auth is fine,
  it's the convergence gate: (1) verify `agents.MODEL` is pinned so behavior is reproducible; a CLI
  auto-update can make the checker abruptly stricter. (2) Raise `agents.MAX_REVISIONS` and/or rely on
  the grace-exit-to-Editor (see the Revision-budget note above). This exact failure mode stalled
  publishing 2026-07-13→14: fixed by pinning the model (`claude-sonnet-4-6`), `MAX_REVISIONS 2→4`,
  and the grace-exit. Restart the container after editing (`code/` is bind-mounted `:ro`, no rebuild).

## Morning Telegram integration (live 2026-06-01)

The day's article appears at the bottom of Alec's existing morning Telegram from Node-RED, formatted as a newspaper card with a tappable headline.

### Endpoint
- `GET http://192.168.0.179:8089/api/today` → `{available, slug, title, dek, published_at, url, magazine_url}` (latest published article; `available:false` when none).

### Node-RED wiring
Live tab: "Daily Messages" (`88ecaf824ac715f2`). A new branch hangs off fan-out junction `63b3f47ca49fc3ce` parallel to the weather/calendar/etc. branches:
1. **`mag-http-…`** — HTTP request `GET /api/today`, `senderr:true`, `reqTimeout:5000` (fail-open: empty response if magazine is down → no broken morning message).
2. **`mag-fmt-…`** — function: sets `msg.topic="magazineArticle"`, builds the formatted block wrapped in boundary markers `XCURIOUSBEGINX…XCURIOUSENDX`. Title and dek are MarkdownV2-escaped; URL is a slug so no defensive escape needed. Empty string when no article.
3. **`mag-lout-…`** — `link out` named "Daily Message Internal Routing Out", targeting link-in `4a3196f0754961ec`, which feeds join `c910776fe7d2cd7a` (custom-object, key=topic, **count bumped 7 → 8**).
4. Notify function `e83bcedb75f50bb3` appends `${magazineArticle}` to the morning message; `weatherSynopsis` trailing whitespace is trimmed so spacing collapses to a single blank line.

### Escape-bypass for the inline link
The Notifications tab (`1729cdf8.53b912`) has a global escape change-node `68f42f2070d6cb22` that unconditionally escapes MarkdownV2 special chars (`[ ] ( ) ~ ` > # + - = | { } . !`) on `msg.payload.content`. That breaks inline-link syntax. Two new functions on the same tab bypass it for the magazine block only:
- **`mag-extract-…`** wired *before* the escape: regex-extracts the marker-wrapped block from `msg.payload.content`, stashes the inner string on `msg.curiousBlock`, replaces the span with sentinel `XCURIOUSPLACEHOLDERX` (no escape-list chars).
- **`mag-restore-…`** wired *after* the escape: substitutes the sentinel back with `msg.curiousBlock`, preserving the pristine `[title](url)` syntax.

Chain after rewire: Set Message `f9244b6b.62c6d8` → extract → escape → restore → telegram sender `72d3ecbb.ea2f44`.

### Bonus fix: weather on manual `resend_sunrise_message`
The native sunrise trigger node `b0d8d648a8376b38` wires to BOTH the junction and the weather service-call `402ffc5b1e3060a2` (`weather.get_forecasts` on `weather.pirateweather`). The manual resend path entered via link-in `fc7eefa6c66bc925` only fed the junction, so weather was always `*__Weather is currently unavailable__*`. Fix: added `402ffc5b1e3060a2` to that link-in's wires so manual triggers also fire the weather fetch.

### Rendered block
```
📰 *The Curious*  (bold + underlined)
[Born Before Bach](http://192.168.0.179:8089/article/born-before-bach-…)  (tappable title)
_A vertebrate that hits puberty at 150…_  (dek in italics)
```

### Deploy / re-deploy
- All Node-RED edits done via the admin API (`http://192.168.0.154:1880`, open on LAN). No restart needed for flow deploys.
- Magazine endpoint changes (`/api/today` shape) require restarting the magazine stack: `docker compose restart magazine` on CT 128.
