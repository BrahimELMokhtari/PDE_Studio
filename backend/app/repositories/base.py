"""Abstract repository interface for database-agnostic persistence (SQLite & PostgreSQL)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from app.schemas.model_schema import CanonicalSimulationModel
from app.security.auth import DEFAULT_DEV_USER_ID


@dataclass(frozen=True)
class ProjectRecord:
    """Domain persistence record representing a stored PDE simulation project."""

    id: str
    name: str
    description: str
    schema_version: str
    model: CanonicalSimulationModel
    created_at: str
    updated_at: str
    owner_id: str = DEFAULT_DEV_USER_ID


class ProjectRepository(ABC):
    """Repository interface isolating database specifics from domain/service logic."""

    @property
    def backend_name(self) -> str:
        return "sqlite"

    @abstractmethod
    def initialize(self) -> None:
        """Initialize underlying storage schema if needed."""

    @abstractmethod
    def health_check(self) -> bool:
        """Verify database connectivity and readiness."""

    @abstractmethod
    def list_projects(self, owner_id: Optional[str] = None) -> list[ProjectRecord]:
        """Return all stored projects (filtered by owner_id when provided) ordered by updated_at descending."""

    @abstractmethod
    def count_projects(self, owner_id: str) -> int:
        """Return total number of projects owned by owner_id."""

    @abstractmethod
    def get_project(self, project_id: str) -> Optional[ProjectRecord]:
        """Retrieve a single project by its unique ID, or None if not found."""

    @abstractmethod
    def create_project(
        self,
        name: str,
        description: str,
        model: CanonicalSimulationModel,
        project_id: Optional[str] = None,
        owner_id: str = DEFAULT_DEV_USER_ID,
    ) -> ProjectRecord:
        """Persist a new project record and return it."""

    @abstractmethod
    def update_project(
        self,
        project_id: str,
        name: Optional[str],
        description: Optional[str],
        model: CanonicalSimulationModel,
    ) -> Optional[ProjectRecord]:
        """Update an existing project record or return None if not found."""

    @abstractmethod
    def delete_project(self, project_id: str) -> bool:
        """Delete a project by ID and return True if a record was deleted."""
