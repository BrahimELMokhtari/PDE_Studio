"""Health check endpoints reporting database, durable storage, NGSolve FEM engine, and Redis/RQ status."""

from __future__ import annotations

from datetime import datetime, timezone
import ngsolve as ngs
from fastapi import APIRouter, Depends, Request

from app.api.deps import get_project_repository, get_storage
from app.config import Settings, get_settings
from app.jobs.rq_tasks import get_redis_connection_and_mode
from app.repositories.base import ProjectRepository
from app.storage import ArtifactStorage

router = APIRouter(tags=["health"])


@router.get("/health")
@router.get("/api/health")
def health_check(
    request: Request,
    repo: ProjectRepository = Depends(get_project_repository),
    storage: ArtifactStorage = Depends(get_storage),
) -> dict[str, object]:
    """Return service health, schema version, database status, storage status, Redis/RQ status, and NGSolve capabilities."""
    settings: Settings = getattr(request.app.state, "settings", None) or get_settings()
    db_ok = repo.health_check()
    storage_ok = storage.health_check()
    _conn, queue_mode = get_redis_connection_and_mode(settings.redis_url)

    return {
        "status": "ok" if (db_ok and storage_ok) else "degraded",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "schema_version": settings.schema_version,
        "database": {
            "backend": "postgresql" if settings.is_postgres else "sqlite",
            "connected": db_ok,
            "abstraction": "ProjectRepository & SimulationJobRepository (SQLite & PostgreSQL)",
        },
        "storage": {
            "backend": storage.backend_name,
            "connected": storage_ok,
            "abstraction": "ArtifactStorage (LocalFilesystemStorage & S3CompatibleStorage)",
        },
        "queue": {
            "engine": "Redis + RQ",
            "mode": queue_mode,
            "queue_name": settings.rq_queue_name,
        },
        "security": {
            "auth_required": settings.auth_required or settings.app_env.lower() == "production",
            "oidc_configured": bool(
                settings.oidc_jwks_url.strip() or settings.oidc_jwt_secret.strip()
            ),
            "rate_limit_rpm": settings.rate_limit_requests_per_minute,
            "max_request_body_bytes": settings.max_request_body_bytes,
        },
        "capabilities": {
            "phase": 3,
            "geometry_modeling": True,
            "boundary_conditions": True,
            "canonical_json_schema": True,
            "pde_solver_execution": True,
            "solver_engine": f"NGSolve {getattr(ngs, '__version__', '6.2')} / Netgen OpenCASCADE",
            "reproducible_script_export": True,
            "vtu_and_csv_export": True,
            "cross_section_clipping": True,
            "durable_artifact_storage": True,
        },
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
