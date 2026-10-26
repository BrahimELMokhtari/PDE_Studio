"""Simulation execution, job polling, VTU/CSV artifact exports, job deletion, quotas, and package routes."""

from __future__ import annotations

import re
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.api.deps import get_job_repository, get_project_service, get_storage
from app.config import Settings, get_settings
from app.jobs.rq_tasks import enqueue_simulation_job
from app.repositories.job_repository import SimulationJobRepository
from app.schemas.model_schema import CanonicalSimulationModel
from app.schemas.simulation_schema import (
    SimulationJobResponse,
    SimulationScriptResponse,
    SimulationSubmitRequest,
    UserQuotaSummaryResponse,
)
from app.security.auth import AuthenticatedPrincipal, get_current_principal
from app.services.project_service import ProjectService
from app.solver.exceptions import SolverError
from app.solver.exporter import (
    export_boundary_csv_bytes,
    export_nodal_csv_bytes,
    export_surface_vtu_from_summary,
)
from app.solver.package_builder import build_simulation_package_zip
from app.solver.script_generator import generate_reproducible_python_script
from app.storage import ArtifactStorage

router = APIRouter(prefix="/api/simulations", tags=["simulations"])


def _safe_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9-_]+", "-", name.lower()).strip("-")
    return slug or "pde-simulation"


def _enforce_job_ownership(
    job: SimulationJobResponse, principal: AuthenticatedPrincipal
) -> None:
    if job.owner_id != principal.user_id and "admin" not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: you do not own this simulation job.",
        )


@router.get("/quotas", response_model=UserQuotaSummaryResponse)
def get_user_quotas(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    project_service: ProjectService = Depends(get_project_service),
    job_repo: SimulationJobRepository = Depends(get_job_repository),
    storage: ArtifactStorage = Depends(get_storage),
) -> UserQuotaSummaryResponse:
    """Return the authenticated user's project, simulation, and object-storage quota usage."""
    settings: Settings = getattr(request.app.state, "settings", None) or get_settings()
    projects_used = project_service.count_projects(owner_id=principal.user_id)
    sims_used = job_repo.count_jobs(owner_id=principal.user_id)
    storage_used = storage.get_prefix_size_bytes(f"jobs/{principal.user_id}/")

    return UserQuotaSummaryResponse(
        owner_id=principal.user_id,
        plan_tier=principal.plan_tier,
        projects_used=projects_used,
        projects_limit=settings.quota_max_projects_per_user,
        simulations_used=sims_used,
        simulations_limit=settings.quota_max_simulations_per_user,
        storage_bytes_used=storage_used,
        storage_bytes_limit=settings.quota_max_storage_bytes_per_user,
        max_mesh_elements_limit=settings.max_mesh_elements,
    )


@router.post(
    "",
    response_model=SimulationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@router.post(
    "/jobs",
    response_model=SimulationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_simulation_job(
    payload: SimulationSubmitRequest,
    request: Request,
    wait: bool = Query(
        default=False,
        description="If true, drains the RQ worker synchronously before returning (useful for deterministic CLI/test runs).",
    ),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    job_repo: SimulationJobRepository = Depends(get_job_repository),
    storage: ArtifactStorage = Depends(get_storage),
) -> SimulationJobResponse:
    """Create and enqueue an asynchronous 3D steady-state heat conduction FEM simulation job."""
    settings: Settings = getattr(request.app.state, "settings", None) or get_settings()

    # Enforce simulation count quota
    sims_used = job_repo.count_jobs(owner_id=principal.user_id)
    if sims_used >= settings.quota_max_simulations_per_user:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Simulation job quota exceeded: {sims_used}/{settings.quota_max_simulations_per_user} "
                f"jobs stored for account '{principal.user_id}'. Delete older jobs to free quota."
            ),
        )

    # Enforce durable storage quota
    storage_used = storage.get_prefix_size_bytes(f"jobs/{principal.user_id}/")
    if storage_used >= settings.quota_max_storage_bytes_per_user:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Artifact storage quota exceeded: {storage_used} / {settings.quota_max_storage_bytes_per_user} bytes used. "
                "Delete older simulation jobs to reclaim storage."
            ),
        )

    db_target = (
        settings.database_url
        if settings.is_postgres and settings.database_url
        else getattr(request.app.state, "sqlite_db_path", settings.sqlite_db_path)
    )

    # Apply optional mesh overrides onto the stored job model
    effective_model = payload.model
    if payload.max_element_size is not None or payload.polynomial_order is not None:
        updated_mesh = effective_model.mesh.model_copy(
            update={
                "max_element_size": (
                    payload.max_element_size
                    if payload.max_element_size is not None
                    else effective_model.mesh.max_element_size
                ),
                "polynomial_order": (
                    payload.polynomial_order
                    if payload.polynomial_order is not None
                    else effective_model.mesh.polynomial_order
                ),
            }
        )
        effective_model = effective_model.model_copy(update={"mesh": updated_mesh})

    job = job_repo.create_job(
        model=effective_model,
        project_id=payload.project_id,
        owner_id=principal.user_id,
    )

    rq_job_id, _mode = enqueue_simulation_job(
        job_id=job.job_id,
        db_path=str(db_target),
        max_element_size=effective_model.mesh.max_element_size,
        polynomial_order=effective_model.mesh.polynomial_order,
        run_synchronously_for_test=wait,
        local_storage_path=settings.local_storage_path,
    )
    job_repo.set_rq_job_id(job.job_id, rq_job_id)

    refreshed = job_repo.get_job(job.job_id)
    assert refreshed is not None
    return refreshed


