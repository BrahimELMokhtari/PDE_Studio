/**
 * Canonical Model Factory, Scientific Validation, and Pre-Check Metrics.
 */

import {
  ALL_FACE_IDS,
  BoundaryConditionMap,
  CanonicalSimulationModel,
  FaceBoundaryCondition,
  FaceId,
  MATERIAL_PRESET_LIBRARY,
  SCHEMA_VERSION,
  ValidationIssue,
  ValidationReport,
} from '../types/model';

export function createDefaultBoundaryConditions(): BoundaryConditionMap {
  return {
    X_MIN: {
      face_id: 'X_MIN',
      type: 'dirichlet',
      temperature: 373.15,
      heat_flux: null,
      convection_coefficient: null,
      ambient_temperature: null,
    },
    X_MAX: {
      face_id: 'X_MAX',
      type: 'robin',
      temperature: null,
      heat_flux: null,
      convection_coefficient: 25.0,
      ambient_temperature: 293.15,
    },
    Y_MIN: {
      face_id: 'Y_MIN',
      type: 'insulated',
      temperature: null,
      heat_flux: null,
      convection_coefficient: null,
      ambient_temperature: null,
    },
    Y_MAX: {
      face_id: 'Y_MAX',
      type: 'insulated',
      temperature: null,
      heat_flux: null,
      convection_coefficient: null,
      ambient_temperature: null,
    },
    Z_MIN: {
      face_id: 'Z_MIN',
      type: 'insulated',
      temperature: null,
      heat_flux: null,
      convection_coefficient: null,
      ambient_temperature: null,
    },
    Z_MAX: {
      face_id: 'Z_MAX',
      type: 'insulated',
      temperature: null,
      heat_flux: null,
      convection_coefficient: null,
      ambient_temperature: null,
    },
  };
}

export function createDefaultModel(name = 'Copper Thermal Block'): CanonicalSimulationModel {
  const now = new Date().toISOString();
  const copper = MATERIAL_PRESET_LIBRARY.copper;

  return {
    schema_version: SCHEMA_VERSION,
    metadata: {
      name,
      description:
        'Steady-state 3D heat conduction across a parametric copper block with Dirichlet heating on X_MIN and convective cooling on X_MAX.',
      author: 'CAE Engineer',
      created_at: now,
      updated_at: now,
    },
    units: {
      length: 'm',
      temperature: 'K',
      thermal_conductivity: 'W/(m*K)',
      heat_source: 'W/m^3',
      heat_flux: 'W/m^2',
      convection_coefficient: 'W/(m^2*K)',
    },
    geometry: {
      type: 'rectangular_cuboid',
      dimensions: {
        length_x: 1.2,
        length_y: 0.7,
        length_z: 0.5,
      },
      position: { x: 0, y: 0, z: 0 },
      rotation_deg: { x: 0, y: 0, z: 0 },
    },
    material: {
      id: copper.id,
      name: copper.name,
      preset: copper.preset,
      thermal_conductivity: copper.thermal_conductivity,
    },
    physics: {
      type: 'steady_state_heat_conduction',
      volumetric_heat_source: 1500.0,
    },
    boundary_conditions: createDefaultBoundaryConditions(),
    mesh: {
      element_type: 'hexahedral_8node',
      divisions: {
        nx: 12,
        ny: 7,
        nz: 5,
      },
    },
  };
}

export type ProjectTemplateId = 'copper_block' | 'al_heat_spreader' | 'silicon_die';

