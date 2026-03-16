# Ollama + Open WebUI

**Last Updated**: 2026-03-15
**Related Systems**: Container 130 (ollama)

## Summary
Dedicated LXC container running Ollama (local LLM inference) and Open WebUI (chat interface). Migrated from CT 128 (Komodo) to isolate memory-heavy model loading from other services.

## Container Details

| Setting | Value |
|---------|-------|
| CTID | 130 |
| Hostname | ollama |
| IP | 192.168.0.130 |
| OS | Ubuntu 22.04 LTS |
| Mode | Privileged |
| Cores | 2 |
| RAM | 10GB |
| Swap | 4GB |
| Disk | 50GB on `littlestorage` |
| Onboot | yes |
| Bind Mount | `/mnt/docker` (shared docker data) |

## Services

| Service | URL | Purpose |
|---------|-----|---------|
| Ollama API | http://192.168.0.130:11434 | LLM inference API |
| Open WebUI | http://192.168.0.130:8085 | Chat interface (no auth) |

## Model

- **mistral:7b** (Q4_K_M, ~4.1GB) — general-purpose 7B parameter model

### Managing Models
```bash
# List models
docker exec ollama ollama list

# Pull a new model
docker exec ollama ollama pull <model:tag>

# Remove a model
docker exec ollama ollama rm <model:tag>
```

## Configuration

### Compose File (`/opt/ollama/compose.yaml`)
```yaml
services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: unless-stopped
    security_opt:
      - apparmor=unconfined
    ports:
      - "11434:11434"
    volumes:
      - /mnt/docker/ollama/data:/root/.ollama
    environment:
      - OLLAMA_NUM_PARALLEL=1
      - OLLAMA_MAX_LOADED_MODELS=1
      - OLLAMA_NUM_THREADS=2
      - OLLAMA_KEEP_ALIVE=10m
    healthcheck:
      test: ["CMD-SHELL", "ollama list || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

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
      - OLLAMA_BASE_URL=http://ollama:11434
      - WEBUI_AUTH=false
    depends_on:
      ollama:
        condition: service_healthy
```

### Key Environment Variables
- `OLLAMA_NUM_PARALLEL=1` — one request at a time (memory constrained)
- `OLLAMA_MAX_LOADED_MODELS=1` — only one model in memory
- `OLLAMA_NUM_THREADS=2` — matches 2-core LXC allocation
- `OLLAMA_KEEP_ALIVE=10m` — unload model after 10min idle
- `WEBUI_AUTH=false` — no login required for Open WebUI

### Data Locations
- Model data: `/mnt/docker/ollama/data` (bind mount)
- Open WebUI data: `/mnt/docker/ollama/open-webui` (bind mount)

## Management

Not managed by Komodo — access via SSH or `pct exec`:
```bash
# Check status
ssh claude@192.168.0.151 'sudo pct exec 130 -- docker ps'

# View logs
ssh claude@192.168.0.151 'sudo pct exec 130 -- docker logs ollama'
ssh claude@192.168.0.151 'sudo pct exec 130 -- docker logs open-webui'

# Restart stack
ssh claude@192.168.0.151 'sudo pct exec 130 -- bash -c "cd /opt/ollama && docker compose restart"'

# Update images
ssh claude@192.168.0.151 'sudo pct exec 130 -- docker pull ollama/ollama:latest'
ssh claude@192.168.0.151 'sudo pct exec 130 -- docker pull ghcr.io/open-webui/open-webui:main'
ssh claude@192.168.0.151 'sudo pct exec 130 -- bash -c "cd /opt/ollama && docker compose up -d"'
```

## Verification
- Ollama API: `curl http://192.168.0.130:11434/api/tags`
- Open WebUI: Browse to `http://192.168.0.130:8085`
- Container health: `docker ps` should show both as "healthy"

## Troubleshooting

### Open WebUI slow to start
First boot takes 30-60 seconds — it initializes the database and downloads embedding models. Check logs with `docker logs open-webui`.

### Model loading slow / high memory
With 10GB RAM and `OLLAMA_KEEP_ALIVE=10m`, the model unloads after idle. First query after idle will take longer as the model reloads. If memory is tight, reduce to a smaller model (e.g., `phi3:mini`).
