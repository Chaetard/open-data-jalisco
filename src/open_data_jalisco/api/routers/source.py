# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""AGPLv3 §13 source-code disclosure endpoint.

Returns the canonical repository URL, the version in execution and, when set
at deploy time via ``SOURCE_COMMIT``, the exact commit. Operators of modified
instances MUST keep this endpoint pointing to their own public fork.
"""

import os

from fastapi import APIRouter

from ... import __version__

REPOSITORY_URL = "https://github.com/Chaetard/open-data-jalisco"
LICENSE_SPDX = "AGPL-3.0-or-later"

router = APIRouter(tags=["meta"])


@router.get("/source")
def source() -> dict[str, str | None]:
    return {
        "repository": REPOSITORY_URL,
        "license": LICENSE_SPDX,
        "version": __version__,
        "commit": os.getenv("SOURCE_COMMIT"),
    }
