"""Scientific Validation Test Suite for the NGSolve 3D Steady-State Heat Conduction FEM Solver."""

from __future__ import annotations

from typing import Any
import pytest

from app.schemas.model_schema import ALL_FACE_IDS, CanonicalSimulationModel
from app.solver.exceptions import (
    IllPosedProblemError,
    InvalidSimulationParameterError,
)
from app.solver.fem_engine import run_steady_state_heat_conduction


def _make_all_insulated_bcs() -> dict[str, Any]:
    return {
        face.value: {
            "face_id": face.value,
            "type": "insulated",
            "temperature": None,
            "heat_flux": None,
            "convection_coefficient": None,
            "ambient_temperature": None,
        }
        for face in ALL_FACE_IDS
    }


def _make_base_test_model() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "metadata": {
            "name": "Analytical Validation Cuboid",
            "description": "Scientific benchmark test",
            "author": "Scientific Validation Suite",
        },
        "units": {
            "length": "m",
            "temperature": "K",
            "thermal_conductivity": "W/(m*K)",
            "heat_source": "W/m^3",
            "heat_flux": "W/m^2",
            "convection_coefficient": "W/(m^2*K)",
        },
        "geometry": {
            "type": "rectangular_cuboid",
            "dimensions": {"length_x": 1.0, "length_y": 0.4, "length_z": 0.4},
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "rotation_deg": {"x": 0.0, "y": 0.0, "z": 0.0},
        },
        "material": {
            "id": "mat_test",
            "name": "Isotropic Test Conductor",
            "preset": "custom",
            "thermal_conductivity": 100.0,
        },
        "physics": {
            "type": "steady_state_heat_conduction",
            "volumetric_heat_source": 0.0,
        },
        "boundary_conditions": _make_all_insulated_bcs(),
        "mesh": {
            "element_type": "tetrahedral_4node",
            "divisions": {"nx": 5, "ny": 2, "nz": 2},
            "max_element_size": 0.25,
            "polynomial_order": 1,
        },
    }


def test_linear_conduction_between_opposite_faces_matches_analytical_solution() -> None:
    """
    Benchmark 1:
    Cuboid with X_MIN at T1 = 400 K, X_MAX at T2 = 300 K, remaining 4 faces insulated, Q = 0.
    Exact analytical solution: T(x) = 350 - 100 * x for x in [-0.5, 0.5].
    Mean temperature = 350 K; conductive heat rate = k * A * (T1 - T2) / Lx = 100 * 0.16 * 100 / 1.0 = 1600 W.
    """
    raw = _make_base_test_model()
    raw["boundary_conditions"]["X_MIN"] = {
        "face_id": "X_MIN",
        "type": "dirichlet",
        "temperature": 400.0,
        "heat_flux": None,
        "convection_coefficient": None,
        "ambient_temperature": None,
    }
    raw["boundary_conditions"]["X_MAX"] = {
        "face_id": "X_MAX",
        "type": "dirichlet",
        "temperature": 300.0,
        "heat_flux": None,
        "convection_coefficient": None,
        "ambient_temperature": None,
    }
    model = CanonicalSimulationModel.model_validate(raw)
    result = run_steady_state_heat_conduction(model)

    assert result.min_temperature_k == pytest.approx(300.0, abs=1e-4)
    assert result.max_temperature_k == pytest.approx(400.0, abs=1e-4)
    assert result.mean_temperature_k == pytest.approx(350.0, abs=1e-3)

    # Check every sample along the X centerline against T_exact(x) = 350 - 100 * x
    x_profile = result.centerline_profiles["x"]
    assert len(x_profile) >= 10
    for sample in x_profile:
        t_exact = 350.0 - 100.0 * sample.coordinate_m
        assert sample.temperature_k == pytest.approx(t_exact, abs=1e-3)

    # Check boundary heat rate on X_MAX (+1600 W leaving X_MAX) and X_MIN (-1600 W leaving X_MIN)
    assert result.boundary_stats["X_MAX"].net_outward_heat_rate_w == pytest.approx(
        1600.0, rel=1e-2
    )
    assert result.boundary_stats["X_MIN"].net_outward_heat_rate_w == pytest.approx(
        -1600.0, rel=1e-2
    )