export function createModelFromTemplate(templateId: ProjectTemplateId): CanonicalSimulationModel {
  const base = createDefaultModel();

  if (templateId === 'al_heat_spreader') {
    const al = MATERIAL_PRESET_LIBRARY.aluminum_6061;
    return {
      ...base,
      metadata: {
        ...base.metadata,
        name: 'Aluminum 6061 Heat Spreader Plate',
        description:
          'Bottom-heated aluminum plate with top convective cooling and lateral adiabatic boundaries.',
      },
      geometry: {
        type: 'rectangular_cuboid',
        dimensions: { length_x: 1.6, length_y: 0.3, length_z: 1.2 },
        position: { x: 0, y: 0, z: 0 },
        rotation_deg: { x: 0, y: 0, z: 0 },
      },
      material: {
        id: al.id,
        name: al.name,
        preset: al.preset,
        thermal_conductivity: al.thermal_conductivity,
      },
      physics: {
        type: 'steady_state_heat_conduction',
        volumetric_heat_source: 500.0,
      },
      boundary_conditions: {
        ...createDefaultBoundaryConditions(),
        X_MIN: {
          face_id: 'X_MIN',
          type: 'insulated',
          temperature: null,
          heat_flux: null,
          convection_coefficient: null,
          ambient_temperature: null,
        },
        X_MAX: {
          face_id: 'X_MAX',
          type: 'insulated',
          temperature: null,
          heat_flux: null,
          convection_coefficient: null,
          ambient_temperature: null,
        },
        Y_MIN: {
          face_id: 'Y_MIN',
          type: 'dirichlet',
          temperature: 360.0,
          heat_flux: null,
          convection_coefficient: null,
          ambient_temperature: null,
        },
        Y_MAX: {
          face_id: 'Y_MAX',
          type: 'robin',
          temperature: null,
          heat_flux: null,
          convection_coefficient: 45.0,
          ambient_temperature: 295.0,
        },
      },
      mesh: {
        element_type: 'hexahedral_8node',
        divisions: { nx: 16, ny: 4, nz: 12 },
      },
    };
  }

  if (templateId === 'silicon_die') {
    const si = MATERIAL_PRESET_LIBRARY.silicon;
    return {
      ...base,
      units: {
        ...base.units,
        length: 'mm',
        temperature: 'C',
      },
      metadata: {
        ...base.metadata,
        name: 'Silicon Power Die Package',
        description:
          'High power-density semiconductor substrate with Neumann heat flux input and bottom cold-plate Dirichlet boundary.',
      },
      geometry: {
        type: 'rectangular_cuboid',
        dimensions: { length_x: 2.0, length_y: 0.5, length_z: 2.0 },
        position: { x: 0, y: 0, z: 0 },
        rotation_deg: { x: 0, y: 0, z: 0 },
      },
      material: {
        id: si.id,
        name: si.name,
        preset: si.preset,
        thermal_conductivity: si.thermal_conductivity,
      },
      physics: {
        type: 'steady_state_heat_conduction',
        volumetric_heat_source: 25000.0,
      },
      boundary_conditions: {
        ...createDefaultBoundaryConditions(),
        X_MIN: {
          face_id: 'X_MIN',
          type: 'insulated',
          temperature: null,
          heat_flux: null,
          convection_coefficient: null,
          ambient_temperature: null,
        },
        X_MAX: {
          face_id: 'X_MAX',
          type: 'insulated',
          temperature: null,
          heat_flux: null,
          convection_coefficient: null,
          ambient_temperature: null,
        },
        Y_MIN: {
          face_id: 'Y_MIN',
          type: 'dirichlet',
          temperature: 25.0,
          heat_flux: null,
          convection_coefficient: null,
          ambient_temperature: null,
        },
        Y_MAX: {
          face_id: 'Y_MAX',
          type: 'neumann',
          temperature: null,
          heat_flux: 12000.0,
          convection_coefficient: null,
          ambient_temperature: null,
        },
      },
      mesh: {
        element_type: 'hexahedral_8node',
        divisions: { nx: 16, ny: 6, nz: 16 },
      },
    };
  }

  return base;
}

/**
 * Validates a CanonicalSimulationModel on the client side using the exact same rules
 * as the FastAPI Pydantic schema and scientific validator.
 */
