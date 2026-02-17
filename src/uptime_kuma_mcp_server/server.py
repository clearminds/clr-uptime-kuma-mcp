"""Uptime Kuma MCP Server — FastMCP tools for Uptime Kuma monitoring."""

import argparse
import logging
import sys
from typing import Any

from fastmcp import FastMCP

from uptime_kuma_mcp_server.config import Settings, configure_logging
from uptime_kuma_mcp_server.kuma_client import KumaClient


def parse_cli_args() -> dict[str, Any]:
    """Parse CLI arguments for configuration overrides."""
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

    return overlay


mcp = FastMCP("Uptime Kuma")
client: KumaClient | None = None


# ---------------------------------------------------------------------------
# Status Overview
# ---------------------------------------------------------------------------


@mcp.tool
def kuma_status() -> dict[str, Any]:
    """Get overall monitoring status summary.

    Returns total monitor count and breakdown by status (up, down, pending,
    maintenance), plus a list of any monitors that are currently down.
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


@mcp.tool
def kuma_list_monitors() -> list[dict[str, Any]]:
    """List all Uptime Kuma monitors with status and response times.

    Returns monitors sorted by name, each with id, name, type, status,
    response time (ms), URL/hostname, and certificate info if available.
    """
    monitors = client.get_monitors()
    monitors.sort(key=lambda m: m.get("name", "").lower())
    return monitors


@mcp.tool
def kuma_get_monitor(monitor_id: int) -> dict[str, Any]:
    """Get detailed information for a specific monitor.

    Args:
        monitor_id: Numeric monitor ID.

    Returns all available fields for the monitor.
    """
    monitor = client.get_monitor(monitor_id)
    if not monitor:
        raise ValueError(f"Monitor {monitor_id} not found")
    return monitor


# ---------------------------------------------------------------------------
# Down Monitors
# ---------------------------------------------------------------------------


@mcp.tool
def kuma_down_monitors() -> list[dict[str, Any]]:
    """List only monitors that are currently down.

    Returns an empty list if everything is up.
    """
    monitors = client.get_monitors()
    return [m for m in monitors if m.get("status") == 0]


# ---------------------------------------------------------------------------
# Certificate Expiry
# ---------------------------------------------------------------------------


@mcp.tool
def kuma_cert_expiry() -> list[dict[str, Any]]:
    """Show SSL certificate expiry for all HTTPS monitors.

    Returns monitors that have certificate data, sorted by days remaining
    (most urgent first). Each entry includes cert_days_remaining, cert_valid,
    and a severity level (CRITICAL <= 7 days, WARNING <= 30 days, OK otherwise).
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
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Main entry point for the Uptime Kuma MCP server."""
    global client

    cli_overlay = parse_cli_args()

    try:
        settings = Settings(**cli_overlay)
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    logger.info("Starting Uptime Kuma MCP Server")
    logger.info(
        "Config: url=%s transport=%s", settings.uptime_kuma_url, settings.transport
    )

    try:
        client = KumaClient(
            url=settings.uptime_kuma_url,
            token=settings.uptime_kuma_token,
        )
        logger.debug("Kuma client initialized")
    except Exception as e:
        logger.error("Failed to initialize Kuma client: %s", e)
        sys.exit(1)

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
