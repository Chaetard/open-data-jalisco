# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""The jurisdiction heuristic. Municipality names are injected (the corpus's
real municipalities), never hardcoded, so it scales past the pilot towns."""
import pytest

from open_data_jalisco.domain.jurisdiction import (
    FEDERAL,
    MUNICIPAL,
    STATE,
    UNKNOWN,
    infer_jurisdiction,
)

# Stand-in for the corpus municipalities deps.corpus_local_markers() supplies.
CORPUS = frozenset({"tala", "tequila", "san pedro tlaquepaque"})


@pytest.mark.parametrize(
    "title,markers,expected",
    [
        # State of Jalisco budget volumes — the docs that crowd out a town's own.
        # Note the CamelCase concatenation: the substring match must still fire.
        ("PresupuestoJaliscoVolVI-2023", CORPUS, STATE),
        ("PresupuestoJaliscoVolV-2024", CORPUS, STATE),
        ("Periódico Oficial El Estado de Jalisco", CORPUS, STATE),
        ("PARTICIPACIONES A MUNICIPIOS DEL ESTADO DE JALISCO", CORPUS, STATE),
        # Federal laws — "y los municipios" must NOT pull them to municipal, and a
        # corpus name in the title must not override FEDERAL (checked first).
        ("LEY DE DISCIPLINA FINANCIERA DE LAS ENTIDADES FEDERATIVAS Y LOS MUNICIPIOS", CORPUS, FEDERAL),
        ("LEY GENERAL DE TRANSPARENCIA", CORPUS, FEDERAL),
        # Municipal via corpus-independent structural markers (no place name).
        ("REGLAMENTO DE LA ADMINISTRACION PUBLICA MUNICIPAL", frozenset(), MUNICIPAL),
        ("REGLAMENTO DE PARTICIPACIÓN CIUDADANA DEL MUNICIPIO DE TALA", frozenset(), MUNICIPAL),
        # Municipal via an injected corpus name — works for ANY ingested town,
        # not just the original pilot. This is the de-hardcoding payoff.
        ("Leyes de Ingreso Tala 2022", CORPUS, MUNICIPAL),
        ("Presupuesto de Egresos Tequila Jalisco 2024", CORPUS, MUNICIPAL),
        ("Acta San Pedro Tlaquepaque 2023", CORPUS, MUNICIPAL),
        # Same Tequila title WITHOUT the marker falls back to the state badge —
        # proof the injected name is what pins it; nothing is hardcoded.
        ("Presupuesto de Egresos Tequila Jalisco 2024", frozenset(), STATE),
        # No marker → honest UNKNOWN (kept by local_only, never wrongly hidden).
        ("Ingresos_EstadisticaTrimestral_Oct-Dic25", CORPUS, UNKNOWN),
        ("", CORPUS, UNKNOWN),
        (None, CORPUS, UNKNOWN),
    ],
)
def test_infer_jurisdiction(title, markers, expected):
    assert infer_jurisdiction(title, markers) == expected


def test_default_markers_are_empty_and_safe():
    # Called with just a title (schemas.document_to_out path): no place names,
    # structural markers still classify, no crash.
    assert infer_jurisdiction("PRESUPUESTO MUNICIPAL") == MUNICIPAL
    assert infer_jurisdiction("PresupuestoJaliscoVolV-2024") == STATE
