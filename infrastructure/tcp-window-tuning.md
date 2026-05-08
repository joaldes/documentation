# Fast Far-Away Transfers — Empirical Results + Defaults

**Last Updated**: 2026-05-07 (post-empirical testing)
**Status**: **Decision made — aria2 -x 8 is the default for big HTTP file pulls. Kernel tuning shelved (not needed for current use cases).**
**Related Systems**: CT 124 (Claude AI) primarily; any host pulling large files
**Multi-agent reviewed**: 2026-05-07 (3 reviewers)

## TL;DR — what to actually do

For any **single big file** download from HTTP/HTTPS/FTP, run:

```bash
aria2c -x 8 -s 8 -k 1M --file-allocation=none URL
```

That alone gives **2× speedup over single-stream curl/wget** on real-world transfers. No kernel tuning needed.

**For SFTP/SSH** with public-key auth: aria2 doesn't support pubkey. Use `rsync` or `scp`. If the source is shaped (like Hetzner CCX23), no tool will help — accept the ceiling.

## Empirical Results (2026-05-07)

Tested CT 124 (Tucson) pulling 1-2 GB files from various sources.

| Source | Method | Throughput | Notes |
|---|---|---|---|
| Hetzner Falkenstein (`scp`) | single-stream SSH | 8.6 MB/s (69 Mbps) | Source shaped at sustained ~100 Mbps |
| Hetzner Falkenstein (HTTP) | single-stream curl | 13.6 MB/s (109 Mbps) | SSH cipher overhead removed → 1.6× faster |
| Hetzner Falkenstein (HTTP) | aria2 -x 8 | 14.9 MB/s (119 Mbps) | Hits Hetzner CCX23 ceiling; parallel only adds 10% |
| thinkbroadband UK (HTTP) | single-stream curl | 17.7 MB/s (142 Mbps) | Real BDP-limited single-stream from EU |
| thinkbroadband UK (HTTP) | **aria2 -x 8** | **38.6 MB/s (309 Mbps)** | **2.18× speedup; no kernel tuning** |

**Home link cap**: 800 Mbps. Not yet saturated even with parallel — likely backbone or source server side. For transfers we actually do (≤30 GB occasional), 309 Mbps is plenty.

## Decision Log

- **2026-05-07 morning**: First draft of this doc proposed kernel `tcp_rmem` tuning. Tabled because rsync was already mid-flight.
- **2026-05-07 afternoon**: Multi-agent review found 3 critical fixes (namespace scope, `tcp_mem` safety cap, BBR positioning).
- **2026-05-07 afternoon**: Pivoted from phased rollout to "all-at-once" (window + aria2 parallel).
- **2026-05-07 afternoon**: Empirical test:
  - Hetzner side appears shaped at ~120 Mbps regardless of TCP-level optimization.
  - thinkbroadband (real source) showed 2.18× from parallel alone, no kernel tuning.
  - Conclusion: **parallel streams alone unlock the gains**. Kernel tuning is not the bottleneck in our typical use case.
- **2026-05-07**: **Decision: aria2 default for big HTTP pulls. Kernel tuning shelved.**

## When to use which tool

| Tool | Use case | Comment |
|---|---|---|
| **`aria2c -x 8 -s 8`** | Big single HTTP/HTTPS/FTP file (>500 MB) | **Default. ~2× faster than curl/wget.** Supports byte-range parallel reads, BitTorrent, Magnet links. |
| `rsync -avP` | Directory trees, incremental sync, anything over SSH | Native pubkey auth. Unbeatable for re-syncing changed files. |
| `scp` | One-off small copies | Convenient. SSH pubkey works. Slow for big files (single-stream + cipher cost). |
| `wget -c URL` | Resumable single file, no parallel needed | Lighter than aria2. Use if you want simplicity. |
| `rclone copy` | Cloud storage (S3, GDrive, B2, etc.) | Built for cloud APIs. Has its own parallel. |
| `curl` | Quick HTTP fetches, scripting | Use for `<100 MB`. |

## Recommended bash alias

Add to `~/.bashrc` or `/etc/profile.d/aria.sh`:
```bash
alias bigpull='aria2c -x 8 -s 8 -k 1M --file-allocation=none --console-log-level=warn --summary-interval=10'
```

Then: `bigpull -d /tmp -o foo.tar https://example.com/foo.tar`

## What we DIDN'T need (and why)

### Kernel TCP window tuning (`net.ipv4.tcp_rmem`)
Was the original proposal. Empirically, on the workloads we actually have:
- Hetzner sources are shaped at ~120 Mbps regardless of window. Tuning won't help.
- Real fast sources (thinkbroadband) saturate at ~309 Mbps with **parallel alone**. Tuning *might* push higher but we never need >300 Mbps for once-every-few-months pulls.

If a future transfer plateaus at single-stream-limited speeds (~140 Mbps) AND parallel doesn't help — that's the signal to revisit kernel tuning. Until then, **shelved**.

### BBR congestion control
Considered as alternative path. Empirically the loss isn't where we'd benefit:
- Hetzner path: shaped, not lossy
- thinkbroadband path: cubic gets us 142 single-stream, parallel scales linearly → no loss

BBR shines on lossy paths (`mtr` showing >0.5% drops). Not our scenario.

### Application-level cipher tuning (ChaCha20 vs AES-GCM)
Single-stream SSH was 69 Mbps. With AES-NI hardware acceleration, OpenSSH can push 2-3 Gbps single-core. Cipher isn't the bottleneck at our throughput. Skip.

## Reference Configurations (kept for posterity)

If future you needs to apply the kernel tuning anyway, here's the validated config from the multi-agent review:

### `/etc/sysctl.d/99-bigwin.conf` (apply INSIDE the LXC where transfers run)
```ini
# Per-socket window caps for high-BDP transfers
net.ipv4.tcp_rmem = 4096 524288 67108864
net.ipv4.tcp_wmem = 4096 524288 67108864
net.core.rmem_max = 67108864
net.core.wmem_max = 67108864
# Global TCP memory ceiling — safety valve so a runaway can't OOM the LXC.
# Format: low pressure max (4 KB pages). Values = 256 MB / 2 GB / 4 GB.
net.ipv4.tcp_mem = 65536 524288 1048576
net.ipv4.tcp_window_scaling = 1
```

```bash
sudo cp 99-bigwin.conf /etc/sysctl.d/99-bigwin.conf
sudo sysctl --system
```

**Key correction from the review**: these sysctls are network-namespace-scoped. Setting them on the Proxmox host doesn't propagate into LXCs. Apply *inside the LXC where transfer processes run.*

### Optional BBR
```bash
echo "net.ipv4.tcp_congestion_control = bbr" | sudo tee -a /etc/sysctl.d/99-bigwin.conf
echo "net.core.default_qdisc = fq" | sudo tee -a /etc/sysctl.d/99-bigwin.conf
sudo sysctl --system
```

Only worth it if `mtr -c 200 <host>` shows packet loss >0.5% on transatlantic hops.

### Rollback
```bash
sudo rm /etc/sysctl.d/99-bigwin.conf && sudo sysctl --system
```

## References
- Empirical test 2026-05-07 — this doc
- ESnet fasterdata.es.net — recommends `tcp_rmem max = 67108864` for 100+ Mbps × 100+ ms RTT links
- Linux kernel `net/ipv4/tcp.c` — `tcp_moderate_rcvbuf` auto-tune
- Google IETF77 BBR paper (Cardwell et al., 2016)
- aria2 docs — http://aria2.github.io/manual/en/html/
