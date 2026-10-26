/**
 * Left Geometry & Model Tree Panel
 *
 * Provides:
 * 1. Hierarchical CAD/CAE Model Tree (Geometry, 6 Semantic Faces with BC badges, Material, Physics, Mesh)
 * 2. Parametric Rectangular Cuboid Editor (Dimensions X/Y/Z, Position X/Y/Z, Euler Rotation X/Y/Z, Units)
 */

import React from 'react';
import {
  ALL_FACE_IDS,
  CanonicalSimulationModel,
  CuboidDimensions,
  FaceId,
  LengthUnit,
  TemperatureUnit,
  Vector3D,
} from '../types/model';
import { SEMANTIC_FACE_DESCRIPTORS } from '../utils/semanticFaces';

export interface LeftGeometryPanelProps {
  model: CanonicalSimulationModel;
  selectedFace: FaceId;
  hoveredFace: FaceId | null;
  onSelectFace: (faceId: FaceId) => void;
  onHoverFace: (faceId: FaceId | null) => void;
  onUpdateDimensions: (dims: Partial<CuboidDimensions>) => void;
  onUpdatePosition: (pos: Partial<Vector3D>) => void;
  onUpdateRotation: (rot: Partial<Vector3D>) => void;
  onUpdateUnits: (units: { length?: LengthUnit; temperature?: TemperatureUnit }) => void;
  onResetGeometry: () => void;
  onSelectInspectorTab: (tab: 'boundaries' | 'physics' | 'mesh' | 'json') => void;
}

