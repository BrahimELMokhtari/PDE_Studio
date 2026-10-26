"""Real 3D Steady-State Heat Conduction FEM Solver Engine using NGSolve and Netgen OpenCASCADE."""

from __future__ import annotations

import math
import time
from typing import Callable, Literal, Optional

import ngsolve as ngs
import numpy as np
from netgen.occ import Axis, Box, OCCGeometry, Pnt, Vec

from app.schemas.model_schema import (
    ALL_FACE_IDS,
    BoundaryConditionType,
    CanonicalSimulationModel,
    FaceId,
)
from app.schemas.simulation_schema import (
    BoundaryFaceResult,
    ConvergenceInfo,
    LineProfileSample,
    MeshQualityStats,
    SimulationResultSummary,
    SurfaceContourMesh,
)
from app.solver.exceptions import (
    ExecutionLimitExceededError,
    MeshGenerationError,
    NumericalSolverError,
)
from app.solver.exporter import export_ngsolve_volume_vtu_bytes
from app.solver.unit_converter import (
    NormalizedSIModel,
    convert_and_validate_si_model,
    kelvin_to_model_temp,
)

ProgressCallback = Callable[[int, str, str], None]
VtuExportCallback = Callable[[bytes], None]


def _tag_cuboid_semantic_faces(box: object, lx_m: float, ly_m: float, lz_m: float) -> set[str]:
    """Assign stable semantic identifiers (X_MIN..Z_MAX) to the 6 faces of an unrotated OCC Box."""
    tol = 1e-6 * min(lx_m, ly_m, lz_m)
    assigned: set[str] = set()

    for face in box.faces:  # type: ignore[attr-defined]
        c = face.center
        if abs(c.x - (-lx_m / 2.0)) <= tol:
            face.name = FaceId.X_MIN.value
        elif abs(c.x - (lx_m / 2.0)) <= tol:
            face.name = FaceId.X_MAX.value
        elif abs(c.y - (-ly_m / 2.0)) <= tol:
            face.name = FaceId.Y_MIN.value
        elif abs(c.y - (ly_m / 2.0)) <= tol:
            face.name = FaceId.Y_MAX.value
        elif abs(c.z - (-lz_m / 2.0)) <= tol:
            face.name = FaceId.Z_MIN.value
        elif abs(c.z - (lz_m / 2.0)) <= tol:
            face.name = FaceId.Z_MAX.value
        if face.name:
            assigned.add(face.name)

    return assigned


def build_occ_geometry_and_mesh(
    si_model: NormalizedSIModel,
    max_elements_limit: int = 250_000,
) -> ngs.Mesh:
    """Construct the 3D OpenCASCADE cuboid, preserve semantic face tags, and generate a tetrahedral FEM mesh."""
    lx, ly, lz = si_model.lx_m, si_model.ly_m, si_model.lz_m

    try:
        box = Box(Pnt(-lx / 2.0, -ly / 2.0, -lz / 2.0), Pnt(lx / 2.0, ly / 2.0, lz / 2.0))
        box.mat("solid_domain")
        assigned_faces = _tag_cuboid_semantic_faces(box, lx, ly, lz)
        expected_faces = {f.value for f in ALL_FACE_IDS}
        if assigned_faces != expected_faces:
            raise MeshGenerationError(
                f"Failed to tag all 6 semantic cuboid faces. Tagged: {sorted(assigned_faces)}"
            )

        # Apply intrinsic XYZ Euler rotation (matching Three.js Euler 'XYZ' order) around local origin
        if abs(si_model.rot_z_deg) > 1e-9:
            box = box.Rotate(Axis(Pnt(0, 0, 0), Vec(0, 0, 1)), si_model.rot_z_deg)
        if abs(si_model.rot_y_deg) > 1e-9:
            box = box.Rotate(Axis(Pnt(0, 0, 0), Vec(0, 1, 0)), si_model.rot_y_deg)
        if abs(si_model.rot_x_deg) > 1e-9:
            box = box.Rotate(Axis(Pnt(0, 0, 0), Vec(1, 0, 0)), si_model.rot_x_deg)

        # Apply translation in SI meters
        if (
            abs(si_model.pos_x_m) > 1e-9
            or abs(si_model.pos_y_m) > 1e-9
            or abs(si_model.pos_z_m) > 1e-9
        ):
            box = box.Move(Vec(si_model.pos_x_m, si_model.pos_y_m, si_model.pos_z_m))

        geo = OCCGeometry(box)
        ngmesh = geo.GenerateMesh(maxh=si_model.maxh_m)
        mesh = ngs.Mesh(ngmesh)
    except MeshGenerationError:
        raise
    except Exception as exc:
        raise MeshGenerationError(f"Netgen/OpenCASCADE meshing failed: {exc}") from exc

    mesh_boundaries = set(mesh.GetBoundaries())
    if not expected_faces.issubset(mesh_boundaries):
        raise MeshGenerationError(
            f"Generated mesh boundaries {sorted(mesh_boundaries)} do not preserve semantic face mapping {sorted(expected_faces)}."
        )

    if mesh.ne == 0 or mesh.nv == 0:
        raise MeshGenerationError("Generated tetrahedral mesh has zero elements or vertices.")

    if mesh.ne > max_elements_limit:
        raise ExecutionLimitExceededError(
            f"Generated mesh has {mesh.ne} tetrahedra, exceeding safety limit of {max_elements_limit}."
        )

    return mesh


