# Uptime Kuma Write Operations Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add monitor CRUD, pause/resume, and maintenance window management to the Uptime Kuma MCP server.

**Architecture:** Hybrid client — keep existing `KumaClient` (Prometheus metrics + API token) for reads, add `KumaWriteClient` wrapping `uptime-kuma-api` (Socket.IO + username/password) for writes. Write client creates a fresh connection per operation.

**Tech Stack:** Python 3.11+, FastMCP, uptime-kuma-api, httpx, pydantic-settings

---

### Task 1: Add uptime-kuma-api dependency

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add dependency**

In `pyproject.toml`, add `uptime-kuma-api` to the dependencies list:

```toml
dependencies = [
    "httpx>=0.28.1",
    "fastmcp>=2.14.0,<3",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "uptime-kuma-api>=1.2.0",
]
```

Also update the description from "A read-only MCP server" to "An MCP server":

```toml
description = "An MCP server for Uptime Kuma"
```

And bump version to `1.1.0`.

**Step 2: Install dependencies**

Run: `cd /home/daniel/mcp-work/clr-uptime-kuma-mcp && uv sync`

Expected: Dependencies install successfully, `uv.lock` updated.

**Step 3: Verify import works**

Run: `cd /home/daniel/mcp-work/clr-uptime-kuma-mcp && uv run python -c "from uptime_kuma_api import UptimeKumaApi; print('OK')"`

Expected: `OK`

**Step 4: Commit**

```bash
cd /home/daniel/mcp-work/clr-uptime-kuma-mcp
git add pyproject.toml uv.lock
git commit -m "Add uptime-kuma-api dependency for write operations"
```

---

### Task 2: Add username/password to config

**Files:**
- Modify: `src/clr_uptime_kuma_mcp/config.py`

**Step 1: Add fields to Settings class**

Add these two fields after `uptime_kuma_token`:

```python
    uptime_kuma_username: str = ""
    uptime_kuma_password: str = ""
```

**Step 2: Update load_credentials to handle username/password**

The `load_credentials()` method currently loads `url` and `token`. Add `username` and `password` in the same pattern (env vars base, config file overrides):

In the env vars section, add:
```python
        if self.uptime_kuma_username:
            creds["username"] = self.uptime_kuma_username
        if self.uptime_kuma_password:
            creds["password"] = self.uptime_kuma_password
```

In the config file section, add:
```python
                if "username" in file_creds:
                    creds["username"] = file_creds["username"]
                if "password" in file_creds:
                    creds["password"] = file_creds["password"]
```

Keep the existing warning check for url+token (read ops). Add a separate info log if username/password are missing (write ops won't work but that's OK):

```python
        if not (creds.get("username") and creds.get("password")):
            logger.info(
                "No username/password configured — write operations will be unavailable. "
                "Set UPTIME_KUMA_USERNAME/UPTIME_KUMA_PASSWORD env vars or add to %s",
                CREDS_PATH,
            )
```

**Step 3: Commit**

```bash
cd /home/daniel/mcp-work/clr-uptime-kuma-mcp
git add src/clr_uptime_kuma_mcp/config.py
git commit -m "Add username/password credential support for write operations"
```

---

### Task 3: Add KumaWriteClient

**Files:**
- Modify: `src/clr_uptime_kuma_mcp/kuma_client.py`

**Step 1: Add KumaWriteClient class**

Add this class at the bottom of `kuma_client.py`, after the existing `KumaClient` class:

