"""S3-compatible durable object storage implementation (AWS S3, Cloudflare R2, MinIO, Backblaze B2)."""

from __future__ import annotations

from typing import Any, Optional

from app.storage.base import ArtifactStorage, StoredArtifactMetadata
from app.storage.local_storage import _normalize_and_validate_key


class S3CompatibleStorage(ArtifactStorage):
    """Durable object storage backed by an S3-compatible bucket via boto3."""

    def __init__(
        self,
        bucket_name: str,
        endpoint_url: str = "",
        access_key_id: str = "",
        secret_access_key: str = "",
        region_name: str = "us-east-1",
        s3_client: Optional[Any] = None,
    ) -> None:
        self._bucket = bucket_name
        if s3_client is not None:
            self._client = s3_client
        else:
            import boto3  # type: ignore[import-untyped]

            kwargs: dict[str, Any] = {"region_name": region_name or "us-east-1"}
            if endpoint_url:
                kwargs["endpoint_url"] = endpoint_url
            if access_key_id and secret_access_key:
                kwargs["aws_access_key_id"] = access_key_id
                kwargs["aws_secret_access_key"] = secret_access_key
            self._client = boto3.client("s3", **kwargs)

    @property
    def backend_name(self) -> str:
        return "s3_compatible"

    def _clean_key(self, key: str) -> str:
        return "/".join(_normalize_and_validate_key(key))

    def health_check(self) -> bool:
        try:
            self._client.head_bucket(Bucket=self._bucket)
            return True
        except Exception:
            return False

    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> StoredArtifactMetadata:
        clean_key = self._clean_key(key)
        self._client.put_object(
            Bucket=self._bucket,
            Key=clean_key,
            Body=data,
            ContentType=content_type,
        )
        return StoredArtifactMetadata(
            key=clean_key,
            size_bytes=len(data),
            content_type=content_type,
        )

    def get_bytes(self, key: str) -> Optional[bytes]:
        clean_key = self._clean_key(key)
        try:
            res = self._client.get_object(Bucket=self._bucket, Key=clean_key)
            return bytes(res["Body"].read())
        except Exception:
            return None

    def exists(self, key: str) -> bool:
        clean_key = self._clean_key(key)
        try:
            self._client.head_object(Bucket=self._bucket, Key=clean_key)
            return True
        except Exception:
            return False

    def delete_key(self, key: str) -> bool:
        clean_key = self._clean_key(key)
        if not self.exists(clean_key):
            return False
        self._client.delete_object(Bucket=self._bucket, Key=clean_key)
        return True

    def delete_prefix(self, prefix: str) -> int:
        items = self.list_keys(prefix)
        removed = 0
        for item in items:
            self._client.delete_object(Bucket=self._bucket, Key=item.key)
            removed += 1
        return removed

    def list_keys(self, prefix: str = "") -> list[StoredArtifactMetadata]:
        clean_prefix = (
            "/".join(_normalize_and_validate_key(prefix)) if prefix.strip("/") else ""
        )
        kwargs: dict[str, Any] = {"Bucket": self._bucket}
        if clean_prefix:
            kwargs["Prefix"] = clean_prefix

        response = self._client.list_objects_v2(**kwargs)
        contents = response.get("Contents", []) or []
        results: list[StoredArtifactMetadata] = []
        for obj in contents:
            results.append(
                StoredArtifactMetadata(
                    key=str(obj["Key"]),
                    size_bytes=int(obj.get("Size", 0)),
                    content_type="application/octet-stream",
                )
            )
        results.sort(key=lambda m: m.key)
        return results

    def get_usage_bytes(self, prefix: str = "") -> int:
        return sum(item.size_bytes for item in self.list_keys(prefix))
