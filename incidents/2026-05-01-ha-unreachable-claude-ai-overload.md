# HA Unreachable — Triggered by Claude AI CT Overload

**Last Updated**: 2026-05-01
**Related Systems**: Container 124 (Claude AI), VM 100 (Home Assistant), Container 101 (AdGuard / DHCP), Proxmox host
**Duration**: ~55 minutes (HA unreachable 14:17:49 → 15:12:45 MST)
**Severity**: Medium — HA dashboard / API inaccessible, automations continued running internally

## Summary

Two failures occurred in the same window. CT 124 (Claude AI) crashed under runaway load from duplicate Claude sessions, briefly starving the Proxmox host. The host CPU pressure stalled HA VM 100's vCPU long enough that NetworkManager's DHCP renewal timers were skipped; the lease expired and NM never recovered on its own. HA was unreachable from the LAN for ~55 minutes until manual `nmcli connection up` recovered the IP. Both root causes are now mitigated.

## Problem / Goal

User reported "I can't access HA" at ~22:05 UTC. HA's web UI (8123), SSH, and ICMP all unreachable. VM was running per `qm status`. Goal: identify the cause (not just paper over it) and prevent recurrence.

## Solution

Two independent fixes, applied in priority order:

1. **CT 124 (root cause)**: removed `--autologin claudeai` from `console-getty.service` so only `tty1` auto-launches `claude`. The duplicate console session was spawning a second full set of MCP servers (~24 → 41 processes), driving load average to 400+ on a 2-core container.
2. **HA VM 100 (immediate fix)**: user manually ran `nmcli connection up "Supervisor enp0s18"` to re-acquire the DHCP lease. Subsequently extended the AdGuard DHCP lease from 600s → 86400s for resilience.
3. **Monitoring**: added `192.168.0.154` to the Prometheus blackbox-icmp probe list so future drops alert in Grafana within ~30s.

## Implementation Details

### Timeline (UTC)

