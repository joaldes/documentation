# System Inventory — Shipyard
*Last updated: 2026-05-05 04:00 UTC*

**Shipyard** (192.168.0.151) | CPU: 5.91, 3.47, 3.28 | RAM: 36/62 GB | Uptime: 92 days

**47 services** — 23 LXC containers, 24 Docker stacks, 3 VMs, 11 storage pools

## All Services (47)
| Name | Type | IP | Port | URL | Status |
|------------------|--------|----------------|-------|------------------------------|---------|
| adguard | lxc | 192.168.0.11 | 80 | http://192.168.0.11:80 | running |
| authentik | docker | 192.168.0.179 | 9000 | http://192.168.0.179:9000 | running |
| bazarr | lxc | 192.168.0.48 | 6767 | http://192.168.0.48:6767 | running |
| bento-pdf | docker | 192.168.0.179 | 8095 | http://192.168.0.179:8095 | running |
| birdnet-go | docker | 192.168.0.179 | 8060 | http://192.168.0.179:8060 | running |
| claudeai | lxc | 192.168.0.180 | 3000 | http://192.168.0.180:3000 | running |
| emby | lxc | 192.168.0.13 | 8096 | http://192.168.0.13:8096 | running |
| fragments | docker | 192.168.0.179 | 8075 | http://192.168.0.179:8075 | running |
| frigate | docker | 192.168.0.179 | 5000 | http://192.168.0.179:5000 | running |
| gis-stack | lxc | 192.168.0.229 | - | - | running |
| grafana | docker | 192.168.0.179 | 3001 | http://192.168.0.179:3001 | running |
| homelable | lxc | 192.168.0.218 | - | - | running |
| homepage | lxc | 192.168.0.70 | 3000 | http://192.168.0.70:3000 | running |
| immich | docker | 192.168.0.179 | 2283 | http://192.168.0.179:2283 | running |
| jellyseerr | lxc | 192.168.0.43 | 5055 | http://192.168.0.43:5055 | running |
| jellystat | docker | 192.168.0.179 | 3000 | http://192.168.0.179:3000 | running |
| karakeep | docker | 192.168.0.179 | 8055 | http://192.168.0.179:8055 | running |
| komodo | lxc | 192.168.0.179 | 9120 | http://192.168.0.179:9120 | running |
| komodo | docker | 192.168.0.179 | 9120 | http://192.168.0.179:9120 | running |
| lubelogger | docker | 192.168.0.179 | 8071 | http://192.168.0.179:8071 | running |
| manyfold | docker | 192.168.0.179 | 3214 | http://192.168.0.179:3214 | running |
| mealie | docker | 192.168.0.179 | 9925 | http://192.168.0.179:9925 | running |
| nginxproxymanager | lxc | 192.168.0.30 | 81 | http://192.168.0.30:81 | running |
| ollama | lxc | 192.168.0.130 | - | - | running |
| overpass | docker | 192.168.0.179 | 12345 | http://192.168.0.179:12345 | running |
| paperless | docker | 192.168.0.179 | 8010 | http://192.168.0.179:8010 | running |
| paperless-ai | docker | 192.168.0.179 | 3030 | http://192.168.0.179:3030 | running |
| photon | docker | 192.168.0.179 | 2322 | http://192.168.0.179:2322 | running |
| prometheus | docker | 192.168.0.179 | 9092 | http://192.168.0.179:9092 | running |
| pulse | lxc | 192.168.0.175 | 7655 | http://192.168.0.175:7655 | running |
| radarr | lxc | 192.168.0.42 | 7878 | http://192.168.0.42:7878 | running |
| reyday | docker | 192.168.0.179 | 8105 | http://192.168.0.179:8105 | running |
| samba | lxc | 192.168.0.176 | - | - | running |
| sander | docker | 192.168.0.179 | 8100 | http://192.168.0.179:8100 | running |
| scanopy | lxc | 192.168.0.219 | - | - | running |
| scanopy-daemon | docker | 192.168.0.179 | - | - | running |
| sftp | docker | 192.168.0.179 | 8070 | http://192.168.0.179:8070 | running |
| sonarr | lxc | 192.168.0.24 | 8989 | http://192.168.0.24:8989 | running |
| syncthing | lxc | 192.168.0.45 | 8384 | http://192.168.0.45:8384 | running |
| tandoor | docker | 192.168.0.179 | 8090 | http://192.168.0.179:8090 | running |
| tracearr | lxc | 192.168.0.211 | 3000 | http://192.168.0.211:3000 | running |
| trailhead | docker | 192.168.0.179 | 8076 | http://192.168.0.179:8076 | running |
| unmanic | lxc | 192.168.0.207 | 8888 | http://192.168.0.207:8888 | running |
| uptimekuma | lxc | 192.168.0.44 | 3001 | http://192.168.0.44:3001 | running |
| urbackup | lxc | 192.168.0.209 | 55414 | http://192.168.0.209:55414 | running |
| wikijs | lxc | 192.168.0.57 | 3000 | http://192.168.0.57:3000 | running |
| zwave-js-ui | lxc | 192.168.0.153 | 8091 | http://192.168.0.153:8091 | running |

