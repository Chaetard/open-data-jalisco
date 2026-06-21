# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Generate a readable, content-derived title for a document via the LLM.

Filenames in the portal are cryptic and unreliable (RegGilbertoTorres_…), so a
citation that leans on them earns no trust. This produces a human title from
the document's own text — run as a batch ingest job, not at request time.
"""
from __future__ import annotations

import re

from .ports.llm import ChatMessage, LLMClient

_CONTEXT_CHARS = 2000  # first ~2k chars carry the heading/date; enough to title.
_MAX_TITLE_CHARS = 200

_PROVISIONAL_MAX = 120
# Spanish connectors lowercased after title-casing so an ALL-CAPS filename reads
# naturally: "...DE DESARROLLO Y GOBERNANZA" -> "...de Desarrollo y Gobernanza".
_CONNECTORS = frozenset(
    {"de", "del", "la", "el", "los", "las", "y", "e", "o", "u",
     "en", "para", "por", "con", "a", "al"}
)
_EXT = re.compile(r"\.(pdf|xlsx?|docx?|csv|html?|txt|json)$", re.IGNORECASE)


def provisional_title(raw: str | None) -> str | None:
    """Cheap, deterministic readable title from a filename-derived one.

    NO LLM / no AI / no network — pure regex + string ops, zero cost. A display
    fallback for the chat when the real content-derived ``inferred_title`` hasn't
    been generated. Drops file extensions, leading index/date numbering and
    separator noise, and folds ALL-CAPS / all-lowercase filenames to Title Case.
    Returns None when nothing usable remains. The LLM ``infer_title`` (which DOES
    cost calls) still overrides it whenever it has run.
    """
    if not raw:
        return None
    s = _EXT.sub("", raw.strip())
    s = re.sub(r"[_\-]+", " ", s)                       # separators -> spaces
    s = re.sub(r"^\s*\d{1,2}\s+\d{1,2}\s+\d{2,4}\s+", "", s)  # leading dd dd yy date
    s = re.sub(r"^\s*\d+[.\)]?\s+", "", s)              # leading "33." / "01)" / "7 "
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return None
    # Only normalise case when the author gave none (shouting caps or all lower);
    # leave intentionally mixed-case titles alone.
    if s.isupper() or s.islower():
        words = s.split()
        s = " ".join(
            w.lower() if i > 0 and w.lower() in _CONNECTORS else w.capitalize()
            for i, w in enumerate(words)
        )
    s = re.sub(r"\s+[A-Za-z]$", "", s).strip()          # drop truncated 1-char tail
    return s[:_PROVISIONAL_MAX] or None

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
