from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..domain.enums import SourceKind

DEFAULT_SOURCES_DIR = Path("datasets/sources")


class SourceConfigError(Exception):
    pass


class SourceConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    slug: str
    name: str
    kind: SourceKind
    municipality: str
    official_url: str
    description: str | None = None
    metadata: dict[str, Any] | None = None
    is_active: bool = True
    scraper: dict[str, Any] = Field(default_factory=dict)


def load_source_config(path: Path) -> SourceConfig:
    if not path.exists():
        raise SourceConfigError(f"Source config not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SourceConfigError(f"Source config must be a mapping: {path}")
    try:
        return SourceConfig.model_validate(raw)
    except ValidationError as e:
        raise SourceConfigError(f"Invalid source config {path}: {e}") from e


def iter_source_configs(directory: Path = DEFAULT_SOURCES_DIR) -> Iterator[SourceConfig]:
    if not directory.exists():
        return
    for path in sorted(directory.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        yield load_source_config(path)


def find_source_config(slug: str, directory: Path = DEFAULT_SOURCES_DIR) -> SourceConfig:
    for cfg in iter_source_configs(directory):
        if cfg.slug == slug:
            return cfg
    raise SourceConfigError(f"No source config found with slug={slug!r} in {directory}")
