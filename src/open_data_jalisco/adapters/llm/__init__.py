# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from ...ports.llm import LLMClient
from ...shared.config import get_settings
from .openai_compat import OpenAICompatClient


def build_llm_client() -> LLMClient | None:
    """Build the chat client, or ``None`` when no API key is configured.

    ``None`` means the answering agent is disabled: POST /ask returns 503 and
    the rest of the API is unaffected. No key in the repo, ever — it comes from
    ``LLM_API_KEY`` at runtime.
    """
    settings = get_settings()
    if not settings.llm_api_key:
        return None
    return OpenAICompatClient(
        base_url=settings.llm_api_base,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        temperature=settings.llm_temperature,
    )


__all__ = ["OpenAICompatClient", "build_llm_client"]