| Time | Event |
|------|------|
| ~13:30 | CT 101 (AdGuard) `dbus-daemon` ↔ `unattended-upgrades` ↔ `login1` loop begins (still active; not causal but observed) |
| 14:07:49 | HA NM: last successful DHCP renewal (10-min lease) |
| 14:08:07 | HA: LIFX integration timeouts begin — first sign of LAN packet loss |
| 14:12:49 | T1 renewal due — never logged (NM didn't attempt) |
| 14:15:18–14:19:56 | Proxmox: 10+ `vncproxy:124` console attach attempts (user trying to reach hung CT 124) |
| 14:17:49 | HA NM: lease expires, "state changed no lease". Connection enters CONNECTED_SITE, no auto-retry |
| 14:19:15 | HA kernel: `clocksource: Long readout interval, cs_nsec: 1023026762` (~1 sec vCPU stall — proves host starved the VM) |
| 14:20:10 | CT 124 deactivated (clean stop after pve-container watchdog) |
| 14:20:11 | CT 124 restarted; came back at uptime 0 with load avg 257/413/224 |
| 15:12:45 | User runs `nmcli connection up` on HA → new lease acquired in <1s, services back |

### Causal chain

```
CT 124 duplicate Claude sessions (auto-login on console + tty1)
  → 41 processes, load avg 400+ on 2-core container
  → Proxmox host CPU starvation
  → VM 100 vCPU stalls (proven by clocksource warning)
  → NM DHCP renewal timers skipped at T1/T2
  → Lease expires; NM enters "no lease" CONNECTED_SITE state
  → autoconnect-retries doesn't fire (only triggers on activation failure)
  → HA unreachable until manual intervention
```

The two failures were not independent. Same Proxmox host, same 5-minute overload window. An initial diagnosis that called them "causally unrelated" was wrong — the user pushed back on that, and the kernel clocksource warning at 14:19:15 confirmed the link.

### Steps Performed

1. Diagnosed CT 124 crash (duplicate sessions on `console` + `tty1`):
   ```bash
   ssh claude@192.168.0.151 'sudo pct exec 124 -- ps -ft pts/0 -ft pts/1 -ft console -ft tty1'
   # Killed duplicate session on pts/0
   ```

2. Confirmed HA had no IPv4 via console screenshot + guest exec:
   ```bash
   sudo qm monitor 100 <<< "screendump /tmp/ha-console.ppm"
   sudo qm guest exec 100 -- /bin/bash -c "ip a show enp0s18"
   # → only IPv6 link-local, no 192.168.0.154
   ```

3. User manually fixed HA via `nmcli connection up "Supervisor enp0s18"`.

4. User extended AdGuard DHCP lease from 600s → 86400s.

5. Disabled console autologin on CT 124:
   ```bash
   ssh claude@192.168.0.151 'sudo pct exec 124 -- bash -c "
     cp /etc/systemd/system/console-getty.service.d/override.conf \
        /etc/systemd/system/console-getty.service.d/override.conf.backup-$(date +%Y%m%d-%H%M%S)
     cat > /etc/systemd/system/console-getty.service.d/override.conf <<EOF
   [Service]
   ExecStart=
   ExecStart=-/sbin/agetty --noclear --keep-baud - 115200,38400,9600 linux
   EOF
     systemctl daemon-reload && systemctl restart console-getty.service"'
   ```

6. Added HA to blackbox-icmp probes; reloaded Prometheus:
   ```bash
   # added entry to /etc/komodo/stacks/prometheus/prometheus.yaml in blackbox-icmp job:
   #   - targets: ["192.168.0.154"]
   #     labels: {name: "HA VM"}
   ssh claude@192.168.0.151 'sudo pct exec 128 -- curl -s -X POST http://localhost:9092/-/reload'
   ```

### Key Files Modified

- `/etc/systemd/system/console-getty.service.d/override.conf` (CT 124) — removed `--autologin claudeai`
- `/etc/komodo/stacks/prometheus/prometheus.yaml` (CT 128) — added 192.168.0.154 to blackbox-icmp targets
- AdGuard DHCP settings (CT 101, via UI) — lease duration 600 → 86400 (user)

## Verification

- CT 124: `who` shows only `tty1`; process count back to ~25 (was 41); load avg back to single digits (was 400+).
- HA: `ping 192.168.0.154` ✅; `curl http://192.168.0.154:8123/` returns HTTP 200; `nmcli -t -f DHCP4.OPTION device show enp0s18 | grep dhcp_lease_time` shows 86400.
- Prometheus: `probe_success{instance="192.168.0.154"} = 1` on Grafana network-performance dashboard.

## Troubleshooting Lessons

- **Trust the timing.** Two failures on the same host in the same 5-min window are almost never independent. Initial "unrelated" claim wasted investigation cycles.
- **NetworkManager renewal logs are silence-on-success-or-skip.** Absence of log lines does NOT mean "renewal succeeded silently" — it can also mean "renewal timer never fired". Check the kernel clocksource log for VM-stall hints.
- **NM's `CONNECTED_SITE` state is a trap.** When DHCP fails on an active connection, NM doesn't always mark it as failed. `autoconnect-retries` only fires from a failed/disconnected state, not from "active but no IP". A long lease + static reservation is more reliable than tuning NM retries.
- **Check the console screenshot first** for any "VM is running but unreachable" symptom. `qm monitor 100 <<< "screendump /tmp/x.ppm"` is faster than guessing — it instantly distinguishes "OS hung" from "OS up, network broken".
- **`qm guest exec`** is reliable for HA OS even though the QEMU guest agent has been flagged unreliable for ping. Use it for `ip a`, `journalctl`, `nmcli`, `ss`.

## Follow-up

Remaining items, not done in this incident:
- AdGuard CT 101 dbus-daemon ↔ login1 loop. Still active. Not causal here but real misconfiguration.
- Add HA static DHCP reservation in AdGuard (deferred — not done by user yet).
- Persist NM `ipv4.dhcp-timeout=infinity` and `connection.autoconnect-retries=0` defaults on HA via `/etc/NetworkManager/conf.d/` drop-in (deferred — won't help in the CONNECTED_SITE trap, lower priority than expected).

See `/home/claudeai/.claude/plans/i-was-concerned-about-gleaming-iverson.md` for the full diagnostic plan including the false-start hypotheses.