```python
from contextlib import contextmanager
from uptime_kuma_api import UptimeKumaApi, MonitorType, MaintenanceStrategy


MONITOR_TYPE_MAP = {
    "http": MonitorType.HTTP,
    "ping": MonitorType.PING,
    "port": MonitorType.PORT,
    "dns": MonitorType.DNS,
    "keyword": MonitorType.KEYWORD,
    "docker": MonitorType.DOCKER,
    "push": MonitorType.PUSH,
    "mqtt": MonitorType.MQTT,
    "group": MonitorType.GROUP,
    "mysql": MonitorType.MYSQL,
    "postgres": MonitorType.POSTGRES,
    "redis": MonitorType.REDIS,
    "mongodb": MonitorType.MONGODB,
}

MAINTENANCE_STRATEGY_MAP = {
    "manual": MaintenanceStrategy.MANUAL,
    "single": MaintenanceStrategy.SINGLE,
    "recurring-interval": MaintenanceStrategy.RECURRING_INTERVAL,
    "recurring-weekday": MaintenanceStrategy.RECURRING_WEEKDAY,
    "recurring-day-of-month": MaintenanceStrategy.RECURRING_DAY_OF_MONTH,
    "cron": MaintenanceStrategy.CRON,
}


class KumaWriteClient:
    """Uptime Kuma write client via Socket.IO (uptime-kuma-api)."""

    def __init__(self, url: str, username: str, password: str) -> None:
        self.url = url.rstrip("/")
        self.username = username
        self.password = password

    @contextmanager
    def _connect(self):
        """Create a fresh API connection, yield it, then disconnect."""
        api = UptimeKumaApi(self.url)
        try:
            api.login(self.username, self.password)
            yield api
        finally:
            api.disconnect()

    # -- Monitor CRUD --

    def add_monitor(self, **kwargs) -> dict[str, Any]:
        """Add a new monitor. Returns dict with monitorID."""
        with self._connect() as api:
            return api.add_monitor(**kwargs)

    def edit_monitor(self, monitor_id: int, **kwargs) -> dict[str, Any]:
        """Edit an existing monitor."""
        with self._connect() as api:
            return api.edit_monitor(monitor_id, **kwargs)

    def delete_monitor(self, monitor_id: int) -> dict[str, Any]:
        """Delete a monitor."""
        with self._connect() as api:
            return api.delete_monitor(monitor_id)

    def pause_monitor(self, monitor_id: int) -> dict[str, Any]:
        """Pause a monitor."""
        with self._connect() as api:
            return api.pause_monitor(monitor_id)

    def resume_monitor(self, monitor_id: int) -> dict[str, Any]:
        """Resume a paused monitor."""
        with self._connect() as api:
            return api.resume_monitor(monitor_id)

    # -- Maintenance --

    def get_maintenances(self) -> list[dict[str, Any]]:
        """List all maintenance windows."""
        with self._connect() as api:
            return api.get_maintenances()

    def add_maintenance(self, **kwargs) -> dict[str, Any]:
        """Add a maintenance window. Returns dict with maintenanceID."""
        with self._connect() as api:
            return api.add_maintenance(**kwargs)

    def delete_maintenance(self, maintenance_id: int) -> dict[str, Any]:
        """Delete a maintenance window."""
        with self._connect() as api:
            return api.delete_maintenance(maintenance_id)

    def pause_maintenance(self, maintenance_id: int) -> dict[str, Any]:
        """Pause a maintenance window."""
        with self._connect() as api:
            return api.pause_maintenance(maintenance_id)

    def resume_maintenance(self, maintenance_id: int) -> dict[str, Any]:
        """Resume a maintenance window."""
        with self._connect() as api:
            return api.resume_maintenance(maintenance_id)
```

**Step 2: Verify import**

Run: `cd /home/daniel/mcp-work/clr-uptime-kuma-mcp && uv run python -c "from clr_uptime_kuma_mcp.kuma_client import KumaWriteClient; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
cd /home/daniel/mcp-work/clr-uptime-kuma-mcp
git add src/clr_uptime_kuma_mcp/kuma_client.py
git commit -m "Add KumaWriteClient wrapping uptime-kuma-api"
```

---

### Task 4: Add write tools to server.py

**Files:**
- Modify: `src/clr_uptime_kuma_mcp/server.py`

**Step 1: Add import and global**

At top of server.py, update the import line:

```python
from clr_uptime_kuma_mcp.kuma_client import KumaClient, KumaWriteClient, MONITOR_TYPE_MAP, MAINTENANCE_STRATEGY_MAP
```

Add a second global after `client`:

```python
write_client: KumaWriteClient | None = None
```

Add a helper function after the globals:

```python
def _require_write_client() -> KumaWriteClient:
    """Return the write client or raise if not configured."""
    if write_client is None:
        raise ValueError(
            "Write operations require username/password. "
            "Set UPTIME_KUMA_USERNAME/UPTIME_KUMA_PASSWORD or add to credentials.json"
        )
    return write_client
```

**Step 2: Add monitor management tools**

Add after the cert_expiry tool section:

