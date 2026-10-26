"""Environment-driven application configuration (Phase 1, 2 & 3 Commercial Platform)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv(_BACKEND_DIR.parent / ".env")


def _parse_cors_origins(raw: str) -> list[str]:
    if not raw or not raw.strip():
        return ["http://localhost:5173", "http://127.0.0.1:5173"]
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or ["http://localhost:5173"]


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    """Immutable application settings loaded from environment variables."""

    app_name: str = field(
        default_factory=lambda: os.getenv("APP_NAME", "PDE Simulation Studio API")
    )
    app_env: str = field(
        default_factory=lambda: os.getenv("APP_ENV", "development")
    )
    api_host: str = field(
        default_factory=lambda: os.getenv("API_HOST", "0.0.0.0")
    )
    api_port: int = field(
        default_factory=lambda: int(os.getenv("API_PORT", "8000"))
    )
    cors_origins: list[str] = field(
        default_factory=lambda: _parse_cors_origins(
            os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173",
            )
        )
    )
    # Database configuration (PostgreSQL in production via DATABASE_URL; SQLite in local dev)
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "")
    )
    sqlite_db_path: str = field(
        default_factory=lambda: os.getenv(
            "SQLITE_DB_PATH", str(_BACKEND_DIR / "data" / "pde_studio.db")
        )
    )
    # Durable Object Storage (S3-compatible in production; local filesystem in dev)
    storage_backend: str = field(
        default_factory=lambda: os.getenv("STORAGE_BACKEND", "local").strip().lower()
    )
    local_storage_path: str = field(
        default_factory=lambda: os.getenv(
            "LOCAL_STORAGE_PATH", str(_BACKEND_DIR / "data" / "artifacts")
        )
    )
    s3_endpoint_url: str = field(
        default_factory=lambda: os.getenv("S3_ENDPOINT_URL", "")
    )
    s3_bucket_name: str = field(
        default_factory=lambda: os.getenv("S3_BUCKET_NAME", "pde-simulation-studio")
    )
    s3_access_key_id: str = field(
        default_factory=lambda: os.getenv("S3_ACCESS_KEY_ID", "")
    )
    s3_secret_access_key: str = field(
        default_factory=lambda: os.getenv("S3_SECRET_ACCESS_KEY", "")
    )
    s3_region: str = field(
        default_factory=lambda: os.getenv("S3_REGION", "us-east-1")
    )
    # Redis + RQ Worker Configuration
    redis_url: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    rq_queue_name: str = field(
        default_factory=lambda: os.getenv("RQ_QUEUE_NAME", "pde_simulations")
    )
    job_timeout_seconds: int = field(
        default_factory=lambda: int(os.getenv("JOB_TIMEOUT_SECONDS", "180"))
    )
    max_mesh_elements: int = field(
        default_factory=lambda: int(os.getenv("MAX_MESH_ELEMENTS", "250000"))
    )
    max_inline_surface_triangles: int = field(
        default_factory=lambda: int(os.getenv("MAX_INLINE_SURFACE_TRIANGLES", "15000"))
    )
    # Authentication & Authorization (OIDC-compatible; fails closed in production)
    auth_required: bool = field(
        default_factory=lambda: _parse_bool(
            os.getenv("AUTH_REQUIRED"),
            default=os.getenv("APP_ENV", "development").strip().lower() == "production",
        )
    )
    oidc_issuer_url: str = field(
        default_factory=lambda: os.getenv("OIDC_ISSUER_URL", "")
    )
    oidc_audience: str = field(
        default_factory=lambda: os.getenv("OIDC_AUDIENCE", "pde-simulation-studio-api")
    )
    oidc_jwks_url: str = field(
        default_factory=lambda: os.getenv("OIDC_JWKS_URL", "")
    )
    oidc_jwt_secret: str = field(
        default_factory=lambda: os.getenv("OIDC_JWT_SECRET", "")
    )
    oidc_algorithms: list[str] = field(
        default_factory=lambda: [
            alg.strip()
            for alg in os.getenv("OIDC_ALGORITHMS", "RS256,HS256").split(",")
            if alg.strip()
        ]
    )
    # Rate Limiting, Upload & Resource Quotas
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
    )
    max_request_body_bytes: int = field(
        default_factory=lambda: int(os.getenv("MAX_REQUEST_BODY_BYTES", "2097152"))
    )
    max_projects_per_user: int = field(
        default_factory=lambda: int(os.getenv("MAX_PROJECTS_PER_USER", "50"))
    )
    max_jobs_per_user: int = field(
        default_factory=lambda: int(os.getenv("MAX_SIMULATION_JOBS_PER_USER", "100"))
    )
    max_storage_bytes_per_user: int = field(
        default_factory=lambda: int(os.getenv("MAX_STORAGE_BYTES_PER_USER", "524288000"))
    )
    schema_version: str = "1.0.0"
    app_version: str = "3.0.0-production"

    @property
    def is_postgres(self) -> bool:
        url = self.database_url.strip().lower()
        return url.startswith("postgres://") or url.startswith("postgresql://")

    @property
    def rate_limit_requests_per_minute(self) -> int:
        return self.rate_limit_per_minute

    @property
    def quota_max_projects_per_user(self) -> int:
        return self.max_projects_per_user

    @property
    def quota_max_simulations_per_user(self) -> int:
        return self.max_jobs_per_user

    @property
    def quota_max_storage_bytes_per_user(self) -> int:
        return self.max_storage_bytes_per_user


def get_settings() -> Settings:
    """Return a fresh settings instance reading current environment variables."""
    return Settings()
