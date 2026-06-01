# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
