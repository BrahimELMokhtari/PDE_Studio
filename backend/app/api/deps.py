"""Dependency injection providers for FastAPI routes (Projects, Simulation Jobs, and Artifact Storage)."""

from __future__ import annotations

from fastapi import Request

from app.config import get_settings
from app.repositories.base import ProjectRepository
from app.repositories.job_repository import (
    PostgresSimulationJobRepository,
    SimulationJobRepository,
    SQLiteSimulationJobRepository,
)
from app.repositories.postgres_repository import PostgresProjectRepository
from app.repositories.sqlite_repository import SQLiteProjectRepository
from app.services.project_service import ProjectService
from app.storage import ArtifactStorage, get_artifact_storage


def get_project_repository(request: Request) -> ProjectRepository:
    """Return the application-scoped ProjectRepository (PostgreSQL in production or SQLite locally)."""
    repo = getattr(request.app.state, "project_repository", None)
    if repo is None:
        settings = getattr(request.app.state, "settings", None) or get_settings()
        if settings.is_postgres:
            repo = PostgresProjectRepository(settings.database_url)  # type: ignore[arg-type]
        else:
            repo = SQLiteProjectRepository(settings.sqlite_db_path)
        request.app.state.project_repository = repo
    return repo


def get_project_service(request: Request) -> ProjectService:
    """Return a ProjectService wired with the active ProjectRepository."""
    repo = get_project_repository(request)
    return ProjectService(repo)


def get_job_repository(request: Request) -> SimulationJobRepository:
    """Return the application-scoped SimulationJobRepository (PostgreSQL or SQLite)."""
    job_repo = getattr(request.app.state, "job_repository", None)
    if job_repo is None:
        settings = getattr(request.app.state, "settings", None) or get_settings()
        if settings.is_postgres:
            job_repo = PostgresSimulationJobRepository(settings.database_url)  # type: ignore[arg-type]
        else:
            job_repo = SQLiteSimulationJobRepository(settings.sqlite_db_path)
        request.app.state.job_repository = job_repo
    return job_repo


def get_storage(request: Request) -> ArtifactStorage:
    """Return the application-scoped ArtifactStorage (S3-compatible or LocalFilesystemStorage)."""
    storage = getattr(request.app.state, "artifact_storage", None)
    if storage is None:
        settings = getattr(request.app.state, "settings", None) or get_settings()
        storage = get_artifact_storage(settings)
        request.app.state.artifact_storage = storage
    return storage
