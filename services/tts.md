# TTS — Pocket TTS · Kokoro · Chatterbox · Voice Studio (+ Athena/Majel pipeline)

**Last Updated**: 2026-07-12
**Related Systems**: **CT 200 "forge" on the t5 node (192.168.0.155) now hosts the ENTIRE voice stack** —
Pocket TTS + Kokoro (CPU), the Voice Studio gateway (:8010), the announcer, and Chatterbox on the GTX 1660
Super (CUDA). **All consolidated onto forge 2026-07-12** (previously the CPU pieces lived on CT 130 "foundry").
Foundry (CT 130) is being retired 2026-07-12 — open-webui + searxng also moved to forge. Komodo-managed stacks on the **forge** server,
Trailhead (AI - Foundry group), documents samba (tts), Home Assistant VM 100 (announcements).

> **Naming (2026-07-12):** CT 200 was **renamed `forge` → `foundry`** once the whole AI hub landed on it —
> **"forge" anywhere in this doc = CT 200 = now `foundry`** (192.168.0.155). Physical node stays `t5`. The old
> foundry (CT 130) became `foundry-old` and is retiring.

## Engines at a glance
| Engine | Host | Port | Role | Cloning | Speed |
|---|---|---|---|---|---|
| **Pocket TTS** (Kyutai, 100M) | forge (CPU) | 8001 | fast zero-shot cloning; standalone engine + native UI | yes (zero-shot) | ~3× realtime |
| **Kokoro** (82M, remsky) | forge (CPU) | 8880 | 67 preset voices + blend builder | no (blend only) | ~1.7× realtime |
| **Chatterbox** (Resemble, 0.5B base) | forge (GPU) | 8004 | most natural cloning + emotion knobs | yes (zero-shot) | ~2–7s/line on CUDA (≫ realtime) |

*(All four engines + the gateway run on **CT 200 "forge"** @ 192.168.0.155 since 2026-07-12. The two CPU
engines are capped pocket 2c/2g + kokoro 3c/4g; they share forge's 6 cores with ollama/SD but are CPU-only,
so they don't touch the 1660 Super's VRAM.)*

*(XTTS-v2 was the third engine until 2026-07-10 — replaced by Chatterbox; see the Chatterbox § and History.)*

The **Voice Studio** is a **standalone gateway** — its own container/stack on **:8010** (no model loaded) —
that serves the single UI over all three engines (tabs *Pocket TTS* / *Kokoro Blend* / *Chatterbox Clone*, one
text box / player / clips panel). Pocket + Kokoro are proxied **by container name** over the shared `tts`
docker network; Chatterbox is proxied **by host IP** (`192.168.0.155:8004`). **Since 2026-07-12 all three
engines are on the same box (forge)** — the host-IP hop to Chatterbox is now same-node, but kept as an IP
for zero config churn. URLs: `http://192.168.0.155:8010/` · `voice-studio.home` · `https://voice-studio.1701.me`.

Each engine also stands alone on its own port with its **native** dashboard: Pocket `:8001/`,
Chatterbox `192.168.0.155:8004/` (devnen web UI), Kokoro `:8880/web/`. **(Split from the fused pocket-tts
container on 2026-06-15 — see History.)**

## Deployment / source of truth
**Everything is on CT 200 "forge" (t5 node, 192.168.0.155) as of 2026-07-12.** The five voice stacks —
pocket-tts, kokoro, voice-studio, announcer, chatterbox — live at `/mnt/docker/<name>/` on forge
(compose.yaml + code in each), plain `docker compose`, and are **Komodo-managed on the `forge` server**
(id `6a5293eb777538def1e93c60`) as files_on_host stacks (run_directory `/mnt/docker/<name>`, project_name =
name). They were registered/adopted 2026-07-12 by pointing the existing Komodo stack defs at the forge
server (Komodo adopted the running containers, no redeploy). **No git** (no homelab stack uses it).
- **⚠ SMB-mount dependency (new 2026-07-12):** the voices/clips library lives on the documents samba
  (Shipyard/CT 104), which forge can't natively see. The **t5 host** CIFS-mounts it and bind-passes it into
  forge: `//192.168.0.176/documents → /mnt/documents` on the t5 host (fstab, creds
  `/root/.smb-documents.cred`, `uid=100000,gid=100000` = CT200's unpriv-idmapped root, `vers=3.1.1`,
  `_netdev,nofail,x-systemd.automount`), then `mp0: /mnt/documents` on CT 200. So the exact same host paths
  (`…/tts/voices`, `…/tts/studio`) resolve inside forge and the composes were copied verbatim. If Samba/CT104
  is down, the studio's voice list + saves fail (same coupling foundry had); `nofail` keeps forge booting.
