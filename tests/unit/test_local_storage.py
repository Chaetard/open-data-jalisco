from datetime import datetime, timezone

from open_data_jalisco.adapters.storage.local_filesystem import LocalFilesystemRawStorage
from open_data_jalisco.shared.hashing import sha256_bytes


def test_store_creates_content_addressed_path(tmp_path):
    storage = LocalFilesystemRawStorage(tmp_path)
    payload = b"hello"
    sha = sha256_bytes(payload)
    captured_at = datetime(2025, 7, 4, tzinfo=timezone.utc)

    rel = storage.store(
        content=payload,
        sha256=sha,
        source_slug="tala-piloto",
        captured_at=captured_at,
        extension="txt",
    )

    expected = f"tala-piloto/2025/07/{sha[:2]}/{sha}.txt"
    assert rel.replace("\\", "/") == expected
    assert storage.exists(rel)
    assert storage.open(rel).read_bytes() == payload


def test_store_is_idempotent_for_same_hash(tmp_path):
    storage = LocalFilesystemRawStorage(tmp_path)
    payload = b"abc"
    sha = sha256_bytes(payload)
    captured_at = datetime(2025, 7, 4, tzinfo=timezone.utc)

    a = storage.store(
        content=payload, sha256=sha, source_slug="x", captured_at=captured_at, extension="bin"
    )
    b = storage.store(
        content=payload, sha256=sha, source_slug="x", captured_at=captured_at, extension="bin"
    )
    assert a == b
