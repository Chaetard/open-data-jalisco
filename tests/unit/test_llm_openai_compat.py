# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Wire serialization for the OpenAI-compatible client.

The key case is the regression that caused Gemini 400s: an assistant turn that
carries tool_calls but no text must NOT send content: null.
"""
from open_data_jalisco.adapters.llm.openai_compat import _message_to_wire, _parse_message
from open_data_jalisco.ports.llm import ChatMessage, ToolCall


def test_assistant_tool_call_omits_null_content() -> None:
    m = ChatMessage(
        role="assistant",
        content=None,
        tool_calls=[ToolCall(id="a", name="search_documents", arguments='{"query":"x"}')],
    )
    wire = _message_to_wire(m)
    assert "content" not in wire  # Gemini rejects content: null here
    assert wire["tool_calls"][0]["id"] == "a"
    assert wire["tool_calls"][0]["function"]["name"] == "search_documents"


def test_tool_result_keeps_content_and_call_id() -> None:
    m = ChatMessage(
        role="tool",
        content='{"results": []}',
        tool_call_id="a",
        name="search_documents",
    )
    wire = _message_to_wire(m)
    assert wire["content"] == '{"results": []}'
    assert wire["tool_call_id"] == "a"
    assert wire["name"] == "search_documents"


def test_plain_user_message_keeps_content() -> None:
    wire = _message_to_wire(ChatMessage(role="user", content="hola"))
    assert wire == {"role": "user", "content": "hola"}


def test_gemini_thought_signature_round_trips_on_tool_calls() -> None:
    result = _parse_message(
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "function-call-1",
                    "type": "function",
                    "extra_content": {
                        "google": {"thought_signature": "signature-from-gemini"}
                    },
                    "function": {
                        "name": "search_documents",
                        "arguments": '{"query":"licencia"}',
                    },
                }
            ],
        }
    )

    wire = _message_to_wire(
        ChatMessage(role="assistant", content=result.content, tool_calls=result.tool_calls)
    )

    assert wire["tool_calls"][0]["extra_content"] == {
        "google": {"thought_signature": "signature-from-gemini"}
    }