def test_mesh_refinement_and_convergence_with_internal_heat_source() -> None:
    """
    Benchmark 2:
    1D slab conduction with uniform internal volumetric heat generation Q = 8000 W/m^3,
    k = 100 W/(m*K), Lx = 1.0 m, X_MIN and X_MAX held at T0 = 300 K, other 4 faces insulated.
    Exact analytical parabolic solution:
      T(x) = 300 + (Q / (2*k)) * (0.25 - x^2) = 300 + 40 * (0.25 - x^2)
      T_max(0) = 310.0 K, Mean T = 300 + (Q * Lx^2) / (12 * k) = 306.6667 K.
    Verify that refining the tetrahedral mesh reduces the numerical error monotonically.
    """
    raw = _make_base_test_model()
    raw["physics"]["volumetric_heat_source"] = 8000.0
    for face_name in ("X_MIN", "X_MAX"):
        raw["boundary_conditions"][face_name] = {
            "face_id": face_name,
            "type": "dirichlet",
            "temperature": 300.0,
            "heat_flux": None,
            "convection_coefficient": None,
            "ambient_temperature": None,
        }
    model = CanonicalSimulationModel.model_validate(raw)

    exact_mean_t = 300.0 + (8000.0 * 1.0**2) / (12.0 * 100.0)  # 306.66667 K

    res_coarse = run_steady_state_heat_conduction(
        model, override_max_element_size=0.45, override_polynomial_order=1
    )
    res_fine = run_steady_state_heat_conduction(
        model, override_max_element_size=0.16, override_polynomial_order=1
    )
    res_p2 = run_steady_state_heat_conduction(
        model, override_max_element_size=0.35, override_polynomial_order=2
    )

    assert res_fine.mesh_tetrahedra > res_coarse.mesh_tetrahedra

    err_coarse = abs(res_coarse.mean_temperature_k - exact_mean_t)
    err_fine = abs(res_fine.mean_temperature_k - exact_mean_t)
    err_p2 = abs(res_p2.mean_temperature_k - exact_mean_t)

    assert err_fine < err_coarse
    # Quadratic (P2) elements capture the quadratic temperature profile almost exactly
    assert err_p2 < 1e-3
    assert res_p2.max_temperature_k == pytest.approx(310.0, abs=5e-2)


def test_semantic_boundary_condition_mapping_across_axes() -> None:
    """
    Benchmark 3:
    Verify that GUI surface identifiers Y_MIN / Y_MAX and Z_MIN / Z_MAX map to the exact
    corresponding solver boundary faces in 3D.
    """
    raw = _make_base_test_model()
    raw["geometry"]["dimensions"] = {"length_x": 0.4, "length_y": 1.0, "length_z": 0.4}
    raw["boundary_conditions"]["Y_MIN"] = {
        "face_id": "Y_MIN",
        "type": "dirichlet",
        "temperature": 280.0,
        "heat_flux": None,
        "convection_coefficient": None,
        "ambient_temperature": None,
    }
    raw["boundary_conditions"]["Y_MAX"] = {
        "face_id": "Y_MAX",
        "type": "dirichlet",
        "temperature": 380.0,
        "heat_flux": None,
        "convection_coefficient": None,
        "ambient_temperature": None,
    }
    model = CanonicalSimulationModel.model_validate(raw)
    result = run_steady_state_heat_conduction(model, override_max_element_size=0.25)

    assert result.boundary_stats["Y_MIN"].mean_temperature_k == pytest.approx(
        280.0, abs=1e-3
    )
    assert result.boundary_stats["Y_MAX"].mean_temperature_k == pytest.approx(
        380.0, abs=1e-3
    )
    # Lateral faces X_MIN, X_MAX, Z_MIN, Z_MAX must average the midpoint temperature 330 K
    for lateral in ("X_MIN", "X_MAX", "Z_MIN", "Z_MAX"):
        assert result.boundary_stats[lateral].mean_temperature_k == pytest.approx(
            330.0, abs=2.0
        )


def test_neumann_outward_heat_flux_sign_conventions_and_robin_convection() -> None:
    """
    Benchmark 4:
    Verify outward heat flux sign convention (-k grad(T) . n = q_out):
    - X_MIN fixed at T0 = 350 K, Lx = 1.0 m, k = 100 W/(m*K), Q = 0.
    - Case A: Positive outward heat flux q_out = +2000 W/m^2 on X_MAX (heat leaving domain -> cooling):
        Exact T(X_MAX) = 350 - (2000 * 1.0) / 100 = 330 K.
    - Case B: Negative outward heat flux q_out = -2000 W/m^2 on X_MAX (heat entering domain -> heating):
        Exact T(X_MAX) = 350 - (-2000 * 1.0) / 100 = 370 K.
    - Case C: Robin convection on X_MAX with h = 100 W/(m^2*K), T_inf = 250 K:
        Exact q = (350 - 250) / (1/100 + 1/100) = 5000 W/m^2 => T(X_MAX) = 300 K.
    """
    raw = _make_base_test_model()
    raw["boundary_conditions"]["X_MIN"] = {
        "face_id": "X_MIN",
        "type": "dirichlet",
        "temperature": 350.0,
        "heat_flux": None,
        "convection_coefficient": None,
        "ambient_temperature": None,
    }

    # Case A: q_out = +2000 W/m^2 (cooling)
    raw["boundary_conditions"]["X_MAX"] = {
        "face_id": "X_MAX",
        "type": "neumann",
        "temperature": None,
        "heat_flux": 2000.0,
        "convection_coefficient": None,
        "ambient_temperature": None,
    }
    res_cooling = run_steady_state_heat_conduction(
        CanonicalSimulationModel.model_validate(raw)
    )
    assert res_cooling.boundary_stats["X_MAX"].mean_temperature_k == pytest.approx(
        330.0, abs=1e-2
    )

    # Case B: q_out = -2000 W/m^2 (heating)
    raw["boundary_conditions"]["X_MAX"]["heat_flux"] = -2000.0
    res_heating = run_steady_state_heat_conduction(
        CanonicalSimulationModel.model_validate(raw)
    )
    assert res_heating.boundary_stats["X_MAX"].mean_temperature_k == pytest.approx(
        370.0, abs=1e-2
    )

    # Case C: Robin convection (h = 100, T_inf = 250 K)
    raw["boundary_conditions"]["X_MAX"] = {
        "face_id": "X_MAX",
        "type": "robin",
        "temperature": None,
        "heat_flux": None,
        "convection_coefficient": 100.0,
        "ambient_temperature": 250.0,
    }
    res_robin = run_steady_state_heat_conduction(
        CanonicalSimulationModel.model_validate(raw)
    )
    assert res_robin.boundary_stats["X_MAX"].mean_temperature_k == pytest.approx(
        300.0, abs=1e-2
    )


