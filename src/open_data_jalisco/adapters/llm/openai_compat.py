# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""OpenAI-compatible Chat Completions client over plain HTTP (httpx).

No vendor SDK: the request/response shape is stable across providers, so this
one adapter serves Gemini (OpenAI-compat endpoint), OpenAI, Groq, Together, a
local llama.cpp server, etc. Point ``base_url``/``model``/``api_key`` at
whatever the deployer wants.
"""
from __future__ import annotations

from typing import Any

import httpx

from ...ports.llm import ChatMessage, ChatResult, ToolCall


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

        resp = httpx.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        message = resp.json()["choices"][0]["message"]
        return _parse_message(message)


def _message_to_wire(m: ChatMessage) -> dict[str, Any]:
    out: dict[str, Any] = {"role": m.role}
    # OpenAI requires "content" present even when null for assistant tool calls.
    out["content"] = m.content
    if m.tool_calls:
        out["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": tc.arguments},
            }
            for tc in m.tool_calls
        ]
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
        )
        for c in raw_calls
        if c.get("type", "function") == "function"
    ]
    return ChatResult(content=message.get("content"), tool_calls=tool_calls)
