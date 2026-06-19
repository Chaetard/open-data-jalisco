# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Answering agent: a bounded ReAct loop over the semantic-search tool.

The model is handed one tool — ``search_documents`` — and the question. It
searches, reads the fragments, reasons, searches again if needed, and finally
answers in prose citing the documents. Grounding is enforced by the prompt and
by only ever feeding it real search results; the agent never sees the corpus
except through the tool.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..api.schemas import SearchHit
from ..ports.llm import ChatMessage, LLMClient

# (query, local_only, limit) -> hits. Injected so the agent stays decoupled
# from the DB/embedder wiring and is trivial to fake in tests.
SearchFn = Callable[[str, bool, int], list[SearchHit]]

_SYSTEM_PROMPT = (
    "Eres un asistente que responde preguntas sobre los documentos públicos del "
    "municipio de Tala, Jalisco. Reglas:\n"
    "- Responde SÓLO con información obtenida mediante la herramienta "
    "search_documents. No uses conocimiento externo ni inventes datos.\n"
    "- Si la primera búsqueda no basta, reformula la consulta y busca de nuevo "
    "(puedes buscar varias veces).\n"
    "- Si tras buscar no encuentras evidencia, dilo claramente; no rellenes.\n"
    "- Cita los documentos por su título cuando afirmes algo.\n"
    "- Responde en español, claro y conciso."
)

_SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": (
            "Busca por significado (no por palabra exacta) en los documentos "
            "públicos del municipio de Tala. Devuelve fragmentos con su documento, "
            "página y URL. Llámala varias veces con consultas distintas si hace falta."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Consulta en lenguaje natural, en español.",
                },
                "local_only": {
                    "type": "boolean",
                    "description": (
                        "Si true (por defecto), oculta documentos estatales/federales "
                        "republicados y deja sólo los del municipio. Pon false sólo si "
                        "necesitas explícitamente leyes estatales o federales."
                    ),
                },
            },
            "required": ["query"],
        },
    },
}

_TOOL_HIT_LIMIT = 6
_SNIPPET_CHARS = 500


@dataclass
class Source:
    title: str | None
    url: str
    page_start: int | None
    page_end: int | None
    jurisdiction: str


@dataclass
class AskResult:
    answer: str
    sources: list[Source] = field(default_factory=list)
    iterations: int = 0
    model: str = ""


class AskAgent:
    def __init__(self, *, llm: LLMClient, search: SearchFn, max_iters: int = 5):
        self._llm = llm
        self._search = search
        self._max_iters = max_iters

    def ask(self, question: str) -> AskResult:
        messages = [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(role="user", content=question),
        ]
        sources: dict[str, Source] = {}  # keyed by url, dedupes across searches

        for i in range(self._max_iters):
            result = self._llm.chat(messages, tools=[_SEARCH_TOOL])
            if not result.tool_calls:
                return AskResult(
                    answer=result.content or "",
                    sources=list(sources.values()),
                    iterations=i + 1,
                    model=self._llm.model,
                )

            messages.append(
                ChatMessage(
                    role="assistant",
                    content=result.content,
                    tool_calls=result.tool_calls,
                )
            )
            for call in result.tool_calls:
                hits = self._run_tool(call.name, call.arguments)
                for hit in hits:
                    sources[hit.document.official_url] = _to_source(hit)
                messages.append(
                    ChatMessage(
                        role="tool",
                        tool_call_id=call.id,
                        name=call.name,
                        content=_format_hits(hits),
                    )
                )

        # Iterations exhausted: force a final answer with the evidence gathered,
        # no tools this time so the model must conclude.
        final = self._llm.chat(messages, tools=None)
        return AskResult(
            answer=final.content or "No pude llegar a una respuesta con la evidencia encontrada.",
            sources=list(sources.values()),
            iterations=self._max_iters,
            model=self._llm.model,
        )

    def _run_tool(self, name: str, arguments: str) -> list[SearchHit]:
        if name != "search_documents":
            return []
        try:
            args = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            return []
        query = str(args.get("query", "")).strip()
        if not query:
            return []
        local_only = bool(args.get("local_only", True))
        return self._search(query, local_only, _TOOL_HIT_LIMIT)


def _to_source(hit: SearchHit) -> Source:
    return Source(
        title=hit.document.title,
        url=hit.document.official_url,
        page_start=hit.chunk.page_start,
        page_end=hit.chunk.page_end,
        jurisdiction=hit.document.jurisdiction,
    )


def _format_hits(hits: list[SearchHit]) -> str:
    """Compact JSON the model reads as tool output."""
    if not hits:
        return json.dumps({"results": [], "note": "sin resultados"}, ensure_ascii=False)
    results = [
        {
            "title": h.document.title,
            "url": h.document.official_url,
            "page": h.chunk.page_start,
            "jurisdiction": h.document.jurisdiction,
            "text": h.chunk.text[:_SNIPPET_CHARS],
        }
        for h in hits
    ]
    return json.dumps({"results": results}, ensure_ascii=False)
