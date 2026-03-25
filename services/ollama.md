# Ollama (Container 130)

**Last Updated**: 2026-03-25
**Related Systems**: LXC 130 (192.168.0.130), Open WebUI (:8085), Ollama API (:11434)

## Summary

Local LLM inference running on Intel Iris Xe iGPU via Intel IPEX-optimized Ollama. Two models configured: a fast general-purpose model and a coding-focused model. Accessible via Open WebUI at `192.168.0.130:8085`.

## Infrastructure

- **Container**: LXC 130 (Ubuntu, 10GB RAM, 5 cores)
- **GPU**: Intel Iris Xe iGPU passed through (`/dev/dri/card0`, `/dev/dri/renderD128`)
- **Docker Image**: `ipex_ollama:latest` (Intel-optimized build)
- **Storage**: 50GB root on `littlestorage`, models at `/models`
- **Open WebUI**: `ghcr.io/open-webui/open-webui:main`

## Models

| Model | Size | Speed | Prompt Processing | Use Case |
|-------|------|-------|-------------------|----------|
| **qwen2.5:1.5b** | 1.0 GB | 23 tok/s | 147 tok/s | Fast daily chat, quick questions, summaries |
| **qwen2.5-coder:3b** | 1.9 GB | ~13 tok/s | ~80 tok/s | Code generation, Node-RED flows, YAML/JSON configs |

**Total model storage**: 2.9 GB

## Key Configuration

| Setting | Value | Purpose |
|---------|-------|---------|
| `OLLAMA_KEEP_ALIVE` | `-1` | Models stay loaded in GPU memory permanently |
| `OLLAMA_NUM_CTX` | `8192` | Context window size (tokens) |
| `OLLAMA_NUM_GPU` | `999` | Use GPU for all layers |
| `OLLAMA_NUM_PARALLEL` | `1` | One request at a time (iGPU memory constraint) |
| `OLLAMA_INTEL_GPU` | `true` | Enable Intel GPU acceleration |
| `ONEAPI_DEVICE_SELECTOR` | `level_zero:0` | Select Intel iGPU device |

## Performance Notes

### Speed Expectations
- **First request after restart**: ~15-25s delay (model loading from disk to GPU memory)
- **Subsequent requests (same model)**: <0.5s to first token
- **Model switching**: ~15-25s delay (unload old model, load new one)
- **Long conversations**: Prompt processing slows as history grows (~147 tok/s for 1.5b, ~80 tok/s for 3b). A 1,500 token conversation takes ~10-12s before first token on the 1.5b model.

### Tips for Best Performance
- **Start new chats** when you don't need conversation history — first message is always fast
- **Stick to one model** per session to avoid model swap delays
- Use **qwen2.5:1.5b** as default — switch to coder only when writing code
- Shorter model responses = faster future prompts (history grows slower)

### Hardware Limitations
- Intel Iris Xe iGPU shares system memory — no dedicated VRAM
- `OLLAMA_NUM_PARALLEL=1` means requests are serialized (only one at a time)
- 7B+ models are too slow on this hardware (~7 tok/s) — stick to 3B and under
- These local models are not comparable to cloud LLMs (Claude, GPT-4) in quality. They hallucinate more, struggle with complex reasoning, and give surface-level answers. Best for simple/private tasks.

## Model Management

```bash
# List models
curl -s http://192.168.0.130:11434/api/tags | jq '.models[] | {name, size}'

# Pull a new model
curl -s http://192.168.0.130:11434/api/pull -d '{"name":"model:tag"}'

# Remove a model
curl -s -X DELETE http://192.168.0.130:11434/api/delete -d '{"name":"model:tag"}'

# Test model performance
curl -s http://192.168.0.130:11434/api/generate -d '{"model":"qwen2.5:1.5b","prompt":"your prompt","stream":false}'
```

## Recommended Models for Intel Iris Xe

If swapping models in the future, stay within these ranges:

| Tier | Size | Speed | Notes |
|------|------|-------|-------|
| Fast | 0.5-1.5B | 23-40+ tok/s | Quick but shallow answers |
| Balanced | 1.5-3B | 13-23 tok/s | Best quality/speed tradeoff for this hardware |
| Max quality | 3-4B | 9-13 tok/s | Diminishing returns below this speed |
| Too slow | 7B+ | <7 tok/s | Not recommended for this iGPU |

## Troubleshooting

**Slow first response**: Model is loading from disk. Wait ~20s, subsequent requests will be fast.

**All responses slow**: Model may have been evicted. Check with:
```bash
curl -s http://192.168.0.130:11434/api/ps
```

**Out of memory**: Container has 10GB RAM. If loading a large model fails, remove unused models first.

**GPU not detected**: Verify `/dev/dri/card0` and `/dev/dri/renderD128` exist inside the container:
```bash
ssh claude@192.168.0.151 "sudo pct exec 130 -- docker exec ollama ls -la /dev/dri/"
```
