"""Unit tests for the SQLiteProjectRepository implementation."""

from __future__ import annotations

from typing import Any
from app.repositories.sqlite_repository import SQLiteProjectRepository
from app.schemas.model_schema import CanonicalSimulationModel


def test_sqlite_repository_persistence_and_ordering(
    sqlite_repo: SQLiteProjectRepository, sample_model_dict: dict[str, Any]
) -> None:
    assert sqlite_repo.health_check() is True

    model = CanonicalSimulationModel.model_validate(sample_model_dict)
    rec1 = sqlite_repo.create_project("Model A", "First model", model)
    rec2 = sqlite_repo.create_project("Model B", "Second model", model)

    all_projects = sqlite_repo.list_projects()
    assert len(all_projects) == 2
    assert {r.id for r in all_projects} == {rec1.id, rec2.id}

    fetched = sqlite_repo.get_project(rec1.id)
    assert fetched is not None
    assert fetched.name == "Model A"
    assert fetched.model.metadata.name == "Model A"

    assert sqlite_repo.delete_project(rec1.id) is True
    assert sqlite_repo.get_project(rec1.id) is None
    assert sqlite_repo.delete_project(rec1.id) is False
