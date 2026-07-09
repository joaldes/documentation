# TTS on foundry — Pocket TTS · Kokoro · XTTS-v2 · Voice Studio (+ Athena/Majel pipeline)

**Last Updated**: 2026-07-09
**Related Systems**: CT 130 "foundry" (192.168.0.130) — three standalone CPU TTS engines fronted by a standalone Voice Studio gateway (:8010),
Komodo-managed, Trailhead (AI - Foundry group), documents samba (tts), Home Assistant VM 100 (announcements)

## Engines at a glance
| Engine | Port | Role | Cloning | Speed (CPU) |
|---|---|---|---|---|
| **Pocket TTS** (Kyutai, 100M) | 8001 | fast zero-shot cloning; standalone engine + native UI | yes (zero-shot) | ~3× realtime (fastest) |
| **Kokoro** (82M, remsky) | 8880 | 67 preset voices + blend builder | no (blend only) | ~1.7× realtime |
| **XTTS-v2** (Coqui/idiap) | 8002 | most natural + multilingual cloning | yes (zero-shot, 17 langs) | ~0.35× realtime (slowest, heaviest) |

The **Voice Studio** is a **standalone gateway** — its own container/stack on **:8010** (no model loaded) —
that serves the single UI over all three engines (tabs *Pocket TTS* / *Kokoro Blend* / *XTTS Clone*, one
text box / player / clips panel) and **proxies each tab's API calls to the engine containers by name** over
the shared `tts` docker network. URLs: `http://192.168.0.130:8010/` · `voice-studio.home` ·
`https://voice-studio.1701.me`.

Each engine also stands alone on its own port with its **native** dashboard: Pocket `:8001/`,
XTTS `:8002/`, Kokoro `:8880/web/`. **(Split from the fused pocket-tts container on 2026-06-15 — see History.)**

## Deployment / source of truth
- All three stacks are **Komodo-managed, "Files on Host"** at `/mnt/docker/<name>/` (registered 2026-06-15
  on the foundry server) — same as every other homelab stack; manage via the Komodo UI. **No git** (no
  homelab stack uses it; durability rides on system backups — the former `/mnt/docker` backup gap was
  **closed 2026-07-01**: the nightly PBS fileshares job now backs up `/mnt/docker` as `docker.pxar`).
- **One image, two containers via a `ROLE` env (split 2026-06-15).** The single image
  `pocket-tts-pocket-tts:latest` runs as **`pocket-engine`** (`ROLE=engine`, `/mnt/docker/pocket-tts/`,
  :8001 — loads the model, serves the native Pocket UI + `/generate` + `/tts`) and **`voice-studio`**
  (`ROLE=gateway`, `/mnt/docker/voice-studio/`, :8010 — no model; serves the studio UI and proxies
  `/generate`→`pocket-engine`, `/generate_kokoro`→`kokoro`, `/generate_xtts`→`xtts`). No rebuild — both
  reference the existing image tag.
- The only hand-authored code is `/mnt/docker/pocket-tts/app/main.py` + `/mnt/docker/pocket-tts/studio/index.html`,
  bind-mounted into **both** containers (engine mounts only `main.py` → native UI; gateway also mounts
  `studio/index.html` → studio). One `.bak` per file; a full pre-split backup is at
  `…/claudeai/tts/_pre-split-backup-2026-06-15/`. The vendored clone is only the build context.
- **HTML edits are rebuild-free** — `studio/index.html` is read per request, so editing it needs no
  recreate. Only `main.py` edits need **`docker compose up -d --force-recreate`** (engine and/or gateway).