export function validateCanonicalModel(model: CanonicalSimulationModel): ValidationReport {
  const issues: ValidationIssue[] = [];

  if (model.schema_version !== SCHEMA_VERSION) {
    issues.push({
      severity: 'error',
      field: 'schema_version',
      message: `Unsupported schema_version '${String(model.schema_version)}'. Expected '${SCHEMA_VERSION}'.`,
    });
  }

  if (!model.metadata.name || !model.metadata.name.trim()) {
    issues.push({
      severity: 'error',
      field: 'metadata.name',
      message: 'Project name must not be empty.',
    });
  }

  const { length_x, length_y, length_z } = model.geometry.dimensions;
  if (!Number.isFinite(length_x) || length_x <= 0) {
    issues.push({
      severity: 'error',
      field: 'geometry.dimensions.length_x',
      message: 'Dimension X (Width) must be greater than 0.',
    });
  }
  if (!Number.isFinite(length_y) || length_y <= 0) {
    issues.push({
      severity: 'error',
      field: 'geometry.dimensions.length_y',
      message: 'Dimension Y (Height) must be greater than 0.',
    });
  }
  if (!Number.isFinite(length_z) || length_z <= 0) {
    issues.push({
      severity: 'error',
      field: 'geometry.dimensions.length_z',
      message: 'Dimension Z (Depth) must be greater than 0.',
    });
  }

  const rot = model.geometry.rotation_deg;
  for (const axis of ['x', 'y', 'z'] as const) {
    if (!Number.isFinite(rot[axis]) || rot[axis] < -360 || rot[axis] > 360) {
      issues.push({
        severity: 'error',
        field: `geometry.rotation_deg.${axis}`,
        message: `Rotation ${axis.toUpperCase()} must be between -360° and 360°.`,
      });
    }
  }

  if (
    !Number.isFinite(model.material.thermal_conductivity) ||
    model.material.thermal_conductivity <= 0
  ) {
    issues.push({
      severity: 'error',
      field: 'material.thermal_conductivity',
      message: 'Thermal conductivity k must be strictly positive (> 0 W/(m·K)).',
    });
  }

  if (!Number.isFinite(model.physics.volumetric_heat_source)) {
    issues.push({
      severity: 'error',
      field: 'physics.volumetric_heat_source',
      message: 'Volumetric heat source Q must be a finite number.',
    });
  }

  const minTemp = model.units.temperature === 'K' ? 0 : -273.15;
  const tempUnit = model.units.temperature;
  let hasAnchoringBC = false;

  for (const faceId of ALL_FACE_IDS) {
    const bc: FaceBoundaryCondition | undefined = model.boundary_conditions?.[faceId];
    if (!bc) {
      issues.push({
        severity: 'error',
        field: `boundary_conditions.${faceId}`,
        message: `Missing boundary condition for semantic face ${faceId}.`,
      });
      continue;
    }
    if (bc.face_id !== faceId) {
      issues.push({
        severity: 'error',
        field: `boundary_conditions.${faceId}.face_id`,
        message: `Face key ${faceId} does not match inner face_id ${bc.face_id}.`,
      });
    }

    if (bc.type === 'dirichlet') {
      hasAnchoringBC = true;
      if (bc.temperature === null || !Number.isFinite(bc.temperature)) {
        issues.push({
          severity: 'error',
          field: `boundary_conditions.${faceId}.temperature`,
          message: `Face ${faceId} (Dirichlet): Fixed temperature is required.`,
        });
      } else if (bc.temperature < minTemp) {
        issues.push({
          severity: 'error',
          field: `boundary_conditions.${faceId}.temperature`,
          message: `Face ${faceId}: Temperature (${bc.temperature} ${tempUnit}) is below absolute zero (${minTemp} ${tempUnit}).`,
        });
      }
    } else if (bc.type === 'neumann') {
      if (bc.heat_flux === null || !Number.isFinite(bc.heat_flux)) {
        issues.push({
          severity: 'error',
          field: `boundary_conditions.${faceId}.heat_flux`,
          message: `Face ${faceId} (Neumann): Heat flux q₀ is required.`,
        });
      }
    } else if (bc.type === 'robin') {
      hasAnchoringBC = true;
      if (
        bc.convection_coefficient === null ||
        !Number.isFinite(bc.convection_coefficient) ||
        bc.convection_coefficient <= 0
      ) {
        issues.push({
          severity: 'error',
          field: `boundary_conditions.${faceId}.convection_coefficient`,
          message: `Face ${faceId} (Robin): Convection coefficient h must be > 0.`,
        });
      }
      if (bc.ambient_temperature === null || !Number.isFinite(bc.ambient_temperature)) {
        issues.push({
          severity: 'error',
          field: `boundary_conditions.${faceId}.ambient_temperature`,
          message: `Face ${faceId} (Robin): Ambient temperature T∞ is required.`,
        });
      } else if (bc.ambient_temperature < minTemp) {
        issues.push({
          severity: 'error',
          field: `boundary_conditions.${faceId}.ambient_temperature`,
          message: `Face ${faceId}: Ambient temperature (${bc.ambient_temperature} ${tempUnit}) is below absolute zero.`,
        });
      }
    }
  }

  if (!hasAnchoringBC) {
    issues.push({
      severity: 'warning',
      field: 'boundary_conditions',
      message:
        'No Dirichlet or Robin BC is assigned on any face. Steady-state heat conduction with only Neumann/Insulated boundaries has a non-unique solution.',
    });
  }

  const { nx, ny, nz } = model.mesh.divisions;
  for (const [key, val] of [
    ['nx', nx],
    ['ny', ny],
    ['nz', nz],
  ] as const) {
    if (!Number.isInteger(val) || val < 1 || val > 200) {
      issues.push({
        severity: 'error',
        field: `mesh.divisions.${key}`,
        message: `Mesh division ${key} must be an integer between 1 and 200.`,
      });
    }
  }

  const safeLx = Math.max(length_x, 1e-6);
  const safeLy = Math.max(length_y, 1e-6);
  const safeLz = Math.max(length_z, 1e-6);
  const safeNx = Math.max(1, Math.floor(nx || 1));
  const safeNy = Math.max(1, Math.floor(ny || 1));
  const safeNz = Math.max(1, Math.floor(nz || 1));

  const dx = safeLx / safeNx;
  const dy = safeLy / safeNy;
  const dz = safeLz / safeNz;
  const aspectRatio = Math.max(dx, dy, dz) / Math.min(dx, dy, dz);

  if (aspectRatio > 5.0) {
    issues.push({
      severity: 'warning',
      field: 'mesh.divisions',
      message: `Mesh element aspect ratio is ${aspectRatio.toFixed(2)} (> 5.0). Adjust nx, ny, nz for more uniform cells.`,
    });
  }

  const baseHex = safeNx * safeNy * safeNz;
  const totalElements =
    model.mesh.element_type === 'hexahedral_8node' ? baseHex : baseHex * 6;
  const totalNodes = (safeNx + 1) * (safeNy + 1) * (safeNz + 1);
  const volume = safeLx * safeLy * safeLz;
  const surfaceArea = 2 * (safeLx * safeLy + safeLy * safeLz + safeLx * safeLz);

  return {
    valid: !issues.some((i) => i.severity === 'error'),
    schema_version: SCHEMA_VERSION,
    issues,
    metrics: {
      volume: Number(volume.toFixed(6)),
      surface_area: Number(surfaceArea.toFixed(6)),
      total_elements: totalElements,
      total_nodes: totalNodes,
      element_aspect_ratio: Number(aspectRatio.toFixed(4)),
    },
  };
}

