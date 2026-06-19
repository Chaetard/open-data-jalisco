# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""The jurisdiction heuristic, checked against real Tala-portal titles."""
import pytest

from open_data_jalisco.domain.jurisdiction import (
    FEDERAL,
    MUNICIPAL,
    STATE,
    UNKNOWN,
    infer_jurisdiction,
)


@pytest.mark.parametrize(
    "title,expected",
    [
        # State of Jalisco budget volumes — the docs that crowd out Tala's own.
        # Note the CamelCase concatenation: the substring match must still fire.
        ("PresupuestoJaliscoVolVI-2023", STATE),
        ("PresupuestoJaliscoVolV-2024", STATE),
        ("Periódico Oficial El Estado de Jalisco", STATE),
        ("PARTICIPACIONES A MUNICIPIOS DEL ESTADO DE JALISCO", STATE),
        # Federal laws — "y los municipios" must NOT pull them to municipal.
        ("LEY DE DISCIPLINA FINANCIERA DE LAS ENTIDADES FEDERATIVAS Y LOS MUNICIPIOS", FEDERAL),
        ("LEY GENERAL DE TRANSPARENCIA", FEDERAL),
        # Municipal: explicit Tala / municipio / municipal markers.
        ("Leyes de Ingreso Tala 2022", MUNICIPAL),
        ("REGLAMENTO DE LA ADMINISTRACION PUBLICA MUNICIPAL", MUNICIPAL),
        ("REGLAMENTO DE PARTICIPACIÓN CIUDADANA DEL MUNICIPIO DE TALA", MUNICIPAL),
        # No marker → honest UNKNOWN (kept by local_only, never wrongly hidden).
        ("Ingresos_EstadisticaTrimestral_Oct-Dic25", UNKNOWN),
        ("", UNKNOWN),
        (None, UNKNOWN),
    ],
)
def test_infer_jurisdiction(title, expected):
    assert infer_jurisdiction(title) == expected
