# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Generate a readable, content-derived title for a document via the LLM.

Filenames in the portal are cryptic and unreliable (RegGilbertoTorres_…), so a
citation that leans on them earns no trust. This produces a human title from
the document's own text — run as a batch ingest job, not at request time.
"""
from __future__ import annotations

from .ports.llm import ChatMessage, LLMClient

_CONTEXT_CHARS = 2000  # first ~2k chars carry the heading/date; enough to title.
_MAX_TITLE_CHARS = 200

_SYSTEM_PROMPT = (
    "Genera un título descriptivo y conciso en español para un documento "
    "público municipal, basándote ÚNICAMENTE en su contenido. Incluye el tipo "
    "de documento (acta, presupuesto, reglamento, convocatoria…) y la "
    "fecha/periodo si son evidentes. Máximo 14 palabras. No inventes datos que "
    "no estén en el texto. Responde SÓLO con el título, sin comillas ni nada más."
)


def infer_title(
    llm: LLMClient,
    *,
    text: str,
    municipality: str | None = None,
    year: int | None = None,
) -> str:
    """Return a content-derived title, or "" if the text is empty/unusable."""
    snippet = text[:_CONTEXT_CHARS].strip()
    if not snippet:
        return ""
    hint = f"Municipio: {municipality or 'desconocido'}. Año conocido: {year or 'desconocido'}."
    user = f"{hint}\n\nContenido del documento:\n{snippet}"
    result = llm.chat(
        [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user),
        ],
        tools=None,
    )
    return _clean(result.content or "")


def _clean(raw: str) -> str:
    stripped = raw.strip()
    if not stripped:
        return ""
    # Models sometimes wrap the title in quotes or add a stray second line.
    first_line = stripped.splitlines()[0].strip()
    return first_line.strip("\"'").strip()[:_MAX_TITLE_CHARS]
