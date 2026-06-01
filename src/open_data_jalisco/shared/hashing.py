import hashlib
from pathlib import Path
from typing import BinaryIO

_CHUNK_SIZE = 65536


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


def sha256_stream(stream: BinaryIO) -> str:
    h = hashlib.sha256()
    while chunk := stream.read(_CHUNK_SIZE):
        h.update(chunk)
    return h.hexdigest()
