# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

import os
import sys
from pathlib import Path

# Hermetic config: never let the developer's local .env (which may enable the
# real embedder/reranker — ~18 s of model loads on CPU) leak into the unit
# suite. Env vars take precedence over the .env file in pydantic-settings, and
# this runs before any test imports settings.
os.environ["EMBEDDING_PROVIDER"] = "dummy"
os.environ["EMBEDDING_MODEL"] = "dummy-v1"
os.environ["RERANK_PROVIDER"] = "none"

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
