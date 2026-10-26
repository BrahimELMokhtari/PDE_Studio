"""Repository abstraction, SQLite, and PostgreSQL implementations for simulation jobs."""

from __future__ import annotations

import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.schemas.model_schema import CanonicalSimulationModel
from app.schemas.simulation_schema import (
    JobStatus,
    SimulationJobResponse,
    SimulationResultSummary,
)
from app.security.auth import DEFAULT_DEV_USER_ID


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


class SimulationJobRepository(ABC):
    """Database-agnostic repository interface for simulation job tracking and ownership."""

    @property
    def backend_name(self) -> str:
        return "sqlite"

    @abstractmethod
    def initialize(self) -> None:
        """Initialize underlying storage schema."""

    @abstractmethod
    def create_job(
        self,
        model: CanonicalSimulationModel,
        project_id: Optional[str] = None,
        job_id: Optional[str] = None,
        owner_id: str = DEFAULT_DEV_USER_ID,
    ) -> SimulationJobResponse:
        """Create a new simulation job in QUEUED state."""

    @abstractmethod
    def set_rq_job_id(self, job_id: str, rq_job_id: str) -> None:
        """Associate the Redis Queue (RQ) job identifier."""

    @abstractmethod
    def update_progress(
        self,
        job_id: str,
        status: JobStatus,
        progress_percent: int,
        stage: str,
        log_line: Optional[str] = None,
    ) -> None:
        """Update job status, progress percentage, current stage, and append a log entry."""

    @abstractmethod
    def mark_completed(
        self,
        job_id: str,
        result: SimulationResultSummary,
        final_log: Optional[str] = None,
    ) -> Optional[SimulationJobResponse]:
        """Transition job to COMPLETED and persist the numerical FEM result."""

    @abstractmethod
    def mark_failed(
        self,
        job_id: str,
        error_type: str,
        error_message: str,
    ) -> Optional[SimulationJobResponse]:
        """Transition job to FAILED and record structured error details."""

    @abstractmethod
    def get_job(self, job_id: str) -> Optional[SimulationJobResponse]:
        """Fetch a simulation job by ID."""

    @abstractmethod
    def list_jobs(
        self,
        limit: int = 30,
        owner_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> list[SimulationJobResponse]:
        """List recent simulation jobs ordered by creation time descending."""

    @abstractmethod
    def count_jobs(self, owner_id: str) -> int:
        """Count total jobs belonging to owner_id."""

    @abstractmethod
    def delete_job(self, job_id: str) -> bool:
        """Delete a simulation job record by ID."""


class SQLiteSimulationJobRepository(SimulationJobRepository):
    """SQLite-backed repository for simulation job lifecycles and FEM results."""

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
                CREATE TABLE IF NOT EXISTS simulation_jobs (
                    job_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL DEFAULT '{DEFAULT_DEV_USER_ID}',
                    rq_job_id TEXT,
                    project_id TEXT,
                    project_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress_percent INTEGER NOT NULL DEFAULT 0,
                    current_stage TEXT NOT NULL DEFAULT 'Queued',
                    logs_json TEXT NOT NULL DEFAULT '[]',
                    error_type TEXT,
                    error_message TEXT,
                    model_json TEXT NOT NULL,
                    result_json TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                )
                """
            )
            cols = [
                row["name"]
                for row in conn.execute("PRAGMA table_info(simulation_jobs)").fetchall()
            ]
            if "owner_id" not in cols:
                conn.execute(
                    f"ALTER TABLE simulation_jobs ADD COLUMN owner_id TEXT NOT NULL DEFAULT '{DEFAULT_DEV_USER_ID}'"
                )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_simulation_jobs_created_at
                ON simulation_jobs (created_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_simulation_jobs_owner
                ON simulation_jobs (owner_id, created_at DESC)
                """
            )
            conn.commit()

    def _row_to_response(self, row: sqlite3.Row) -> SimulationJobResponse:
        model = CanonicalSimulationModel.model_validate(json.loads(row["model_json"]))
        logs = json.loads(row["logs_json"]) if row["logs_json"] else []
        result = (
            SimulationResultSummary.model_validate(json.loads(row["result_json"]))
            if row["result_json"]
            else None
        )
        owner = (
            row["owner_id"]
            if "owner_id" in row.keys() and row["owner_id"]
            else DEFAULT_DEV_USER_ID
        )
        return SimulationJobResponse(
            job_id=row["job_id"],
            owner_id=owner,
            rq_job_id=row["rq_job_id"],
            project_id=row["project_id"],
            project_name=row["project_name"],
            status=JobStatus(row["status"]),
            progress_percent=int(row["progress_percent"]),
            current_stage=row["current_stage"],
            logs=logs,
            error_type=row["error_type"],
            error_message=row["error_message"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            model=model,
            result=result,
        )

    def create_job(
        self,
        model: CanonicalSimulationModel,
        project_id: Optional[str] = None,
        job_id: Optional[str] = None,
        owner_id: str = DEFAULT_DEV_USER_ID,
    ) -> SimulationJobResponse:
        jid = job_id or str(uuid.uuid4())
        now = _utc_now_iso()
        initial_logs = [f"[{now}] Job {jid[:8]} queued for 3D NGSolve FEM execution."]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO simulation_jobs (
                    job_id, owner_id, rq_job_id, project_id, project_name, status,
                    progress_percent, current_stage, logs_json, model_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    jid,
                    owner_id,
                    jid,
                    project_id,
                    model.metadata.name,
                    JobStatus.QUEUED.value,
                    0,
                    "Queued",
                    json.dumps(initial_logs),
                    model.model_dump_json(),
                    now,
                ),
            )
            conn.commit()
        fetched = self.get_job(jid)
        assert fetched is not None
        return fetched

    def set_rq_job_id(self, job_id: str, rq_job_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE simulation_jobs SET rq_job_id = ? WHERE job_id = ?",
                (rq_job_id, job_id),
            )
            conn.commit()

    def update_progress(
        self,
        job_id: str,
        status: JobStatus,
        progress_percent: int,
        stage: str,
        log_line: Optional[str] = None,
    ) -> None:
        now = _utc_now_iso()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT logs_json, started_at FROM simulation_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                return
            logs: list[str] = json.loads(row["logs_json"]) if row["logs_json"] else []
            if log_line:
                logs.append(f"[{now}] {log_line}")
            started_at = row["started_at"] or (
                now if status == JobStatus.RUNNING else None
            )
            conn.execute(
                """
                UPDATE simulation_jobs
                SET status = ?, progress_percent = ?, current_stage = ?, logs_json = ?, started_at = ?
                WHERE job_id = ?
                """,
                (
                    status.value,
                    max(0, min(100, int(progress_percent))),
                    stage,
                    json.dumps(logs),
                    started_at,
                    job_id,
                ),
            )
            conn.commit()

    def mark_completed(
        self,
        job_id: str,
        result: SimulationResultSummary,
        final_log: Optional[str] = None,
    ) -> Optional[SimulationJobResponse]:
        now = _utc_now_iso()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT logs_json, started_at FROM simulation_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                return None
            logs: list[str] = json.loads(row["logs_json"]) if row["logs_json"] else []
            if final_log:
                logs.append(f"[{now}] {final_log}")
            started_at = row["started_at"] or now
            conn.execute(
                """
                UPDATE simulation_jobs
                SET status = ?, progress_percent = 100, current_stage = 'Completed',
                    logs_json = ?, result_json = ?, started_at = ?, completed_at = ?,
                    error_type = NULL, error_message = NULL
                WHERE job_id = ?
                """,
                (
                    JobStatus.COMPLETED.value,
                    json.dumps(logs),
                    result.model_dump_json(),
                    started_at,
                    now,
                    job_id,
                ),
            )
            conn.commit()
        return self.get_job(job_id)

    def mark_failed(
        self,
        job_id: str,
        error_type: str,
        error_message: str,
    ) -> Optional[SimulationJobResponse]:
        now = _utc_now_iso()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT logs_json, started_at FROM simulation_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                return None
            logs: list[str] = json.loads(row["logs_json"]) if row["logs_json"] else []
            logs.append(f"[{now}] ERROR ({error_type}): {error_message}")
            started_at = row["started_at"] or now
            conn.execute(
                """
                UPDATE simulation_jobs
                SET status = ?, current_stage = 'Failed', logs_json = ?,
                    error_type = ?, error_message = ?, started_at = ?, completed_at = ?
                WHERE job_id = ?
                """,
                (
                    JobStatus.FAILED.value,
                    json.dumps(logs),
                    error_type,
                    error_message,
                    started_at,
                    now,
                    job_id,
                ),
            )
            conn.commit()
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> Optional[SimulationJobResponse]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM simulation_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_response(row)

    def list_jobs(
        self,
        limit: int = 30,
        owner_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> list[SimulationJobResponse]:
        with self._connect() as conn:
            if owner_id is not None and project_id is not None:
                rows = conn.execute(
                    "SELECT * FROM simulation_jobs WHERE owner_id = ? AND project_id = ? ORDER BY created_at DESC LIMIT ?",
                    (owner_id, project_id, limit),
                ).fetchall()
            elif owner_id is not None:
                rows = conn.execute(
                    "SELECT * FROM simulation_jobs WHERE owner_id = ? ORDER BY created_at DESC LIMIT ?",
                    (owner_id, limit),
                ).fetchall()
            elif project_id is not None:
                rows = conn.execute(
                    "SELECT * FROM simulation_jobs WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                    (project_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM simulation_jobs ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [self._row_to_response(r) for r in rows]

    def count_jobs(self, owner_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM simulation_jobs WHERE owner_id = ?",
                (owner_id,),
            ).fetchone()
            return int(row["cnt"]) if row else 0

    def delete_job(self, job_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM simulation_jobs WHERE job_id = ?",
                (job_id,),
            )
            conn.commit()
            return cur.rowcount > 0


class PostgresSimulationJobRepository(SimulationJobRepository):
    """Production PostgreSQL-backed simulation job repository."""

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
                    CREATE TABLE IF NOT EXISTS simulation_jobs (
                        job_id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL DEFAULT '{DEFAULT_DEV_USER_ID}',
                        rq_job_id TEXT,
                        project_id TEXT,
                        project_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        progress_percent INTEGER NOT NULL DEFAULT 0,
                        current_stage TEXT NOT NULL DEFAULT 'Queued',
                        logs_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                        error_type TEXT,
                        error_message TEXT,
                        model_json JSONB NOT NULL,
                        result_json JSONB,
                        created_at TEXT NOT NULL,
                        started_at TEXT,
                        completed_at TEXT
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_pg_sim_jobs_owner_created
                    ON simulation_jobs (owner_id, created_at DESC)
                    """
                )
            conn.commit()

    def _row_to_response(self, row: dict[str, Any]) -> SimulationJobResponse:
        raw_model = row["model_json"]
        model = CanonicalSimulationModel.model_validate(
            json.loads(raw_model) if isinstance(raw_model, str) else raw_model
        )
        raw_logs = row["logs_json"]
        logs = (
            json.loads(raw_logs)
            if isinstance(raw_logs, str)
            else (raw_logs or [])
        )
        raw_res = row["result_json"]
        result = None
        if raw_res is not None:
            result = SimulationResultSummary.model_validate(
                json.loads(raw_res) if isinstance(raw_res, str) else raw_res
            )
        return SimulationJobResponse(
            job_id=row["job_id"],
            owner_id=row.get("owner_id") or DEFAULT_DEV_USER_ID,
            rq_job_id=row["rq_job_id"],
            project_id=row["project_id"],
            project_name=row["project_name"],
            status=JobStatus(row["status"]),
            progress_percent=int(row["progress_percent"]),
            current_stage=row["current_stage"],
            logs=logs,
            error_type=row["error_type"],
            error_message=row["error_message"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            model=model,
            result=result,
        )

    def create_job(
        self,
        model: CanonicalSimulationModel,
        project_id: Optional[str] = None,
        job_id: Optional[str] = None,
        owner_id: str = DEFAULT_DEV_USER_ID,
    ) -> SimulationJobResponse:
        jid = job_id or str(uuid.uuid4())
        now = _utc_now_iso()
        initial_logs = [f"[{now}] Job {jid[:8]} queued for 3D NGSolve FEM execution."]
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO simulation_jobs (
                        job_id, owner_id, rq_job_id, project_id, project_name, status,
                        progress_percent, current_stage, logs_json, model_json, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                    """,
                    (
                        jid,
                        owner_id,
                        jid,
                        project_id,
                        model.metadata.name,
                        JobStatus.QUEUED.value,
                        0,
                        "Queued",
                        json.dumps(initial_logs),
                        model.model_dump_json(),
                        now,
                    ),
                )
            conn.commit()
        fetched = self.get_job(jid)
        assert fetched is not None
        return fetched

    def set_rq_job_id(self, job_id: str, rq_job_id: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE simulation_jobs SET rq_job_id = %s WHERE job_id = %s",
                    (rq_job_id, job_id),
                )
            conn.commit()

    def update_progress(
        self,
        job_id: str,
        status: JobStatus,
        progress_percent: int,
        stage: str,
        log_line: Optional[str] = None,
    ) -> None:
        job = self.get_job(job_id)
        if job is None:
            return
        now = _utc_now_iso()
        logs = list(job.logs)
        if log_line:
            logs.append(f"[{now}] {log_line}")
        started_at = job.started_at or (now if status == JobStatus.RUNNING else None)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE simulation_jobs
                    SET status = %s, progress_percent = %s, current_stage = %s, logs_json = %s::jsonb, started_at = %s
                    WHERE job_id = %s
                    """,
                    (
                        status.value,
                        max(0, min(100, int(progress_percent))),
                        stage,
                        json.dumps(logs),
                        started_at,
                        job_id,
                    ),
                )
            conn.commit()

    def mark_completed(
        self,
        job_id: str,
        result: SimulationResultSummary,
        final_log: Optional[str] = None,
    ) -> Optional[SimulationJobResponse]:
        job = self.get_job(job_id)
        if job is None:
            return None
        now = _utc_now_iso()
        logs = list(job.logs)
        if final_log:
            logs.append(f"[{now}] {final_log}")
        started_at = job.started_at or now
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE simulation_jobs
                    SET status = %s, progress_percent = 100, current_stage = 'Completed',
                        logs_json = %s::jsonb, result_json = %s::jsonb, started_at = %s, completed_at = %s,
                        error_type = NULL, error_message = NULL
                    WHERE job_id = %s
                    """,
                    (
                        JobStatus.COMPLETED.value,
                        json.dumps(logs),
                        result.model_dump_json(),
                        started_at,
                        now,
                        job_id,
                    ),
                )
            conn.commit()
        return self.get_job(job_id)

    def mark_failed(
        self,
        job_id: str,
        error_type: str,
        error_message: str,
    ) -> Optional[SimulationJobResponse]:
        job = self.get_job(job_id)
        if job is None:
            return None
        now = _utc_now_iso()
        logs = list(job.logs)
        logs.append(f"[{now}] ERROR ({error_type}): {error_message}")
        started_at = job.started_at or now
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE simulation_jobs
                    SET status = %s, current_stage = 'Failed', logs_json = %s::jsonb,
                        error_type = %s, error_message = %s, started_at = %s, completed_at = %s
                    WHERE job_id = %s
                    """,
                    (
                        JobStatus.FAILED.value,
                        json.dumps(logs),
                        error_type,
                        error_message,
                        started_at,
                        now,
                        job_id,
                    ),
                )
            conn.commit()
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> Optional[SimulationJobResponse]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM simulation_jobs WHERE job_id = %s",
                    (job_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_response(row)

    def list_jobs(
        self,
        limit: int = 30,
        owner_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> list[SimulationJobResponse]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                if owner_id is not None and project_id is not None:
                    cur.execute(
                        "SELECT * FROM simulation_jobs WHERE owner_id = %s AND project_id = %s ORDER BY created_at DESC LIMIT %s",
                        (owner_id, project_id, limit),
                    )
                elif owner_id is not None:
                    cur.execute(
                        "SELECT * FROM simulation_jobs WHERE owner_id = %s ORDER BY created_at DESC LIMIT %s",
                        (owner_id, limit),
                    )
                elif project_id is not None:
                    cur.execute(
                        "SELECT * FROM simulation_jobs WHERE project_id = %s ORDER BY created_at DESC LIMIT %s",
                        (project_id, limit),
                    )
                else:
                    cur.execute(
                        "SELECT * FROM simulation_jobs ORDER BY created_at DESC LIMIT %s",
                        (limit,),
                    )
                rows = cur.fetchall()
        return [self._row_to_response(r) for r in rows]

    def count_jobs(self, owner_id: str) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM simulation_jobs WHERE owner_id = %s",
                    (owner_id,),
                )
                row = cur.fetchone()
                return int(row["cnt"]) if row else 0

    def delete_job(self, job_id: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM simulation_jobs WHERE job_id = %s",
                    (job_id,),
                )
                deleted = cur.rowcount > 0
            conn.commit()
            return deleted
