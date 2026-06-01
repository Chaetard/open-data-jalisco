from pathlib import Path

import pytest

from open_data_jalisco.domain.enums import SourceKind
from open_data_jalisco.ingestion.source_loader import (
    SourceConfigError,
    find_source_config,
    iter_source_configs,
    load_source_config,
)


def _write_yaml(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_load_valid_source(tmp_path):
    f = _write_yaml(
        tmp_path / "x.yaml",
        """
slug: tala-piloto
name: Tala — fuente piloto
kind: municipal_portal
municipality: Tala
official_url: https://example.invalid/portal
is_active: false
scraper:
  type: generic_http
  documents: []
""",
    )
    cfg = load_source_config(f)
    assert cfg.slug == "tala-piloto"
    assert cfg.kind is SourceKind.MUNICIPAL_PORTAL
    assert cfg.municipality == "Tala"
    assert cfg.is_active is False
    assert cfg.scraper["type"] == "generic_http"


def test_invalid_yaml_raises(tmp_path):
    f = _write_yaml(tmp_path / "bad.yaml", "slug: ok\nname: no-kind\n")
    with pytest.raises(SourceConfigError):
        load_source_config(f)


def test_missing_file_raises(tmp_path):
    with pytest.raises(SourceConfigError):
        load_source_config(tmp_path / "nope.yaml")


def test_iter_skips_underscored_files(tmp_path):
    _write_yaml(
        tmp_path / "a.yaml",
        """
slug: a
name: A
kind: municipal_portal
municipality: Tala
official_url: https://example.invalid/a
""",
    )
    _write_yaml(
        tmp_path / "_disabled.yaml",
        """
slug: disabled
name: D
kind: municipal_portal
municipality: Tala
official_url: https://example.invalid/d
""",
    )
    slugs = [c.slug for c in iter_source_configs(tmp_path)]
    assert slugs == ["a"]


def test_find_source_by_slug(tmp_path):
    _write_yaml(
        tmp_path / "a.yaml",
        """
slug: target
name: T
kind: municipal_portal
municipality: Tala
official_url: https://example.invalid/t
""",
    )
    cfg = find_source_config("target", tmp_path)
    assert cfg.slug == "target"

    with pytest.raises(SourceConfigError):
        find_source_config("missing", tmp_path)
