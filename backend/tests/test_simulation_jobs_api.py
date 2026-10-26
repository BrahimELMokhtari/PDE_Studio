"""Integration tests for Asynchronous Simulation Jobs (Redis + RQ), Script Generation, and ZIP Packaging."""

from __future__ import annotations

import io
import zipfile
from typing import Any
from fastapi.testclient import TestClient


def test_submit_and_execute_simulation_job_lifecycle(
    client: TestClient, sample_model_dict: dict[str, Any]
) -> None:
    # Submit simulation job with wait=true (drains RQ burst worker deterministically)
    res_submit = client.post(
        "/api/simulations?wait=true",
        json={
            "model": sample_model_dict,
            "max_element_size": 0.35,
            "polynomial_order": 1,
        },
    )
    assert res_submit.status_code == 202
    job = res_submit.json()
    job_id = job["job_id"]
    assert job["status"] == "completed"
    assert job["progress_percent"] == 100
    assert job["result"] is not None
    assert job["result"]["mesh_tetrahedra"] > 0
    assert job["result"]["min_temperature_k"] > 290.0
    assert len(job["logs"]) >= 4

    # Poll job by ID
    res_poll = client.get(f"/api/simulations/{job_id}")
    assert res_poll.status_code == 200
    assert res_poll.json()["status"] == "completed"

    # Download ZIP package for completed job
    res_zip = client.get(f"/api/simulations/{job_id}/package")
    assert res_zip.status_code == 200
    assert res_zip.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(res_zip.content), "r") as zf:
        names = set(zf.namelist())
        assert {
            "simulation.py",
            "model.json",
            "requirements.txt",
            "README.md",
            "results_summary.json",
        }.issubset(names)
        sim_script = zf.read("simulation.py").decode("utf-8")
        assert "import ngsolve as ngs" in sim_script
        assert "DIRICHLET_BC" in sim_script


def test_ill_posed_simulation_job_transitions_to_failed_state(
    client: TestClient, sample_model_dict: dict[str, Any]
) -> None:
    # Make all 6 faces insulated (ill-posed steady-state problem)
    ill_posed_model = dict(sample_model_dict)
    ill_posed_model["boundary_conditions"] = {
        fid: {
            "face_id": fid,
            "type": "insulated",
            "temperature": None,
            "heat_flux": None,
            "convection_coefficient": None,
            "ambient_temperature": None,
        }
        for fid in ("X_MIN", "X_MAX", "Y_MIN", "Y_MAX", "Z_MIN", "Z_MAX")
    }

    res = client.post(
        "/api/simulations?wait=true",
        json={"model": ill_posed_model},
    )
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "failed"
    assert data["error_type"] == "IllPosedProblemError"
    assert "Ill-posed" in data["error_message"]


def test_generate_reproducible_script_endpoint(
    client: TestClient, sample_model_dict: dict[str, Any]
) -> None:
    res = client.post("/api/simulations/script", json=sample_model_dict)
    assert res.status_code == 200
    payload = res.json()
    assert payload["filename"] == "simulation.py"
    assert "def run_simulation()" in payload["script_content"]
    assert "OCCGeometry" in payload["script_content"]