- Engines talk over the **external `tts` docker network**, reached by container name:
  `KOKORO_BASE=http://kokoro:8880`, `XTTS_BASE=http://xtts:5002` (xtts's *internal* port is 5002),
  `POCKET_BASE=http://pocket-engine:8000`. Create once with `docker network create tts`; all four
  composes reference it `external: true`. A oneshot **`tts-network.service`** on CT 130 (enabled, `After=docker.service`) recreates the network at boot so it survives a reboot / `docker prune`.
- **NPM:** `voice-studio.home` (HTTP) + `voice-studio.1701.me` (LE cert) → `192.168.0.130:8010`.
  **Trailhead** (AI - Foundry): *Voice Studio* → :8010; *Pocket/XTTS/Kokoro (engine)* cards → native ports.
- **Shared assets** live in the documents samba at `…/claudeai/tts/` (renamed from `athena-voice/`
  2026-06-15), organized **fully per voice** — the folder tree is the source of truth and the app
  conforms to it (2026-06-15):
  - `voices/<persona>/` = **everything for that voice in one place**: the cloneable refs sit right
    in the persona folder (`voices/athena/athena_natural.wav` + `.txt`, etc.), with supporting
    material in subfolders — `source-clips/` (SDH cue-rips), `<persona>_cues.csv`, Majel's
    `majel_scores.csv`, Athena's `expressiveness-samples/` + stitch artifacts (`picks.txt`, `_sil.wav`).
    Personas today: `athena`, `majel`, and `custom/` (where "➜ voice" promotions land).
  - **`voices/` IS the live `/voices` mount** (bind-mounted into pocket-tts rw + xtts ro). The app
    discovers voices by globbing `*/*.wav` (one level), so a voice's id is `persona/name.wav`; the
    picker groups by persona. There is **no flat `reference/` dir anymore** — it was dissolved into
    `voices/` 2026-06-15 and the app rewired to read the tree (see Voice Studio §).
  - `studio/` = generated clips, bind-mounted `/out`, sorted `<engine>/<voice>/`.
  - `tools/` = the extraction/bakeoff scripts (`extract_athena.py`, `bakeoff.py`).
  - `tts-bench/` = cross-engine benchmarks + `results.md`.
  Bind-mounted stacks point at `…/tts/voices` (`/voices`) + `…/tts/studio` (`/out`).

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
the per-engine controls, type text, generate, play in-browser.
- **Exposed controls per engine (2026-06-15 — every natively-reachable knob):**
  - **Pocket:** temperature, decode_steps, eos_threshold, **noise_clamp** (`0`=off). These are the 4
    live-mutable sampler attrs (`tts_model.temp/lsd_decode_steps/eos_threshold/noise_clamp`), set per
    request under `_gen_lock` then restored.
  - **Kokoro:** voice/blend, speed, **volume_multiplier**, **lang_code** (accent override), and the 7
    **normalization** toggles (`normalize`/url/email/phone/optional-pluralization/replace-symbols/unit)
    → forwarded as Kokoro's `normalization_options`. (Payload sets `stream:false` — `urllib.read()`
    raises `IncompleteRead` on Kokoro's default chunked stream.)
  - **XTTS:** voice (clone a `/voices` reference, **upload a clip to clone**, **or** one of XTTS-v2's
    **58 built-in studio speakers** id `builtin/<Name>` → server `speaker_id`), language (17). **Not exposed:** temperature/top_k/top_p/repetition+length-penalty/
    text-splitting and `speed` — the stock Coqui `tts-server` `/api/tts` doesn't pass them to the model
    (its `/v1/audio/speech` has `speed` but hardcodes language to the server default), so reaching them
    needs a **custom XTTS inference server** (deferred — would mean rebuilding the xtts container).
- **Generation does NOT auto-save (changed 2026-06-15).** `POST /generate*` returns the audio bytes
  directly (played from a browser object-URL) with the suggested filename in an `X-Clip-Name` header;
  nothing is written to disk. The result row shows the clip as **· unsaved** with a **💾 save** icon.
- **Manual save:** the 💾 icon `POST`s the held audio + suggested name to **`/save`**, which writes it
  into the library at `tts/studio/<engine>/<voice>/<stem>.wav` (stem = `{vkey}_t{temp}_s{steps}`;
  collisions get `_N`). Only saved clips appear in the **Saved clips** panel — listed newest-first,
  grouped under an `engine · voice` header, with inline players + a delete ✕ (delete prunes the
  now-empty voice/engine dir).
- Voice picker = the custom references discovered under `tts/voices/<persona>/` (grouped by persona
  via `<optgroup>`, voice id = `persona/name.wav`) **+** the 26 built-in Kyutai voices (alba,
  estelle, …, passed through as `voice_url`). `/voices` globs `*/*.wav`; cloning resolves
  `REFS_DIR / "<persona>/<name>.wav"` natively, so the file tree drives the UI.
- Implemented as extra FastAPI routes in pocket-tts `main.py` (`GET /`, `/voices`, `/clips`,
  `/clips/{name:path}` GET+DELETE+promote — `:path` so nested `engine/voice/file.wav` matches,
  `POST /generate` / `/generate_kokoro` / `/generate_xtts` → **return audio + `X-Clip-Name`** (no
  disk write), and `POST /save` → write the held audio into the library). `/generate*` build only a
  *suggested* name via `_suggest_name`; `/save` does the real collision-safe `_resolve_out`. `/clips`
  walks the tree (`rglob`). The page is bind-mounted
  (`studio/index.html` → `/app/pocket_tts/static/studio.html`); pocket generation reuses the loaded
  model under `_gen_lock`, rendering to a temp file it reads back (never the studio tree).
- **CT 130 now mounts the documents samba** (added 2026-06-13): `mp5: /mnt/documents,mp=/mnt/documents`
  in `/etc/pve/lxc/130.conf`. This was required for the fold-in (so foundry can read
  `voices/` and write `studio/`) and needed a one-time CT 130 reboot to apply (mp hotplug
  doesn't take; the reboot bounces ollama/open-webui/searxng/kokoro — they auto-recover). compose
  binds: `…/tts/voices:/voices` and `…/tts/studio:/out`.
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
  `POST /generate_kokoro` (Form `text`/`voice`/`speed`/`volume_multiplier`/`lang_code`/`normalization`
  → kokoro `/v1/audio/speech` wav, returned to the browser). kokoro does the heavy work in its own
  process. No compose change — both files were already bind-mounted.
- **Single-voice blend fix:** `buildBlendString()` emits a lone voice **bare** (`af_bella`), not
  `af_bella(1)` — Kokoro only parses weights inside a `+`/`-` blend, so a parenthesized single voice is
  read as a literal filename → 500.
- **Clip naming/sorting:** `_kblend_slug` captures the blend identity (voices + signs + weights,
  prefixes stripped, subtraction as `~`, speed excluded) → that's the per-voice folder; `_kspec_stem`
  adds `_spd{n}` when speed ≠1. So `af_jadzia(2)+af_sarah(1)` lands at
  `studio/kokoro/jadzia2-sarah/jadzia2-sarah.wav` (counter `_2/_3` on collision), in the same clips
  panel as Pocket clips.
- Note: Kokoro is ~1.8× slower than Pocket and pegs 3 cores (per the Harvard+Rainbow benchmark), so
  it's the "design a voice you like" engine; Pocket remains the fast path.

### Cloning + voice management in the studio (2026-06-14 / -15)
Pocket **and XTTS** both expose upload-to-clone, and a **Voice library** panel manages the reference set:
- **Upload a clip to clone (on the fly):** file input on the Pocket **and** XTTS tabs (`voice_wav` on
  `POST /generate` and `POST /generate_xtts`; priority: upload > built-in/dropdown). Pocket clones via
  `get_state_for_audio_prompt(..., truncate=True)`. XTTS has no writable `/voices`, so its upload is
  **staged into `/out/.xtts_refs/`** (xtts mounts `/out` rw), passed as `speaker_wav=/out/.xtts_refs/…`,
  then deleted; `/clips` skips dot-dirs so the staging never shows as a clip. (XTTS accepts wav/mp3 — it
  has ffmpeg; Pocket's `/voices` uploads are WAV-only, no transcoder in that container.)
- **Voice library panel** (right column) — manage the cloneable references used by Pocket + XTTS:
  `GET /voices/{rel:path}` preview, `POST /voices/upload` (persona/name/WAV), `POST /voices/rename`
  (rename or move persona, carries the `.txt` companion, prunes empty dirs), `DELETE /voices/{rel:path}`.
  All paths are traversal-guarded under `/voices` (`_safe_voice`). Edits refresh every voice picker live.
- **Save as Pocket voice (promote a clip → reference):** every saved clip has a **➜ voice** button →
  `POST /clips/{name:path}/promote` (Form `refname`) copies the clip from `/out` into
  `/voices/custom/{name}.wav` as a permanent, cloneable voice (id `custom/{name}.wav`), then it appears
  in the Pocket voice dropdown under the **custom** persona. This is the **blend/design → clone-for-speed
  loop**: build a voice in the Kokoro tab (or upload one), generate a decent-length take, promote it, then
  synthesize fast with Pocket. **Requires `/voices` mounted writable** (pocket-tts mounts it rw; xtts ro).

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
`/mnt/documents/personal/alec/claudeai/tts/voices/athena/` (samba: `documents\personal\alec\claudeai\tts\voices\athena\`)

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
`<persona>_cues.csv`); the stitch step writes the finished ref + `picks.txt` + `_sil.wav` straight
into the persona folder (`tts/voices/athena/`). The live bind-mounted dirs are `voices/` (`/voices`)
and `studio/` (`/out`).

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
| Refs | `…/tts/voices:/voices:ro` + `…/studio:/out` (same tree as pocket-tts; ro) |
| Trailhead | "XTTS-v2" card in AI - Foundry |

**Synthesis API** (`GET /api/tts` → 24 kHz WAV): clone → `&speaker_wav=/voices/<persona>/<ref>.wav`;
built-in speaker → `&speaker_id=<Name>` (list at the xtts server's `GET /voices`, 58 speakers). **The
language param is `language_id` — NOT `language_idx`** (the server silently ignores the wrong name and
falls back to its default `en`; this was a real bug in the studio, fixed 2026-06-15). The studio's
`/xtts/speakers` route proxies + caches that speaker list.

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
and `POST /generate_xtts` (Form `text`/`voice`/`language`) + `GET /xtts/speakers`. The tab's voice
dropdown offers **both** the `/voices` clone references (apples-to-apples with Pocket) **and** XTTS's 58
built-in studio speakers (`builtin/<Name>`), plus a working **language** selector (XTTS's 17 languages).
Clips sort to `studio/xtts/<voice>/<vkey>_<lang>.wav`. XTTS itself stays a
standalone container; the studio just calls its `/api/tts`.

## Announcer — play Voice Studio voices on the Chromecast (2026-07-07)
A small **`announcer`** service casts Voice Studio audio to the Chromecast Audio **"Home Announcer"**
(`192.168.0.206`). Compose stack at `/mnt/docker/announcer/` on CT 130, **host-networked**, FastAPI at
**`http://192.168.0.130:8011`**.
- **From the Voice Studio UI:** every generated clip now has a **📢 cast** button (beside 💾 save) that
  POSTs the held audio blob to `announcer:/cast_upload` → plays it on Home Announcer (casts the exact
  audio you auditioned, no regeneration). Use the **HTTP** studio URL (`192.168.0.130:8010` /
  `voice-studio.home`) — an HTTPS page (`voice-studio.1701.me`) blocks the cross-origin HTTP cast call
  (mixed content).
- **From anything (curl/HA):** `GET /say?text=...&voice=athena/athena_calm.wav&engine=pocket&volume=0.5`
  regenerates via Voice Studio, serves the WAV, casts it. `POST /cast_upload` (multipart `audio` +
  `volume`) casts an existing clip. Temp WAVs auto-pruned after 10 min.
- **How it works:** the CCA plays a *URL it fetches itself*, so the announcer serves the WAV at
  `http://192.168.0.130:8011/audio/<id>.wav` (host-reachable) and drives playback via **pychromecast**
  (`get_chromecasts(known_hosts=["192.168.0.206"])`, retried — mDNS is lossy). CORS `*` on the announcer
  so the UI button can call it.
- **Files:** `/mnt/docker/announcer/{app.py,Dockerfile,requirements.txt,compose.yaml}`; UI button
  (`castClip`) in `pocket-tts/studio/index.html` (bind-mounted, rebuild-free; `.bak` kept). Announcer
  app edits need `docker compose up -d --build`.
- Chromecast provisioning itself (orphaned CCA → local `eureka` API): `troubleshoot/chromecast-audio-provisioning.md`.
- **Trailhead card** "Announcer (cast)" (AI - Foundry tab, Voice group — same group as the engine cards)
  → `:8011/docs` (added 2026-07-09 — the root path is API-only/404, Swagger is the landing page).

## Home Assistant integration
Where HA voice stands relative to the local TTS stack — written 2026-07-09, per the HA voice sessions of
2026-07-05→08 plus a live check:

**HA voice today is fully cloud.** Both Assist pipelines ("Home Assistant Cloud" and the preferred
"Concierge") use Nabu Casa cloud STT/TTS (`stt./tts.home_assistant_cloud`, voices JennyNeural/SaraNeural).
Nothing in HA is wired to the foundry engines yet.

**Deliberate non-goals (decided 2026-07-07):** Wyoming / openWakeWord / Piper / Whisper are **not needed**
— there is no microphone/satellite hardware, so wake-word and local STT are moot. The `core_piper` and
`core_openwakeword` add-ons are installed but **stopped** (dead weight from past experiments; Piper has
been off since the 2026-02-04 boot-loop incident — that incident's "reinstall if needed" TODO is hereby
closed as won't-do). Whisper was never installed. If hands-free interaction is ever wanted, the path is an
HA Voice Preview Edition puck (~$60) or a DIY ESP32-S3 satellite — revisit then.

**What works now:**
- **Chime TTS** (HACS integration, verified 2026-07-08): `chime_tts.say` →
  `media_player.chromecastaudio7822` ("Home Announcer" CCA, `192.168.0.206`) — pre-merges chime+speech
  into one file, eliminating the Google cast "beep" and ~2 s lead delay. Currently voiced by
  `tts.home_assistant_cloud`.
- **Announcer from HA automations (no token needed):** any HA `rest_command` can hit the announcer's
  `/say` (endpoints in the Announcer § above) today — the announcer drives the CCA itself. HA can also
  cast a served WAV URL directly via `media_player.play_media`.

**Designed but NOT built (blocked):** a `via=cca|hass` switch on the announcer + a
`rest_command.announcer_say` in `/config/packages/announcer.yaml` + a 🏠 HA cast chip in the studio UI —
so casts route *through* HA's media_player (more reliable than pychromecast's lossy mDNS, occasional
504s/6× retries). **Blocked on a Home Assistant long-lived access token** (user task; HA's REST API has no
trusted-network bypass). Designed 2026-07-08, not resumed since.

**Local voice in the HA pipeline (open, the "good voice for HASS" path):**
- **Kokoro**: install HACS **"OpenAI TTS Speech Service"** (sfortis) pointed at
  `http://192.168.0.130:8880/v1`, model `kokoro`, any preset voice → creates a `tts.` entity that Chime
  TTS and the Assist pipelines can use instead of cloud. Explained 2026-07-08, **not installed yet**.
- **Pocket TTS (Athena/Majel)**: its API is not OpenAI-shaped, so reaching HA-native TTS needs a small
  OpenAI-compatible (or Wyoming) shim in front of `pocket-engine`. Until then the Athena voice reaches
  speakers only via the announcer path above.

## Open TODOs (voice stack)
1. HA long-lived access token → build the `via=hass` announcer path + `rest_command.announcer_say` + 🏠 HA studio chip.
2. Kokoro as an HA-native `tts.` entity (HACS OpenAI TTS Speech Service → `:8880/v1`), then point Chime TTS/pipelines at it.
3. OpenAI-compatible shim for pocket-engine so Athena/Majel can be an HA pipeline voice.
4. Kokoro blend → promote-to-Pocket-reference button (Pocket/XTTS clips have ➜ voice; Kokoro blends don't).
5. XTTS deep knobs (temperature/top_k/top_p/penalties/speed) — deferred; needs a custom inference server + rebuild (declined 2026-06-15).

## History

- **2026-07-09 — Voice audit + doc consolidation.** Multi-agent sweep of chats/docs/live state; all five
  voice containers verified healthy. Announcer Trailhead card added (had been missed at deploy). HA
  integration state + open TODOs captured above.
- **2026-07-08 — Chime TTS live in HA; announcer-via-HA designed but blocked.** Chime TTS (HACS) verified
  end-to-end on the Home Announcer with the cloud voice; the `via=hass` announcer route was designed but
  is blocked on an HA long-lived access token. Studio UI: Kokoro blend weight-slider step fixed to 0.1.
- **2026-07-07 — Announcer deployed** (see section above) after the Chromecast Audio provisioning saga;
  HA Assist-pipeline review concluded Wyoming/Piper/Whisper/wake-word are not needed (no mic hardware).
- **2026-06-15 — Split: standalone Voice Studio gateway (:8010) + standalone engines.** The fused
  `pocket-tts` container (which did model + studio UI + proxy at :8001) was split via a `ROLE` env flag
  into `pocket-engine` (:8001, model + native UI) and `voice-studio` (:8010, studio UI + proxy), sharing
  one image and the shared `tts` network. Each engine now exposes its native dashboard on its own port.
  Verified end-to-end (all three tabs generate through the gateway). Pre-split backup kept at
  `…/tts/_pre-split-backup-2026-06-15/`.
- 2026-06-10: Deployed; bake-off vs NeuTTS Air (q4-GGUF fork) — Pocket TTS won on voice
  quality (user ear test) and operational simplicity. NeuTTS stack/image/folder removed
  (22GB reclaimed). Athena references built same day.