## LXC Containers (23)
| CT | Name | IP | Port | URL | Status |
|-----|------------------|----------------|-------|------------------------------|---------|
| 101 | adguard | 192.168.0.11 | 80 | http://192.168.0.11:80 | running |
| 102 | emby | 192.168.0.13 | 8096 | http://192.168.0.13:8096 | running |
| 103 | syncthing | 192.168.0.45 | 8384 | http://192.168.0.45:8384 | running |
| 104 | samba | 192.168.0.176 | - | - | running |
| 105 | unmanic | 192.168.0.207 | 8888 | http://192.168.0.207:8888 | running |
| 107 | radarr | 192.168.0.42 | 7878 | http://192.168.0.42:7878 | running |
| 108 | zwave-js-ui | 192.168.0.153 | 8091 | http://192.168.0.153:8091 | running |
| 109 | homelable | 192.168.0.218 | - | - | running |
| 110 | sonarr | 192.168.0.24 | 8989 | http://192.168.0.24:8989 | running |
| 111 | urbackup | 192.168.0.209 | 55414 | http://192.168.0.209:55414 | running |
| 112 | nginxproxymanager | 192.168.0.30 | 81 | http://192.168.0.30:81 | running |
| 113 | jellyseerr | 192.168.0.43 | 5055 | http://192.168.0.43:5055 | running |
| 114 | uptimekuma | 192.168.0.44 | 3001 | http://192.168.0.44:3001 | running |
| 115 | bazarr | 192.168.0.48 | 6767 | http://192.168.0.48:6767 | running |
| 116 | tracearr | 192.168.0.211 | 3000 | http://192.168.0.211:3000 | running |
| 117 | wikijs | 192.168.0.57 | 3000 | http://192.168.0.57:3000 | running |
| 118 | homepage | 192.168.0.70 | 3000 | http://192.168.0.70:3000 | running |
| 120 | pulse | 192.168.0.175 | 7655 | http://192.168.0.175:7655 | running |
| 121 | scanopy | 192.168.0.219 | - | - | running |
| 124 | claudeai | 192.168.0.180 | 3000 | http://192.168.0.180:3000 | running |
| 128 | komodo | 192.168.0.179 | 9120 | http://192.168.0.179:9120 | running |
| 130 | ollama | 192.168.0.130 | - | - | running |
| 131 | gis-stack | 192.168.0.229 | - | - | running |

## Docker Stacks (24) — 192.168.0.179
| Stack | Port | Containers | Healthy | Status | URL |
|---------------|------|------------|---------|---------|--------------------------------|
| authentik | 9000 | 4/4 | 4 | running | http://192.168.0.179:9000 |
| bento-pdf | 8095 | 1/1 | 0 | running | http://192.168.0.179:8095 |
| birdnet-go | 8060 | 1/1 | 1 | running | http://192.168.0.179:8060 |
| fragments | 8075 | 2/2 | 0 | running | http://192.168.0.179:8075 |
| frigate | 5000 | 1/1 | 1 | running | http://192.168.0.179:5000 |
| grafana | 3001 | 1/1 | 1 | running | http://192.168.0.179:3001 |
| immich | 2283 | 5/5 | 5 | running | http://192.168.0.179:2283 |
| jellystat | 3000 | 2/2 | 2 | running | http://192.168.0.179:3000 |
| karakeep | 8055 | 3/3 | 1 | running | http://192.168.0.179:8055 |
| komodo | 9120 | 7/7 | 2 | running | http://192.168.0.179:9120 |
| lubelogger | 8071 | 1/1 | 0 | running | http://192.168.0.179:8071 |
| manyfold | 3214 | 1/1 | 1 | running | http://192.168.0.179:3214 |
| mealie | 9925 | 1/1 | 1 | running | http://192.168.0.179:9925 |
| overpass | 12345 | 2/2 | 0 | running | http://192.168.0.179:12345 |
| paperless | 8010 | 5/5 | 3 | running | http://192.168.0.179:8010 |
| paperless-ai | 3030 | 1/1 | 1 | running | http://192.168.0.179:3030 |
| photon | 2322 | 1/1 | 1 | running | http://192.168.0.179:2322 |
| prometheus | 9092 | 5/5 | 2 | running | http://192.168.0.179:9092 |
| reyday | 8105 | 1/1 | 0 | running | http://192.168.0.179:8105 |
| sander | 8100 | 1/1 | 0 | running | http://192.168.0.179:8100 |
| scanopy-daemon | - | 1/1 | 1 | running | - |
| sftp | 8070 | 1/1 | 0 | running | http://192.168.0.179:8070 |
| tandoor | 8090 | 2/2 | 2 | running | http://192.168.0.179:8090 |
| trailhead | 8076 | 2/2 | 1 | running | http://192.168.0.179:8076 |

## VMs (3)
| VMID | Name | Status |
|------|----------------|---------|
| 100 | homeassistant | running |
| 106 | WindowsXP | stopped |
| 119 | WindowsTiny10 | stopped |

## Storage (11)
| ID | Type | Used/Total GB | % Used |
|-----------------|---------|---------------|--------|
| backups | dir | 5929/10158 | 58% |
| birdnet | dir | 0/228 | 0% |
| container-backups | dir | 807/1006 | 80% |
| docker-data | dir | 238/2014 | 11% |
| littlestorage | lvmthin | 133/1830 | 7% |
| local | dir | 51/93 | 54% |
| local-lvm | lvmthin | 281/348 | 80% |
| smb-documents | dir | 31/921 | 3% |
| smb-frigate | dir | 591/1006 | 58% |
| smb-hometheater | dir | 16475/29679 | 55% |
| smb-pictures | dir | 2340/10158 | 23% |
