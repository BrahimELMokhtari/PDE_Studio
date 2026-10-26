"""Storage package providing LocalFilesystemStorage and S3CompatibleStorage."""

from __future__ import annotations

from app.config import Settings, get_settings
from app.storage.base import ArtifactStorage, StoredArtifactMetadata
from app.storage.local_storage import LocalFilesystemStorage
from app.storage.s3_storage import S3CompatibleStorage


def create_artifact_storage(settings: Settings | None = None) -> ArtifactStorage:
    """Factory that instantiates S3CompatibleStorage or LocalFilesystemStorage from settings."""
    cfg = settings or get_settings()
    if cfg.storage_backend == "s3":
        return S3CompatibleStorage(
            bucket_name=cfg.s3_bucket_name,
            endpoint_url=cfg.s3_endpoint_url,
            access_key_id=cfg.s3_access_key_id,
            secret_access_key=cfg.s3_secret_access_key,
            region_name=cfg.s3_region,
        )
    return LocalFilesystemStorage(cfg.local_storage_path)


get_artifact_storage = create_artifact_storage

__all__ = [
    "ArtifactStorage",
    "LocalFilesystemStorage",
    "S3CompatibleStorage",
    "StoredArtifactMetadata",
    "create_artifact_storage",
    "get_artifact_storage",
]
