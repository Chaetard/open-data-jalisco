# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Search reranking + local_only jurisdiction filter, wired through the app.

Uses a fake reranker so nothing is downloaded and CI stays offline.
"""
from fastapi.testclient import TestClient

from open_data_jalisco.api.app import create_app
from open_data_jalisco.api.deps import (
    get_chunk_repository,
    get_document_repository,
    get_embedding_provider,
    get_reranker,
)

from ._api_helpers import FakeChunkRepo, FakeDocRepo, FakeEmbedder, make_chunk, make_document

STATE_TITLE = "PresupuestoJaliscoVolV-2024"
FEDERAL_TITLE = "LEY GENERAL DE TRANSPARENCIA"
MUNICIPAL_TITLE = "PRESUPUESTO CIUDADANO MUNICIPAL DE TALA"


class FakeReranker:
    name = "fake_rerank"
    model = "fake-rerank-v1"

    def rerank(self, query: str, passages: list[str]) -> list[float]:
        # Municipal budget wins, state second, federal last — regardless of the
        # order the vector stage produced.
        out = []
        for p in passages:
            if "CIUDADANO" in p:
                out.append(5.0)
            elif "jalisco" in p.lower():
                out.append(1.0)
            else:
                out.append(0.0)
        return out


def _client(*, reranker) -> TestClient:
    # Vector stage hands back state, federal, municipal in that (bad) order.
    docs = [
        make_document(title=STATE_TITLE),
        make_document(title=FEDERAL_TITLE),
        make_document(title=MUNICIPAL_TITLE),
    ]
    chunks = [make_chunk(d, text=f"body of {d.title}") for d in docs]
    app = create_app()
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbedder()
    app.dependency_overrides[get_chunk_repository] = lambda: FakeChunkRepo(chunks)
    app.dependency_overrides[get_document_repository] = lambda: FakeDocRepo(docs)
    app.dependency_overrides[get_reranker] = lambda: reranker
    return TestClient(app)


def test_documents_carry_jurisdiction_badge():
    client = _client(reranker=None)
    body = client.post("/search", json={"q": "presupuesto", "local_only": False}).json()
    by_title = {h["document"]["title"]: h["document"]["jurisdiction"] for h in body["hits"]}
    assert by_title[STATE_TITLE] == "state"
    assert by_title[FEDERAL_TITLE] == "federal"
    assert by_title[MUNICIPAL_TITLE] == "municipal"


def test_hybrid_fuses_lexical_above_misses_when_no_reranker():
    # With no reranker the RRF fusion decides order. FEDERAL_TITLE's chunk text
    # has no "presupuesto", so only the vector arm surfaces it; the two lexical
    # matches (state + municipal budgets) fuse above it.
    client = _client(reranker=None)
    body = client.post("/search", json={"q": "presupuesto", "local_only": False}).json()
    assert body["reranker"] is None
    titles = [h["document"]["title"] for h in body["hits"]]
    assert set(titles) == {STATE_TITLE, FEDERAL_TITLE, MUNICIPAL_TITLE}
    assert titles.index(STATE_TITLE) < titles.index(FEDERAL_TITLE)
    assert titles.index(MUNICIPAL_TITLE) < titles.index(FEDERAL_TITLE)
    assert all(h["rerank_score"] is None for h in body["hits"])


def test_reranker_reorders_and_reports_scores():
    client = _client(reranker=FakeReranker())
    body = client.post(
        "/search", json={"q": "presupuesto municipal", "local_only": False}
    ).json()
    assert body["reranker"] == "fake-rerank-v1"
    titles = [h["document"]["title"] for h in body["hits"]]
    assert titles == [MUNICIPAL_TITLE, STATE_TITLE, FEDERAL_TITLE]
    assert body["hits"][0]["rerank_score"] == 5.0
    scores = [h["rerank_score"] for h in body["hits"]]
    assert scores == sorted(scores, reverse=True)


def test_state_and_federal_hidden_by_default():
    # local_only defaults to true: the state budget / federal law are noise and
    # must not appear unless the caller explicitly asks for the full corpus.
    client = _client(reranker=None)
    body = client.post("/search", json={"q": "presupuesto"}).json()
    titles = [h["document"]["title"] for h in body["hits"]]
    assert titles == [MUNICIPAL_TITLE]


def test_local_only_false_includes_reference_material():
    client = _client(reranker=None)
    body = client.post("/search", json={"q": "presupuesto", "local_only": False}).json()
    titles = {h["document"]["title"] for h in body["hits"]}
    assert STATE_TITLE in titles
    assert FEDERAL_TITLE in titles