- **Backups:** the documents samba (voices/clips) rides the nightly PBS pictures/documents job. ⚠ forge/CT200's
  `/mnt/docker` (the stack code itself) has **no PBS coverage yet** (open TODO #6) — the pre-migration LVM-thin
  snapshot `pct snapshot 200 pre_tts_migration` (2026-07-12) is the rollback point; also the foundry stack dirs
  are **kept in place, stopped** (see rollback note in History) so the code has an off-box copy there for now.
- **`chatterbox-power.service`** (forge/CT 200, systemd, not Docker) — `/opt/chatterbox-power/warden.py`
  on `:8005`; the stop/start control plane behind Voice Studio's GPU Power button (see the Chatterbox §).
  No PBS coverage on forge — the unit + script are the sole copy; re-createable from that § if lost.
- **Two SEPARATE services, each owning its stack (real split 2026-07-11 — replaced the 2026-06-15
  `ROLE`-flag arrangement).** No shared image, no ROLE env:
  - **`voice-studio`** (`/mnt/docker/voice-studio/`, image `voice-studio:latest`, **:8010→8010**) —
    the standalone gateway. Slim `python:3.12-slim` + fastapi/uvicorn/python-multipart (no pocket_tts
    package, no model). Owns **its** code `app/main.py` (UI serving, voice library, clips, `/save`,
    `/generate` proxy→pocket-engine, kokoro + chatterbox proxies) and **its** UI `studio/index.html`.
    Built-in Kyutai voice names are proxied from the engine's `/voices` (cached ~5 min; degrades to
    an empty builtin list if the engine is down). Paths env-overridable: `VOICES_DIR`/`CLIPS_DIR`/`STUDIO_DIR`.
  - **`pocket-engine`** (`/mnt/docker/pocket-tts/`, image **`pocket-tts:latest`** — retag of the
    original 2026-06-10 build, NOT rebuilt, :8001→8000) — ENGINE ONLY. Its `app/main.py` keeps the
    expressiveness patch, `/generate` (studio contract, X-Clip-Name), `/tts`, `/voices` (+`/voices/{rel}`
    read), native UI at `/`. All gateway routes removed (they 404 here). ⚠ its compose's `build:` stanza
    is **dormant** — the base image tag is rolling; if you ever rebuild, `docker compose build` +
    smoke-test BEFORE `up -d`.
