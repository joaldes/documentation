# Dashy Dashboard Investigation

**Last Updated**: 2026-02-19
**Status**: Research / Not yet deployed
**Related Systems**: Komodo (LXC 128), Homepage (LXC 118), AdGuard (LXC 101), NPM (LXC 112)

## Summary

Investigation into Dashy (lissy93/dashy) as an alternative to Homepage (gethomepage.dev) for the homelab dashboard. Dashy has a significantly more powerful theming system with 40+ CSS variables, inline custom CSS, external stylesheet loading, and per-item color overrides — making it much better suited for the NPS Unigrid design theme than Homepage's Tailwind-based system that requires constant `!important` overrides.

## Why Dashy Over Homepage

| Feature | Dashy | Homepage |
|---------|-------|---------|
| CSS Variables | 40+ built-in (including `--curve-factor` for corners) | Fight Tailwind with `!important` |
| Theme System | Full custom theme creation, 25+ built-in, UI color picker | Just dark/light + color palette |
| Custom Fonts | `externalStyleSheet` config loads Google Fonts natively | Must hack via custom.css |
| Background Images | `backgroundImg` config option (supports SVG) | CSS-only via custom.css |
| Embed Widgets | `html-embed` with arbitrary HTML/CSS/JS | No custom HTML injection |
| Per-Item Styling | `item.color`, `item.backgroundColor` in config | Requires CSS class targeting |
| Status Checking | Built-in per-item with response time | Requires service widget integration |
| Multi-Link | `subItems` dropdown per item | Multi-link bookmarks only |
| Config | Single YAML, no database | Multiple YAML files |
| UI Config Editor | Built-in YAML + CSS editor | File-based only |

---

## Docker Deployment

### Image
`lissy93/dashy:latest`

### Docker Compose

```yaml
name: dashy
services:
  dashy:
    image: lissy93/dashy:latest
    container_name: dashy
    ports:
      - 4000:8080
    volumes:
      - ./conf.yml:/app/user-data/conf.yml
      - ./item-icons:/app/user-data/item-icons
    environment:
      - NODE_ENV=production
    restart: unless-stopped
    healthcheck:
      test: ['CMD', 'node', '/app/services/healthcheck']
      interval: 1m30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### Key Facts
- Container listens on port **8080** internally
- `NODE_ENV=production` is the only meaningful env var
- No database — single YAML file is the entire config
- Config file: `conf.yml` (`.yml`, NOT `.yaml`)
- Path inside container: `/app/user-data/conf.yml`
- Custom icons mount to `/app/user-data/item-icons/`
- Built-in healthcheck at `/app/services/healthcheck`

### Deployment on Komodo
- Stack directory: `/opt/stacks/dashy/`
- Port 4000 is available on Komodo (192.168.0.179)
- Komodo Periphery auto-discovers new stacks via Docker socket
- DNS: `dashy.home` → 192.168.0.30 (NPM) → 192.168.0.179:4000

---

## Configuration Reference

### Config Structure

Three root-level keys: `pageInfo`, `appConfig`, `sections`.

```yaml
pageInfo:
  title: SHIPYARD
  description: Proxmox Homelab Dashboard
  navLinks:
    - title: Proxmox
      path: https://192.168.0.151:8006
    - title: Komodo
      path: http://komodo.home

appConfig:
  theme: nps-park
  layout: auto
  iconSize: medium
  language: en
  statusCheck: true
  statusCheckInterval: 0
  disableUpdateChecks: true
  colCount: 3
  enableFontAwesome: true
  customCss: ''
  customColors: {}
  externalStyleSheet: []

sections:
  - name: Infrastructure
    icon: fas fa-server
    displayData:
      sortBy: default
      collapsed: false
      cols: 1
    items:
      - title: Proxmox
        description: Hypervisor management
        url: https://192.168.0.151:8006
        icon: hl-proxmox
        statusCheck: true
        statusCheckAllowInsecure: true
```

---

## Theme CSS Variables (Complete)

### Core Variables

| Variable | Description | NPS Value |
|---|---|---|
| `--primary` | Primary text/accent color | `#3b2314` (dark brown) |
| `--background` | Main background | `#f5f1eb` (cream) |
| `--background-darker` | Nav, section headers, footer | `#1a3024` (dark green) |
| `--curve-factor` | Global border-radius | `0px` (sharp corners) |

### Full Variable List

