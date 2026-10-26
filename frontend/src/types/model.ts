/**
 * Versioned Canonical Simulation Model Schema (v1.0.0) & Phase 2/3 FEM Simulation Types
 * Shared between the React/Three.js Frontend and Python/FastAPI/NGSolve Backend.
 */

export const SCHEMA_VERSION = '1.0.0' as const;

export type FaceId = 'X_MIN' | 'X_MAX' | 'Y_MIN' | 'Y_MAX' | 'Z_MIN' | 'Z_MAX';

export const ALL_FACE_IDS: readonly FaceId[] = [
  'X_MIN',
  'X_MAX',
  'Y_MIN',
  'Y_MAX',
  'Z_MIN',
  'Z_MAX',
] as const;

export const OPPOSITE_FACE_MAP: Record<FaceId, FaceId> = {
  X_MIN: 'X_MAX',
  X_MAX: 'X_MIN',
  Y_MIN: 'Y_MAX',
  Y_MAX: 'Y_MIN',
  Z_MIN: 'Z_MAX',
  Z_MAX: 'Z_MIN',
};

export type LengthUnit = 'm' | 'cm' | 'mm';
export type TemperatureUnit = 'K' | 'C';

export type MaterialPreset =
  | 'copper'
  | 'aluminum_6061'
  | 'steel_304'
  | 'silicon'
  | 'titanium'
  | 'custom';

export type BoundaryConditionType =
  | 'dirichlet'
  | 'neumann'
  | 'robin'
  | 'insulated';

export type ElementType = 'hexahedral_8node' | 'tetrahedral_4node';

