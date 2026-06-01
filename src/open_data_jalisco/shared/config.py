# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["local", "dev", "staging", "prod"] = "local"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://odj:odj@localhost:5432/open_data_jalisco"
    raw_storage_path: Path = Path("./data/raw")
    manifests_dir: Path = Path("./datasets/manifests")

    embedding_provider: Literal["dummy"] = "dummy"
    embedding_model: str = "dummy-v1"
    embedding_dimension: int = 384

    scraper_user_agent: str = "open-data-jalisco/0.1"
    scraper_timeout_seconds: int = 30
    scraper_max_retries: int = 3
    scraper_retry_backoff_seconds: int = 2

    chunk_max_chars: int = 1800
    chunk_overlap_chars: int = 200
    chunk_min_chars: int = 120

    api_host: str = "0.0.0.0"
    api_port: int = 8000


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings_cache() -> None:
    global _settings
    _settings = None