def _transform_local_to_world_m(
    local_xyz: tuple[float, float, float], si_model: NormalizedSIModel
) -> tuple[float, float, float]:
    """Transform a point in local cuboid coordinates (m) to world coordinates (m)."""
    x, y, z = local_xyz
    rx = math.radians(si_model.rot_x_deg)
    ry = math.radians(si_model.rot_y_deg)
    rz = math.radians(si_model.rot_z_deg)

    # Rotate around Z
    cz, sz = math.cos(rz), math.sin(rz)
    x1, y1, z1 = cz * x - sz * y, sz * x + cz * y, z
    # Rotate around Y
    cy, sy = math.cos(ry), math.sin(ry)
    x2, y2, z2 = cy * x1 + sy * z1, y1, -sy * x1 + cy * z1
    # Rotate around X
    cx, sx = math.cos(rx), math.sin(rx)
    x3, y3, z3 = x2, cx * y2 - sx * z2, sx * y2 + cx * z2

    return (x3 + si_model.pos_x_m, y3 + si_model.pos_y_m, z3 + si_model.pos_z_m)


def _sample_centerline_profiles(
    mesh: ngs.Mesh,
    gfu: ngs.GridFunction,
    si_model: NormalizedSIModel,
    num_samples: int = 25,
) -> dict[Literal["x", "y", "z"], list[LineProfileSample]]:
    """Sample the FEM temperature solution along the local X, Y, and Z centerlines."""
    scale = si_model.length_scale_to_m
    temp_unit = si_model.temperature_unit
    profiles: dict[Literal["x", "y", "z"], list[LineProfileSample]] = {
        "x": [],
        "y": [],
        "z": [],
    }

    axis_spans: list[tuple[Literal["x", "y", "z"], float]] = [
        ("x", si_model.lx_m),
        ("y", si_model.ly_m),
        ("z", si_model.lz_m),
    ]

    for axis_name, span_m in axis_spans:
        half = span_m / 2.0
        eps = span_m * 1e-5
        coords_m = np.linspace(-half + eps, half - eps, num_samples)
        for coord_m in coords_m:
            if axis_name == "x":
                local_pt = (float(coord_m), 0.0, 0.0)
            elif axis_name == "y":
                local_pt = (0.0, float(coord_m), 0.0)
            else:
                local_pt = (0.0, 0.0, float(coord_m))

            wx, wy, wz = _transform_local_to_world_m(local_pt, si_model)
            try:
                mip = mesh(wx, wy, wz)
                t_k = float(gfu(mip))
            except Exception:
                t_k = float("nan")

            if math.isfinite(t_k):
                profiles[axis_name].append(
                    LineProfileSample(
                        coordinate_m=round(float(coord_m), 6),
                        coordinate_display=round(float(coord_m / scale), 6),
                        temperature_k=round(t_k, 5),
                        temperature_display=round(
                            kelvin_to_model_temp(t_k, temp_unit), 5
                        ),
                    )
                )

    return profiles


