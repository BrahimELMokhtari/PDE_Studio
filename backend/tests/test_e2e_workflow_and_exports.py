"""End-to-End Scientific Workflow, VTU/CSV Artifact Export, and Storage Lifecycle Tests."""

from __future__ import annotations

import csv
import io
import zipfile
from typing import Any
from xml.etree import ElementTree as ET

from fastapi.testclient import TestClient


def test_complete_e2e_scientific_workflow_and_artifact_exports(
    client: TestClient, sample_model_dict: dict[str, Any]
) -> None:
    """Test the complete workflow:
    create geometry -> assign conditions -> configure mesh -> generate Python ->
    submit simulation -> verify convergence & results -> export VTU/CSV/ZIP -> delete job & artifacts.
    """
    # 1. Create and persist project with custom geometry, BCs, and mesh configuration
    model_payload = dict(sample_model_dict)
    model_payload["geometry"]["dimensions"] = {
        "length_x": 1.0,
        "length_y": 0.5,
        "length_z": 0.5,
    }
    model_payload["geometry"]["rotation_deg"] = {"x": 0.0, "y": 0.0, "z": 0.0}
    model_payload["physics"]["volumetric_heat_source"] = 0.0
    for fid in ["X_MIN", "X_MAX", "Y_MIN", "Y_MAX", "Z_MIN", "Z_MAX"]:
        model_payload["boundary_conditions"][fid] = {
            "face_id": fid,
            "type": "insulated",
            "temperature": None,
            "heat_flux": None,
            "convection_coefficient": None,
            "ambient_temperature": None,
        }
    model_payload["boundary_conditions"]["X_MIN"] = {
        "face_id": "X_MIN",
        "type": "dirichlet",
        "temperature": 400.0,
        "heat_flux": None,
        "convection_coefficient": None,
        "ambient_temperature": None,
    }
    model_payload["boundary_conditions"]["X_MAX"] = {
        "face_id": "X_MAX",
        "type": "dirichlet",
        "temperature": 300.0,
        "heat_flux": None,
        "convection_coefficient": None,
        "ambient_temperature": None,
    }
    model_payload["mesh"] = {
        "element_type": "tetrahedral_4node",
        "divisions": {"nx": 8, "ny": 4, "nz": 4},
        "max_element_size": 0.25,
        "polynomial_order": 1,
    }

    res_proj = client.post(
        "/api/projects",
        json={
            "name": "E2E Linear Conduction Benchmark",
            "description": "End-to-end validation of Phase 3 scientific platform",
            "model": model_payload,
        },
    )
    assert res_proj.status_code == 201
    project_id = res_proj.json()["id"]

    # 2. Generate reproducible Python script
    res_script = client.post("/api/simulations/script", json=model_payload)
    assert res_script.status_code == 200
    assert "ngsolve" in res_script.json()["script_content"]

    # 3. Submit simulation job and execute synchronously via RQ worker
    res_sim = client.post(
        "/api/simulations?wait=true",
        json={
            "project_id": project_id,
            "model": model_payload,
            "max_element_size": 0.25,
            "polynomial_order": 1,
        },
    )
    assert res_sim.status_code == 202
    job_data = res_sim.json()
    job_id = job_data["job_id"]
    assert job_data["status"] == "completed"

    result = job_data["result"]
    assert result is not None
    assert abs(result["min_temperature_k"] - 300.0) < 1e-3
    assert abs(result["max_temperature_k"] - 400.0) < 1e-3
    assert abs(result["mean_temperature_k"] - 350.0) < 0.5

    # Verify Phase 3 ConvergenceInfo, MeshQualityStats, and SimulationArtifactsMap
    assert result["convergence"] is not None
    assert result["convergence"]["converged"] is True
    assert result["convergence"]["relative_residual_norm"] < 1e-8

    assert result["mesh_quality"] is not None
    assert result["mesh_quality"]["surface_triangles_total"] > 0
    assert result["mesh_quality"]["mean_edge_length_m"] > 0.0

    assert result["artifacts"] is not None
    assert result["artifacts"]["total_artifact_bytes"] > 0
    assert result["artifacts"]["vtu_key"].endswith("solution.vtu")

    # 4. Export VTK XML UnstructuredGrid (.vtu) and verify XML structure
    res_vtu = client.get(f"/api/simulations/{job_id}/artifacts/vtu")
    assert res_vtu.status_code == 200
    vtu_xml = res_vtu.content.decode("utf-8", errors="ignore")
    assert "<VTKFile" in vtu_xml
    assert "UnstructuredGrid" in vtu_xml
    assert "Temperature_K" in vtu_xml
    root = ET.fromstring(vtu_xml)
    assert root.tag == "VTKFile"

    # 5. Export Nodal CSV and verify columns & temperature values
    res_nodal_csv = client.get(f"/api/simulations/{job_id}/artifacts/nodal-csv")
    assert res_nodal_csv.status_code == 200
    nodal_rows = list(csv.reader(io.StringIO(res_nodal_csv.text)))
    assert len(nodal_rows) == result["mesh_vertices"] + 1
    assert nodal_rows[0][0] == "node_id"
    assert "temperature_k" in nodal_rows[0]

    # 6. Export Boundary Summary CSV and verify all 6 semantic faces
    res_bnd_csv = client.get(f"/api/simulations/{job_id}/artifacts/boundary-csv")
    assert res_bnd_csv.status_code == 200
    bnd_rows = list(csv.reader(io.StringIO(res_bnd_csv.text)))
    assert len(bnd_rows) == 7  # header + 6 semantic faces
    exported_faces = {row[0] for row in bnd_rows[1:]}
    assert exported_faces == {"X_MIN", "X_MAX", "Y_MIN", "Y_MAX", "Z_MIN", "Z_MAX"}

    # 7. Download full ZIP package and verify it includes VTU and CSV files
    res_zip = client.get(f"/api/simulations/{job_id}/package")
    assert res_zip.status_code == 200
    with zipfile.ZipFile(io.BytesIO(res_zip.content), mode="r") as zf:
        names = set(zf.namelist())
        assert {
            "simulation.py",
            "model.json",
            "requirements.txt",
            "README.md",
            "results_summary.json",
            "solution.vtu",
            "nodal_results.csv",
            "boundary_summary.csv",
        }.issubset(names)

    # 8. Check user quotas and job history listing endpoints
    res_jobs_list = client.get(f"/api/simulations?project_id={project_id}")
    assert res_jobs_list.status_code == 200
    assert len(res_jobs_list.json()) == 1
    assert res_jobs_list.json()[0]["job_id"] == job_id

    res_quotas = client.get("/api/simulations/quotas")
    assert res_quotas.status_code == 200
    qdata = res_quotas.json()
    assert qdata["projects_used"] == 1
    assert qdata["simulations_used"] == 1
    assert qdata["storage_bytes_used"] > 0

    # 9. Delete simulation job and verify both DB record and artifacts are purged
    res_del = client.delete(f"/api/simulations/{job_id}")
    assert res_del.status_code == 200
    assert res_del.json()["deleted"] is True
    assert res_del.json()["deleted_artifacts_count"] >= 6

    res_quotas_after = client.get("/api/simulations/quotas")
    assert res_quotas_after.json()["simulations_used"] == 0
    assert res_quotas_after.json()["storage_bytes_used"] == 0
