# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""LLM chat port, modelled on the OpenAI Chat Completions shape.

That shape is the lingua franca of hosted and local models, so a single
adapter speaks to Gemini (via its OpenAI-compat endpoint), OpenAI, Groq, a
local server, etc. The deployer chooses the model — nothing here is
provider-specific.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class LLMError(RuntimeError):
    """Upstream LLM call failed (bad request, quota, network, timeout).

    Carries the provider's own message so callers can surface the real reason
    instead of a blank 500.
    """


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string as emitted by the model
    extra_content: dict[str, Any] | None = None  # provider-specific tool-call metadata


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str | None = None
    tool_calls: list[ToolCall] | None = None  # assistant requesting tools
    tool_call_id: str | None = None  # role="tool": which call this answers
    name: str | None = None  # role="tool": the tool's name


@dataclass
class ChatResult:
    content: str | None
    tool_calls: list[ToolCall]


class LLMClient(Protocol):
    @property
    def model(self) -> str: ...

    def chat(
        self, messages: list[ChatMessage], tools: list[dict[str, Any]] | None = None
    ) -> ChatResult:
        """One chat-completion turn. ``tools`` are JSON schemas (OpenAI format).

        Returns the assistant's text and/or the tool calls it wants run. The
        caller executes the tools and calls again with the results appended.
        """
        ...
