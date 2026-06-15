# TTS on foundry — Pocket TTS · Kokoro · XTTS-v2 · Voice Studio (+ Athena/Majel pipeline)

**Last Updated**: 2026-06-15
**Related Systems**: CT 130 "foundry" (192.168.0.130) — three CPU TTS engines behind one Voice Studio,
Komodo-managed, Trailhead (AI - Foundry group), documents samba (tts)

## Engines at a glance
| Engine | Port | Role | Cloning | Speed (CPU) |
|---|---|---|---|---|
| **Pocket TTS** (Kyutai, 100M) | 8001 | fast zero-shot cloning; hosts the Voice Studio UI | yes (zero-shot) | ~3× realtime (fastest) |
| **Kokoro** (82M, remsky) | 8880 | 67 preset voices + blend builder | no (blend only) | ~1.7× realtime |
| **XTTS-v2** (Coqui/idiap) | 8002 | most natural + multilingual cloning | yes (zero-shot, 17 langs) | ~0.35× realtime (slowest, heaviest) |

The **Voice Studio** (`http://192.168.0.130:8001/`) is the single UI over all three — tabs *Pocket TTS*
/ *Kokoro Blend* / *XTTS Clone*, sharing one text box, player, and clips panel.

## Deployment / source of truth
- All three stacks are **Komodo-managed, "Files on Host"** at `/mnt/docker/<name>/` (registered 2026-06-15
  on the foundry server) — same as every other homelab stack; manage via the Komodo UI. **No git** (no
  homelab stack uses it; durability rides on system backups — note `/mnt/docker` backup coverage is a
  known homelab-wide gap, tracked separately).
- The only hand-authored code is Pocket TTS's overlay: `/mnt/docker/pocket-tts/app/main.py` (de-conflated
  out of the vendored Kyutai clone 2026-06-15) + `/mnt/docker/pocket-tts/studio/index.html`, both
  bind-mounted into the container; one `.bak` kept per file. The vendored clone is now only the build
  context. **Edit → `docker compose up -d --force-recreate`** (or redeploy in Komodo).
- **Shared assets** live in the documents samba at `…/claudeai/tts/` (renamed from `athena-voice/`
  2026-06-15 to match the project), organized **per voice** (2026-06-15):
  - `reference/` = cloneable voices, **bind-mounted `/refs`, kept FLAT** (the studio globs it
    non-recursively + clones via `/refs/<name>`, so this stays a flat dir — do not nest it).
  - `studio/` = generated clips, bind-mounted `/out`, sorted `<engine>/<voice>/`.
  - `voices/<persona>/` = each voice's **source material + metadata**: `voices/athena/` and
    `voices/majel/` hold `source-clips/` (the SDH cue-rips), `<persona>_cues.csv`, plus Majel's
    `majel_scores.csv` and Athena's `expressiveness-samples/`. Not load-bearing.
  - `tools/` = the extraction/bakeoff scripts (`extract_athena.py`, `bakeoff.py`).
  - `tts-bench/` = cross-engine benchmarks + `results.md`.
  Both bind-mounted stacks (pocket-tts, xtts) point at `…/tts/reference` + `…/tts/studio`.

## Summary
Kyutai Pocket TTS (100M-param CALM model, MIT) runs CPU-only on foundry and provides
high-quality zero-shot voice cloning at ~3× real-time. Deployed 2026-06-10 after a
bake-off against NeuTTS Air (retired same day — lost on voice quality by ear, after its
community fork needed four builds to even boot). The marquee use: the **USS Athena ship's
computer voice** from *Star Trek: Starfleet Academy*, extracted from the Emby library via
SDH subtitle mining.

## Service

| | |
|---|---|
| Endpoint | `http://192.168.0.130:8001` — Swagger UI at `/docs`, health at `/health` |
| Stack | `/mnt/docker/pocket-tts/compose.yaml` (own compose project, image built from `./pocket-tts` clone of github.com/kyutai-labs/pocket-tts) |
| Container | `pocket-tts`, 2 CPUs / 2g cap, **no iGPU** (deliberate — Ollama owns the Iris Xe) |
| Model cache | `/mnt/docker/pocket-tts/cache/huggingface` (bind mount — survives rebuilds) |
| Voices dir | `/mnt/docker/pocket-tts/voices` (for exported .safetensors voices) |

