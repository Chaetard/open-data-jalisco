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
        self.document_types: list[str | None] = []

    def __call__(
        self,
        query: str,
        local_only: bool = True,
        limit: int = 6,
        municipality: str | None = None,
        year: int | None = None,
        document_type: str | None = None,
    ) -> list[SearchHit]:
        self.queries.append((query, local_only, limit, municipality, year))
        self.document_types.append(document_type)
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


def _titled_hit(title: str, url: str) -> SearchHit:
    doc = make_document(title=title)
    chunk = make_chunk(doc, text="contenido")
    out = document_to_out(doc).model_copy(update={"official_url": url})
    return SearchHit(score=0.9, chunk=chunk_to_out(chunk), document=out)


def test_sources_track_documents_cited_in_the_answer():
    # Three docs consulted; the final answer names only two (by code / title).
    # Only those two surface — the third must not, even though it was retrieved.
    hits = [
        _titled_hit("PE-298 26 Octubre 2023", "https://x.invalid/pe298"),
        _titled_hit("Leyes de Ingreso Tala 2021", "https://x.invalid/ingreso"),
        _titled_hit("COMUR_POA25 Plan Operativo", "https://x.invalid/comur"),
    ]
    llm = ScriptedLLM(
        [
            _tool_call("egresos"),
            ChatResult(
                content=(
                    "Hallazgo: la póliza PE-298 registra un pago (HISTÓRICO). "
                    "Las Leyes de Ingreso Tala 2021 son antecedente documental."
                ),
                tool_calls=[],
            ),
        ]
    )
    result = AskAgent(llm=llm, search=RecordingSearch(hits), max_iters=5).ask("egresos")
    urls = {s.url for s in result.sources}
    assert urls == {"https://x.invalid/pe298", "https://x.invalid/ingreso"}
    assert "https://x.invalid/comur" not in urls  # consulted but never cited


def test_sources_get_provisional_title_when_no_inferred():
    # No LLM inferred_title -> the chat still shows a readable title cleaned from
    # the cryptic filename, with NO per-doc LLM call.
    llm = ScriptedLLM([_tool_call("q"), ChatResult(content="ok", tool_calls=[])])
    hit = _titled_hit("POA-OBRAS-2023", "https://x.invalid/poa")
    result = AskAgent(llm=llm, search=RecordingSearch([hit]), max_iters=5).ask("x")
    assert result.sources[0].inferred_title == "Poa Obras 2023"


def test_mode_selects_system_prompt():
    # The chosen mode must reach the system message and be echoed on the result.
    for mode, marker in (("ciudadano", "modo ciudadano"), ("investigador", "modo investigador")):
        llm = ScriptedLLM([ChatResult(content="ok", tool_calls=[])])
        result = AskAgent(llm=llm, search=RecordingSearch([]), max_iters=3).ask("x", mode=mode)
        system_prompt = llm.calls[0][0][0].content
        assert marker in system_prompt
        assert result.mode == mode


def test_unknown_mode_falls_back_to_default():
    llm = ScriptedLLM([ChatResult(content="ok", tool_calls=[])])
    result = AskAgent(llm=llm, search=RecordingSearch([]), max_iters=3).ask("x", mode="bogus")
    assert result.mode == "ciudadano"


def test_history_is_replayed_before_the_question():
    llm = ScriptedLLM([ChatResult(content="ok", tool_calls=[])])
    AskAgent(llm=llm, search=RecordingSearch([]), max_iters=3).ask(
        "¿y en Tequila?",
        history=[("¿gasto en obra?", "Fue X."), ("¿y becas?", "Fue Y.")],
    )
    msgs = llm.calls[0][0]
    assert [m.role for m in msgs] == [
        "system", "user", "assistant", "user", "assistant", "user",
    ]
    assert msgs[1].content == "¿gasto en obra?"
    assert msgs[2].content == "Fue X."
    assert msgs[-1].content == "¿y en Tequila?"


