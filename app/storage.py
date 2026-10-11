import os
from pathlib import Path
from typing import BinaryIO, Protocol

from app.config import get_settings


class StorageBackend(Protocol):
    def put(self, job_id: str, cert_id: str, payload: bytes) -> str: ...
    def open(self, path: str) -> BinaryIO: ...
    def full_path(self, path: str) -> Path: ...
    def delete(self, path: str) -> None: ...


class LocalStorage:
    """
    Local-disk storage with atomic writes.

    Files are written to a sibling ``.tmp`` then ``os.replace``-d into place, so a
    crash mid-write can never leave a truncated PDF that looks valid.
    Swap for S3 later by implementing ``put`` / ``open`` / ``full_path`` / ``delete``.
    """

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe(self, rel: str) -> Path:
        target = (self.root / rel).resolve()
        if not str(target).startswith(str(self.root) + os.sep) and target != self.root:
            raise ValueError(f"path traversal detected: {rel!r}")
        return target

    def put(self, job_id: str, cert_id: str, payload: bytes) -> str:
        rel = f"{job_id}/{cert_id}.pdf"
        target = self._safe(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".pdf.tmp")
        with open(tmp, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
        return rel

    def open(self, path: str) -> BinaryIO:
        return open(self._safe(path), "rb")

    def full_path(self, path: str) -> Path:
        return self._safe(path)

    def delete(self, path: str) -> None:
        try:
            self._safe(path).unlink()
        except FileNotFoundError:
            pass


_storage: LocalStorage | None = None


def get_storage() -> LocalStorage:
    global _storage
    if _storage is None:
        _storage = LocalStorage(get_settings().storage_root)
    return _storage


def reset_storage() -> None:
    """Test hook — lets a new settings snapshot rebuild the backend."""
    global _storage
    _storage = None