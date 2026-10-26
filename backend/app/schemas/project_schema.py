"""Request and response schemas for Project CRUD and import/export endpoints."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.model_schema import CanonicalSimulationModel, ValidationReport


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    model: CanonicalSimulationModel

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Project name must not be empty.")
        return cleaned


class ProjectUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)
    model: CanonicalSimulationModel

    @field_validator("name")
    @classmethod
    def strip_optional_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Project name must not be empty.")
        return cleaned


class ProjectListItem(BaseModel):
    id: str
    owner_id: str = "local-dev-user"
    name: str
    description: str
    schema_version: str
    material_name: str
    dimensions_summary: str
    created_at: str
    updated_at: str


class ProjectResponse(BaseModel):
    id: str
    owner_id: str = "local-dev-user"
    name: str
    description: str
    schema_version: str
    model: CanonicalSimulationModel
    validation: ValidationReport
    created_at: str
    updated_at: str


class ProjectExportPayload(BaseModel):
    """Canonical portable JSON file structure for export/import."""

    export_format: str = "pde_simulation_studio_project"
    schema_version: str = "1.0.0"
    project_id: Optional[str] = None
    exported_at: str
    model: CanonicalSimulationModel


class ProjectImportRequest(BaseModel):
    """Accepts either a wrapped ProjectExportPayload or a direct CanonicalSimulationModel."""

    name: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)
    save_to_database: bool = Field(default=True)
    model: CanonicalSimulationModel