### API usage
```bash
curl -X POST http://192.168.0.130:8001/tts \
  -F "text=Warning. Hull breach on deck seven." \
  -F "voice_wav=@athena_urgent.wav" \
  -F "temperature=0.9" -F "decode_steps=1" \
  -o out.wav
```
Fields: `text` + (`voice_wav` upload | `voice_url`) + optional **expressiveness params**
`temperature` / `decode_steps` / `eos_threshold`. Output: 24kHz mono PCM WAV.
Warm generation ≈ 1–4s per sentence on foundry's CPU.

### Expressiveness patch (2026-06-13)
Stock `/tts` exposed no sampling controls. The model's `temp`, `lsd_decode_steps`,
`eos_threshold` are live-mutable instance attributes read at sampling time (verified in
`models/tts_model.py` `_sample_next_latent`), so `/tts` was patched to accept them as optional
Form fields and mutate the **already-loaded** global model per-request (under a lock, restored in
`finally`) — no reload. Defaults unchanged when omitted (temp 0.7 / steps 1 / eos −4.0).
- Higher **temperature** (0.8–1.0) = more prosodic variation/emotion; too high = artifacts.
  Lower = flatter, rock-stable. **Reference audio is the bigger lever** — cloning copies the
  reference's prosody, so a deadpan computer ref yields a deadpan read by design.
