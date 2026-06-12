# Stock Screener — Swing-Trade Candidates + Backtester

**Last Updated**: 2026-06-12
**Related Systems**: CT 128 (Komodo), Alpaca paper account, jobs.home, Trailhead

## Summary
Nightly EOD screener for short-term (2–15 day hold) US-equity swing candidates, with a trade-level backtester. Signal spec was produced by two multi-agent evidence reviews — every rule is either backed by a published backtest (Alvarez/QuantifiedStrategies/academic) or explicitly flagged untested. Live at `http://192.168.0.179:8087` (Trailhead card "Stock Screener"; `screener.home` pending an NPM proxy-host entry).

## Strategy (spec v3, condensed)
Both modes: **buy weakness in quality stocks, sell the first bounce, no tight stops.**

- **Mode A — trend pullback**: close>SMA100, top-quintile 126d return (skip last 5d), 3 consecutive lower lows + close<SMA5.
- **Mode B — mean reversion**: close>SMA100, RSI(2)<5, IBS<0.25, skip if ≥5% gap-down in last 10d.
- **Entry (both)**: next-day LIMIT at `close − 0.5×ATR(10)`.
- **Exit (both)**: first close > prior close → sell next open. Time stop A=10d, B=5d. **No price stops** (published evidence: stops hurt this trade type).
- **Regime**: SPX>200dSMA confirmed 3 closes = risk-on; VIX/VIX3M>1 (backwardation) = hard risk-off; breadth shown as context.
- Full reviewed spec with citations: session plan `multi-agents-review-all-zesty-pine.md` (CT 124 `~/.claude/plans/`).

## Architecture
- **Stack**: `/etc/komodo/stacks/screener/` (compose + Dockerfile + `.env` with Alpaca keys, mode 600)
- **Code**: `/mnt/docker/screener/code/` — `config.py`, `store.py` (SQLite), `universe.py` (Wikipedia S&P500+400 scrape, hardened), `fetch.py` (yfinance primary / Alpaca fallback behind one interface), `indicators.py` (plain pandas — deliberately not pandas-ta), `signals.py`, `screener.py`, `backtest.py`, `nightly.py`, `backfill.py`, `webui.py` (Flask)
- **Data**: `/mnt/docker/screener/data/screener.db` (SQLite: prices 2016→now, universe snapshots, fetch log) + `data/screens/*.json`
- **Container**: `screener` (python:3.12-slim), `network_mode: bridge` — **CT 128's Docker address pools are exhausted; new compose networks fail**
- **Web UI**: container port 8086 → host **8087** (8086 taken)
- **Cron**: `/etc/cron.d/screener` — 03:30 UTC Tue–Sat: `nightly.py` (fetch+sanity) then `screener.py` (signals→JSON), jobctl-wrapped → jobs.home

## Data sources (free tier)
- **yfinance 0.2.66** primary: batched chunks of 100, jittered sleeps, exponential backoff
- **Alpaca Basic** (paper keys, account PA33VYMAOFTV): fallback + 2016→now backfill. SIP daily bars, `adjustment=all`. **Free tier 403s on data <15 min old** — `fetch.py` caps `end` at now−16min. Symbols: Alpaca uses `BRK.B`, store uses `BRK-B` (Yahoo style)
- Earnings intentionally degraded (yfinance-only, no extra signups — user decision)

## Verification
```bash
# from CT 128
docker exec screener python universe.py     # expect sp500=~503 sp400=~400
docker exec screener python nightly.py      # expect coverage ≥95%
docker exec screener python screener.py     # writes data/screens/latest.json
curl -s localhost:8087/api/latest | head    # UI/API serving
docker exec screener python backtest.py mode_b 2017-01-01 2026-06-12
```
Backtest sanity anchor: mode B should show ~55–65% win, ~+0.2–0.5%/trade pre-cost. Materially exceeding published numbers (=0.5–0.9% pre-decay) indicates a bug, not alpha. Ignore the compounded "total%" line (per-trade compounding, not a portfolio sim).

## Troubleshooting
- **All SMA/ATR suddenly NaN, zero candidates**: a sparse date row (e.g. lone ^VIX bar on a market holiday) inside the rolling window. `build_frames` drops dates with <100 tickers; if it recurs check `store.load_wide('close').notna().sum(axis=1)` and `DELETE FROM prices WHERE date='<bad>'`.
- **Coverage <95% / STALE flag in UI**: Yahoo outage. Alpaca fallback should cover; check `/tmp/screener-nightly.log` and fetch_log table.
- **403 from Alpaca**: requesting data newer than 15 min (free tier) — should be impossible via `fetch.py`; check the end-cap logic.
- **Trailhead card edits**: editing `trailhead.yaml` with `sed -i` breaks the file bind-mount (new inode) — `docker restart trailhead-generator` after in-place edits.

## Pending / future
- NPM proxy host `screener.home` / `screener.1701.me` → `192.168.0.179:8087` (needs NPM admin)
- Validation suite v2: per-filter ablation, point-in-time universe (fja05680/sp500), portfolio sim with position caps, Monte Carlo
- NWS/NWSA-style dual-class dedupe; Stooq bulk import for pre-2016 history
- Possible later phase: Alpaca paper-trading to measure real fills (same account/keys)
