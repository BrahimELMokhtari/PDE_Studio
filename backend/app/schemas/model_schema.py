"""Canonical versioned JSON simulation model schema (v1.0.0) shared between frontend and backend."""

from __future__ import annotations

import math
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0.0"


class FaceId(str, Enum):
    """Stable semantic identifiers for the 6 faces of a rectangular cuboid."""

    X_MIN = "X_MIN"
    X_MAX = "X_MAX"
    Y_MIN = "Y_MIN"
    Y_MAX = "Y_MAX"
    Z_MIN = "Z_MIN"
    Z_MAX = "Z_MAX"


ALL_FACE_IDS: tuple[FaceId, ...] = (
    FaceId.X_MIN,
    FaceId.X_MAX,
    FaceId.Y_MIN,
    FaceId.Y_MAX,
    FaceId.Z_MIN,
    FaceId.Z_MAX,
)


class LengthUnit(str, Enum):
    M = "m"
    CM = "cm"
    MM = "mm"


class TemperatureUnit(str, Enum):
    K = "K"
    C = "C"


class MaterialPreset(str, Enum):
    COPPER = "copper"
    ALUMINUM_6061 = "aluminum_6061"
    STEEL_304 = "steel_304"
    SILICON = "silicon"
    TITANIUM = "titanium"
    CUSTOM = "custom"


class BoundaryConditionType(str, Enum):
    DIRICHLET = "dirichlet"
    NEUMANN = "neumann"
    ROBIN = "robin"
    INSULATED = "insulated"


class ElementType(str, Enum):
    HEXAHEDRAL_8NODE = "hexahedral_8node"
    TETRAHEDRAL_4NODE = "tetrahedral_4node"


class ModelMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=120, description="Model name")
    description: str = Field(
        default="", max_length=1000, description="Engineering description"
    )
    author: str = Field(
        default="Engineer", max_length=120, description="Model author"
    )
    created_at: Optional[str] = Field(default=None)
    updated_at: Optional[str] = Field(default=None)

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Model metadata name must not be blank.")
        return cleaned


class UnitSystem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    length: LengthUnit = Field(default=LengthUnit.M)
    temperature: TemperatureUnit = Field(default=TemperatureUnit.K)
    thermal_conductivity: Literal["W/(m*K)"] = Field(default="W/(m*K)")
    heat_source: Literal["W/m^3"] = Field(default="W/m^3")
    heat_flux: Literal["W/m^2"] = Field(default="W/m^2")
    convection_coefficient: Literal["W/(m^2*K)"] = Field(default="W/(m^2*K)")


class CuboidDimensions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    length_x: float = Field(
        ..., gt=0.0, le=1e6, description="Dimension along local X axis"
    )
    length_y: float = Field(
        ..., gt=0.0, le=1e6, description="Dimension along local Y axis"
    )
    length_z: float = Field(
        ..., gt=0.0, le=1e6, description="Dimension along local Z axis"
    )

    @field_validator("length_x", "length_y", "length_z")
    @classmethod
    def ensure_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Cuboid dimension must be a finite number.")
        return value


