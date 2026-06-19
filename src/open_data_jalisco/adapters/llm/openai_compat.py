# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""OpenAI-compatible Chat Completions client over plain HTTP (httpx).

No vendor SDK: the request/response shape is stable across providers, so this
one adapter serves Gemini (OpenAI-compat endpoint), OpenAI, Groq, Together, a
local llama.cpp server, etc. Point ``base_url``/``model``/``api_key`` at
whatever the deployer wants.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from ...ports.llm import ChatMessage, ChatResult, LLMError, ToolCall
from ...shared.logging import get_logger

logger = get_logger(__name__)


class OpenAICompatClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 60,
        temperature: float = 0.2,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._temperature = temperature

    @property
    def model(self) -> str:
        return self._model

    def chat(
        self, messages: list[ChatMessage], tools: list[dict[str, Any]] | None = None
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [_message_to_wire(m) for m in messages],
            "temperature": self._temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        logger.info(
            "llm chat: model=%s msgs=%d tools=%s timeout=%ss",
            self._model,
            len(messages),
            bool(tools),
            self._timeout,
        )
        start = time.perf_counter()
        try:
            resp = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._timeout,
            )
        except httpx.RequestError as e:
            logger.warning(
                "llm chat failed (network) after %.1fs: %s", time.perf_counter() - start, e
            )
            raise LLMError(f"LLM request failed: {e}") from e
        elapsed = time.perf_counter() - start
        if resp.status_code >= 400:
            # Surface the provider's own message. raise_for_status() would hide
            # the body, but that body is exactly where Gemini/OpenAI explain the
            # real reason (bad field, quota, model name, ...).
            logger.warning("llm chat -> %d in %.1fs: %s", resp.status_code, elapsed, resp.text[:300])
            raise LLMError(f"LLM upstream {resp.status_code}: {resp.text[:1000]}")
        logger.info("llm chat -> %d in %.1fs", resp.status_code, elapsed)
        message = resp.json()["choices"][0]["message"]
        return _parse_message(message)


def _message_to_wire(m: ChatMessage) -> dict[str, Any]:
    out: dict[str, Any] = {"role": m.role}
    # Gemini's OpenAI-compat layer rejects content: null on an assistant turn
    # that carries tool_calls (OpenAI tolerates it) - a 400 that only fires when
    # the model calls the tool without any preamble text. Omit content when None.
    if m.content is not None:
        out["content"] = m.content
    if m.tool_calls:
        out["tool_calls"] = []
        for tc in m.tool_calls:
            call = {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": tc.arguments},
            }
            if tc.extra_content is not None:
                call["extra_content"] = tc.extra_content
            out["tool_calls"].append(call)
    if m.tool_call_id is not None:
        out["tool_call_id"] = m.tool_call_id
    if m.name is not None:
        out["name"] = m.name
    return out


def _parse_message(message: dict[str, Any]) -> ChatResult:
    raw_calls = message.get("tool_calls") or []
    tool_calls = [
        ToolCall(
            id=c.get("id", ""),
            name=c["function"]["name"],
            arguments=c["function"].get("arguments", "") or "",
            extra_content=c.get("extra_content"),
        )
        for c in raw_calls
        if c.get("type", "function") == "function"
    ]
    return ChatResult(content=message.get("content"), tool_calls=tool_calls)
