/**
 * Right Properties Inspector Panel (Phase 2)
 *
 * Provides 4 Engineering Inspector Tabs:
 * 1. Boundary Conditions (Dirichlet, Neumann outward flux, Robin convection, Insulated) per semantic face
 * 2. Physics & Material (Steady-state heat conduction equation -div(k grad(T)) = Q)
 * 3. Mesh Configuration (Netgen/OpenCASCADE tetrahedral element size max_element_size, polynomial_order, divisions)
 * 4. Canonical JSON Schema Inspector
 */

import React, { useState } from 'react';
import {
  ALL_FACE_IDS,
  BoundaryConditionType,
  CanonicalSimulationModel,
  ElementType,
  FaceBoundaryCondition,
  FaceId,
  MATERIAL_PRESET_LIBRARY,
  MaterialConfig,
  MaterialPreset,
  MeshConfig,
  OPPOSITE_FACE_MAP,
  PhysicsConfig,
  ValidationReport,
} from '../types/model';
import {
  getSemanticFacePlaneTransform,
  SEMANTIC_FACE_DESCRIPTORS,
} from '../utils/semanticFaces';

export interface RightInspectorPanelProps {
  model: CanonicalSimulationModel;
  validationReport: ValidationReport;
  selectedFace: FaceId;
  activeTab: 'boundaries' | 'physics' | 'mesh' | 'json';
  onTabChange: (tab: 'boundaries' | 'physics' | 'mesh' | 'json') => void;
  onSelectFace: (faceId: FaceId) => void;
  onUpdateFaceBC: (faceId: FaceId, updated: Partial<FaceBoundaryCondition>) => void;
  onCopyBcToOppositeFace: (sourceFaceId: FaceId) => void;
  onUpdateMaterial: (updated: Partial<MaterialConfig>) => void;
  onSelectMaterialPreset: (preset: MaterialPreset) => void;
  onUpdatePhysics: (updated: Partial<PhysicsConfig>) => void;
  onUpdateMesh: (updated: Partial<MeshConfig>) => void;
  onUpdateMetadata: (updated: { description?: string; author?: string }) => void;
  onTriggerBackendValidation: () => void;
}