def test_search_receives_municipality_and_year_filters():
    llm = ScriptedLLM(
        [
            ChatResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="1",
                        name="search_documents",
                        arguments='{"query":"egresos","municipality":"Tequila","year":2024}',
                    )
                ],
            ),
            ChatResult(content="ok", tool_calls=[]),
        ]
    )
    search = RecordingSearch([_hit("Doc", "t")])
    AskAgent(llm=llm, search=search, max_iters=5).ask("x")
    query, _local, _limit, municipality, year = search.queries[0]
    assert query == "egresos"
    assert municipality == "Tequila"
    assert year == 2024


def test_search_receives_document_type_filter():
    # The agent can scope to a document type from the corpus panorama.
    llm = ScriptedLLM(
        [
            ChatResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="1",
                        name="search_documents",
                        arguments='{"query":"sesiones","document_type":"acta"}',
                    )
                ],
            ),
            ChatResult(content="ok", tool_calls=[]),
        ]
    )
    search = RecordingSearch([_hit("Doc", "t")])
    AskAgent(llm=llm, search=search, max_iters=5).ask("x")
    assert search.document_types[0] == "acta"


def test_corpus_overview_is_appended_to_system_prompt():
    llm = ScriptedLLM([ChatResult(content="ok", tool_calls=[])])
    AskAgent(
        llm=llm,
        search=RecordingSearch([]),
        max_iters=3,
        corpus_overview=lambda: "PANORAMA: Tequila (5)",
    ).ask("x")
    assert "PANORAMA: Tequila (5)" in llm.calls[0][0][0].content


def test_corpus_overview_failure_does_not_break_ask():
    def boom() -> str:
        raise RuntimeError("db down")

    llm = ScriptedLLM([ChatResult(content="ok", tool_calls=[])])
    result = AskAgent(
        llm=llm, search=RecordingSearch([]), max_iters=3, corpus_overview=boom
    ).ask("x")
    assert result.answer == "ok"


def test_municipality_name_is_not_a_false_citation():
    # A doc titled only with a municipality name must NOT count as cited just
    # because the answer mentions that municipality — the dynamic muni stopwords
    # strip it. A distinctively-titled doc still surfaces.
    hits = [
        _titled_hit("Tequila", "https://x.invalid/muni"),
        _titled_hit("Reglamento de Construcción", "https://x.invalid/regla"),
    ]
    llm = ScriptedLLM(
        [
            _tool_call("q"),
            ChatResult(
                content="En Tequila, el Reglamento de Construcción pide A, B, C.",
                tool_calls=[],
            ),
        ]
    )
    result = AskAgent(
        llm=llm,
        search=RecordingSearch(hits),
        max_iters=5,
        corpus_municipalities=lambda: frozenset({"tequila"}),
    ).ask("requisitos")
    urls = {s.url for s in result.sources}
    assert urls == {"https://x.invalid/regla"}  # the bare-municipality doc dropped


class _StubRouter:
    def __init__(self, route):
        self.model = "router-llm"
        self._route = route

    def classify(self, question, history=None):
        return self._route


def test_router_short_circuits_non_search():
    from open_data_jalisco.agent.router import Route

    llm = ScriptedLLM([])  # must never be called
    search = RecordingSearch([])
    result = AskAgent(
        llm=llm,
        search=search,
        max_iters=5,
        router=_StubRouter(Route("chitchat", "¡Hola! ¿Qué documento buscas?")),
    ).ask("hola")

    assert result.answer == "¡Hola! ¿Qué documento buscas?"
    assert result.iterations == 0
    assert result.sources == []
    assert result.model == "router-llm"
    assert llm.calls == []  # no expensive loop
    assert search.queries == []  # no search


def test_router_search_intent_runs_the_loop():
    from open_data_jalisco.agent.router import Route

    llm = ScriptedLLM(
        [_tool_call("requisitos"), ChatResult(content="Necesitas A.", tool_calls=[])]
    )
    search = RecordingSearch([_hit("Reglamento", "A")])
    result = AskAgent(
        llm=llm,
        search=search,
        max_iters=5,
        router=_StubRouter(Route("search")),
    ).ask("¿requisitos?")

    assert "Necesitas A." in result.answer
    assert result.iterations == 2
    assert len(search.queries) == 1


