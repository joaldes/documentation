# Docker CPU Optimization — Resource Limits & cAdvisor Tuning

**Last Updated**: 2026-03-23
**Related Systems**: Container 128 (Komodo), Proxmox Host (Shipyard)

## Summary

Added CPU resource limits to 19 previously unlimited Docker containers on Komodo (CT 128) and tuned cAdvisor's polling interval. Host load average dropped from ~2.0 to ~1.14 (43% reduction). cAdvisor memory usage dropped from 1.34 GiB to 83 MiB (94% reduction).

## Problem

The Proxmox host (i5-11320H, 4 cores / 8 threads) was running at a sustained load average of ~2.0 with 46 Docker containers across 20 compose projects on CT 128. Investigation revealed:

1. **cAdvisor** was the biggest offender — consuming 3-68% CPU (highly variable) and 1.34 GiB memory with zero resource limits and default 1-second polling interval
2. **19 Docker containers** had no CPU limits at all, meaning any container could monopolize the host
3. Only 7 containers (prometheus, grafana, birdnet-go, frigate, immich, paperless, bentopdf) had existing CPU limits

### Pre-Change CPU Snapshot (Baseline)

```
NAME                      CPU %     MEM USAGE / LIMIT
cadvisor                  3.12%     1.344GiB / 32GiB     ← no limits, spiked to 68%
karakeep-web-1            1.15%     333.9MiB / 32GiB     ← no limits
komodo-postgres-1         1.16%     352.2MiB / 32GiB     ← no limits
komodo-web-1              1.03%     331.4MiB / 32GiB     ← no limits
authentik-server          0.30%     432.5MiB / 1GiB      ← mem limit only
authentik-worker          0.13%     450.2MiB / 1GiB      ← mem limit only
sftpgo-server             0.09%     34MiB / 32GiB        ← no limits
tandoor-web               0.04%     656MiB / 32GiB       ← no limits
```

Host load average: **~2.0**

## Solution

Two-pronged approach:
1. **Tune cAdvisor** — reduce polling from 1s to 30s, disable unnecessary metrics, add resource caps
2. **Add CPU limits** to all 19 unlimited containers using appropriate compose syntax per file

### Limit Style Convention

Two compose limit styles are used across the system. Each file was matched to its existing convention:

| Style | Used When | Example |
|-------|-----------|---------|
| **Shorthand** (`cpus:`, `mem_limit:`) | File already uses shorthand | prometheus, authentik, bento-pdf |
| **Deploy** (`deploy.resources.limits`) | File has no existing limits, or already uses deploy | mealie, trailhead, karakeep, tandoor, etc. |

Both styles are fully supported on Docker Compose v5.0.0 with cgroup v2.

## Changes By Stack

### 1. Prometheus Stack — cAdvisor Tuning (Biggest Win)

**File**: `/etc/komodo/stacks/prometheus/compose.yaml`

**cAdvisor** — added command flags and resource limits:

```yaml
cadvisor:
  image: gcr.io/cadvisor/cadvisor:latest
  command:
    - '--housekeeping_interval=30s'           # default 1s — way too frequent
    - '--docker_only=true'                    # skip non-Docker cgroups
    - '--disable_metrics=percpu,disk,diskIO'  # only ones not already disabled by default
  cpus: 0.5
  mem_limit: 2G
```

**Why these flags matter:**
- `--housekeeping_interval=30s` — cAdvisor polls all container stats every 1s by default. Prometheus only scrapes every 30s, so 29 out of 30 polls were wasted work. This single flag eliminated most of the CPU usage.
- `--docker_only=true` — skips scanning non-Docker cgroups (systemd services, LXC internals) that we don't monitor
- `--disable_metrics=percpu,disk,diskIO` — most metrics (sched, tcp, udp, hugetlb, referenced_memory, memory_numa, cpu_topology) are already disabled by default in recent cAdvisor versions. Only percpu, disk, and diskIO needed explicit disabling.

**ENTRYPOINT note**: cAdvisor's image uses `ENTRYPOINT ["/usr/bin/cadvisor", "-logtostderr"]`. The compose `command:` overrides CMD (not ENTRYPOINT), so `-logtostderr` must NOT be included in the command list — it's already baked into the entrypoint.

**mem_limit at 2G**: Pre-change usage was 1.34 GiB. Started at 2G as a safe ceiling. Post-tuning usage dropped to ~83 MiB — can be reduced to 512M in the future.

