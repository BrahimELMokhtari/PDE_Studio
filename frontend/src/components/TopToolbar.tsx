/**
 * Top CAD/CAE Application Toolbar (Phase 2)
 *
 * Includes:
 * - Application Title & Phase 2 FEM Solver Badge
 * - Inline Project Name Editor & Dirty State Indicator
 * - Preset Template Selector
 * - New, Open, Save, Export JSON, Import JSON controls
 * - Viewport Reset View shortcut
 * - Run Simulation & Solver Dashboard Button (with live status indicator)
 */

import React, { useRef } from 'react';
import { JobStatus } from '../types/model';
import { ProjectTemplateId } from '../utils/modelValidation';

export interface TopToolbarProps {
  projectId: string | null;
  projectName: string;
  isDirty: boolean;
  isSaving: boolean;
  activeJobStatus?: JobStatus | null;
  activeJobProgress?: number;
  onProjectNameChange: (newName: string) => void;
  onNewProject: (templateId?: ProjectTemplateId) => void;
  onOpenProjectModal: () => void;
  onSaveProject: () => void;
  onExportJson: () => void;
  onImportJsonFile: (file: File) => void;
  onResetView: () => void;
  onRunSimulation: () => void;
  onOpenSolverModal: () => void;
}

export const TopToolbar: React.FC<TopToolbarProps> = ({
  projectId,
  projectName,
  isDirty,
  isSaving,
  activeJobStatus,
  activeJobProgress = 0,
  onProjectNameChange,
  onNewProject,
  onOpenProjectModal,
  onSaveProject,
  onExportJson,
  onImportJsonFile,
  onResetView,
  onRunSimulation,
  onOpenSolverModal,
}) => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onImportJsonFile(file);
      e.target.value = '';
    }
  };

  const isRunningJob = activeJobStatus === 'queued' || activeJobStatus === 'running';

  return (
    <header className="top-toolbar" role="banner">
      <div className="toolbar-brand">
        <div className="brand-logo" aria-hidden="true">
          <span>∇²</span>
        </div>
        <div className="brand-titles">
          <div className="brand-name-row">
            <span className="brand-title">PDE Simulation Studio</span>
            <span className="phase-badge">PHASE 2 • NGSOLVE 3D FEM</span>
          </div>
          <span className="brand-subtitle">
            3D Parametric CAD &amp; Steady-State Thermal FEM Solver
          </span>
        </div>
      </div>

      {/* Active Project Name Input */}
      <div className="toolbar-project-meta">
        <label htmlFor="project-name-input" className="sr-only">
          Project Name
        </label>
        <input
          id="project-name-input"
          type="text"
          className="project-name-input"
          value={projectName}
          onChange={(e) => onProjectNameChange(e.target.value)}
          placeholder="Enter project name..."
          aria-label="Project Name"
        />
        <span
          className={`project-save-state ${isDirty ? 'state-unsaved' : 'state-saved'}`}
          title={
            projectId
              ? `Project ID: ${projectId}`
              : 'Unsaved local draft (Click Save to persist to database)'
          }
        >
          {isDirty ? '● Unsaved Changes' : projectId ? '✓ Saved' : 'Draft'}
        </span>
      </div>

      {/* Project & File Operations */}
      <div className="toolbar-actions">
        <div className="toolbar-group">
          <select
            aria-label="Load Engineering Template"
            className="toolbar-select"
            defaultValue=""
            onChange={(e) => {
              const val = e.target.value as ProjectTemplateId | '';
              if (val) {
                onNewProject(val);
                e.target.value = '';
              }
            }}
          >
            <option value="" disabled>
              + New from Template...
            </option>
            <option value="copper_block">Copper Thermal Block (Default)</option>
            <option value="al_heat_spreader">Aluminum 6061 Heat Spreader</option>
            <option value="silicon_die">Silicon Power Die (mm / °C)</option>
          </select>

          <button
            type="button"
            className="toolbar-btn"
            onClick={() => onNewProject('copper_block')}
            title="Create a fresh default project"
          >
            New
          </button>

          <button
            type="button"
            className="toolbar-btn"
            onClick={onOpenProjectModal}
            title="Open a saved project from the SQLite database"
          >
            Open...
          </button>

          <button
            type="button"
            className="toolbar-btn toolbar-btn-primary"
            onClick={onSaveProject}
            disabled={isSaving}
            title="Save project to backend database"
          >
            {isSaving ? 'Saving...' : 'Save'}
          </button>
        </div>

        <div className="toolbar-divider" />

        <div className="toolbar-group">
          <button
            type="button"
            className="toolbar-btn"
            onClick={onExportJson}
            title="Export canonical v1.0.0 JSON model file"
          >
            Export JSON
          </button>

          <button
            type="button"
            className="toolbar-btn"
            onClick={() => fileInputRef.current?.click()}
            title="Import canonical v1.0.0 JSON model file"
          >
            Import JSON
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,application/json"
            style={{ display: 'none' }}
            onChange={handleFileChange}
            data-testid="import-json-file-input"
          />

          <button
            type="button"
            className="toolbar-btn"
            onClick={onResetView}
            title="Reset 3D camera to isometric view"
          >
            Reset View
          </button>
        </div>

        <div className="toolbar-divider" />

        {/* Phase 2 Real NGSolve FEM Simulation Execution & Results Button */}
        <div className="toolbar-group">
          <button
            type="button"
            data-testid="run-simulation-btn"
            className="toolbar-btn toolbar-btn-run"
            onClick={onRunSimulation}
            disabled={isRunningJob}
            title="Execute 3D Tetrahedral FEM Steady-State Heat Conduction Simulation (NGSolve + Redis/RQ)"
          >
            <span>
              {isRunningJob
                ? `⏳ Solving (${activeJobProgress}%)`
                : '▶ Run Simulation'}
            </span>
          </button>

          <button
            type="button"
            data-testid="open-solver-dashboard-btn"
            className="toolbar-btn toolbar-btn-solver"
            onClick={onOpenSolverModal}
            title="Open Simulation Results, Logs, Reproducible Python Script & ZIP Package"
          >
            <span>⚡ Results &amp; Script</span>
            {activeJobStatus === 'completed' && (
              <span className="solver-phase-tag tag-ok">✓ Ready</span>
            )}
          </button>
        </div>
      </div>
    </header>
  );
};