```python
# ---------------------------------------------------------------------------
# Monitor Management (write)
# ---------------------------------------------------------------------------


@mcp.tool
def kuma_add_monitor(
    name: str,
    type: str = "http",
    url: str = "",
    hostname: str = "",
    port: int = 0,
    interval: int = 60,
    keyword: str = "",
) -> dict[str, Any]:
    """Add a new monitor.

    Args:
        name: Display name for the monitor.
        type: Monitor type (http, ping, port, dns, keyword, docker, push, mqtt, group, mysql, postgres, redis, mongodb).
        url: URL to monitor (for http/keyword types).
        hostname: Hostname to monitor (for ping/port/dns types).
        port: Port number (for port type).
        interval: Check interval in seconds (default 60).
        keyword: Keyword to search for (for keyword type).
    """
    wc = _require_write_client()
    monitor_type = MONITOR_TYPE_MAP.get(type.lower())
    if monitor_type is None:
        raise ValueError(f"Unknown monitor type '{type}'. Valid: {', '.join(MONITOR_TYPE_MAP)}")

    kwargs: dict[str, Any] = {"type": monitor_type, "name": name, "interval": interval}
    if url:
        kwargs["url"] = url
    if hostname:
        kwargs["hostname"] = hostname
    if port:
        kwargs["port"] = port
    if keyword:
        kwargs["keyword"] = keyword

    return wc.add_monitor(**kwargs)


@mcp.tool
def kuma_edit_monitor(
    monitor_id: int,
    name: str = "",
    url: str = "",
    hostname: str = "",
    port: int = 0,
    interval: int = 0,
    keyword: str = "",
) -> dict[str, Any]:
    """Edit an existing monitor. Only provided fields are updated.

    Args:
        monitor_id: ID of the monitor to edit.
        name: New display name.
        url: New URL.
        hostname: New hostname.
        port: New port.
        interval: New check interval in seconds.
        keyword: New keyword.
    """
    wc = _require_write_client()
    kwargs: dict[str, Any] = {}
    if name:
        kwargs["name"] = name
    if url:
        kwargs["url"] = url
    if hostname:
        kwargs["hostname"] = hostname
    if port:
        kwargs["port"] = port
    if interval:
        kwargs["interval"] = interval
    if keyword:
        kwargs["keyword"] = keyword

    if not kwargs:
        raise ValueError("No fields to update")

    return wc.edit_monitor(monitor_id, **kwargs)


@mcp.tool
def kuma_delete_monitor(monitor_id: int) -> dict[str, Any]:
    """Delete a monitor.

    Args:
        monitor_id: ID of the monitor to delete.
    """
    wc = _require_write_client()
    return wc.delete_monitor(monitor_id)
```

**Step 3: Add pause/resume tools**

```python
# ---------------------------------------------------------------------------
# Pause / Resume
# ---------------------------------------------------------------------------


@mcp.tool
def kuma_pause_monitor(monitor_id: int) -> dict[str, Any]:
    """Pause a monitor (stop checking).

    Args:
        monitor_id: ID of the monitor to pause.
    """
    wc = _require_write_client()
    return wc.pause_monitor(monitor_id)


@mcp.tool
def kuma_resume_monitor(monitor_id: int) -> dict[str, Any]:
    """Resume a paused monitor.

    Args:
        monitor_id: ID of the monitor to resume.
    """
    wc = _require_write_client()
    return wc.resume_monitor(monitor_id)
```

**Step 4: Add maintenance tools**

