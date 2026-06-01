import hashlib
from io import BytesIO

from open_data_jalisco.shared.hashing import sha256_bytes, sha256_file, sha256_stream


def test_sha256_bytes_matches_hashlib():
    payload = b"open-data-jalisco"
    assert sha256_bytes(payload) == hashlib.sha256(payload).hexdigest()


def test_sha256_file_matches(tmp_path):
    payload = b"x" * (70 * 1024)  # > internal chunk size
    f = tmp_path / "blob.bin"
    f.write_bytes(payload)
    assert sha256_file(f) == hashlib.sha256(payload).hexdigest()


def test_sha256_stream_matches():
    payload = b"hello world\n" * 1000
    assert sha256_stream(BytesIO(payload)) == hashlib.sha256(payload).hexdigest()


def test_same_bytes_same_hash():
    a = b"same content"
    b = b"same content"
    assert sha256_bytes(a) == sha256_bytes(b)


def test_different_bytes_different_hash():
    assert sha256_bytes(b"a") != sha256_bytes(b"b")
