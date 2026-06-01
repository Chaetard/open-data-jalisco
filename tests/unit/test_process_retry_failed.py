"""Verify ProcessDocumentsUseCase forwards retry_failed to the repo correctly."""
from __future__ import annotations

from open_data_jalisco.processing.pipeline import ProcessDocumentsUseCase


class _RecordingDocRepo:
    def __init__(self):
        self.calls: list[dict] = []

    def list_pending(self, limit: int = 50, *, include_failed: bool = False):
        self.calls.append({"limit": limit, "include_failed": include_failed})
        return []  # no docs → use case is a no-op past this point

    # Unused by the test path we exercise, but the repo Protocol requires them.
    def get_by_id(self, *a, **kw): return None
    def find_by_url_and_hash(self, *a, **kw): return None
    def find_current_by_url(self, *a, **kw): return None
    def insert_new_version(self, doc, supersedes): return doc
    def update(self, doc): return doc
    def list_documents(self, **kw): return []


def _use_case(repo) -> ProcessDocumentsUseCase:
    return ProcessDocumentsUseCase(
        document_repo=repo,
        chunk_repo=None,       # not reached when there are no pending docs
        raw_storage=None,
        extractors=None,
        chunker=None,
        embedder=None,
    )


def test_process_defaults_to_pending_only():
    repo = _RecordingDocRepo()
    _use_case(repo).execute(limit=10)
    assert repo.calls == [{"limit": 10, "include_failed": False}]


def test_process_with_retry_failed_includes_failed_docs():
    repo = _RecordingDocRepo()
    _use_case(repo).execute(limit=5, retry_failed=True)
    assert repo.calls == [{"limit": 5, "include_failed": True}]
