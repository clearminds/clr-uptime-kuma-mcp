"""Configuration management for Uptime Kuma MCP Server."""

import json
import logging
import logging.config
from pathlib import Path
from typing import Any, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

CREDS_PATH = Path.home() / ".config" / "uptime-kuma" / "credentials.json"


class Settings(BaseSettings):
    """Centralized configuration for Uptime Kuma MCP Server.

    Priority order for credentials:
    1. ~/.config/uptime-kuma/credentials.json
    2. Environment variables (UPTIME_KUMA_URL, UPTIME_KUMA_TOKEN) - override

    Attributes:
        uptime_kuma_url: Base URL of the Uptime Kuma instance.
        uptime_kuma_token: API token for Prometheus metrics authentication.
        uptime_kuma_username: Username for Socket.IO write operations.
        uptime_kuma_password: Password for Socket.IO write operations.
        transport: MCP transport protocol to use.
        host: Hostname to bind when using HTTP transport.
        port: Port to bind when using HTTP transport.
        log_level: Logging verbosity level.
    """

    uptime_kuma_url: str = ""
    uptime_kuma_token: str = ""
    uptime_kuma_username: str = ""
    uptime_kuma_password: str = ""
    kuma_read_only: bool = False

    transport: Literal["stdio", "http"] = "stdio"
    host: str = "127.0.0.1"
    port: int = 8000

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("uptime_kuma_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate and normalize the Uptime Kuma URL.

        Args:
            v: Raw URL string from configuration.

        Returns:
            The URL with trailing slashes stripped.

        Raises:
            ValueError: If the URL does not start with http:// or https://.
        """
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("UPTIME_KUMA_URL must start with http:// or https://")
        return v.rstrip("/") if v else v

    def load_credentials(self) -> dict[str, Any]:
        """Load credentials with config-file-first, env-override pattern.

        Returns:
            Dict with url and token.
        """
        creds: dict[str, Any] = {}

        # 1. FIRST: Load from environment variables (base/fallback)
        if self.uptime_kuma_url:
            creds["url"] = self.uptime_kuma_url
        if self.uptime_kuma_token:
            creds["token"] = self.uptime_kuma_token
        if self.uptime_kuma_username:
            creds["username"] = self.uptime_kuma_username
        if self.uptime_kuma_password:
            creds["password"] = self.uptime_kuma_password

        # 2. THEN: Override with credentials.json file (takes priority)
        if CREDS_PATH.exists():
            try:
                file_creds: dict[str, Any] = json.loads(CREDS_PATH.read_text())

                if "url" in file_creds:
                    creds["url"] = file_creds["url"]
                if "token" in file_creds:
                    creds["token"] = file_creds["token"]
                if "username" in file_creds:
                    creds["username"] = file_creds["username"]
                if "password" in file_creds:
                    creds["password"] = file_creds["password"]

                logger.info(f"Loaded Uptime Kuma credentials from {CREDS_PATH}")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load {CREDS_PATH}: {e}")

        if not (creds.get("url") and creds.get("token")):
            logger.warning(
                "No Uptime Kuma credentials configured. Set UPTIME_KUMA_URL/UPTIME_KUMA_TOKEN "
                f"env vars or create {CREDS_PATH}"
            )

        if not (creds.get("username") and creds.get("password")):
            logger.info(
                "No username/password configured — write operations will be unavailable. "
                "Set UPTIME_KUMA_USERNAME/UPTIME_KUMA_PASSWORD env vars or add to %s",
                CREDS_PATH,
            )

        return creds


def configure_logging(
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
) -> None:
    """Configure application-wide logging with a console handler on stderr.

    Args:
        log_level: Root logger verbosity level.
    """
    config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "console",
                "stream": "ext://sys.stderr",
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["console"],
        },
    }
    logging.config.dictConfig(config)
