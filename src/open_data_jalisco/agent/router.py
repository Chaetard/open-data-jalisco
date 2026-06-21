# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Cheap intent router run before the expensive ReAct loop.

One small-model call classifies the question into four intents:

- ``search``: a COMPLEX question that needs several document lookups / comparisons
  → run the full agent loop.
- ``simple``: a FACTUAL, narrow question answerable with ONE quick search → run the
  agent but with a tight iteration budget so it stays fast.
- ``chitchat``: greeting / "what can you do" → the router answers directly, and its
  reply recommends what to ask, naming the data that actually exists.
- ``out_of_scope``: clearly unrelated → a polite redirect.

``search`` and ``simple`` carry no reply (the agent handles them); ``chitchat`` and
``out_of_scope`` must carry one. Anything ambiguous, or any failure, defaults to
``search`` — never refuse a real question because the router hiccuped.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from ..ports.llm import ChatMessage, LLMClient
from ..shared.logging import get_logger

logger = get_logger(__name__)

SEARCH = "search"
SIMPLE = "simple"
# search/simple are handled by the agent (which searches); chitchat/out_of_scope
# are answered by the router's own reply.
_AGENT_INTENTS = frozenset({SEARCH, SIMPLE})
_VALID = frozenset({SEARCH, SIMPLE, "chitchat", "out_of_scope"})
# Only the last couple of turns matter for "is this a follow-up?".
_HISTORY_TURNS = 2

_SYSTEM = (
    "Eres el enrutador de un asistente de transparencia sobre documentos "
    "públicos de municipios de Jalisco. Clasifica el ÚLTIMO mensaje del usuario "
    "y responde SÓLO con JSON válido, sin texto adicional ni markdown, con la "
    'forma: {"intent": "...", "reply": "..."}\n'
    "\n"
    "Intenciones:\n"
    '- "search": pregunta COMPLEJA que exige consultar o comparar varios '
    "documentos, cifras, periodos o pasos (comparar presupuestos, rastrear "
    'ejecución, varios años, análisis). Deja "reply" vacío.\n'
    '- "simple": pregunta FACTUAL y acotada que se resuelve con UNA búsqueda '
    "rápida (p.ej. «¿quién es el presidente municipal?», «¿qué días atiende "
    "catastro?», «¿teléfono de transparencia?», «¿cuánto cuesta un acta?»). Deja "
    '"reply" vacío. Ante la duda entre simple y search, usa "search".\n'
    '- "chitchat": saludo, agradecimiento o «¿qué puedes hacer?». En "reply" '
    "saluda BREVE y recomienda qué preguntar, MENCIONANDO los datos que de verdad "
    "existen (municipios, años y tipos del PANORAMA DEL CORPUS si aparece abajo). "
    "No inventes cobertura.\n"
    '- "out_of_scope": claramente ajeno (recetas, programación, opiniones). En '
    '"reply" redirige con cortesía a lo que sí cubre el asistente.\n'
    "\n"
    "Usa el historial: un seguimiento como «¿y en Tequila?» o «¿de qué año?» "
    "hereda la intención previa (normalmente search o simple).\n"
    "NUNCA contestes tú mismo datos sustantivos (montos, nombres, fechas): para "
    "eso están search/simple, que sí buscan en los documentos."
)


@dataclass
class Route:
    intent: str
    reply: str = ""


class Router:
    def __init__(
        self,
        llm: LLMClient,
        corpus_overview: Callable[[], str] | None = None,
    ):
        self._llm = llm
        # Same compact corpus description the agent uses; appended so chitchat
        # replies recommend real municipalities/years/types instead of guessing.
        self._corpus_overview = corpus_overview

    @property
    def model(self) -> str:
        return self._llm.model

    def _system_prompt(self) -> str:
        if self._corpus_overview is None:
            return _SYSTEM
        try:
            overview = self._corpus_overview()
        except Exception:  # best-effort; a router without data still classifies
            logger.warning("router: corpus overview failed", exc_info=True)
            return _SYSTEM
        return f"{_SYSTEM}\n\n{overview}" if overview else _SYSTEM

    def classify(self, question: str, history: list[tuple[str, str]] | None = None) -> Route:
        messages = [ChatMessage(role="system", content=self._system_prompt())]
        for prev_q, prev_a in (history or [])[-_HISTORY_TURNS:]:
            messages.append(ChatMessage(role="user", content=prev_q))
            messages.append(ChatMessage(role="assistant", content=prev_a))
        messages.append(ChatMessage(role="user", content=question))
        try:
            result = self._llm.chat(messages, tools=None)
        except Exception:  # network/quota/timeout — don't block the real answer
            logger.warning("router: classify failed, defaulting to search", exc_info=True)
            return Route(SEARCH)
        route = _parse(result.content or "")
        logger.info("router: intent=%s", route.intent)
        return route


def _parse(content: str) -> Route:
    try:
        data = json.loads(_extract_json(content))
        intent = str(data.get("intent", "")).strip().lower()
        reply = str(data.get("reply", "")).strip()
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        logger.warning("router: unparseable %r, defaulting to search", content[:200])
        return Route(SEARCH)
    if intent not in _VALID:
        return Route(SEARCH)
    # Agent intents (search/simple) don't need a reply; the agent answers.
    if intent in _AGENT_INTENTS:
        return Route(intent)
    # chitchat/out_of_scope must carry a reply; without one, search is safe.
    if not reply:
        return Route(SEARCH)
    return Route(intent, reply)


def _extract_json(text: str) -> str:
    """Tolerate ```json fences and surrounding prose; grab the first {...} block."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
    start, end = t.find("{"), t.rfind("}")
    return t[start : end + 1] if start != -1 and end > start else t
