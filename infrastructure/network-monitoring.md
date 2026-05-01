# Network Performance Monitoring

**Last Updated**: 2026-05-01
**Related Systems**: Container 128 (Komodo), Prometheus stack, Grafana

## Summary

Added live network performance monitoring to the existing Prometheus stack on Komodo (CT 128, 192.168.0.179): 30-minute internet speed tests via `speedtest-exporter` and continuous LAN/WAN ICMP latency probes via `blackbox-exporter`. New Grafana dashboard at `http://192.168.0.179:3001/d/network-performance/network-performance`.

## Problem / Goal

The Prometheus stack tracked host/container metrics but had no visibility into network performance — internet up/down speed, LAN latency, jitter, or packet loss. Goal: capture both internet-side and internal-LAN performance for trend analysis and incident detection. Wired-only vantage from CT 128; WiFi vantage (Pi at 192.168.0.136) deferred.

## Solution

The `speedtest-exporter` service was already declared in `compose.yaml` but had never been deployed; ICMP probes were configured for 4 targets but missing internal hosts. Reconciled and extended:

1. Deployed `speedtest-exporter` (image `miguelndecarvalho/speedtest-exporter:latest`, port 9798).
2. Added `preferred_ip_protocol: ip4` to the `icmp` blackbox module (avoids IPv6 fallback weirdness).
3. Extended ICMP target list to include Proxmox host, Samba/NAS, and Claude AI CT.
4. Bumped speedtest scrape_timeout from 120s → 180s.
5. Built custom Grafana dashboard with internet speed/latency stats and per-target LAN RTT/loss panels.

## Implementation Details

### Files Modified (on CT 128, 192.168.0.179)

- `/etc/komodo/stacks/prometheus/blackbox.yml` — added `preferred_ip_protocol: ip4` to `icmp` module
- `/etc/komodo/stacks/prometheus/prometheus.yaml` — added 3 ICMP targets, bumped speedtest scrape_timeout to 180s
- `/etc/komodo/stacks/prometheus/dashboards/network-performance.json` — new dashboard JSON (also imported into Grafana)
- `/mnt/docker/trailhead/trailhead.yaml` — added Network Monitoring tile under Dashboards category

In-place backups created with `<file>.backup-YYYYMMDD-HHMMSS` per stack convention.

### Probe Targets

| Target | Type | Purpose |
|---|---|---|
| 1.1.1.1 | ICMP | Cloudflare DNS — upstream/ISP visibility |
| 8.8.8.8 | ICMP | Google DNS — upstream/ISP visibility |
| 192.168.0.1 | ICMP | Gateway — first-hop sanity |
| 192.168.0.11 | ICMP | AdGuard / DNS |
| 192.168.0.151 | ICMP | Proxmox host |
| 192.168.0.176 | ICMP | Samba / NAS |
| 192.168.0.180 | ICMP | Claude AI CT |
| speedtest-exporter:9798 | speedtest | Internet up/down/ping/jitter |

**Excluded:** 192.168.0.154 (HA VM) does not respond to ICMP — would create permanent red panel. 192.168.0.179 (Komodo itself) excluded as meaningless self-ping.

### Deployment Commands

```bash
# Deploy speedtest container
ssh claude@192.168.0.151 'sudo pct exec 128 -- bash -c "cd /etc/komodo/stacks/prometheus && docker compose up -d speedtest-exporter"'

# Apply blackbox config change
ssh claude@192.168.0.151 'sudo pct exec 128 -- docker restart blackbox-exporter'

# Reload Prometheus config
ssh claude@192.168.0.151 'sudo pct exec 128 -- curl -s -X POST http://localhost:9092/-/reload'
```

## Verification

- All 7 ICMP targets return `probe_success 1` (verified)
- Manual speedtest probe completed: 824 Mbps down / 41 Mbps up / 8.8 ms ping / 0.7 ms jitter
- Prometheus targets page (`http://192.168.0.179:9092/targets`) shows `blackbox-icmp` and `speedtest` jobs as `UP`
- Grafana dashboard at `http://192.168.0.179:3001/d/network-performance/network-performance` populates LAN panels within 1 min, internet speed within 30 min
- Trailhead tile "Network Monitoring" appears under Dashboards

## Operational Notes

- **Speedtest cadence:** every 30 min (~30–100 GB/month bandwidth). Configured in `prometheus.yaml` `speedtest` job `scrape_interval: 30m`.
- **Retention:** Prometheus is 90 days, capped at 8 GB. New ICMP series at 15s × 7 targets is low cardinality but worth re-checking after a week.
- **Alerting:** intentionally not configured yet — observe baseline for 1–2 weeks, then add rules for sustained packet loss and speedtest failures.

## Known Issues

- `blackbox-http-external` probes (Google, Cloudflare, Xfinity HTTPS) have been failing at connect (probe_success=0, status_code=0) since before this change. DNS resolves but TCP connect to 443 returns nothing. Likely Docker outbound HTTPS issue from the `monitoring` network. Not blocking this work but worth investigating separately.

## Future Work

- WiFi vantage point: install `blackbox_exporter` on the gazebo Pi (192.168.0.136) probing the same target list. Wired-vs-WiFi delta is the headline insight for end-user experience.
- Alerting rules in `/etc/komodo/stacks/prometheus/rules/` once baseline data exists.
- TCP probe to AdGuard DNS:53 for service-level signal beyond ICMP.