- **Edit workflow:** `studio/index.html` (in **voice-studio/**) is read per request → save + browser
  refresh, nothing to restart. `app/main.py` edits: **`docker restart voice-studio`** (its app dir is
  bind-mounted) or **`docker restart pocket-engine`** (single-file bind over the installed package —
  overwrite the host file IN PLACE with cp/sed so the inode survives). Nothing is baked into either
  image except python deps.
- The pocket + kokoro engines talk to the gateway over the **external `tts` docker network** (on forge),
  reached by container name: `KOKORO_BASE=http://kokoro:8880`, `POCKET_BASE=http://pocket-engine:8000`.
  Chatterbox is reached by host IP `CHATTERBOX_BASE=http://192.168.0.155:8004` (same box now, but kept as
  IP — it's a separate compose project not on the `tts` net). Create the network once with `docker network
  create tts`; the composes reference it `external: true`. A oneshot **`tts-network.service`** on **CT 200/forge**
  (copied from foundry 2026-07-12, enabled, `After=docker.service`) recreates the network at boot so it
  survives a reboot / `docker prune`.
- **NPM:** `voice-studio.home` (HTTP) + `voice-studio.1701.me` (LE cert) → `192.168.0.155:8010` (proxy hosts
  212/213; repointed .130→.155 2026-07-12 via the NPM sqlite DB + conf regen).
  **Trailhead** (AI - Foundry): *Voice Studio* → :8010; *Pocket/Chatterbox/Kokoro (engine)* + *Announcer* cards → native ports (all :192.168.0.155).
- **Shared assets** live in the documents samba at `…/claudeai/tts/` (renamed from `athena-voice/`
  2026-06-15), organized **fully per voice** — the folder tree is the source of truth and the app
  conforms to it (2026-06-15):
  - `voices/<persona>/` = **everything for that voice in one place**: the cloneable refs sit right
    in the persona folder (`voices/athena/athena_natural.wav` + `.txt`, etc.), with supporting
    material in subfolders — `source-clips/` (SDH cue-rips), `<persona>_cues.csv`, Majel's
    `majel_scores.csv`, Athena's `expressiveness-samples/` + stitch artifacts (`picks.txt`, `_sil.wav`).
    Personas today: `athena`, `majel`, and `custom/` (where "➜ voice" promotions land).
  - **`voices/` IS the live `/voices` mount** (bind-mounted into pocket-tts + the gateway rw; Chatterbox
    has **no mount** — the gateway ships reference clips to it over HTTP, see the Chatterbox §). The app
    discovers voices by globbing `*/*.wav` (one level), so a voice's id is `persona/name.wav`; the
    picker groups by persona. There is **no flat `reference/` dir anymore** — it was dissolved into
    `voices/` 2026-06-15 and the app rewired to read the tree (see Voice Studio §).
  - `studio/` = generated clips, bind-mounted `/out`, sorted `<engine>/<voice>/`.
  - `tools/` = the extraction/bakeoff scripts (`extract_athena.py`, `bakeoff.py`).
  - `tts-bench/` = `results.md` (cross-engine bench writeup; the WAVs were pruned 2026-07-11).
  Bind-mounted stacks point at `…/tts/voices` (`/voices`) + `…/tts/studio` (`/out`).

## Summary
Kyutai Pocket TTS (100M-param CALM model, MIT) runs CPU-only on forge and provides
high-quality zero-shot voice cloning at ~3× real-time. Deployed 2026-06-10 after a
bake-off against NeuTTS Air (retired same day — lost on voice quality by ear, after its
community fork needed four builds to even boot). The marquee use: the **USS Athena ship's
computer voice** from *Star Trek: Starfleet Academy*, extracted from the Emby library via
SDH subtitle mining.

## Service

| | |
|---|---|
| Endpoint | `http://192.168.0.155:8001` — Swagger UI at `/docs`, health at `/health` |
| Stack | `/mnt/docker/pocket-tts/compose.yaml` (own compose project; image `pocket-tts:latest` originally built from the `./pocket-tts` clone of github.com/kyutai-labs/pocket-tts) |
| Container | `pocket-engine`, 2 CPUs / 2g cap on forge, **CPU-only** (no GPU — the 1660 Super is for chatterbox/ollama/SD) |
| Model cache | `/mnt/docker/pocket-tts/cache/huggingface` (bind mount — survives rebuilds) |
| Voices dir | `/mnt/docker/pocket-tts/voices` (for exported .safetensors voices) |

### API usage
```bash
curl -X POST http://192.168.0.155:8001/tts \
  -F "text=Warning. Hull breach on deck seven." \
  -F "voice_wav=@athena_urgent.wav" \
  -F "temperature=0.9" -F "decode_steps=1" \
  -o out.wav
```
Fields: `text` + (`voice_wav` upload | `voice_url`) + optional **expressiveness params**
`temperature` / `decode_steps` / `eos_threshold`. Output: 24kHz mono PCM WAV.
Warm generation ≈ 1–4s per sentence on forge's CPU.

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
  from `/mnt/docker/pocket-tts/app/main.py` (see "Deployment / source of truth" above); a
  `docker restart pocket-engine` (one warm load) applies edits. One `.bak` kept per hand-authored file.

## Voice Studio (web UI — standalone gateway service)
`http://192.168.0.155:8010/` — the voice-studio gateway's root page is the studio: pick a voice,
dial the per-engine controls, type text, generate, play in-browser. (Historically the studio was
folded into pocket-tts at :8001, then ROLE-split 2026-06-15, then made a genuinely standalone
service 2026-07-11 — the engine's :8001 root is back to the stock Kyutai page.)
- **Exposed controls per engine (2026-06-15 — every natively-reachable knob):**
  - **Pocket:** temperature, decode_steps, eos_threshold, **noise_clamp** (`0`=off). These are the 4
    live-mutable sampler attrs (`tts_model.temp/lsd_decode_steps/eos_threshold/noise_clamp`), set per
    request under `_gen_lock` then restored.
  - **Kokoro:** voice/blend, speed, **volume_multiplier**, **lang_code** (accent override), and the 7
    **normalization** toggles (`normalize`/url/email/phone/optional-pluralization/replace-symbols/unit)
    → forwarded as Kokoro's `normalization_options`. (Payload sets `stream:false` — `urllib.read()`
    raises `IncompleteRead` on Kokoro's default chunked stream.)
  - **Chatterbox:** voice (clone a `/voices` reference, **upload a clip to clone**, **or** one of the
    server's built-in predefined voices, id `predefined/<file>` → `predefined_voice_id`), plus the three
    emotion knobs: **exaggeration** (0–2, default 0.5 — emotion intensity), **cfg_weight** (0–1, default
    0.5 — adherence/pacing vs the reference), **temperature** (default 0.8). The gateway always sends
    `split_text:false` (single-pass prosody; studio lines are short). English only (base model).
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
- Implemented in the gateway's own `voice-studio/app/main.py` (`GET /`, `/voices`, `/clips`,
  `/clips/{name:path}` GET+DELETE+promote — `:path` so nested `engine/voice/file.wav` matches,
  `POST /generate` / `/generate_kokoro` / `/generate_chatterbox` → **return audio + `X-Clip-Name`** (no
  disk write), and `POST /save` → write the held audio into the library). `/generate*` build only a
  *suggested* name via `_suggest_name`; `/save` does the real collision-safe `_resolve_out`. `/clips`
  walks the tree (`rglob`). The UI is served from `voice-studio/studio/index.html` (read per request);
  all generation is proxied — Pocket generation happens in `pocket-engine`, which reuses its loaded
  model under `_gen_lock`, rendering to a temp file it reads back (never the studio tree).
- **How forge reaches the voices/clips (documents samba):** the t5 host CIFS-mounts
  `//192.168.0.176/documents → /mnt/documents` and CT 200 bind-mounts it via `mp0: /mnt/documents` in
  `/etc/pve/lxc/200.conf` (see Deployment §). compose binds: `…/tts/voices:/voices` and `…/tts/studio:/out`.
  *(Historical: 2026-06-13→2026-07-12 this ran on foundry/CT 130 via `mp5: /mnt/documents` — that native
  Proxmox bind was replaced by the t5 CIFS mount when the stack moved to forge; adding `mp0` to CT 200
  needed a one-time CT 200 restart to apply, which bounced ollama/sd-webui/chatterbox — they auto-recover.)*
- An earlier interim build hosted the same UI as a standalone Flask app on CT 124 (port 8088); that
  was retired once the fold-in was verified (the documents-mount approach was chosen instead).

### Kokoro blend — second engine in the studio (2026-06-14)
The studio is **multi-engine** (Pocket TTS | Kokoro Blend | Chatterbox Clone — see the Chatterbox section
for the third tab): an engine switch above the shared
text box / result player / clips panel. The Kokoro tab is a **voice-blend builder** — add any of the
67 Kokoro voices, give each a `+`/`−` sign and a relative weight, set speed, generate. It leverages
Kokoro's own blend config: the `voice` string `af_jadzia(2)+af_sarah(1)-am_adam(0.5)` (additive `+`,
subtractive `−`, parenthesized weights **auto-normalized to sum 1** by kokoro-fastapi). The UI shows a
live "effective mix %" and the literal blend string. Scope is **audition + save only** — no
promote-to-Pocket-reference button yet (the blend→clone-for-speed loop is deferred).
- **Reach:** kokoro sits on the shared external `tts` network, so the gateway calls it **by container
  name** (`KOKORO_BASE=http://kokoro:8880`, stdlib `urllib`, no `requests` dep). The browser stays
  same-origin (no CORS) because the studio proxies everything through the gateway.
- **Gateway routes:** `GET /kokoro/voices` (cached proxy to kokoro's voice list) and
  `POST /generate_kokoro` (Form `text`/`voice`/`speed`/`volume_multiplier`/`lang_code`/`normalization`
  → kokoro `/v1/audio/speech` wav, returned to the browser). kokoro does the heavy work in its own
  process.
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

### Cloning + voice management in the studio (2026-06-14 / -15, Chatterbox rewired 2026-07-10)
Pocket **and Chatterbox** both expose upload-to-clone, and a **Voice library** panel manages the reference set:
- **Upload a clip to clone (on the fly):** file input on the Pocket **and** Chatterbox tabs (`voice_wav` on
  `POST /generate` and `POST /generate_chatterbox`; priority: upload > built-in/dropdown). Pocket clones via
  `get_state_for_audio_prompt(..., truncate=True)`. **Chatterbox cloning is HTTP, not shared-path** (it's
  on another node): the gateway uploads the clip to the server's reference store (`POST /upload_reference`,
  multipart field `files`) under a **content-hashed name** `vs_<slug>_<sha1[:8]>.wav`, then synthesizes with
  `reference_audio_filename=<the RETURNED name>` — the server **sanitizes filenames and skips duplicates**
  (never overwrites), so the hash makes re-uploads of identical audio a server-side no-op and changed audio
  a new name (no stale-content risk; `reference_audio/` growth is bounded per distinct clip). Chatterbox
  accepts wav/mp3, **max 30s reference**; Pocket's `/voices` uploads are WAV-only.
- **Voice library panel** (right column) — manage the cloneable references used by Pocket + Chatterbox:
  `GET /voices/{rel:path}` preview, `POST /voices/upload` (persona/name/WAV), `POST /voices/rename`
  (rename or move persona, carries the `.txt` companion, prunes empty dirs), `DELETE /voices/{rel:path}`.
  All paths are traversal-guarded under `/voices` (`_safe_voice`). Edits refresh every voice picker live.
- **Save as Pocket voice (promote a clip → reference):** every saved clip has a **➜ voice** button →
  `POST /clips/{name:path}/promote` (Form `refname`) copies the clip from `/out` into
  `/voices/custom/{name}.wav` as a permanent, cloneable voice (id `custom/{name}.wav`), then it appears
  in the Pocket voice dropdown under the **custom** persona. This is the **blend/design → clone-for-speed
  loop**: build a voice in the Kokoro tab (or upload one), generate a decent-length take, promote it, then
  synthesize fast with Pocket. **Requires `/voices` mounted writable** (pocket-tts + gateway mount it rw).

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
- `curl http://192.168.0.155:8001/health` → `{"status":"healthy"}`
- Clone test: API call above with any athena reference → WAV in seconds, voice matches show.
- Trailhead → AI - Foundry → Pocket TTS card.

## Troubleshooting
- **500 "could not download weights … voice cloning"** → HF_TOKEN missing/cache wiped; see gated-weights section.
- **First request slow** → model loads lazily into RAM on first synthesis after restart (~30–60s), then fast.
- **Container name conflicts after killed `compose up`** → dockerd phantom name reservation; use a different container_name or restart dockerd. PREVENT: run long creates detached (`setsid nohup docker compose up -d`) — on foundry's disk, creates from multi-GB images take minutes. (Bit us 3× during the NeuTTS saga.)
- **Voice sounds wrong/muddy** → reference is everything: shorter + cleaner beats longer + contaminated; check the reference for music/SFX under the voice.

## Chatterbox — third engine, on the forge GPU (2026-07-10, replaced XTTS-v2)
Chatterbox (Resemble AI, MIT, **base 0.5B English** model) via the **devnen/Chatterbox-TTS-Server**
self-host server, running on **CT 200 "forge"** (t5 node) on the **GTX 1660 Super** — the first
cross-node engine. Replaced XTTS-v2 (see the decommission note below).

| | |
|---|---|
| Endpoint | `http://192.168.0.155:8004` — devnen web UI at `/`, Swagger at `/docs` |
| Stack | `/mnt/docker/chatterbox/compose.yaml` on **CT 200** (plain compose, NOT Komodo — forge has no periphery) |
| Container | `chatterbox`, `gpus: all` + explicit `/dev/nvidia*` devices (same pattern as forge's ollama/sd-webui) |
| Build | local clone of github.com/devnen/Chatterbox-TTS-Server; CUDA 12.1 Dockerfile, fp32 (Turing has no bf16) |
| Config | `./config.yaml` — `model.repo_id: chatterbox` (base 0.5B), `tts_engine.device: cuda`, exaggeration default 0.5 |
| Model cache | `./hf_cache` bind mount (survives rebuilds — the upstream compose's *named volume* would re-download; that file is kept as `docker-compose.yml.upstream`, do NOT deploy from it) |
| VRAM | **On-demand since 2026-07-12: 0 model VRAM by default** (`CHATTERBOX_PRELOAD=false` — no startup load; ~404 MiB process floor once used), loads on first request, **auto-unloads after 10 min idle** (`CHATTERBOX_IDLE_UNLOAD_SEC=600`). In use: **~3.1 GB floor, plateaus ~4.0 GB** (leak FIXED 2026-07-11 — see below). `POST /api/unload` frees the model manually. Compose sets `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` + `CONDS_CACHE_MAX=3` — do not remove either |
| Trailhead | "Chatterbox (engine)" card, AI - Foundry → Voice |

**Server API** (what the gateway uses): `POST /tts` (JSON: `text`, `voice_mode` `clone|predefined`,
`reference_audio_filename` / `predefined_voice_id`, `exaggeration`, `cfg_weight`, `temperature`,
`split_text`, `output_format`) → streamed WAV; `POST /upload_reference` (multipart `files`, **sanitizes
names + skips duplicates** — use the returned filename); `GET /get_predefined_voices`;
`GET /api/model-info` (**there is no `/health`** — use this for readiness); `POST /api/unload` (free VRAM).

**Why base 0.5B and NOT Turbo:** Turbo (350M, 1-step decoder) **silently ignores `exaggeration` and
`cfg_weight`** (CFG stripped for speed — needs batch-2; exaggeration training dropped) — the devnen server
logs "not supported by Turbo version and will be ignored". The emotion knobs are the point of the studio,
so base it is. Turbo remains one dropdown away in the devnen web UI (runtime model hot-swap) if a fast
flat read is ever wanted; `chatterbox-multilingual` (23 langs) is a config-only swap if non-English
cloning is ever needed. All output carries Resemble's inaudible **Perth watermark** (not disableable).

**VRAM leak FIXED 2026-07-11** (was: creep 3.1→5.4 GB over a varied session → intermittent 502s from
CUDA OOM; full forensics in `…/claudeai/tts/chatterbox-vram-leak-findings.md`). Two upstream bugs in the
devnen server's `engine.py`, patched locally (file is **bind-mounted** `./engine.py:/app/engine.py` AND
in the build context; rollback = `git checkout -- engine.py`): (1) the voice-conditioning cache
`_conds_cache` held GPU tensors with **no eviction** — now LRU-capped via **`CONDS_CACHE_MAX`**
(compose env, **3**; each entry costs **~260 MiB** measured, so cap ≈ floor 3.1 GB + N×0.26); (2)
`synthesize()` never released allocator reserve — now `torch.cuda.empty_cache()` in a `finally` per
chunk. Verified: 10 varied voice×exaggeration generations plateau **flat at ~4.0 GB**, all 200, no OOM.
A nightly `docker restart chatterbox` cron (04:00 Phoenix, `/etc/cron.d/chatterbox-restart` in CT200)
stays as backstop.

**VRAM contention (the 6 GB reality, measured 2026-07-10):** chatterbox at its ~4.0 GB plateau +
gemma3:4b **~3.3 GB** > 6 GB — they can't both be fully VRAM-resident. Ollama's `OLLAMA_KEEP_ALIVE=5m`
(already set on forge) means chat models unload after idle; when both are hot, Ollama partially
CPU-offloads (slower chat, not a crash). An SD render on top of resident chatterbox can OOM A1111
(whose post-OOM `--medvram` state corrupts → `docker restart sd-webui`; note A1111 `/sdapi/v1/unload-checkpoint`
does **not** release VRAM under `--medvram` — a container restart is what frees SD's ~2.5 GB). Contention
levers, in order: **(0) automatic — since 2026-07-12 chatterbox holds 0 model VRAM until a request and
self-unloads after 10 min idle** (see the On-demand § below), so an idle chatterbox no longer competes;
(1) **GPU Power button in Voice Studio** (see below — stops the container, frees the full ~4 GB down to ~0);
(2) `curl -X POST http://192.168.0.155:8004/api/unload` (frees the model, process keeps the ~404 MiB floor);
(3) the known 12 GB RTX 3060 / A2000 upgrade path (planned, <$500).

### GPU Power button — stop/start Chatterbox from Voice Studio (2026-07-11)
So the forge 6 GB card can be handed to **Stable Diffusion** without a CLI, the studio's **Chatterbox
Clone** tab has a **GPU Power** panel: a red **⏻ Free GPU — stop Chatterbox** button (JS `confirm()`
before it acts), a **▶ Start Chatterbox** button, and a live status line showing running/stopped + GPU
VRAM. Stopping the container frees the whole ~4 GB (down to ~172 MiB) — more thorough than `/api/unload`,
which leaves the process floor resident. This is the intended lever whenever you want to run image gen.

**Why a helper service was needed:** CUDA has no cross-process VRAM eviction, so *something* must control
Chatterbox's Docker to free the card for SD. The warden was built when Voice Studio was cross-node on foundry;
since 2026-07-12 the gateway and Chatterbox are both on forge, but the same warden chain is retained unchanged
(all same-origin from the browser, matching the gateway's proxy pattern):

| Layer | What |
|---|---|
| Warden (forge) | **`chatterbox-power.service`** — systemd unit running `/opt/chatterbox-power/warden.py` (stdlib-only Python) on **`:8005`** of CT 200. `GET /status` → `{running, vram_used_mib, vram_total_mib}` (via `docker inspect` + `nvidia-smi`); `POST /stop` / `POST /start` → `docker stop/start chatterbox`. **Blast radius hardcoded to the `chatterbox` container** (LAN-only, no auth — homelab norm). `Restart=on-failure`, enabled at boot. |
| Gateway (forge) | `voice-studio/app/main.py` proxy routes `GET /chatterbox/power`, `POST /chatterbox/power/stop`, `POST /chatterbox/power/start` → the warden. Base URL env **`CHATTERBOX_POWER_BASE`** (compose default `http://192.168.0.155:8005`). |
| UI | `studio/index.html` — `refreshCbPower()` polls status on tab open; Stop wrapped in `confirm()`. |

⚠ **Editing-over-SSH trap (learned here):** heredoc'ing JS through `ssh "... <<'EOF'"` double-nests
shell quoting and collapsed `\n`→a real newline inside a JS string literal (syntax error, killed the whole
inline script). Fix: write the patch script **locally + `scp`** it, don't heredoc code through a
double-quoted ssh arg.

**Speed (measured, same Athena line):** first-ever clone of a reference ~18s (one-time upload +
conditioning); subsequent clones **~2–7s** per line (conditioning cache keyed on file+mtime+exaggeration).
XTTS-CPU took 25–46s for the same work.

### On-demand model loading + idle-unload (2026-07-12)
Chatterbox was pinning ~3.3 GB of the 6 GB card **whenever the container ran** (the devnen server loads the
model in FastAPI `lifespan` and never releases it). Since it's only needed for ad-hoc cloning via Voice
Studio (Pocket + Kokoro on forge CPU cover everyday TTS), it now **loads on the first request and unloads
after 10 min idle, container staying up at :8004**. Complements — does not replace — the GPU Power button
(that stops the whole container to ~0; this keeps it reachable and drops just the model).

**How** — patched the devnen `server.py`, which is **now bind-mounted** (`./server.py:/app/server.py` added to
compose next to `engine.py`; edits are restart-only, no `--build`):
- module helpers `_ensure_model_loaded()` (idempotent, double-checked `_model_lock`) and `_idle_monitor()`
  (asyncio task, 60s tick → `engine.unload_model()` when `MODEL_LOADED` and idle > `IDLE_UNLOAD_SEC`);
- `lifespan` skips the startup load unless `CHATTERBOX_PRELOAD=true`, and launches the monitor (cancelled in `finally`);
- the two `if not engine.MODEL_LOADED: 503` guards (`custom_tts_endpoint`, `/v1/audio/speech`) now call
  `_ensure_model_loaded()` first, so a request that arrives cold loads the model instead of erroring.
- **Env (compose):** `CHATTERBOX_IDLE_UNLOAD_SEC=600` (0 = never), `CHATTERBOX_PRELOAD=false`.
- **Backups:** `server.py.bak-pre-idleunload`, `compose.yaml.bak-pre-idleunload`. **Rollback:** drop the
  `./server.py` mount + the two envs → back to load-at-startup.

**Behavior notes / traps:**
- After **▶ Start Chatterbox** (or the nightly 04:00 restart) the container comes up holding **0 model VRAM**
  now — `/api/model-info` reads `loaded:false` until the first request. That's expected, not "broken."
- First request after idle pays a **one-time ~3–8 s** model load; the Voice Studio gateway just needs its
  HTTP timeout to exceed that (it does).
- ⚠ `/v1/audio/speech` `voice` needs the **`.wav` suffix** (`"Olivia.wav"`) or you get a 404 *before* the
  load guard runs.
- The idle-unload cannot fix a **cold load into an already-full card**: with sd-webui holding ~2.5 GB, a
  first TTS load OOMs synthesis (`CUBLAS_STATUS_ALLOC_FAILED`) — free SD first (container restart). Same 6 GB
  ceiling; the 2nd-GPU purchase is the real fix.
- Verified 2026-07-12: boot → 0 VRAM; request → `loaded:true` + valid 127 KB 24 kHz WAV; `/api/unload` →
  `loaded:false`, card back to ~404 MiB floor.

### XTTS-v2 decommission note (2026-07-10)
XTTS-v2 (Coqui/idiap, foundry `:8002`) was **replaced by Chatterbox**: highest-maintenance engine of the
trio (hand-built image, `transformers==4.57.1`+`torchcodec`+CPU-torch pins, stock server exposed none of
its own sampling knobs) and slowest (0.35× realtime on CPU). Container stopped + Voice Studio/announcer/
Trailhead rewired 2026-07-10; **A/B confirmed by ear same night ("chatter is way better") → fully
deleted**: `/mnt/docker/xtts/` removed and `xtts-xtts` image rmi'd (~5 GB reclaimed; compose.yaml +
Dockerfile archive + A/B clips since removed in the 2026-07-11 samba cleanup). Only the stale Komodo UI stack entry remains (TODO #5).
Lessons worth
keeping: prebuilt `ghcr.io/idiap/coqui-tts-cpu` ships no torch; coqui-tts 0.27 needs `transformers==4.57.1`
(5.x dropped `isin_mps_friendly`); Coqui's `/api/tts` language param is `language_id`, NOT `language_idx`
(silently ignored → falls back to `en`).

## Announcer — play Voice Studio voices on the Chromecast (2026-07-07)
A small **`announcer`** service casts Voice Studio audio to the Chromecast Audio **"Home Announcer"**
(`192.168.0.206`). Compose stack at `/mnt/docker/announcer/` on **CT 200/forge** (moved 2026-07-12),
**host-networked**, FastAPI at **`http://192.168.0.155:8011`** (`SELF_URL` env updated .130→.155 in the move —
the CCA fetches the audio from that URL, so it must be forge's IP).
> **⚠ OPEN CAVEAT (2026-07-12): the cast leg is UNVERIFIED from forge.** forge sits behind the MS60 wireless
> mesh backhaul; the "Home Announcer" CCA is a WiFi device. At migration time the CCA was **powered off**
> (HA `media_player.chromecastaudio7822` = off; *foundry couldn't ARP it either*), so it couldn't be tested
> from anywhere. **Risk:** the mesh may L2-isolate forge from WiFi clients (forge's ARP for .206 was
> INCOMPLETE, but so was foundry's while the device was down). **To verify:** power the CCA on, then
> `curl 'http://192.168.0.155:8011/say?text=test&voice=athena/athena_calm.wav&engine=pocket'` — expect audio
> on the speaker. **If it fails** (forge genuinely can't reach the CCA), the fallback is to run *just the
> announcer* back on foundry (its stack dir is still there, stopped): `cd /mnt/docker/announcer && docker
> compose up -d` on CT 130 (revert `SELF_URL` to .130), leaving the engines on forge — the announcer reaches
> the gateway cross-node by IP just as it reaches Chatterbox today. Everything else in the stack is verified.
- **From the Voice Studio UI:** every generated clip now has a **📢 cast** button (beside 💾 save) that
  POSTs the held audio blob to `announcer:/cast_upload` → plays it on Home Announcer (casts the exact
  audio you auditioned, no regeneration). Use the **HTTP** studio URL (`192.168.0.155:8010` /
  `voice-studio.home`) — an HTTPS page (`voice-studio.1701.me`) blocks the cross-origin HTTP cast call
  (mixed content).
- **From anything (curl/HA):** `GET /say?text=...&voice=athena/athena_calm.wav&engine=pocket&volume=0.5`
  regenerates via Voice Studio, serves the WAV, casts it. Engines: `pocket` (default) / `kokoro` /
  `chatterbox` — **`engine=xtts` is kept as a legacy alias for chatterbox** (2026-07-10) so any old
  HA/scripted callers keep working. `POST /cast_upload` (multipart `audio` +
  `volume`) casts an existing clip. Temp WAVs auto-pruned after 10 min.
- **How it works:** the CCA plays a *URL it fetches itself*, so the announcer serves the WAV at
  `http://192.168.0.155:8011/audio/<id>.wav` (host-reachable) and drives playback via **pychromecast**
  (`get_chromecasts(known_hosts=["192.168.0.206"])`, retried — mDNS is lossy). CORS `*` on the announcer
  so the UI button can call it.
- **Files:** `/mnt/docker/announcer/{app.py,Dockerfile,requirements.txt,compose.yaml}`; UI button
  (`castClip`) in `voice-studio/studio/index.html` (read per request, rebuild-free; `.bak` kept).
  ⚠ **castClip POSTs to a HARDCODED absolute IP** `http://192.168.0.155:8011/cast_upload` (must be an
  http:// absolute URL — mixed-content/proxy won't work; see the ui-guide landmine). The 2026-07-12 forge
  migration missed this literal (it stayed `.130` → casting silently broke); **repointed .130→.155 2026-07-12**.
  Re-edit it directly if the announcer ever moves. ⚠ **Announcer
  app edits need `docker compose up -d --build` — `app.py` is BAKED into the image (COPY, no bind mount);
  a plain `docker restart` silently keeps the old code** (bit us on the 2026-07-10 chatterbox remap).
- Chromecast provisioning itself (orphaned CCA → local `eureka` API): `troubleshoot/chromecast-audio-provisioning.md`.
- **Trailhead card** "Announcer (cast)" (AI - Foundry tab, Voice group — same group as the engine cards)
  → `:8011/docs` (added 2026-07-09 — the root path is API-only/404, Swagger is the landing page).

## Home Assistant integration
Where HA voice stands relative to the local TTS stack — written 2026-07-09, per the HA voice sessions of
2026-07-05→08 plus a live check:

**HA voice today is fully cloud.** Both Assist pipelines ("Home Assistant Cloud" and the preferred
"Concierge") use Nabu Casa cloud STT/TTS (`stt./tts.home_assistant_cloud`, voices JennyNeural/SaraNeural).
Nothing in HA is wired to the forge TTS engines yet.

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
  `http://192.168.0.155:8880/v1`, model `kokoro`, any preset voice → creates a `tts.` entity that Chime
  TTS and the Assist pipelines can use instead of cloud. Explained 2026-07-08, **not installed yet**.
- **Pocket TTS (Athena/Majel)**: its API is not OpenAI-shaped, so reaching HA-native TTS needs a small
  OpenAI-compatible (or Wyoming) shim in front of `pocket-engine`. Until then the Athena voice reaches
  speakers only via the announcer path above.

## Open TODOs (voice stack)
1. HA long-lived access token → build the `via=hass` announcer path + `rest_command.announcer_say` + 🏠 HA studio chip.
2. Kokoro as an HA-native `tts.` entity (HACS OpenAI TTS Speech Service → `:8880/v1`), then point Chime TTS/pipelines at it.
3. OpenAI-compatible shim for pocket-engine so Athena/Majel can be an HA pipeline voice.
4. Kokoro blend → promote-to-Pocket-reference button (Pocket/Chatterbox clips have ➜ voice; Kokoro blends don't).
5. Remove the dead `xtts` stack entry in the **Komodo UI** (the deploy itself is fully deleted — this is
   just the stale registration; one click).
6. Consider PBS/backup coverage for forge/CT200's `/mnt/docker` (now chatterbox + ollama + sd-webui **+ the
   four migrated voice stacks** — more valuable to back up after 2026-07-12).
7. **Verify the announcer cast leg from forge** (see the ⚠ caveat in the Announcer §) — the CCA was offline
   at migration; confirm forge can reach it, else fall back to running just the announcer on foundry.
8. After a soak period, delete the stopped foundry voice stacks' images/containers (~9 GB) once the announcer
   caveat is resolved and rollback is no longer wanted (ask first).

## History

- **2026-07-12 — ENTIRE voice stack consolidated onto forge (CT 200, t5 node).** The four CPU-side pieces
  (pocket-tts, kokoro, voice-studio gateway, announcer) moved from foundry/CT 130 to join Chatterbox on forge,
  so all TTS now lives on one box. Method: t5 host CIFS-mounts the documents samba (`//192.168.0.176/documents`,
  uid/gid 100000) → `mp0` into CT 200 (so the voices/clips paths resolve unchanged); `tts-network.service`
  copied to forge (recreates the `tts` docker net); stack dirs rsynced; `pocket-tts` (3.17 GB) + kokoro images
  moved via `docker save|load` and pull; voice-studio + announcer rebuilt on forge; announcer `SELF_URL`
  .130→.155. Repointed: NPM proxy hosts 212/213 (DB + conf), Trailhead Voice cards, Komodo (the 3 foundry stack
  defs re-pointed to the `forge` server + announcer newly registered → all 5 adopted, running). **Straggler
  found + fixed 2026-07-12:** the studio UI's 📢 cast button hardcoded `192.168.0.130:8011` (not covered by the
  SELF_URL/NPM repoints) → silently broken casting; repointed to `.155`. Pre-migration
  LVM-thin snapshot `pre_tts_migration` taken. **Verified end-to-end:** pocket/kokoro/chatterbox generate
  through the gateway, voice list + a `/save` round-trip to the samba share both work over the SMB mount.
  **NOT verified:** the announcer→Chromecast cast — the CCA was powered off during the migration (see the
  Announcer § caveat). Foundry freed of ~9 GB images + its 6.5 GB of TTS mem-limits; its stopped stack dirs
  are the rollback. (Foundry's open-webui + searxng also moved to forge 2026-07-12; CT 130 is being retired.)

- **2026-07-11 (later still) — Studio UI redesigned via Claude Design.** New `index.html` (~910
  lines) produced in a sandboxed Claude Design session (handoff via samba `tts/ui-rebuild/` — that
  session has no shell/SSH, files must be uploaded to it), contract-reviewed against the ui-guide
  (all fetch surfaces + landmines intact, incl. the HTTP cast button and legacy `x*` element ids),
  deployed live-on-refresh. Visual/organizational only: per-tab ⓘ help popovers, grouped controls,
  collapsible Saved-clips/Voice-library panels (localStorage-persisted). API contract unchanged;
  previous UI kept as `index.html.bak`.
- **2026-07-11 (later) — Chatterbox VRAM leak fixed.** Intermittent `/generate_chatterbox` 502s =
  CUDA OOM from two upstream `engine.py` bugs (unbounded GPU-tensor voice cache + no per-generation
  allocator release). Patched locally (LRU cap `CONDS_CACHE_MAX=3` + `empty_cache()` in a finally),
  deployed via bind mount, hardened per pre-deploy opus review (env clamp, race-safe eviction).
  Measured ~260 MiB per cache entry; verified flat ~4.0 GB plateau over varied generations. Nightly
  restart cron kept as backstop. Forensics doc: `…/claudeai/tts/chatterbox-vram-leak-findings.md`.
- **2026-07-11 — Real split: standalone voice-studio gateway + engine-only pocket-tts.** The 2026-06-15
  ROLE-flag arrangement (one image, two containers, code living in the neighbor's dir) was rebuilt into
  properly-separated stacks: `/mnt/docker/voice-studio/` now owns its own slim image (`voice-studio:latest`,
  python:3.12-slim, no pocket_tts dep), its own `app/main.py` (all gateway routes; builtin voice list
  proxied from the engine, graceful when the engine is down) and `studio/index.html`;
  `/mnt/docker/pocket-tts/` trimmed to engine-only `main.py` (gateway routes 404 there) with the original
  image retagged `pocket-tts:latest` (deliberately NOT rebuilt — rolling base tag). External surface
  unchanged (ports, API contract, `tts` network, voice/clip mounts, Trailhead, DNS). Cleanup: orphan
  `xtts_default` network + empty `/mnt/docker/xtts/` removed. Old image kept as rollback. Pre- and
  post-implementation multi-agent (opus) reviews; pre-review caught 2 CRITICAL packaging bugs
  (missing WORKDIR/CMD; a surviving `import typer` in the slim image) + a stale-backup rollback trap.
  **Rollback to the ROLE-era gateway is NOT a one-file restore** — `voice-studio/compose.yaml.bak`
  mounts files that moved; the prerequisite steps are written at the top of that .bak itself.
- **2026-07-10 — XTTS-v2 → Chatterbox (first GPU engine).** XTTS dumped as highest-maintenance/slowest;
  Chatterbox base 0.5B (devnen server, CUDA fp32) deployed on forge/CT200's GTX 1660 Super at
  `192.168.0.155:8004`. Gateway `/generate_xtts` + `/xtts/*` routes replaced by `/generate_chatterbox` +
  `/chatterbox/voices`; cloning went shared-path → HTTP upload (content-hashed, dedup'd); studio tab now
  has exaggeration/cfg_weight/temperature sliders (base chosen over Turbo BECAUSE Turbo ignores the first
  two); announcer's `engine=xtts` remapped with alias kept. Measured: chatterbox 3.3 GB VRAM resident,
  ~2–7s/line vs XTTS's 25–46s. A/B passed by ear same night → XTTS fully deleted (see decommission note).
  Multi-agent recon + adversarial review preceded the swap (caught the Turbo-ignores-emotion-knobs trap
  and the announcer dependency); a post-deploy review round caught three more: the announcer patch needed
  an image **rebuild** (app.py is baked — a restart doesn't apply it), forge's rootfs hit 100% (16 GB
  chatterbox build cache → pruned, rootfs grown 90→130 G), and CUDA-allocator creep caused generation
  OOMs → fixed with `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` in the chatterbox compose.
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
  Verified end-to-end (all three tabs generate through the gateway). The pre-split backup dir was removed in the 2026-07-11 samba cleanup
  (superseded by the real split's on-box .baks).
- 2026-06-10: Deployed; bake-off vs NeuTTS Air (q4-GGUF fork) — Pocket TTS won on voice
  quality (user ear test) and operational simplicity. NeuTTS stack/image/folder removed
  (22GB reclaimed). Athena references built same day.
