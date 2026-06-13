# Pocket TTS — Voice Cloning on foundry (+ Athena Computer Voice Pipeline)

**Last Updated**: 2026-06-13
**Related Systems**: CT 130 "foundry" (192.168.0.130), CT 124 (Voice Studio web UI), Trailhead (AI - Foundry group), documents samba (athena-voice)

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

## Voice Studio (web UI — CT 124)
`http://192.168.0.180:8088/` — a tiny Flask front-end (NOT on foundry; see note) to pick a voice,
dial temperature/decode-steps/EOS, type text, generate, and play in-browser. Every clip is saved
to `athena-voice/studio/` with a succinct spec name `{voice}_t{temp}_s{steps}_{texthash}.wav`
(e.g. `athenaCalm_t0.9_s1_115c.wav`); a panel lists saved clips with inline players + delete.
- Voice picker = the custom references in `athena-voice/reference/` **+** the 26 built-in Kyutai
  voices (alba, estelle, …, passed through as `voice_url`).
- Source: `/home/claudeai/voice-studio/` (`app.py` + `index.html`), venv
  `/home/claudeai/.venvs/voice-studio/`, systemd unit `voice-studio.service` (port 8088), pattern
  mirrors `claude-ui`/`claude-dev`. It proxies to pocket-tts `/tts` and reads/writes the samba
  athena folder directly.
- **Why CT 124, not foundry:** the studio needs the documents samba (to save into the athena
  folder), but `/mnt/documents` is **not mounted on CT 130** — only on CT 124/104/128/102. Folding
  the UI into pocket-tts would have required adding the mount to CT 130 (an LXC reboot bouncing
  ollama/open-webui/searxng), so the UI lives on CT 124 where the share already exists and reaches
  pocket-tts over HTTP. The `/tts` param patch is the only foundry-side change.

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
