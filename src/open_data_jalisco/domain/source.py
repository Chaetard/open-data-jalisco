# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from ..shared.time import utcnow
from .enums import SourceKind


@dataclass
class Source:
    slug: str
    name: str
    kind: SourceKind
    municipality: str
    official_url: str
    description: str | None = None
    metadata: dict[str, Any] | None = None
    is_active: bool = True
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