```python
# ---------------------------------------------------------------------------
# Maintenance Windows
# ---------------------------------------------------------------------------


@mcp.tool
def kuma_list_maintenances() -> list[dict[str, Any]]:
    """List all maintenance windows."""
    wc = _require_write_client()
    return wc.get_maintenances()


@mcp.tool
def kuma_add_maintenance(
    title: str,
    strategy: str = "manual",
    description: str = "",
    date_range: str = "",
    duration_minutes: int = 60,
    cron: str = "",
    timezone: str = "",
) -> dict[str, Any]:
    """Add a maintenance window.

    Args:
        title: Maintenance window title.
        strategy: Strategy type (manual, single, recurring-interval, recurring-weekday, recurring-day-of-month, cron).
        description: Optional description.
        date_range: For 'single' strategy: start and end as 'YYYY-MM-DD HH:MM,YYYY-MM-DD HH:MM'.
        duration_minutes: Duration in minutes for cron strategy (default 60).
        cron: Cron expression for 'cron' strategy.
        timezone: Timezone (e.g. 'Europe/Stockholm').
    """
    wc = _require_write_client()
    maint_strategy = MAINTENANCE_STRATEGY_MAP.get(strategy.lower())
    if maint_strategy is None:
        raise ValueError(f"Unknown strategy '{strategy}'. Valid: {', '.join(MAINTENANCE_STRATEGY_MAP)}")

    kwargs: dict[str, Any] = {
        "title": title,
        "strategy": maint_strategy,
        "description": description,
    }
    if date_range:
        parts = [p.strip() for p in date_range.split(",")]
        if len(parts) == 2:
            kwargs["dateRange"] = parts
    if duration_minutes != 60:
        kwargs["durationMinutes"] = duration_minutes
    if cron:
        kwargs["cron"] = cron
    if timezone:
        kwargs["timezoneOption"] = timezone

    return wc.add_maintenance(**kwargs)


@mcp.tool
def kuma_delete_maintenance(maintenance_id: int) -> dict[str, Any]:
    """Delete a maintenance window.

    Args:
        maintenance_id: ID of the maintenance window to delete.
    """
    wc = _require_write_client()
    return wc.delete_maintenance(maintenance_id)


@mcp.tool
def kuma_pause_maintenance(maintenance_id: int) -> dict[str, Any]:
    """Pause a maintenance window.

    Args:
        maintenance_id: ID of the maintenance window to pause.
    """
    wc = _require_write_client()
    return wc.pause_maintenance(maintenance_id)


@mcp.tool
def kuma_resume_maintenance(maintenance_id: int) -> dict[str, Any]:
    """Resume a paused maintenance window.

    Args:
        maintenance_id: ID of the maintenance window to resume.
    """
    wc = _require_write_client()
    return wc.resume_maintenance(maintenance_id)
```

**Step 5: Update main() to initialize write client**

In the `main()` function, after the existing `KumaClient` initialization block, add:

```python
    # Initialize write client (optional — needs username/password)
    if creds.get("username") and creds.get("password"):
        try:
            write_client = KumaWriteClient(
                url=creds["url"],
                username=creds["username"],
                password=creds["password"],
            )
            logger.info("Write client initialized (username/password auth)")
        except Exception as e:
            logger.warning("Failed to initialize write client: %s", e)
    else:
        logger.info("Write client not initialized (no username/password)")
```

Also add `write_client` to the `global` declaration at the top of `main()`:
```python
    global client, write_client
```

**Step 6: Verify server starts**

Run: `cd /home/daniel/mcp-work/clr-uptime-kuma-mcp && uv run python -c "from clr_uptime_kuma_mcp.server import mcp; print(f'{len(mcp._tool_manager._tools)} tools registered')"`

Expected: `15 tools registered` (5 existing + 10 new)

**Step 7: Commit**

```bash
cd /home/daniel/mcp-work/clr-uptime-kuma-mcp
git add src/clr_uptime_kuma_mcp/server.py
git commit -m "Add 10 write operation tools (monitor CRUD, pause/resume, maintenance)"
```

---

### Task 5: Update credentials example and docs

**Files:**
- Modify: `credentials.json.example`
- Modify: `TODO.md`

**Step 1: Update credentials.json.example**

Replace contents with:

```json
{
  "url": "https://uptime.example.com",
  "token": "your-api-token",
  "username": "admin",
  "password": "your-password"
}
```

**Step 2: Update TODO.md**

Replace contents with:

```markdown
# TODO

## Completed

- [x] Add monitor (create new monitors)
- [x] Delete monitor
- [x] Pause/resume monitor support
- [x] Maintenance window support

## Future

- [ ] Edit maintenance window
- [ ] Add monitors to maintenance window
- [ ] Heartbeat history
- [ ] Notification management
- [ ] Status page management
- [ ] Tag management
```

**Step 3: Commit**

```bash
cd /home/daniel/mcp-work/clr-uptime-kuma-mcp
git add credentials.json.example TODO.md
git commit -m "Update credentials example and TODO"
```

---

### Task 6: Update marketplace .mcp.json

**Files:**
- Modify: `/home/daniel/mcp-work/marketplace/plugins/uptime-kuma/.mcp.json`

**Step 1: Add username/password env vars**

Replace contents with:

