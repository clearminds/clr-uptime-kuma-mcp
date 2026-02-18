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
    1. Environment variables (UPTIME_KUMA_URL, UPTIME_KUMA_TOKEN)
    2. ~/.config/uptime-kuma/credentials.json
    """

    uptime_kuma_url: str = ""
    uptime_kuma_token: str = ""

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
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("UPTIME_KUMA_URL must start with http:// or https://")
        return v.rstrip("/") if v else v

    def load_credentials(self) -> dict[str, Any]:
        """Load credentials with env-first, config-file-fallback pattern.

        Returns:
            Dict with url and token.
        """
        creds: dict[str, Any] = {}

        # 1. FIRST: Check environment variables
        if self.uptime_kuma_url:
            creds["url"] = self.uptime_kuma_url
        if self.uptime_kuma_token:
            creds["token"] = self.uptime_kuma_token

        # If we have all required creds from env, return early
        if creds.get("url") and creds.get("token"):
            logger.info("Using Uptime Kuma credentials from environment variables")
            return creds

        # 2. FALLBACK: Check credentials.json file
        if CREDS_PATH.exists():
            try:
                file_creds: dict[str, Any] = json.loads(CREDS_PATH.read_text())

                # Only use file values if NOT already set by env vars
                if "url" in file_creds and not creds.get("url"):
                    creds["url"] = file_creds["url"]
                if "token" in file_creds and not creds.get("token"):
                    creds["token"] = file_creds["token"]

                logger.info(f"Loaded Uptime Kuma credentials from {CREDS_PATH}")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load {CREDS_PATH}: {e}")

        if not (creds.get("url") and creds.get("token")):
            logger.warning(
                "No Uptime Kuma credentials configured. Set UPTIME_KUMA_URL/UPTIME_KUMA_TOKEN "
                f"env vars or create {CREDS_PATH}"
            )

        return creds


def configure_logging(
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
) -> None:
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
