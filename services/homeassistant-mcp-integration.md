# Home Assistant MCP Integration

**Last Updated**: 2026-01-26
**Status**: Research complete, not yet implemented

---

## Overview

MCP (Model Context Protocol) allows Claude to interact with external systems through defined tools. By adding a Home Assistant MCP server, Claude can monitor and control smart home devices directly from conversations.

```
┌─────────────────┐      stdio      ┌─────────────────┐      HTTP      ┌─────────────────┐
│   Claude Code   │ ◄────────────► │    hass-mcp     │ ◄────────────► │ Home Assistant  │
│   (LXC 124)     │   (local pipe)  │  (Python proc)  │   (REST API)   │                 │
└─────────────────┘                 └─────────────────┘                └─────────────────┘
```

---

## Available MCP Servers Compared

| Server | Language | Install Method | Capabilities | Maintained |
|--------|----------|----------------|--------------|------------|
| [voska/hass-mcp](https://github.com/voska/hass-mcp) | Python | pip, uvx, Docker | Read + Control | ✓ Active |
| [tevonsb/homeassistant-mcp](https://github.com/tevonsb/homeassistant-mcp) | Node.js | npm, Docker | Full ecosystem (HACS, add-ons) | ✓ Active |
| [Official HA MCP Server](https://www.home-assistant.io/integrations/mcp_server/) | Python | HA Integration | Expose Assist API | ✓ Core |
| [mtebusi/HA_MCP](https://github.com/mtebusi/HA_MCP) | Node.js | HA Add-on | SSE transport | ✗ Archived |

**Recommendation**: `voska/hass-mcp` - simplest setup, pip installable, covers most use cases.

---

## hass-mcp Capabilities

### Tools Available

| Tool | Description |
|------|-------------|
| `get_version` | Get Home Assistant version |
| `get_entity` | Get state of specific entity with optional field filtering |
| `entity_action` | Turn on/off/toggle entities, set brightness, temperature, etc. |
| `list_entities` | List all entities or filter by domain |
| `search_entities_tool` | Find entities by name, area, or attributes |
| `domain_summary_tool` | Get summary of all entities in a domain |
| `list_automations` | List all automations |
| `call_service_tool` | Call any Home Assistant service |
| `restart_ha` | Restart Home Assistant |
| `get_history` | Get historical state data for an entity |
| `get_error_log` | Read Home Assistant error log |

### What It CAN Do

- Query entity states (sensors, lights, switches, climate, etc.)
- Control devices (turn on/off, set values, toggle)
- Run scenes and scripts
- Trigger automations
- Read error logs for debugging
- View state history
- Get domain summaries ("show all lights")
- Search entities by various criteria
- Restart Home Assistant

### What It CANNOT Do

- Create entities
- Create or edit automations
- Modify Home Assistant configuration
- Install integrations or add-ons
- Edit YAML files
- Manage HACS

### Workarounds via call_service

Some creation is possible through HA services:

```yaml
# Create input helpers
input_boolean.create
input_number.create
input_text.create
input_datetime.create
input_select.create

# Reload configurations
automation.reload
script.reload
scene.reload
```

---

## Installation (Claude LXC 124)

### Prerequisites

- Python 3.11+ (available: Python 3.11.2)
- pip3 (available)
- Home Assistant URL
- Long-lived access token

### Step 1: Install hass-mcp

```bash
pip3 install hass-mcp
```

Or for enhanced version with automation traces:
```bash
pip3 install hass-mcp-plus
```

### Step 2: Get HA Access Token

1. Log into Home Assistant
2. Click profile (bottom left)
3. Go to Security tab
4. Scroll to "Long-Lived Access Tokens"
5. Click "Create Token"
6. Name it (e.g., "Claude MCP")
7. Copy the token (only shown once)

### Step 3: Configure MCP

Edit `/home/claudeai/.mcp.json`:

```json
{
  "mcpServers": {
    "filesystem": { ... },
    "memory": { ... },
    "sqlite": { ... },
    "homeassistant": {
      "command": "python3",
      "args": ["-m", "hass_mcp"],
      "env": {
        "HA_URL": "http://<HA_IP>:8123",
        "HA_TOKEN": "<YOUR_LONG_LIVED_TOKEN>"
      }
    }
  }
}
```

### Step 4: Enable in Claude Settings

Edit `/home/claudeai/.claude/settings.json`:

```json
{
  "enabledMcpjsonServers": [
    "filesystem",
    "memory",
    "sqlite",
    "homeassistant"
  ]
}
```

### Step 5: Restart Claude Code

Exit and restart the Claude Code session to load the new MCP server.

---

## Example Usage

After setup, Claude can:

**Query states:**
> "What's the temperature in the living room?"
> → Calls `get_entity` for `sensor.living_room_temperature`

**Control devices:**
> "Turn on the porch lights"
> → Calls `entity_action` for `light.porch`

**Run scenes:**
> "Activate movie mode"
> → Calls `call_service` for `scene.turn_on` with `scene.movie_mode`

**Debug issues:**
> "Why did my garage automation fail?"
> → Calls `get_error_log` and `get_history`

**Bulk queries:**
> "Show me all lights that are on"
> → Calls `list_entities` with domain filter and state filter

---

## Security Considerations

| Aspect | Detail |
|--------|--------|
| Authentication | Long-lived access token (you control scope) |
| Network | Local LAN only (192.168.0.x) |
| Permissions | Token determines what Claude can access |
| Data flow | Claude → hass-mcp (local) → HA (local) |
| No cloud | All traffic stays on local network |

### Token Scope

The access token grants full API access by default. To limit:
- Use HA's entity exposure settings
- Create a dedicated user with limited permissions
- Token inherits user's permissions

---

## Alternative: tevonsb/homeassistant-mcp

For more comprehensive capabilities (HACS, add-ons, automation editing):

```bash
git clone https://github.com/tevonsb/homeassistant-mcp.git
cd homeassistant-mcp
npm install
npm run build
```

Requires Node.js 20+ and more complex setup.

---

## Troubleshooting

### MCP server not loading

```bash
# Test manually
python3 -m hass_mcp
```

Should output MCP protocol messages. If errors, check:
- `HA_URL` environment variable
- `HA_TOKEN` environment variable
- Network connectivity to HA

### Connection refused

- Verify HA is running
- Check firewall allows port 8123
- Ensure HA URL is correct (http vs https)

### Authentication failed

- Token may have expired or been revoked
- Create new token in HA

### Entity not found

- Entity ID may be different than expected
- Use `list_entities` or `search_entities_tool` to find correct ID

---

## References

- [voska/hass-mcp GitHub](https://github.com/voska/hass-mcp)
- [hass-mcp on PyPI](https://pypi.org/project/hass-mcp/)
- [hass-mcp-plus (enhanced fork)](https://pypi.org/project/hass-mcp-plus/)
- [tevonsb/homeassistant-mcp GitHub](https://github.com/tevonsb/homeassistant-mcp)
- [Official HA MCP Server Integration](https://www.home-assistant.io/integrations/mcp_server/)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)

---

## Status

| Item | Status |
|------|--------|
| Research | ✓ Complete |
| Package selection | ✓ hass-mcp recommended |
| Installation | ⏳ Pending (need HA URL + token) |
| Configuration | ⏳ Pending |
| Testing | ⏳ Pending |