**alertmanager** — added limits (previously none):
```yaml
alertmanager:
  cpus: 0.25
  mem_limit: 256M
```

**blackbox-exporter** — added limits (previously none):
```yaml
blackbox-exporter:
  cpus: 0.25
  mem_limit: 128M
```

### 2. Authentik Stack — CPU Limits

**File**: `/etc/komodo/stacks/authentik/compose.yaml`
**Style**: Shorthand (matches existing `mem_limit:`/`mem_reservation:`)

| Service | CPU Limit Added | Existing Memory Limit |
|---------|-----------------|----------------------|
| server | `cpus: 1.0` | mem_limit: 1g |
| worker | `cpus: 0.5` | mem_limit: 1g |
| postgresql | `cpus: 0.5` | mem_limit: 512m |
| redis | `cpus: 0.25` | mem_limit: 256m |

### 3. Komodo Core Stack — CPU Limits

**File**: `/opt/komodo/compose.yaml` (note: different path from other stacks)
**Style**: `deploy.resources.limits`

| Service | CPU Limit Added |
|---------|----------------|
| core | `cpus: "1.0"` |
| periphery | `cpus: "0.5"` |
| postgres | `cpus: "0.5"` |
| ferretdb | `cpus: "0.25"` |

### 4. Karakeep Stack — CPU Limits

**File**: `/etc/komodo/stacks/karakeep/compose.yaml`
**Style**: `deploy.resources.limits`

| Service | CPU Limit Added |
|---------|----------------|
| web | `cpus: "0.5"` |
| chrome | `cpus: "0.5"` |
| meilisearch | *not limited — see Known Issues* |

### 5. Tandoor Stack — CPU Limits

**File**: `/etc/komodo/stacks/tandoor/compose.yaml`
**Style**: `deploy.resources.limits`

| Service | CPU Limit Added |
|---------|----------------|
| web_recipes | `cpus: "0.5"` |
| db_recipes | `cpus: "0.5"` |

### 6. Fragments Stack — CPU + Memory Limits

**File**: `/etc/komodo/stacks/fragments/compose.yaml`
**Style**: `deploy.resources.limits`

| Service | CPU Limit | Memory Limit |
|---------|-----------|-------------|
| web | `cpus: "0.25"` | `memory: 256M` |
| api | `cpus: "0.25"` | `memory: 256M` |

### 7. Mealie — CPU Limit Added to Existing Block

**File**: `/etc/komodo/stacks/mealie/compose.yaml`
**Style**: `deploy.resources.limits` (already had `memory: 1000M`)

Added `cpus: "0.5"` alongside existing memory limit.

### 8. Trailhead — CPU Limits Added to Existing Blocks

**File**: `/etc/komodo/stacks/trailhead/compose.yaml`
**Style**: `deploy.resources.limits` (already had memory limits)

| Service | CPU Limit Added | Existing Memory Limit |
|---------|-----------------|----------------------|
| generator | `cpus: "0.5"` | memory: 512M |
| web | `cpus: "0.25"` | memory: 128M |

### 9. SFTPGo — CPU + Memory Limits

**File**: `/etc/komodo/stacks/sftp/compose.yaml`
**Style**: `deploy.resources.limits`

| Service | CPU Limit | Memory Limit |
|---------|-----------|-------------|
| sftpgo | `cpus: "0.25"` | `memory: 256M` |

### No Changes Required

These stacks already had appropriate resource limits:
- **prometheus** — cpus: 1.0, mem_limit: 2g
- **grafana** — cpus: 0.5, mem_limit: 1g
- **birdnet-go** — cpus: 2.0, mem_limit: 2g
- **frigate** — cpus: 2.0, mem_limit: 4g
- **immich** — cpus: 2.0, memory: 4g
- **paperless** — cpus: 2.0
- **bentopdf** — cpus: 2.0, mem_limit: 2g

## CPU Budget Summary

All limits are ceilings (not reservations). Total oversubscription is expected and safe — containers only use what they need.

| Category | Total cpus |
|----------|-----------|
| **Existing limits** (unchanged) | 11.5 |
| **New limits** (this change) | 10.0 |
| **Grand total** | 21.5 |
| **Available cores** (CT 128) | 8 |

## Results

### Post-Change CPU Snapshot

