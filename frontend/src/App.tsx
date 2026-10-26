/**
 * PDE Simulation Studio — Main CAD/CAE & 3D FEM Workstation Shell (Phase 2)
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { BottomStatusBar } from './components/BottomStatusBar';
import { LeftGeometryPanel } from './components/LeftGeometryPanel';
import { Phase2SolverModal } from './components/Phase2SolverModal';
import { ProjectModal } from './components/ProjectModal';
import { RightInspectorPanel } from './components/RightInspectorPanel';
import { TopToolbar } from './components/TopToolbar';
import { Viewport3D } from './components/Viewport3D';
import { apiClient } from './services/api';
import {
  CameraPreset,
  CanonicalSimulationModel,
  CuboidDimensions,
  FaceBoundaryCondition,
  FaceId,
  LengthUnit,
  MATERIAL_PRESET_LIBRARY,
  MaterialConfig,
  MaterialPreset,
  MeshConfig,
  OPPOSITE_FACE_MAP,
  PhysicsConfig,
  ProjectExportPayload,
  ProjectListItem,
  SCHEMA_VERSION,
  SimulationJobResponse,
  TemperatureUnit,
  Vector3D,
} from './types/model';
import {
  createDefaultModel,
  createModelFromTemplate,
  parseAndValidateImportedJson,
  ProjectTemplateId,
  validateCanonicalModel,
} from './utils/modelValidation';
import { ParsedVtuDataset, parseVtuXmlUnstructuredGrid } from './utils/vtuParser';

export const App: React.FC = () => {
  // Core Canonical Model & Project State
  const [model, setModel] = useState<CanonicalSimulationModel>(() => createDefaultModel());
  const [projectId, setProjectId] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);

  // Selection & Inspector Navigation State
  const [selectedFace, setSelectedFace] = useState<FaceId>('X_MIN');
  const [hoveredFace, setHoveredFace] = useState<FaceId | null>(null);
  const [activeInspectorTab, setActiveInspectorTab] = useState<
    'boundaries' | 'physics' | 'mesh' | 'json'
  >('boundaries');

  // 3D Viewport Display State
  const [showGrid, setShowGrid] = useState<boolean>(true);
  const [showAxes, setShowAxes] = useState<boolean>(true);
  const [showMeshLines, setShowMeshLines] = useState<boolean>(true);
  const [showBcColors, setShowBcColors] = useState<boolean>(true);
  const [showContourField, setShowContourField] = useState<boolean>(false);
  const [cameraPresetTrigger, setCameraPresetTrigger] = useState<{
    preset: CameraPreset;
    seq: number;
  }>({ preset: 'iso', seq: 0 });

  // Phase 2 & 3 Simulation Job & VTU Volume State
  const [activeJob, setActiveJob] = useState<SimulationJobResponse | null>(null);
  const [vtuDataset, setVtuDataset] = useState<ParsedVtuDataset | null>(null);
  const [isSubmittingJob, setIsSubmittingJob] = useState<boolean>(false);

  // Modals & Backend Connectivity State
  const [isProjectModalOpen, setIsProjectModalOpen] = useState<boolean>(false);
  const [isSolverModalOpen, setIsSolverModalOpen] = useState<boolean>(false);
  const [savedProjects, setSavedProjects] = useState<ProjectListItem[]>([]);
  const [isLoadingProjects, setIsLoadingProjects] = useState<boolean>(false);
  const [projectsError, setProjectsError] = useState<string | null>(null);
  const [backendConnected, setBackendConnected] = useState<boolean | null>(null);
  const [bannerAlert, setBannerAlert] = useState<{
    type: 'error' | 'success' | 'info';
    message: string;
  } | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>(
    'Ready — Configure geometry & boundary conditions, then click "▶ Run Simulation" to solve.'
  );

  const validationReport = useMemo(() => validateCanonicalModel(model), [model]);

  const checkBackendHealth = useCallback(async () => {
    try {
      const health = await apiClient.checkHealth();
      setBackendConnected(health.status === 'ok');
      const recentJobs = await apiClient.listSimulationJobs(1);
      if (Array.isArray(recentJobs) && recentJobs.length > 0 && recentJobs[0].job_id) {
        setActiveJob((prev) => prev ?? recentJobs[0]);
      }
    } catch {
      setBackendConnected(false);
    }
  }, []);

  useEffect(() => {
    void checkBackendHealth();
  }, [checkBackendHealth]);

  // Automatically load & parse the 3D .vtu volume dataset when a simulation job completes
  useEffect(() => {
    const completedJobId =
      activeJob?.status === 'completed' && activeJob.result ? activeJob.job_id : null;
    if (!completedJobId) {
      setVtuDataset(null);
      return;
    }
    let cancelled = false;
    apiClient
      .downloadVtuArtifact(completedJobId)
      .then((blob) => blob.text())
      .then((xmlText) => {
        if (!cancelled) {
          setVtuDataset(parseVtuXmlUnstructuredGrid(xmlText));
        }
      })
      .catch(() => {
        // Keep inline surface mesh fallback if VTU download is unavailable
      });
    return () => {
      cancelled = true;
    };
  }, [activeJob?.job_id, activeJob?.status, activeJob?.result]);

  // Poll active simulation job while queued or running
  useEffect(() => {
    if (!activeJob) return;
    if (activeJob.status !== 'queued' && activeJob.status !== 'running') return;

    const timer = setInterval(async () => {
      try {
        const refreshed = await apiClient.getSimulationJob(activeJob.job_id);
        setActiveJob(refreshed);
        setStatusMessage(
          `Simulation [${refreshed.status.toUpperCase()}]: ${refreshed.current_stage} (${refreshed.progress_percent}%)`
        );
        if (refreshed.status === 'completed' && refreshed.result) {
          setShowContourField(true);
          setBannerAlert({
            type: 'success',
            message: `FEM Simulation Completed: T_min = ${refreshed.result.min_temperature_display.toFixed(
              2
            )} ${refreshed.result.temperature_unit}, T_max = ${refreshed.result.max_temperature_display.toFixed(
              2
            )} ${refreshed.result.temperature_unit} (${refreshed.result.mesh_tetrahedra} tetrahedra).`,
          });
        } else if (refreshed.status === 'failed') {
          setBannerAlert({
            type: 'error',
            message: `Simulation Failed (${refreshed.error_type || 'SolverError'}): ${
              refreshed.error_message || 'Unknown solver error'
            }`,
          });
        }
      } catch {
        // Ignore transient network hiccup during poll
      }
    }, 550);

    return () => clearInterval(timer);
  }, [activeJob]);

  const fetchProjectsList = useCallback(async () => {
    setIsLoadingProjects(true);
    setProjectsError(null);
    try {
      const list = await apiClient.listProjects();
      setSavedProjects(list);
      setBackendConnected(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unable to reach backend API.';
      setProjectsError(msg);
      setBackendConnected(false);
    } finally {
      setIsLoadingProjects(false);
    }
  }, []);

  const updateModel = useCallback(
    (updater: (prev: CanonicalSimulationModel) => CanonicalSimulationModel) => {
      setModel((prev) => {
        const next = updater(prev);
        return {
          ...next,
          metadata: {
            ...next.metadata,
            updated_at: new Date().toISOString(),
          },
        };
      });
      setIsDirty(true);
    },
    []
  );

  // Execute Phase 2 NGSolve 3D FEM Simulation
  const handleRunSimulation = async () => {
    if (!validationReport.valid) {
      const firstErr = validationReport.issues.find((i) => i.severity === 'error');
      setBannerAlert({
        type: 'error',
        message: `Cannot run simulation on invalid model: ${
          firstErr?.message ?? 'Fix validation errors first.'
        }`,
      });
      return;
    }

    setIsSubmittingJob(true);
    setIsSolverModalOpen(true);
    setBannerAlert(null);
    try {
      const job = await apiClient.submitSimulationJob({
        project_id: projectId,
        model,
        max_element_size: model.mesh.max_element_size ?? null,
        polynomial_order: model.mesh.polynomial_order ?? 1,
      });
      setActiveJob(job);
      setBackendConnected(true);
      setStatusMessage(`Submitted simulation job ${job.job_id.slice(0, 8)}...`);
      if (job.status === 'completed' && job.result) {
        setShowContourField(true);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to enqueue simulation job.';
      setBannerAlert({ type: 'error', message: `Simulation Submit Error: ${msg}` });
      setStatusMessage(`Simulation failed to start: ${msg}`);
    } finally {
      setIsSubmittingJob(false);
    }
  };

  // Download Reproducible Simulation Package (.zip)
  const handleDownloadPackage = async () => {
    try {
      const blob = activeJob
        ? await apiClient.downloadSimulationPackageFromJob(activeJob.job_id)
        : await apiClient.downloadSimulationPackageFromModel(model);
      const url = URL.createObjectURL(blob);
      const safeName =
        (model.metadata.name || 'pde-simulation')
          .toLowerCase()
          .replace(/[^a-z0-9-_]+/g, '-')
          .replace(/^-|-$/g, '') || 'pde-simulation';
      const link = document.createElement('a');
      link.href = url;
      link.download = `${safeName}-package.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      setStatusMessage(`Downloaded simulation package (${safeName}-package.zip)`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Package download failed.';
      setBannerAlert({ type: 'error', message: msg });
    }
  };

  const handleProjectNameChange = (newName: string) => {
    updateModel((prev) => ({
      ...prev,
      metadata: { ...prev.metadata, name: newName },
    }));
  };

  const handleNewProject = (templateId: ProjectTemplateId = 'copper_block') => {
    const freshModel = createModelFromTemplate(templateId);
    setModel(freshModel);
    setProjectId(null);
    setActiveJob(null);
    setShowContourField(false);
    setIsDirty(false);
    setSelectedFace('X_MIN');
    setBannerAlert(null);
    setStatusMessage(`Created new project from template: ${freshModel.metadata.name}`);
  };

  const handleOpenProjectModal = () => {
    setIsProjectModalOpen(true);
    void fetchProjectsList();
  };

  const handleSaveProject = async () => {
    if (!validationReport.valid) {
      const firstErr = validationReport.issues.find((i) => i.severity === 'error');
      setBannerAlert({
        type: 'error',
        message: `Cannot save invalid model: ${
          firstErr?.message ?? 'Fix validation errors first.'
        }`,
      });
      return;
    }

    setIsSaving(true);
    setBannerAlert(null);
    try {
      const cleanName = model.metadata.name.trim() || 'Untitled PDE Project';
      const response = projectId
        ? await apiClient.updateProject(projectId, {
            name: cleanName,
            description: model.metadata.description,
            model,
          })
        : await apiClient.createProject({
            name: cleanName,
            description: model.metadata.description,
            model,
          });

      setProjectId(response.id);
      setModel(response.model);
      setIsDirty(false);
      setBackendConnected(true);
      setStatusMessage(`Saved project "${response.name}" (ID: ${response.id.slice(0, 8)}...)`);
      setBannerAlert({
        type: 'success',
        message: `Project "${response.name}" saved to SQLite repository.`,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to save project.';
      setBannerAlert({ type: 'error', message: `Save failed: ${msg}` });
      setStatusMessage(`Save failed: ${msg}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleSelectProjectFromModal = async (targetId: string) => {
    setIsLoadingProjects(true);
    setProjectsError(null);
    try {
      const loaded = await apiClient.getProject(targetId);
      setProjectId(loaded.id);
      setModel(loaded.model);
      setActiveJob(null);
      setShowContourField(false);
      setIsDirty(false);
      setIsProjectModalOpen(false);
      setStatusMessage(`Opened project "${loaded.name}"`);
      setBannerAlert({
        type: 'info',
        message: `Loaded project "${loaded.name}" from database.`,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to open project.';
      setProjectsError(msg);
    } finally {
      setIsLoadingProjects(false);
    }
  };

  const handleDeleteProjectFromModal = async (targetId: string) => {
    try {
      await apiClient.deleteProject(targetId);
      if (projectId === targetId) {
        setProjectId(null);
        setIsDirty(true);
      }
      await fetchProjectsList();
      setStatusMessage(`Deleted project ${targetId.slice(0, 8)}...`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to delete project.';
      setProjectsError(msg);
    }
  };

  const handleExportJson = () => {
    const exportPayload: ProjectExportPayload = {
      export_format: 'pde_simulation_studio_project',
      schema_version: SCHEMA_VERSION,
      project_id: projectId,
      exported_at: new Date().toISOString(),
      model,
    };
    const jsonString = JSON.stringify(exportPayload, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const safeFilename =
      (model.metadata.name || 'pde-model')
        .toLowerCase()
        .replace(/[^a-z0-9-_]+/g, '-')
        .replace(/^-|-$/g, '') || 'pde-model';

    const link = document.createElement('a');
    link.href = url;
    link.download = `${safeFilename}.pde.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    setStatusMessage(`Exported canonical JSON (${safeFilename}.pde.json)`);
  };

  const handleImportJsonFile = async (file: File) => {
    setBannerAlert(null);
    try {
      const rawText = await file.text();
      const { model: importedModel } = parseAndValidateImportedJson(rawText);
      setModel(importedModel);
      setProjectId(null);
      setActiveJob(null);
      setShowContourField(false);
      setIsDirty(true);
      setStatusMessage(`Imported model "${importedModel.metadata.name}" from ${file.name}`);
      setBannerAlert({
        type: 'success',
        message: `Successfully imported and validated "${importedModel.metadata.name}" (Schema v${importedModel.schema_version}).`,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Invalid JSON file.';
      setBannerAlert({ type: 'error', message: `JSON Import Error: ${msg}` });
      setStatusMessage(`Import failed: ${msg}`);
    }
  };

  const handleUpdateDimensions = (dims: Partial<CuboidDimensions>) => {
    setShowContourField(false);
    updateModel((prev) => ({
      ...prev,
      geometry: {
        ...prev.geometry,
        dimensions: { ...prev.geometry.dimensions, ...dims },
      },
    }));
  };

  const handleUpdatePosition = (pos: Partial<Vector3D>) => {
    setShowContourField(false);
    updateModel((prev) => ({
      ...prev,
      geometry: {
        ...prev.geometry,
        position: { ...prev.geometry.position, ...pos },
      },
    }));
  };

  const handleUpdateRotation = (rot: Partial<Vector3D>) => {
    setShowContourField(false);
    updateModel((prev) => ({
      ...prev,
      geometry: {
        ...prev.geometry,
        rotation_deg: { ...prev.geometry.rotation_deg, ...rot },
      },
    }));
  };

  const handleUpdateUnits = (units: {
    length?: LengthUnit;
    temperature?: TemperatureUnit;
  }) => {
    updateModel((prev) => ({
      ...prev,
      units: { ...prev.units, ...units },
    }));
  };

  const handleResetGeometry = () => {
    setShowContourField(false);
    updateModel((prev) => ({
      ...prev,
      geometry: {
        type: 'rectangular_cuboid',
        dimensions: { length_x: 1.2, length_y: 0.7, length_z: 0.5 },
        position: { x: 0, y: 0, z: 0 },
        rotation_deg: { x: 0, y: 0, z: 0 },
      },
    }));
    setCameraPresetTrigger((prev) => ({ preset: 'iso', seq: prev.seq + 1 }));
    setStatusMessage('Reset cuboid dimensions, position, and orientation.');
  };

  const handleUpdateFaceBC = (
    faceId: FaceId,
    updated: Partial<FaceBoundaryCondition>
  ) => {
    updateModel((prev) => ({
      ...prev,
      boundary_conditions: {
        ...prev.boundary_conditions,
        [faceId]: {
          ...prev.boundary_conditions[faceId],
          ...updated,
          face_id: faceId,
        },
      },
    }));
    setStatusMessage(`Updated boundary condition on semantic face ${faceId}`);
  };

  const handleCopyBcToOppositeFace = (sourceFaceId: FaceId) => {
    const targetFaceId = OPPOSITE_FACE_MAP[sourceFaceId];
    const sourceBc = model.boundary_conditions[sourceFaceId];
    updateModel((prev) => ({
      ...prev,
      boundary_conditions: {
        ...prev.boundary_conditions,
        [targetFaceId]: {
          ...sourceBc,
          face_id: targetFaceId,
        },
      },
    }));
    setStatusMessage(`Copied ${sourceFaceId} boundary condition to ${targetFaceId}`);
  };

  const handleSelectMaterialPreset = (preset: MaterialPreset) => {
    const def = MATERIAL_PRESET_LIBRARY[preset];
    updateModel((prev) => ({
      ...prev,
      material: {
        id: def.id,
        name: def.name,
        preset: def.preset,
        thermal_conductivity: def.thermal_conductivity,
      },
    }));
    setStatusMessage(
      `Assigned material preset: ${def.name} (k = ${def.thermal_conductivity} W/(m·K))`
    );
  };

  const handleUpdateMaterial = (updated: Partial<MaterialConfig>) => {
    updateModel((prev) => ({
      ...prev,
      material: { ...prev.material, ...updated },
    }));
  };

  const handleUpdatePhysics = (updated: Partial<PhysicsConfig>) => {
    updateModel((prev) => ({
      ...prev,
      physics: { ...prev.physics, ...updated },
    }));
  };

  const handleUpdateMesh = (updated: Partial<MeshConfig>) => {
    updateModel((prev) => ({
      ...prev,
      mesh: { ...prev.mesh, ...updated },
    }));
  };

  const handleUpdateMetadata = (updated: { description?: string; author?: string }) => {
    updateModel((prev) => ({
      ...prev,
      metadata: { ...prev.metadata, ...updated },
    }));
  };

  const handleTriggerBackendValidation = async () => {
    try {
      const report = await apiClient.validateModel(model);
      setBackendConnected(true);
      setBannerAlert({
        type: report.valid ? 'success' : 'error',
        message: report.valid
          ? `Backend Pydantic & scientific validation passed (${report.metrics.total_elements} elements, ${report.metrics.total_nodes} nodes).`
          : 'Backend reported validation issues.',
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Backend validation failed.';
      setBannerAlert({ type: 'error', message: msg });
    }
  };

  const triggerCameraPreset = (preset: CameraPreset) => {
    setCameraPresetTrigger((prev) => ({ preset, seq: prev.seq + 1 }));
    setStatusMessage(`Camera view oriented to: ${preset.toUpperCase()}`);
  };

  return (
    <div className="studio-app-shell">
      <TopToolbar
        projectId={projectId}
        projectName={model.metadata.name}
        isDirty={isDirty}
        isSaving={isSaving}
        activeJobStatus={activeJob?.status ?? null}
        activeJobProgress={activeJob?.progress_percent ?? 0}
        onProjectNameChange={handleProjectNameChange}
        onNewProject={handleNewProject}
        onOpenProjectModal={handleOpenProjectModal}
        onSaveProject={() => void handleSaveProject()}
        onExportJson={handleExportJson}
        onImportJsonFile={(file) => void handleImportJsonFile(file)}
        onResetView={() => triggerCameraPreset('iso')}
        onRunSimulation={() => void handleRunSimulation()}
        onOpenSolverModal={() => setIsSolverModalOpen(true)}
      />

      {bannerAlert && (
        <div
          className={`studio-notification-bar notify-${bannerAlert.type}`}
          role="status"
          data-testid="studio-notification-banner"
        >
          <span>{bannerAlert.message}</span>
          <button
            type="button"
            className="notify-close-btn"
            onClick={() => setBannerAlert(null)}
            aria-label="Dismiss notification"
          >
            ✕
          </button>
        </div>
      )}

      <main className="studio-workspace">
        <LeftGeometryPanel
          model={model}
          selectedFace={selectedFace}
          hoveredFace={hoveredFace}
          onSelectFace={(fid) => {
            setSelectedFace(fid);
            setStatusMessage(`Selected semantic face ${fid}`);
          }}
          onHoverFace={setHoveredFace}
          onUpdateDimensions={handleUpdateDimensions}
          onUpdatePosition={handleUpdatePosition}
          onUpdateRotation={handleUpdateRotation}
          onUpdateUnits={handleUpdateUnits}
          onResetGeometry={handleResetGeometry}
          onSelectInspectorTab={setActiveInspectorTab}
        />

        <Viewport3D
          model={model}
          simulationResult={activeJob?.result ?? null}
          vtuDataset={vtuDataset}
          showContourField={showContourField}
          onToggleContourField={() => setShowContourField((v) => !v)}
          selectedFace={selectedFace}
          hoveredFace={hoveredFace}
          onSelectFace={(fid) => {
            setSelectedFace(fid);
            setActiveInspectorTab('boundaries');
            setStatusMessage(`Selected semantic face ${fid} in 3D viewport`);
          }}
          onHoverFace={setHoveredFace}
          showGrid={showGrid}
          showAxes={showAxes}
          showMeshLines={showMeshLines}
          showBcColors={showBcColors}
          cameraPresetTrigger={cameraPresetTrigger}
          onToggleGrid={() => setShowGrid((v) => !v)}
          onToggleAxes={() => setShowAxes((v) => !v)}
          onToggleMeshLines={() => setShowMeshLines((v) => !v)}
          onToggleBcColors={() => setShowBcColors((v) => !v)}
          onTriggerCameraPreset={triggerCameraPreset}
        />

        <RightInspectorPanel
          model={model}
          validationReport={validationReport}
          selectedFace={selectedFace}
          activeTab={activeInspectorTab}
          onTabChange={setActiveInspectorTab}
          onSelectFace={setSelectedFace}
          onUpdateFaceBC={handleUpdateFaceBC}
          onCopyBcToOppositeFace={handleCopyBcToOppositeFace}
          onUpdateMaterial={handleUpdateMaterial}
          onSelectMaterialPreset={handleSelectMaterialPreset}
          onUpdatePhysics={handleUpdatePhysics}
          onUpdateMesh={handleUpdateMesh}
          onUpdateMetadata={handleUpdateMetadata}
          onTriggerBackendValidation={() => void handleTriggerBackendValidation()}
        />
      </main>

      <BottomStatusBar
        model={model}
        validationReport={validationReport}
        selectedFace={selectedFace}
        hoveredFace={hoveredFace}
        backendConnected={backendConnected}
        activeJob={activeJob}
        statusMessage={statusMessage}
      />

      <ProjectModal
        isOpen={isProjectModalOpen}
        projects={savedProjects}
        isLoading={isLoadingProjects}
        error={projectsError}
        activeProjectId={projectId}
        onClose={() => setIsProjectModalOpen(false)}
        onRefresh={() => void fetchProjectsList()}
        onSelectProject={(id) => void handleSelectProjectFromModal(id)}
        onDeleteProject={(id) => void handleDeleteProjectFromModal(id)}
      />

      <Phase2SolverModal
        isOpen={isSolverModalOpen}
        model={model}
        validationReport={validationReport}
        activeJob={activeJob}
        isSubmitting={isSubmittingJob}
        onClose={() => setIsSolverModalOpen(false)}
        onRunSimulation={() => void handleRunSimulation()}
        onDownloadPackage={() => void handleDownloadPackage()}
        onExportJson={handleExportJson}
        onJobDeleted={(deletedId) => {
          if (activeJob?.job_id === deletedId) {
            setActiveJob(null);
            setShowContourField(false);
          }
          setStatusMessage(`Deleted simulation job ${deletedId.slice(0, 8)} and purged artifacts.`);
        }}
        onSelectHistoricalJob={(historicalJob) => {
          setModel(historicalJob.model);
          setActiveJob(historicalJob);
          if (historicalJob.status === 'completed' && historicalJob.result) {
            setShowContourField(true);
          }
          setStatusMessage(
            `Loaded simulation job ${historicalJob.job_id.slice(0, 8)} (${historicalJob.project_name}).`
          );
        }}
      />
    </div>
  );
};

export default App;
