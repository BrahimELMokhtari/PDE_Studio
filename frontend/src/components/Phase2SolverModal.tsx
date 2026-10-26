/**
 * Phase 2 & 3 Simulation Execution, Scientific Post-Processing Dashboard,
 * VTK/VTU & CSV Exports, Job History, Account Quotas & Reproducible Python Script Modal
 *
 * Displays:
 * - Asynchronous RQ Job Status (queued, running, completed, failed), Progress Bar, and Real-Time Logs
 * - 3D NGSolve FEM Numerical Results (T_min, T_max, T_mean, Tetrahedra, DOFs, Energy Balance)
 * - Linear Solver Convergence Diagnostics (||K u - f||_2, Relative Residual, Stage Timings)
 * - 3D Tetrahedral Mesh Quality Statistics (Min/Max/Mean Edge Length, Aspect Ratio, Artifact Storage Size)
 * - Direct VTK/VTU (solution.vtu), Nodal CSV (nodal_results.csv), Boundary CSV (boundary_summary.csv),
 *   simulation.py, model.json, and .zip Package Downloads
 * - Job History & Account Quotas Tab (Browse past simulation runs, load results into 3D viewport, delete jobs, inspect storage quotas)
 */

import React, { useCallback, useEffect, useState } from 'react';
import { apiClient } from '../services/api';
import {
  ALL_FACE_IDS,
  CanonicalSimulationModel,
  SimulationJobResponse,
  UserQuotaSummaryResponse,
  ValidationReport,
} from '../types/model';

export interface Phase2SolverModalProps {
  isOpen: boolean;
  model: CanonicalSimulationModel;
  validationReport: ValidationReport;
  activeJob: SimulationJobResponse | null;
  isSubmitting: boolean;
  onClose: () => void;
  onRunSimulation: () => void;
  onDownloadPackage: () => void;
  onExportJson: () => void;
  onJobDeleted?: (jobId: string) => void;
  onSelectHistoricalJob?: (job: SimulationJobResponse) => void;
}