```
NAME                      CPU %     MEM USAGE / LIMIT
cadvisor                  0.00%     82.89MiB / 2GiB      ← was 3-68%, 1.34 GiB
authentik-server          0.38%     407.4MiB / 1GiB       ← bounded at 1.0 CPU
authentik-worker          0.12%     510MiB / 1GiB         ← bounded at 0.5 CPU
komodo-postgres-1         0.22%     1.008GiB / 32GiB      ← bounded at 0.5 CPU
karakeep-web-1            0.91%     322.3MiB / 32GiB      ← bounded at 0.5 CPU
sftpgo-server             0.04%     37.41MiB / 256MiB     ← bounded at 0.25 CPU + 256M
fragments-web             0.00%     3.418MiB / 256MiB     ← bounded at 0.25 CPU + 256M
mealie                    0.08%     284.6MiB / 1000MiB    ← bounded at 0.5 CPU
```

### Key Metrics Comparison

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **Host load average** | ~2.0 | ~1.14 | **-43%** |
| **cAdvisor CPU** | 3-68% (variable) | 0.00% | **~99% reduction** |
| **cAdvisor memory** | 1.344 GiB | 82.89 MiB | **-94% (1.26 GiB freed)** |
| **Containers with CPU limits** | 7 / 46 | 26 / 46 | +19 containers bounded |
| **Unlimited containers** | 39 | 20 | -19 |

### What's Still Unlimited

These containers still have no CPU limits (low priority — minimal CPU usage):
- komodo-web-1, komodo-meilisearch-1, komodo-chrome-1 (orphan containers from karakeep stack sharing komodo project name)
- jellystat, jellystat-db
- paperless-ai, paperless-tika, paperless-gotenberg, paperless-broker
- immich_redis
- file-server
- reyday
- bentopdf (already limited via shorthand)

## Known Issues

### Karakeep Meilisearch EAGAIN Error

During the restart, `karakeep-meilisearch-1` entered a crash loop with:
```
error=Internal error: Resource temporarily unavailable (os error 11)
```

This is EAGAIN — a thread/process creation failure. The error persisted even after removing all resource limits from the container, confirming it was **not caused by our changes**. The container eventually self-recovered after several restart cycles.

**If this recurs**: The error is likely related to cgroup thread limits in the LXC → Docker nesting chain, or a meilisearch startup race condition. Workaround is to wait for auto-recovery (restart policy handles it).

## Verification Checklist

After applying these changes, verify:

1. **All containers running**: `docker ps` — check no unexpected restarts
2. **cAdvisor metrics flowing**: Check Prometheus targets at `192.168.0.179:9092/targets` — all should show UP
3. **Authentik SSO working**: Test login at `home.1701.me`
4. **Host load average**: Should be below 1.5 (was ~2.0 before)
5. **Docker stats**: `docker stats --no-stream` — verify limits show in MEM USAGE / LIMIT column

## Future Improvements

- **Reduce cAdvisor mem_limit**: Memory dropped from 1.34 GiB to ~83 MiB after tuning. Can safely reduce `mem_limit` from 2G to 512M after confirming stability over 48 hours.
- **Add limits to remaining 20 containers**: Low priority since they're minimal CPU users, but would complete the coverage.
- **Prometheus scrape interval alignment**: Currently scraping cAdvisor every 30s with housekeeping at 30s. If scrape interval is reduced, housekeeping should match.

## Files Modified

All on CT 128 (192.168.0.179):

| File | Changes |
|------|---------|
| `/etc/komodo/stacks/prometheus/compose.yaml` | cAdvisor command flags + cpus/mem_limit; alertmanager + blackbox-exporter limits |
| `/etc/komodo/stacks/authentik/compose.yaml` | cpus on all 4 services (server, worker, postgresql, redis) |
| `/opt/komodo/compose.yaml` | deploy.resources.limits.cpus on core, periphery, postgres, ferretdb |
| `/etc/komodo/stacks/karakeep/compose.yaml` | deploy.resources.limits.cpus on web, chrome |
| `/etc/komodo/stacks/tandoor/compose.yaml` | deploy.resources.limits.cpus on web_recipes, db_recipes |
| `/etc/komodo/stacks/fragments/compose.yaml` | deploy.resources.limits (cpus + memory) on web, api |
| `/etc/komodo/stacks/mealie/compose.yaml` | Added cpus to existing deploy.resources.limits block |
| `/etc/komodo/stacks/trailhead/compose.yaml` | Added cpus to existing deploy.resources.limits blocks (generator, web) |
| `/etc/komodo/stacks/sftp/compose.yaml` | deploy.resources.limits (cpus + memory) on sftpgo |
