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
from .router import SEARCH as ROUTER_SEARCH
from .router import Router

logger = get_logger(__name__)

# Called with keyword args (query, local_only, limit, municipality, year) -> hits.
# Injected so the agent stays decoupled from the DB/embedder wiring and is trivial
# to fake in tests.
SearchFn = Callable[..., list[SearchHit]]

_CORE_RULES = (
    "Eres un asistente de transparencia que responde sobre los documentos "
    "públicos de municipios de Jalisco (los disponibles aparecen en el PANORAMA "
    "DEL CORPUS al final de estas instrucciones). Tu trabajo "
    "es reportar lo que los documentos dicen, no juzgar a la autoridad. Cuando la "
    "pregunta no nombre un municipio, no asumas uno: si los documentos recuperados "
    "son de varios, distingue de cuál es cada hallazgo. Reglas:\n"
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
    "CUANDO EL DOCUMENTO NO ESTÁ EN EL CORPUS\n"
    "- Si tras buscar no encuentras el documento o el dato que la persona pide, "
    "recomiéndale SIEMPRE solicitarlo por la Plataforma Nacional de Transparencia "
    "(PNT), que es el canal oficial para pedir información pública a la autoridad.\n"
    "- Menciona además que este panel cuenta con una guía paso a paso, fácil de "
    "seguir, para hacer esa solicitud en la PNT.\n"
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
)

# El bloque RESPUESTA cambia según el modo; todo lo de arriba (grounding,
# exactitud, vigencia, certeza) es idéntico, para que ningún modo sacrifique
# correctitud — sólo cambia la presentación.
_RESPUESTA_TECNICO = (
    "\n"
    "RESPUESTA (modo investigador)\n"
    "- Cita por su título los documentos que realmente usaste (todos los que "
    "sustenten un hallazgo), no los que sólo hojeaste. Cada hallazgo debe poder "
    "rastrearse a un documento citado.\n"
    "- Español claro y conciso. Si no encuentras evidencia, dilo; no rellenes."
)

_RESPUESTA_CIUDADANO = (
    "\n"
    "RESPUESTA (modo ciudadano)\n"
    "- Escribe para una persona sin formación técnica: lenguaje sencillo, sin "
    "jerga contable ni tablas (no digas 'partida 333'; di 'el rubro de…').\n"
    "- Si la pregunta es sobre un trámite o servicio, estructura la respuesta así: "
    "QUÉ necesitas, DÓNDE se hace (dependencia), QUÉ llevar (requisitos), CUÁNTO "
    "cuesta y QUÉ FALTA CONFIRMAR en ventanilla oficial.\n"
    "- Da la respuesta directa primero; el detalle, después y breve.\n"
    "- Aun en lenguaje simple, respeta TODAS las reglas de arriba: sólo lo que "
    "digan los documentos, cita por su título los que usaste, y marca lo que no "
    "aparezca en ellos como 'conviene confirmar oficialmente'. No inventes."
)

# Default ciudadano: la beta está orientada al público. El modo investigador es
# opt-in (clientes que quieren la traza técnica completa).
_SYSTEM_PROMPTS = {
    "ciudadano": _CORE_RULES + _RESPUESTA_CIUDADANO,
    "investigador": _CORE_RULES + _RESPUESTA_TECNICO,
}
DEFAULT_MODE = "ciudadano"

_SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": (
            "Búsqueda híbrida (significado + texto exacto) en los documentos "
            "públicos de los municipios de Jalisco disponibles (los que aparecen "
            "en el PANORAMA DEL CORPUS). Encuentra "
            "tanto conceptos como "
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
                "municipality": {
                    "type": "string",
                    "description": (
                        "Acota a un municipio. Usa EXACTAMENTE uno de los nombres del "
                        "PANORAMA DEL CORPUS. Omítelo para buscar en todos. Si no hay "
                        "resultados con el filtro, vuelve a buscar sin él."
                    ),
                },
                "year": {
                    "type": "integer",
                    "description": (
                        "Acota a un año (p.ej. 2024). Omítelo para no filtrar por año. "
                        "Si no hay resultados, reintenta sin el filtro."
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
# Prior (question, answer) pairs replayed for follow-up context. Only the final
# Q→A is kept (never the tool-call transcript) so tokens stay bounded.
_HISTORY_TURNS = 3
# Spanish function words too common to signal that a specific document was cited.
# Municipality names are NOT listed here — they'd also be false citation signals
# (a title "Presupuesto Tequila 2024" would "match" any answer mentioning
# Tequila), but they're injected at runtime from the corpus so this scales to
# whatever municipalities are ingested instead of hardcoding two.
_STOPWORDS = frozenset(
    {
        "de", "la", "el", "los", "las", "del", "y", "en", "por", "para", "con",
        "un", "una", "al", "lo", "su", "sus", "o", "e", "municipio",
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
    # Which answer style produced this (ciudadano | investigador). Echoed so the
    # UI can label the response and offer a "ver versión técnica" toggle.
    mode: str = DEFAULT_MODE


class AskAgent:
    def __init__(
        self,
        *,
        llm: LLMClient,
        search: SearchFn,
        max_iters: int = 5,
        corpus_overview: Callable[[], str] | None = None,
        corpus_municipalities: Callable[[], frozenset[str]] | None = None,
        router: Router | None = None,
    ):
        self._llm = llm
        self._search = search
        self._max_iters = max_iters
        # Optional cheap intent classifier. When set, greetings/off-topic skip the
        # search loop entirely. None = always search (original behavior).
        self._router = router
        # Returns a compact description of what's in the corpus (municipalities,
        # years, doc types). Appended to the system prompt so the agent scopes
        # searches to real data instead of guessing. Cached by the caller.
        self._corpus_overview = corpus_overview
        # Normalized municipality-name tokens, treated as citation stopwords so a
        # municipality in a doc title isn't mistaken for a citation. Dynamic so it
        # scales past the two municipalities in the current beta.
        self._corpus_municipalities = corpus_municipalities

    def ask(
        self,
        question: str,
        *,
        mode: str = DEFAULT_MODE,
        history: list[tuple[str, str]] | None = None,
    ) -> AskResult:
        mode = mode if mode in _SYSTEM_PROMPTS else DEFAULT_MODE

        # Route first: a greeting or off-topic question shouldn't pay for a search
        # loop. Only "search" falls through to the documents.
        if self._router is not None:
            route = self._router.classify(question, history)
            if route.intent != ROUTER_SEARCH:
                logger.info("ask: routed intent=%s, answered without search", route.intent)
                return AskResult(
                    answer=route.reply,
                    sources=[],
                    iterations=0,
                    model=self._router.model,
                    mode=mode,
                )

        messages = [ChatMessage(role="system", content=self._system_prompt(mode))]
        # Replay prior turns so follow-ups ("¿y en Tequila?") keep context.
        for prev_q, prev_a in (history or [])[-_HISTORY_TURNS:]:
            messages.append(ChatMessage(role="user", content=prev_q))
            messages.append(ChatMessage(role="assistant", content=prev_a))
        messages.append(ChatMessage(role="user", content=question))
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
                selected = _select_sources(answer, sources, self._muni_stopwords())
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
                    mode=mode,
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
            sources=_select_sources(answer, sources, self._muni_stopwords()),
            iterations=self._max_iters,
            model=self._llm.model,
            mode=mode,
        )

    def _muni_stopwords(self) -> frozenset[str]:
        if self._corpus_municipalities is None:
            return frozenset()
        try:
            return self._corpus_municipalities()
        except Exception:  # best-effort; fall back to title-only stopwords
            logger.warning("ask: corpus municipalities failed", exc_info=True)
            return frozenset()

    def _system_prompt(self, mode: str) -> str:
        prompt = _SYSTEM_PROMPTS[mode]
        if self._corpus_overview is None:
            return prompt
        try:
            overview = self._corpus_overview()
        except Exception:  # corpus query is best-effort; never break /ask over it
            logger.warning("ask: corpus overview failed", exc_info=True)
            return prompt
        return f"{prompt}\n\n{overview}" if overview else prompt

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
        municipality = (str(args.get("municipality")).strip() or None) if args.get("municipality") else None
        try:
            year = int(args["year"]) if args.get("year") is not None else None
        except (TypeError, ValueError):
            year = None
        # Log before the call, not just after: if search hangs (dead DB, slow
        # rerank) the "returned" line never prints, so without this a hang here
        # is invisible.
        logger.info(
            "ask: search q=%r local_only=%s municipality=%s year=%s",
            query, local_only, municipality, year,
        )
        hits = self._search(
            query=query,
            local_only=local_only,
            limit=_TOOL_HIT_LIMIT,
            municipality=municipality,
            year=year,
        )
        logger.info("ask: search returned %d hits", len(hits))
        return hits


def _select_sources(
    answer: str,
    sources: dict[str, tuple[float, Source]],
    muni_stopwords: frozenset[str] = frozenset(),
) -> list[Source]:
    """Keep the consulted documents the answer actually cites.

    Traceability fix: the final list must match the findings in the prose. A
    document counts as cited when a distinctive token of its title (a word >=4
    chars or a code like ``PE-298``/``COMUR_POA25``) appears in the answer. When
    nothing matches (model summarised without naming docs) fall back to the most
    relevant few so the list is never empty. ``muni_stopwords`` are the corpus's
    municipality names, dropped so they don't count as citation matches.
    """
    by_score = [s for _, s in sorted(sources.values(), key=lambda p: p[0], reverse=True)]
    answer_words = set(_norm(answer).split())
    answer_codes = _codes(answer)
    stop = _STOPWORDS | muni_stopwords
    cited = [s for s in by_score if _is_cited(answer_words, answer_codes, s, stop)]
    if cited:
        return cited[:_MAX_CITED]
    return by_score[:_FALLBACK_SOURCES]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _title_tokens(title: str, stopwords: frozenset[str] = _STOPWORDS) -> set[str]:
    # Distinctive words: drop stopwords and bare numbers (years collide across
    # documents); keep real words (>=4) and alphanumeric codes (poa25).
    out = set()
    for t in _norm(title).split():
        if t in stopwords or t.isdigit():
            continue
        if len(t) >= 4 or any(c.isdigit() for c in t):
            out.add(t)
    return out


def _codes(text: str) -> set[str]:
    # Compact identifiers like PE-298, COMUR_POA25, POA25 -> {"pe298","poa25"}.
    found = re.findall(r"[a-zA-Z]{2,}[-_ ]?\d{2,}|[A-Z]{2,}\d+", text)
    return {re.sub(r"[^a-z0-9]", "", m.lower()) for m in found}


def _is_cited(
    answer_words: set[str],
    answer_codes: set[str],
    src: Source,
    stopwords: frozenset[str] = _STOPWORDS,
) -> bool:
    for cand in (src.inferred_title, src.title):
        if not cand:
            continue
        if _title_tokens(cand, stopwords) & answer_words:
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
            # Relevance so the model can tell a strong hit from a weak one and
            # decide whether to re-search. Rerank score when present (a calibrated
            # cross-encoder logit), else the vector similarity.
            "relevancia": round(
                float(h.rerank_score if h.rerank_score is not None else h.score), 3
            ),
            "text": h.chunk.text[:_SNIPPET_CHARS],
        }
        for h in hits
    ]
    return json.dumps({"results": results}, ensure_ascii=False)