function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export const Phase2SolverModal: React.FC<Phase2SolverModalProps> = ({
  isOpen,
  model,
  validationReport,
  activeJob,
  isSubmitting,
  onClose,
  onRunSimulation,
  onDownloadPackage,
  onExportJson,
  onJobDeleted,
  onSelectHistoricalJob,
}) => {
  const [modalTab, setModalTab] = useState<'results' | 'script' | 'logs' | 'history'>('results');
  const [axisChoice, setAxisChoice] = useState<'x' | 'y' | 'z'>('x');
  const [scriptText, setScriptText] = useState<string>('');
  const [scriptError, setScriptError] = useState<string | null>(null);
  const [isLoadingScript, setIsLoadingScript] = useState<boolean>(false);
  const [copiedScript, setCopiedScript] = useState<boolean>(false);
  const [exportStatusMsg, setExportStatusMsg] = useState<string | null>(null);

  // Phase 3 Job History & Quotas State
  const [jobHistory, setJobHistory] = useState<SimulationJobResponse[]>([]);
  const [quotas, setQuotas] = useState<UserQuotaSummaryResponse | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false);

  const refreshHistoryAndQuotas = useCallback(async () => {
    setIsLoadingHistory(true);
    try {
      const [jobsList, quotaSummary] = await Promise.all([
        apiClient.listSimulationJobs(25),
        apiClient.getUserQuotas(),
      ]);
      setJobHistory(Array.isArray(jobsList) ? jobsList : []);
      setQuotas(quotaSummary);
    } catch {
      // Ignore in mocked/offline environments
    } finally {
      setIsLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    if (!isOpen || modalTab !== 'script') return;
    let cancelled = false;
    setIsLoadingScript(true);
    setScriptError(null);
    apiClient
      .generateSimulationScript(model)
      .then((res) => {
        if (!cancelled) {
          setScriptText(res.script_content);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setScriptError(err instanceof Error ? err.message : 'Failed to generate script.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingScript(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, modalTab, model]);

  useEffect(() => {
    if (!isOpen || modalTab !== 'history') return;
    void refreshHistoryAndQuotas();
  }, [isOpen, modalTab, refreshHistoryAndQuotas]);

  if (!isOpen) return null;

  const result = activeJob?.result ?? null;
  const status = activeJob?.status ?? null;
  const isRunning = isSubmitting || status === 'queued' || status === 'running';
  const tempUnit = result?.temperature_unit ?? model.units.temperature;
  const lengthUnit = result?.length_unit ?? model.units.length;

  const profileSamples = result?.centerline_profiles?.[axisChoice] ?? [];

  const handleCopyScript = async () => {
    if (!scriptText) return;
    try {
      await navigator.clipboard.writeText(scriptText);
      setCopiedScript(true);
      setTimeout(() => setCopiedScript(false), 2000);
    } catch {
      // clipboard unavailable
    }
  };

  const handleDownloadPyScript = () => {
    if (!scriptText) return;
    const blob = new Blob([scriptText], { type: 'text/x-python' });
    triggerBlobDownload(blob, 'simulation.py');
  };

  const handleExportVtu = async () => {
    if (!activeJob) return;
    try {
      setExportStatusMsg('Downloading solution.vtu...');
      const blob = await apiClient.downloadVtuArtifact(activeJob.job_id);
      triggerBlobDownload(blob, `solution-${activeJob.job_id.slice(0, 8)}.vtu`);
      setExportStatusMsg('Exported VTK UnstructuredGrid (.vtu).');
    } catch (err) {
      setExportStatusMsg(err instanceof Error ? err.message : 'VTU export failed.');
    }
  };

  const handleExportNodalCsv = async () => {
    if (!activeJob) return;
    try {
      setExportStatusMsg('Downloading nodal_results.csv...');
      const blob = await apiClient.downloadNodalCsvArtifact(activeJob.job_id);
      triggerBlobDownload(blob, `nodal-results-${activeJob.job_id.slice(0, 8)}.csv`);
      setExportStatusMsg('Exported Nodal Temperature CSV.');
    } catch (err) {
      setExportStatusMsg(err instanceof Error ? err.message : 'Nodal CSV export failed.');
    }
  };

  const handleExportBoundaryCsv = async () => {
    if (!activeJob) return;
    try {
      setExportStatusMsg('Downloading boundary_summary.csv...');
      const blob = await apiClient.downloadBoundaryCsvArtifact(activeJob.job_id);
      triggerBlobDownload(blob, `boundary-summary-${activeJob.job_id.slice(0, 8)}.csv`);
      setExportStatusMsg('Exported Boundary Summary CSV.');
    } catch (err) {
      setExportStatusMsg(err instanceof Error ? err.message : 'Boundary CSV export failed.');
    }
  };

  const handleDeleteJob = async (targetJobId?: string) => {
    const jid = targetJobId ?? activeJob?.job_id;
    if (!jid) return;
    try {
      await apiClient.deleteSimulationJob(jid);
      setExportStatusMsg('Deleted job and purged stored artifacts.');
      onJobDeleted?.(jid);
      if (modalTab === 'history') {
        await refreshHistoryAndQuotas();
      }
    } catch (err) {
      setExportStatusMsg(err instanceof Error ? err.message : 'Failed to delete job.');
    }
  };

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="NGSolve 3D FEM Simulation Runner and Results"
    >
      <div className="modal-container modal-container-wide">
        <div className="modal-header">
          <div>
            <h2>NGSolve 3D Steady-State Heat Conduction Solver &amp; Post-Processor</h2>
            <p className="modal-subtitle">
              Equation: <code>-∇ · (k ∇T) = Q</code> • OpenCASCADE Tetrahedral FEM • VTK/VTU &amp;
              CSV Export • Durable Object Storage
            </p>
          </div>
          <div className="modal-header-actions">
            <button
              type="button"
              className="toolbar-btn toolbar-btn-run"
              onClick={onRunSimulation}
              disabled={isRunning}
            >
              {isRunning ? `⏳ Running (${activeJob?.progress_percent ?? 0}%)` : '▶ Run Simulation'}
            </button>
            <button
              type="button"
              className="toolbar-btn toolbar-btn-primary"
              onClick={onDownloadPackage}
              title="Download ZIP containing simulation.py, model.json, solution.vtu, CSVs, requirements.txt, and README.md"
            >
              ⬇ Download Package (.zip)
            </button>
            <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Close">
              ✕
            </button>
          </div>
        </div>

        {/* Job Progress & Status Bar */}
        {activeJob && (
          <div className={`job-status-banner job-banner-${activeJob.status}`}>
            <div className="job-status-top">
              <div>
                <span className={`job-state-pill state-${activeJob.status}`}>
                  {activeJob.status.toUpperCase()}
                </span>
                <strong style={{ marginLeft: '0.5rem' }}>{activeJob.current_stage}</strong>
              </div>
              <span className="job-id-tag">
                Job ID: <code>{activeJob.job_id.slice(0, 8)}</code> • Progress:{' '}
                <strong>{activeJob.progress_percent}%</strong>
              </span>
            </div>
            <div className="job-progress-track">
              <div
                className="job-progress-fill"
                style={{ width: `${activeJob.progress_percent}%` }}
              />
            </div>
            {activeJob.status === 'failed' && activeJob.error_message && (
              <div className="job-error-box" role="alert">
                <strong>{activeJob.error_type || 'SolverError'}:</strong>{' '}
                {activeJob.error_message}
              </div>
            )}
          </div>
        )}

        {/* Modal Tabs */}
        <div className="inspector-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={modalTab === 'results'}
            className={`inspector-tab ${modalTab === 'results' ? 'active' : ''}`}
            onClick={() => setModalTab('results')}
          >
            Numerical Results, Convergence &amp; Exports
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={modalTab === 'script'}
            className={`inspector-tab ${modalTab === 'script' ? 'active' : ''}`}
            onClick={() => setModalTab('script')}
          >
            Reproducible Python Script (simulation.py)
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={modalTab === 'logs'}
            className={`inspector-tab ${modalTab === 'logs' ? 'active' : ''}`}
            onClick={() => setModalTab('logs')}
          >
            RQ Worker Logs ({activeJob?.logs.length ?? 0})
          </button>
          <button
            type="button"
            role="tab"
            data-testid="solver-history-tab-btn"
            aria-selected={modalTab === 'history'}
            className={`inspector-tab ${modalTab === 'history' ? 'active' : ''}`}
            onClick={() => setModalTab('history')}
          >
            Job History &amp; Quotas
          </button>
        </div>

        <div className="modal-body">
          {modalTab === 'results' && (
            <>
              {!result ? (
                <div className="modal-empty-state">
                  <p className="empty-title">
                    {isRunning
                      ? 'Solving 3D Tetrahedral FEM System...'
                      : 'No Simulation Results Yet'}
                  </p>
                  <p className="empty-desc">
                    Click <strong>▶ Run Simulation</strong> to generate the 3D Netgen/OpenCASCADE
                    tetrahedral mesh, assemble the H¹ stiffness matrix for{' '}
                    <code>-∇ · (k ∇T) = Q</code>, and solve for the 3D temperature distribution.
                  </p>
                  {!validationReport.valid && (
                    <p className="text-warning" style={{ marginTop: '0.5rem' }}>
                      Note: Please resolve model validation errors before running the solver.
                    </p>
                  )}
                </div>
              ) : (
                <div className="solver-results-dashboard" data-testid="solver-results-dashboard">
                  {/* Scientific Artifact Export Toolbar */}
                  <div className="control-card highlight-card">
                    <div className="control-card-title">
                      <span>Scientific Data Exports (ParaView VTK/VTU, CSV &amp; Artifacts)</span>
                      {exportStatusMsg && (
                        <span className="semantic-tag">{exportStatusMsg}</span>
                      )}
                    </div>
                    <div className="json-actions-row" style={{ flexWrap: 'wrap', gap: '0.5rem' }}>
                      <button
                        type="button"
                        data-testid="export-vtu-btn"
                        className="secondary-action-btn"
                        onClick={() => void handleExportVtu()}
                      >
                        ⬇ Export VTK/VTU (solution.vtu)
                      </button>
                      <button
                        type="button"
                        data-testid="export-nodal-csv-btn"
                        className="secondary-action-btn"
                        onClick={() => void handleExportNodalCsv()}
                      >
                        ⬇ Export Nodal CSV (nodal_results.csv)
                      </button>
                      <button
                        type="button"
                        data-testid="export-boundary-csv-btn"
                        className="secondary-action-btn"
                        onClick={() => void handleExportBoundaryCsv()}
                      >
                        ⬇ Export Boundary CSV (boundary_summary.csv)
                      </button>
                      <button
                        type="button"
                        className="secondary-action-btn"
                        onClick={onDownloadPackage}
                      >
                        ⬇ Full Package (.zip)
                      </button>
                      <button
                        type="button"
                        className="secondary-action-btn"
                        onClick={onExportJson}
                      >
                        ⬇ Export model.json
                      </button>
                      {activeJob && (
                        <button
                          type="button"
                          data-testid="delete-job-btn"
                          className="secondary-action-btn"
                          style={{ marginLeft: 'auto', color: '#f87171' }}
                          onClick={() => void handleDeleteJob()}
                        >
                          🗑 Delete Job &amp; Artifacts
                        </button>
                      )}
                    </div>
                  </div>

                  {/* KPI Summary Cards */}
                  <div className="kpi-grid-4">
                    <div className="kpi-card">
                      <span className="kpi-label">Min Temperature</span>
                      <strong className="kpi-value text-cool">
                        {result.min_temperature_display.toFixed(2)} {tempUnit}
                      </strong>
                      <span className="kpi-sub">{result.min_temperature_k.toFixed(2)} K</span>
                    </div>

                    <div className="kpi-card">
                      <span className="kpi-label">Max Temperature</span>
                      <strong className="kpi-value text-warm">
                        {result.max_temperature_display.toFixed(2)} {tempUnit}
                      </strong>
                      <span className="kpi-sub">{result.max_temperature_k.toFixed(2)} K</span>
                    </div>

                    <div className="kpi-card">
                      <span className="kpi-label">Mean Domain Temp</span>
                      <strong className="kpi-value">
                        {result.mean_temperature_display.toFixed(2)} {tempUnit}
                      </strong>
                      <span className="kpi-sub">{result.mean_temperature_k.toFixed(2)} K</span>
                    </div>

                    <div className="kpi-card">
                      <span className="kpi-label">3D Tetrahedral Mesh</span>
                      <strong className="kpi-value">
                        {result.mesh_tetrahedra.toLocaleString()} tets
                      </strong>
                      <span className="kpi-sub">
                        {result.total_dofs.toLocaleString()} DOFs (P{result.polynomial_order}) •{' '}
                        {result.solve_wall_time_seconds.toFixed(2)}s
                      </span>
                    </div>
                  </div>

                  {/* Convergence, Residual & Mesh Quality Diagnostics */}
                  <div className="control-card">
                    <div className="control-card-title">
                      <span>Convergence, Linear Solver Residual &amp; 3D Mesh Statistics</span>
                      <span className="semantic-tag">
                        {result.convergence?.converged !== false ? '✓ CONVERGED' : '⚠ CHECK RESIDUAL'}
                      </span>
                    </div>
                    <div className="form-grid-3">
                      <div>
                        <span className="hud-meta-key">Solver Method:</span>{' '}
                        <code>
                          {result.convergence?.solver_method ?? 'Sparse Cholesky Direct (SPD)'}
                        </code>
                      </div>
                      <div>
                        <span className="hud-meta-key">Relative Residual ||Ku-f||/||f||:</span>{' '}
                        <code>
                          {(result.convergence?.relative_residual_norm ?? 0).toExponential(2)}
                        </code>
                      </div>
                      <div>
                        <span className="hud-meta-key">Stage Timings (Mesh / Solve):</span>{' '}
                        <code>
                          {(result.convergence?.geometry_meshing_time_s ?? 0).toFixed(3)}s /{' '}
                          {(result.convergence?.solve_time_s ?? 0).toFixed(3)}s
                        </code>
                      </div>
                      <div>
                        <span className="hud-meta-key">Mean Edge Length (m):</span>{' '}
                        <code>{(result.mesh_quality?.mean_edge_length_m ?? 0).toFixed(4)} m</code>
                      </div>
                      <div>
                        <span className="hud-meta-key">Mean Surface Aspect Ratio:</span>{' '}
                        <code>{(result.mesh_quality?.mean_aspect_ratio ?? 1.0).toFixed(2)}</code>
                      </div>
                      <div>
                        <span className="hud-meta-key">Stored Artifacts Size:</span>{' '}
                        <code>
                          {((result.artifacts?.total_artifact_bytes ?? 0) / 1024).toFixed(1)} KB
                        </code>
                      </div>
                    </div>
                  </div>

                  {/* Energy Balance & Flux Bar */}
                  <div className="control-card">
                    <div className="control-card-title">
                      <span>Global Thermal Energy Conservation &amp; Flux</span>
                      <span className="semantic-tag">{result.solver_backend}</span>
                    </div>
                    <div className="form-grid-3">
                      <div>
                        <span className="hud-meta-key">Internal Heat Gen (∫Q dΩ):</span>{' '}
                        <code>{result.total_internal_heat_generation_w.toFixed(3)} W</code>
                      </div>
                      <div>
                        <span className="hud-meta-key">Net Outward Boundary Flux:</span>{' '}
                        <code>{result.net_boundary_heat_loss_w.toFixed(3)} W</code>
                      </div>
                      <div>
                        <span className="hud-meta-key">RMS Heat Flux |q|:</span>{' '}
                        <code>{result.max_heat_flux_w_m2.toFixed(2)} W/m²</code>
                      </div>
                    </div>
                  </div>

                  {/* Semantic Boundary Face Results Table */}
                  <div className="control-card">
                    <div className="control-card-title">
                      <span>Semantic Boundary Face Summary (X_MIN .. Z_MAX)</span>
                    </div>
                    <div className="table-scroll-wrapper">
                      <table className="results-table">
                        <thead>
                          <tr>
                            <th>Face ID</th>
                            <th>BC Type</th>
                            <th>Area (m²)</th>
                            <th>Min T ({tempUnit})</th>
                            <th>Mean T ({tempUnit})</th>
                            <th>Max T ({tempUnit})</th>
                            <th>Outward Heat Rate (W)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {ALL_FACE_IDS.map((fid) => {
                            const bstat = result.boundary_stats[fid];
                            if (!bstat) return null;
                            return (
                              <tr key={fid}>
                                <td>
                                  <code>{fid}</code>
                                </td>
                                <td>
                                  <span className={`bc-badge bc-${bstat.bc_type}`}>
                                    {bstat.bc_type}
                                  </span>
                                </td>
                                <td>{bstat.area_m2.toFixed(4)}</td>
                                <td>{bstat.min_temperature_display.toFixed(2)}</td>
                                <td>
                                  <strong>{bstat.mean_temperature_display.toFixed(2)}</strong>
                                </td>
                                <td>{bstat.max_temperature_display.toFixed(2)}</td>
                                <td>
                                  <code>
                                    {bstat.net_outward_heat_rate_w >= 0 ? '+' : ''}
                                    {bstat.net_outward_heat_rate_w.toFixed(2)} W
                                  </code>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* 1D Centerline Temperature Profile Plot */}
                  <div className="control-card">
                    <div className="control-card-title">
                      <span>
                        1D Centerline Temperature Profile along {axisChoice.toUpperCase()}-Axis
                      </span>
                      <div className="axis-toggle-group">
                        {(['x', 'y', 'z'] as const).map((ax) => (
                          <button
                            key={ax}
                            type="button"
                            className={`panel-mini-btn ${axisChoice === ax ? 'active' : ''}`}
                            onClick={() => setAxisChoice(ax)}
                          >
                            {ax.toUpperCase()}-Axis
                          </button>
                        ))}
                      </div>
                    </div>

                    {profileSamples.length > 1 && (
                      <div className="profile-chart-box">
                        <svg viewBox="0 0 520 130" className="profile-svg">
                          {(() => {
                            const temps = profileSamples.map((s) => s.temperature_display);
                            const minT = Math.min(...temps);
                            const maxT = Math.max(...temps);
                            const spanT = Math.max(maxT - minT, 1e-3);
                            const pts = profileSamples
                              .map((s, idx) => {
                                const px =
                                  30 + (idx / (profileSamples.length - 1)) * 470;
                                const py =
                                  105 - ((s.temperature_display - minT) / spanT) * 85;
                                return `${px.toFixed(1)},${py.toFixed(1)}`;
                              })
                              .join(' ');
                            return (
                              <>
                                <line
                                  x1="30"
                                  y1="105"
                                  x2="500"
                                  y2="105"
                                  stroke="#334155"
                                  strokeWidth="1"
                                />
                                <polyline
                                  fill="none"
                                  stroke="#38bdf8"
                                  strokeWidth="2.5"
                                  points={pts}
                                />
                                <text x="32" y="16" fill="#94a3b8" fontSize="10">
                                  Max: {maxT.toFixed(2)} {tempUnit}
                                </text>
                                <text x="32" y="122" fill="#94a3b8" fontSize="10">
                                  {profileSamples[0].coordinate_display} {lengthUnit} (Min:{' '}
                                  {minT.toFixed(2)} {tempUnit})
                                </text>
                                <text
                                  x="500"
                                  y="122"
                                  fill="#94a3b8"
                                  fontSize="10"
                                  textAnchor="end"
                                >
                                  +{profileSamples[profileSamples.length - 1].coordinate_display}{' '}
                                  {lengthUnit}
                                </text>
                              </>
                            );
                          })()}
                        </svg>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}

          {modalTab === 'script' && (
            <div className="inspector-pane">
              <div className="json-actions-row">
                <button
                  type="button"
                  className="secondary-action-btn"
                  onClick={() => void handleCopyScript()}
                  disabled={!scriptText}
                >
                  {copiedScript ? '✓ Copied simulation.py' : 'Copy simulation.py'}
                </button>
                <button
                  type="button"
                  className="secondary-action-btn"
                  onClick={handleDownloadPyScript}
                  disabled={!scriptText}
                >
                  ⬇ Download simulation.py
                </button>
                <button
                  type="button"
                  className="secondary-action-btn"
                  onClick={onDownloadPackage}
                >
                  ⬇ Download Full Package (.zip)
                </button>
              </div>

              {isLoadingScript ? (
                <p className="field-hint">Generating reproducible NGSolve script...</p>
              ) : scriptError ? (
                <div className="job-error-box" role="alert">
                  {scriptError}
                </div>
              ) : (
                <pre className="canonical-json-viewer" data-testid="reproducible-script-viewer">
                  {scriptText}
                </pre>
              )}
            </div>
          )}

          {modalTab === 'logs' && (
            <div className="inspector-pane">
              <pre className="canonical-json-viewer">
                {activeJob && activeJob.logs.length > 0
                  ? activeJob.logs.join('\n')
                  : 'No simulation job logs recorded yet. Click "▶ Run Simulation" to start a job.'}
              </pre>
            </div>
          )}

          {modalTab === 'history' && (
            <div className="solver-results-dashboard" data-testid="solver-history-panel">
              {quotas && (
                <div className="kpi-grid-4">
                  <div className="kpi-card">
                    <span className="kpi-label">Account &amp; Plan Tier</span>
                    <strong className="kpi-value">{quotas.plan_tier.toUpperCase()}</strong>
                    <span className="kpi-sub">Owner: {quotas.owner_id}</span>
                  </div>
                  <div className="kpi-card">
                    <span className="kpi-label">Saved Projects Quota</span>
                    <strong className="kpi-value">
                      {quotas.projects_used} / {quotas.projects_limit}
                    </strong>
                    <span className="kpi-sub">Active projects stored</span>
                  </div>
                  <div className="kpi-card">
                    <span className="kpi-label">Simulation Jobs Quota</span>
                    <strong className="kpi-value">
                      {quotas.simulations_used} / {quotas.simulations_limit}
                    </strong>
                    <span className="kpi-sub">
                      Max {quotas.max_mesh_elements_limit.toLocaleString()} tets/job
                    </span>
                  </div>
                  <div className="kpi-card">
                    <span className="kpi-label">Artifact Storage Used</span>
                    <strong className="kpi-value">
                      {(quotas.storage_bytes_used / (1024 * 1024)).toFixed(2)} MB
                    </strong>
                    <span className="kpi-sub">
                      Limit: {(quotas.storage_bytes_limit / (1024 * 1024)).toFixed(0)} MB
                    </span>
                  </div>
                </div>
              )}

              <div className="control-card">
                <div className="control-card-title">
                  <span>Simulation Job History ({jobHistory.length})</span>
                  <button
                    type="button"
                    className="panel-mini-btn"
                    onClick={() => void refreshHistoryAndQuotas()}
                    disabled={isLoadingHistory}
                  >
                    {isLoadingHistory ? 'Refreshing...' : '↻ Refresh'}
                  </button>
                </div>

                {jobHistory.length === 0 ? (
                  <p className="field-hint">
                    No simulation jobs recorded yet. Run a simulation to populate job history.
                  </p>
                ) : (
                  <div className="table-scroll-wrapper">
                    <table className="results-table">
                      <thead>
                        <tr>
                          <th>Job ID</th>
                          <th>Project Name</th>
                          <th>Status</th>
                          <th>Created At</th>
                          <th>Temp Range</th>
                          <th>Mesh</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {jobHistory.map((item) => (
                          <tr key={item.job_id}>
                            <td>
                              <code>{item.job_id.slice(0, 8)}</code>
                            </td>
                            <td>
                              <strong>{item.project_name}</strong>
                            </td>
                            <td>
                              <span className={`job-state-pill state-${item.status}`}>
                                {item.status.toUpperCase()}
                              </span>
                            </td>
                            <td>{item.created_at.replace('T', ' ').slice(0, 19)}</td>
                            <td>
                              {item.result
                                ? `${item.result.min_temperature_display.toFixed(1)} .. ${item.result.max_temperature_display.toFixed(1)} ${item.result.temperature_unit}`
                                : '—'}
                            </td>
                            <td>
                              {item.result ? `${item.result.mesh_tetrahedra} tets` : '—'}
                            </td>
                            <td style={{ display: 'flex', gap: '0.35rem' }}>
                              {onSelectHistoricalJob && (
                                <button
                                  type="button"
                                  className="panel-mini-btn"
                                  onClick={() => {
                                    onSelectHistoricalJob(item);
                                    setModalTab('results');
                                  }}
                                >
                                  Load in 3D
                                </button>
                              )}
                              <button
                                type="button"
                                className="panel-mini-btn"
                                style={{ color: '#f87171' }}
                                onClick={() => void handleDeleteJob(item.job_id)}
                              >
                                Delete
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="modal-footer-bar">
            <button type="button" className="toolbar-btn" onClick={onExportJson}>
              Export model.json
            </button>
            <button
              type="button"
              className="toolbar-btn toolbar-btn-primary"
              onClick={onClose}
            >
              Return to 3D Viewport
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