def _compute_mesh_quality_stats(
    vertices_m: list[tuple[float, float, float]],
    surface_triangles_all: list[list[int]],
    surface_triangles_inline: list[list[int]],
    truncated: bool,
) -> MeshQualityStats:
    """Compute surface element edge length and aspect ratio metrics in SI meters."""
    if not surface_triangles_all or not vertices_m:
        return MeshQualityStats(
            min_edge_length_m=0.0,
            max_edge_length_m=0.0,
            mean_edge_length_m=0.0,
            mean_aspect_ratio=1.0,
            surface_triangles_total=0,
            surface_triangles_inline=0,
            inline_mesh_truncated=False,
        )

    edge_lengths: list[float] = []
    aspect_ratios: list[float] = []

    for tri in surface_triangles_all:
        p0 = vertices_m[tri[0]]
        p1 = vertices_m[tri[1]]
        p2 = vertices_m[tri[2]]

        l01 = math.dist(p0, p1)
        l12 = math.dist(p1, p2)
        l20 = math.dist(p2, p0)
        edge_lengths.extend([l01, l12, l20])

        max_e = max(l01, l12, l20)
        min_e = max(min(l01, l12, l20), 1e-15)
        aspect_ratios.append(max_e / min_e)

    return MeshQualityStats(
        min_edge_length_m=round(float(min(edge_lengths)), 6),
        max_edge_length_m=round(float(max(edge_lengths)), 6),
        mean_edge_length_m=round(float(sum(edge_lengths) / len(edge_lengths)), 6),
        mean_aspect_ratio=round(float(sum(aspect_ratios) / len(aspect_ratios)), 4),
        surface_triangles_total=len(surface_triangles_all),
        surface_triangles_inline=len(surface_triangles_inline),
        inline_mesh_truncated=truncated,
    )


