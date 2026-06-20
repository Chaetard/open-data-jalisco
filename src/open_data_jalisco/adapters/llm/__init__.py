# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from ...ports.llm import LLMClient
from ...shared.config import Settings, get_settings
from .openai_compat import OpenAICompatClient

# Default OpenAI-compatible endpoints per provider. "custom" isn't here on
# purpose: it means "I'll set LLM_API_BASE myself" (local server, other host).
_PROVIDER_BASES = {
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


def resolve_base_url(settings: Settings) -> str:
    """Endpoint to call: explicit LLM_API_BASE wins, else the provider preset."""
    if settings.llm_api_base.strip():
        return settings.llm_api_base.strip()
    return _PROVIDER_BASES.get(settings.llm_provider, "")


def _build(settings: Settings, model: str, temperature: float) -> OpenAICompatClient:
    return OpenAICompatClient(
        base_url=resolve_base_url(settings),
        api_key=settings.llm_api_key,
        model=model,
        timeout_seconds=settings.llm_timeout_seconds,
        temperature=temperature,
    )


def build_llm_client() -> LLMClient | None:
    """Build the main chat client, or ``None`` when unconfigured.

    ``None`` means the answering agent is disabled: POST /ask returns 503 and the
    rest of the API is unaffected. Needs a key and a resolvable endpoint (a
    "custom" provider with no LLM_API_BASE counts as unconfigured). No key in the
    repo, ever — it comes from ``LLM_API_KEY`` at runtime.
    """
    settings = get_settings()
    if not settings.llm_api_key or not resolve_base_url(settings):
        return None
    return _build(settings, settings.llm_model, settings.llm_temperature)


def build_router_client() -> LLMClient | None:
    """Build the cheap intent-router client, or ``None`` when not enabled.

    Same provider/key/endpoint as the main client, just a smaller model and
    temperature 0 (classification should be deterministic). Empty
    ``LLM_ROUTER_MODEL`` returns ``None`` → routing off, every question searches.
    """
    settings = get_settings()
    model = settings.llm_router_model.strip()
    if not model or not settings.llm_api_key or not resolve_base_url(settings):
        return None
    return _build(settings, model, 0.0)


__all__ = [
    "OpenAICompatClient",
    "build_llm_client",
    "build_router_client",
    "resolve_base_url",
]
