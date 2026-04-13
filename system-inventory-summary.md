# System Inventory — Shipyard
*Last updated: 2026-03-28 19:00 UTC*

**Shipyard** (192.168.0.151) | CPU: 2.46, 2.08, 2.39 | RAM: 35/62 GB | Uptime: 55 days

**22 services** — 22 LXC containers, 0 Docker stacks, 3 VMs, 11 storage pools

## All Services (22)
| Name | Type | IP | Port | URL | Status |
|------------------|--------|----------------|-------|------------------------------|---------|
| adguard | lxc | 192.168.0.11 | 80 | http://192.168.0.11:80 | running |
| bazarr | lxc | 192.168.0.48 | 6767 | http://192.168.0.48:6767 | running |
| claudeai | lxc | 192.168.0.180 | 3000 | http://192.168.0.180:3000 | running |
| emby | lxc | 192.168.0.13 | 8096 | http://192.168.0.13:8096 | running |
| homelable | lxc | 192.168.0.218 | - | - | running |
| homepage | lxc | 192.168.0.70 | 3000 | http://192.168.0.70:3000 | running |
| jellyseerr | lxc | 192.168.0.43 | 5055 | http://192.168.0.43:5055 | running |
| komodo | lxc | 192.168.0.179 | 9120 | http://192.168.0.179:9120 | running |
| nginxproxymanager | lxc | 192.168.0.30 | 81 | http://192.168.0.30:81 | running |
| ollama | lxc | 192.168.0.130 | - | - | running |
| pulse | lxc | 192.168.0.175 | 7655 | http://192.168.0.175:7655 | running |
| radarr | lxc | 192.168.0.42 | 7878 | http://192.168.0.42:7878 | running |
| samba | lxc | 192.168.0.176 | - | - | running |
| scanopy | lxc | 192.168.0.219 | - | - | running |
| sonarr | lxc | 192.168.0.24 | 8989 | http://192.168.0.24:8989 | running |
| syncthing | lxc | 192.168.0.45 | 8384 | http://192.168.0.45:8384 | running |
| tracearr | lxc | 192.168.0.211 | 3000 | http://192.168.0.211:3000 | running |
| unmanic | lxc | 192.168.0.207 | 8888 | http://192.168.0.207:8888 | running |
| uptimekuma | lxc | 192.168.0.44 | 3001 | http://192.168.0.44:3001 | running |
| urbackup | lxc | 192.168.0.209 | 55414 | http://192.168.0.209:55414 | running |
| wikijs | lxc | 192.168.0.57 | 3000 | http://192.168.0.57:3000 | running |
| zwave-js-ui | lxc | 192.168.0.153 | 8091 | http://192.168.0.153:8091 | running |

## LXC Containers (22)
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

## Docker Stacks (0) — 192.168.0.179
| Stack | Port | Containers | Healthy | Status | URL |
|---------------|------|------------|---------|---------|--------------------------------|

## VMs (3)
| VMID | Name | Status |
|------|----------------|---------|
| 100 | homeassistant | running |
| 106 | WindowsXP | stopped |
| 119 | WindowsTiny10 | stopped |

## Storage (11)
| ID | Type | Used/Total GB | % Used |
|-----------------|---------|---------------|--------|
| backups | dir | 5483/10158 | 53% |
| birdnet | dir | 0/228 | 0% |
| container-backups | dir | 708/1006 | 70% |
| docker-data | dir | 68/2014 | 3% |
| littlestorage | lvmthin | 115/1830 | 6% |
| local | dir | 48/93 | 51% |
| local-lvm | lvmthin | 264/348 | 75% |
| smb-documents | dir | 1/921 | 0% |
| smb-frigate | dir | 454/1006 | 45% |
| smb-hometheater | dir | 15974/29679 | 53% |
| smb-pictures | dir | 2337/10158 | 23% |
