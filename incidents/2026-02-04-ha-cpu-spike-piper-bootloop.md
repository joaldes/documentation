# Home Assistant CPU Spike - Piper Add-on Boot Loop - 2026-02-04

## Summary
At approximately 1700 on February 3, 2026, CPU usage on the Home Assistant VM (VM 100) increased from ~2.5% to ~10% and remained elevated. The root cause was the **Piper text-to-speech add-on** entering an error state and boot looping. Each crash/restart cycle consumed CPU, and because add-ons auto-restart, the issue persisted through a full HA reboot. Disabling the Piper add-on restored CPU to normal levels.

---

## What Happened

### Timeline
- **~1700 Feb 3** - CPU usage on VM 100 jumped from ~2.5% to ~7.2%, accompanied by a disk I/O spike (writes jumped from ~250KB/s to 1.3MB/s)
- **~1730 Feb 3** - CPU settled at ~10% and remained there
- **Feb 3-4** - CPU stayed consistently at ~10% (confirmed via Proxmox RRD data spanning 70+ data points)
- **~1327 Feb 4** - User rebooted Home Assistant; CPU returned to ~10% immediately (no improvement)
- **~1400 Feb 4** - Investigation began via Proxmox API, QEMU guest agent, and process analysis
- **~1400 Feb 4** - rtl_433 add-ons disabled as initial suspect; no CPU change
- **~1415 Feb 4** - User checked HA web UI, discovered Piper add-on in error state and boot looping
- **~1415 Feb 4** - User disabled Piper add-on; CPU returned to ~2.5% baseline

### Root Cause
The **Piper text-to-speech add-on** (slug: `core_piper`, version 2.2.1) entered an error state and began boot looping. Each restart cycle involved:
1. Docker container spin-up
2. Piper model loading into memory
3. Crash/error
4. Supervisor detecting the failure
5. Auto-restart triggering immediately

This continuous cycle consumed ~7-8% CPU on the 4-core VM. Because the HA Supervisor's watchdog/auto-restart kicks in after any reboot, the issue persisted through a full HA restart.

---

## Technical Details

### VM 100 Configuration
- **Name**: homeassistant
- **Type**: QEMU VM (HAOS)
- **IP**: 192.168.0.154
- **CPUs**: 4 cores
- **Memory**: 4GB (3.8GB usable)
- **Disk**: 100GB on littlestorage LVM thin pool
- **HA Version**: 2026.1.3

### CPU Data from Proxmox RRD (30-minute intervals)

| Timestamp (UTC) | CPU Ratio | CPU % | Notes |
|-----------------|-----------|-------|-------|
| Feb 3 ~22:00 | 0.025 | 2.5% | Normal baseline |
| Feb 3 ~23:00 | 0.026 | 2.6% | Normal baseline |
| Feb 4 00:30 | 0.072 | 7.2% | **Spike begins** - disk I/O burst |
| Feb 4 01:00 | 0.096 | 9.6% | Elevated - sustained |
| Feb 4 02:00 | 0.096 | 9.6% | Elevated - sustained |
| Feb 4 04:00 | 0.096 | 9.6% | Elevated - sustained |
| Feb 4 06:00 | 0.100 | 10.0% | Elevated - sustained |
| Feb 4 08:00 | 0.100 | 10.0% | Elevated - sustained |
| Feb 4 10:00 | 0.098 | 9.8% | Elevated - sustained |
| Feb 4 12:00 | 0.100 | 10.0% | Elevated - sustained |
| Feb 4 14:00 | 0.098 | 9.8% | Elevated - just before fix |

The disk I/O spike at the onset (writes jumped from ~250KB/s to 1.3MB/s) corresponds to the initial Piper crash and the beginning of the restart loop, including Docker container image layer operations.

### Process Analysis (captured during investigation)
Top CPU consumers at time of investigation:

| Process | CPU % | TIME+ | Memory | Notes |
|---------|-------|-------|--------|-------|
| python3 -m homeassistant | 2.4-9.2% | 0:44 | 789MB (20%) | HA Core (variable, recently restarted) |
| rtl_433 | 1.3% | 53:54 | 12MB | RF receiver (ruled out) |
| node-red | 0.6% | 34:36 | 230MB | Automation engine (normal) |
| bluetoothd | 0.3% | 20:34 | 5.5MB | Bluetooth (normal) |
| dockerd | 0.3% | 18:47 | 68MB | Docker daemon (elevated from restarts) |

Note: The Piper add-on's CPU usage was distributed across Docker operations (container create/destroy cycles) and the HA Supervisor monitoring, making it difficult to attribute to a single process in `top`.

### Items Ruled Out During Investigation
1. **rtl_433 add-ons** - Disabled both `9b13b3f4_rtl433` and `9b13b3f4_rtl433mqttautodiscovery`; no CPU change
2. **Recorder database** - 1.6GB with healthy 6.7MB WAL file; 60-day retention is standard
3. **Node-RED** - Logs showed normal message flow and memory usage (~225MB)
4. **Template sensors** - Reviewed all templates in `/config/templates/`; all reactive, no polling loops
5. **History stats sensors** - Only 5 configured, all with daily reset intervals
6. **Command line sensors** - Only 2, both with 3600s scan intervals
7. **Disk space** - Main data partition at 40% (37.3GB of 97.7GB)
8. **Prometheus historical data** - Only ~3 hours retention available; not useful for this investigation

### Add-ons Status at Time of Investigation
Running add-ons on VM 100:

