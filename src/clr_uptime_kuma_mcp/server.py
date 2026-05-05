"""Uptime Kuma MCP Server — FastMCP tools for Uptime Kuma monitoring."""

import argparse
import logging
import sys
from typing import Any

from fastmcp import FastMCP

from clr_uptime_kuma_mcp.config import Settings, configure_logging
from clr_uptime_kuma_mcp.middleware import ToolValidationMiddleware
from clr_uptime_kuma_mcp.kuma_client import (
    MAINTENANCE_STRATEGY_MAP,
    MONITOR_TYPE_MAP,
    KumaClient,
    KumaWriteClient,
)


def parse_cli_args() -> tuple[dict[str, Any], bool | None]:
    """Parse CLI arguments for configuration overrides.

    Returns:
        A tuple of (overlay dict, read_only flag).
    """
    parser = argparse.ArgumentParser(description="Uptime Kuma MCP Server")

    parser.add_argument("--uptime-kuma-url", type=str, help="Uptime Kuma URL")
    parser.add_argument("--uptime-kuma-token", type=str, help="Uptime Kuma API token")
    parser.add_argument(
        "--transport", type=str, choices=["stdio", "http"], help="MCP transport"
    )
    parser.add_argument("--host", type=str, help="HTTP host")
    parser.add_argument("--port", type=int, help="HTTP port")
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Log level",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        default=None,
        help="Run in read-only mode (hide write tools)",
    )

    args = parser.parse_args()

    overlay: dict[str, Any] = {}
    for key in [
        "uptime_kuma_url",
        "uptime_kuma_token",
        "transport",
        "host",
        "port",
        "log_level",
    ]:
        val = getattr(args, key, None)
        if val is not None:
            overlay[key] = val

    return overlay, args.read_only


mcp = FastMCP("Uptime Kuma")
mcp.add_middleware(ToolValidationMiddleware())

# Imported here (not at the top) on purpose: annotations.py needs ``mcp`` from
# this module, so importing it before the ``mcp = FastMCP(...)`` line above
# would be a circular import. Do not move.
from clr_uptime_kuma_mcp.annotations import (  # noqa: E402
    destructive_tool,
    read_tool,
    remove_non_read_tools,
    write_tool,
)

client: KumaClient | None = None
write_client: KumaWriteClient | None = None


def _require_write_client() -> KumaWriteClient:
    """Return the write client or raise if not configured.

    Returns:
        The initialized KumaWriteClient instance.

    Raises:
        ValueError: If write credentials were not configured at startup.
    """
    if write_client is None:
        raise ValueError(
            "Write operations require username/password. "
            "Set UPTIME_KUMA_USERNAME/UPTIME_KUMA_PASSWORD or add to credentials.json"
        )
    return write_client


# ---------------------------------------------------------------------------
# Status Overview
# ---------------------------------------------------------------------------


@read_tool
def kuma_status() -> dict[str, Any]:
    """Get overall monitoring status summary.

    Returns total monitor count and breakdown by status (up, down, pending,
    maintenance), plus a list of any monitors that are currently down.

    Returns:
        A dict with total, up, down, pending, maintenance counts and a
        down_monitors list.
    """
    monitors = client.get_monitors()

    up = sum(1 for m in monitors if m.get("status") == 1)
    down = sum(1 for m in monitors if m.get("status") == 0)
    pending = sum(1 for m in monitors if m.get("status") == 2)
    maintenance = sum(1 for m in monitors if m.get("status") == 3)

    down_monitors = [
        {"id": m["id"], "name": m["name"], "type": m["type"], "url": m.get("url", "")}
        for m in monitors
        if m.get("status") == 0
    ]

    return {
        "total": len(monitors),
        "up": up,
        "down": down,
        "pending": pending,
        "maintenance": maintenance,
        "down_monitors": down_monitors,
    }


# ---------------------------------------------------------------------------
# List / Get Monitors
# ---------------------------------------------------------------------------


