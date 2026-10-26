"""Project CRUD, tenant ownership authorization, quota enforcement, validation, and canonical JSON import/export endpoints."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import ValidationError

from app.api.deps import get_project_service
from app.config import Settings, get_settings
from app.schemas.model_schema import CanonicalSimulationModel, ValidationReport
from app.schemas.project_schema import (
    ProjectCreateRequest,
    ProjectExportPayload,
    ProjectImportRequest,
    ProjectListItem,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.security.auth import AuthenticatedPrincipal, get_current_principal
from app.services.project_service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _enforce_project_ownership(
    project: ProjectResponse, principal: AuthenticatedPrincipal
) -> None:
    if project.owner_id != principal.user_id and "admin" not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: you do not own this project.",
        )


def _enforce_project_quota(
    request: Request,
    service: ProjectService,
    principal: AuthenticatedPrincipal,
) -> None:
    settings: Settings = getattr(request.app.state, "settings", None) or get_settings()
    current_count = service.count_projects(owner_id=principal.user_id)
    if current_count >= settings.quota_max_projects_per_user:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Project quota exceeded: {current_count}/{settings.quota_max_projects_per_user} "
                f"projects used for account '{principal.user_id}'."
            ),
        )


@router.get("", response_model=list[ProjectListItem])
def list_projects(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    service: ProjectService = Depends(get_project_service),
) -> list[ProjectListItem]:
    """List all saved PDE simulation projects owned by the authenticated user."""
    return service.list_projects(owner_id=principal.user_id)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    payload: ProjectCreateRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """Create and persist a new PDE simulation project under the authenticated user."""
    _enforce_project_quota(request, service, principal)
    return service.create_project(payload, owner_id=principal.user_id)


@router.post("/validate", response_model=ValidationReport)
def validate_model_endpoint(
    model: CanonicalSimulationModel,
    _principal: AuthenticatedPrincipal = Depends(get_current_principal),
    service: ProjectService = Depends(get_project_service),
) -> ValidationReport:
    """Validate a canonical simulation model and compute geometry/mesh pre-check metrics."""
    return service.validate_model(model)


@router.post(
    "/import",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_project_json(
    request: Request,
    raw_payload: dict[str, Any] = Body(...),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """Import a project from either a wrapped export JSON or a direct canonical model JSON."""
    try:
        if "model" in raw_payload and isinstance(raw_payload["model"], dict):
            import_req = ProjectImportRequest(
                name=raw_payload.get("name"),
                description=raw_payload.get("description"),
                save_to_database=raw_payload.get("save_to_database", True),
                model=CanonicalSimulationModel.model_validate(raw_payload["model"]),
            )
        else:
            model = CanonicalSimulationModel.model_validate(raw_payload)
            import_req = ProjectImportRequest(
                name=model.metadata.name,
                description=model.metadata.description,
                save_to_database=True,
                model=model,
            )
    except ValidationError as exc:
        raise HTTPException(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            detail={
                "message": "Invalid canonical simulation model JSON.",
                "errors": exc.errors(include_url=False),
            },
        ) from exc

    if import_req.save_to_database:
        _enforce_project_quota(request, service, principal)

    return service.import_project(import_req, owner_id=principal.user_id)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """Retrieve a saved project by ID."""
    project = service.get_project(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' was not found.",
        )
    _enforce_project_ownership(project, principal)
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    payload: ProjectUpdateRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """Update an existing project's metadata and canonical simulation model."""
    existing = service.get_project(project_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' was not found.",
        )
    _enforce_project_ownership(existing, principal)
    updated = service.update_project(project_id, payload)
    assert updated is not None
    return updated


@router.delete("/{project_id}", status_code=status.HTTP_200_OK)
def delete_project(
    project_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    service: ProjectService = Depends(get_project_service),
) -> dict[str, Any]:
    """Delete a saved project by ID."""
    existing = service.get_project(project_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' was not found.",
        )
    _enforce_project_ownership(existing, principal)
    service.delete_project(project_id)
    return {"deleted": True, "id": project_id}


@router.get("/{project_id}/export", response_model=ProjectExportPayload)
def export_project(
    project_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    service: ProjectService = Depends(get_project_service),
) -> ProjectExportPayload:
    """Export a saved project in the canonical portable JSON format."""
    existing = service.get_project(project_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' was not found.",
        )
    _enforce_project_ownership(existing, principal)
    exported = service.export_project(project_id)
    assert exported is not None
    return exported
