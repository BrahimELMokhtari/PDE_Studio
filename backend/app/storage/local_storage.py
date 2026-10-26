"""Local filesystem implementation of ArtifactStorage for development and testing."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from app.storage.base import ArtifactStorage, StoredArtifactMetadata

_SAFE_KEY_PART_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


def _normalize_and_validate_key(key: str) -> list[str]:
    """Validate logical storage key to prevent path traversal or unsafe characters."""
    cleaned = key.strip().strip("/")
    if not cleaned:
        raise ValueError("Storage key must not be empty.")
    parts = cleaned.split("/")
    for part in parts:
        if part in ("", ".", "..") or not _SAFE_KEY_PART_RE.match(part):
            raise ValueError(f"Unsafe storage key segment: '{part}'")
    return parts


class LocalFilesystemStorage(ArtifactStorage):
    """Stores artifacts on the local filesystem with strict path traversal protection."""

    def __init__(self, root_dir: str) -> None:
        self._root = Path(root_dir).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def backend_name(self) -> str:
        return "local_filesystem"

    def _resolve_path(self, key: str) -> Path:
        parts = _normalize_and_validate_key(key)
        candidate = self._root.joinpath(*parts).resolve()
        if not str(candidate).startswith(str(self._root)):
            raise ValueError("Storage key escaped root directory.")
        return candidate

    def health_check(self) -> bool:
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            return self._root.is_dir()
        except OSError:
            return False

    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> StoredArtifactMetadata:
        target = self._resolve_path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        norm_key = "/".join(_normalize_and_validate_key(key))
        return StoredArtifactMetadata(
            key=norm_key,
            size_bytes=len(data),
            content_type=content_type,
        )

    def get_bytes(self, key: str) -> Optional[bytes]:
        target = self._resolve_path(key)
        if not target.is_file():
            return None
        return target.read_bytes()

    def exists(self, key: str) -> bool:
        target = self._resolve_path(key)
        return target.is_file()

    def delete_key(self, key: str) -> bool:
        target = self._resolve_path(key)
        if target.is_file():
            target.unlink()
            return True
        return False

    def delete_prefix(self, prefix: str) -> int:
        items = self.list_keys(prefix)
        removed = 0
        for item in items:
            if self.delete_key(item.key):
                removed += 1
        return removed

    def list_keys(self, prefix: str = "") -> list[StoredArtifactMetadata]:
        norm_prefix = "/".join(_normalize_and_validate_key(prefix)) if prefix.strip("/") else ""
        results: list[StoredArtifactMetadata] = []
        if not self._root.exists():
            return results
        for file_path in self._root.rglob("*"):
            if file_path.is_file():
                rel = file_path.relative_to(self._root).as_posix()
                if not norm_prefix or rel == norm_prefix or rel.startswith(norm_prefix + "/"):
                    results.append(
                        StoredArtifactMetadata(
                            key=rel,
                            size_bytes=file_path.stat().st_size,
                            content_type="application/octet-stream",
                        )
                    )
        results.sort(key=lambda m: m.key)
        return results

    def get_usage_bytes(self, prefix: str = "") -> int:
        return sum(item.size_bytes for item in self.list_keys(prefix))
