"""Integration tests for Project CRUD, validation, and import/export API endpoints."""

from __future__ import annotations

from typing import Any
from fastapi.testclient import TestClient


def test_project_crud_lifecycle(
    client: TestClient, sample_model_dict: dict[str, Any]
) -> None:
    # 1. Initially empty
    res_list = client.get("/api/projects")
    assert res_list.status_code == 200
    assert res_list.json() == []

    # 2. Create project
    create_payload = {
        "name": "Aluminum Heat Spreader",
        "description": "Electronic package thermal test",
        "model": sample_model_dict,
    }
    res_create = client.post("/api/projects", json=create_payload)
    assert res_create.status_code == 201
    created = res_create.json()
    project_id = created["id"]
    assert created["name"] == "Aluminum Heat Spreader"
    assert created["model"]["metadata"]["name"] == "Aluminum Heat Spreader"
    assert created["validation"]["valid"] is True

    # 3. Get project by ID
    res_get = client.get(f"/api/projects/{project_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == project_id

    # 4. Update project
    updated_model = dict(sample_model_dict)
    updated_model["physics"] = {
        "type": "steady_state_heat_conduction",
        "volumetric_heat_source": 5000.0,
    }
    res_update = client.put(
        f"/api/projects/{project_id}",
        json={
            "name": "Aluminum Heat Spreader v2",
            "description": "Updated heat source",
            "model": updated_model,
        },
    )
    assert res_update.status_code == 200
    updated_data = res_update.json()
    assert updated_data["name"] == "Aluminum Heat Spreader v2"
    assert updated_data["model"]["physics"]["volumetric_heat_source"] == 5000.0

    # 5. Export project JSON
    res_export = client.get(f"/api/projects/{project_id}/export")
    assert res_export.status_code == 200
    exported = res_export.json()
    assert exported["export_format"] == "pde_simulation_studio_project"
    assert exported["schema_version"] == "1.0.0"
    assert exported["model"]["physics"]["volumetric_heat_source"] == 5000.0

    # 6. Import exported JSON as new project
    res_import = client.post("/api/projects/import", json=exported)
    assert res_import.status_code == 201
    imported = res_import.json()
    assert imported["id"] != project_id
    assert imported["model"]["physics"]["volumetric_heat_source"] == 5000.0

    # 7. Delete project
    res_del = client.delete(f"/api/projects/{project_id}")
    assert res_del.status_code == 200
    assert res_del.json()["deleted"] is True

    # 8. Verify 404 after deletion
    res_missing = client.get(f"/api/projects/{project_id}")
    assert res_missing.status_code == 404


def test_invalid_model_returns_422_with_structured_errors(
    client: TestClient, sample_model_dict: dict[str, Any]
) -> None:
    bad_model = dict(sample_model_dict)
    bad_model["geometry"] = {
        "type": "rectangular_cuboid",
        "dimensions": {"length_x": -1.0, "length_y": 1.0, "length_z": 1.0},
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "rotation_deg": {"x": 0.0, "y": 0.0, "z": 0.0},
    }
    res = client.post(
        "/api/projects",
        json={"name": "Invalid Project", "description": "", "model": bad_model},
    )
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert "errors" in detail
    assert len(detail["errors"]) >= 1
