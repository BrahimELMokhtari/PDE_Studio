"""Unit tests for canonical model validation and scientific pre-checks."""

from __future__ import annotations

from typing import Any
import pytest
from pydantic import ValidationError

from app.schemas.model_schema import (
    CanonicalSimulationModel,
    validate_scientific_model,
)


def test_valid_canonical_model_parses_and_validates(
    sample_model_dict: dict[str, Any],
) -> None:
    model = CanonicalSimulationModel.model_validate(sample_model_dict)
    assert model.schema_version == "1.0.0"
    assert model.geometry.dimensions.length_x == 1.2
    assert model.boundary_conditions.X_MIN.type.value == "dirichlet"

    report = validate_scientific_model(model)
    assert report.valid is True
    assert report.metrics["total_elements"] == 12 * 8 * 5
    assert report.metrics["total_nodes"] == 13 * 9 * 6


def test_negative_or_zero_dimensions_rejected(
    sample_model_dict: dict[str, Any],
) -> None:
    sample_model_dict["geometry"]["dimensions"]["length_x"] = 0.0
    with pytest.raises(ValidationError):
        CanonicalSimulationModel.model_validate(sample_model_dict)

    sample_model_dict["geometry"]["dimensions"]["length_x"] = -2.5
    with pytest.raises(ValidationError):
        CanonicalSimulationModel.model_validate(sample_model_dict)


def test_non_positive_thermal_conductivity_rejected(
    sample_model_dict: dict[str, Any],
) -> None:
    sample_model_dict["material"]["thermal_conductivity"] = 0.0
    with pytest.raises(ValidationError):
        CanonicalSimulationModel.model_validate(sample_model_dict)


def test_dirichlet_requires_temperature_above_absolute_zero(
    sample_model_dict: dict[str, Any],
) -> None:
    sample_model_dict["boundary_conditions"]["X_MIN"]["temperature"] = None
    with pytest.raises(ValidationError):
        CanonicalSimulationModel.model_validate(sample_model_dict)

    sample_model_dict["boundary_conditions"]["X_MIN"]["temperature"] = -5.0  # < 0 K
    with pytest.raises(ValidationError):
        CanonicalSimulationModel.model_validate(sample_model_dict)


def test_robin_requires_positive_convection_coeff_and_ambient_temp(
    sample_model_dict: dict[str, Any],
) -> None:
    sample_model_dict["boundary_conditions"]["X_MAX"]["convection_coefficient"] = -10.0
    with pytest.raises(ValidationError):
        CanonicalSimulationModel.model_validate(sample_model_dict)


def test_mismatched_semantic_face_key_and_id_rejected(
    sample_model_dict: dict[str, Any],
) -> None:
    sample_model_dict["boundary_conditions"]["Z_MAX"]["face_id"] = "Z_MIN"
    with pytest.raises(ValidationError):
        CanonicalSimulationModel.model_validate(sample_model_dict)


def test_all_insulated_triggers_non_unique_steady_state_warning(
    sample_model_dict: dict[str, Any],
) -> None:
    for face_id in ("X_MIN", "X_MAX", "Y_MIN", "Y_MAX", "Z_MIN", "Z_MAX"):
        sample_model_dict["boundary_conditions"][face_id] = {
            "face_id": face_id,
            "type": "insulated",
            "temperature": None,
            "heat_flux": None,
            "convection_coefficient": None,
            "ambient_temperature": None,
        }
    model = CanonicalSimulationModel.model_validate(sample_model_dict)
    report = validate_scientific_model(model)
    assert report.valid is True
    assert any(
        issue.field == "boundary_conditions" and issue.severity == "warning"
        for issue in report.issues
    )
