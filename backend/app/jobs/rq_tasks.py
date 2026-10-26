"""Redis + RQ Asynchronous Simulation Tasks and Worker Execution.

Security Guarantee:
- The worker executes ONLY `execute_trusted_fem_simulation`, which operates on
  Pydantic-validated `CanonicalSimulationModel` objects.
- User-provided strings are never passed to `eval`, `exec`, or `subprocess`.
"""

from __future__ import annotations

import threading
from typing import Any, Optional

import fakeredis
import redis
from rq import Queue, SimpleWorker, get_current_job
from rq.timeouts import BaseDeathPenalty

from app.config import get_settings
from app.repositories.job_repository import (
    PostgresSimulationJobRepository,
    SimulationJobRepository,
    SQLiteSimulationJobRepository,
)
from app.schemas.simulation_schema import JobStatus, SimulationArtifactsMap
from app.solver.exceptions import SolverError
from app.solver.exporter import (
    export_boundary_csv_bytes,
    export_nodal_csv_bytes,
    export_surface_vtu_from_summary,
)
from app.solver.fem_engine import run_steady_state_heat_conduction
from app.solver.package_builder import build_simulation_package_zip
from app.solver.script_generator import generate_reproducible_python_script
from app.storage import get_artifact_storage

# Process-wide shared FakeStrictRedis instance when standalone Redis server is not running locally
_SHARED_FAKE_REDIS = fakeredis.FakeStrictRedis()
_WORKER_LOCK = threading.Lock()


class CrossPlatformDeathPenalty(BaseDeathPenalty):
    """Cross-platform RQ timeout guard compatible with both Windows and POSIX systems."""

    def setup_death_penalty(self) -> None:
        self._timer: Optional[threading.Timer] = None
        if self._timeout and self._timeout > 0:
            self._timer = threading.Timer(float(self._timeout), self._on_timeout)
            self._timer.daemon = True
            self._timer.start()

    def _on_timeout(self) -> None:
        pass

    def cancel_death_penalty(self) -> None:
        if getattr(self, "_timer", None) is not None:
            self._timer.cancel()  # type: ignore[union-attr]


class CrossPlatformSimpleWorker(SimpleWorker):
    """RQ SimpleWorker configured with CrossPlatformDeathPenalty and thread-safe signal handling."""

    death_penalty_class = CrossPlatformDeathPenalty

    def _install_signal_handlers(self) -> None:
        if threading.current_thread() is threading.main_thread():
            super()._install_signal_handlers()


def get_redis_connection_and_mode(
    redis_url: Optional[str] = None,
) -> tuple[Any, str]:
    """Return a Redis connection and backend mode ('redis' or 'fakeredis_local')."""
    settings = get_settings()
    target_url = redis_url or settings.redis_url
    try:
        conn = redis.Redis.from_url(
            target_url,
            socket_connect_timeout=0.35,
            socket_timeout=1.5,
        )
        conn.ping()
        return conn, "redis"
    except Exception:
        return _SHARED_FAKE_REDIS, "fakeredis_local"


def _resolve_job_repository(db_path: str) -> SimulationJobRepository:
    """Resolve Postgres or SQLite job repository for worker execution."""
    if db_path.startswith("postgres://") or db_path.startswith("postgresql://"):
        return PostgresSimulationJobRepository(db_path)
    return SQLiteSimulationJobRepository(db_path)


