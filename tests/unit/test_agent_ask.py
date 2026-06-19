# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""The ReAct loop, driven by a scripted LLM and a fake search — no network."""
from open_data_jalisco.agent import AskAgent
from open_data_jalisco.api.schemas import SearchHit, chunk_to_out, document_to_out
from open_data_jalisco.ports.llm import ChatResult, ToolCall

from ._api_helpers import make_chunk, make_document


def _hit(title: str, text: str) -> SearchHit:
    doc = make_document(title=title)
    chunk = make_chunk(doc, text=text)
    return SearchHit(score=0.9, chunk=chunk_to_out(chunk), document=document_to_out(doc))


class ScriptedLLM:
    model = "fake-llm"

    def __init__(self, results: list[ChatResult]):
        self._results = list(results)
        self.calls: list[tuple] = []

    def chat(self, messages, tools=None):
        self.calls.append((messages, tools))
        return self._results.pop(0)


class RecordingSearch:
    def __init__(self, hits: list[SearchHit]):
        self._hits = hits
        self.queries: list[tuple] = []

    def __call__(self, query: str, local_only: bool, limit: int) -> list[SearchHit]:
        self.queries.append((query, local_only, limit))
        return self._hits


def _tool_call(query: str) -> ChatResult:
    return ChatResult(
        content=None,
        tool_calls=[
            ToolCall(id="1", name="search_documents", arguments=f'{{"query":"{query}"}}')
        ],
    )


def test_agent_searches_then_answers():
    llm = ScriptedLLM(
        [
            _tool_call("requisitos licencia construccion"),
            ChatResult(content="Necesitas A, B y C (Reglamento de construcción).", tool_calls=[]),
        ]
    )
    search = RecordingSearch([_hit("Reglamento de construcción", "Los requisitos son A, B, C")])
    result = AskAgent(llm=llm, search=search, max_iters=5).ask("¿Qué requisitos?")

    assert "A, B y C" in result.answer
    assert result.iterations == 2
    assert result.model == "fake-llm"
    assert search.queries[0][0] == "requisitos licencia construccion"
    assert search.queries[0][1] is True  # local_only defaults true inside the tool
    assert [s.title for s in result.sources] == ["Reglamento de construcción"]


def test_agent_answers_without_searching():
    llm = ScriptedLLM([ChatResult(content="Hola, ¿en qué ayudo?", tool_calls=[])])
    search = RecordingSearch([])
    result = AskAgent(llm=llm, search=search, max_iters=5).ask("hola")

    assert result.answer.startswith("Hola")
    assert result.iterations == 1
    assert search.queries == []
    assert result.sources == []


def test_agent_is_bounded_and_forces_a_final_answer():
    # The model never stops asking to search; the loop must cap at max_iters and
    # then force one final, tool-less answer.
    llm = ScriptedLLM(
        [
            _tool_call("q1"),
            _tool_call("q2"),
            ChatResult(content="Respuesta final con lo encontrado.", tool_calls=[]),
        ]
    )
    search = RecordingSearch([_hit("Doc", "texto")])
    result = AskAgent(llm=llm, search=search, max_iters=2).ask("pregunta")

    assert result.iterations == 2
    assert len(search.queries) == 2
    assert "Respuesta final" in result.answer
    # The final forced call must not offer tools.
    assert llm.calls[-1][1] is None


def test_agent_dedupes_sources_by_url():
    same = _hit("Doc repetido", "a")
    llm = ScriptedLLM(
        [
            _tool_call("q1"),
            _tool_call("q2"),
            ChatResult(content="ok", tool_calls=[]),
        ]
    )
    # Same hit returned on both searches → one source, not two.
    result = AskAgent(llm=llm, search=RecordingSearch([same]), max_iters=5).ask("x")
    assert len(result.sources) == 1


def _scored_hit(url: str, score: float) -> SearchHit:
    doc = make_document(title=f"Doc {url}")
    chunk = make_chunk(doc, text="t")
    out = document_to_out(doc).model_copy(update={"official_url": url})
    return SearchHit(score=score, chunk=chunk_to_out(chunk), document=out)


def test_agent_caps_and_ranks_sources():
    # One search returns 8 distinct docs; only the 5 highest-scoring survive,
    # ordered by score. Stops the agent from dumping every chunk it ever saw.
    hits = [_scored_hit(f"https://x.invalid/{i}", score=i / 10) for i in range(8)]
    llm = ScriptedLLM([_tool_call("q"), ChatResult(content="ok", tool_calls=[])])
    result = AskAgent(llm=llm, search=RecordingSearch(hits), max_iters=5).ask("x")

    assert len(result.sources) == 5
    assert [s.url for s in result.sources] == [f"https://x.invalid/{i}" for i in (7, 6, 5, 4, 3)]
