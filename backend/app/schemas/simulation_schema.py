"""Pydantic schemas for Phase 2 & 3 FEM Simulation Jobs, Progress, Logs, Convergence, Mesh Quality, Artifacts, and Numerical Results."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.model_schema import CanonicalSimulationModel, FaceId


class JobStatus(str, Enum):
    """Lifecycle states of an asynchronous simulation job."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BoundaryFaceResult(BaseModel):
    """Computed FEM post-processing metrics on a semantic boundary face."""

    face_id: FaceId
    bc_type: str
    area_m2: float
    min_temperature_k: float
    max_temperature_k: float
    mean_temperature_k: float
    min_temperature_display: float
    max_temperature_display: float
    mean_temperature_display: float
    net_outward_heat_rate_w: float


class LineProfileSample(BaseModel):
    """1D temperature profile sampled along a domain centerline axis."""

    coordinate_m: float
    coordinate_display: float
    temperature_k: float
    temperature_display: float


class SurfaceContourMesh(BaseModel):
    """Boundary surface triangle mesh and nodal temperatures for 3D WebGL contour rendering."""

    vertices: list[list[float]] = Field(
        description="3D vertex coordinates [x, y, z] in model length units"
    )
    vertex_temperatures_k: list[float] = Field(
        description="Nodal temperatures in SI Kelvin (K)"
    )
    vertex_temperatures_display: list[float] = Field(
        description="Nodal temperatures in model temperature unit (K or C)"
    )
    triangles: list[list[int]] = Field(
        description="Boundary surface triangles [v0, v1, v2] indexing into vertices"
    )
    triangle_face_ids: list[str] = Field(
        description="Semantic FaceId (X_MIN..Z_MAX) for each boundary triangle"
    )


class ConvergenceInfo(BaseModel):
    """Linear solver convergence and stage timing diagnostics."""

    solver_method: str = "Sparse Cholesky Direct Factorization (SPD)"
    linear_system_residual_l2: float = Field(
        description="L2 norm of free-DOF linear system residual ||K u - f||_2"
    )
    relative_residual_norm: float = Field(
        description="Relative residual ||K u - f||_2 / max(||f||_2, ||K u||_2, 1e-15)"
    )
    energy_balance_rel_error: float = Field(
        description="Relative global conservation error |Q_gen - Q_out| / max(|Q_gen|, |Q_out|, 1.0)"
    )
    converged: bool = True
    geometry_meshing_time_s: float
    assembly_time_s: float
    solve_time_s: float
    postprocess_time_s: float


class MeshQualityStats(BaseModel):
    """3D tetrahedral mesh geometric quality and inline payload statistics."""

    min_edge_length_m: float
    max_edge_length_m: float
    mean_edge_length_m: float
    mean_aspect_ratio: float
    surface_triangles_total: int
    surface_triangles_inline: int
    inline_mesh_truncated: bool = False


class SimulationArtifactsMap(BaseModel):
    """Durable object-storage keys for exported simulation artifacts."""

    vtu_key: Optional[str] = None
    nodal_csv_key: Optional[str] = None
    boundary_csv_key: Optional[str] = None
    script_key: Optional[str] = None
    model_key: Optional[str] = None
    package_zip_key: Optional[str] = None
    total_artifact_bytes: int = 0


class SimulationResultSummary(BaseModel):
    """Complete numerical output from the NGSolve 3D steady-state heat conduction FEM solver."""

    solver_backend: str = "NGSolve / Netgen OpenCASCADE 3D Tetrahedral FEM"
    ngsolve_version: str
    mesh_vertices: int
    mesh_tetrahedra: int
    mesh_surface_triangles: int
    free_dofs: int
    total_dofs: int
    polynomial_order: int
    max_element_size_m: float
    domain_volume_m3: float
    min_temperature_k: float
    max_temperature_k: float
    mean_temperature_k: float
    min_temperature_display: float
    max_temperature_display: float
    mean_temperature_display: float
    temperature_unit: str
    length_unit: str
    max_grad_t_k_per_m: float
    max_heat_flux_w_m2: float
    total_internal_heat_generation_w: float
    net_boundary_heat_loss_w: float
    energy_balance_residual_w: float
    solve_wall_time_seconds: float
    boundary_stats: dict[str, BoundaryFaceResult]
    centerline_profiles: dict[Literal["x", "y", "z"], list[LineProfileSample]]
    surface_mesh: SurfaceContourMesh
    convergence: Optional[ConvergenceInfo] = None
    mesh_quality: Optional[MeshQualityStats] = None
    artifacts: Optional[SimulationArtifactsMap] = None


class SimulationSubmitRequest(BaseModel):
    """Request payload to enqueue and execute a 3D steady-state heat conduction simulation."""

    model_config = ConfigDict(extra="forbid")

    project_id: Optional[str] = Field(default=None)
    model: CanonicalSimulationModel
    max_element_size: Optional[float] = Field(
        default=None, gt=0.0, le=1e6, description="Optional override for h_max in model length units"
    )
    polynomial_order: Optional[int] = Field(
        default=None, ge=1, le=3, description="Optional override for H1 polynomial order"
    )


class SimulationJobResponse(BaseModel):
    """Status, progress, logs, and results of a simulation job."""

    job_id: str
    owner_id: str = "local-dev-user"
    rq_job_id: Optional[str] = None
    project_id: Optional[str] = None
    project_name: str
    status: JobStatus
    progress_percent: int = Field(ge=0, le=100)
    current_stage: str
    logs: list[str] = Field(default_factory=list)
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    model: CanonicalSimulationModel
    result: Optional[SimulationResultSummary] = None


class SimulationScriptResponse(BaseModel):
    """Generated standalone reproducible Python simulation script."""

    filename: str = "simulation.py"
    schema_version: str = "1.0.0"
    script_content: str
    instructions: str


class UserQuotaSummaryResponse(BaseModel):
    """Current authenticated user's resource usage against configured plan limits."""

    owner_id: str
    plan_tier: str
    projects_used: int
    projects_limit: int
    simulations_used: int
    simulations_limit: int
    storage_bytes_used: int
    storage_bytes_limit: int
    max_mesh_elements_limit: int