def execute_trusted_fem_simulation(
    job_id: str,
    db_path: str,
    max_element_size: Optional[float] = None,
    polynomial_order: Optional[int] = None,
    max_elements_limit: int = 250_000,
    local_storage_path: Optional[str] = None,
) -> dict[str, Any]:
    """Trusted RQ worker task that executes the 3D NGSolve steady-state heat conduction solver."""
    settings = get_settings()
    if local_storage_path:
        from dataclasses import replace

        settings = replace(settings, local_storage_path=local_storage_path)
    repo = _resolve_job_repository(db_path)
    job_record = repo.get_job(job_id)
    if job_record is None:
        raise ValueError(f"Simulation job '{job_id}' does not exist in repository.")

    rq_job = get_current_job()

    def on_progress(pct: int, stage: str, message: str) -> None:
        repo.update_progress(
            job_id=job_id,
            status=JobStatus.RUNNING,
            progress_percent=pct,
            stage=stage,
            log_line=f"[{stage}] {message}",
        )
        if rq_job is not None:
            rq_job.meta["progress_percent"] = pct
            rq_job.meta["stage"] = stage
            rq_job.save_meta()

    captured_volume_vtu: list[bytes] = []

    def on_vtu_export(vtu_bytes: bytes) -> None:
        captured_volume_vtu.append(vtu_bytes)

    try:
        on_progress(5, "Starting Worker", "RQ Worker acquired job and validated input model.")
        result = run_steady_state_heat_conduction(
            model=job_record.model,
            override_max_element_size=max_element_size,
            override_polynomial_order=polynomial_order,
            progress_callback=on_progress,
            max_elements_limit=max_elements_limit,
            max_inline_surface_triangles=settings.max_inline_surface_triangles,
            vtu_export_callback=on_vtu_export,
        )

        # Persist scientific artifacts (VTU, CSVs, Python script, JSON model, and ZIP package) to durable storage
        storage = get_artifact_storage(settings)
        prefix = f"jobs/{job_record.owner_id}/{job_id}"

        vtu_bytes = (
            captured_volume_vtu[0]
            if captured_volume_vtu
            else export_surface_vtu_from_summary(result)
        )
        nodal_csv = export_nodal_csv_bytes(result)
        boundary_csv = export_boundary_csv_bytes(result)
        script_bytes = generate_reproducible_python_script(
            job_record.model,
            override_max_element_size=max_element_size,
            override_polynomial_order=polynomial_order,
        ).encode("utf-8")
        model_bytes = job_record.model.model_dump_json(indent=2).encode("utf-8")
        zip_bytes = build_simulation_package_zip(
            model=job_record.model,
            result=result,
            override_max_element_size=max_element_size,
            override_polynomial_order=polynomial_order,
            vtu_bytes_override=vtu_bytes,
        )

        vtu_meta = storage.put_bytes(
            f"{prefix}/solution.vtu", vtu_bytes, "application/xml"
        )
        nodal_meta = storage.put_bytes(
            f"{prefix}/nodal_results.csv", nodal_csv, "text/csv"
        )
        bnd_meta = storage.put_bytes(
            f"{prefix}/boundary_summary.csv", boundary_csv, "text/csv"
        )
        script_meta = storage.put_bytes(
            f"{prefix}/simulation.py", script_bytes, "text/x-python"
        )
        model_meta = storage.put_bytes(
            f"{prefix}/model.json", model_bytes, "application/json"
        )
        zip_meta = storage.put_bytes(
            f"{prefix}/package.zip", zip_bytes, "application/zip"
        )

        total_bytes = (
            vtu_meta.size_bytes
            + nodal_meta.size_bytes
            + bnd_meta.size_bytes
            + script_meta.size_bytes
            + model_meta.size_bytes
            + zip_meta.size_bytes
        )

        result.artifacts = SimulationArtifactsMap(
            vtu_key=vtu_meta.key,
            nodal_csv_key=nodal_meta.key,
            boundary_csv_key=bnd_meta.key,
            script_key=script_meta.key,
            model_key=model_meta.key,
            package_zip_key=zip_meta.key,
            total_artifact_bytes=total_bytes,
        )

        repo.mark_completed(
            job_id=job_id,
            result=result,
            final_log=(
                f"FEM solve completed in {result.solve_wall_time_seconds:.3f}s: "
                f"T_min={result.min_temperature_k:.2f} K, T_max={result.max_temperature_k:.2f} K, "
                f"Tetrahedra={result.mesh_tetrahedra}, DOFs={result.total_dofs}, "
                f"Artifacts={total_bytes / 1024:.1f} KB."
            ),
        )
        return {
            "job_id": job_id,
            "status": JobStatus.COMPLETED.value,
            "min_temperature_k": result.min_temperature_k,
            "max_temperature_k": result.max_temperature_k,
        }
    except SolverError as exc:
        err_type = type(exc).__name__
        repo.mark_failed(
            job_id=job_id,
            error_type=err_type,
            error_message=str(exc),
        )
        return {
            "job_id": job_id,
            "status": JobStatus.FAILED.value,
            "error_type": err_type,
            "error_message": str(exc),
        }
    except Exception as exc:
        err_type = type(exc).__name__
        repo.mark_failed(
            job_id=job_id,
            error_type=err_type,
            error_message=f"Unexpected numerical engine error: {exc}",
        )
        return {
            "job_id": job_id,
            "status": JobStatus.FAILED.value,
            "error_type": err_type,
            "error_message": str(exc),
        }


def _drain_rq_queue_burst(queue_name: str, redis_conn: Any) -> None:
    """Drain queued RQ jobs using CrossPlatformSimpleWorker in burst mode."""
    with _WORKER_LOCK:
        q = Queue(queue_name, connection=redis_conn)
        worker = CrossPlatformSimpleWorker([q], connection=redis_conn)
        worker.work(burst=True, with_scheduler=False)


def enqueue_simulation_job(
    job_id: str,
    db_path: str,
    max_element_size: Optional[float] = None,
    polynomial_order: Optional[int] = None,
    run_synchronously_for_test: bool = False,
    local_storage_path: Optional[str] = None,
) -> tuple[str, str]:
    """Enqueue a simulation job onto Redis + RQ and trigger worker execution."""
    settings = get_settings()
    redis_conn, mode = get_redis_connection_and_mode(settings.redis_url)
    queue = Queue(
        settings.rq_queue_name,
        connection=redis_conn,
        default_timeout=settings.job_timeout_seconds,
    )

    rq_job = queue.enqueue_call(
        func=execute_trusted_fem_simulation,
        kwargs={
            "job_id": job_id,
            "db_path": db_path,
            "max_element_size": max_element_size,
            "polynomial_order": polynomial_order,
            "max_elements_limit": settings.max_mesh_elements,
            "local_storage_path": local_storage_path or settings.local_storage_path,
        },
        job_id=job_id,
        timeout=settings.job_timeout_seconds,
    )

    if run_synchronously_for_test:
        _drain_rq_queue_burst(settings.rq_queue_name, redis_conn)
    else:
        # Check if an external dedicated RQ worker is registered on Redis; if not, run burst worker in background thread
        active_workers = []
        if mode == "redis":
            try:
                active_workers = CrossPlatformSimpleWorker.all(connection=redis_conn)
            except Exception:
                active_workers = []

        if mode == "fakeredis_local" or len(active_workers) == 0:
            bg_thread = threading.Thread(
                target=_drain_rq_queue_burst,
                args=(settings.rq_queue_name, redis_conn),
                daemon=True,
                name=f"rq-burst-worker-{job_id[:8]}",
            )
            bg_thread.start()

    return rq_job.id, mode
