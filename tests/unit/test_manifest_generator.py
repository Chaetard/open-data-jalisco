from datetime import datetime, timezone
from uuid import UUID, uuid4

from open_data_jalisco.domain.document import Document
from open_data_jalisco.domain.enums import DocumentType, ProcessingStatus, SourceKind
from open_data_jalisco.domain.source import Source
from open_data_jalisco.manifests import ManifestGenerator


class _InMemorySourceRepo:
    def __init__(self, sources):
        self._by_slug = {s.slug: s for s in sources}

    def get_by_slug(self, slug):
        return self._by_slug.get(slug)


class _InMemoryDocumentRepo:
    def __init__(self, docs):
        self._docs = docs

    def list_documents(self, *, source_id, current_only, limit, **kw):
        items = [d for d in self._docs if d.source_id == source_id]
        if current_only:
            items = [d for d in items if d.is_current]
        return items[:limit]


def test_manifest_lists_documents_with_provenance():
    source = Source(
        slug="tala-x",
        name="Tala X",
        kind=SourceKind.MUNICIPAL_PORTAL,
        municipality="Tala",
        official_url="https://example.invalid/x",
    )
    captured = datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    docs = [
        Document(
            source_id=source.id,
            sha256="a" * 64,
            official_url="https://example.invalid/x/doc1.pdf",
            mime_type="application/pdf",
            storage_path="tala-x/2025/01/aa/" + "a" * 64 + ".pdf",
            file_size=123,
            captured_at=captured,
            municipality="Tala",
            document_type=DocumentType.CONTRACT,
            title="Contrato 1",
            year=2025,
            processing_status=ProcessingStatus.INDEXED,
        ),
    ]

    gen = ManifestGenerator(
        source_repo=_InMemorySourceRepo([source]),
        document_repo=_InMemoryDocumentRepo(docs),
        pipeline_version="0.1.0-test",
    )
    manifest = gen.generate("tala-x")

    assert manifest["document_count"] == 1
    assert manifest["source"]["slug"] == "tala-x"
    assert manifest["pipeline_version"] == "0.1.0-test"
    [entry] = manifest["documents"]
    assert entry["sha256"] == "a" * 64
    assert entry["official_url"].endswith("/doc1.pdf")
    assert entry["document_type"] == "contract"
    assert entry["version"] == 1
    assert entry["is_current"] is True
    # Has required provenance fields
    for key in ("id", "captured_at", "storage_path", "mime_type", "file_size"):
        assert key in entry