| Variable | Description |
|---|---|
| `--heading-text-color` | Heading text |
| `--nav-link-text-color` | Nav link text |
| `--nav-link-background-color` | Nav link background |
| `--nav-link-text-color-hover` | Nav link text hover |
| `--nav-link-background-color-hover` | Nav link bg hover |
| `--nav-link-border-color` | Nav link border |
| `--nav-link-border-color-hover` | Nav link border hover |
| `--search-container-background` | Search bar background |
| `--search-text-color` | Search input text |
| `--item-text-color` | Item text color |
| `--item-group-outer-background` | Section outer bg |
| `--item-group-background` | Section inner bg |
| `--item-group-heading-text-color` | Section heading text |
| `--item-group-padding` | Section border width |
| `--item-shadow` | Item box shadow |
| `--item-hover-shadow` | Item box shadow on hover |
| `--item-icon-transform` | CSS transform on item icon |
| `--item-icon-transform-hover` | Icon transform on hover |
| `--config-settings-color` | Settings panel text |
| `--config-settings-background` | Settings panel bg |
| `--scroll-bar-color` | Scrollbar thumb |
| `--scroll-bar-background` | Scrollbar track |
| `--footer-text-color` | Footer text |
| `--footer-background` | Footer background |
| `--font-headings` | Font family for headings |
| `--font-body` | Font family for body |

### Applying Custom Colors via Config

```yaml
appConfig:
  theme: nps-park
  customColors:
    nps-park:
      primary: '#3b2314'
      background: '#f5f1eb'
      background-darker: '#1a3024'
      curve-factor: '0px'
```

### Custom CSS Methods

**Method 1: Inline in config (`appConfig.customCss`)**
```yaml
appConfig:
  customCss: |
    .item { border-radius: 0; }
    .section-heading { font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.2em; }
```

**Method 2: External stylesheet (`appConfig.externalStyleSheet`)**
```yaml
appConfig:
  externalStyleSheet:
    - 'https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;600;700;900&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&display=swap'
    - 'https://example.com/my-theme.css'
```

**Method 3: Full custom theme via CSS selector**
```yaml
appConfig:
  customCss: |
    html[data-theme='nps-park'] {
      --primary: #3b2314;
      --background: #f5f1eb;
      --background-darker: #1a3024;
      --curve-factor: 0px;
    }
```

---

## NPS Theme Mapping for Dashy

### Color Tokens (from nps-homelab.html mockup)

| Element | Color | Hex | Dashy Variable |
|---------|-------|-----|----------------|
| Page background | Cream | `#f5f1eb` | `--background` |
| Card/panel bg | Off-white | `#f2ede3` | `--item-group-background` |
| Primary text | Dark brown | `#3b2314` | `--primary`, `--item-text-color` |
| Secondary text | Brown-gray | `#6b6259` | (customCss) |
| Nav/section headers | Dark green | `#1a3024` | `--background-darker` |
| Header text | Off-white | `#f2ede3` | `--nav-link-text-color`, `--item-group-heading-text-color` |
| Borders | Brown | `rgba(91,64,51,0.25)` | (customCss) |
| Accent/hover | Copper | `#c56c39` | (customCss) |
| Footer bg | Black | `#1a1a1a` | `--footer-background` |
| Footer text | Warm gray | `#cbc4bc` | `--footer-text-color` |
| Status healthy | Green | `#4a7c3f` | (customCss) |
| Warning | Gold | `#c8900a` | (customCss) |
| Scrollbar | Warm gray | `#cbc4bc` | `--scroll-bar-color` |

### Typography
- **Headings**: Source Sans 3 (weights 300, 400, 600, 700, 900) → `--font-headings`
- **Body**: Source Serif 4 (weights 400, 600, italic) → `--font-body`
- Loaded via `externalStyleSheet` Google Fonts URL

### Key CSS Overrides Needed (via customCss)

```css
/* Topo SVG background */
body::before {
  content: '';
  position: fixed;
  inset: 0;
  background-image:
    radial-gradient(ellipse at 20% 50%, rgba(40,71,52,0.04) 0%, transparent 60%),
    radial-gradient(ellipse at 80% 20%, rgba(139,71,32,0.03) 0%, transparent 50%),
    url("data:image/svg+xml,...[topo SVG]...");
  background-size: 400px 400px;
  pointer-events: none;
  z-index: 0;
}

/* Section headers — dark green bands */
.section-heading {
  font-family: 'Source Sans 3', sans-serif;
  font-weight: 700;
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.2em;
}

/* Item cards — off-white with brown borders */
.item {
  background: #f2ede3;
  border: 1px solid rgba(91,64,51,0.25);
  border-radius: 0;
}

/* Inset border channel */
.item::after {
  content: '';
  position: absolute;
  top: 4px; right: 4px; bottom: 4px; left: 4px;
  border: 1px solid rgba(91,64,51,0.12);
  pointer-events: none;
}

/* Hover states */
.item:hover {
  background: #f5f1eb;
  border-color: rgba(91,64,51,0.4);
}

/* Item titles — uppercase NPS style */
.item .tile-title {
  font-family: 'Source Sans 3', sans-serif;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-size: 0.82rem;
}
```

