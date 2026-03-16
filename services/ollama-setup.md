# Ollama + Open WebUI

**Last Updated**: 2026-03-16
**Related Systems**: Container 130 (ollama)

## Summary
Dedicated LXC container running Ollama with Intel Iris Xe iGPU acceleration (via IPEX-LLM) and Open WebUI chat interface. Migrated from CT 128 (Komodo) to isolate memory-heavy model loading from other services.

## Container Details

| Setting | Value |
|---------|-------|
| CTID | 130 |
| Hostname | ollama |
| IP | 192.168.0.130 |
| OS | Ubuntu 22.04 LTS |
| Mode | Privileged |
| Cores | 4 |
| RAM | 10GB |
| Swap | 4GB |
| Disk | 50GB on `littlestorage` |
| Onboot | yes |
| GPU | Intel Iris Xe (shared with CT 128) |
| Bind Mount | `/mnt/docker` (shared docker data) |

## Services

| Service | URL | Purpose |
|---------|-----|---------|
| Ollama API | http://192.168.0.130:11434 | LLM inference API (GPU-accelerated) |
| Open WebUI | http://192.168.0.130:8085 | Chat interface (no auth) |

## Model

- **mistral:7b** (Q4_K_M, ~4.4GB) — general-purpose 7B parameter model

### Managing Models
```bash
# List models
docker exec ollama /llm/ollama/ollama list

# Pull a new model
docker exec ollama /llm/ollama/ollama pull <model:tag>

# Remove a model
docker exec ollama /llm/ollama/ollama rm <model:tag>
```

## Configuration

### Compose File (`/opt/ollama/compose.yaml`)
```yaml
services:
  ollama:
    image: ipex_ollama:latest
    container_name: ollama
    restart: unless-stopped
    security_opt:
      - apparmor=unconfined
    ports:
      - "11434:11434"
    devices:
      - /dev/dri:/dev/dri
    volumes:
      - /mnt/docker/ollama/models:/models
      - /mnt/docker/ollama/logs:/logs
    environment:
      DEVICE: "iGPU"
      OLLAMA_NUM_GPU: "999"
      OLLAMA_INTEL_GPU: "true"
      OLLAMA_HOST: "0.0.0.0"
      OLLAMA_NUM_PARALLEL: "1"
      OLLAMA_MODELS: "/models"
      OLLAMA_KEEP_ALIVE: "-1"
      OLLAMA_NUM_CTX: "8192"
      ZES_ENABLE_SYSMAN: "1"
      SYCL_CACHE_PERSISTENT: "1"
      SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS: "1"
      ONEAPI_DEVICE_SELECTOR: "level_zero:0"
      PATH: "/llm/ollama:${PATH}"
      NO_PROXY: "localhost,127.0.0.1"
    command: bash -c "/llm/ollama/ollama serve > /logs/ollama.log 2>&1"
    healthcheck:
      test: ["CMD-SHELL", "/llm/ollama/ollama list || exit 1"]
      interval: 60s
      timeout: 10s
      retries: 5
      start_period: 90s

  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: open-webui
    restart: unless-stopped
    security_opt:
      - apparmor=unconfined
    ports:
      - "8085:8080"
    volumes:
      - /mnt/docker/ollama/open-webui:/app/backend/data
    environment:
      OLLAMA_BASE_URL: "http://ollama:11434"
      WEBUI_AUTH: "false"
    depends_on:
      ollama:
        condition: service_healthy
```

### Custom Docker Image
The Ollama container uses a locally-built image based on Intel's IPEX-LLM. The Dockerfile at `/opt/ollama/Dockerfile`:
```dockerfile
FROM intelanalytics/ipex-llm-inference-cpp-xpu:latest
RUN mkdir -p /llm/ollama && cd /llm/ollama && init-ollama
ENV LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/llm/ollama"
WORKDIR /llm/ollama
```

To rebuild after base image update:
```bash
docker pull intelanalytics/ipex-llm-inference-cpp-xpu:latest
docker build -t ipex_ollama:latest /opt/ollama/
cd /opt/ollama && docker compose up -d
```

### Key Environment Variables
- `OLLAMA_INTEL_GPU=true` — enable Intel GPU inference via oneAPI
- `OLLAMA_NUM_GPU=999` — offload all model layers to GPU
- `OLLAMA_NUM_PARALLEL=1` — one request at a time (memory constrained)
- `OLLAMA_KEEP_ALIVE=-1` — never unload model from memory (avoids 4.4GB reload from HDD)
- `OLLAMA_NUM_CTX=8192` — context window size
- `DEVICE=iGPU` — Intel integrated GPU target
- `WEBUI_AUTH=false` — no login required for Open WebUI

### GPU Passthrough
CT 130 shares the Intel Iris Xe iGPU with CT 128 (Immich). Config in `/etc/pve/lxc/130.conf`:
```
dev0: /dev/dri/card0,gid=44
dev1: /dev/dri/renderD128,gid=104
```

### Data Locations
- Model data: `/mnt/docker/ollama/models`
- Ollama logs: `/mnt/docker/ollama/logs/ollama.log`
- Open WebUI data: `/mnt/docker/ollama/open-webui`

## Management

Not managed by Komodo — access via SSH or `pct exec`:
```bash
# Check status
ssh claude@192.168.0.151 'sudo pct exec 130 -- docker ps'

# View Ollama logs
ssh claude@192.168.0.151 'sudo pct exec 130 -- cat /mnt/docker/ollama/logs/ollama.log'

# View Open WebUI logs
ssh claude@192.168.0.151 'sudo pct exec 130 -- docker logs open-webui'

# Restart stack
ssh claude@192.168.0.151 'sudo pct exec 130 -- bash -c "cd /opt/ollama && docker compose restart"'
```

## Verification
- Ollama API: `curl http://192.168.0.130:11434/api/tags`
- Open WebUI: Browse to `http://192.168.0.130:8085`
- GPU in use: check `ollama.log` for `library=oneapi` and `name="Intel(R) Iris(R) Xe Graphics"`
- Container health: `docker ps` should show both as "healthy"
- Test speed: `curl -s http://192.168.0.130:11434/api/generate -d '{"model":"mistral:7b","prompt":"Hi","stream":false}'`

## Troubleshooting

### Open WebUI slow to start
First boot takes 30-90 seconds — it initializes the database and downloads embedding models. Check logs with `docker logs open-webui`.

### I/O delay spike on first query
After a container restart, the first query loads the 4.4GB model from HDD into RAM. With `OLLAMA_KEEP_ALIVE=-1` the model stays loaded permanently, so subsequent queries are fast. Only restarts trigger a reload.

### GPU not detected
Check `ollama.log` for `OLLAMA_INTEL_GPU:true` and `library=oneapi`. If it shows `library=cpu`, verify `/dev/dri` is visible inside the container (`ls -la /dev/dri/`) and that `OLLAMA_INTEL_GPU=true` is set in the compose.

### Performance baseline
- ~7-8 tokens/sec with Intel Iris Xe GPU acceleration
- First query after restart: ~30s (model load from HDD)
- Subsequent queries: ~2-3s for short responses
