from datetime import datetime
from pathlib import Path

from ...shared.logging import get_logger

logger = get_logger(__name__)


class LocalFilesystemRawStorage:
    """Content-addressed raw storage on the local filesystem.

    Layout: <root>/<source_slug>/<yyyy>/<mm>/<sha256[:2]>/<sha256>.<ext>
    Files are written atomically and never overwritten — same hash ⇒ same bytes.
    """

    def __init__(self, root: Path):
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _path_for(
        self,
        *,
        source_slug: str,
        captured_at: datetime,
        sha256: str,
        extension: str,
    ) -> Path:
        ext = extension.lstrip(".").lower() or "bin"
        return (
            self._root
            / source_slug
            / f"{captured_at.year:04d}"
            / f"{captured_at.month:02d}"
            / sha256[:2]
            / f"{sha256}.{ext}"
        )

    def store(
        self,
        *,
        content: bytes,
        sha256: str,
        source_slug: str,
        captured_at: datetime,
        extension: str,
    ) -> str:
        target = self._path_for(
            source_slug=source_slug,
            captured_at=captured_at,
            sha256=sha256,
            extension=extension,
        )
        if target.exists():
            logger.debug("raw_storage.hit existing path=%s", target)
            return str(target.relative_to(self._root))

        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".part")
        tmp.write_bytes(content)
        tmp.replace(target)
        logger.info("raw_storage.write path=%s bytes=%d", target, len(content))
        return str(target.relative_to(self._root))

    def open(self, storage_path: str) -> Path:
        return self._root / storage_path

    def exists(self, storage_path: str) -> bool:
        return (self._root / storage_path).exists()
