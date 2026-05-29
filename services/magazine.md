# The Curious — Self-Writing Fun-Fact Magazine

**Last Updated**: 2026-05-29
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
subprocess, authenticated with a **dedicated in-container Claude Max login** — no API key):

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

Sources are archived locally (the agent's actual search snippet as the authoritative record,
plus best-effort httpx HTML + Chromium full-page PDF) against link rot. Hero images are fetched
open-license (Wikimedia Commons → Unsplash) with attribution.

## Architecture
- **Stack**: `/etc/komodo/stacks/magazine/compose.yaml` (+ `.env`), built from `/mnt/docker/magazine/code/`.
- **Data**: `/mnt/docker/magazine/data/` — `magazine.db` (SQLite, WAL) + `articles/<slug>/`
  (markdown, `hero.*`, `sources/`).
- **Config (edit via Samba)**: `/mnt/docker/magazine/taxonomy.yaml`, `trusted-sources.yaml`.
- **Auth**: `/mnt/docker/magazine/claude-home/` mounted to `/root/.claude` (dedicated Max session).
- **Port**: 8089 → `magazine.home` (AdGuard rewrite).
- **Schedule**: in-container cron at `NIGHTLY_HOUR` (TZ-aware), wrapped in `jobctl run magazine-nightly`.

### Key files
- `code/orchestrator.py` — pipeline, leasing, resume, revision loop, usage budget, auth detection.
- `code/agents.py` — the six system prompts + output JSON schemas.
- `code/archive.py` — background source archiving + hero image.
- `code/app.py` — FastAPI + server-rendered frontend.

## Operations
```bash
# Manually trigger an article (from CT 128):
curl -X POST http://localhost:8089/run/nightly

# One-off from CLI inside the container:
docker exec magazine python orchestrator.py --nightly
docker exec magazine python orchestrator.py --custom "Why is the speed of light what it is?"

# Re-auth the Max session if articles show 'auth_expired':
docker exec -it magazine claude   # then /login, follow device-code flow

# Logs / cron log:
docker logs magazine
docker exec magazine cat /data/cron.log
```

## Verification
- `docker exec magazine claude -p "say hi"` → completes (Max subprocess auth works).
- `POST /run/nightly` → watch phases on jobs.home; an article reaches `published`.
- `/spiked` shows rejected pieces + Fact-Checker reasons.

## Troubleshooting
- **`auth_expired` articles** → the Max token lapsed; re-run `claude` login in the container.
- **No hero images** → Wikimedia returned nothing and no `UNSPLASH_KEY` set; harmless (text-only).
- **Chromium/PDF failures** → archiving is best-effort and never blocks publishing; check
  `/dev/shm` (`shm_size: 512m` in compose) and `--no-sandbox` flags.
- **Empty magazine / lots of spikes** → tighten or loosen `trusted-sources.yaml`; review `/spiked`.
