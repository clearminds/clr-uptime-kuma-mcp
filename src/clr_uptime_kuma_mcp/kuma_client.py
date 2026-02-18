"""Uptime Kuma client using the Prometheus metrics endpoint and Socket.IO API."""

import logging
import re
from collections import defaultdict
from contextlib import contextmanager
from typing import Any

import httpx
from uptime_kuma_api import MaintenanceStrategy, MonitorType, UptimeKumaApi

logger = logging.getLogger(__name__)

STATUS_NAMES = {0: "DOWN", 1: "UP", 2: "PENDING", 3: "MAINTENANCE"}


def parse_prometheus_metrics(text: str) -> dict[str, dict[str, Any]]:
    """Parse Prometheus metrics text into structured monitor data."""
    monitors: dict[str, dict[str, Any]] = defaultdict(dict)

    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue

        match = re.match(r"(\w+)\{([^}]+)\}\s+([\d.]+)", line)
        if not match:
            continue

        metric_name, labels_str, value = match.groups()

        labels = {}
        for label_match in re.finditer(r'(\w+)="([^"]*)"', labels_str):
            labels[label_match.group(1)] = label_match.group(2)

        monitor_id = labels.get("monitor_id")
        if not monitor_id:
            continue

        monitors[monitor_id]["id"] = int(monitor_id)
        monitors[monitor_id]["name"] = labels.get("monitor_name", "?")
        monitors[monitor_id]["type"] = labels.get("monitor_type", "?")
        monitors[monitor_id]["url"] = labels.get("monitor_url", "")
        monitors[monitor_id]["hostname"] = labels.get("monitor_hostname", "")
        monitors[monitor_id]["port"] = labels.get("monitor_port", "")

        if metric_name == "monitor_status":
            status_code = int(float(value))
            monitors[monitor_id]["status"] = status_code
            monitors[monitor_id]["status_name"] = STATUS_NAMES.get(
                status_code, "UNKNOWN"
            )
        elif metric_name == "monitor_response_time":
            monitors[monitor_id]["response_time_ms"] = float(value)
        elif metric_name == "monitor_cert_days_remaining":
            monitors[monitor_id]["cert_days_remaining"] = int(float(value))
        elif metric_name == "monitor_cert_is_valid":
            monitors[monitor_id]["cert_valid"] = int(float(value)) == 1

    return dict(monitors)


class KumaClient:
    """Uptime Kuma client via Prometheus metrics endpoint with API key auth."""

    def __init__(self, url: str, token: str) -> None:
        self.url = url.rstrip("/")
        self._client = httpx.Client(timeout=30.0, auth=("", token))

    def get_monitors(self) -> list[dict[str, Any]]:
        """Fetch all monitors from Prometheus metrics."""
        resp = self._client.get(f"{self.url}/metrics")
        resp.raise_for_status()
        metrics = parse_prometheus_metrics(resp.text)
        return list(metrics.values())

    def get_monitor(self, monitor_id: int) -> dict[str, Any] | None:
        """Get a specific monitor by ID."""
        resp = self._client.get(f"{self.url}/metrics")
        resp.raise_for_status()
        metrics = parse_prometheus_metrics(resp.text)
        return metrics.get(str(monitor_id))


MONITOR_TYPE_MAP: dict[str, MonitorType] = {
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

MAINTENANCE_STRATEGY_MAP: dict[str, MaintenanceStrategy] = {
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
        """Add a new monitor."""
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
        """Add a maintenance window."""
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
