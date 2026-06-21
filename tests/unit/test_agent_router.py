# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""The intent router: classification, JSON tolerance, and safe fallbacks."""
from open_data_jalisco.agent.router import SEARCH, SIMPLE, Route, Router, _parse
from open_data_jalisco.ports.llm import ChatResult


class StubLLM:
    model = "router-llm"

    def __init__(self, content):
        self._content = content
        self.calls = 0
        self.last_messages = None

    def chat(self, messages, tools=None):
        self.calls += 1
        self.last_messages = messages
        if isinstance(self._content, Exception):
            raise self._content
        return ChatResult(content=self._content, tool_calls=[])


def test_search_intent_has_no_reply():
    r = _parse('{"intent": "search", "reply": ""}')
    assert r == Route(SEARCH)


def test_chitchat_keeps_reply():
    r = _parse('{"intent": "chitchat", "reply": "¡Hola! Pregúntame sobre documentos."}')
    assert r.intent == "chitchat"
    assert "Hola" in r.reply


def test_simple_intent_has_no_reply():
    # "simple" goes to the agent (it searches), so it needs no router reply.
    assert _parse('{"intent": "simple", "reply": ""}') == Route(SIMPLE)
    assert _parse('{"intent": "simple", "reply": "lo que sea"}') == Route(SIMPLE)


def test_router_appends_corpus_overview_to_prompt():
    llm = StubLLM('{"intent": "chitchat", "reply": "¡Hola! Pregunta sobre presupuestos."}')
    route = Router(llm, corpus_overview=lambda: "PANORAMA: Tequila (5733)").classify("hola")
    assert route.intent == "chitchat"
    assert "PANORAMA: Tequila (5733)" in llm.last_messages[0].content


def test_router_overview_failure_does_not_break_classify():
    def boom() -> str:
        raise RuntimeError("db down")

    route = Router(StubLLM('{"intent":"search","reply":""}'), corpus_overview=boom).classify("x")
    assert route.intent == SEARCH


def test_json_fence_is_tolerated():
    r = _parse('```json\n{"intent":"out_of_scope","reply":"Sólo cubro documentos."}\n```')
    assert r.intent == "out_of_scope"
    assert r.reply == "Sólo cubro documentos."


def test_non_search_without_reply_falls_back_to_search():
    # A non-search intent with no reply would leave the user with nothing — search.
    assert _parse('{"intent": "chitchat", "reply": ""}') == Route(SEARCH)


def test_garbage_defaults_to_search():
    assert _parse("no soy json").intent == SEARCH
    assert _parse('{"intent": "banana", "reply": "x"}').intent == SEARCH


def test_router_classify_uses_history():
    llm = StubLLM('{"intent": "search", "reply": ""}')
    route = Router(llm).classify("¿y en Tequila?", history=[("¿gasto en obra?", "Fue X.")])
    assert route.intent == SEARCH
    assert llm.calls == 1


def test_router_failure_defaults_to_search():
    route = Router(StubLLM(RuntimeError("boom"))).classify("hola")
    assert route.intent == SEARCH
