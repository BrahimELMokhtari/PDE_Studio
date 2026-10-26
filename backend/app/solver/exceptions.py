"""Custom exception hierarchy for the Phase 2 FEM Solver Engine."""

from __future__ import annotations


class SolverError(Exception):
    """Base exception for all PDE solver and pre-processing errors."""


class IllPosedProblemError(SolverError):
    """Raised when the boundary value problem is mathematically ill-posed or singular."""


class InvalidSimulationParameterError(SolverError):
    """Raised when physical, geometric, or meshing parameters violate solver constraints."""


class MeshGenerationError(SolverError):
    """Raised when Netgen/OpenCASCADE 3D tetrahedral mesh generation fails."""


class ExecutionLimitExceededError(SolverError):
    """Raised when mesh size, degree-of-freedom count, or runtime exceeds safety limits."""


class NumericalSolverError(SolverError):
    """Raised when linear system factorization or solve produces singular/non-finite results."""