| Add-on | State | Notes |
|--------|-------|-------|
| ESPHome Device Builder | started | Normal |
| Google Drive Backup | started | Normal |
| MQTT Explorer | started | Normal |
| Mosquitto broker | started | Normal |
| Node-RED | started | Normal |
| **Piper** | **started (error/boot looping)** | **ROOT CAUSE** |
| Samba share | started | Normal |
| Studio Code Server | started | Normal |
| Zigbee2MQTT | started | Normal |
| Advanced SSH & Web Terminal | started | Normal |
| Terminal & SSH | started | Normal |
| Ring-MQTT | started | Normal |
| rtl_433 | started | Ruled out |
| rtl_433 MQTT Auto Discovery | started | Ruled out |
| Matter Server | started | Normal |
| Home Assistant Time Machine | started | Normal |
| SQLite Web | error | Pre-existing error, not related |
| openWakeWord | error | Pre-existing error, not related |

---

## Resolution

### Immediate Fix
User disabled the Piper add-on via the HA web UI:
**Settings → Add-ons → Piper → Stop → Disable watchdog/auto-start**

CPU immediately returned to ~2.5% baseline.

### To Restore Piper (When Needed)
1. Check Piper add-on logs: **Settings → Add-ons → Piper → Log**
2. Look for crash reason (corrupted model cache, config issue, resource exhaustion)
3. Try: **Settings → Add-ons → Piper → Rebuild** (reinstalls the container)
4. If rebuild fails, uninstall and reinstall the add-on
5. Monitor CPU after re-enabling to confirm the issue is resolved

---

## Investigation Access Methods Used

### Primary: Proxmox QEMU Guest Agent
```bash
# Process listing and system commands
SSHPASS='claudepassword' sshpass -e ssh claude@192.168.0.151 \
  "sudo qm guest exec 100 -- <command>"

# HA CLI commands
sudo qm guest exec 100 -- ha core stats
sudo qm guest exec 100 -- ha addons
sudo qm guest exec 100 -- ha core logs --lines 200

# Docker exec for filesystem access (files inside HA container)
sudo qm guest exec 100 -- docker exec homeassistant cat /config/configuration.yaml
sudo qm guest exec 100 -- docker exec homeassistant ls /config/custom_components/
```

### Secondary: Proxmox API
```bash
# VM status with CPU metrics
curl -s -k -H "Authorization: PVEAPIToken=claude@pam!api=<token>" \
  "https://192.168.0.151:8006/api2/json/nodes/Shipyard/qemu/100/status/current"

# Historical RRD data (30-minute intervals, ~24 hours)
curl -s -k -H "Authorization: PVEAPIToken=claude@pam!api=<token>" \
  "https://192.168.0.151:8006/api2/json/nodes/Shipyard/qemu/100/rrddata?timeframe=day"
```

### Limitations Encountered
- **Direct SSH to HAOS**: Not available (HAOS restrictions, password auth rejected)
- **QEMU guest agent**: Some filesystem commands return null (ls, cat on certain paths); works for basic commands and docker exec
- **Prometheus**: Only ~3 hours of data retention; no historical data from yesterday
- **HA logs**: Lost after reboot; only post-reboot logs available

---

## Lessons Learned

### 1. Boot-Looping Add-ons Survive Reboots
Unlike a runaway process that would be killed by a reboot, add-ons with auto-restart enabled will immediately begin boot looping again after any reboot. The Supervisor's watchdog restarts them as part of the normal boot sequence.

### 2. Check the HA Web UI First
The fastest path to diagnosis was **Settings → Add-ons** in the HA web UI, which clearly showed Piper in an error state. Programmatic investigation through the QEMU guest agent was slower and couldn't easily surface add-on health status.

### 3. Add-on CPU Doesn't Show in `ha core stats`
The `ha core stats` command only reports HA Core's container CPU usage. Add-on CPU usage is in separate Docker containers and must be checked via `ha addons stats <slug>` or `top`/`ps` at the VM level.

### 4. Proxmox RRD Data is Valuable
The RRD endpoint (`/rrddata?timeframe=day`) provided 30-minute-interval CPU history that confirmed the exact time of the spike, even though Prometheus lacked historical data. This should be the first data source checked for VM-level CPU investigations.

### 5. Disk I/O Spikes Correlate with Docker Restart Loops
The initial disk I/O burst (1.3MB/s writes vs 250KB/s baseline) was caused by Docker repeatedly creating and destroying container layers during the boot loop. This pattern can serve as a diagnostic indicator for similar issues in the future.

---

## Recommendations

### Immediate
- [x] Piper add-on disabled; CPU restored to baseline
- [ ] Check Piper logs to understand the crash reason
- [ ] Consider reinstalling Piper if TTS is needed

### Short-term
- [ ] Review all add-ons with `state: error` (SQLite Web, openWakeWord) and either fix or remove them
- [ ] Disable watchdog/auto-start on non-critical add-ons to prevent future boot loop CPU drain

### Long-term
- [ ] Set up Proxmox-level alerting for VM CPU thresholds (e.g., alert if VM 100 CPU > 5% sustained for 1 hour)
- [ ] Extend Prometheus retention beyond 3 hours to retain useful historical data for investigations
- [ ] Document the `ha addons stats <slug>` command for per-add-on CPU monitoring

---

## Related Systems
- **VM 100**: Home Assistant OS (QEMU VM)
- **Proxmox Host**: Shipyard (192.168.0.151)
- **Affected Add-on**: Piper TTS (core_piper, v2.2.1)
- **Also in Error State**: SQLite Web (a0d7b954_sqlite-web), openWakeWord (core_openwakeword)

---

*Incident Duration: ~21 hours (1700 Feb 3 to ~1415 Feb 4)*
*Time to Diagnose: ~15 minutes (from start of investigation to root cause)*
*Time to Resolve: Immediate (disable add-on)*
