# Uptime Kuma Write Operations Design

**Date:** 2026-02-18
**Status:** Approved

## Problem

The current implementation is read-only, using only the Prometheus `/metrics` endpoint. Users need to create/delete monitors, pause/resume monitoring, and manage maintenance windows.

## Approach: Hybrid Client

- **Read operations** stay on existing `KumaClient` (Prometheus `/metrics` + API token)
- **Write operations** use new `KumaWriteClient` wrapping `uptime-kuma-api` library (Socket.IO + username/password)
- Write client connects lazily (only when a write tool is first called)
- If username/password not configured, write tools fail with clear error message

## New Dependency

- `uptime-kuma-api>=1.2.0` (PyPI) - Python wrapper for Uptime Kuma Socket.IO API

## Credential Changes

### New fields

- `UPTIME_KUMA_USERNAME` env var / `username` in credentials.json
- `UPTIME_KUMA_PASSWORD` env var / `password` in credentials.json

### credentials.json format

```json
{
  "url": "https://uptime.example.com",
  "token": "api-token-for-reads",
  "username": "admin",
  "password": "secret"
}
```

### Priority order

1. Environment variables (base/fallback)
2. Config file (`~/.config/uptime-kuma/credentials.json`) takes priority

## New Tools (10)

### Monitor Management

| Tool | Parameters | Returns |
|------|-----------|---------|
| `kuma_add_monitor` | `name: str, type: str, url: str = "", hostname: str = "", port: int = 0, interval: int = 60, keyword: str = ""` | `dict` with monitor_id |
| `kuma_edit_monitor` | `monitor_id: int, name: str = "", url: str = "", interval: int = 0, ...` | `dict` with ok/msg |
| `kuma_delete_monitor` | `monitor_id: int` | `dict` with ok/msg |

### Pause/Resume

| Tool | Parameters | Returns |
|------|-----------|---------|
| `kuma_pause_monitor` | `monitor_id: int` | `dict` with ok/msg |
| `kuma_resume_monitor` | `monitor_id: int` | `dict` with ok/msg |

### Maintenance Windows

| Tool | Parameters | Returns |
|------|-----------|---------|
| `kuma_list_maintenances` | (none) | `list[dict]` |
| `kuma_add_maintenance` | `title: str, strategy: str = "manual", description: str = "", ...` | `dict` with maintenance_id |
| `kuma_delete_maintenance` | `maintenance_id: int` | `dict` with ok/msg |
| `kuma_pause_maintenance` | `maintenance_id: int` | `dict` with ok/msg |
| `kuma_resume_maintenance` | `maintenance_id: int` | `dict` with ok/msg |

## Monitor Types

Supported values for `type` parameter: `http`, `ping`, `port`, `dns`, `keyword`, `docker`, `push`, `mqtt`, `group`, `mysql`, `postgres`, `redis`, `mongodb`

## Maintenance Strategies

Supported values for `strategy` parameter: `manual`, `single`, `recurring-interval`, `recurring-weekday`, `recurring-day-of-month`, `cron`

## Files to Modify

### Server code (clr-uptime-kuma-mcp/)

1. `pyproject.toml` - Add `uptime-kuma-api` dependency
2. `src/.../config.py` - Add username/password fields + credential loading
3. `src/.../kuma_client.py` - Add `KumaWriteClient` class
4. `src/.../server.py` - Add 10 new tools, initialize write client
5. `credentials.json.example` - Add username/password
6. `README.md` - Update docs
7. `TODO.md` - Mark items done

### Marketplace (clearminds-dev/)

8. `plugins/uptime-kuma/.mcp.json` - Add UPTIME_KUMA_USERNAME/PASSWORD env vars
9. `plugins/uptime-kuma/skills/uptime-kuma/SKILL.md` - New tools, credential examples

## Error Handling

- Write tools check for username/password, raise `ValueError("Write operations require UPTIME_KUMA_USERNAME and UPTIME_KUMA_PASSWORD")`
- Socket.IO connection errors surface as descriptive tool errors
- Each write tool creates a fresh connection (connect, operate, disconnect) for simplicity