@read_tool
def kuma_list_monitors() -> list[dict[str, Any]]:
    """List all Uptime Kuma monitors with status and response times.

    Returns:
        Monitors sorted by name, each with id, name, type, status,
        response time (ms), URL/hostname, and certificate info if available.
    """
    monitors = client.get_monitors()
    monitors.sort(key=lambda m: m.get("name", "").lower())
    return monitors


@read_tool
def kuma_get_monitor(monitor_id: int) -> dict[str, Any]:
    """Get detailed information for a specific monitor.

    Args:
        monitor_id: Numeric monitor ID.

    Returns:
        A dict with all available fields for the monitor.

    Raises:
        ValueError: If the monitor ID is not found.
    """
    monitor = client.get_monitor(monitor_id)
    if not monitor:
        raise ValueError(f"Monitor {monitor_id} not found")
    return monitor


# ---------------------------------------------------------------------------
# Down Monitors
# ---------------------------------------------------------------------------


@read_tool
def kuma_down_monitors() -> list[dict[str, Any]]:
    """List only monitors that are currently down.

    Returns:
        A list of monitor dicts with status 0, or an empty list if all are up.
    """
    monitors = client.get_monitors()
    return [m for m in monitors if m.get("status") == 0]


# ---------------------------------------------------------------------------
# Certificate Expiry
# ---------------------------------------------------------------------------


@read_tool
def kuma_cert_expiry() -> list[dict[str, Any]]:
    """Show SSL certificate expiry for all HTTPS monitors.

    Returns:
        Monitors with certificate data, sorted by days remaining (most urgent
        first). Each entry includes cert_days_remaining, cert_valid, and a
        severity level (CRITICAL <= 7 days, WARNING <= 30 days, OK otherwise).
    """
    monitors = client.get_monitors()
    with_certs = [m for m in monitors if "cert_days_remaining" in m]
    with_certs.sort(key=lambda m: m.get("cert_days_remaining", 999))

    for m in with_certs:
        days = m.get("cert_days_remaining", 999)
        valid = m.get("cert_valid", True)
        if not valid or days <= 7:
            m["severity"] = "CRITICAL"
        elif days <= 30:
            m["severity"] = "WARNING"
        else:
            m["severity"] = "OK"

    return with_certs


# ---------------------------------------------------------------------------
# Monitor Management (write)
# ---------------------------------------------------------------------------


@write_tool
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

    Returns:
        API response dict with the created monitor details.

    Raises:
        ValueError: If the monitor type is unknown or write client is unavailable.
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


@write_tool
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

    Returns:
        API response dict with the updated monitor details.

    Raises:
        ValueError: If no fields are provided or write client is unavailable.
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


@destructive_tool
def kuma_delete_monitor(monitor_id: int) -> dict[str, Any]:
    """Delete a monitor.

    Args:
        monitor_id: ID of the monitor to delete.

    Returns:
        API response dict confirming deletion.
    """
    wc = _require_write_client()
    return wc.delete_monitor(monitor_id)


# ---------------------------------------------------------------------------
# Pause / Resume
# ---------------------------------------------------------------------------


@write_tool
def kuma_pause_monitor(monitor_id: int) -> dict[str, Any]:
    """Pause a monitor (stop checking).

    Args:
        monitor_id: ID of the monitor to pause.

    Returns:
        API response dict confirming the pause.
    """
    wc = _require_write_client()
    return wc.pause_monitor(monitor_id)


@write_tool
def kuma_resume_monitor(monitor_id: int) -> dict[str, Any]:
    """Resume a paused monitor.

    Args:
        monitor_id: ID of the monitor to resume.

    Returns:
        API response dict confirming the resume.
    """
    wc = _require_write_client()
    return wc.resume_monitor(monitor_id)


# ---------------------------------------------------------------------------
# Maintenance Windows
# ---------------------------------------------------------------------------


