# Provisioning an Orphaned Chromecast Audio Without Google Home

**Last Updated**: 2026-07-07
**Related Systems**: Chromecast Audio (now `Home Announcer`, 192.168.0.206), any device on the LAN

## Summary
A second-hand Chromecast Audio could not be set up through the Google Home app (it never appeared
on two Galaxy S23 phones). We provisioned it onto the home Wi-Fi **directly through the device's
local `eureka` setup API**, bypassing Google Home entirely. Result: the device joined `storm_slow`,
pulled an OTA firmware update, and was renamed — all via HTTP POSTs. This guide captures the working
method and the (many) gotchas.

## Problem / Goal
- Goal: get an orphaned/second-hand Chromecast Audio onto the home Wi-Fi.
- Blocker: the Google Home app would not discover the device for setup. This is a **known
  March 2025 expired-device-certificate bug** that broke setup on exactly the 2nd-gen Chromecast and
  Chromecast Audio; Google fixed it server-side and in Home app ≥ 3.30.1.6 (Android) / 3.30.106 (iOS).
  An outdated Home app silently fails to set these up — the most likely reason discovery failed.

## Solution
Every Chromecast in setup mode broadcasts an open Wi-Fi hotspot and runs a local setup server. You
can hand it Wi-Fi credentials directly:
1. `GET /setup/eureka_info` → read the device's RSA `public_key`.
2. RSA-encrypt (PKCS#1 v1.5) the Wi-Fi password with that key, base64 it.
3. `POST /setup/connect_wifi` + `/setup/save_wifi` with the SSID and encrypted password.

The device drops its hotspot and joins the target network. **No Google account or cloud token is
required while the device is in setup mode.**

## Implementation Details

### Device facts
- Setup hotspot SSID: `ChromecastAudioXXXX.a` (open). Device is at **`192.168.255.249`** on that AP.
- Reads (`eureka_info`) stay on cleartext **HTTP :8008**.
- **Writes (`connect_wifi`, `save_wifi`, `set_eureka_info`) moved to HTTPS :8443** on firmware since
  ~2019 (self-signed cert → disable TLS verification). POSTing writes to :8008 returns **403** — this
  was the single biggest red herring in our session.

### The working script
Saved at `/mnt/documents/personal/alec/claudeai/cca.py`. Run it from any machine joined to the
Chromecast's setup hotspot (`pip install rsa requests`):

```python
import base64, requests, rsa, urllib3
urllib3.disable_warnings()

WIFI_SSID = "storm_slow"      # target home network
WIFI_PASS = "<password>"
READ  = "http://192.168.255.249:8008"    # eureka_info stays cleartext here
WRITE = "https://192.168.255.249:8443"   # connect_wifi / save_wifi moved here

info = requests.get(f"{READ}/setup/eureka_info?options=detail", timeout=10).json()
pubkey = rsa.PublicKey.load_pkcs1(base64.b64decode(info["public_key"]), format="DER")
enc_b64 = base64.b64encode(rsa.encrypt(WIFI_PASS.encode(), pubkey)).decode()

# scan is skipped (unreliable in setup mode); WPA2-PSK/AES hardcoded
payload = {"ssid": WIFI_SSID, "enc_passwd": enc_b64, "wpa_auth": 7, "wpa_cipher": 4}
r  = requests.post(f"{WRITE}/setup/connect_wifi", json=payload, timeout=30, verify=False)
r2 = requests.post(f"{WRITE}/setup/save_wifi", json={"keep_hotspot_until_connected": True},
                   timeout=20, verify=False)
print("connect_wifi:", r.status_code, "| save_wifi:", r2.status_code)   # want 200 / 200
```

### Renaming (after it's on the LAN)
Once provisioned, the device is reachable at its LAN IP and can be renamed via the same API — and it
was NOT token-walled even when provisioned:
```bash
curl -k -X POST 'https://192.168.0.206:8443/setup/set_eureka_info' \
     -H 'Content-Type: application/json' --data '{"name":"Home Announcer"}'
# verify:
curl -s http://192.168.0.206:8008/setup/eureka_info | tr ',' '\n' | grep '"name"'
```

## Gotchas (the hard-won lessons)

1. **Windows will NOT hold the setup hotspot.** The hotspot is open with no internet; Windows NCSI
   flags it "No Internet" and WLAN AutoConfig silently roams the single Wi-Fi radio back to the home
   SSID. Symptoms: `net::ERR_ADDRESS_UNREACHABLE`, DHCP → APIPA (`169.254.x`), `arp -a` showing the
   adapter back on the home subnet. **Use an Android phone instead** — Android happily stays on a
   no-internet Wi-Fi for LAN while routing internet over cellular. On-device Python via **Pydroid 3**
   runs the same script. If you must use Windows: disable "Connect automatically" on the home SSID,
   set a static IP (`192.168.255.100/24`, blank gateway), and disable adapter power-save/roaming.

2. **`GET eureka_info` on :8008 works but POST writes 403** → writes moved to **HTTPS :8443**. This is
   the fix, not an auth failure. No `cast-local-authorization-token` is needed in setup mode.

3. **`scan_wifi`/`scan_results` returns empty** in setup mode — the single radio can't scan while
   hosting the 2.4 GHz AP. **Skip the scan** and hardcode `wpa_auth=7`, `wpa_cipher=4` for a normal
   WPA2-PSK/AES network. (The scan only exists to discover those two integers.)

4. **"Connected to the hotspot" ≠ reachable.** Confirm with `curl http://192.168.255.249:8008/setup/eureka_info`
   returning JSON before running the script. A resolved ARP entry for `.249` (`arp -a`) proves L2, but
   the device only services IP traffic to a client that stayed on its subnet.

5. **Dual-band ≠ prefer 5 GHz.** A Chromecast Audio streams a few hundred kbps; 5 GHz buys nothing.
   For a stationary audio device, **2.4 GHz is usually more reliable** (range/penetration). Only pick
   5 GHz if it sits close to the AP and 2.4 GHz is congested.

## Verification
- `setup_state` in `eureka_info` goes from `10` (setup mode) to `60` (provisioned).
- From the homelab, confirm it joined the LAN by MAC:
  ```bash
  ssh claude@192.168.0.151 "sudo nmap -sn 192.168.0.0/24 >/dev/null; ip neigh | grep -i a4:77:33"
  ```
- Query it directly: `curl -s http://192.168.0.206:8008/setup/eureka_info` → `connected:true`,
  `ssid:storm_slow`, `ip_address:192.168.0.206`.
- Cast a test track from a LAN host with `catt` or `pychromecast` (see below).

## Controlling / casting to it
- No web UI — port **8008** is the control API, **8009** is the Cast protocol (TLS), **5353/udp** is
  mDNS discovery.
- Scriptable with **CATT**: `catt -d 192.168.0.206 cast <media-url>` (install into a venv/pipx; the
  host Python on CT 124 is PEP-668 externally-managed).
- **Home Assistant** can cast TTS/announcements to it at `192.168.0.206` (fits the `Home Announcer`
  name).

## References
- rithvikvibhu/GHLocalApi — reverse-engineered eureka/setup endpoints
- interfect gist "Set up a Chromecast from Linux"; blog.brokennetwork.ca setup-without-Home-app
- 9to5Google / TechRadar (Mar 2025) — expired-cert bug + Home app 3.30.x fix for reset CCA/2nd-gen
