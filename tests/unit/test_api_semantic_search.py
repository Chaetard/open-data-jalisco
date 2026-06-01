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


def test_post_semantic_search_returns_hits():
    doc = make_document()
    chunk = make_chunk(doc)
    app = create_app()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbedder()
    app.dependency_overrides[get_chunk_repository] = lambda: FakeChunkRepo([chunk])
    app.dependency_overrides[get_document_repository] = lambda: FakeDocRepo([doc])

    client = TestClient(app)
    res = client.post("/semantic-search", json={"q": "anything", "limit": 5})
    assert res.status_code == 200
    body = res.json()
    assert body["query"] == "anything"
    assert body["embedding_provider"] == "fake"
    assert len(body["hits"]) == 1


def test_post_semantic_search_rejects_short_query():
    app = create_app()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbedder()
    app.dependency_overrides[get_chunk_repository] = lambda: FakeChunkRepo([])
    app.dependency_overrides[get_document_repository] = lambda: FakeDocRepo([])

    client = TestClient(app)
    res = client.post("/semantic-search", json={"q": "a"})
    assert res.status_code == 422
