"""
Application configuration via environment variables.

Uses pydantic-settings to load and validate all config from the
environment (or a `.env` file in the project root).
"""

from __future__ import annotations

import base64
import json
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration object – one instance shared app-wide."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────
    database_url: str

    # ── Google Drive ──────────────────────────────────────────────────
    google_service_account_base64: str

    # ── Admin auth ────────────────────────────────────────────────────
    admin_password: str

    # ── Face recognition ──────────────────────────────────────────────
    insightface_model: str = "buffalo_sc"
    similarity_threshold: float = 0.55

    # ── CORS ──────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # ── Indexing ──────────────────────────────────────────────────────
    indexing_concurrency: int = 3

    # ── Helpers ───────────────────────────────────────────────────────

    @field_validator("similarity_threshold")
    @classmethod
    def _clamp_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("similarity_threshold must be between 0.0 and 1.0")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        """Return CORS origins as a list of strings."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def get_service_account_info(self) -> dict[str, Any]:
        """Decode the base64-encoded service-account JSON."""
        raw = base64.b64decode(self.google_service_account_base64)
        return json.loads(raw)

    def write_service_account_file(self) -> Path:
        """Write service-account JSON to a temp file and return the path.

        Useful for libraries that require a file path rather than a dict.
        """
        info = self.get_service_account_info()
        tmp = Path(tempfile.gettempdir()) / "recall_sa.json"
        tmp.write_text(json.dumps(info))
        return tmp


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached, validated application settings."""
    return Settings()  # type: ignore[call-arg]
