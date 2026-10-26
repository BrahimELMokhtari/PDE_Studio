import { describe, expect, it } from 'vitest';
import {
  createDefaultModel,
  parseAndValidateImportedJson,
  validateCanonicalModel,
} from '../utils/modelValidation';

describe('Canonical Simulation Model Validation (v1.0.0)', () => {
  it('creates a valid default Copper Thermal Block model', () => {
    const model = createDefaultModel();
    const report = validateCanonicalModel(model);
    expect(report.valid).toBe(true);
    expect(report.schema_version).toBe('1.0.0');
    expect(report.metrics.total_elements).toBe(12 * 7 * 5);
    expect(report.metrics.total_nodes).toBe(13 * 8 * 6);
  });

  it('flags non-positive cuboid dimensions and thermal conductivity as errors', () => {
    const model = createDefaultModel();
    model.geometry.dimensions.length_x = -0.5;
    model.material.thermal_conductivity = 0;

    const report = validateCanonicalModel(model);
    expect(report.valid).toBe(false);
    expect(
      report.issues.some((i) => i.field === 'geometry.dimensions.length_x' && i.severity === 'error')
    ).toBe(true);
    expect(
      report.issues.some(
        (i) => i.field === 'material.thermal_conductivity' && i.severity === 'error'
      )
    ).toBe(true);
  });

  it('validates Dirichlet and Robin boundary condition constraints', () => {
    const model = createDefaultModel();
    model.boundary_conditions.X_MIN.type = 'dirichlet';
    model.boundary_conditions.X_MIN.temperature = -10; // Invalid in Kelvin

    const report = validateCanonicalModel(model);
    expect(report.valid).toBe(false);
    expect(
      report.issues.some((i) => i.field === 'boundary_conditions.X_MIN.temperature')
    ).toBe(true);
  });

  it('parses and validates exported JSON payloads on import', () => {
    const model = createDefaultModel('Exported Test Model');
    const wrappedJson = JSON.stringify({
      export_format: 'pde_simulation_studio_project',
      schema_version: '1.0.0',
      exported_at: '2026-10-25T20:00:00Z',
      model,
    });

    const { model: parsed, report } = parseAndValidateImportedJson(wrappedJson);
    expect(parsed.metadata.name).toBe('Exported Test Model');
    expect(report.valid).toBe(true);
  });
});
