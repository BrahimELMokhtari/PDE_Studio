"""Solver package for PDE Simulation Studio Phase 2."""

from app.solver.exceptions import (
    ExecutionLimitExceededError,
    IllPosedProblemError,
    InvalidSimulationParameterError,
    MeshGenerationError,
    NumericalSolverError,
    SolverError,
)
from app.solver.fem_engine import (
    build_occ_geometry_and_mesh,
    run_steady_state_heat_conduction,
)
from app.solver.package_builder import build_simulation_package_zip
from app.solver.script_generator import generate_reproducible_python_script
from app.solver.unit_converter import (
    NormalizedBoundaryConditionSI,
    NormalizedSIModel,
    convert_and_validate_si_model,
    kelvin_to_model_temp,
    model_temp_to_kelvin,
)

__all__ = [
    "ExecutionLimitExceededError",
    "IllPosedProblemError",
    "InvalidSimulationParameterError",
    "MeshGenerationError",
    "NormalizedBoundaryConditionSI",
    "NormalizedSIModel",
    "NumericalSolverError",
    "SolverError",
    "build_occ_geometry_and_mesh",
    "build_simulation_package_zip",
    "convert_and_validate_si_model",
    "generate_reproducible_python_script",
    "kelvin_to_model_temp",
    "model_temp_to_kelvin",
    "run_steady_state_heat_conduction",
]
