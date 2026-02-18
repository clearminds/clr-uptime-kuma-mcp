# uptime-kuma-mcp-server

Uptime Kuma monitoring

## Install

```bash
pip install uptime-kuma-mcp-server
# or
uvx uptime-kuma-mcp-server
```

## Configuration

**Preferred:** Configuration file at `~/.config/uptime-kuma/credentials.json` (chmod 600):

```json
{
  "url": "https://uptime.example.com",
  "username": "admin",
  "password": "your-password"
}
```

**Alternative:** Environment variables are also supported:

| Variable | Description | Example |
|----------|-------------|---------|
| `UPTIME_KUMA_URL` | Uptime Kuma URL | `https://uptime.example.com` |
| `UPTIME_KUMA_USERNAME` | Username | `admin` |
| `UPTIME_KUMA_PASSWORD` | Password | `your-password` |

See `--help` for additional options:

```bash
uptime-kuma-mcp-server --help
```

## Development

```bash
git clone https://github.com/clearminds/uptime-kuma-mcp-server.git
cd uptime-kuma-mcp-server
uv sync
uv run uptime-kuma-mcp-server
```

## License

MIT