/**
 * Parses and validates an imported JSON string (supporting both wrapped ProjectExportPayload
 * and direct CanonicalSimulationModel JSON).
 */
export function parseAndValidateImportedJson(rawJson: string): {
  model: CanonicalSimulationModel;
  report: ValidationReport;
} {
  let parsed: unknown;
  try {
    parsed = JSON.parse(rawJson);
  } catch {
    throw new Error('The selected file is not valid JSON.');
  }

  if (!parsed || typeof parsed !== 'object') {
    throw new Error('JSON root must be an object.');
  }

  const obj = parsed as Record<string, unknown>;
  const candidateModel = (
    obj.model && typeof obj.model === 'object' ? obj.model : obj
  ) as CanonicalSimulationModel;

  if (candidateModel.schema_version !== SCHEMA_VERSION) {
    throw new Error(
      `Invalid or missing schema_version '${String(candidateModel.schema_version)}'. Expected '${SCHEMA_VERSION}'.`
    );
  }

  if (
    !candidateModel.geometry ||
    candidateModel.geometry.type !== 'rectangular_cuboid' ||
    !candidateModel.geometry.dimensions
  ) {
    throw new Error('Invalid or missing rectangular_cuboid geometry block in JSON.');
  }

  if (!candidateModel.boundary_conditions) {
    throw new Error('Missing boundary_conditions map in JSON.');
  }

  for (const faceId of ALL_FACE_IDS as readonly FaceId[]) {
    if (!candidateModel.boundary_conditions[faceId]) {
      throw new Error(`Missing semantic face '${faceId}' in boundary_conditions.`);
    }
  }

  const report = validateCanonicalModel(candidateModel);
  const firstError = report.issues.find((i) => i.severity === 'error');
  if (firstError) {
    throw new Error(`Model validation error (${firstError.field}): ${firstError.message}`);
  }

  return { model: candidateModel, report };
}