class Vector3D(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(default=0.0)
    y: float = Field(default=0.0)
    z: float = Field(default=0.0)

    @field_validator("x", "y", "z")
    @classmethod
    def ensure_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Coordinate value must be a finite number.")
        return value


class Rotation3D(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(default=0.0, ge=-360.0, le=360.0)
    y: float = Field(default=0.0, ge=-360.0, le=360.0)
    z: float = Field(default=0.0, ge=-360.0, le=360.0)

    @field_validator("x", "y", "z")
    @classmethod
    def ensure_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Rotation angle must be a finite number.")
        return value


class CuboidGeometry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["rectangular_cuboid"] = Field(default="rectangular_cuboid")
    dimensions: CuboidDimensions
    position: Vector3D = Field(default_factory=Vector3D)
    rotation_deg: Rotation3D = Field(default_factory=Rotation3D)


class MaterialConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default="mat_copper", min_length=1, max_length=80)
    name: str = Field(..., min_length=1, max_length=100)
    preset: MaterialPreset = Field(default=MaterialPreset.COPPER)
    thermal_conductivity: float = Field(
        ..., gt=0.0, le=1e6, description="Thermal conductivity k in W/(m*K)"
    )

    @field_validator("thermal_conductivity")
    @classmethod
    def ensure_finite_conductivity(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Thermal conductivity must be finite and > 0.")
        return value


class PhysicsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["steady_state_heat_conduction"] = Field(
        default="steady_state_heat_conduction"
    )
    volumetric_heat_source: float = Field(
        default=0.0, description="Internal volumetric heat generation Q in W/m^3"
    )

    @field_validator("volumetric_heat_source")
    @classmethod
    def ensure_finite_source(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Volumetric heat source must be a finite number.")
        return value


class FaceBoundaryCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    face_id: FaceId
    type: BoundaryConditionType
    temperature: Optional[float] = Field(
        default=None, description="Fixed temperature T0 for Dirichlet BC"
    )
    heat_flux: Optional[float] = Field(
        default=None, description="Specified inward/outward heat flux q0 for Neumann BC"
    )
    convection_coefficient: Optional[float] = Field(
        default=None, description="Convection heat transfer coefficient h for Robin BC"
    )
    ambient_temperature: Optional[float] = Field(
        default=None, description="Ambient fluid temperature T_inf for Robin BC"
    )

    @model_validator(mode="after")
    def validate_bc_parameters(self) -> "FaceBoundaryCondition":
        if self.type == BoundaryConditionType.DIRICHLET:
            if self.temperature is None or not math.isfinite(self.temperature):
                raise ValueError(
                    f"Face {self.face_id.value}: Dirichlet boundary condition requires a finite 'temperature' value."
                )
        elif self.type == BoundaryConditionType.NEUMANN:
            if self.heat_flux is None or not math.isfinite(self.heat_flux):
                raise ValueError(
                    f"Face {self.face_id.value}: Neumann boundary condition requires a finite 'heat_flux' value."
                )
        elif self.type == BoundaryConditionType.ROBIN:
            if (
                self.convection_coefficient is None
                or not math.isfinite(self.convection_coefficient)
                or self.convection_coefficient <= 0.0
            ):
                raise ValueError(
                    f"Face {self.face_id.value}: Robin boundary condition requires 'convection_coefficient' > 0."
                )
            if self.ambient_temperature is None or not math.isfinite(
                self.ambient_temperature
            ):
                raise ValueError(
                    f"Face {self.face_id.value}: Robin boundary condition requires a finite 'ambient_temperature' value."
                )
        elif self.type == BoundaryConditionType.INSULATED:
            # Insulated is equivalent to zero heat flux; extra parameters are ignored/nullable
            pass
        return self


class BoundaryConditionMap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    X_MIN: FaceBoundaryCondition
    X_MAX: FaceBoundaryCondition
    Y_MIN: FaceBoundaryCondition
    Y_MAX: FaceBoundaryCondition
    Z_MIN: FaceBoundaryCondition
    Z_MAX: FaceBoundaryCondition

    @model_validator(mode="after")
    def ensure_face_keys_match_ids(self) -> "BoundaryConditionMap":
        for face in ALL_FACE_IDS:
            bc: FaceBoundaryCondition = getattr(self, face.value)
            if bc.face_id != face:
                raise ValueError(
                    f"Boundary condition under key '{face.value}' has mismatched face_id '{bc.face_id.value}'."
                )
        return self


class MeshDivisions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nx: int = Field(default=10, ge=1, le=200)
    ny: int = Field(default=10, ge=1, le=200)
    nz: int = Field(default=10, ge=1, le=200)


class MeshConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    element_type: ElementType = Field(default=ElementType.TETRAHEDRAL_4NODE)
    divisions: MeshDivisions = Field(default_factory=MeshDivisions)
    max_element_size: Optional[float] = Field(
        default=None,
        gt=0.0,
        le=1e6,
        description="Target maximum tetrahedral element size (h_max) in model length units.",
    )
    polynomial_order: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Lagrange H1 finite element polynomial order (1, 2, or 3).",
    )

    @field_validator("max_element_size")
    @classmethod
    def ensure_finite_maxh(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and not math.isfinite(value):
            raise ValueError("max_element_size must be a finite positive number.")
        return value


class CanonicalSimulationModel(BaseModel):
    """Canonical versioned simulation model shared across frontend and backend."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = Field(default=SCHEMA_VERSION)
    metadata: ModelMetadata
    units: UnitSystem = Field(default_factory=UnitSystem)
    geometry: CuboidGeometry
    material: MaterialConfig
    physics: PhysicsConfig = Field(default_factory=PhysicsConfig)
    boundary_conditions: BoundaryConditionMap
    mesh: MeshConfig = Field(default_factory=MeshConfig)

    @model_validator(mode="after")
    def validate_physical_temperatures(self) -> "CanonicalSimulationModel":
        min_temp = 0.0 if self.units.temperature == TemperatureUnit.K else -273.15
        unit_label = self.units.temperature.value

        for face in ALL_FACE_IDS:
            bc: FaceBoundaryCondition = getattr(self.boundary_conditions, face.value)
            if bc.type == BoundaryConditionType.DIRICHLET and bc.temperature is not None:
                if bc.temperature < min_temp:
                    raise ValueError(
                        f"Face {face.value}: Temperature ({bc.temperature} {unit_label}) cannot be below absolute zero ({min_temp} {unit_label})."
                    )
            if bc.type == BoundaryConditionType.ROBIN and bc.ambient_temperature is not None:
                if bc.ambient_temperature < min_temp:
                    raise ValueError(
                        f"Face {face.value}: Ambient temperature ({bc.ambient_temperature} {unit_label}) cannot be below absolute zero ({min_temp} {unit_label})."
                    )
        return self


class ValidationIssue(BaseModel):
    severity: Literal["error", "warning", "info"]
    field: str
    message: str


class ValidationReport(BaseModel):
    valid: bool
    schema_version: str = SCHEMA_VERSION
    issues: list[ValidationIssue] = Field(default_factory=list)
    metrics: dict[str, float | int] = Field(default_factory=dict)


def validate_scientific_model(model: CanonicalSimulationModel) -> ValidationReport:
    """Perform engineering and numerical pre-check on a validated canonical model."""
    issues: list[ValidationIssue] = []

    # Check whether at least one face anchors temperature (Dirichlet or Robin)
    anchoring_faces = [
        face.value
        for face in ALL_FACE_IDS
        if getattr(model.boundary_conditions, face.value).type
        in (BoundaryConditionType.DIRICHLET, BoundaryConditionType.ROBIN)
    ]
    if not anchoring_faces:
        issues.append(
            ValidationIssue(
                severity="warning",
                field="boundary_conditions",
                message=(
                    "No Dirichlet or Robin boundary condition is defined on any face. "
                    "Steady-state heat conduction with only Neumann/Insulated boundaries has a non-unique temperature field."
                ),
            )
        )

    # Check mesh aspect ratio
    dx = model.geometry.dimensions.length_x / model.mesh.divisions.nx
    dy = model.geometry.dimensions.length_y / model.mesh.divisions.ny
    dz = model.geometry.dimensions.length_z / model.mesh.divisions.nz
    min_h = min(dx, dy, dz)
    max_h = max(dx, dy, dz)
    aspect_ratio = max_h / min_h if min_h > 0 else 1.0

    if aspect_ratio > 5.0:
        issues.append(
            ValidationIssue(
                severity="warning",
                field="mesh.divisions",
                message=(
                    f"Element aspect ratio is {aspect_ratio:.2f} (> 5.0). "
                    "Consider adjusting mesh divisions (nx, ny, nz) to improve element quality."
                ),
            )
        )

    nx = model.mesh.divisions.nx
    ny = model.mesh.divisions.ny
    nz = model.mesh.divisions.nz
    base_hex_elements = nx * ny * nz
    total_elements = (
        base_hex_elements
        if model.mesh.element_type == ElementType.HEXAHEDRAL_8NODE
        else base_hex_elements * 6
    )
    total_nodes = (nx + 1) * (ny + 1) * (nz + 1)
    volume = (
        model.geometry.dimensions.length_x
        * model.geometry.dimensions.length_y
        * model.geometry.dimensions.length_z
    )
    surface_area = 2.0 * (
        model.geometry.dimensions.length_x * model.geometry.dimensions.length_y
        + model.geometry.dimensions.length_y * model.geometry.dimensions.length_z
        + model.geometry.dimensions.length_x * model.geometry.dimensions.length_z
    )

    return ValidationReport(
        valid=not any(i.severity == "error" for i in issues),
        schema_version=model.schema_version,
        issues=issues,
        metrics={
            "volume": round(volume, 6),
            "surface_area": round(surface_area, 6),
            "total_elements": total_elements,
            "total_nodes": total_nodes,
            "element_aspect_ratio": round(aspect_ratio, 4),
        },
    )
