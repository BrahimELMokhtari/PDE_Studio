"""FastAPI application entrypoint for PDE Simulation Studio (Phase 3)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.health import router as health_router
from app.api.routes.projects import router as projects_router
from app.api.routes.simulations import router as simulations_router
from app.config import Settings, get_settings
from app.repositories.base import ProjectRepository
from app.repositories.job_repository import (
    PostgresSimulationJobRepository,
    SimulationJobRepository,
    SQLiteSimulationJobRepository,
)
from app.repositories.postgres_repository import PostgresProjectRepository
from app.repositories.sqlite_repository import SQLiteProjectRepository
from app.security.middleware import SecurityAndQuotaMiddleware
from app.storage import ArtifactStorage, get_artifact_storage

logger = logging.getLogger("pde_simulation_studio")


def create_app(
    settings: Optional[Settings] = None,
    repository: Optional[ProjectRepository] = None,
    job_repository: Optional[SimulationJobRepository] = None,
    artifact_storage: Optional[ArtifactStorage] = None,
) -> FastAPI:
    """Application factory supporting environment config, PostgreSQL/SQLite, and S3/local storage injection."""
    active_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if getattr(app.state, "project_repository", None) is None:
            if repository is not None:
                app.state.project_repository = repository
            elif active_settings.is_postgres and active_settings.database_url:
                app.state.project_repository = PostgresProjectRepository(
                    active_settings.database_url
                )
            else:
                app.state.project_repository = SQLiteProjectRepository(
                    active_settings.sqlite_db_path
                )

        if getattr(app.state, "job_repository", None) is None:
            if job_repository is not None:
                app.state.job_repository = job_repository
            elif active_settings.is_postgres and active_settings.database_url:
                app.state.job_repository = PostgresSimulationJobRepository(
                    active_settings.database_url
                )
            else:
                app.state.job_repository = SQLiteSimulationJobRepository(
                    active_settings.sqlite_db_path
                )

        if getattr(app.state, "artifact_storage", None) is None:
            app.state.artifact_storage = artifact_storage or get_artifact_storage(
                active_settings
            )

        logger.info(
            "PDE Simulation Studio started (env=%s, db=%s, storage=%s)",
            active_settings.app_env,
            "postgresql" if active_settings.is_postgres else "sqlite",
            active_settings.storage_backend,
        )
        yield
        logger.info("PDE Simulation Studio shutting down gracefully.")

    app = FastAPI(
        title=active_settings.app_name,
        version=active_settings.app_version,
        description=(
            "Phase 3 Backend API for PDE Simulation Studio: 3D parametric geometry, "
            "semantic boundary conditions, NGSolve/Netgen OpenCASCADE 3D tetrahedral FEM solver, "
            "Redis + RQ asynchronous simulation jobs, PostgreSQL & S3-compatible storage, "
            "OIDC authentication, and VTK/VTU/CSV scientific post-processing exports."
        ),
        lifespan=lifespan,
    )

    app.state.settings = active_settings
    app.state.sqlite_db_path = active_settings.sqlite_db_path
    if repository is not None:
        app.state.project_repository = repository
    if job_repository is not None:
        app.state.job_repository = job_repository
    if artifact_storage is not None:
        app.state.artifact_storage = artifact_storage

    # Register rate limiter, upload size guard, and security headers middleware
    app.add_middleware(
        SecurityAndQuotaMiddleware,
        max_body_bytes=active_settings.max_request_body_bytes,
        rate_limit_per_minute=active_settings.rate_limit_per_minute,
    )

    # Configure CORS from environment variables (restrict wildcard in production)
    allow_all = (
        "*" in active_settings.cors_origins
        and active_settings.app_env.lower() != "production"
    )
    effective_origins = (
        ["*"]
        if allow_all
        else [o for o in active_settings.cors_origins if o != "*"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=effective_origins,
        allow_credentials=not allow_all,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Debug-User-Id", "X-Debug-Plan-Tier"],
        expose_headers=["Content-Disposition", "X-Process-Time-Ms"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        sanitized_errors = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err.get("loc", []) if part != "body")
            sanitized_errors.append(
                {
                    "field": loc or "payload",
                    "message": err.get("msg", "Validation error"),
                    "type": err.get("type", "value_error"),
                }
            )
        return JSONResponse(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            content={
                "detail": {
                    "message": "Model or request validation failed.",
                    "errors": sanitized_errors,
                }
            },
        )

    app.include_router(health_router)
    app.include_router(projects_router)
    app.include_router(simulations_router)

    return app


app = create_app()
