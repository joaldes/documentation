# Pocket TTS — Voice Cloning on foundry (+ Athena Computer Voice Pipeline)

**Last Updated**: 2026-06-14
**Related Systems**: CT 130 "foundry" (192.168.0.130) — Pocket TTS + Kokoro (dual-engine Voice Studio), Trailhead (AI - Foundry group), documents samba (athena-voice)

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
  from the build context (`/mnt/docker/pocket-tts/pocket-tts/pocket_tts/main.py`); a
  `docker compose up -d --force-recreate` (one warm load) applies it. Backups:
  `main.py.bak-prestudio`, `compose.yaml.bak-prestudio`.

## Voice Studio (web UI — folded into Pocket TTS)
`http://192.168.0.130:8001/` — pocket-tts's own root page **is** the studio: pick a voice, dial
temperature/decode-steps/EOS, type text, generate, play in-browser. Every clip saves to
`athena-voice/studio/` with a spec name `{voice}_t{temp}_s{steps}.wav` (e.g.
`athenaCalm_t0.9_s1.wav`); on a name collision a counter is appended (`…_s1_2.wav`, `…_s1_3.wav`).
A panel lists saved clips with inline players + delete.
- Voice picker = the custom references in `athena-voice/reference/` **+** the 26 built-in Kyutai
  voices (alba, estelle, …, passed through as `voice_url`).
- Implemented as extra FastAPI routes in pocket-tts `main.py` (`GET /`, `/voices`, `/clips`,
  `/clips/{name}` GET+DELETE, `POST /generate`). The page is bind-mounted
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
The studio is now **dual-engine**: an engine switch (`Pocket TTS` | `Kokoro Blend`) above the shared
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
- **Clip naming:** `_kspec_name` → succinct `kok_<voices>.wav`, prefixes stripped, weight kept when
  ≠1, subtraction as `~`, `_spd{n}` when speed ≠1 (e.g. `af_jadzia(2)+af_sarah(1)` →
  `kok_jadzia2-sarah.wav`); counter `_2/_3` on collision. Lands in the same `athena-voice/studio/`
  folder + clips panel as Pocket clips.
- Note: Kokoro is ~1.8× slower than Pocket and pegs 3 cores (per the Harvard+Rainbow benchmark), so
  it's the "design a voice you like" engine; Pocket remains the fast path. Backups from this change:
  `main.py.bak-preblend`, `studio/index.html.bak-preblend`.

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
  applied). Promoted voices land in the same `athena-voice/reference/` folder as the curated refs.

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
`/mnt/documents/personal/alec/claudeai/athena-voice/reference/` (samba: `documents\personal\alec\claudeai\athena-voice\reference\`)

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
Script: `/mnt/documents/personal/alec/claudeai/athena-voice/extract_athena.py`
(modes: `parse` / `extract` / `stitch`). Companion: `bakeoff.py` (blind A/B harness).

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

## History
- 2026-06-10: Deployed; bake-off vs NeuTTS Air (q4-GGUF fork) — Pocket TTS won on voice
  quality (user ear test) and operational simplicity. NeuTTS stack/image/folder removed
  (22GB reclaimed). Athena references built same day.
