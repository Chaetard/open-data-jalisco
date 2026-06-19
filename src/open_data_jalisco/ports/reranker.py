# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from typing import Protocol


class Reranker(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...

    def rerank(self, query: str, passages: list[str]) -> list[float]:
        """Score each passage's relevance to ``query``; higher = more relevant.

        Returns one score per passage, in the same order. Scores are only
        meaningful relative to each other within a single call (cross-encoder
        logits, not probabilities): callers sort the candidates by them and do
        not threshold across calls.
        """
        ...