---

## Item Configuration

### Item Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `title` | string | Yes | Display name |
| `url` | string | No | Click destination URL |
| `description` | string | No | Subtitle/tooltip |
| `icon` | string | No | Icon identifier |
| `color` | string | No | Text/icon color |
| `backgroundColor` | string | No | Item background |
| `target` | string | No | `newtab`, `sametab`, `modal`, `workspace`, `clipboard` |
| `hotkey` | number | No | Keyboard shortcut (1-9) |
| `tags` | list | No | Search keywords |
| `statusCheck` | boolean | No | Per-item toggle |
| `statusCheckUrl` | string | No | Alternate URL for check |
| `statusCheckAllowInsecure` | boolean | No | Allow self-signed certs |
| `statusCheckAcceptCodes` | string | No | HTTP codes to accept |
| `subItems` | list | No | Nested links (multi-URL) |

### Icon Types

| Prefix | Example | Source |
|---|---|---|
| `hl-` | `hl-proxmox` | Home Lab Icons (self-hosted apps) |
| `fas fa-` / `fab fa-` | `fas fa-server` | Font Awesome |
| `si-` | `si-proxmox` | Simple Icons (brand SVGs) |
| `mdi-` | `mdi-docker` | Material Design Icons |
| `favicon` | `favicon` | Auto-fetch from URL |
| URL | `https://...` | Direct image URL |

### Multi-Link (subItems) — for LCL/EXT pattern

```yaml
- title: Emby
  icon: hl-emby
  statusCheck: true
  subItems:
    - title: Local
      url: http://emby.home
      icon: fas fa-home
    - title: External
      url: http://movies.1701.me
      icon: fas fa-globe
```

Parent renders as a single tile. Click expands dropdown with sub-items. Each subItem supports: `title`, `url`, `icon`, `color`, `target`.

### Single-Link Item

```yaml
- title: Grafana
  url: http://grafana.home
  icon: hl-grafana
  statusCheck: true
  description: Monitoring dashboards
```

---

## Status Checking

### Global Config
```yaml
appConfig:
  statusCheck: true
  statusCheckInterval: 0   # 0 = check on page load only (recommended)
```

### Per-Item
```yaml
- title: Proxmox
  url: https://192.168.0.151:8006
  statusCheck: true
  statusCheckUrl: https://192.168.0.151:8006/api2/json
  statusCheckAllowInsecure: true
  statusCheckAcceptCodes: '200,401,403'
```

- Green dot = up, Red dot = down
- Hover shows response time and status code
- `statusCheckAllowInsecure: true` needed for self-signed HTTPS
- Checks run server-side from the Dashy container

---

## Layout & Sections

### Global Layout
```yaml
appConfig:
  colCount: 3         # Section grid columns (1-8)
  layout: auto         # 'auto' or 'grid'
  iconSize: medium     # 'small', 'medium', 'large'
```

### Per-Section
```yaml
sections:
  - name: Infrastructure
    icon: fas fa-server
    displayData:
      cols: 2              # Span 2 grid columns (1-5)
      rows: 1              # Span rows (1-5)
      collapsed: false     # Start collapsed?
      sortBy: default      # 'default', 'alphabetical', 'most-used', 'last-used'
      cutToHeight: true    # Fixed height with scroll
      sectionLayout: grid  # 'grid' or 'auto'
      itemCountX: 4        # Items per row (grid mode, 1-12)
      itemSize: medium     # 'small', 'medium', 'large'
```

### Recommended for ~36 Services
- `colCount: 3` with 8 sections of 4-6 items each
- Important sections can span `cols: 2` or `cols: 3`

---

## Built-in Widgets

Widget sections use `widgets:` instead of `items:`. A section cannot have both.

### Available Widgets