def test_si_unit_conversion_mm_and_celsius() -> None:
    """
    Benchmark 5:
    Verify that a model specified in millimeters (1000 mm x 400 mm x 400 mm) and Celsius
    (X_MIN = 100 °C, X_MAX = 0 °C) converts accurately to SI meters and Kelvin.
    """
    raw = _make_base_test_model()
    raw["units"]["length"] = "mm"
    raw["units"]["temperature"] = "C"
    raw["geometry"]["dimensions"] = {
        "length_x": 1000.0,
        "length_y": 400.0,
        "length_z": 400.0,
    }
    raw["mesh"]["max_element_size"] = 250.0  # 250 mm = 0.25 m
    raw["boundary_conditions"]["X_MIN"] = {
        "face_id": "X_MIN",
        "type": "dirichlet",
        "temperature": 100.0,
        "heat_flux": None,
        "convection_coefficient": None,
        "ambient_temperature": None,
    }
    raw["boundary_conditions"]["X_MAX"] = {
        "face_id": "X_MAX",
        "type": "dirichlet",
        "temperature": 0.0,
        "heat_flux": None,
        "convection_coefficient": None,
        "ambient_temperature": None,
    }

    model = CanonicalSimulationModel.model_validate(raw)
    result = run_steady_state_heat_conduction(model)

    assert result.domain_volume_m3 == pytest.approx(0.16, rel=1e-4)
    assert result.min_temperature_k == pytest.approx(273.15, abs=1e-3)
    assert result.max_temperature_k == pytest.approx(373.15, abs=1e-3)
    assert result.min_temperature_display == pytest.approx(0.0, abs=1e-3)
    assert result.max_temperature_display == pytest.approx(100.0, abs=1e-3)
    assert result.mean_temperature_display == pytest.approx(50.0, abs=1e-2)


def test_ill_posed_and_singular_problems_detected_and_rejected() -> None:
    """
    Benchmark 6:
    Verify that pure Neumann / all-insulated problems (missing thermal reference condition)
    raise IllPosedProblemError, and overly fine element sizes raise InvalidSimulationParameterError.
    """
    # All 6 faces insulated -> singular stiffness matrix
    raw_insulated = _make_base_test_model()
    model_insulated = CanonicalSimulationModel.model_validate(raw_insulated)
    with pytest.raises(IllPosedProblemError, match="Ill-posed steady-state thermal problem"):
        run_steady_state_heat_conduction(model_insulated)

    # Pure Neumann + Insulated without Dirichlet/Robin -> singular stiffness matrix
    raw_neumann = _make_base_test_model()
    raw_neumann["boundary_conditions"]["X_MIN"] = {
        "face_id": "X_MIN",
        "type": "neumann",
        "temperature": None,
        "heat_flux": -500.0,
        "convection_coefficient": None,
        "ambient_temperature": None,
    }
    model_neumann = CanonicalSimulationModel.model_validate(raw_neumann)
    with pytest.raises(IllPosedProblemError):
        run_steady_state_heat_conduction(model_neumann)

    # Valid Dirichlet face, but element size violates safety limit
    raw_valid = _make_base_test_model()
    raw_valid["boundary_conditions"]["X_MIN"] = {
        "face_id": "X_MIN",
        "type": "dirichlet",
        "temperature": 350.0,
        "heat_flux": None,
        "convection_coefficient": None,
        "ambient_temperature": None,
    }
    model_valid = CanonicalSimulationModel.model_validate(raw_valid)
    with pytest.raises(InvalidSimulationParameterError):
        run_steady_state_heat_conduction(model_valid, override_max_element_size=1e-5)
