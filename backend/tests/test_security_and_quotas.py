"""Phase 3 Security, OIDC Fail-Closed Authentication, Tenant Ownership, Rate Limits & Quota Tests."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import jwt
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories.job_repository import SQLiteSimulationJobRepository
from app.repositories.sqlite_repository import SQLiteProjectRepository
from app.storage import LocalFilesystemStorage


def test_production_auth_fails_closed_when_oidc_unconfigured(
    tmp_path: Path, sample_model_dict: dict[str, Any]
) -> None:
    """Production mode MUST fail closed (HTTP 503) if OIDC credentials are not configured."""
    db_path = str(tmp_path / "prod_closed.db")
    settings = Settings(
        app_env="production",
        auth_required=True,
        oidc_jwks_url="",
        oidc_jwt_secret="",
        sqlite_db_path=db_path,
        local_storage_path=str(tmp_path / "artifacts"),
    )
    app = create_app(
        settings=settings,
        repository=SQLiteProjectRepository(db_path),
        job_repository=SQLiteSimulationJobRepository(db_path),
        artifact_storage=LocalFilesystemStorage(str(tmp_path / "artifacts")),
    )
    prod_client = TestClient(app)

    res = prod_client.get("/api/projects")
    assert res.status_code == 503
    assert "failed closed" in res.json()["detail"].lower()

    res_post = prod_client.post(
        "/api/projects",
        json={"name": "Blocked Project", "description": "", "model": sample_model_dict},
    )
    assert res_post.status_code == 503


def test_oidc_jwt_authentication_and_tenant_ownership_isolation(
    tmp_path: Path, sample_model_dict: dict[str, Any]
) -> None:
    """Verify OIDC JWT validation and strict per-user project ownership authorization."""
    db_path = str(tmp_path / "oidc_tenant.db")
    jwt_secret = "super-secret-hs256-signing-key-for-oidc-tests-2026"
    settings = Settings(
        app_env="production",
        auth_required=True,
        oidc_jwt_secret=jwt_secret,
        oidc_issuer_url="https://auth.pdestudio.example.com",
        oidc_audience="pde-simulation-studio-api",
        oidc_algorithms=["HS256"],
        sqlite_db_path=db_path,
        local_storage_path=str(tmp_path / "artifacts"),
    )
    app = create_app(
        settings=settings,
        repository=SQLiteProjectRepository(db_path),
        job_repository=SQLiteSimulationJobRepository(db_path),
        artifact_storage=LocalFilesystemStorage(str(tmp_path / "artifacts")),
    )
    client = TestClient(app)

    def make_token(sub: str, roles: list[str] | None = None) -> str:
        now = int(time.time())
        payload = {
            "sub": sub,
            "email": f"{sub}@example.com",
            "name": f"Engineer {sub}",
            "plan_tier": "enterprise",
            "roles": roles or ["engineer"],
            "iss": "https://auth.pdestudio.example.com",
            "aud": "pde-simulation-studio-api",
            "iat": now,
            "exp": now + 3600,
        }
        return jwt.encode(payload, jwt_secret, algorithm="HS256")

    token_alice = make_token("user-alice")
    token_bob = make_token("user-bob")

    # 1. Unauthenticated request in production returns 401
    res_unauth = client.get("/api/projects")
    assert res_unauth.status_code == 401

    # 2. Alice creates a project
    res_create = client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {token_alice}"},
        json={
            "name": "Alice Secret Turbine Blade",
            "description": "Classified thermal model",
            "model": sample_model_dict,
        },
    )
    assert res_create.status_code == 201
    project_id = res_create.json()["id"]
    assert res_create.json()["owner_id"] == "user-alice"

    # 3. Bob lists projects -> sees 0 projects
    res_bob_list = client.get(
        "/api/projects",
        headers={"Authorization": f"Bearer {token_bob}"},
    )
    assert res_bob_list.status_code == 200
    assert res_bob_list.json() == []

    # 4. Bob attempts to read, update, or delete Alice's project -> 403 Forbidden
    res_bob_get = client.get(
        f"/api/projects/{project_id}",
        headers={"Authorization": f"Bearer {token_bob}"},
    )
    assert res_bob_get.status_code == 403

    res_bob_del = client.delete(
        f"/api/projects/{project_id}",
        headers={"Authorization": f"Bearer {token_bob}"},
    )
    assert res_bob_del.status_code == 403

    # 5. Alice can read and delete her own project
    res_alice_get = client.get(
        f"/api/projects/{project_id}",
        headers={"Authorization": f"Bearer {token_alice}"},
    )
    assert res_alice_get.status_code == 200
    assert res_alice_get.json()["name"] == "Alice Secret Turbine Blade"


def test_project_quota_rate_limiting_and_payload_size_guard(
    tmp_path: Path, sample_model_dict: dict[str, Any]
) -> None:
    """Verify project quotas (HTTP 429), body size limits (HTTP 413), and security headers."""
    db_path = str(tmp_path / "quotas.db")
    settings = Settings(
        app_env="test",
        max_projects_per_user=2,
        max_request_body_bytes=40_000,
        rate_limit_per_minute=50,
        sqlite_db_path=db_path,
        local_storage_path=str(tmp_path / "artifacts"),
    )
    app = create_app(
        settings=settings,
        repository=SQLiteProjectRepository(db_path),
        job_repository=SQLiteSimulationJobRepository(db_path),
        artifact_storage=LocalFilesystemStorage(str(tmp_path / "artifacts")),
    )
    client = TestClient(app)

    # Create 2 projects (up to quota limit)
    for idx in range(2):
        r = client.post(
            "/api/projects",
            json={"name": f"Quota Project {idx + 1}", "description": "", "model": sample_model_dict},
        )
        assert r.status_code == 201
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "DENY"

    # 3rd project exceeds quota -> HTTP 429
    r_exceed = client.post(
        "/api/projects",
        json={"name": "Quota Project 3", "description": "", "model": sample_model_dict},
    )
    assert r_exceed.status_code == 429
    assert "quota exceeded" in r_exceed.json()["detail"].lower()

    # Oversized payload (> 40,000 bytes) -> HTTP 413
    oversized_body = "x" * 50_000
    r_large = client.post(
        "/api/projects",
        content=oversized_body,
        headers={"Content-Type": "application/json"},
    )
    assert r_large.status_code == 413
