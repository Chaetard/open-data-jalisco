# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Answering agent endpoint.

POST a question; the agent searches the municipal documents (possibly several
times), reasons, and replies with a grounded answer plus the documents it used.
Disabled (503) unless ``LLM_API_KEY`` is set — the rest of the API is unaffected.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...agent import AskAgent
from ..deps import get_ask_agent

router = APIRouter(tags=["agent"])


class AskRequest(BaseModel):
    question: str = Field(min_length=3, description="Natural-language question")


class AskSource(BaseModel):
    title: str | None
    url: str
    page_start: int | None
    page_end: int | None
    jurisdiction: str


class AskResponse(BaseModel):
    answer: str
    model: str
    iterations: int
    sources: list[AskSource]


@router.post("/ask", response_model=AskResponse)
def ask(
    body: AskRequest,
    agent: AskAgent | None = Depends(get_ask_agent),
) -> AskResponse:
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="Agent not configured. Set LLM_API_KEY (and optionally LLM_MODEL).",
        )
    result = agent.ask(body.question)
    return AskResponse(
        answer=result.answer,
        model=result.model,
        iterations=result.iterations,
        sources=[
            AskSource(
                title=s.title,
                url=s.url,
                page_start=s.page_start,
                page_end=s.page_end,
                jurisdiction=s.jurisdiction,
            )
            for s in result.sources
        ],
    )
