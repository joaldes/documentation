# VPN with Deep Traffic Logging

**Last Updated**: 2026-05-30
**Related Systems**: CT 133 (vpn), CT 101 (AdGuard)

## Summary
Self-hosted WireGuard VPN on LXC 133 with deep traffic telemetry: DNS query logging via AdGuard, Zeek connection/SSL/JA4 metadata, Suricata IDS, all queryable in a local Grafana/Loki stack on the same LXC. Maximum-detail logging without MITM (no payload decryption).

## Problem / Goal
Self-host a VPN to route personal devices through home and capture rich metadata (where, when, what app) on outbound traffic.

## Solution
- **CT 133 "vpn"** (192.168.0.220, 4 vCPU / 16GB RAM / 32GB rootfs + 500GB log mount)
- WireGuard + wg-easy in Docker for client management
- nftables (inside wg-easy netns): DNS DNAT to AdGuard, DoT REJECT, DoH IP blocklist
- Zeek + zeek-ja4 plugin sniffing wg0 via `nsenter` into wg-easy netns
- Suricata 7.0 IDS on the same interface with ET Open ruleset
- Loki + Grafana + Promtail stack on the same LXC (port 3000)
- ntfy.sh push alerts for Suricata sev:1 events

## Implementation Details

### Architecture
```
[client] --WG--> [wg-easy in Docker, has wg0]
                     |
                     +-- nftables DNS DNAT --> AdGuard CT 101
                     +-- DoT/DoH REJECT
                     |
   Zeek (nsenter -t $wgpid -n) ---> /var/log/zeek/*.log ---> Promtail ---> Loki ---> Grafana
   Suricata (same nsenter) -------> /var/log/suricata/eve.json -+
```

### Key URLs (LAN)
- wg-easy UI: http://192.168.0.220:51821 (login: `password`)
- Grafana: http://192.168.0.220:3000 (admin/password)
- Loki API: http://192.168.0.220:3100

### Public Endpoint
- WAN IP: 76.159.199.214, UDP/51820 (router port-forwarded to 192.168.0.220)

### Key Files
- `/opt/vpn-data/wg-easy/` — wg-easy persistent state (client configs)
- `/opt/vpn-data/scripts/apply-wg-firewall.sh` — installs nftables rules inside wg-easy netns (idempotent, runs on boot via `wg-firewall.service`)
- `/opt/vpn-data/scripts/refresh-doh-blocklist.sh` — weekly DoH IP ipset refresh from dibdot/DoH-IP-blocklists (run by `doh-refresh.timer`, Sun 03:00)
- `/opt/vpn-data/stack/docker-compose.yaml` — Loki/Grafana/Promtail stack
- `/opt/zeek/share/zeek/site/local.zeek` — Zeek config (JSON output, JA4 plugin)
- `/etc/suricata/suricata.yaml` — Suricata config (HOME_NET=10.8.0.0/24, wg0 interface)
- `/opt/vpn-data/state/ntfy_topic` — ntfy.sh topic for alerts

### Systemd Units
- `wg-firewall.service` — applies DNS DNAT + DoT/DoH iptables rules into wg-easy netns
- `doh-refresh.timer` / `.service` — weekly DoH blocklist refresh
- `zeek-vpn.service` — Zeek running inside wg-easy netns
- `suricata-vpn.service` — Suricata running inside wg-easy netns
- `suricata-ntfy.service` — tails eve.json, POSTs sev:1 alerts to ntfy.sh

### AdGuard Changes (CT 101)
Added user_rule: `/.*/$dnstype=HTTPS` — blocks DNS type-65 (HTTPS RR) records to delay ECH rollout and keep SNI logging useful.

## Adding a Client
1. Open http://192.168.0.220:51821, log in (`password`)
2. "New Client" → name (e.g. "Alec iPhone") → scan QR with WireGuard app
3. Client gets auto-assigned 10.8.0.x with AdGuard as DNS and PersistentKeepalive=25

