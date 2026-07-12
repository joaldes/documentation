# GPU VRAM Monitoring — forge / t5 (GTX 1660 Super)

**Last Updated**: 2026-07-12
**Related Systems**: t5 PVE host (192.168.0.152), CT 200 forge (192.168.0.155), CT 128 Prometheus/Grafana

## Summary
Per-container VRAM monitoring for the GTX 1660 Super on the t5 node. A collector on the t5 host attributes every GPU process to its docker container inside forge (ollama / chatterbox / sd-webui), exports the numbers through the existing node-exporter → Prometheus pipeline, and a Grafana dashboard + Telegram alert sit on top. Built because the 6 GB card is chronically contended and OOM debugging previously required manual `nvidia-smi` + `/proc` spelunking.

## Problem / Goal
Three GPU consumers share 6 GB: Ollama (~3.3 GB with a model loaded), Chatterbox TTS (~3.3–4.0 GB resident), sd-webui (~116 MiB idle, 2–4 GB with a checkpoint loaded). `nvidia-smi` shows only anonymous host PIDs (`python3`, `venv/bin/python`) — no way to see *what* holds the VRAM, and no history or alerting.

## Solution
- **Collector**: `/usr/local/bin/gpu-vram-textfile.py` on the **t5 host** (not inside forge — the host sees all PIDs and can resolve them). Maps each nvidia-smi compute PID → `docker-<id>` in `/proc/<pid>/cgroup` → container name via one `pct exec 200 -- docker ps --no-trunc` call. Writes Prometheus textfile metrics atomically to `/var/lib/prometheus/node-exporter/gpu.prom`.
- **Schedule**: `/etc/cron.d/gpu-vram-metrics` — every minute (same pattern as the existing smartmon/nvme textfile crons).
- **Transport**: node-exporter's textfile collector on `t5-host:9100`, already scraped by Prometheus (CT 128) — zero Prometheus config changes.
- **Dashboard**: Grafana **`http://192.168.0.179:3001/d/gpu-forge/`** — stacked per-container VRAM with total-used + card-max lines, VRAM gauge (70/90% thresholds), current-allocation table, util/temp/power. Created via the Grafana API (not file-provisioned; lives in Grafana's DB).
- **Alert**: rule `gpu-vram-high` (folder "GPU", group `gpu`, eval 1m): VRAM >90% for 5 min → contact point **`telegram-homelab`** (bot + chat id reused from the arr-stack Telegram wiring; chat id `-4576105359`). Root notification policy routes to it. `noDataState: NoData` doubles as a collector-down signal.
- **Live view**: `nvtop` installed on the t5 host; `watch -n2 nvidia-smi` also works.

## Metrics
```
nvidia_gpu_up                                  1 = collection OK, 0 = nvidia-smi failed
nvidia_gpu_memory_used_bytes / nvidia_gpu_memory_total_bytes
nvidia_gpu_utilization_percent
nvidia_gpu_temperature_celsius
nvidia_gpu_power_watts
nvidia_gpu_container_memory_bytes{container="chatterbox|ollama|sd-webui|..."}
```
Labels are docker container names; a GPU process not in a forge container falls back to its command basename. No `pid` label (avoids series churn); multiple PIDs in one container are summed.

## Key Files
- t5 host: `/usr/local/bin/gpu-vram-textfile.py` — collector (python3 stdlib only)
- t5 host: `/etc/cron.d/gpu-vram-metrics` — `* * * * * root /usr/local/bin/gpu-vram-textfile.py` (PATH includes `/usr/sbin` for `pct`)
- t5 host: `/var/lib/prometheus/node-exporter/gpu.prom` — output (atomic tmp+rename)
- Grafana (API-managed, in DB): dashboard uid `gpu-forge`, alert rule uid `gpu-vram-high`, contact point `telegram-homelab`
- CT 128: `/mnt/docker/trailhead/trailhead.yaml` — card `gpu-vram` (AI - Foundry section)

## Verification
```bash
# collector runs and attributes correctly
ssh root@192.168.0.152 /usr/local/bin/gpu-vram-textfile.py && ssh root@192.168.0.152 cat /var/lib/prometheus/node-exporter/gpu.prom

# exported + scraped
curl -s http://192.168.0.152:9100/metrics | grep ^nvidia_gpu
curl -s 'http://192.168.0.179:9092/api/v1/query?query=nvidia_gpu_container_memory_bytes'
```
Then load/unload something (generate a TTS line, load an Ollama model) and watch the dashboard move within ~1 min.

## Troubleshooting
- **`nvidia_gpu_up 0`**: nvidia-smi failing on the t5 host — check the driver (`nvidia-smi` by hand; DKMS should survive kernel updates per the t5 build notes).
- **Metric missing entirely / stale**: cron or node-exporter problem — check `stat /var/lib/prometheus/node-exporter/gpu.prom` mtime and `systemctl status prometheus-node-exporter cron` on t5.
- **Container shows as 12-hex-char id or command name**: the process isn't in forge (CT 200) or `docker ps` timed out; if a second GPU LXC is ever added, extend `FORGE_CT`/`container_names()` in the collector.
- **Alert fires constantly**: usually sd-webui holding a checkpoint after image gen (it does NOT auto-unload) — `docker restart sd-webui` in forge frees it. Chatterbox creep should be gone (LRU cache fix 2026-07-11, nightly 04:00 restart as backstop).
- **Telegram silent**: contact point shares the arr-stack bot; if the arrs still notify, the problem is in Grafana (`docker logs grafana | grep -i telegram` on CT 128).
