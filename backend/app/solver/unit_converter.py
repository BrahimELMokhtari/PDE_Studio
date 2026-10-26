"""SI Unit Conversion and Parameter Normalization for Steady-State Heat Conduction."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from app.schemas.model_schema import (
    ALL_FACE_IDS,
    BoundaryConditionType,
    CanonicalSimulationModel,
    FaceId,
    LengthUnit,
    TemperatureUnit,
)
from app.solver.exceptions import (
    IllPosedProblemError,
    InvalidSimulationParameterError,
)

LENGTH_TO_METERS: dict[LengthUnit, float] = {
    LengthUnit.M: 1.0,
    LengthUnit.CM: 0.01,
    LengthUnit.MM: 0.001,
}


def model_temp_to_kelvin(value: float, unit: TemperatureUnit) -> float:
    """Convert a temperature value from the model's temperature unit to SI Kelvin (K)."""
    if unit == TemperatureUnit.C:
        return float(value) + 273.15
    return float(value)


def kelvin_to_model_temp(value_k: float, unit: TemperatureUnit) -> float:
    """Convert a temperature value from SI Kelvin (K) back to the model's temperature unit."""
    if unit == TemperatureUnit.C:
        return float(value_k) - 273.15
    return float(value_k)


@dataclass(frozen=True)
class NormalizedBoundaryConditionSI:
    """Boundary condition normalized to strict SI units (K, W/m^2, W/(m^2*K))."""

    face_id: FaceId
    bc_type: BoundaryConditionType
    temperature_k: Optional[float] = None
    outward_heat_flux_w_m2: Optional[float] = None
    convection_coeff_w_m2k: Optional[float] = None
    ambient_temperature_k: Optional[float] = None


@dataclass(frozen=True)
class NormalizedSIModel:
    """Complete simulation model normalized to SI units (m, K, W/(m*K), W/m^3)."""

    length_unit: LengthUnit
    temperature_unit: TemperatureUnit
    length_scale_to_m: float
    lx_m: float
    ly_m: float
    lz_m: float
    pos_x_m: float
    pos_y_m: float
    pos_z_m: float
    rot_x_deg: float
    rot_y_deg: float
    rot_z_deg: float
    maxh_m: float
    polynomial_order: int
    thermal_conductivity_w_mk: float
    volumetric_heat_source_w_m3: float
    boundary_conditions: dict[FaceId, NormalizedBoundaryConditionSI]