export const RightInspectorPanel: React.FC<RightInspectorPanelProps> = ({
  model,
  validationReport,
  selectedFace,
  activeTab,
  onTabChange,
  onSelectFace,
  onUpdateFaceBC,
  onCopyBcToOppositeFace,
  onUpdateMaterial,
  onSelectMaterialPreset,
  onUpdatePhysics,
  onUpdateMesh,
  onUpdateMetadata,
  onTriggerBackendValidation,
}) => {
  const [copiedJson, setCopiedJson] = useState(false);

  const activeBc = model.boundary_conditions[selectedFace];
  const faceDesc = SEMANTIC_FACE_DESCRIPTORS[selectedFace];
  const faceTransform = getSemanticFacePlaneTransform(
    selectedFace,
    model.geometry.dimensions,
    model.mesh.divisions
  );
  const oppositeFace = OPPOSITE_FACE_MAP[selectedFace];
  const tempUnit = model.units.temperature;
  const lengthUnit = model.units.length;

  const handleBcTypeChange = (newType: BoundaryConditionType) => {
    const defaultTemp = tempUnit === 'K' ? 300.0 : 25.0;
    if (newType === 'dirichlet') {
      onUpdateFaceBC(selectedFace, {
        type: 'dirichlet',
        temperature: activeBc.temperature ?? defaultTemp,
        heat_flux: null,
        convection_coefficient: null,
        ambient_temperature: null,
      });
    } else if (newType === 'neumann') {
      onUpdateFaceBC(selectedFace, {
        type: 'neumann',
        temperature: null,
        heat_flux: activeBc.heat_flux ?? 1000.0,
        convection_coefficient: null,
        ambient_temperature: null,
      });
    } else if (newType === 'robin') {
      onUpdateFaceBC(selectedFace, {
        type: 'robin',
        temperature: null,
        heat_flux: null,
        convection_coefficient: activeBc.convection_coefficient ?? 25.0,
        ambient_temperature: activeBc.ambient_temperature ?? defaultTemp,
      });
    } else {
      onUpdateFaceBC(selectedFace, {
        type: 'insulated',
        temperature: null,
        heat_flux: null,
        convection_coefficient: null,
        ambient_temperature: null,
      });
    }
  };

  const handleCopyJson = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(model, null, 2));
      setCopiedJson(true);
      setTimeout(() => setCopiedJson(false), 2000);
    } catch {
      // Clipboard API may be unavailable in restricted contexts
    }
  };

  const computedDefaultMaxH = Number(
    Math.max(
      model.geometry.dimensions.length_x / Math.max(1, model.mesh.divisions.nx),
      model.geometry.dimensions.length_y / Math.max(1, model.mesh.divisions.ny),
      model.geometry.dimensions.length_z / Math.max(1, model.mesh.divisions.nz)
    ).toFixed(4)
  );

  return (
    <aside className="right-inspector" aria-label="Properties Inspector">
      <div className="inspector-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'boundaries'}
          className={`inspector-tab ${activeTab === 'boundaries' ? 'active' : ''}`}
          onClick={() => onTabChange('boundaries')}
        >
          Boundaries
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'physics'}
          className={`inspector-tab ${activeTab === 'physics' ? 'active' : ''}`}
          onClick={() => onTabChange('physics')}
        >
          Physics &amp; Material
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'mesh'}
          className={`inspector-tab ${activeTab === 'mesh' ? 'active' : ''}`}
          onClick={() => onTabChange('mesh')}
        >
          Mesh
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'json'}
          className={`inspector-tab ${activeTab === 'json' ? 'active' : ''}`}
          onClick={() => onTabChange('json')}
        >
          Schema JSON
        </button>
      </div>

      <div className="inspector-content">
        {/* TAB 1: BOUNDARY CONDITIONS */}
        {activeTab === 'boundaries' && (
          <div className="inspector-pane" data-testid="inspector-pane-boundaries">
            <div className="pane-header">
              <h3>Boundary Condition Inspector</h3>
              <p className="pane-subtitle">
                Assign boundary conditions using stable semantic face IDs.
              </p>
            </div>

            <div className="face-pill-grid" role="group" aria-label="Inspector Face Selector">
              {ALL_FACE_IDS.map((fid) => {
                const bc = model.boundary_conditions[fid];
                return (
                  <button
                    key={fid}
                    type="button"
                    data-testid={`inspector-face-pill-${fid}`}
                    className={`face-pill-btn ${selectedFace === fid ? 'selected' : ''}`}
                    onClick={() => onSelectFace(fid)}
                  >
                    <span className="pill-fid">{fid}</span>
                    <span className={`pill-bctype bc-${bc.type}`}>{bc.type}</span>
                  </button>
                );
              })}
            </div>

            <div className="control-card highlight-card">
              <div className="control-card-title">
                <span>{faceDesc.fullLabel}</span>
                <span className="semantic-tag">{selectedFace}</span>
              </div>
              <div className="telemetry-kv-list">
                <div className="kv-row">
                  <span>Outward Unit Normal n̂:</span>
                  <code>
                    [{faceTransform.outwardNormal.x}, {faceTransform.outwardNormal.y},{' '}
                    {faceTransform.outwardNormal.z}]
                  </code>
                </div>
                <div className="kv-row">
                  <span>Local Face Center:</span>
                  <code>
                    ({faceTransform.center.x.toFixed(3)}, {faceTransform.center.y.toFixed(3)},{' '}
                    {faceTransform.center.z.toFixed(3)}) {lengthUnit}
                  </code>
                </div>
                <div className="kv-row">
                  <span>Surface Area:</span>
                  <code>
                    {faceTransform.area.toFixed(4)} {lengthUnit}²
                  </code>
                </div>
              </div>
            </div>

            <div className="control-card">
              <div className="form-field">
                <label htmlFor="bc-type-select">Boundary Condition Type</label>
                <select
                  id="bc-type-select"
                  data-testid="bc-type-select"
                  value={activeBc.type}
                  onChange={(e) =>
                    handleBcTypeChange(e.target.value as BoundaryConditionType)
                  }
                >
                  <option value="dirichlet">Dirichlet — Fixed Temperature (T = T₀)</option>
                  <option value="neumann">
                    Neumann — Outward Heat Flux (-k∇T·n̂ = q₀)
                  </option>
                  <option value="robin">
                    Robin — Convection (-k∇T·n̂ = h(T - T∞))
                  </option>
                  <option value="insulated">Insulated — Adiabatic Zero Flux (-k∇T·n̂ = 0)</option>
                </select>
              </div>

              <div className="equation-box">
                {activeBc.type === 'dirichlet' && (
                  <div>
                    <strong>Dirichlet Condition:</strong> <code>T = T₀</code> on{' '}
                    <code>Γ_{selectedFace}</code>
                  </div>
                )}
                {activeBc.type === 'neumann' && (
                  <div>
                    <strong>Neumann Outward Flux:</strong> <code>-k ∇T · n̂ = q₀</code> on{' '}
                    <code>Γ_{selectedFace}</code>
                  </div>
                )}
                {activeBc.type === 'robin' && (
                  <div>
                    <strong>Robin Convection Condition:</strong>{' '}
                    <code>-k ∇T · n̂ = h (T - T∞)</code> on <code>Γ_{selectedFace}</code>
                  </div>
                )}
                {activeBc.type === 'insulated' && (
                  <div>
                    <strong>Adiabatic / Insulated Condition:</strong>{' '}
                    <code>-k ∇T · n̂ = 0</code> on <code>Γ_{selectedFace}</code>
                  </div>
                )}
              </div>

              {activeBc.type === 'dirichlet' && (
                <div className="form-field">
                  <label htmlFor="bc-temperature-input">
                    Fixed Temperature T₀ ({tempUnit})
                  </label>
                  <input
                    id="bc-temperature-input"
                    data-testid="bc-temperature-input"
                    type="number"
                    step="5"
                    value={activeBc.temperature ?? ''}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value);
                      onUpdateFaceBC(selectedFace, {
                        temperature: Number.isFinite(val) ? val : null,
                      });
                    }}
                  />
                  <span className="field-hint">
                    Must be ≥ {tempUnit === 'K' ? '0 K' : '-273.15 °C'} (absolute zero).
                  </span>
                </div>
              )}

              {activeBc.type === 'neumann' && (
                <div className="form-field">
                  <label htmlFor="bc-heat-flux-input">
                    Outward Heat Flux q₀ ({model.units.heat_flux})
                  </label>
                  <input
                    id="bc-heat-flux-input"
                    data-testid="bc-heat-flux-input"
                    type="number"
                    step="50"
                    value={activeBc.heat_flux ?? ''}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value);
                      onUpdateFaceBC(selectedFace, {
                        heat_flux: Number.isFinite(val) ? val : null,
                      });
                    }}
                  />
                  <span className="field-hint">
                    q₀ &gt; 0: heat leaving domain (cooling); q₀ &lt; 0: heat entering domain
                    (heating).
                  </span>
                </div>
              )}

              {activeBc.type === 'robin' && (
                <div className="form-grid-2">
                  <div className="form-field">
                    <label htmlFor="bc-conv-coeff-input">
                      Convection Coeff h ({model.units.convection_coefficient})
                    </label>
                    <input
                      id="bc-conv-coeff-input"
                      data-testid="bc-conv-coeff-input"
                      type="number"
                      step="5"
                      min="0.001"
                      value={activeBc.convection_coefficient ?? ''}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        onUpdateFaceBC(selectedFace, {
                          convection_coefficient: Number.isFinite(val) ? val : null,
                        });
                      }}
                    />
                  </div>
                  <div className="form-field">
                    <label htmlFor="bc-ambient-temp-input">
                      Ambient Temp T∞ ({tempUnit})
                    </label>
                    <input
                      id="bc-ambient-temp-input"
                      data-testid="bc-ambient-temp-input"
                      type="number"
                      step="5"
                      value={activeBc.ambient_temperature ?? ''}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        onUpdateFaceBC(selectedFace, {
                          ambient_temperature: Number.isFinite(val) ? val : null,
                        });
                      }}
                    />
                  </div>
                </div>
              )}

              {activeBc.type === 'insulated' && (
                <p className="field-hint">
                  Perfect thermal insulation (zero normal temperature gradient across{' '}
                  <code>{selectedFace}</code>).
                </p>
              )}

              <div className="bc-utility-actions">
                <button
                  type="button"
                  className="secondary-action-btn"
                  onClick={() => onCopyBcToOppositeFace(selectedFace)}
                  title={`Copy ${selectedFace} boundary condition to opposite face ${oppositeFace}`}
                >
                  Copy to Opposite Face ({oppositeFace})
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: PHYSICS & MATERIAL */}
        {activeTab === 'physics' && (
          <div className="inspector-pane" data-testid="inspector-pane-physics">
            <div className="pane-header">
              <h3>Steady-State Heat Conduction</h3>
              <p className="pane-subtitle">
                Configure isotropic material thermal conductivity and volumetric heat generation.
              </p>
            </div>

            <div className="equation-box">
              <div>
                <strong>Governing Elliptic PDE:</strong> <code>-∇ · (k ∇T) = Q</code> in{' '}
                <code>Ω ⊂ ℝ³</code>
              </div>
            </div>

            <div className="control-card">
              <div className="control-card-title">Solid Domain Material</div>

              <div className="form-field">
                <label htmlFor="material-preset-select">Engineering Material Preset</label>
                <select
                  id="material-preset-select"
                  data-testid="material-preset-select"
                  value={model.material.preset}
                  onChange={(e) =>
                    onSelectMaterialPreset(e.target.value as MaterialPreset)
                  }
                >
                  {Object.values(MATERIAL_PRESET_LIBRARY).map((item) => (
                    <option key={item.preset} value={item.preset}>
                      {item.name} — k = {item.thermal_conductivity} W/(m·K)
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label htmlFor="material-name-input">Material Designation</label>
                <input
                  id="material-name-input"
                  type="text"
                  value={model.material.name}
                  onChange={(e) => onUpdateMaterial({ name: e.target.value })}
                />
              </div>

              <div className="form-field">
                <label htmlFor="thermal-conductivity-input">
                  Thermal Conductivity k ({model.units.thermal_conductivity})
                </label>
                <input
                  id="thermal-conductivity-input"
                  data-testid="thermal-conductivity-input"
                  type="number"
                  step="1"
                  min="0.001"
                  value={model.material.thermal_conductivity}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value);
                    onUpdateMaterial({
                      preset: 'custom',
                      thermal_conductivity: Number.isFinite(val) ? val : 0,
                    });
                  }}
                />
              </div>
            </div>

            <div className="control-card">
              <div className="control-card-title">Internal Heat Source</div>
              <div className="form-field">
                <label htmlFor="heat-source-input">
                  Volumetric Heat Generation Q ({model.units.heat_source})
                </label>
                <input
                  id="heat-source-input"
                  data-testid="heat-source-input"
                  type="number"
                  step="100"
                  value={model.physics.volumetric_heat_source}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value);
                    onUpdatePhysics({
                      volumetric_heat_source: Number.isFinite(val) ? val : 0,
                    });
                  }}
                />
              </div>
            </div>

            <div className="control-card">
              <div className="control-card-title">Project Notes &amp; Author</div>
              <div className="form-field">
                <label htmlFor="project-author-input">Author / Engineer</label>
                <input
                  id="project-author-input"
                  type="text"
                  value={model.metadata.author}
                  onChange={(e) => onUpdateMetadata({ author: e.target.value })}
                />
              </div>
              <div className="form-field">
                <label htmlFor="project-desc-input">Engineering Description</label>
                <textarea
                  id="project-desc-input"
                  rows={3}
                  value={model.metadata.description}
                  onChange={(e) => onUpdateMetadata({ description: e.target.value })}
                />
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: MESH CONFIGURATION */}
        {activeTab === 'mesh' && (
          <div className="inspector-pane" data-testid="inspector-pane-mesh">
            <div className="pane-header">
              <h3>Netgen/OpenCASCADE 3D Tetrahedral FEM Mesh</h3>
              <p className="pane-subtitle">
                Configure tetrahedral element size (h_max), H¹ polynomial order, and grid divisions.
              </p>
            </div>

            <div className="control-card">
              <div className="form-grid-2">
                <div className="form-field">
                  <label htmlFor="mesh-maxh-input">
                    Max Element Size h_max ({lengthUnit})
                  </label>
                  <input
                    id="mesh-maxh-input"
                    data-testid="mesh-maxh-input"
                    type="number"
                    step="0.05"
                    min="0.001"
                    placeholder={`Auto (${computedDefaultMaxH})`}
                    value={model.mesh.max_element_size ?? ''}
                    onChange={(e) => {
                      const raw = e.target.value;
                      if (!raw.trim()) {
                        onUpdateMesh({ max_element_size: null });
                        return;
                      }
                      const val = parseFloat(raw);
                      if (Number.isFinite(val) && val > 0) {
                        onUpdateMesh({ max_element_size: val });
                      }
                    }}
                  />
                </div>

                <div className="form-field">
                  <label htmlFor="mesh-poly-order-select">H¹ FEM Polynomial Order</label>
                  <select
                    id="mesh-poly-order-select"
                    value={model.mesh.polynomial_order ?? 1}
                    onChange={(e) =>
                      onUpdateMesh({
                        polynomial_order: parseInt(e.target.value, 10),
                      })
                    }
                  >
                    <option value={1}>Order 1 (Linear P1 Tetrahedra)</option>
                    <option value={2}>Order 2 (Quadratic P2 Tetrahedra)</option>
                    <option value={3}>Order 3 (Cubic P3 Tetrahedra)</option>
                  </select>
                </div>
              </div>

              <div className="form-field">
                <label htmlFor="mesh-element-type-select">Finite Element Topology</label>
                <select
                  id="mesh-element-type-select"
                  value={model.mesh.element_type}
                  onChange={(e) =>
                    onUpdateMesh({ element_type: e.target.value as ElementType })
                  }
                >
                  <option value="tetrahedral_4node">
                    Netgen/OCC 3D Tetrahedra (Unstructured FEM)
                  </option>
                  <option value="hexahedral_8node">
                    8-Node Trilinear Hexahedra (Structured Preview)
                  </option>
                </select>
              </div>

              <div className="control-card-title" style={{ marginTop: '0.5rem' }}>
                <span>Reference Grid Divisions (nx × ny × nz)</span>
              </div>

              <div className="mesh-preset-row">
                <button
                  type="button"
                  className="panel-mini-btn"
                  onClick={() =>
                    onUpdateMesh({
                      divisions: { nx: 6, ny: 6, nz: 6 },
                      max_element_size: Number(
                        (Math.max(
                          model.geometry.dimensions.length_x,
                          model.geometry.dimensions.length_y,
                          model.geometry.dimensions.length_z
                        ) / 4).toFixed(3)
                      ),
                    })
                  }
                >
                  Coarse
                </button>
                <button
                  type="button"
                  className="panel-mini-btn"
                  onClick={() =>
                    onUpdateMesh({
                      divisions: { nx: 12, ny: 12, nz: 12 },
                      max_element_size: Number(
                        (Math.max(
                          model.geometry.dimensions.length_x,
                          model.geometry.dimensions.length_y,
                          model.geometry.dimensions.length_z
                        ) / 7).toFixed(3)
                      ),
                    })
                  }
                >
                  Medium
                </button>
                <button
                  type="button"
                  className="panel-mini-btn"
                  onClick={() =>
                    onUpdateMesh({
                      divisions: { nx: 20, ny: 20, nz: 20 },
                      max_element_size: Number(
                        (Math.max(
                          model.geometry.dimensions.length_x,
                          model.geometry.dimensions.length_y,
                          model.geometry.dimensions.length_z
                        ) / 11).toFixed(3)
                      ),
                    })
                  }
                >
                  Fine
                </button>
              </div>

              <div className="form-grid-3">
                <div className="form-field">
                  <label htmlFor="mesh-nx-input">Divisions nx</label>
                  <input
                    id="mesh-nx-input"
                    type="number"
                    min="1"
                    max="200"
                    step="1"
                    value={model.mesh.divisions.nx}
                    onChange={(e) =>
                      onUpdateMesh({
                        divisions: {
                          ...model.mesh.divisions,
                          nx: Math.max(1, parseInt(e.target.value || '1', 10)),
                        },
                      })
                    }
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="mesh-ny-input">Divisions ny</label>
                  <input
                    id="mesh-ny-input"
                    type="number"
                    min="1"
                    max="200"
                    step="1"
                    value={model.mesh.divisions.ny}
                    onChange={(e) =>
                      onUpdateMesh({
                        divisions: {
                          ...model.mesh.divisions,
                          ny: Math.max(1, parseInt(e.target.value || '1', 10)),
                        },
                      })
                    }
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="mesh-nz-input">Divisions nz</label>
                  <input
                    id="mesh-nz-input"
                    type="number"
                    min="1"
                    max="200"
                    step="1"
                    value={model.mesh.divisions.nz}
                    onChange={(e) =>
                      onUpdateMesh({
                        divisions: {
                          ...model.mesh.divisions,
                          nz: Math.max(1, parseInt(e.target.value || '1', 10)),
                        },
                      })
                    }
                  />
                </div>
              </div>
            </div>

            <div className="control-card highlight-card">
              <div className="control-card-title">Discretization Pre-Check</div>
              <div className="telemetry-kv-list">
                <div className="kv-row">
                  <span>Target Tetrahedral Size h_max:</span>
                  <code>
                    {model.mesh.max_element_size ?? computedDefaultMaxH} {lengthUnit}
                  </code>
                </div>
                <div className="kv-row">
                  <span>H¹ Polynomial Order:</span>
                  <code>P{model.mesh.polynomial_order ?? 1}</code>
                </div>
                <div className="kv-row">
                  <span>Cell Aspect Ratio:</span>
                  <code
                    className={
                      validationReport.metrics.element_aspect_ratio > 5
                        ? 'text-warning'
                        : 'text-success'
                    }
                  >
                    {validationReport.metrics.element_aspect_ratio.toFixed(2)}
                  </code>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: CANONICAL JSON SCHEMA */}
        {activeTab === 'json' && (
          <div className="inspector-pane" data-testid="inspector-pane-json">
            <div className="pane-header">
              <h3>Canonical Model JSON (v{model.schema_version})</h3>
              <p className="pane-subtitle">
                Shared frontend/backend schema for persistence and NGSolve FEM execution.
              </p>
            </div>

            <div className="json-actions-row">
              <button
                type="button"
                className="secondary-action-btn"
                onClick={() => void handleCopyJson()}
              >
                {copiedJson ? '✓ Copied to Clipboard' : 'Copy Canonical JSON'}
              </button>
              <button
                type="button"
                className="secondary-action-btn"
                onClick={onTriggerBackendValidation}
              >
                Verify with Backend API
              </button>
            </div>

            <pre className="canonical-json-viewer" data-testid="canonical-json-preview">
              {JSON.stringify(model, null, 2)}
            </pre>
          </div>
        )}

        {/* Validation Diagnostics Section */}
        <div className="validation-summary-card">
          <div className="control-card-title">
            <span>Real-Time Model Diagnostics</span>
            <span
              className={`diag-pill ${
                validationReport.valid ? 'diag-valid' : 'diag-invalid'
              }`}
            >
              {validationReport.valid ? 'VALID MODEL' : 'INVALID'}
            </span>
          </div>

          {validationReport.issues.length === 0 ? (
            <p className="diag-ok-msg">
              ✓ Geometry, material, steady-state heat conduction physics, all 6 semantic boundaries,
              and mesh parameters pass validation.
            </p>
          ) : (
            <ul className="diag-issue-list">
              {validationReport.issues.map((issue, idx) => (
                <li key={idx} className={`diag-issue-item severity-${issue.severity}`}>
                  <span className="issue-badge">{issue.severity.toUpperCase()}</span>
                  <span className="issue-text">{issue.message}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </aside>
  );
};
