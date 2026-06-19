# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""The /ask endpoint contract: disabled-by-default, and the happy path."""
from fastapi.testclient import TestClient

from open_data_jalisco.agent import AskResult, Source
from open_data_jalisco.api.app import create_app
from open_data_jalisco.api.deps import get_ask_agent
from open_data_jalisco.ports.llm import LLMError


def test_ask_returns_503_when_agent_disabled():
    app = create_app()
    app.dependency_overrides[get_ask_agent] = lambda: None
    res = TestClient(app).post("/ask", json={"question": "¿cómo solicito una licencia?"})
    assert res.status_code == 503
    assert "LLM_API_KEY" in res.json()["detail"]


class _FakeAgent:
    def ask(self, question: str) -> AskResult:
        return AskResult(
            answer="Respuesta basada en los documentos.",
            sources=[
                Source(
                    title="Reglamento municipal",
                    url="https://example.invalid/doc",
                    page_start=3,
                    page_end=3,
                    jurisdiction="municipal",
                )
            ],
            iterations=2,
            model="fake-llm",
        )


def test_ask_returns_answer_and_sources():
    app = create_app()
    app.dependency_overrides[get_ask_agent] = lambda: _FakeAgent()
    res = TestClient(app).post("/ask", json={"question": "¿qué requisitos necesito?"})
    assert res.status_code == 200
    body = res.json()
    assert body["answer"] == "Respuesta basada en los documentos."
    assert body["model"] == "fake-llm"
    assert body["iterations"] == 2
    assert body["sources"][0]["title"] == "Reglamento municipal"
    assert body["sources"][0]["jurisdiction"] == "municipal"


def test_ask_rejects_short_question():
    app = create_app()
    app.dependency_overrides[get_ask_agent] = lambda: _FakeAgent()
    res = TestClient(app).post("/ask", json={"question": "a"})
    assert res.status_code == 422


class _BoomAgent:
    def ask(self, question: str) -> AskResult:
        raise LLMError("LLM upstream 400: invalid value at messages[2].content")


def test_ask_returns_502_on_upstream_llm_error():
    app = create_app()
    app.dependency_overrides[get_ask_agent] = lambda: _BoomAgent()
    res = TestClient(app).post("/ask", json={"question": "¿qué requisitos?"})
    assert res.status_code == 502
    assert "LLM" in res.json()["detail"]
