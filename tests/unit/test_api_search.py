# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from fastapi.testclient import TestClient

from open_data_jalisco.api.app import create_app
from open_data_jalisco.api.deps import (
    get_chunk_repository,
    get_document_repository,
    get_embedding_provider,
)

from ._api_helpers import FakeChunkRepo, FakeDocRepo, FakeEmbedder, make_chunk, make_document


def _client_with_one_hit() -> TestClient:
    doc = make_document()
    chunk = make_chunk(doc)
    app = create_app()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbedder()
    app.dependency_overrides[get_chunk_repository] = lambda: FakeChunkRepo([chunk])
    app.dependency_overrides[get_document_repository] = lambda: FakeDocRepo([doc])
    return TestClient(app)


def test_post_search_returns_hits_with_request_body():
    client = _client_with_one_hit()
    res = client.post("/search", json={"q": "anything", "limit": 5})
    assert res.status_code == 200
    body = res.json()
    assert body["query"] == "anything"
    assert body["embedding_provider"] == "fake"
    assert body["embedding_dimension"] == 4
    assert len(body["hits"]) == 1
    hit = body["hits"][0]
    assert hit["score"] > 0
    assert hit["chunk"]["text"] == "Sample chunk text"
    assert hit["document"]["title"] == "Sample document"


def test_post_search_rejects_short_query():
    client = _client_with_one_hit()
    res = client.post("/search", json={"q": "a"})
    assert res.status_code == 422


def test_post_search_accepts_filters():
    client = _client_with_one_hit()
    res = client.post(
        "/search",
        json={
            "q": "anything",
            "limit": 3,
            "municipality": "Example",
            "document_type": "other",
        },
    )
    assert res.status_code == 200


def test_get_search_still_works_for_compat():
    client = _client_with_one_hit()
    res = client.get("/search", params={"q": "anything"})
    assert res.status_code == 200
    assert len(res.json()["hits"]) == 1