@router.get("", response_model=list[SimulationJobResponse])
@router.get("/jobs", response_model=list[SimulationJobResponse])
def list_simulation_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    project_id: Optional[str] = Query(default=None),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    job_repo: SimulationJobRepository = Depends(get_job_repository),
) -> list[SimulationJobResponse]:
    """List recent simulation jobs owned by the authenticated user."""
    return job_repo.list_jobs(
        limit=limit,
        owner_id=principal.user_id,
        project_id=project_id,
    )


@router.get("/{job_id}", response_model=SimulationJobResponse)
@router.get("/jobs/{job_id}", response_model=SimulationJobResponse)
def get_simulation_job(
    job_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    job_repo: SimulationJobRepository = Depends(get_job_repository),
) -> SimulationJobResponse:
    """Retrieve status, progress, logs, and FEM results for a simulation job."""
    job = job_repo.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation job '{job_id}' was not found.",
        )
    _enforce_job_ownership(job, principal)
    return job


@router.delete("/{job_id}", status_code=status.HTTP_200_OK)
@router.delete("/jobs/{job_id}", status_code=status.HTTP_200_OK)
def delete_simulation_job(
    job_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    job_repo: SimulationJobRepository = Depends(get_job_repository),
    storage: ArtifactStorage = Depends(get_storage),
) -> dict[str, Any]:
    """Delete a simulation job record and purge its associated object-storage artifacts."""
    job = job_repo.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation job '{job_id}' was not found.",
        )
    _enforce_job_ownership(job, principal)

    deleted_artifacts = storage.delete_prefix(f"jobs/{job.owner_id}/{job.job_id}/")
    job_repo.delete_job(job_id)
    return {
        "deleted": True,
        "job_id": job_id,
        "deleted_artifacts_count": deleted_artifacts,
    }


