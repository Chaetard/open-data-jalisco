# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Heuristic jurisdiction inference for republished documents.

A municipal transparency portal (e.g. Tala) is legally required to ALSO
republish state and federal reference material: the Jalisco state budget,
federal laws, etc. All of it is ingested tagged ``municipality="Tala"``, so
metadata alone can't tell "Tala's own act" from "a state/federal document Tala
merely hosts". Searching "presupuesto municipal" then surfaces the multi-volume
*state* budget above Tala's own, which is not what a citizen browsing Tala
wants.

We infer the level of government from the document title so search can offer a
"local only" scope (hide state/federal reference material).

Municipality names are NOT hardcoded. The caller passes ``local_markers`` — the
names of the municipalities actually present in the corpus — so the heuristic
recognises every ingested municipality (Tala, Tequila, the next hundred) instead
of assuming a single pilot. Generic structural markers (ayuntamiento, "municipio
de", a municipal gazette) are corpus-independent and stay built in.

ponytail: title-pattern heuristic with a known ceiling, not a classifier. It is
deliberately high-precision on STATE/FEDERAL (the material to hide) and falls
back to UNKNOWN rather than guessing MUNICIPAL — a terse operational title with
no marker stays UNKNOWN and is kept by the "local only" filter. Upgrade path: an
explicit ingest-time field or a trained classifier if the patterns stop holding.
"""
from __future__ import annotations

import re
from functools import lru_cache

MUNICIPAL = "municipal"
STATE = "state"
FEDERAL = "federal"
UNKNOWN = "unknown"

# A federal law that mentions "municipios" is still federal, so this is checked
# first and wins over the other markers.
_FEDERAL = re.compile(
    r"ley general|entidades federativas|federaci[oó]n|\bfederal(es)?\b|"
    r"constituci[oó]n pol[ií]tica de los estados unidos|"
    r"diario oficial de la federaci[oó]n",
    re.IGNORECASE,
)
# State-of-Jalisco markers. "jalisco" is matched as a substring on purpose:
# real titles concatenate it CamelCase ("PresupuestoJaliscoVolVI"), where a word
# boundary would never fire.
_STATE = re.compile(
    r"jalisco|del estado|\bestatal\b|peri[oó]dico oficial",
    re.IGNORECASE,
)
# Corpus-independent structural markers: an ayuntamiento/edilicio body, a
# municipal gazette, or "municipio de ..." pins a title to its municipality
# without naming one. Place names come from the corpus (see _markers_pattern).
_LOCAL_STRUCTURAL = re.compile(
    r"ayuntamiento|edilici|gaceta municipal|municipio de",
    re.IGNORECASE,
)
_MUNICIPAL_WORD = re.compile(r"municip", re.IGNORECASE)


@lru_cache(maxsize=32)
def _markers_pattern(markers: frozenset[str]) -> re.Pattern[str] | None:
    """Word-boundary regex matching any corpus municipality name.

    Cached on the (hashable) frozenset so it recompiles only when the set of
    ingested municipalities changes — not once per chunk. Names are escaped so a
    multi-word municipality ("San Pedro Tlaquepaque") matches literally.
    """
    names = sorted({m.strip().lower() for m in markers if m and m.strip()})
    if not names:
        return None
    alternation = "|".join(re.escape(n) for n in names)
    return re.compile(rf"\b({alternation})\b", re.IGNORECASE)


def infer_jurisdiction(
    title: str | None, local_markers: frozenset[str] = frozenset()
) -> str:
    if not title:
        return UNKNOWN
    if _FEDERAL.search(title):
        return FEDERAL
    pattern = _markers_pattern(local_markers)
    has_local = bool(_LOCAL_STRUCTURAL.search(title)) or (
        pattern is not None and bool(pattern.search(title))
    )
    has_state = bool(_STATE.search(title))
    # An explicit local marker (structural, or a corpus municipality name) beats
    # a bare "Jalisco": "Egresos Tequila Jalisco 2024" is municipal, not state.
    if has_local:
        return MUNICIPAL
    if has_state:
        return STATE
    if _MUNICIPAL_WORD.search(title):
        return MUNICIPAL
    return UNKNOWN
