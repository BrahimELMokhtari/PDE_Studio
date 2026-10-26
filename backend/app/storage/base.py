"""Abstract ArtifactStorage interface for meshes, generated scripts, VTU, and CSV results."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class StoredArtifactMetadata:
    """Metadata describing a stored simulation or project artifact."""

    key: str
    size_bytes: int
    content_type: str


class ArtifactStorage(ABC):
    """Durable object storage abstraction supporting S3-compatible cloud storage and local dev filesystem."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Identifier of the active storage backend ('local' or 's3')."""

    @abstractmethod
    def health_check(self) -> bool:
        """Verify storage availability and write/read readiness."""

    @abstractmethod
    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> StoredArtifactMetadata:
        """Persist binary content under the given logical key."""

    @abstractmethod
    def get_bytes(self, key: str) -> Optional[bytes]:
        """Retrieve binary content by logical key, or None if not found."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if the artifact key exists."""

    @abstractmethod
    def delete_key(self, key: str) -> bool:
        """Delete a single artifact key and return True if removed."""

    @abstractmethod
    def delete_prefix(self, prefix: str) -> int:
        """Delete all artifacts under a logical key prefix and return count deleted."""

    @abstractmethod
    def list_keys(self, prefix: str = "") -> list[StoredArtifactMetadata]:
        """List stored artifacts matching the optional key prefix."""

    @abstractmethod
    def get_usage_bytes(self, prefix: str = "") -> int:
        """Calculate total bytes stored under the given prefix (e.g. per owner_id)."""

    def get_prefix_size_bytes(self, prefix: str = "") -> int:
        """Alias for get_usage_bytes."""
        return self.get_usage_bytes(prefix)