@router.post("/script", response_model=SimulationScriptResponse)
def generate_script_endpoint(
    model: CanonicalSimulationModel,
    _principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> SimulationScriptResponse:
    """Generate a standalone, editable NGSolve Python script from a validated canonical model."""
    try:
        script_code = generate_reproducible_python_script(model)
    except SolverError as exc:
        raise HTTPException(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            detail={
                "message": str(exc),
                "error_type": type(exc).__name__,
            },
        ) from exc

    return SimulationScriptResponse(
        filename="simulation.py",
        schema_version=model.schema_version,
        script_content=script_code,
        instructions=(
            "Install dependencies (`pip install ngsolve numpy scipy`) and run `python simulation.py` "
            "to reproduce the 3D mesh, solve the steady-state heat equation, and export `solution.vtu`."
        ),
    )


@router.post("/package")
def download_package_from_model(
    model: CanonicalSimulationModel,
    _principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> Response:
    """Build and download a ZIP simulation package (simulation.py, model.json, requirements.txt, README.md)."""
    try:
        zip_bytes = build_simulation_package_zip(model=model)
    except SolverError as exc:
        raise HTTPException(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            detail={
                "message": str(exc),
                "error_type": type(exc).__name__,
            },
        ) from exc

    filename = f"{_safe_slug(model.metadata.name)}-simulation-package.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/{job_id}/package")
@router.get("/jobs/{job_id}/package")
def download_package_from_job(
    job_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    job_repo: SimulationJobRepository = Depends(get_job_repository),
    storage: ArtifactStorage = Depends(get_storage),
) -> Response:
    """Download a ZIP simulation package for an existing job (includes VTU, CSVs, and results_summary.json)."""
    job = job_repo.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation job '{job_id}' was not found.",
        )
    _enforce_job_ownership(job, principal)

    zip_bytes: Optional[bytes] = None
    if job.result and job.result.artifacts and job.result.artifacts.package_zip_key:
        zip_bytes = storage.get_bytes(job.result.artifacts.package_zip_key)

    if zip_bytes is None:
        try:
            zip_bytes = build_simulation_package_zip(
                model=job.model,
                result=job.result,
            )
        except SolverError as exc:
            raise HTTPException(
                status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
                detail={
                    "message": str(exc),
                    "error_type": type(exc).__name__,
                },
            ) from exc

    filename = f"{_safe_slug(job.project_name)}-{job.job_id[:8]}-package.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/{job_id}/artifacts/vtu")
@router.get("/jobs/{job_id}/artifacts/vtu")
def download_vtu_artifact(
    job_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    job_repo: SimulationJobRepository = Depends(get_job_repository),
    storage: ArtifactStorage = Depends(get_storage),
) -> Response:
    """Download the computed 3D VTK XML UnstructuredGrid (.vtu) result file."""
    job = job_repo.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation job '{job_id}' was not found.",
        )
    _enforce_job_ownership(job, principal)
    if job.result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Simulation job has not completed with numerical results.",
        )

    vtu_bytes: Optional[bytes] = None
    if job.result.artifacts and job.result.artifacts.vtu_key:
        vtu_bytes = storage.get_bytes(job.result.artifacts.vtu_key)
    if vtu_bytes is None:
        vtu_bytes = export_surface_vtu_from_summary(job.result)

    filename = f"{_safe_slug(job.project_name)}-{job.job_id[:8]}-solution.vtu"
    return Response(
        content=vtu_bytes,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/{job_id}/artifacts/nodal-csv")
@router.get("/jobs/{job_id}/artifacts/nodal-csv")
def download_nodal_csv_artifact(
    job_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    job_repo: SimulationJobRepository = Depends(get_job_repository),
    storage: ArtifactStorage = Depends(get_storage),
) -> Response:
    """Download the nodal coordinates and computed temperature dataset in CSV format."""
    job = job_repo.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation job '{job_id}' was not found.",
        )
    _enforce_job_ownership(job, principal)
    if job.result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Simulation job has not completed with numerical results.",
        )

    csv_bytes: Optional[bytes] = None
    if job.result.artifacts and job.result.artifacts.nodal_csv_key:
        csv_bytes = storage.get_bytes(job.result.artifacts.nodal_csv_key)
    if csv_bytes is None:
        csv_bytes = export_nodal_csv_bytes(job.result)

    filename = f"{_safe_slug(job.project_name)}-{job.job_id[:8]}-nodal-results.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/{job_id}/artifacts/boundary-csv")
@router.get("/jobs/{job_id}/artifacts/boundary-csv")
def download_boundary_csv_artifact(
    job_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    job_repo: SimulationJobRepository = Depends(get_job_repository),
    storage: ArtifactStorage = Depends(get_storage),
) -> Response:
    """Download the per-face boundary temperatures and outward heat rates in CSV format."""
    job = job_repo.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation job '{job_id}' was not found.",
        )
    _enforce_job_ownership(job, principal)
    if job.result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Simulation job has not completed with numerical results.",
        )

    csv_bytes: Optional[bytes] = None
    if job.result.artifacts and job.result.artifacts.boundary_csv_key:
        csv_bytes = storage.get_bytes(job.result.artifacts.boundary_csv_key)
    if csv_bytes is None:
        csv_bytes = export_boundary_csv_bytes(job.result)

    filename = f"{_safe_slug(job.project_name)}-{job.job_id[:8]}-boundary-summary.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