export const LeftGeometryPanel: React.FC<LeftGeometryPanelProps> = ({
  model,
  selectedFace,
  hoveredFace,
  onSelectFace,
  onHoverFace,
  onUpdateDimensions,
  onUpdatePosition,
  onUpdateRotation,
  onUpdateUnits,
  onResetGeometry,
  onSelectInspectorTab,
}) => {
  const { dimensions, position, rotation_deg } = model.geometry;
  const lengthUnit = model.units.length;
  const tempUnit = model.units.temperature;

  const parseNumericInput = (raw: string, fallback: number): number => {
    const parsed = parseFloat(raw);
    return Number.isFinite(parsed) ? parsed : fallback;
  };

  return (
    <aside className="left-panel" aria-label="Geometry and Model Tree Panel">
      {/* Section 1: Parametric Rectangular Cuboid Editor */}
      <div className="panel-section">
        <div className="panel-section-header">
          <h2>Parametric Geometry</h2>
          <button
            type="button"
            className="panel-mini-btn"
            onClick={onResetGeometry}
            title="Reset cuboid dimensions, position, and rotation to defaults"
          >
            Reset Cuboid
          </button>
        </div>

        {/* Unit System Controls */}
        <div className="control-card">
          <div className="control-card-title">Unit System</div>
          <div className="form-grid-2">
            <div className="form-field">
              <label htmlFor="unit-length-select">Length Unit</label>
              <select
                id="unit-length-select"
                value={lengthUnit}
                onChange={(e) => onUpdateUnits({ length: e.target.value as LengthUnit })}
              >
                <option value="m">Meters (m)</option>
                <option value="cm">Centimeters (cm)</option>
                <option value="mm">Millimeters (mm)</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="unit-temp-select">Temperature Unit</label>
              <select
                id="unit-temp-select"
                value={tempUnit}
                onChange={(e) =>
                  onUpdateUnits({ temperature: e.target.value as TemperatureUnit })
                }
              >
                <option value="K">Kelvin (K)</option>
                <option value="C">Celsius (°C)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Dimensions (X, Y, Z) */}
        <div className="control-card">
          <div className="control-card-title">
            <span>Cuboid Dimensions ({lengthUnit})</span>
            <span className="card-subtle-tag">rectangular_cuboid</span>
          </div>
          <div className="form-grid-3">
            <div className="form-field">
              <label htmlFor="dim-x-input">
                <span className="axis-dot axis-x-bg" /> Width Lx
              </label>
              <input
                id="dim-x-input"
                type="number"
                step="0.1"
                min="0.001"
                value={dimensions.length_x}
                onChange={(e) =>
                  onUpdateDimensions({
                    length_x: parseNumericInput(e.target.value, dimensions.length_x),
                  })
                }
              />
            </div>

            <div className="form-field">
              <label htmlFor="dim-y-input">
                <span className="axis-dot axis-y-bg" /> Height Ly
              </label>
              <input
                id="dim-y-input"
                type="number"
                step="0.1"
                min="0.001"
                value={dimensions.length_y}
                onChange={(e) =>
                  onUpdateDimensions({
                    length_y: parseNumericInput(e.target.value, dimensions.length_y),
                  })
                }
              />
            </div>

            <div className="form-field">
              <label htmlFor="dim-z-input">
                <span className="axis-dot axis-z-bg" /> Depth Lz
              </label>
              <input
                id="dim-z-input"
                type="number"
                step="0.1"
                min="0.001"
                value={dimensions.length_z}
                onChange={(e) =>
                  onUpdateDimensions({
                    length_z: parseNumericInput(e.target.value, dimensions.length_z),
                  })
                }
              />
            </div>
          </div>
        </div>

        {/* Origin / Center Position (X, Y, Z) */}
        <div className="control-card">
          <div className="control-card-title">
            <span>Center Position ({lengthUnit})</span>
            <button
              type="button"
              className="inline-reset-link"
              onClick={() => onUpdatePosition({ x: 0, y: 0, z: 0 })}
            >
              Zero
            </button>
          </div>
          <div className="form-grid-3">
            <div className="form-field">
              <label htmlFor="pos-x-input">Center X</label>
              <input
                id="pos-x-input"
                type="number"
                step="0.1"
                value={position.x}
                onChange={(e) =>
                  onUpdatePosition({ x: parseNumericInput(e.target.value, position.x) })
                }
              />
            </div>
            <div className="form-field">
              <label htmlFor="pos-y-input">Center Y</label>
              <input
                id="pos-y-input"
                type="number"
                step="0.1"
                value={position.y}
                onChange={(e) =>
                  onUpdatePosition({ y: parseNumericInput(e.target.value, position.y) })
                }
              />
            </div>
            <div className="form-field">
              <label htmlFor="pos-z-input">Center Z</label>
              <input
                id="pos-z-input"
                type="number"
                step="0.1"
                value={position.z}
                onChange={(e) =>
                  onUpdatePosition({ z: parseNumericInput(e.target.value, position.z) })
                }
              />
            </div>
          </div>
        </div>

        {/* Euler Orientation / Rotation (deg) */}
        <div className="control-card">
          <div className="control-card-title">
            <span>Orientation Rotation (°)</span>
            <button
              type="button"
              className="inline-reset-link"
              onClick={() => onUpdateRotation({ x: 0, y: 0, z: 0 })}
            >
              0° All
            </button>
          </div>
          <div className="form-grid-3">
            <div className="form-field">
              <label htmlFor="rot-x-input">Rot X (°)</label>
              <input
                id="rot-x-input"
                type="number"
                step="5"
                min="-360"
                max="360"
                value={rotation_deg.x}
                onChange={(e) =>
                  onUpdateRotation({ x: parseNumericInput(e.target.value, rotation_deg.x) })
                }
              />
            </div>
            <div className="form-field">
              <label htmlFor="rot-y-input">Rot Y (°)</label>
              <input
                id="rot-y-input"
                type="number"
                step="5"
                min="-360"
                max="360"
                value={rotation_deg.y}
                onChange={(e) =>
                  onUpdateRotation({ y: parseNumericInput(e.target.value, rotation_deg.y) })
                }
              />
            </div>
            <div className="form-field">
              <label htmlFor="rot-z-input">Rot Z (°)</label>
              <input
                id="rot-z-input"
                type="number"
                step="5"
                min="-360"
                max="360"
                value={rotation_deg.z}
                onChange={(e) =>
                  onUpdateRotation({ z: parseNumericInput(e.target.value, rotation_deg.z) })
                }
              />
            </div>
          </div>
        </div>
      </div>

      {/* Section 2: Semantic Boundary Tree & Model Hierarchy */}
      <div className="panel-section">
        <div className="panel-section-header">
          <h2>Semantic Boundary Faces</h2>
          <span className="section-pill">6 Faces</span>
        </div>

        <ul className="semantic-face-list" role="listbox" aria-label="Semantic Cuboid Faces">
          {ALL_FACE_IDS.map((faceId) => {
            const desc = SEMANTIC_FACE_DESCRIPTORS[faceId];
            const bc = model.boundary_conditions[faceId];
            const isSelected = selectedFace === faceId;
            const isHovered = hoveredFace === faceId;

            let valueSummary = 'q = 0';
            if (bc.type === 'dirichlet') {
              valueSummary = `T = ${bc.temperature ?? '—'} ${tempUnit}`;
            } else if (bc.type === 'neumann') {
              valueSummary = `q = ${bc.heat_flux ?? '—'} W/m²`;
            } else if (bc.type === 'robin') {
              valueSummary = `h=${bc.convection_coefficient ?? '—'}, T∞=${
                bc.ambient_temperature ?? '—'
              }`;
            }

            return (
              <li key={faceId}>
                <button
                  type="button"
                  data-testid={`tree-face-${faceId}`}
                  className={`semantic-face-item ${isSelected ? 'selected' : ''} ${
                    isHovered ? 'hovered' : ''
                  }`}
                  onClick={() => {
                    onSelectFace(faceId);
                    onSelectInspectorTab('boundaries');
                  }}
                  onMouseEnter={() => onHoverFace(faceId)}
                  onMouseLeave={() => onHoverFace(null)}
                >
                  <div className="face-item-left">
                    <span className="face-id-code">{faceId}</span>
                    <span className="face-short-desc">{desc.shortLabel}</span>
                  </div>
                  <div className="face-item-right">
                    <span className={`bc-badge bc-${bc.type}`}>{bc.type}</span>
                    <span className="face-bc-val">{valueSummary}</span>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>

        {/* Quick Model Tree Navigation Shortcuts */}
        <div className="model-tree-shortcuts">
          <button
            type="button"
            className="tree-shortcut-row"
            onClick={() => onSelectInspectorTab('physics')}
          >
            <span className="tree-node-title">Material: {model.material.name}</span>
            <span className="tree-node-meta">k = {model.material.thermal_conductivity} W/(m·K)</span>
          </button>
          <button
            type="button"
            className="tree-shortcut-row"
            onClick={() => onSelectInspectorTab('physics')}
          >
            <span className="tree-node-title">Physics: Steady Heat Conduction</span>
            <span className="tree-node-meta">Q = {model.physics.volumetric_heat_source} W/m³</span>
          </button>
          <button
            type="button"
            className="tree-shortcut-row"
            onClick={() => onSelectInspectorTab('mesh')}
          >
            <span className="tree-node-title">Mesh: {model.mesh.element_type}</span>
            <span className="tree-node-meta">
              {model.mesh.divisions.nx} × {model.mesh.divisions.ny} × {model.mesh.divisions.nz}
            </span>
          </button>
        </div>
      </div>
    </aside>
  );
};
