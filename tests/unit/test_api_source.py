# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from fastapi.testclient import TestClient

from open_data_jalisco import __version__
from open_data_jalisco.api.app import create_app


def test_source_endpoint_returns_repository_and_license():
    client = TestClient(create_app())
    response = client.get("/source")
    assert response.status_code == 200
    body = response.json()
    assert body["repository"] == "https://github.com/Chaetard/open-data-jalisco"
    assert body["license"] == "AGPL-3.0-or-later"
    assert body["version"] == __version__
    assert "commit" in body


def test_source_endpoint_exposes_commit_when_env_set(monkeypatch):
    monkeypatch.setenv("SOURCE_COMMIT", "deadbeef")
    client = TestClient(create_app())
    response = client.get("/source")
    assert response.json()["commit"] == "deadbeef"
