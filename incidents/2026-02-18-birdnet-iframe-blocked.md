# BirdNET-Go Iframe Blocked in Home Assistant Dashboard

**Last Updated**: 2026-02-18
**Related Systems**: BirdNET-Go (Container 128), Home Assistant (VM 100), Nginx Proxy Manager

## Summary
BirdNET-Go dashboard could not load in a Home Assistant iframe panel due to the `X-Frame-Options: SAMEORIGIN` header sent by BirdNET-Go, combined with an incorrect HTTPS URL. Resolved by stripping the header in Nginx Proxy Manager and using the correct HTTP proxy URL.

## Problem
Attempting to embed BirdNET-Go's dashboard (`https://192.168.0.179:8060/ui/dashboard`) in a Home Assistant dashboard iframe resulted in two issues:
1. **"Invalid response"** — the URL used `https://` but BirdNET-Go serves plain HTTP on port 8060
2. **Iframe refused to load** — BirdNET-Go sends `X-Frame-Options: SAMEORIGIN`, blocking cross-origin iframe embedding

## Solution
1. Added a custom Nginx directive in Nginx Proxy Manager to strip the blocking header
2. Used the NPM proxy domain (`http://birds.1701.me/ui/dashboard`) instead of the direct IP

## Implementation Details

### Steps Performed
1. Confirmed the `X-Frame-Options: SAMEORIGIN` header was present on BirdNET-Go responses:
   ```bash
   curl -sI http://192.168.0.179:8060/ | grep -i x-frame
   # X-Frame-Options: SAMEORIGIN
   ```

2. Checked BirdNET-Go config — no setting to disable the header; it is hardcoded in the application.

3. In **Nginx Proxy Manager**, edited the proxy host for BirdNET-Go and added this in the **Advanced** tab:
   ```nginx
   proxy_hide_header X-Frame-Options;
   ```

4. Updated the Home Assistant dashboard iframe URL to use the proxy domain:
   ```
   http://birds.1701.me/ui/dashboard
   ```

### Key Configuration
- **NPM Proxy Host**: `birds.1701.me` → `192.168.0.179:8060`
- **Custom Nginx Directive**: `proxy_hide_header X-Frame-Options;`

## Verification
BirdNET-Go dashboard loads correctly inside the Home Assistant iframe panel at `http://birds.1701.me/ui/dashboard`.

## Troubleshooting
- If the iframe shows nested sidebars (HA sidebar + BirdNET sidebar repeating), the BirdNET-Go full UI shell is being loaded recursively — ensure the URL path is `/ui/dashboard`
- If "invalid response" appears, verify the URL uses `http://` not `https://` (unless NPM terminates TLS)
- The `X-Frame-Options` header is hardcoded in BirdNET-Go and cannot be disabled via config — a reverse proxy is required