```json
{
  "uptime-kuma": {
    "command": "uvx",
    "args": ["--from", "git+ssh://git@github.com/clearminds/clr-uptime-kuma-mcp.git", "clr-uptime-kuma-mcp"],
    "env": {
      "UPTIME_KUMA_URL": "${UPTIME_KUMA_URL}",
      "UPTIME_KUMA_TOKEN": "${UPTIME_KUMA_TOKEN}",
      "UPTIME_KUMA_USERNAME": "${UPTIME_KUMA_USERNAME}",
      "UPTIME_KUMA_PASSWORD": "${UPTIME_KUMA_PASSWORD}"
    }
  }
}
```

**Note:** Also updated the git URL and command name from `uptime-kuma-mcp-server` to `clr-uptime-kuma-mcp` to match the renamed package.

**Step 2: Commit**

```bash
cd /home/daniel/mcp-work/marketplace
git add plugins/uptime-kuma/.mcp.json
git commit -m "Add username/password env vars for uptime-kuma write operations"
```

---

### Task 7: Update marketplace SKILL.md

**Files:**
- Modify: `/home/daniel/mcp-work/marketplace/plugins/uptime-kuma/skills/uptime-kuma/SKILL.md`

**Step 1: Update SKILL.md**

The full updated SKILL.md should:

1. Update the description to mention write operations (create/delete/pause/resume monitors, maintenance windows)
2. Update credential priority order (config file takes priority over env vars)
3. Add username/password to credential examples (both PRIVATE and PUBLIC blocks)
4. Add all 10 new tools to the tools table
5. Add new workflow examples
6. Update the Safety section (no longer read-only)

Key sections to update:

**Tools table** — add these rows:

```markdown
| `kuma_add_monitor` | Create a new monitor | `name`, `type`, `url`/`hostname`, `interval` |
| `kuma_edit_monitor` | Edit monitor settings | `monitor_id`, optional fields |
| `kuma_delete_monitor` | Delete a monitor | `monitor_id` |
| `kuma_pause_monitor` | Pause monitoring | `monitor_id` |
| `kuma_resume_monitor` | Resume monitoring | `monitor_id` |
| `kuma_list_maintenances` | List maintenance windows | — |
| `kuma_add_maintenance` | Create maintenance window | `title`, `strategy` |
| `kuma_delete_maintenance` | Delete maintenance window | `maintenance_id` |
| `kuma_pause_maintenance` | Pause maintenance window | `maintenance_id` |
| `kuma_resume_maintenance` | Resume maintenance window | `maintenance_id` |
```

**Credential examples** — add username/password:

PRIVATE block:
```json
{
  "url": "https://uptime.clearminds.se",
  "token": "your-api-token",
  "username": "admin",
  "password": "your-password"
}
```

PUBLIC block:
```json
{
  "url": "https://uptime.example.com",
  "token": "your-api-token",
  "username": "admin",
  "password": "your-password"
}
```

**Priority order** — update both PRIVATE and PUBLIC:
```
1. `~/.config/uptime-kuma/credentials.json` (primary) - best for daily local use
2. Environment variables (fallback/override) - for CI/CD, Docker, testing
```

**Safety section** — update:
```markdown
## Safety

- Read operations use Prometheus metrics endpoint (GET only, API key auth)
- Write operations use Socket.IO (username/password auth)
- Write tools require explicit username/password configuration
- Destructive actions (delete monitor/maintenance) execute immediately — no confirmation
```

**Step 2: Commit**

```bash
cd /home/daniel/mcp-work/marketplace
git add plugins/uptime-kuma/skills/uptime-kuma/SKILL.md
git commit -m "Update uptime-kuma skill with write operation tools and credential docs"
```

---

### Task 8: Final verification

**Step 1: Verify server imports cleanly**

Run: `cd /home/daniel/mcp-work/clr-uptime-kuma-mcp && uv run python -c "from clr_uptime_kuma_mcp.server import main; print('OK')"`

Expected: `OK`

**Step 2: Verify all tools are registered**

Run: `cd /home/daniel/mcp-work/clr-uptime-kuma-mcp && uv run python -c "
from clr_uptime_kuma_mcp.server import mcp
tools = list(mcp._tool_manager._tools.keys())
print(f'{len(tools)} tools:')
for t in sorted(tools):
    print(f'  {t}')
"`

Expected: 15 tools listed (5 read + 10 write).

**Step 3: Verify .mcp.json has no hardcoded values**

Run: Check that all env values use `${VAR}` pattern.

**Step 4: Update mcp-work submodule references**

```bash
cd /home/daniel/mcp-work
git add clr-uptime-kuma-mcp marketplace
git commit -m "Update uptime-kuma submodules after write operations feature"
```
