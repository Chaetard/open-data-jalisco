import json
from pathlib import Path
from typing import Any

from .. import __version__
from ..ports.repositories import DocumentRepository, SourceRepository
from ..shared.logging import get_logger
from ..shared.time import utcnow

logger = get_logger(__name__)

DEFAULT_MANIFESTS_DIR = Path("datasets/manifests")


class ManifestGenerator:
    def __init__(
        self,
        *,
        source_repo: SourceRepository,
        document_repo: DocumentRepository,
        pipeline_version: str = __version__,
    ):
        self._source_repo = source_repo
        self._doc_repo = document_repo
        self._pipeline_version = pipeline_version

    def generate(self, source_slug: str, *, include_historical: bool = True) -> dict[str, Any]:
        source = self._source_repo.get_by_slug(source_slug)
        if source is None:
            raise LookupError(f"Source not found: {source_slug}")

        documents = self._doc_repo.list_documents(
            source_id=source.id,
            current_only=not include_historical,
            limit=10_000,
        )

        return {
            "dataset": f"open-data-jalisco/{source.slug}",
            "municipality": source.municipality,
            "source": {
                "slug": source.slug,
                "name": source.name,
                "kind": source.kind.value,
                "official_url": source.official_url,
            },
            "generated_at": utcnow().isoformat(),
            "pipeline_version": self._pipeline_version,
            "document_count": len(documents),
            "documents": [
                {
                    "id": str(d.id),
                    "title": d.title,
                    "document_type": d.document_type.value,
                    "year": d.year,
                    "official_url": d.official_url,
                    "captured_at": d.captured_at.isoformat(),
                    "sha256": d.sha256,
                    "storage_path": d.storage_path,
                    "mime_type": d.mime_type,
                    "file_size": d.file_size,
                    "version": d.version,
                    "is_current": d.is_current,
                    "superseded_by": str(d.superseded_by) if d.superseded_by else None,
                    "processing_status": d.processing_status.value,
                }
                for d in documents
            ],
        }


def write_manifest(
    manifest: dict[str, Any],
    *,
    output_dir: Path = DEFAULT_MANIFESTS_DIR,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = manifest["source"]["slug"]
    timestamp = manifest["generated_at"].replace(":", "-")
    path = output_dir / f"{slug}_{timestamp}.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("manifest.written path=%s docs=%d", path, manifest["document_count"])
    return path


def list_manifests(directory: Path = DEFAULT_MANIFESTS_DIR) -> list[dict[str, Any]]:
    """Return summary metadata for every manifest file present on disk.

    Reads JSON files under ``directory`` and projects a small, stable shape
    (filename, source_slug, municipality, generated_at, document_count,
    pipeline_version). Unreadable or non-JSON files are skipped silently —
    a manifest directory may also contain ``.gitkeep`` or partial writes.
    """
    if not directory.exists():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        source = data.get("source") or {}
        out.append(
            {
                "filename": path.name,
                "source_slug": source.get("slug", ""),
                "municipality": data.get("municipality"),
                "generated_at": data.get("generated_at"),
                "document_count": data.get("document_count"),
                "pipeline_version": data.get("pipeline_version"),
            }
        )
    return out