@read_tool
def kuma_list_maintenances() -> list[dict[str, Any]]:
    """List all maintenance windows.

    Returns:
        A list of maintenance window dicts.
    """
    wc = _require_write_client()
    return wc.get_maintenances()


@write_tool
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
        date_range: For 'single' strategy: 'YYYY-MM-DD HH:MM,YYYY-MM-DD HH:MM'.
        duration_minutes: Duration in minutes for cron strategy (default 60).
        cron: Cron expression for 'cron' strategy.
        timezone: Timezone (e.g. 'Europe/Stockholm').

    Returns:
        API response dict with the created maintenance details.

    Raises:
        ValueError: If the strategy is unknown or write client is unavailable.
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


@destructive_tool
def kuma_delete_maintenance(maintenance_id: int) -> dict[str, Any]:
    """Delete a maintenance window.

    Args:
        maintenance_id: ID of the maintenance window to delete.

    Returns:
        API response dict confirming deletion.
    """
    wc = _require_write_client()
    return wc.delete_maintenance(maintenance_id)


@write_tool
def kuma_pause_maintenance(maintenance_id: int) -> dict[str, Any]:
    """Pause a maintenance window.

    Args:
        maintenance_id: ID of the maintenance window to pause.

    Returns:
        API response dict confirming the pause.
    """
    wc = _require_write_client()
    return wc.pause_maintenance(maintenance_id)


@write_tool
def kuma_resume_maintenance(maintenance_id: int) -> dict[str, Any]:
    """Resume a paused maintenance window.

    Args:
        maintenance_id: ID of the maintenance window to resume.

    Returns:
        API response dict confirming the resume.
    """
    wc = _require_write_client()
    return wc.resume_maintenance(maintenance_id)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def init_composite() -> FastMCP:
    """Initialize for composite mounting. Returns the FastMCP instance."""
    global client, write_client

    settings = Settings()
    creds = settings.load_credentials()

    client = KumaClient(
        url=creds.get("url", ""),
        token=creds.get("token", ""),
    )

    if creds.get("username") and creds.get("password"):
        write_client = KumaWriteClient(
            url=creds["url"],
            username=creds["username"],
            password=creds["password"],
        )

    if settings.kuma_read_only and WRITE_TOOLS:
        for name in WRITE_TOOLS:
            mcp.remove_tool(name)

    return mcp


def main() -> None:
    """Main entry point for the Uptime Kuma MCP server."""
    global client, write_client

    cli_overlay, cli_read_only = parse_cli_args()

    try:
        settings = Settings(**cli_overlay)
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    creds = settings.load_credentials()

    logger.info("Starting Uptime Kuma MCP Server")
    logger.info("Config: url=%s transport=%s", creds.get("url", ""), settings.transport)

    try:
        client = KumaClient(
            url=creds.get("url", ""),
            token=creds.get("token", ""),
        )
        logger.debug("Read client initialized (Prometheus metrics)")
    except Exception as e:
        logger.error("Failed to initialize read client: %s", e)
        sys.exit(1)

    if creds.get("username") and creds.get("password"):
        write_client = KumaWriteClient(
            url=creds["url"],
            username=creds["username"],
            password=creds["password"],
        )
        logger.info("Write client initialized (Socket.IO)")
    else:
        logger.info("Write client not initialized (no username/password)")

    read_only = cli_read_only if cli_read_only is not None else settings.kuma_read_only
    if read_only:
        removed = remove_non_read_tools(mcp)
        logger.info("Read-only mode: %d non-read tools removed", removed)

    try:
        if settings.transport == "stdio":
            logger.info("Starting stdio transport")
            mcp.run(transport="stdio")
        elif settings.transport == "http":
            logger.info(
                "Starting HTTP transport on %s:%s", settings.host, settings.port
            )
            mcp.run(transport="http", host=settings.host, port=settings.port)
    except Exception as e:
        logger.error("Failed to start MCP server: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
