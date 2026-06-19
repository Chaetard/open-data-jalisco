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

ponytail: title-pattern heuristic with a known ceiling, not a classifier. It is
deliberately high-precision on STATE/FEDERAL (the material to hide) and falls
back to UNKNOWN rather than guessing MUNICIPAL — a terse operational title with
no marker stays UNKNOWN and is kept by the "local only" filter. Upgrade path: an
explicit ingest-time field or a trained classifier if the patterns stop holding.
"""
from __future__ import annotations

import re

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
# Explicit local markers. "Tala" or an ayuntamiento/edilicio term pins a
# document to the municipality even if a state name also appears.
_LOCAL = re.compile(
    r"\btala\b|ayuntamiento|edilici|gaceta municipal|municipio de",
    re.IGNORECASE,
)
_MUNICIPAL_WORD = re.compile(r"municip", re.IGNORECASE)


def infer_jurisdiction(title: str | None) -> str:
    if not title:
        return UNKNOWN
    if _FEDERAL.search(title):
        return FEDERAL
    has_local = bool(_LOCAL.search(title))
    has_state = bool(_STATE.search(title))
    # Explicit local marker beats a bare "Jalisco": "Leyes de Ingreso Tala" is
    # municipal even though the state enacts it for the municipality.
    if has_local:
        return MUNICIPAL
    if has_state:
        return STATE
    if _MUNICIPAL_WORD.search(title):
        return MUNICIPAL
    return UNKNOWN