def test_agent_caps_and_ranks_sources():
    # One search returns 8 distinct docs; only the 5 highest-scoring survive,
    # ordered by score. Stops the agent from dumping every chunk it ever saw.
    hits = [_scored_hit(f"https://x.invalid/{i}", score=i / 10) for i in range(8)]
    llm = ScriptedLLM([_tool_call("q"), ChatResult(content="ok", tool_calls=[])])
    result = AskAgent(llm=llm, search=RecordingSearch(hits), max_iters=5).ask("x")

    assert len(result.sources) == 5
    assert [s.url for s in result.sources] == [f"https://x.invalid/{i}" for i in (7, 6, 5, 4, 3)]


def test_read_document_tool_drills_into_a_document():
    reads = []

    def fake_read(*, url, page=None):
        reads.append((url, page))
        return [{"page_start": 12, "page_end": 12, "text": "Partida 333: 1,000,000 devengado"}]

    llm = ScriptedLLM(
        [
            ChatResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="1",
                        name="read_document",
                        arguments='{"url":"https://x.invalid/doc","page":12}',
                    )
                ],
            ),
            ChatResult(content="La partida 333 registra 1,000,000 devengado.", tool_calls=[]),
        ]
    )
    result = AskAgent(
        llm=llm, search=RecordingSearch([]), max_iters=5, read_document=fake_read
    ).ask("¿cuánto en la 333?")
    assert reads == [("https://x.invalid/doc", 12)]
    assert "1,000,000" in result.answer
    offered = {t["function"]["name"] for t in llm.calls[0][1]}
    assert "read_document" in offered
    assert "document_coverage" not in offered  # not injected -> not offered


def test_coverage_tool_counts_including_scanned():
    captured = {}

    def fake_cov(*, municipality=None, year=None, document_type=None):
        captured.update(municipality=municipality, year=year, document_type=document_type)
        return {"buscables": 0, "escaneados_sin_texto": 7, "total": 7}

    llm = ScriptedLLM(
        [
            ChatResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="1",
                        name="document_coverage",
                        arguments='{"municipality":"Tequila","year":2024}',
                    )
                ],
            ),
            ChatResult(content="Hay 7 documentos pero están escaneados.", tool_calls=[]),
        ]
    )
    result = AskAgent(
        llm=llm, search=RecordingSearch([]), max_iters=5, coverage=fake_cov
    ).ask("¿hay algo de obra en Tequila 2024?")
    assert captured == {"municipality": "Tequila", "year": 2024, "document_type": None}
    assert "7" in result.answer
    offered = {t["function"]["name"] for t in llm.calls[0][1]}
    assert "document_coverage" in offered


def test_unknown_or_unavailable_tool_does_not_crash():
    # The model calls read_document but it isn't injected -> the loop returns a
    # note and keeps going instead of raising.
    llm = ScriptedLLM(
        [
            ChatResult(
                content=None,
                tool_calls=[ToolCall(id="1", name="read_document", arguments='{"url":"x"}')],
            ),
            ChatResult(content="ok", tool_calls=[]),
        ]
    )
    result = AskAgent(llm=llm, search=RecordingSearch([]), max_iters=5).ask("x")
    assert result.answer == "ok"


def test_simple_intent_uses_tight_budget():
    from open_data_jalisco.agent.router import Route

    # Router says "simple"; the model keeps asking to search, but the loop must
    # cap at the simple budget (2), not max_iters=5.
    llm = ScriptedLLM([_tool_call("q1"), _tool_call("q2"), _tool_call("q3")])
    search = RecordingSearch([_hit("Doc", "t")])
    result = AskAgent(
        llm=llm, search=search, max_iters=5, router=_StubRouter(Route("simple"))
    ).ask("¿quién es el presidente municipal?")
    assert result.iterations == 2
    assert len(search.queries) == 2