export interface ModelMetadata {
  name: string;
  description: string;
  author: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface UnitSystem {
  length: LengthUnit;
  temperature: TemperatureUnit;
  thermal_conductivity: 'W/(m*K)';
  heat_source: 'W/m^3';
  heat_flux: 'W/m^2';
  convection_coefficient: 'W/(m^2*K)';
}

export interface CuboidDimensions {
  length_x: number;
  length_y: number;
  length_z: number;
}

export interface Vector3D {
  x: number;
  y: number;
  z: number;
}

export interface CuboidGeometry {
  type: 'rectangular_cuboid';
  dimensions: CuboidDimensions;
  position: Vector3D;
  rotation_deg: Vector3D;
}

export interface MaterialConfig {
  id: string;
  name: string;
  preset: MaterialPreset;
  thermal_conductivity: number;
}

export interface PhysicsConfig {
  type: 'steady_state_heat_conduction';
  volumetric_heat_source: number;
}

export interface FaceBoundaryCondition {
  face_id: FaceId;
  type: BoundaryConditionType;
  temperature: number | null;
  heat_flux: number | null;
  convection_coefficient: number | null;
  ambient_temperature: number | null;
}

export type BoundaryConditionMap = Record<FaceId, FaceBoundaryCondition>;

export interface MeshDivisions {
  nx: number;
  ny: number;
  nz: number;
}

export interface MeshConfig {
  element_type: ElementType;
  divisions: MeshDivisions;
  max_element_size?: number | null;
  polynomial_order?: number;
}

export interface CanonicalSimulationModel {
  schema_version: '1.0.0';
  metadata: ModelMetadata;
  units: UnitSystem;
  geometry: CuboidGeometry;
  material: MaterialConfig;
  physics: PhysicsConfig;
  boundary_conditions: BoundaryConditionMap;
  mesh: MeshConfig;
}

export interface ValidationIssue {
  severity: 'error' | 'warning' | 'info';
  field: string;
  message: string;
}

export interface ValidationReport {
  valid: boolean;
  schema_version: string;
  issues: ValidationIssue[];
  metrics: {
    volume: number;
    surface_area: number;
    total_elements: number;
    total_nodes: number;
    element_aspect_ratio: number;
  };
}

export interface ProjectListItem {
  id: string;
  owner_id?: string;
  name: string;
  description: string;
  schema_version: string;
  material_name: string;
  dimensions_summary: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectResponse {
  id: string;
  owner_id?: string;
  name: string;
  description: string;
  schema_version: string;
  model: CanonicalSimulationModel;
  validation: ValidationReport;
  created_at: string;
  updated_at: string;
}

export interface ProjectExportPayload {
  export_format: string;
  schema_version: '1.0.0';
  project_id?: string | null;
  exported_at: string;
  model: CanonicalSimulationModel;
}

// Phase 2 & 3 FEM Simulation & Post-Processing Types
export type JobStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface BoundaryFaceResult {
  face_id: FaceId;
  bc_type: string;
  area_m2: number;
  min_temperature_k: number;
  max_temperature_k: number;
  mean_temperature_k: number;
  min_temperature_display: number;
  max_temperature_display: number;
  mean_temperature_display: number;
  net_outward_heat_rate_w: number;
}

export interface LineProfileSample {
  coordinate_m: number;
  coordinate_display: number;
  temperature_k: number;
  temperature_display: number;
}

export interface SurfaceContourMesh {
  vertices: number[][];
  vertex_temperatures_k: number[];
  vertex_temperatures_display: number[];
  triangles: number[][];
  triangle_face_ids: string[];
}

export interface ConvergenceInfo {
  solver_method: string;
  linear_system_residual_l2: number;
  relative_residual_norm: number;
  energy_balance_rel_error: number;
  converged: boolean;
  geometry_meshing_time_s: number;
  assembly_time_s: number;
  solve_time_s: number;
  postprocess_time_s: number;
}

export interface MeshQualityStats {
  min_edge_length_m: number;
  max_edge_length_m: number;
  mean_edge_length_m: number;
  mean_aspect_ratio: number;
  surface_triangles_total: number;
  surface_triangles_inline: number;
  inline_mesh_truncated: boolean;
}

export interface SimulationArtifactsMap {
  vtu_key?: string | null;
  nodal_csv_key?: string | null;
  boundary_csv_key?: string | null;
  script_key?: string | null;
  model_key?: string | null;
  package_zip_key?: string | null;
  total_artifact_bytes: number;
}

export interface SimulationResultSummary {
  solver_backend: string;
  ngsolve_version: string;
  mesh_vertices: number;
  mesh_tetrahedra: number;
  mesh_surface_triangles: number;
  free_dofs: number;
  total_dofs: number;
  polynomial_order: number;
  max_element_size_m: number;
  domain_volume_m3: number;
  min_temperature_k: number;
  max_temperature_k: number;
  mean_temperature_k: number;
  min_temperature_display: number;
  max_temperature_display: number;
  mean_temperature_display: number;
  temperature_unit: string;
  length_unit: string;
  max_grad_t_k_per_m: number;
  max_heat_flux_w_m2: number;
  total_internal_heat_generation_w: number;
  net_boundary_heat_loss_w: number;
  energy_balance_residual_w: number;
  solve_wall_time_seconds: number;
  boundary_stats: Record<string, BoundaryFaceResult>;
  centerline_profiles: Record<'x' | 'y' | 'z', LineProfileSample[]>;
  surface_mesh: SurfaceContourMesh;
  convergence?: ConvergenceInfo | null;
  mesh_quality?: MeshQualityStats | null;
  artifacts?: SimulationArtifactsMap | null;
}

export interface SimulationJobResponse {
  job_id: string;
  owner_id?: string;
  rq_job_id?: string | null;
  project_id?: string | null;
  project_name: string;
  status: JobStatus;
  progress_percent: number;
  current_stage: string;
  logs: string[];
  error_type?: string | null;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  model: CanonicalSimulationModel;
  result?: SimulationResultSummary | null;
}

export interface SimulationScriptResponse {
  filename: string;
  schema_version: string;
  script_content: string;
  instructions: string;
}

export interface UserQuotaSummaryResponse {
  owner_id: string;
  plan_tier: string;
  projects_used: number;
  projects_limit: number;
  simulations_used: number;
  simulations_limit: number;
  storage_bytes_used: number;
  storage_bytes_limit: number;
  max_mesh_elements_limit: number;
}

export interface MaterialPresetDefinition {
  preset: MaterialPreset;
  id: string;
  name: string;
  thermal_conductivity: number;
  description: string;
}

export const MATERIAL_PRESET_LIBRARY: Record<MaterialPreset, MaterialPresetDefinition> = {
  copper: {
    preset: 'copper',
    id: 'mat_copper',
    name: 'Copper (C11000)',
    thermal_conductivity: 401.0,
    description: 'High-conductivity electrolytic tough pitch copper',
  },
  aluminum_6061: {
    preset: 'aluminum_6061',
    id: 'mat_al6061',
    name: 'Aluminum 6061-T6',
    thermal_conductivity: 167.0,
    description: 'Structural aerospace & heat sink aluminum alloy',
  },
  steel_304: {
    preset: 'steel_304',
    id: 'mat_ss304',
    name: 'Stainless Steel 304',
    thermal_conductivity: 16.2,
    description: 'Austenitic corrosion-resistant stainless steel',
  },
  silicon: {
    preset: 'silicon',
    id: 'mat_silicon',
    name: 'Crystalline Silicon (Si)',
    thermal_conductivity: 148.0,
    description: 'Semiconductor wafer substrate at 300 K',
  },
  titanium: {
    preset: 'titanium',
    id: 'mat_ti6al4v',
    name: 'Titanium Ti-6Al-4V',
    thermal_conductivity: 6.7,
    description: 'Low-conductivity high-strength aerospace titanium alloy',
  },
  custom: {
    preset: 'custom',
    id: 'mat_custom',
    name: 'Custom Isotropic Material',
    thermal_conductivity: 50.0,
    description: 'User-defined isotropic thermal conductivity',
  },
};

export type CameraPreset = 'iso' | 'x_pos' | 'x_neg' | 'y_pos' | 'y_neg' | 'z_pos' | 'z_neg';