## Verification
- WireGuard up: `docker exec wg-easy wg show`
- DNS forced through AdGuard: any client query — check AdGuard log
- HTTPS records blocked: `dig @192.168.0.11 cloudflare.com HTTPS +short` should return empty
- Zeek emitting: `ls /var/log/zeek/` should show conn.log, ssl.log, dns.log, ja4.log etc as traffic flows
- Suricata: `tail /var/log/suricata/eve.json`
- Grafana dashboard: http://192.168.0.220:3000 → "VPN Traffic"
- ntfy alerts: subscribe to topic in `/opt/vpn-data/state/ntfy_topic` on the ntfy mobile app

## Troubleshooting

| Symptom | Check |
|---|---|
| Can't connect from phone | Verify router port-forward UDP/51820 to .220. Check `docker logs wg-easy`. |
| Connected but no internet | `docker exec wg-easy iptables -t nat -L POSTROUTING -v` should show MASQUERADE |
| DNS doesn't resolve | `docker exec wg-easy iptables -t nat -L PREROUTING -v` should show DNAT to .11 |
| Zeek logs empty | `systemctl status zeek-vpn`. nsenter target PID changes on wg-easy restart — service should auto-restart. |
| Grafana not loading | `docker logs grafana` — slow first start due to DB migrations |
| DoH blocklist stale | `systemctl status doh-refresh.timer`, `cat /opt/vpn-data/state/doh_count` |

## MITM HTTPS Interception (Added 2026-06-01, laptop-only)

mitmproxy 12.2.3 decrypts HTTPS for peer 10.8.0.2 only (laptop). All other peers untouched. Custom CA (\`Home Network Root CA\`, 10-year, SHA256 \`DC:D9:7A:3F:D7:6B:F7:EA:1E:1C:14:5F:B1:DE:3B:E1:B6:DF:DE:46:71:10:4C:EB:1C:54:E9:FF:85:19:E6:A6\`) installed on Windows laptop trust store.

### Architecture
- mitmproxy 12.2.3 standalone binary at \`/usr/local/bin/mitmdump\`
- Runs via \`mitm-vpn.service\` -> \`nsenter\` into wg-easy netns -> listens on :8080 transparent mode
- iptables in wg-easy netns: REDIRECT \`-s 10.8.0.2 tcp dport 80,443 -> :8080\`, REJECT \`udp dport 443\` (force H3->H2)
- JSON logger addon \`/opt/vpn-data/mitm/json_logger.py\` -> \`/var/log/mitm/flows.json\` -> Promtail -> Loki -> Grafana panel "URLs visited (mitm, last hour)"
- ignore_hosts regex list in \`/root/.mitmproxy/config.yaml\` covers cert-pinned apps (Apple, banks, MS, Signal, etc.)

### Key Files
- \`/root/.mitmproxy/\` - CA bundle + config.yaml
- \`/opt/vpn-data/mitm/json_logger.py\` - JSON flow logger addon
- \`/opt/vpn-data/mitm/config.yaml\` - source-of-truth ignore_hosts (mirrored to confdir)
- \`/etc/systemd/system/mitm-vpn.service\` - daemon
- \`/opt/vpn-data/scripts/apply-wg-firewall.sh\` - has the per-peer iptables block

### Windows CA install
See \`/mnt/documents/personal/alec/claudeai/vpn/mitm-windows-install.md\` for the user-facing guide.

### Adding a host to ignore_hosts when an app breaks
1. \`vi /root/.mitmproxy/config.yaml\` -> add regex under \`ignore_hosts:\`
2. \`systemctl restart mitm-vpn.service\`

### Rollback
\`systemctl mask --now mitm-vpn.service\` + delete the 3 iptables rules with \`-s 10.8.0.2\` (see Windows install doc for exact commands). wg-easy/Zeek/Suricata untouched.
