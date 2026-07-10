# t5 — Second Proxmox Node (Lenovo Legion T5)

**Last Updated**: 2026-07-10
**Related Systems**: Proxmox node `t5` (192.168.0.152), Shipyard (192.168.0.151), Trailhead

## Summary
Installed Proxmox VE 9.2 on the inherited Lenovo Legion T5 28IMB05, creating a standalone second
PVE node at `t5.1701.me` / 192.168.0.152. The node exists to host CUDA workloads (Ollama, TTS) on
its GTX 1660 Super — Shipyard is a Beelink mini-PC with no PCIe slot and can never take a GPU.
Deliberately **not clustered** with Shipyard (2-node corosync loses quorum whenever either reboots,
and every guest is pinned to node-local hardware anyway).

## Hardware
| Component | Detail |
|---|---|
| Model | Lenovo Legion T5 28IMB05 (Intel B460, LGA1200, locked OEM BIOS) |
| CPU | i5-10400 (6c/12t, 65 W, UHD 630 iGPU — **disabled by BIOS**, see Troubleshooting) |
| GPU | GTX 1660 Super 6 GB (TU116, NVENC 8-session limit, no AV1) |
| RAM | 2×8 GB DDR4-2666 (4 slots, 128 GB max, no XMP on B460) |
| Storage | 256 GB WD SN730 NVMe (PVE root + local-lvm) · 1 TB ST1000DM003 HDD (future ISO/vzdump target, untouched) |
| PSU | FSP400-60AGBAK 400 W (factory 650 W drop-in exists if ever needed) |
| Network | Onboard Realtek gigabit (r8169) → office MS60 mesh-satellite ethernet port |

## Problem / Goal
The homelab had no CUDA-capable host. The T5 arrived with a dead Windows install (OOBE crash,
unrecoverable sysprep profile), so the goal was: wipe it, install PVE, get the node patched and
on the LAN — GPU driver work is a separate follow-up phase.

## Solution
Standard PVE 9.2-1 ISO install from USB onto the NVMe, static IP, then first-boot repo fix +
full upgrade, and Trailhead onboarding.

## Implementation Details

### Node identity
| Field | Value |
|---|---|
| IP | 192.168.0.152/24 (static, chosen next to Shipyard's .151) |
| Gateway / DNS | 192.168.0.1 / 192.168.0.11 (AdGuard) |
| Hostname | `t5.1701.me` |
| Web UI | https://192.168.0.152:8006 |
| Root password | fleet standard |

### Steps Performed
1. **Flash installer USB (Windows)** — downloaded `proxmox-ve_9.2-1.iso`, verified SHA256 with
   `certutil -hashfile ... SHA256`, flashed with balenaEtcher. (Rufus works only in **DD Image
   mode** — answer "No" to its GRUB-download prompt; ISO mode produces a non-booting stick.)
2. **Install** — F12 boot menu → graphical installer → target = the 256 GB NVMe (ext4/LVM
   defaults, 8 GB swap), static network config above. Install completes fine with no cable
   attached; config takes effect at first link-up.
3. **Repo fix** (fresh installs ship with the enterprise repo enabled → `apt update` fails 401):
   ```bash
   # disable enterprise (deb822 format)
   for f in pve-enterprise ceph; do echo "Enabled: false" >> /etc/apt/sources.list.d/$f.sources; done
   cat > /etc/apt/sources.list.d/proxmox.sources <<EOF
   Types: deb
   URIs: http://download.proxmox.com/debian/pve
   Suites: trixie
   Components: pve-no-subscription
   Signed-By: /usr/share/keyrings/proxmox-archive-keyring.gpg
   EOF
   ```
4. **Update + reboot** — `apt update && apt -y dist-upgrade` (67 pkgs incl. new kernel), reboot
   into `7.0.14-4-pve`. Node boots in ~45 s.
5. **Trailhead onboarding** — added "Proxmox (t5)" card (Hypervisor category,
   `https://192.168.0.152:8006`) to `/mnt/docker/trailhead/trailhead.yaml`, then rebuilt the
   generator (`docker compose build generator && docker compose up -d generator` — the yaml is
   baked into the image; `touch /tmp/regen` alone does NOT pick up yaml edits).

### Key Files Modified
- `/etc/apt/sources.list.d/{pve-enterprise,ceph}.sources` (t5) — disabled
- `/etc/apt/sources.list.d/proxmox.sources` (t5) — added no-subscription repo
- `/mnt/docker/trailhead/trailhead.yaml` (CT 128) — new bookmark card

## Verification
- `pveversion` → `pve-manager/9.2.4` on kernel `7.0.14-4-pve`; `apt list --upgradable` → 0
- Web UI answers at https://192.168.0.152:8006
- `lspci | grep -i nvidia` → GTX 1660 Super at 01:00.0 (bound to nouveau until driver phase)
- Trailhead: `docker exec trailhead-web grep 192.168.0.152 /usr/share/nginx/html/index.html`

## Troubleshooting
- **Etcher fails validation repeatedly** → the USB stick is bad. Swap sticks; don't keep retrying
  (a hash-verified ISO + 2× validation failure = dying/counterfeit flash).
- **Installer relaunches after install** → the USB stick is still inserted and boots first. Pull
  it and power-cycle; the completed install on the NVMe is intact.
- **iGPU (UHD 630) absent from `lspci`** → the locked Lenovo BIOS disables it whenever a discrete
  card is present. The only lever is *Select Active Video = IGD*, which routes video to a chip with
  **no physical outputs** (this board has none) → black console, CMOS-reset recovery. Not worth it:
  NVENC/NVDEC on the 1660 Super covers any transcode need, and media stays on Shipyard's Iris Xe.
- **GUI shows "apt-get update failed: received interrupt"** → a GUI-triggered refresh collided with
  a CLI apt run holding the lock. Cosmetic; re-run after the CLI job finishes.
- **WiFi** — never install/run PVE on WiFi: a station-mode NIC can't be bridged, so `vmbr0` breaks
  and guests end up NAT'd. The MS60 satellite's ethernet port makes the wireless hop invisible.

## Next Phase (not yet done)
NVIDIA proprietary driver (blacklist nouveau) → UVM boot-order systemd oneshot → GPU LXC template →
Ollama on CUDA → TTS trio. New guest volumes on this node need the MMP fix from
[lxc-onboarding.md](lxc-onboarding.md) Step 7, same as Shipyard.
