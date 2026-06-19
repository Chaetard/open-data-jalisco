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
import re
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
    "VIGENCIA — marca el estatus temporal\n"
    "- Cuando uses documentos de años distintos, etiqueta cada hallazgo: VIGENTE "
    "(periodo actual), HISTÓRICO (periodo pasado ya cerrado), ANTECEDENTE "
    "DOCUMENTAL (sirve de contexto, no prueba el estado actual) o NO VERIFICABLE.\n"
    "- Para afirmar el estado ACTUAL usa el documento más reciente; los anteriores "
    "son antecedente, no evidencia de vigencia. No mezcles años sin marcarlos.\n"
    "\n"
    "CERTEZA — calíbrala, no la infles\n"
    "- Separa la certeza de la MENCIÓN de la certeza del HECHO COMPLETO. Una póliza "
    "de egreso da certeza ALTA de que se registró contablemente un pago, pero "
    "certeza MEDIA de que eso represente la obra completa, el contrato total o el "
    "proveedor final — eso exige contrato/factura/estimación. No declares 'certeza "
    "alta' sobre el hecho completo con sólo evidencia contable o presupuestal.\n"
    "\n"
    "RESPUESTA\n"
    "- Cita por su título los documentos que realmente usaste (todos los que "
    "sustenten un hallazgo), no los que sólo hojeaste. Cada hallazgo debe poder "
    "rastrearse a un documento citado.\n"
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
# Final sources should track what the answer actually cites, not the top-N by
# retrieval score (that dropped documents the agent named in its prose, e.g.
# "PE-298"). We keep every consulted document whose title is mentioned in the
# answer (up to a safety cap), and fall back to the most relevant few only when
# the model named nothing matchable.
# ponytail: title-overlap heuristic; swap for model-emitted citation ids if the
# model ever cites without echoing a title token.
_MAX_CITED = 12
_FALLBACK_SOURCES = 5
# Spanish function words + the ever-present municipality: too common to signal
# that a specific document was cited.
_STOPWORDS = frozenset(
    {
        "de", "la", "el", "los", "las", "del", "y", "en", "por", "para", "con",
        "un", "una", "al", "lo", "su", "sus", "o", "e", "municipio", "tala",
        "jalisco", "documento", "documentos",
    }
)


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
    # Content-derived title (readable); null until the infer-titles job runs.
    inferred_title: str | None = None


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
                answer = result.content or ""
                selected = _select_sources(answer, sources)
                logger.info(
                    "ask: answered after %d iters in %.1fs (%d cited / %d consulted)",
                    i + 1,
                    time.perf_counter() - start,
                    len(selected),
                    len(sources),
                )
                return AskResult(
                    answer=answer,
                    sources=selected,
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
        answer = final.content or "No pude llegar a una respuesta con la evidencia encontrada."
        return AskResult(
            answer=answer,
            sources=_select_sources(answer, sources),
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


def _select_sources(answer: str, sources: dict[str, tuple[float, Source]]) -> list[Source]:
    """Keep the consulted documents the answer actually cites.

    Traceability fix: the final list must match the findings in the prose. A
    document counts as cited when a distinctive token of its title (a word >=4
    chars or a code like ``PE-298``/``COMUR_POA25``) appears in the answer. When
    nothing matches (model summarised without naming docs) fall back to the most
    relevant few so the list is never empty.
    """
    by_score = [s for _, s in sorted(sources.values(), key=lambda p: p[0], reverse=True)]
    answer_words = set(_norm(answer).split())
    answer_codes = _codes(answer)
    cited = [s for s in by_score if _is_cited(answer_words, answer_codes, s)]
    if cited:
        return cited[:_MAX_CITED]
    return by_score[:_FALLBACK_SOURCES]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _title_tokens(title: str) -> set[str]:
    # Distinctive words: drop stopwords and bare numbers (years collide across
    # documents); keep real words (>=4) and alphanumeric codes (poa25).
    out = set()
    for t in _norm(title).split():
        if t in _STOPWORDS or t.isdigit():
            continue
        if len(t) >= 4 or any(c.isdigit() for c in t):
            out.add(t)
    return out


def _codes(text: str) -> set[str]:
    # Compact identifiers like PE-298, COMUR_POA25, POA25 -> {"pe298","poa25"}.
    found = re.findall(r"[a-zA-Z]{2,}[-_ ]?\d{2,}|[A-Z]{2,}\d+", text)
    return {re.sub(r"[^a-z0-9]", "", m.lower()) for m in found}


def _is_cited(answer_words: set[str], answer_codes: set[str], src: Source) -> bool:
    for cand in (src.inferred_title, src.title):
        if not cand:
            continue
        if _title_tokens(cand) & answer_words:
            return True
        if _codes(cand) & answer_codes:
            return True
    return False


def _to_source(hit: SearchHit) -> Source:
    return Source(
        title=hit.document.title,
        url=hit.document.official_url,
        page_start=hit.chunk.page_start,
        page_end=hit.chunk.page_end,
        jurisdiction=hit.document.jurisdiction,
        excerpt=_excerpt(hit.chunk.text),
        inferred_title=hit.document.inferred_title,
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
