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

    embedding_provider: Literal["dummy", "local_st"] = "dummy"
    embedding_model: str = "dummy-v1"
    embedding_dimension: int = 384
    embedding_device: str = "cpu"

    # Optional cross-encoder reranking stage. "none" (default) skips it: no model
    # load, no latency, identical behaviour to before. "cross_encoder" reranks
    # the vector top-N before truncating to the requested limit.
    rerank_provider: Literal["none", "cross_encoder"] = "none"
    rerank_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    rerank_device: str = "cpu"
    # Candidates fetched (and reranked / jurisdiction-filtered) before slicing to
    # the requested limit. Larger = better recall before reranking, slower.
    rerank_pool: int = 50

    scraper_user_agent: str = "open-data-jalisco/0.1"
    scraper_timeout_seconds: int = 30
    scraper_max_retries: int = 3
    scraper_retry_backoff_seconds: int = 2

    chunk_max_chars: int = 1800
    chunk_overlap_chars: int = 200
    chunk_min_chars: int = 120

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    # Cuando la API se sirve detrás de un reverse proxy bajo un prefijo (Caddy
    # mapea /api/* -> aquí), pon ROOT_PATH=/api para que las URLs generadas de
    # docs/openapi lleven el prefijo. Vacío para acceso directo (dev en :8000).
    root_path: str = ""

    # Optional answering agent. Speaks the OpenAI Chat Completions API, so it
    # works with any OpenAI-compatible provider (Gemini via its compat endpoint,
    # OpenAI, Groq, a local server…) — the deployer picks the model. Empty
    # llm_api_key = agent disabled (POST /ask returns 503, nothing else changes).
    llm_api_base: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    llm_api_key: str = ""
    llm_model: str = "gemini-2.5-pro"
    llm_max_iters: int = 5
    llm_timeout_seconds: int = 60
    llm_temperature: float = 0.2
    # Comma-separated list of allowed Origins for CORS. Vite default is
    # http://localhost:5173, CRA default is http://localhost:3000. Override in
    # .env for prod (e.g. CORS_ORIGINS="https://odj.example.com").
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings_cache() -> None:
    global _settings
    _settings = None
