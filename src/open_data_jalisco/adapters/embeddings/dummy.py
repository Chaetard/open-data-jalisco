# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

import hashlib
import math


class DummyEmbeddingProvider:
    """Deterministic embedding provider for development and tests.

    Maps text → fixed-dimensional unit vector via SHA-256 expansion.
    Reproducible across runs, requires no API key, no network. Same text in →
    same vector out. Different texts produce different vectors with high probability.
    """

    def __init__(self, *, dimension: int = 384, model: str = "dummy-v1"):
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension
        self._model = model

    @property
    def name(self) -> str:
        return "dummy"

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        seed = text.encode("utf-8")
        raw = bytearray()
        counter = 0
        bytes_needed = self._dimension * 2
        while len(raw) < bytes_needed:
            raw.extend(hashlib.sha256(seed + counter.to_bytes(4, "big")).digest())
            counter += 1

        values: list[float] = []
        for i in range(self._dimension):
            chunk = raw[i * 2 : i * 2 + 2]
            value = int.from_bytes(chunk, "big", signed=False) / 65535.0
            values.append(value * 2.0 - 1.0)

        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]
