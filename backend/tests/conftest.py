"""Shared pytest fixtures for PDE Simulation Studio backend tests (Phase 1, 2 & 3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories.job_repository import SQLiteSimulationJobRepository
from app.repositories.sqlite_repository import SQLiteProjectRepository
from app.storage import LocalFilesystemStorage


def make_valid_canonical_model_dict() -> dict[str, Any]:
    """Return a canonical v1.0.0 simulation model dictionary."""
    return {
        "schema_version": "1.0.0",
        "metadata": {
            "name": "Copper Thermal Block",
            "description": "Steady-state 3D heat conduction test case",
            "author": "CAE Test Suite",
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
            "dimensions": {
                "length_x": 1.2,
                "length_y": 0.8,
                "length_z": 0.5,
            },
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "rotation_deg": {"x": 0.0, "y": 15.0, "z": 0.0},
        },
        "material": {
            "id": "mat_copper",
            "name": "Copper (C11000)",
            "preset": "copper",
            "thermal_conductivity": 401.0,
        },
        "physics": {
            "type": "steady_state_heat_conduction",
            "volumetric_heat_source": 2500.0,
        },
        "boundary_conditions": {
            "X_MIN": {
                "face_id": "X_MIN",
                "type": "dirichlet",
                "temperature": 373.15,
                "heat_flux": None,
                "convection_coefficient": None,
                "ambient_temperature": None,
            },
            "X_MAX": {
                "face_id": "X_MAX",
                "type": "robin",
                "temperature": None,
                "heat_flux": None,
                "convection_coefficient": 25.0,
                "ambient_temperature": 293.15,
            },
            "Y_MIN": {
                "face_id": "Y_MIN",
                "type": "insulated",
                "temperature": None,
                "heat_flux": None,
                "convection_coefficient": None,
                "ambient_temperature": None,
            },
            "Y_MAX": {
                "face_id": "Y_MAX",
                "type": "neumann",
                "temperature": None,
                "heat_flux": -500.0,
                "convection_coefficient": None,
                "ambient_temperature": None,
            },
            "Z_MIN": {
                "face_id": "Z_MIN",
                "type": "insulated",
                "temperature": None,
                "heat_flux": None,
                "convection_coefficient": None,
                "ambient_temperature": None,
            },
            "Z_MAX": {
                "face_id": "Z_MAX",
                "type": "insulated",
                "temperature": None,
                "heat_flux": None,
                "convection_coefficient": None,
                "ambient_temperature": None,
            },
        },
        "mesh": {
            "element_type": "hexahedral_8node",
            "divisions": {"nx": 12, "ny": 8, "nz": 5},
        },
    }


@pytest.fixture()
def sample_model_dict() -> dict[str, Any]:
    return make_valid_canonical_model_dict()


@pytest.fixture()
def db_file_path(tmp_path: Path) -> str:
    return str(tmp_path / "test_pde_studio.db")


@pytest.fixture()
def storage_dir_path(tmp_path: Path) -> str:
    return str(tmp_path / "artifacts")


@pytest.fixture()
def sqlite_repo(db_file_path: str) -> SQLiteProjectRepository:
    return SQLiteProjectRepository(db_file_path)


@pytest.fixture()
def job_repo(db_file_path: str) -> SQLiteSimulationJobRepository:
    return SQLiteSimulationJobRepository(db_file_path)


@pytest.fixture()
def local_storage(storage_dir_path: str) -> LocalFilesystemStorage:
    return LocalFilesystemStorage(storage_dir_path)


@pytest.fixture()
def client(
    db_file_path: str,
    storage_dir_path: str,
    sqlite_repo: SQLiteProjectRepository,
    job_repo: SQLiteSimulationJobRepository,
    local_storage: LocalFilesystemStorage,
) -> TestClient:
    settings = Settings(
        app_name="PDE Simulation Studio Test API",
        app_env="test",
        cors_origins=["http://localhost:5173", "https://studio.example.com"],
        sqlite_db_path=db_file_path,
        local_storage_path=storage_dir_path,
        redis_url="redis://127.0.0.1:6399/0",  # Forces clean fakeredis fallback in unit tests
    )
    app = create_app(
        settings=settings,
        repository=sqlite_repo,
        job_repository=job_repo,
        artifact_storage=local_storage,
    )
    return TestClient(app)
