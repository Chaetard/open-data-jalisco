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
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..api.schemas import SearchHit
from ..ports.llm import ChatMessage, LLMClient
from ..shared.logging import get_logger

logger = get_logger(__name__)

# (query, local_only, limit) -> hits. Injected so the agent stays decoupled
# from the DB/embedder wiring and is trivial to fake in tests.
SearchFn = Callable[[str, bool, int], list[SearchHit]]

_SYSTEM_PROMPT = (
    "Eres un asistente de transparencia que responde sobre los documentos "
    "públicos del municipio de Tala, Jalisco. Tu trabajo es reportar lo que los "
    "documentos dicen, no juzgar a la autoridad. Reglas:\n"
    "\n"
    "FUENTE\n"
    "- Responde SÓLO con lo obtenido vía la herramienta search_documents. No uses "
    "conocimiento externo ni inventes datos.\n"
    "- Si una búsqueda no basta, reformúlala y busca de nuevo. Sé eficiente: 2 a 4 "
    "búsquedas suelen bastar. No repitas consultas equivalentes.\n"
    "\n"
    "REGLA DE ORO — ausencia de evidencia ≠ cero\n"
    "- NUNCA conviertas «no lo encontré» en «no existe», «es $0», «no se gastó» o "
    "«hay subejercicio». Que un monto no aparezca en los documentos recuperados "
    "sólo significa que NO LO ENCONTRASTE ahí, no que sea cero.\n"
    "- Si no hallas una cifra, di: «No se encontró un monto específico para X en "
    "los documentos recuperados», y enumera las posibles causas cuando aplique "
    "(no se desglosa a ese nivel, está agrupado en un nivel superior, el documento "
    "correcto no se consultó, etc.).\n"
    "\n"
    "TONO — neutral, no acusatorio\n"
    "- Este es un servicio público. NO imputes irregularidades, dolo, desvío, "
    "incumplimiento ni «subejercicio» a partir de datos faltantes o parciales. "
    "Reporta hechos documentales, no juicios sobre la conducta de la autoridad.\n"
    "\n"
    "CALIDAD DE CADA AFIRMACIÓN — etiqueta lo que digas\n"
    "- Distingue siempre: ENCONTRADO (está textual en un documento), NO ENCONTRADO "
    "(no aparece en lo recuperado), INFERIDO (lo deduces, dilo) y NO VERIFICABLE "
    "(haría falta otro documento: contratos, facturas, órdenes de compra, actas).\n"
    "\n"
    "PRESUPUESTO ≠ EJECUCIÓN\n"
    "- No confundas lo PROGRAMADO/APROBADO/CALENDARIZADO (lo que se planeó gastar) "
    "con lo EJECUTADO: DEVENGADO, EJERCIDO o PAGADO (lo que realmente se gastó). "
    "El calendario mensual NO prueba ejecución.\n"
    "- Niveles del Clasificador por Objeto del Gasto, de mayor a menor: capítulo "
    "(p.ej. 3000) ⊃ concepto (3300) ⊃ partida (333). Sé explícito sobre cuál "
    "citas y no mezcles niveles: una cifra de la 333 no es la del 3300.\n"
    "\n"
    "EVIDENCIA EXACTA\n"
    "- Para cualquier cifra, cita la fila/columna exacta del documento (partida o "
    "concepto y la columna: aprobado, modificado, devengado, ejercido, pagado) más "
    "el título del documento y la página. No reportes montos sin su renglón.\n"
    "\n"
    "RESPUESTA\n"
    "- Cita por su título SÓLO los documentos que realmente usaste (máximo 5). No "
    "enumeres todo lo que viste.\n"
    "- Español claro y conciso. Si no encuentras evidencia, dilo; no rellenes."
)

_SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": (
            "Búsqueda híbrida (significado + texto exacto) en los documentos "
            "públicos del municipio de Tala. Encuentra tanto conceptos como "
            "términos literales: códigos de partida (333, 3300), fondos "
            "(FAISMUN), montos, RFC, nombres propios y artículos. Devuelve "
            "fragmentos con su documento, página y URL. Llámala varias veces con "
            "consultas distintas si hace falta."
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
# Length of the verifiable excerpt carried back to the UI per source.
_EXCERPT_CHARS = 300
# Cap the sources returned to the user. The agent may consult dozens of chunks
# across several searches; surfacing all of them implies they were all used and
# drowns the few that mattered. Keep the highest-scoring distinct documents.
# ponytail: score proxy for "used"; swap for model-emitted citations if needed.
_MAX_SOURCES = 5


@dataclass
class Source:
    title: str | None
    url: str
    page_start: int | None
    page_end: int | None
    jurisdiction: str
    # The exact text the citation rests on. The filename-derived title is
    # unreliable; the excerpt is the verifiable evidence, so the UI can show the
    # quote and let the reader judge it regardless of the title.
    excerpt: str


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
        # url -> (best score seen, Source). Dedupes across searches and lets us
        # keep only the most relevant few at the end.
        sources: dict[str, tuple[float, Source]] = {}
        start = time.perf_counter()
        logger.info("ask: start q=%r max_iters=%d", question[:120], self._max_iters)

        for i in range(self._max_iters):
            logger.info("ask: iter %d/%d -> llm", i + 1, self._max_iters)
            result = self._llm.chat(messages, tools=[_SEARCH_TOOL])
            if not result.tool_calls:
                logger.info(
                    "ask: answered after %d iters in %.1fs (%d sources)",
                    i + 1,
                    time.perf_counter() - start,
                    len(sources),
                )
                return AskResult(
                    answer=result.content or "",
                    sources=_top_sources(sources),
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
                    score = hit.rerank_score if hit.rerank_score is not None else hit.score
                    prev = sources.get(hit.document.official_url)
                    if prev is None or score > prev[0]:
                        sources[hit.document.official_url] = (score, _to_source(hit))
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
        logger.warning(
            "ask: hit max_iters=%d in %.1fs, forcing final answer",
            self._max_iters,
            time.perf_counter() - start,
        )
        final = self._llm.chat(messages, tools=None)
        return AskResult(
            answer=final.content or "No pude llegar a una respuesta con la evidencia encontrada.",
            sources=_top_sources(sources),
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
        # Log before the call, not just after: if search hangs (dead DB, slow
        # rerank) the "returned" line never prints, so without this a hang here
        # is invisible.
        logger.info("ask: search q=%r local_only=%s", query, local_only)
        hits = self._search(query, local_only, _TOOL_HIT_LIMIT)
        logger.info("ask: search returned %d hits", len(hits))
        return hits


def _top_sources(sources: dict[str, tuple[float, Source]]) -> list[Source]:
    ordered = sorted(sources.values(), key=lambda p: p[0], reverse=True)
    return [s for _, s in ordered[:_MAX_SOURCES]]


def _to_source(hit: SearchHit) -> Source:
    return Source(
        title=hit.document.title,
        url=hit.document.official_url,
        page_start=hit.chunk.page_start,
        page_end=hit.chunk.page_end,
        jurisdiction=hit.document.jurisdiction,
        excerpt=_excerpt(hit.chunk.text),
    )


def _excerpt(text: str) -> str:
    text = text.strip()
    return text if len(text) <= _EXCERPT_CHARS else text[:_EXCERPT_CHARS].rstrip() + "…"


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
