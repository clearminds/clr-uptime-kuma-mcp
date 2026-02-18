# clr-uptime-kuma-mcp

Uptime Kuma monitoring

## Install

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
clr-uptime-kuma-mcp --help
```

## Development

```bash
git clone https://github.com/clearminds/clr-uptime-kuma-mcp.git
cd clr-uptime-kuma-mcp
uv sync
uv run clr-uptime-kuma-mcp
```

## License

MIT
