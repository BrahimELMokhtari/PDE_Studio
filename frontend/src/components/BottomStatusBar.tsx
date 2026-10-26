/**
 * Bottom Engineering Status Bar (Phase 2)
 */

import React from 'react';
import {
  CanonicalSimulationModel,
  FaceId,
  SimulationJobResponse,
  ValidationReport,
} from '../types/model';

export interface BottomStatusBarProps {
  model: CanonicalSimulationModel;
  validationReport: ValidationReport;
  selectedFace: FaceId;
  hoveredFace: FaceId | null;
  backendConnected: boolean | null;
  activeJob?: SimulationJobResponse | null;
  statusMessage: string;
}

export const BottomStatusBar: React.FC<BottomStatusBarProps> = ({
  model,
  validationReport,
  selectedFace,
  hoveredFace,
  backendConnected,
  activeJob,
  statusMessage,
}) => {
  const errorCount = validationReport.issues.filter((i) => i.severity === 'error').length;
  const warningCount = validationReport.issues.filter((i) => i.severity === 'warning').length;
  const unit = model.units.length;

  return (
    <footer className="bottom-status-bar" role="contentinfo">
      <div className="status-left">
        <span
          className={`status-indicator ${
            backendConnected === true
              ? 'status-online'
              : backendConnected === false
              ? 'status-offline'
              : 'status-checking'
          }`}
          title="FastAPI Backend, SQLite & NGSolve Solver Status"
        >
          ●{' '}
          {backendConnected === true
            ? 'API & NGSolve Ready'
            : backendConnected === false
            ? 'API Offline (Local Mode)'
            : 'Checking API...'}
        </span>

        <span className="status-divider">|</span>

        <span
          className={`status-validation ${
            errorCount > 0
              ? 'val-error'
              : warningCount > 0
              ? 'val-warning'
              : 'val-ok'
          }`}
        >
          {errorCount > 0
            ? `✗ ${errorCount} Validation Error(s)`
            : warningCount > 0
            ? `⚠ Valid (${warningCount} Warning)`
            : '✓ Model Valid'}
        </span>

        <span className="status-divider">|</span>

        <span className="status-message" data-testid="status-bar-message">
          {statusMessage}
        </span>
      </div>

      <div className="status-right">
        <span className="status-telemetry">
          Face: <strong>{selectedFace}</strong>
          {hoveredFace ? ` (Hover: ${hoveredFace})` : ''}
        </span>

        <span className="status-divider">|</span>

        <span className="status-telemetry">
          Vol: <strong>{validationReport.metrics.volume}</strong> {unit}³
        </span>

        {activeJob?.result ? (
          <>
            <span className="status-divider">|</span>
            <span className="status-telemetry">
              FEM:{' '}
              <strong>
                T=[{activeJob.result.min_temperature_display.toFixed(1)}..
                {activeJob.result.max_temperature_display.toFixed(1)}{' '}
                {activeJob.result.temperature_unit}] ({activeJob.result.mesh_tetrahedra} tets)
              </strong>
            </span>
          </>
        ) : null}

        <span className="status-divider">|</span>

        <span className="status-schema-badge">
          Schema v{model.schema_version} • NGSolve 3D FEM + Redis/RQ
        </span>
      </div>
    </footer>
  );
};
