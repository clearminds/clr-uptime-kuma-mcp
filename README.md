# clr-uptime-kuma-mcp

MCP server for Uptime Kuma — monitor services, manage monitors, and control maintenance windows through AI assistants like Claude.

## Features

- **Status overview** — total monitor count, up/down/pending/maintenance breakdown
- **Monitor listing** — all monitors with status, response times, certificate info
- **Down detection** — quickly find which services are currently down
- **Certificate expiry** — SSL cert status sorted by urgency (critical/warning/OK)
- **Monitor management** — create, edit, delete monitors (HTTP, ping, port, DNS, and more)
- **Pause/resume** — pause and resume individual monitors
- **Maintenance windows** — create, delete, pause, resume maintenance windows
- **Dual auth** — API token for reads (Prometheus metrics), username/password for writes (Socket.IO)

## Installation

```bash
pip install clr-uptime-kuma-mcp
# or
uvx clr-uptime-kuma-mcp
```

## Configuration

**Preferred:** Configuration file at `~/.config/uptime-kuma/credentials.json` (chmod 600):

```json
{
  "url": "https://uptime.example.com",
  "token": "your-api-token",
  "username": "admin",
  "password": "your-password"
}
```

- `url` + `token` — required for read operations (Prometheus metrics endpoint)
- `username` + `password` — optional, required for write operations (Socket.IO API)

**Alternative:** Environment variables are also supported:

| Variable | Description | Example |
|----------|-------------|---------|
| `UPTIME_KUMA_URL` | Uptime Kuma URL | `https://uptime.example.com` |
| `UPTIME_KUMA_TOKEN` | API key (Prometheus Basic Auth) | `uk1_abc123...` |
| `UPTIME_KUMA_USERNAME` | Username for write operations | `admin` |
| `UPTIME_KUMA_PASSWORD` | Password for write operations | `secretpass` |

Optional:

| Variable | Description | Default |
|----------|-------------|---------|
| `KUMA_READ_ONLY` | Run in read-only mode | `false` |
| `TRANSPORT` | Transport protocol (`stdio` or `http`) | `stdio` |
| `LOG_LEVEL` | Log level | `INFO` |

**Priority:** Config file takes priority over environment variables.

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "uptime-kuma": {
      "command": "uvx",
      "args": ["clr-uptime-kuma-mcp"]
    }
  }
}
```

### Claude Code

Add via CLI:

```bash
claude mcp add uptime-kuma -- uvx clr-uptime-kuma-mcp
```

Or add to your `.mcp.json`:

```json
{
  "uptime-kuma": {
    "command": "uvx",
    "args": ["clr-uptime-kuma-mcp"]
  }
}
```

### VS Code

Add to your VS Code settings or `.vscode/mcp.json`:

```json
{
  "mcp": {
    "servers": {
      "uptime-kuma": {
        "command": "uvx",
        "args": ["clr-uptime-kuma-mcp"]
      }
    }
  }
}
```

**Note:** Configuration is read from `~/.config/uptime-kuma/credentials.json` or environment variables. No need to specify credentials in MCP config files.

### HTTP Transport

To run as a standalone HTTP server:

```bash
clr-uptime-kuma-mcp --transport http --host 0.0.0.0 --port 8000
```

## Tools

### Read Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `kuma_status` | Overall status summary (up/down/pending/maintenance counts + down list) | — |
| `kuma_list_monitors` | All monitors sorted by name with status, response times, cert info | — |
| `kuma_get_monitor` | Full details for a specific monitor | `monitor_id` |
| `kuma_down_monitors` | Only monitors currently down | — |
| `kuma_cert_expiry` | SSL certificate expiry sorted by urgency | — |

### Write Tools (require username/password)

| Tool | Description | Parameters |
|------|-------------|------------|
| `kuma_add_monitor` | Create a new monitor | `name`, `type`, `url` or `hostname`, `port`, `interval`, `keyword` |
| `kuma_edit_monitor` | Edit monitor settings (only provided fields are updated) | `monitor_id`, optional fields |
| `kuma_delete_monitor` | Delete a monitor | `monitor_id` |
| `kuma_pause_monitor` | Pause a monitor (stop checking) | `monitor_id` |
| `kuma_resume_monitor` | Resume a paused monitor | `monitor_id` |
| `kuma_list_maintenances` | List all maintenance windows | — |
| `kuma_add_maintenance` | Create a maintenance window | `title`, `strategy`, `description`, `date_range`, `cron`, `timezone` |
| `kuma_delete_maintenance` | Delete a maintenance window | `maintenance_id` |
| `kuma_pause_maintenance` | Pause a maintenance window | `maintenance_id` |
| `kuma_resume_maintenance` | Resume a maintenance window | `maintenance_id` |

### Monitor Types

`http`, `ping`, `port`, `dns`, `keyword`, `docker`, `push`, `mqtt`, `group`, `mysql`, `postgres`, `redis`, `mongodb`

### Maintenance Strategies

`manual`, `single`, `recurring-interval`, `recurring-weekday`, `recurring-day-of-month`, `cron`

## Example Usage

Once connected, you can ask your AI assistant things like:

- "Is anything down?"
- "Show all monitors"
- "Any SSL certs expiring soon?"
- "Add an HTTP monitor for https://example.com"
- "Pause monitor 5 for maintenance"
- "Create a maintenance window for tonight"
- "Delete monitor 12"
- "Resume all paused monitors"

## Safety

- Read operations use the Prometheus metrics endpoint (GET only, API key auth)
- Write operations use the Socket.IO API (username/password auth)
- Write tools are only available when username/password are configured
- **Destructive actions (delete monitor/maintenance) execute immediately — no confirmation**

## Technical Notes

- **Read API:** Prometheus `/metrics` endpoint with Basic Auth (empty username, API token as password)
- **Write API:** Socket.IO via `uptime-kuma-api` library, connects fresh per operation
- **Auth:** Read and write use different auth mechanisms — both can be configured independently
- **Lazy writes:** Write client is only initialized if username/password are provided

## Development

```bash
git clone https://github.com/clearminds/clr-uptime-kuma-mcp.git
cd clr-uptime-kuma-mcp
uv sync
uv run clr-uptime-kuma-mcp
```

## License

MIT — see [LICENSE](LICENSE) for details.