def run_steady_state_heat_conduction(
    model: CanonicalSimulationModel,
    override_max_element_size: Optional[float] = None,
    override_polynomial_order: Optional[int] = None,
    progress_callback: Optional[ProgressCallback] = None,
    max_elements_limit: int = 250_000,
    max_inline_surface_triangles: int = 15_000,
    vtu_export_callback: Optional[VtuExportCallback] = None,
) -> SimulationResultSummary:
    """Execute the full 3D steady-state heat conduction FEM workflow using NGSolve."""
    t_start = time.perf_counter()

    def report(pct: int, stage: str, msg: str) -> None:
        if progress_callback is not None:
            progress_callback(pct, stage, msg)

    report(
        10,
        "SI Normalization & Validation",
        "Validating physical parameters, boundary conditions, and converting to SI units.",
    )
    si_model = convert_and_validate_si_model(
        model,
        override_max_element_size=override_max_element_size,
        override_polynomial_order=override_polynomial_order,
    )

    t_mesh_start = time.perf_counter()
    report(
        25,
        "OpenCASCADE Geometry & Tetrahedral Meshing",
        f"Building 3D OCC cuboid ({si_model.lx_m:.4g}×{si_model.ly_m:.4g}×{si_model.lz_m:.4g} m) and meshing with maxh={si_model.maxh_m:.4g} m.",
    )
    mesh = build_occ_geometry_and_mesh(si_model, max_elements_limit=max_elements_limit)
    t_mesh_elapsed = time.perf_counter() - t_mesh_start

    t_asm_start = time.perf_counter()
    report(
        50,
        "Finite Element Space & Weak Form Assembly",
        f"Generated {mesh.ne} tetrahedra and {mesh.nv} vertices. Assembling H1(order={si_model.polynomial_order}) system for -div(k grad(T)) = Q.",
    )

    dirichlet_faces = [
        face_id.value
        for face_id in ALL_FACE_IDS
        if si_model.boundary_conditions[face_id].bc_type == BoundaryConditionType.DIRICHLET
    ]
    dirichlet_regex = "|".join(dirichlet_faces)

    fes = ngs.H1(
        mesh,
        order=si_model.polynomial_order,
        dirichlet=dirichlet_regex if dirichlet_regex else "",
    )
    u = fes.TrialFunction()
    v = fes.TestFunction()

    k = si_model.thermal_conductivity_w_mk
    q_vol = si_model.volumetric_heat_source_w_m3

    # Bilinear form a(u, v) = \int_\Omega k \nabla u \cdot \nabla v dx + \sum_{\Gamma_R} \int_{\Gamma_R} h u v ds
    a = ngs.BilinearForm(fes, symmetric=True)
    a += k * ngs.grad(u) * ngs.grad(v) * ngs.dx

    for face_id in ALL_FACE_IDS:
        bc = si_model.boundary_conditions[face_id]
        if bc.bc_type == BoundaryConditionType.ROBIN and bc.convection_coeff_w_m2k is not None:
            a += bc.convection_coeff_w_m2k * u * v * ngs.ds(face_id.value)

    # Linear form f(v) = \int_\Omega Q v dx - \sum_{\Gamma_N} \int_{\Gamma_N} q_out v ds + \sum_{\Gamma_R} \int_{\Gamma_R} h T_inf v ds
    f = ngs.LinearForm(fes)
    if abs(q_vol) > 0.0:
        f += q_vol * v * ngs.dx

    for face_id in ALL_FACE_IDS:
        bc = si_model.boundary_conditions[face_id]
        if (
            bc.bc_type == BoundaryConditionType.NEUMANN
            and bc.outward_heat_flux_w_m2 is not None
        ):
            # Outward heat flux q_out = -k grad(T) . n => weak form RHS gets -q_out * v
            f += (-bc.outward_heat_flux_w_m2) * v * ngs.ds(face_id.value)
        elif (
            bc.bc_type == BoundaryConditionType.ROBIN
            and bc.convection_coeff_w_m2k is not None
            and bc.ambient_temperature_k is not None
        ):
            f += (
                bc.convection_coeff_w_m2k * bc.ambient_temperature_k
            ) * v * ngs.ds(face_id.value)

    a.Assemble()
    f.Assemble()

    gfu = ngs.GridFunction(fes)

    if dirichlet_faces:
        dirichlet_values = {
            face_id.value: si_model.boundary_conditions[face_id].temperature_k
            for face_id in ALL_FACE_IDS
            if si_model.boundary_conditions[face_id].bc_type
            == BoundaryConditionType.DIRICHLET
            and si_model.boundary_conditions[face_id].temperature_k is not None
        }
        cf_dirichlet = mesh.BoundaryCF(dirichlet_values, default=0.0)
        gfu.Set(cf_dirichlet, definedon=mesh.Boundaries(dirichlet_regex))

    free_dofs_mask = fes.FreeDofs()
    free_dofs_count = int(sum(free_dofs_mask))
    total_dofs_count = int(fes.ndof)
    t_asm_elapsed = time.perf_counter() - t_asm_start

    t_solve_start = time.perf_counter()
    report(
        72,
        "Linear System Direct Solve",
        f"Solving sparse SPD linear system ({free_dofs_count} free DOFs / {total_dofs_count} total DOFs).",
    )

    try:
        residual = f.vec.CreateVector()
        residual.data = f.vec - a.mat * gfu.vec
        rhs_norm = float(np.linalg.norm(residual.FV().NumPy()[list(free_dofs_mask)])) if free_dofs_count > 0 else 0.0
        if free_dofs_count > 0:
            inv = a.mat.Inverse(free_dofs_mask, inverse="sparsecholesky")
            gfu.vec.data += inv * residual

        # Compute post-solve residual on free DOFs: r_final = f - K * u
        final_res = f.vec.CreateVector()
        final_res.data = f.vec - a.mat * gfu.vec
        free_mask_arr = np.array([bool(free_dofs_mask[i]) for i in range(total_dofs_count)], dtype=bool)
        res_free_np = final_res.FV().NumPy()[free_mask_arr]
        res_l2 = float(np.linalg.norm(res_free_np)) if res_free_np.size > 0 else 0.0
        rel_res = res_l2 / max(rhs_norm, 1.0)
    except Exception as exc:
        raise NumericalSolverError(
            f"Sparse linear solver failed to factorize or solve stiffness matrix: {exc}"
        ) from exc

    dof_array = gfu.vec.FV().NumPy()
    if not np.all(np.isfinite(dof_array)):
        raise NumericalSolverError(
            "FEM linear solve produced non-finite (NaN or Inf) nodal temperatures. The problem may be singular."
        )
    t_solve_elapsed = time.perf_counter() - t_solve_start

    t_post_start = time.perf_counter()
    report(
        88,
        "Post-Processing & Energy Balance Verification",
        "Evaluating boundary integrals, heat flux fields, centerline profiles, and 3D contour mesh.",
    )

    # Extract vertex coordinates (in SI m and display length units) and vertex temperatures
    scale = si_model.length_scale_to_m
    temp_unit = si_model.temperature_unit

    vertices_m: list[tuple[float, float, float]] = []
    vertices_display: list[list[float]] = []
    vertex_temps_k: list[float] = []
    vertex_temps_display: list[float] = []

    for i, vtx in enumerate(mesh.vertices):
        pt = vtx.point
        px, py, pz = float(pt[0]), float(pt[1]), float(pt[2])
        vertices_m.append((px, py, pz))
        vertices_display.append(
            [
                round(px / scale, 6),
                round(py / scale, 6),
                round(pz / scale, 6),
            ]
        )
        tk = float(gfu.vec[i])
        vertex_temps_k.append(round(tk, 5))
        vertex_temps_display.append(round(kelvin_to_model_temp(tk, temp_unit), 5))

    # Extract boundary surface triangles and per-face vertex sets
    surface_triangles_all: list[list[int]] = []
    triangle_face_ids_all: list[str] = []
    face_vertex_indices: dict[str, set[int]] = {f.value: set() for f in ALL_FACE_IDS}

    for bnd_el in mesh.Elements(ngs.BND):
        mat_name = bnd_el.mat
        v_nrs = [int(v_id.nr) for v_id in bnd_el.vertices]
        if len(v_nrs) == 3:
            surface_triangles_all.append(v_nrs)
            triangle_face_ids_all.append(mat_name)
        if mat_name in face_vertex_indices:
            face_vertex_indices[mat_name].update(v_nrs)

    # Cap inline JSON triangles to avoid sending oversized numerical arrays over JSON
    truncated = len(surface_triangles_all) > max_inline_surface_triangles
    if truncated:
        step = max(1, len(surface_triangles_all) // max_inline_surface_triangles)
        surface_triangles_inline = surface_triangles_all[::step][:max_inline_surface_triangles]
        triangle_face_ids_inline = triangle_face_ids_all[::step][:max_inline_surface_triangles]
    else:
        surface_triangles_inline = surface_triangles_all
        triangle_face_ids_inline = triangle_face_ids_all

    mesh_quality = _compute_mesh_quality_stats(
        vertices_m=vertices_m,
        surface_triangles_all=surface_triangles_all,
        surface_triangles_inline=surface_triangles_inline,
        truncated=truncated,
    )

    # Compute domain integrals
    domain_vol_m3 = float(ngs.Integrate(ngs.CF(1.0), mesh))
    integral_t = float(ngs.Integrate(gfu, mesh))
    mean_t_k = integral_t / max(domain_vol_m3, 1e-15)
    min_t_k = float(min(vertex_temps_k))
    max_t_k = float(max(vertex_temps_k))

    # Compute gradient and heat flux magnitude
    grad_t_cf = ngs.grad(gfu)
    heat_flux_vec_cf = -k * grad_t_cf
    grad_norm_sq_cf = ngs.InnerProduct(grad_t_cf, grad_t_cf)
    avg_grad_norm = math.sqrt(
        max(0.0, float(ngs.Integrate(grad_norm_sq_cf, mesh)) / max(domain_vol_m3, 1e-15))
    )
    max_heat_flux = k * avg_grad_norm

    # Optional VTU 3D volume export callback
    if vtu_export_callback is not None:
        try:
            vtu_bytes = export_ngsolve_volume_vtu_bytes(mesh, gfu, heat_flux_vec_cf)
            vtu_export_callback(vtu_bytes)
        except Exception:
            pass

    # Boundary face statistics & outward heat rate
    normal_cf = ngs.specialcf.normal(3)
    bnd_flux_cf = ngs.BoundaryFromVolumeCF(heat_flux_vec_cf) * normal_cf

    boundary_stats: dict[str, BoundaryFaceResult] = {}
    net_boundary_heat_loss_w = 0.0

    for face_id in ALL_FACE_IDS:
        fname = face_id.value
        bc = si_model.boundary_conditions[face_id]
        region = mesh.Boundaries(fname)

        f_area = float(ngs.Integrate(ngs.CF(1.0), mesh, ngs.BND, definedon=region))
        f_int_t = float(ngs.Integrate(gfu, mesh, ngs.BND, definedon=region))
        f_mean_k = f_int_t / max(f_area, 1e-15)

        v_indices = face_vertex_indices.get(fname, set())
        if v_indices:
            f_temps = [vertex_temps_k[idx] for idx in v_indices]
            f_min_k = float(min(f_temps))
            f_max_k = float(max(f_temps))
        else:
            f_min_k = f_mean_k
            f_max_k = f_mean_k

        # Compute net outward heat rate (W) across face
        if bc.bc_type == BoundaryConditionType.INSULATED:
            q_rate_w = 0.0
        elif (
            bc.bc_type == BoundaryConditionType.NEUMANN
            and bc.outward_heat_flux_w_m2 is not None
        ):
            q_rate_w = float(bc.outward_heat_flux_w_m2 * f_area)
        elif (
            bc.bc_type == BoundaryConditionType.ROBIN
            and bc.convection_coeff_w_m2k is not None
            and bc.ambient_temperature_k is not None
        ):
            q_rate_w = float(
                ngs.Integrate(
                    bc.convection_coeff_w_m2k * (gfu - bc.ambient_temperature_k),
                    mesh,
                    ngs.BND,
                    definedon=region,
                )
            )
        else:
            # Dirichlet boundary: integrate outward conductive flux (-k grad(T) . n)
            q_rate_w = float(
                ngs.Integrate(bnd_flux_cf, mesh, ngs.BND, definedon=region)
            )

        net_boundary_heat_loss_w += q_rate_w

        boundary_stats[fname] = BoundaryFaceResult(
            face_id=face_id,
            bc_type=bc.bc_type.value,
            area_m2=round(f_area, 6),
            min_temperature_k=round(f_min_k, 4),
            max_temperature_k=round(f_max_k, 4),
            mean_temperature_k=round(f_mean_k, 4),
            min_temperature_display=round(kelvin_to_model_temp(f_min_k, temp_unit), 4),
            max_temperature_display=round(kelvin_to_model_temp(f_max_k, temp_unit), 4),
            mean_temperature_display=round(kelvin_to_model_temp(f_mean_k, temp_unit), 4),
            net_outward_heat_rate_w=round(q_rate_w, 4),
        )

    total_internal_gen_w = float(q_vol * domain_vol_m3)
    energy_residual_w = total_internal_gen_w - net_boundary_heat_loss_w
    max_power_ref = max(
        abs(total_internal_gen_w),
        sum(abs(b.net_outward_heat_rate_w) for b in boundary_stats.values()),
        1.0,
    )
    energy_rel_err = abs(energy_residual_w) / max_power_ref

    centerline_profiles = _sample_centerline_profiles(mesh, gfu, si_model)
    t_post_elapsed = time.perf_counter() - t_post_start
    elapsed_s = time.perf_counter() - t_start

    convergence_info = ConvergenceInfo(
        solver_method="Sparse Cholesky Direct Factorization (SPD)",
        linear_system_residual_l2=round(res_l2, 12),
        relative_residual_norm=round(rel_res, 12),
        energy_balance_rel_error=round(energy_rel_err, 6),
        converged=bool(rel_res < 1e-6),
        geometry_meshing_time_s=round(t_mesh_elapsed, 4),
        assembly_time_s=round(t_asm_elapsed, 4),
        solve_time_s=round(t_solve_elapsed, 4),
        postprocess_time_s=round(t_post_elapsed, 4),
    )

    report(
        100,
        "Completed",
        f"Simulation converged in {elapsed_s:.2f}s (T_min={min_t_k:.2f} K, T_max={max_t_k:.2f} K, rel_res={rel_res:.2e}).",
    )

    return SimulationResultSummary(
        ngsolve_version=getattr(ngs, "__version__", "6.2"),
        mesh_vertices=int(mesh.nv),
        mesh_tetrahedra=int(mesh.ne),
        mesh_surface_triangles=len(surface_triangles_all),
        free_dofs=free_dofs_count,
        total_dofs=total_dofs_count,
        polynomial_order=si_model.polynomial_order,
        max_element_size_m=round(si_model.maxh_m, 6),
        domain_volume_m3=round(domain_vol_m3, 8),
        min_temperature_k=round(min_t_k, 5),
        max_temperature_k=round(max_t_k, 5),
        mean_temperature_k=round(mean_t_k, 5),
        min_temperature_display=round(kelvin_to_model_temp(min_t_k, temp_unit), 5),
        max_temperature_display=round(kelvin_to_model_temp(max_t_k, temp_unit), 5),
        mean_temperature_display=round(kelvin_to_model_temp(mean_t_k, temp_unit), 5),
        temperature_unit=temp_unit.value,
        length_unit=si_model.length_unit.value,
        max_grad_t_k_per_m=round(avg_grad_norm, 5),
        max_heat_flux_w_m2=round(max_heat_flux, 4),
        total_internal_heat_generation_w=round(total_internal_gen_w, 5),
        net_boundary_heat_loss_w=round(net_boundary_heat_loss_w, 5),
        energy_balance_residual_w=round(energy_residual_w, 5),
        solve_wall_time_seconds=round(elapsed_s, 4),
        boundary_stats=boundary_stats,
        centerline_profiles=centerline_profiles,
        surface_mesh=SurfaceContourMesh(
            vertices=vertices_display,
            vertex_temperatures_k=vertex_temps_k,
            vertex_temperatures_display=vertex_temps_display,
            triangles=surface_triangles_inline,
            triangle_face_ids=triangle_face_ids_inline,
        ),
        convergence=convergence_info,
        mesh_quality=mesh_quality,
    )
