# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Cheap intent router run before the expensive ReAct loop.

One small-model call classifies the question into ``search`` (needs the
documents → run the agent), ``chitchat`` (greeting / "what are you") or
``out_of_scope``. For the non-search intents the same call also returns a short
user-facing reply, so a greeting costs one cheap call instead of a full search
loop. Anything ambiguous, or any failure, defaults to ``search`` — never refuse
a real question because the router hiccuped.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from ..ports.llm import ChatMessage, LLMClient
from ..shared.logging import get_logger

logger = get_logger(__name__)

SEARCH = "search"
_VALID = {"search", "chitchat", "out_of_scope"}
# Only the last couple of turns matter for "is this a follow-up search?".
_HISTORY_TURNS = 2

_SYSTEM = (
    "Eres el enrutador de un asistente de transparencia sobre documentos "
    "públicos de municipios de Jalisco. Clasifica el ÚLTIMO mensaje del usuario "
    "y responde SÓLO con JSON válido, sin texto adicional ni markdown, con la "
    'forma: {"intent": "...", "reply": "..."}\n'
    "\n"
    "Intenciones:\n"
    '- "search": pide algo que requiere consultar los documentos (trámites, '
    "presupuestos, reglamentos, actas, contratos, montos, fechas, funcionarios, "
    'etc.). Ante la duda, usa "search". Para "search" deja "reply" vacío.\n'
    '- "chitchat": saludo, agradecimiento o pregunta sobre qué eres o qué puedes '
    'hacer. En "reply" responde breve y amable en español, invitando a preguntar '
    "sobre los documentos públicos municipales.\n"
    '- "out_of_scope": claramente ajeno (no son documentos públicos de Jalisco: '
    'recetas, programación, opiniones, etc.). En "reply" redirige con cortesía a '
    "lo que sí cubre el asistente.\n"
    "\n"
    "Usa el historial: un seguimiento como «¿y en Tequila?» o «¿de qué año?» es "
    '"search".'
)


@dataclass
class Route:
    intent: str
    reply: str = ""


class Router:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    @property
    def model(self) -> str:
        return self._llm.model

    def classify(self, question: str, history: list[tuple[str, str]] | None = None) -> Route:
        messages = [ChatMessage(role="system", content=_SYSTEM)]
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
    # Non-search must carry a reply; without one, search is the safe fallback.
    if intent not in _VALID or intent == SEARCH or not reply:
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