def convert_and_validate_si_model(
    model: CanonicalSimulationModel,
    override_max_element_size: Optional[float] = None,
    override_polynomial_order: Optional[int] = None,
) -> NormalizedSIModel:
    """Validate physical parameters, check well-posedness, and convert all quantities to SI."""
    scale = LENGTH_TO_METERS[model.units.length]
    temp_unit = model.units.temperature

    dims = model.geometry.dimensions
    if dims.length_x <= 0 or dims.length_y <= 0 or dims.length_z <= 0:
        raise InvalidSimulationParameterError(
            "Cuboid dimensions (length_x, length_y, length_z) must be strictly positive."
        )

    lx_m = dims.length_x * scale
    ly_m = dims.length_y * scale
    lz_m = dims.length_z * scale

    pos = model.geometry.position
    pos_x_m = pos.x * scale
    pos_y_m = pos.y * scale
    pos_z_m = pos.z * scale

    rot = model.geometry.rotation_deg

    k = model.material.thermal_conductivity
    if not math.isfinite(k) or k <= 0.0:
        raise InvalidSimulationParameterError(
            f"Material thermal conductivity k ({k}) must be finite and > 0 W/(m*K)."
        )

    q_vol = model.physics.volumetric_heat_source
    if not math.isfinite(q_vol):
        raise InvalidSimulationParameterError(
            "Volumetric heat source Q must be a finite number."
        )

    # Determine element size maxh in SI meters
    raw_maxh = (
        override_max_element_size
        if override_max_element_size is not None
        else getattr(model.mesh, "max_element_size", None)
    )
    if raw_maxh is not None:
        if not math.isfinite(raw_maxh) or raw_maxh <= 0.0:
            raise InvalidSimulationParameterError(
                "Configured mesh max_element_size must be finite and > 0."
            )
        maxh_m = float(raw_maxh) * scale
    else:
        nx = max(1, model.mesh.divisions.nx)
        ny = max(1, model.mesh.divisions.ny)
        nz = max(1, model.mesh.divisions.nz)
        # Derive characteristic element size from divisions along each axis
        maxh_m = max(lx_m / nx, ly_m / ny, lz_m / nz)

    min_dim_m = min(lx_m, ly_m, lz_m)
    if maxh_m < min_dim_m / 60.0:
        raise InvalidSimulationParameterError(
            f"Requested element size ({maxh_m:.6g} m) is too fine relative to smallest domain dimension ({min_dim_m:.6g} m) and would exceed memory/execution limits."
        )

    poly_order = (
        override_polynomial_order
        if override_polynomial_order is not None
        else getattr(model.mesh, "polynomial_order", 1)
    )
    if poly_order < 1 or poly_order > 3:
        raise InvalidSimulationParameterError(
            f"FEM polynomial_order ({poly_order}) must be between 1 and 3."
        )

    bcs_si: dict[FaceId, NormalizedBoundaryConditionSI] = {}
    has_reference_temperature = False

    for face_id in ALL_FACE_IDS:
        bc = getattr(model.boundary_conditions, face_id.value)
        if bc.type == BoundaryConditionType.DIRICHLET:
            if bc.temperature is None or not math.isfinite(bc.temperature):
                raise InvalidSimulationParameterError(
                    f"Face {face_id.value}: Dirichlet BC requires a finite temperature."
                )
            t_k = model_temp_to_kelvin(bc.temperature, temp_unit)
            if t_k < 0.0:
                raise InvalidSimulationParameterError(
                    f"Face {face_id.value}: Dirichlet temperature ({t_k:.2f} K) is below absolute zero (0 K)."
                )
            has_reference_temperature = True
            bcs_si[face_id] = NormalizedBoundaryConditionSI(
                face_id=face_id,
                bc_type=BoundaryConditionType.DIRICHLET,
                temperature_k=t_k,
            )
        elif bc.type == BoundaryConditionType.NEUMANN:
            if bc.heat_flux is None or not math.isfinite(bc.heat_flux):
                raise InvalidSimulationParameterError(
                    f"Face {face_id.value}: Neumann BC requires a finite outward heat_flux."
                )
            bcs_si[face_id] = NormalizedBoundaryConditionSI(
                face_id=face_id,
                bc_type=BoundaryConditionType.NEUMANN,
                outward_heat_flux_w_m2=float(bc.heat_flux),
            )
        elif bc.type == BoundaryConditionType.ROBIN:
            if (
                bc.convection_coefficient is None
                or not math.isfinite(bc.convection_coefficient)
                or bc.convection_coefficient <= 0.0
            ):
                raise InvalidSimulationParameterError(
                    f"Face {face_id.value}: Robin BC requires convection_coefficient > 0."
                )
            if bc.ambient_temperature is None or not math.isfinite(
                bc.ambient_temperature
            ):
                raise InvalidSimulationParameterError(
                    f"Face {face_id.value}: Robin BC requires a finite ambient_temperature."
                )
            t_amb_k = model_temp_to_kelvin(bc.ambient_temperature, temp_unit)
            if t_amb_k < 0.0:
                raise InvalidSimulationParameterError(
                    f"Face {face_id.value}: Robin ambient temperature ({t_amb_k:.2f} K) is below absolute zero (0 K)."
                )
            has_reference_temperature = True
            bcs_si[face_id] = NormalizedBoundaryConditionSI(
                face_id=face_id,
                bc_type=BoundaryConditionType.ROBIN,
                convection_coeff_w_m2k=float(bc.convection_coefficient),
                ambient_temperature_k=t_amb_k,
            )
        else:
            bcs_si[face_id] = NormalizedBoundaryConditionSI(
                face_id=face_id,
                bc_type=BoundaryConditionType.INSULATED,
            )

    if not has_reference_temperature:
        raise IllPosedProblemError(
            "Ill-posed steady-state thermal problem: No Dirichlet (fixed temperature) or "
            "Robin (convective) boundary condition is defined on any of the 6 cuboid faces "
            "(X_MIN..Z_MAX). Pure Neumann/Insulated steady-state heat conduction has a "
            "singular stiffness matrix without a unique temperature solution."
        )

    return NormalizedSIModel(
        length_unit=model.units.length,
        temperature_unit=temp_unit,
        length_scale_to_m=scale,
        lx_m=lx_m,
        ly_m=ly_m,
        lz_m=lz_m,
        pos_x_m=pos_x_m,
        pos_y_m=pos_y_m,
        pos_z_m=pos_z_m,
        rot_x_deg=rot.x,
        rot_y_deg=rot.y,
        rot_z_deg=rot.z,
        maxh_m=maxh_m,
        polynomial_order=poly_order,
        thermal_conductivity_w_mk=k,
        volumetric_heat_source_w_m3=q_vol,
        boundary_conditions=bcs_si,
    )
