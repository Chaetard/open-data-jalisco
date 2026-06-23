# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Answering agent endpoint.

POST a question; the agent searches the municipal documents (possibly several
times), reasons, and replies with a grounded answer plus the documents it used.
Disabled (503) unless ``LLM_API_KEY`` is set — the rest of the API is unaffected.
"""
import json
from collections.abc import Iterator
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...agent import AskAgent
from ...ports.llm import LLMError
from ...shared.logging import get_logger
from ..deps import get_ask_agent

logger = get_logger(__name__)

router = APIRouter(tags=["agent"])


def _sse(event: dict) -> str:
    """Serialize one event as a Server-Sent Events frame."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


class HistoryTurn(BaseModel):
    question: str
    answer: str


class AskRequest(BaseModel):
    question: str = Field(min_length=3, description="Natural-language question")
    # Answer style. `ciudadano` (default): plain language, action-oriented.
    # `investigador`: full technical traceability (rows/columns, partidas).
    mode: Literal["ciudadano", "investigador"] = "ciudadano"
    # Prior Q→A pairs from this browser session, sent by the client so follow-ups
    # keep context. Stateless server: no chats are stored. Only the last few are
    # replayed (the agent caps them) so payloads stay small.
    history: list[HistoryTurn] = Field(default_factory=list)


class AskSource(BaseModel):
    title: str | None
    # Readable display title — prefer over `title`. The LLM content-derived one
    # when it exists, else a deterministic (no-LLM) provisional cleaned from the
    # filename.
    inferred_title: str | None = None
    url: str
    page_start: int | None
    page_end: int | None
    jurisdiction: str
    # Verifiable quote the citation rests on — trust the content, not the
    # (filename-derived, unreliable) title.
    excerpt: str


class AskResponse(BaseModel):
    answer: str
    model: str
    # Which answer style produced this (echoes the request; lets the UI badge it
    # and offer a "ver versión técnica" toggle).
    mode: str
    iterations: int
    sources: list[AskSource]


@router.post("/ask", response_model=AskResponse)
def ask(
    body: AskRequest,
    agent: AskAgent | None = Depends(get_ask_agent),  # noqa: B008
) -> AskResponse:
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="Agent not configured. Set LLM_API_KEY (and optionally LLM_MODEL).",
        )
    try:
        result = agent.ask(
            body.question,
            mode=body.mode,
            history=[(h.question, h.answer) for h in body.history],
        )
    except LLMError as e:
        # Upstream model failed - return its reason as a clean 502 instead of a
        # 500 ASGI traceback.
        raise HTTPException(status_code=502, detail=f"Upstream LLM error: {e}") from e
    return AskResponse(
        answer=result.answer,
        model=result.model,
        mode=result.mode,
        iterations=result.iterations,
        sources=[
            AskSource(
                title=s.title,
                inferred_title=s.inferred_title,
                url=s.url,
                page_start=s.page_start,
                page_end=s.page_end,
                jurisdiction=s.jurisdiction,
                excerpt=s.excerpt,
            )
            for s in result.sources
        ],
    )


@router.post("/ask/stream")
def ask_stream(
    body: AskRequest,
    agent: AskAgent | None = Depends(get_ask_agent),  # noqa: B008
) -> StreamingResponse:
    """Same as ``/ask`` but streams the agent's real activity as Server-Sent
    Events: a ``step`` event per tool call (searching, reading, …) and a final
    ``answer`` event with the grounded response and its sources.
    """
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="Agent not configured. Set LLM_API_KEY (and optionally LLM_MODEL).",
        )

    history = [(h.question, h.answer) for h in body.history]

    def event_source() -> Iterator[str]:
        gen = agent.ask_stream(body.question, mode=body.mode, history=history)
        try:
            while True:
                yield _sse(next(gen))
        except StopIteration as stop:
            result = stop.value
            yield _sse(
                {
                    "type": "answer",
                    "answer": result.answer,
                    "model": result.model,
                    "mode": result.mode,
                    "iterations": result.iterations,
                    "sources": [
                        {
                            "title": s.title,
                            "inferred_title": s.inferred_title,
                            "url": s.url,
                            "page_start": s.page_start,
                            "page_end": s.page_end,
                            "jurisdiction": s.jurisdiction,
                            "excerpt": s.excerpt,
                        }
                        for s in result.sources
                    ],
                }
            )
        except LLMError as e:
            yield _sse({"type": "error", "detail": f"Upstream LLM error: {e}"})
        except Exception:  # noqa: BLE001 — never leak a traceback into the stream
            logger.exception("ask/stream: agent failed")
            yield _sse({"type": "error", "detail": "El asistente tuvo un problema. Intenta de nuevo."})

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
