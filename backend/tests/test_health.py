"""Tests for health check and CORS configuration (Phase 2)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_endpoint_returns_ok_and_phase2_solver_capabilities(
    client: TestClient,
) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["schema_version"] == "1.0.0"
    assert data["database"]["connected"] is True
    assert data["database"]["backend"] == "sqlite"
    assert data["capabilities"]["phase"] >= 2
    assert data["capabilities"]["pde_solver_execution"] is True
    assert data["capabilities"]["vtu_and_csv_export"] is True
    assert "NGSolve" in data["capabilities"]["solver_engine"]
    assert data["queue"]["engine"] == "Redis + RQ"


def test_root_health_alias(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_cors_headers_respect_configured_origins(client: TestClient) -> None:
    response = client.options(
        "/api/projects",
        headers={
            "Origin": "https://studio.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert (
        response.headers.get("access-control-allow-origin")
        == "https://studio.example.com"
    )
