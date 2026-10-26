"""SQLite implementation of the ProjectRepository interface with owner_id isolation."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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


class SQLiteProjectRepository(ProjectRepository):
    """SQLite-backed repository with automatic table creation, migration, and JSON serialization."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @property
    def backend_name(self) -> str:
        return "sqlite"

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL DEFAULT '{DEFAULT_DEV_USER_ID}',
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    schema_version TEXT NOT NULL,
                    model_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            # Upgrade existing Phase 1/2 SQLite databases missing owner_id
            cols = [
                row["name"]
                for row in conn.execute("PRAGMA table_info(projects)").fetchall()
            ]
            if "owner_id" not in cols:
                conn.execute(
                    f"ALTER TABLE projects ADD COLUMN owner_id TEXT NOT NULL DEFAULT '{DEFAULT_DEV_USER_ID}'"
                )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_projects_updated_at
                ON projects (updated_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_projects_owner_id
                ON projects (owner_id, updated_at DESC)
                """
            )
            conn.commit()

    def health_check(self) -> bool:
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT 1 AS ok").fetchone()
                return bool(row and row["ok"] == 1)
        except sqlite3.Error:
            return False

    def _row_to_record(self, row: sqlite3.Row) -> ProjectRecord:
        model_data = json.loads(row["model_json"])
        model = CanonicalSimulationModel.model_validate(model_data)
        owner = (
            row["owner_id"]
            if "owner_id" in row.keys() and row["owner_id"]
            else DEFAULT_DEV_USER_ID
        )
        return ProjectRecord(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            schema_version=row["schema_version"],
            model=model,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            owner_id=owner,
        )

    def list_projects(self, owner_id: Optional[str] = None) -> list[ProjectRecord]:
        with self._connect() as conn:
            if owner_id is not None:
                rows = conn.execute(
                    """
                    SELECT id, owner_id, name, description, schema_version, model_json, created_at, updated_at
                    FROM projects
                    WHERE owner_id = ?
                    ORDER BY updated_at DESC
                    """,
                    (owner_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, owner_id, name, description, schema_version, model_json, created_at, updated_at
                    FROM projects
                    ORDER BY updated_at DESC
                    """
                ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def count_projects(self, owner_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM projects WHERE owner_id = ?",
                (owner_id,),
            ).fetchone()
            return int(row["cnt"]) if row else 0

    def get_project(self, project_id: str) -> Optional[ProjectRecord]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, owner_id, name, description, schema_version, model_json, created_at, updated_at
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
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
            conn.execute(
                """
                INSERT INTO projects (id, owner_id, name, description, schema_version, model_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
            conn.execute(
                """
                UPDATE projects
                SET name = ?, description = ?, schema_version = ?, model_json = ?, updated_at = ?
                WHERE id = ?
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
            cursor = conn.execute(
                "DELETE FROM projects WHERE id = ?",
                (project_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
