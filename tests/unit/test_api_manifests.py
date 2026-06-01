# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

import json
from pathlib import Path

from fastapi.testclient import TestClient

from open_data_jalisco.api.app import create_app
from open_data_jalisco.api.deps import get_manifests_dir


def _write_manifest(directory: Path, slug: str, *, doc_count: int = 2) -> None:
    manifest = {
        "dataset": f"open-data-jalisco/{slug}",
        "municipality": "Example",
        "source": {
            "slug": slug,
            "name": f"{slug} source",
            "kind": "other",
            "official_url": "https://example.invalid/",
        },
        "generated_at": "2024-01-01T00:00:00+00:00",
        "pipeline_version": "0.1.0",
        "document_count": doc_count,
        "documents": [],
    }
    (directory / f"{slug}.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def test_get_manifests_returns_summaries(tmp_path: Path):
    _write_manifest(tmp_path, "alpha", doc_count=3)
    _write_manifest(tmp_path, "beta", doc_count=7)

    app = create_app()
    app.dependency_overrides[get_manifests_dir] = lambda: tmp_path

    client = TestClient(app)
    res = client.get("/manifests")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 2

    by_slug = {item["source_slug"]: item for item in body}
    assert by_slug["alpha"]["document_count"] == 3
    assert by_slug["beta"]["document_count"] == 7
    assert by_slug["alpha"]["pipeline_version"] == "0.1.0"


def test_get_manifests_filter_by_source_slug(tmp_path: Path):
    _write_manifest(tmp_path, "alpha")
    _write_manifest(tmp_path, "beta")

    app = create_app()
    app.dependency_overrides[get_manifests_dir] = lambda: tmp_path

    client = TestClient(app)
    res = client.get("/manifests", params={"source_slug": "beta"})
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["source_slug"] == "beta"


def test_get_manifests_empty_when_dir_missing(tmp_path: Path):
    missing = tmp_path / "does-not-exist"

    app = create_app()
    app.dependency_overrides[get_manifests_dir] = lambda: missing

    client = TestClient(app)
    res = client.get("/manifests")
    assert res.status_code == 200
    assert res.json() == []


def test_get_manifests_skips_invalid_json(tmp_path: Path):
    _write_manifest(tmp_path, "alpha")
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    app = create_app()
    app.dependency_overrides[get_manifests_dir] = lambda: tmp_path

    client = TestClient(app)
    res = client.get("/manifests")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["source_slug"] == "alpha"
