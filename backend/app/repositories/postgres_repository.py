"""PostgreSQL implementation of ProjectRepository for production deployments."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.repositories.base import ProjectRecord, ProjectRepository
from app.schemas.model_schema import CanonicalSimulationModel
from app.security.auth import DEFAULT_DEV_USER_ID


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


class PostgresProjectRepository(ProjectRepository):
    """Production PostgreSQL-backed project repository using psycopg."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self.initialize()

    @property
    def backend_name(self) -> str:
        return "postgresql"

    def _connect(self) -> Any:
        import psycopg  # type: ignore[import-not-found]
        from psycopg.rows import dict_row  # type: ignore[import-not-found]

        return psycopg.connect(self._database_url, row_factory=dict_row)

    def initialize(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS projects (
                        id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL DEFAULT '{DEFAULT_DEV_USER_ID}',
                        name TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        schema_version TEXT NOT NULL,
                        model_json JSONB NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_pg_projects_owner_updated
                    ON projects (owner_id, updated_at DESC)
                    """
                )
            conn.commit()

    def health_check(self) -> bool:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 AS ok")
                    row = cur.fetchone()
                    return bool(row and row["ok"] == 1)
        except Exception:
            return False

    def _row_to_record(self, row: dict[str, Any]) -> ProjectRecord:
        raw_model = row["model_json"]
        model_data = (
            json.loads(raw_model) if isinstance(raw_model, str) else raw_model
        )
        model = CanonicalSimulationModel.model_validate(model_data)
        return ProjectRecord(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            schema_version=row["schema_version"],
            model=model,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            owner_id=row.get("owner_id") or DEFAULT_DEV_USER_ID,
        )

    def list_projects(self, owner_id: Optional[str] = None) -> list[ProjectRecord]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                if owner_id is not None:
                    cur.execute(
                        """
                        SELECT id, owner_id, name, description, schema_version, model_json, created_at, updated_at
                        FROM projects
                        WHERE owner_id = %s
                        ORDER BY updated_at DESC
                        """,
                        (owner_id,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, owner_id, name, description, schema_version, model_json, created_at, updated_at
                        FROM projects
                        ORDER BY updated_at DESC
                        """
                    )
                rows = cur.fetchall()
        return [self._row_to_record(r) for r in rows]

    def count_projects(self, owner_id: str) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM projects WHERE owner_id = %s",
                    (owner_id,),
                )
                row = cur.fetchone()
                return int(row["cnt"]) if row else 0

    def get_project(self, project_id: str) -> Optional[ProjectRecord]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, owner_id, name, description, schema_version, model_json, created_at, updated_at
                    FROM projects
                    WHERE id = %s
                    """,
                    (project_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def create_project(
        self,
        name: str,
        description: str,
        model: CanonicalSimulationModel,
        project_id: Optional[str] = None,
        owner_id: str = DEFAULT_DEV_USER_ID,
    ) -> ProjectRecord:
        pid = project_id or str(uuid.uuid4())
        now = _utc_now_iso()
        updated_metadata = model.metadata.model_copy(
            update={
                "name": name,
                "description": description,
                "created_at": model.metadata.created_at or now,
                "updated_at": now,
            }
        )
        synced_model = model.model_copy(update={"metadata": updated_metadata})
        model_json = synced_model.model_dump_json()

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO projects (id, owner_id, name, description, schema_version, model_json, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    """,
                    (
                        pid,
                        owner_id,
                        name,
                        description,
                        synced_model.schema_version,
                        model_json,
                        now,
                        now,
                    ),
                )
            conn.commit()

        return ProjectRecord(
            id=pid,
            name=name,
            description=description,
            schema_version=synced_model.schema_version,
            model=synced_model,
            created_at=now,
            updated_at=now,
            owner_id=owner_id,
        )

    def update_project(
        self,
        project_id: str,
        name: Optional[str],
        description: Optional[str],
        model: CanonicalSimulationModel,
    ) -> Optional[ProjectRecord]:
        existing = self.get_project(project_id)
        if existing is None:
            return None

        now = _utc_now_iso()
        resolved_name = name if name is not None else model.metadata.name
        resolved_desc = (
            description if description is not None else model.metadata.description
        )
        updated_metadata = model.metadata.model_copy(
            update={
                "name": resolved_name,
                "description": resolved_desc,
                "created_at": existing.created_at,
                "updated_at": now,
            }
        )
        synced_model = model.model_copy(update={"metadata": updated_metadata})
        model_json = synced_model.model_dump_json()

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE projects
                    SET name = %s, description = %s, schema_version = %s, model_json = %s::jsonb, updated_at = %s
                    WHERE id = %s
                    """,
                    (
                        resolved_name,
                        resolved_desc,
                        synced_model.schema_version,
                        model_json,
                        now,
                        project_id,
                    ),
                )
            conn.commit()

        return ProjectRecord(
            id=project_id,
            name=resolved_name,
            description=resolved_desc,
            schema_version=synced_model.schema_version,
            model=synced_model,
            created_at=existing.created_at,
            updated_at=now,
            owner_id=existing.owner_id,
        )

    def delete_project(self, project_id: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM projects WHERE id = %s", (project_id,))
                deleted = cur.rowcount > 0
            conn.commit()
            return deleted
