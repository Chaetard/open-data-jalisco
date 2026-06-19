# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Every request leaves a start and a done log line (the observability we lacked)."""
import logging

from fastapi.testclient import TestClient

from open_data_jalisco.api.app import create_app


def test_requests_are_logged(caplog):
    app = create_app()
    with caplog.at_level(logging.INFO, logger="open_data_jalisco.api.app"):
        res = TestClient(app).get("/health")
    assert res.status_code == 200
    msgs = [r.getMessage() for r in caplog.records]
    assert any("request start GET /health" in m for m in msgs)
    assert any("request done GET /health 200" in m for m in msgs)