- **decode_steps** >1 = richer/smoother at ~linear CPU cost. **eos_threshold** tunes trailing.
- Deployed rebuild-free: patched `main.py` is **bind-mounted** over `/app/pocket_tts/main.py`
  from `/mnt/docker/pocket-tts/app/main.py` (de-conflated 2026-06-15 — see "Deployment / source of
  truth" above); a `docker compose up -d --force-recreate` (one warm load) applies it. One `.bak` kept
  per hand-authored file.

## Voice Studio (web UI — folded into Pocket TTS)
`http://192.168.0.130:8001/` — pocket-tts's own root page **is** the studio: pick a voice, dial
temperature/decode-steps/EOS, type text, generate, play in-browser. Every clip is **sorted on
disk by engine + input voice**: `tts/studio/<engine>/<voice>/<stem>.wav` (2026-06-15) — e.g. a
Pocket clip of `athena_calm` lands at `studio/pocket/athena_calm/athenaCalm_t0.9_s1.wav`. The
stem keeps the spec name (`{vkey}_t{temp}_s{steps}`); on collision a counter is appended
(`…_s1_2.wav`). The clips panel lists clips newest-first, grouped under an `engine · voice`
header, with inline players + a delete ✕ (deleting also prunes the now-empty voice/engine dir).
- Voice picker = the custom references in `tts/reference/` **+** the 26 built-in Kyutai
  voices (alba, estelle, …, passed through as `voice_url`).
- Implemented as extra FastAPI routes in pocket-tts `main.py` (`GET /`, `/voices`, `/clips`,
  `/clips/{name:path}` GET+DELETE+promote — `:path` so nested `engine/voice/file.wav` matches,
  `POST /generate`). `/clips` walks the tree (`rglob`) and returns each clip's relative path +
  split-out `engine`/`voice`; writes go through one `_resolve_out(engine, voice_slug, stem)`
  helper. The page is bind-mounted
  (`studio/index.html` → `/app/pocket_tts/static/studio.html`); generation reuses the loaded model
  under the same `_gen_lock`, saving via `stream_audio_chunks` to `/out`.
- **CT 130 now mounts the documents samba** (added 2026-06-13): `mp5: /mnt/documents,mp=/mnt/documents`
  in `/etc/pve/lxc/130.conf`. This was required for the fold-in (so foundry can read
  `reference/` and write `studio/`) and needed a one-time CT 130 reboot to apply (mp hotplug
  doesn't take; the reboot bounces ollama/open-webui/searxng/kokoro — they auto-recover). compose
  binds: `…/reference:/refs:ro` and `…/studio:/out`.
- An earlier interim build hosted the same UI as a standalone Flask app on CT 124 (port 8088); that
  was retired once the fold-in was verified (the documents-mount approach was chosen instead).

### Kokoro blend — second engine in the studio (2026-06-14)
The studio is **multi-engine** (Pocket TTS | Kokoro Blend | XTTS Clone — see the XTTS section for the
third tab): an engine switch above the shared
text box / result player / clips panel. The Kokoro tab is a **voice-blend builder** — add any of the
67 Kokoro voices, give each a `+`/`−` sign and a relative weight, set speed, generate. It leverages
Kokoro's own blend config: the `voice` string `af_jadzia(2)+af_sarah(1)-am_adam(0.5)` (additive `+`,
subtractive `−`, parenthesized weights **auto-normalized to sum 1** by kokoro-fastapi). The UI shows a
live "effective mix %" and the literal blend string. Scope is **audition + save only** — no
promote-to-Pocket-reference button yet (the blend→clone-for-speed loop is deferred).
- **Cross-network reach:** kokoro runs on its own docker network (`kokoro_default`), separate from
  `pocket-tts_default`, so pocket-tts calls it via the **host IP** `http://192.168.0.130:8880`
  server-side (stdlib `urllib`, no `requests` dep). The browser stays same-origin (no CORS) because
  the studio proxies through pocket-tts.
- **New routes in `main.py`:** `GET /kokoro/voices` (cached proxy to kokoro's voice list) and
  `POST /generate_kokoro` (Form `text`/`voice`/`speed` → kokoro `/v1/audio/speech` wav → save to the
  shared `/out`). `_gen_lock` is taken only around the name-collision check + write (kokoro does the
  heavy work in its own process). No compose change — both files were already bind-mounted.
- **Clip naming/sorting:** `_kblend_slug` captures the blend identity (voices + signs + weights,
  prefixes stripped, subtraction as `~`, speed excluded) → that's the per-voice folder; `_kspec_stem`
  adds `_spd{n}` when speed ≠1. So `af_jadzia(2)+af_sarah(1)` lands at
  `studio/kokoro/jadzia2-sarah/jadzia2-sarah.wav` (counter `_2/_3` on collision), in the same clips
  panel as Pocket clips.
- Note: Kokoro is ~1.8× slower than Pocket and pegs 3 cores (per the Harvard+Rainbow benchmark), so
  it's the "design a voice you like" engine; Pocket remains the fast path.

### Cloning controls in the studio (2026-06-14)
The Pocket tab now exposes Pocket's zero-shot cloning two ways, beyond the prebuilt `/refs` voices:
- **Upload a clip to clone (on the fly):** a file input on the Pocket tab. `POST /generate` now accepts
  an optional `voice_wav` UploadFile (priority: upload > selected `/refs`/built-in voice); it clones the
  uploaded audio via `get_state_for_audio_prompt(..., truncate=True)` and saves the result named off the
  upload's filename stem. Good for one-off clones; longer/cleaner reference (~10–30s) clones better.
- **Save as Pocket voice (promote a clip → reference):** every saved clip has a **➜ voice** button →
  `POST /clips/{name}/promote` (Form `refname`) copies the clip from `/out` into `/refs` as a permanent,
  cloneable Pocket voice (sanitized `{name}.wav`), then it appears in the Pocket voice dropdown. This is
  the **blend/design → clone-for-speed loop**: build a voice in the Kokoro tab (or upload one), generate
  a decent-length take, promote it, then synthesize fast with Pocket. **Requires `/refs` mounted
  writable** — the compose bind was changed `…/reference:/refs:ro` → `…/reference:/refs` (recreate
  applied). Promoted voices land in the same `tts/reference/` folder as the curated refs.

### Gated cloning weights (one-time setup, done 2026-06-10)
Kyutai license-gates the cloning-capable weights. Without auth, only the ~26 preset voices
work and `/tts` with a voice_wav returns 500. Fix (already applied):
1. Accept terms at https://huggingface.co/kyutai/pocket-tts (HF account)
2. Read-scope token → `HF_TOKEN` env in the compose
3. Recreate container; weights download once into the persistent cache
Token is NOT needed at runtime afterward — inference is fully offline. Token only matters
again if the cache is deleted.

## Athena Computer Voice

### Ready-to-use references
`/mnt/documents/personal/alec/claudeai/tts/reference/` (samba: `documents\personal\alec\claudeai\tts\reference\`)

| File | Length | Character |
|---|---|---|
| `athena_calm.wav` (+`.txt`) | 14.4s | measured status-report voice |
| `athena_urgent.wav` (+`.txt`) | 5.3s | alarm/warning delivery |
| `athena_ref_best.wav` | 26s | general, top-7 clips overall |
| `athena_ref_short.wav` (+`.txt`) | 9.5s | strict word-boundary cut, digit-free transcript |
| `athena_natural.wav` (+`.txt`) | 30s | actress's natural speaking voice (YouTube interviews, pooled best windows) |
| `majel_natural.wav` (+`.txt`) | 21.3s | **Majel Barrett — TNG Enterprise computer**, status-report register |
| `majel_urgent.wav` (+`.txt`) | 14.0s | Majel Barrett, warning/alert register |
| `majel.wav` (+`.txt`) | 14.5s | Majel from a YouTube sketch (mixed registers; superseded by the TNG cuts) |

The Majel references were mined from the TNG Blu-ray SDH subs with the same pipeline
(`SHOW=majel`, profile in the script): 318 `COMPUTER:` cues across 7 seasons → solo/SFX/
dash-dialogue gates → 297 clips → ASR+SNR scoring (`majel_scores.csv`) → register picks.
Plain `COMPUTER:` is Majel in TNG; the 3 `MALE COMPUTER VOICE:` cues never match the
start-anchored label pattern.

Pass any of them as `voice_wav`. The `.txt` transcripts exist for engines that need
reference text (Pocket TTS does not).

### How they were built (pipeline — reproducible)
Script: `/mnt/documents/personal/alec/claudeai/tts/tools/extract_athena.py`
(modes: `parse` / `extract` / `stitch`; `SHOW=athena|majel`). Companion: `tools/bakeoff.py` (blind
A/B harness). Each persona's cue-rips + CSV live under `tts/voices/<persona>/` (`source-clips/`,
`<persona>_cues.csv`); the stitch step still writes the finished refs into the flat `reference/`
(`/refs`). The live bind-mounted dirs are only `reference/` and `studio/`.

1. **SDH subtitle mining** (`parse`): SDH subs label speakers explicitly
   (`ATHENA COMPUTER:`). Parser handles `<i>` tags, dash-dialogue, parentheticals,
   continuation cues → `athena_cues.csv` (189 rows: tiers labeled/continuation/possible/mixed).
   Plain `COMPUTER:` labels (E01) are the *Academy/shuttle* computer — a different voice;
   excluded per user decision. E03–E05: she has no labeled lines; E09 has no SDH file.
2. **Quality-gated extraction** (`extract`): only explicit-ATHENA, solo-speaker cues
   (mixed-speaker cue windows contain other people addressing her — the #1 contamination),
   no `[sfx]` annotations; ffmpeg center-channel isolation (`pan=mono|c0=FC` from the 5.1
   EAC3) strips most music; 0.25s/0.45s padding → 24 clips, 24kHz mono.
3. **ASR scoring & ranking**: faster-whisper per clip — pseudo-SNR (15th vs 85th percentile
   frame dB), avg_logprob, word-match vs subtitle text → composite ranking. Also used
   word-level timestamps for surgical first-word→last-word cuts (kills padding spill).
4. **Mood curation**: clips bucketed by content register (alarm vs status), with human
   judgment overrides (e.g. "No enemy vessels detected" is calm content despite "detected";
   the E08 theater-performance line is excluded — wrong register).
5. **Stitch** (`stitch`): chosen clips + 0.3s silence joints → reference WAVs above.

## Verification
- `curl http://192.168.0.130:8001/health` → `{"status":"healthy"}`
- Clone test: API call above with any athena reference → WAV in seconds, voice matches show.
- Trailhead → AI - Foundry → Pocket TTS card.

## Troubleshooting
- **500 "could not download weights … voice cloning"** → HF_TOKEN missing/cache wiped; see gated-weights section.
- **First request slow** → model loads lazily into RAM on first synthesis after restart (~30–60s), then fast.
- **Container name conflicts after killed `compose up`** → dockerd phantom name reservation; use a different container_name or restart dockerd. PREVENT: run long creates detached (`setsid nohup docker compose up -d`) — on foundry's disk, creates from multi-GB images take minutes. (Bit us 3× during the NeuTTS saga.)
- **Voice sounds wrong/muddy** → reference is everything: shorter + cleaner beats longer + contaminated; check the reference for music/SFX under the voice.

## XTTS-v2 — third CPU TTS engine (2026-06-14)
A standalone XTTS-v2 (Coqui, idiap fork) stack on foundry for a quality comparison vs Pocket/Kokoro —
the "best naturalness we can run CPU-only" experiment (GPU not possible).

| | |
|---|---|
| Endpoint | `http://192.168.0.130:8002` — stock Coqui `tts-server` web UI; cloning over `GET /api/tts` |
| Stack | `/mnt/docker/xtts/compose.yaml` (own project, **builds from a local Dockerfile** — see below) |
| Container | `xtts`, 3 CPU / 4g, CPU-only; model cache `/mnt/docker/xtts/models` (1.8 GB, bind-mounted) |
| Refs | `…/tts/reference:/refs` + `…/studio:/out` (same as pocket-tts) |
| Trailhead | "XTTS-v2" card in AI - Foundry |

**Cloning API:** `GET /api/tts?text=…&speaker_wav=/refs/<ref>.wav&language_idx=en` → 24 kHz WAV.
Plain/native voices use XTTS's built-in studio speakers (`speaker_idx`).

**Why a custom build (not a prebuilt image):** `ghcr.io/idiap/coqui-tts-cpu:latest` ships **no torch** —
unusable. So we build from `python:3.11-slim`: install **CPU torch first** from the pytorch CPU index
(so `coqui-tts` doesn't pull CUDA), then `coqui-tts`. **Dependency pins that matter** (the saga):
coqui-tts 0.27.x requires `transformers>=4.57`, but transformers 5.x **dropped `isin_mps_friendly`**
(which coqui's tortoise layer imports) → must pin **`transformers==4.57.1`** (has both that symbol and
`is_torchcodec_available`). transformers 4.57 also needs **`torchcodec`** (CPU, uses the apt `ffmpeg`
libs) for its audio path, and the stock server needs **`flask`** (the `[server]` extra; installed
directly so it doesn't re-resolve transformers back to 5.x). All CPU: torch 2.12.0+cpu, torchcodec
0.14.0+cpu.

**Verdict (A/B in `tts/tts-bench/results.md`):** XTTS is the **slowest** by far — 0.35–0.38×
realtime (46 s for 18 s of audio), heaviest (~2.8 GiB RAM, ~2.7 cores). Pocket's native voice is ~3.3×,
Kokoro ~1.7×, Pocket's clone path ~8 s/short line (re-encodes the ref each call) but amortizes on long
text. Quality is ear-judged — kept for now as the "design a voice" option; Pocket remains the fast path.

**Folded into the Voice Studio (3rd tab "XTTS Clone", 2026-06-14):** the studio (pocket-tts `:8001`)
reaches XTTS server-side via the host IP (separate docker net, like kokoro) — routes `GET /xtts/langs`
and `POST /generate_xtts` (Form `text`/`voice`/`language`). The tab clones from the same `/refs`
references (so it's apples-to-apples with the Pocket tab) and adds a **language** selector (XTTS's 17
languages). Clips sort to `studio/xtts/<voice>/<vkey>_<lang>.wav`. XTTS itself stays a
standalone container; the studio just calls its `/api/tts`.

## History
- 2026-06-10: Deployed; bake-off vs NeuTTS Air (q4-GGUF fork) — Pocket TTS won on voice
  quality (user ear test) and operational simplicity. NeuTTS stack/image/folder removed
  (22GB reclaimed). Athena references built same day.
