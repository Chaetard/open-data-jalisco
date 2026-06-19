# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Content-derived document titling (LLM-backed), driven by a fake LLM."""
from open_data_jalisco.ports.llm import ChatResult
from open_data_jalisco.titling import infer_title


class FakeLLM:
    model = "fake"

    def __init__(self, content: str):
        self._content = content
        self.last_messages = None

    def chat(self, messages, tools=None):
        self.last_messages = messages
        return ChatResult(content=self._content, tool_calls=[])


def test_infer_title_strips_quotes_and_extra_lines():
    llm = FakeLLM('"Acta de Comisión Edilicia, enero 2026"\nnota irrelevante')
    title = infer_title(llm, text="Acta de la comisión...", municipality="Tala", year=2026)
    assert title == "Acta de Comisión Edilicia, enero 2026"


def test_infer_title_empty_text_skips_the_llm():
    llm = FakeLLM("no debería usarse")
    assert infer_title(llm, text="   ") == ""
    assert llm.last_messages is None  # never called -> no wasted token spend


def test_infer_title_feeds_content_and_metadata_to_model():
    llm = FakeLLM("Reglamento de Construcción Municipal")
    infer_title(llm, text="texto del reglamento de construcción", municipality="Tala", year=2024)
    user_msg = llm.last_messages[-1].content
    assert "reglamento de construcción" in user_msg.lower()
    assert "Tala" in user_msg
