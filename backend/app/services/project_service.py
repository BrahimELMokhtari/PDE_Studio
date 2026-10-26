"""Domain service orchestrating project CRUD, ownership authorization, validation, and import/export."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.repositories.base import ProjectRecord, ProjectRepository
from app.schemas.model_schema import (
    CanonicalSimulationModel,
    ValidationReport,
    validate_scientific_model,
)
from app.schemas.project_schema import (
    ProjectCreateRequest,
    ProjectExportPayload,
    ProjectImportRequest,
    ProjectListItem,
    ProjectResponse,
    ProjectUpdateRequest,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ProjectService:
    """Business logic layer between API controllers and persistence repository."""

    def __init__(self, repository: ProjectRepository) -> None:
        self._repo = repository

    def _to_response(self, record: ProjectRecord) -> ProjectResponse:
        validation = validate_scientific_model(record.model)
        return ProjectResponse(
            id=record.id,
            owner_id=record.owner_id,
            name=record.name,
            description=record.description,
            schema_version=record.schema_version,
            model=record.model,
            validation=validation,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def _to_list_item(self, record: ProjectRecord) -> ProjectListItem:
        dims = record.model.geometry.dimensions
        unit = record.model.units.length.value
        dims_summary = f"{dims.length_x:g} × {dims.length_y:g} × {dims.length_z:g} {unit}"
        return ProjectListItem(
            id=record.id,
            owner_id=record.owner_id,
            name=record.name,
            description=record.description,
            schema_version=record.schema_version,
            material_name=record.model.material.name,
            dimensions_summary=dims_summary,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def list_projects(self, owner_id: Optional[str] = None) -> list[ProjectListItem]:
        records = self._repo.list_projects(owner_id=owner_id)
        return [self._to_list_item(rec) for rec in records]

    def count_projects(self, owner_id: Optional[str] = None) -> int:
        return self._repo.count_projects(owner_id=owner_id)

    def get_project(self, project_id: str) -> Optional[ProjectResponse]:
        record = self._repo.get_project(project_id)
        if record is None:
            return None
        return self._to_response(record)

    def create_project(
        self, payload: ProjectCreateRequest, owner_id: str = "local-dev-user"
    ) -> ProjectResponse:
        record = self._repo.create_project(
            name=payload.name,
            description=payload.description,
            model=payload.model,
            owner_id=owner_id,
        )
        return self._to_response(record)

    def update_project(
        self, project_id: str, payload: ProjectUpdateRequest
    ) -> Optional[ProjectResponse]:
        record = self._repo.update_project(
            project_id=project_id,
            name=payload.name,
            description=payload.description,
            model=payload.model,
        )
        if record is None:
            return None
        return self._to_response(record)

    def delete_project(self, project_id: str) -> bool:
        return self._repo.delete_project(project_id)

    def validate_model(self, model: CanonicalSimulationModel) -> ValidationReport:
        return validate_scientific_model(model)

    def export_project(self, project_id: str) -> Optional[ProjectExportPayload]:
        record = self._repo.get_project(project_id)
        if record is None:
            return None
        return ProjectExportPayload(
            project_id=record.id,
            schema_version=record.schema_version,
            exported_at=_utc_now_iso(),
            model=record.model,
        )

    def import_project(
        self, payload: ProjectImportRequest, owner_id: str = "local-dev-user"
    ) -> ProjectResponse:
        resolved_name = (
            payload.name.strip()
            if payload.name and payload.name.strip()
            else payload.model.metadata.name
        )
        resolved_desc = (
            payload.description
            if payload.description is not None
            else payload.model.metadata.description
        )
        if payload.save_to_database:
            record = self._repo.create_project(
                name=resolved_name,
                description=resolved_desc,
                model=payload.model,
                owner_id=owner_id,
            )
            return self._to_response(record)

        now = _utc_now_iso()
        temp_record = ProjectRecord(
            id="transient-import",
            name=resolved_name,
            description=resolved_desc,
            schema_version=payload.model.schema_version,
            model=payload.model,
            created_at=now,
            updated_at=now,
            owner_id=owner_id,
        )
        return self._to_response(temp_record)