| Type | Description | Needs |
|---|---|---|
| `clock` | Live clock | `timeZone`, `format` |
| `weather` | Current weather | OpenWeatherMap API key, `city`, `units` |
| `weather-forecast` | Multi-day forecast | Same as weather |
| `public-ip` | Public IP + ISP | — |
| `iframe` | Embed any URL | `url` |
| `html-embed` | Arbitrary HTML/CSS/JS | `html`, `css`, `script` |
| `gl-current-cpu` | CPU gauge | Glances API endpoint |
| `gl-current-mem` | Memory gauge | Glances API endpoint |
| `gl-disk-space` | Disk usage | Glances API endpoint |

### Widget Example
```yaml
- name: System Info
  widgets:
    - type: clock
      options:
        timeZone: America/Phoenix
        format: en-US
        hideDate: false
    - type: weather
      options:
        apiKey: YOUR_KEY
        city: Phoenix
        units: imperial
```

---

## Complete Example conf.yml (Homelab)

```yaml
pageInfo:
  title: SHIPYARD
  description: Proxmox Homelab Dashboard

appConfig:
  theme: nps-park
  layout: auto
  iconSize: medium
  statusCheck: true
  statusCheckInterval: 0
  disableUpdateChecks: true
  colCount: 3
  enableFontAwesome: true
  externalStyleSheet:
    - 'https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;600;700;900&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&display=swap'
  customColors:
    nps-park:
      primary: '#3b2314'
      background: '#f5f1eb'
      background-darker: '#1a3024'
      curve-factor: '0px'
  customCss: |
    /* NPS Unigrid Theme for Dashy */
    .section-heading {
      font-family: 'Source Sans 3', sans-serif !important;
      font-weight: 700 !important;
      font-size: 0.65rem !important;
      text-transform: uppercase !important;
      letter-spacing: 0.2em !important;
    }
    .item {
      border: 1px solid rgba(91,64,51,0.25) !important;
      position: relative;
    }
    .item:hover {
      background: #f5f1eb !important;
    }
    .tile-title {
      font-family: 'Source Sans 3', sans-serif !important;
      font-weight: 700 !important;
      text-transform: uppercase !important;
      letter-spacing: 0.06em !important;
    }

sections:
  - name: Infrastructure
    icon: fas fa-server
    items:
      - title: Proxmox
        url: http://proxmox.home
        icon: hl-proxmox
        statusCheck: true
        statusCheckAllowInsecure: true
        subItems:
          - title: Local
            url: http://proxmox.home
          - title: External
            url: http://proxmox.1701.me
      - title: AdGuard DNS
        icon: hl-adguardhome
        statusCheck: true
        subItems:
          - title: Local
            url: http://adguard.home
          - title: External
            url: http://adguard.1701.me
      - title: Nginx Proxy Manager
        url: http://npm.home
        icon: hl-nginx-proxy-manager
        statusCheck: true
      - title: Syncthing
        icon: hl-syncthing
        statusCheck: true
        subItems:
          - title: Local
            url: http://syncthing.home
          - title: External
            url: http://syncthing.1701.me
      - title: Z-Wave JS UI
        url: http://zwave.home
        icon: fas fa-broadcast-tower
        statusCheck: true
      - title: Tailscale
        url: https://login.tailscale.com
        icon: hl-tailscale
        statusCheck: false

  - name: Monitoring
    icon: fas fa-chart-line
    items:
      - title: Grafana
        url: http://grafana.home
        icon: hl-grafana
        statusCheck: true
      - title: Prometheus
        url: http://prometheus.home
        icon: hl-prometheus
        statusCheck: true
      - title: Uptime Kuma
        icon: hl-uptime-kuma
        statusCheck: true
        subItems:
          - title: Local
            url: http://uptimekuma.home
          - title: External
            url: http://uptime.1701.me
      - title: Pulse
        url: http://pulse.home
        icon: fas fa-heartbeat
        statusCheck: true

  - name: Media
    icon: fas fa-film
    displayData:
      cols: 2
    items:
      - title: Emby
        icon: hl-emby
        statusCheck: true
        subItems:
          - title: Local
            url: http://emby.home
          - title: External
            url: http://movies.1701.me
      - title: Jellyseerr
        icon: hl-jellyseerr
        statusCheck: true
        subItems:
          - title: Local
            url: http://jellyseerr.home
          - title: External
            url: http://mediarequest.1701.me
      - title: Jellystat
        icon: fas fa-chart-bar
        statusCheck: true
        subItems:
          - title: Local
            url: http://jellystat.home
          - title: External
            url: http://mediastats.1701.me
      - title: Radarr
        icon: hl-radarr
        statusCheck: true
        subItems:
          - title: Local
            url: http://radarr.home
          - title: External
            url: http://radarr.1701.me
      - title: Sonarr
        icon: hl-sonarr
        statusCheck: true
        subItems:
          - title: Local
            url: http://sonarr.home
          - title: External
            url: http://sonarr.1701.me
      - title: Bazarr
        icon: hl-bazarr
        statusCheck: true
        subItems:
          - title: Local
            url: http://bazarr.home
          - title: External
            url: http://subtitles.1701.me
      - title: Tdarr
        url: http://tdarr.home
        icon: hl-tdarr
        statusCheck: true

  - name: Documents
    icon: fas fa-file-alt
    items:
      - title: Paperless
        icon: hl-paperless-ngx
        statusCheck: true
        subItems:
          - title: Local
            url: http://paperless.home
          - title: External
            url: http://scan.1701.me
      - title: Paperless AI
        url: http://paperless-ai.home
        icon: fas fa-robot
        statusCheck: true
      - title: Stirling PDF
        icon: hl-stirling-pdf
        statusCheck: true
        subItems:
          - title: Local
            url: http://bentopdf.home
          - title: External
            url: http://pdf.1701.me
      - title: Wiki JS
        icon: hl-wikijs
        statusCheck: true
        subItems:
          - title: Local
            url: http://wikijs.home
          - title: External
            url: http://wiki.1701.me

  - name: Photos & 3D
    icon: fas fa-camera
    items:
      - title: Immich
        url: http://immich.home
        icon: hl-immich
        statusCheck: true
      - title: Manyfold
        icon: fas fa-cube
        statusCheck: true
        subItems:
          - title: Local
            url: http://manyfold.home
          - title: External
            url: http://3d.1701.me

  - name: Home & Recipes
    icon: fas fa-home
    items:
      - title: Home Assistant
        url: http://homeassistant.home
        icon: hl-home-assistant
        statusCheck: true
      - title: Mealie
        url: http://mealie.home
        icon: hl-mealie
        statusCheck: true
      - title: Tandoor
        icon: fas fa-utensils
        statusCheck: true
        subItems:
          - title: Local
            url: http://tandoor.home
          - title: External
            url: http://recipes.1701.me

  - name: Utilities
    icon: fas fa-tools
    displayData:
      cols: 2
    items:
      - title: Claude AI
        url: http://claude.home
        icon: fas fa-brain
        statusCheck: true
      - title: Komodo
        url: http://komodo.home
        icon: fas fa-dragon
        statusCheck: true
      - title: Authentik
        url: http://authentik.home
        icon: hl-authentik
        statusCheck: true
      - title: Fragments
        icon: fas fa-bookmark
        statusCheck: true
        subItems:
          - title: Local
            url: http://fragments.home
          - title: External
            url: http://fragments.1701.me
      - title: Reyday
        url: http://reyday.home
        icon: fas fa-envelope
        statusCheck: true
      - title: Sander
        url: http://sander.home
        icon: fas fa-file-upload
        statusCheck: true
      - title: Tracearr
        url: http://tracearr.home
        icon: fas fa-route
        statusCheck: true
      - title: Notifiarr
        url: http://notifiarr.home
        icon: hl-notifiarr
        statusCheck: true
      - title: Unmanic
        url: http://unmanic.home
        icon: fas fa-video
        statusCheck: true

  - name: Birds
    icon: fas fa-dove
    items:
      - title: BirdNet Go
        icon: fas fa-feather-alt
        statusCheck: true
        subItems:
          - title: Local
            url: http://birds.home
          - title: External
            url: http://birds2.1701.me
```

---

## Deployment Plan (When Ready)

1. Create `/opt/stacks/dashy/compose.yaml` on LXC 128
2. Create `/opt/stacks/dashy/conf.yml` on LXC 128
3. `docker compose up -d` from `/opt/stacks/dashy/`
4. Add AdGuard DNS rewrite: `dashy.home` → `192.168.0.30`
5. Add NPM proxy host: `dashy.home` → `192.168.0.179:4000`
6. Compare side-by-side with `http://homepage.home`
7. Decide which to keep

## References
- [Dashy GitHub](https://github.com/Lissy93/dashy)
- [Dashy Docs — Configuring](https://dashy.to/docs/configuring/)
- [Dashy Docs — Theming](https://dashy.to/docs/theming/)
- [Dashy Docs — Status Indicators](https://dashy.to/docs/status-indicators/)
- [Dashy Docs — Widgets](https://dashy.to/docs/widgets/)
- [Dashy Docs — Icons](https://dashy.to/docs/icons/)
- NPS design mockup: `/mnt/documents/personal/alec/claudeai/nps-homelab.html`
