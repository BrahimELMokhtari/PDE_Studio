/**
 * Backend REST API Client supporting Project CRUD, Phase 2 NGSolve FEM Simulations,
 * and Phase 3 Scientific Post-Processing Exports (VTU, CSV, Quotas, OIDC Auth).
 */

import {
  CanonicalSimulationModel,
  ProjectExportPayload,
  ProjectListItem,
  ProjectResponse,
  SimulationJobResponse,
  SimulationScriptResponse,
  UserQuotaSummaryResponse,
  ValidationReport,
} from '../types/model';

const DEFAULT_API_BASE = 'http://localhost:8000';

let authToken: string | null = null;

export function setApiAuthToken(token: string | null): void {
  authToken = token;
}

export function getApiBaseUrl(): string {
  const envUrl = import.meta.env?.VITE_API_BASE_URL as string | undefined;
  return (envUrl && envUrl.trim().replace(/\/+$/, '')) || DEFAULT_API_BASE;
}

function buildAuthHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...(extra || {}) };
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }
  return headers;
}

export interface HealthStatusResponse {
  status: string;
  service: string;
  version: string;
  schema_version: string;
  database: {
    backend: string;
    connected: boolean;
    abstraction: string;
  };
  storage?: {
    backend: string;
    connected: boolean;
    abstraction: string;
  };
  queue?: {
    engine: string;
    mode: string;
    queue_name: string;
  };
  capabilities: {
    phase: number;
    pde_solver_execution: boolean;
    solver_engine?: string;
    solver_roadmap?: string;
    vtu_and_csv_export?: boolean;
    cross_section_clipping?: boolean;
  };
}

async function handleApiResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status} (${response.statusText})`;
    try {
      const errBody = await response.json();
      if (errBody?.detail) {
        if (typeof errBody.detail === 'string') {
          errorMessage = errBody.detail;
        } else if (errBody.detail.message) {
          const fieldErrors = Array.isArray(errBody.detail.errors)
            ? errBody.detail.errors
                .map((e: { field?: string; message?: string; msg?: string }) =>
                  `${e.field || 'model'}: ${e.message || e.msg || 'invalid'}`
                )
                .join('; ')
            : '';
          errorMessage = fieldErrors
            ? `${errBody.detail.message} (${fieldErrors})`
            : errBody.detail.message;
        }
      }
    } catch {
      // keep default status text
    }
    throw new Error(errorMessage);
  }
  return (await response.json()) as T;
}

export const apiClient = {
  async checkHealth(): Promise<HealthStatusResponse> {
    const res = await fetch(`${getApiBaseUrl()}/api/health`, {
      headers: buildAuthHeaders(),
    });
    return handleApiResponse<HealthStatusResponse>(res);
  },

  async listProjects(): Promise<ProjectListItem[]> {
    const res = await fetch(`${getApiBaseUrl()}/api/projects`, {
      headers: buildAuthHeaders(),
    });
    return handleApiResponse<ProjectListItem[]>(res);
  },

  async getProject(projectId: string): Promise<ProjectResponse> {
    const res = await fetch(`${getApiBaseUrl()}/api/projects/${encodeURIComponent(projectId)}`, {
      headers: buildAuthHeaders(),
    });
    return handleApiResponse<ProjectResponse>(res);
  },

  async createProject(payload: {
    name: string;
    description: string;
    model: CanonicalSimulationModel;
  }): Promise<ProjectResponse> {
    const res = await fetch(`${getApiBaseUrl()}/api/projects`, {
      method: 'POST',
      headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });
    return handleApiResponse<ProjectResponse>(res);
  },

  async updateProject(
    projectId: string,
    payload: {
      name?: string;
      description?: string;
      model: CanonicalSimulationModel;
    }
  ): Promise<ProjectResponse> {
    const res = await fetch(`${getApiBaseUrl()}/api/projects/${encodeURIComponent(projectId)}`, {
      method: 'PUT',
      headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });
    return handleApiResponse<ProjectResponse>(res);
  },

  async deleteProject(projectId: string): Promise<{ deleted: boolean; id: string }> {
    const res = await fetch(`${getApiBaseUrl()}/api/projects/${encodeURIComponent(projectId)}`, {
      method: 'DELETE',
      headers: buildAuthHeaders(),
    });
    return handleApiResponse<{ deleted: boolean; id: string }>(res);
  },

  async validateModel(model: CanonicalSimulationModel): Promise<ValidationReport> {
    const res = await fetch(`${getApiBaseUrl()}/api/projects/validate`, {
      method: 'POST',
      headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(model),
    });
    return handleApiResponse<ValidationReport>(res);
  },

  async exportProject(projectId: string): Promise<ProjectExportPayload> {
    const res = await fetch(
      `${getApiBaseUrl()}/api/projects/${encodeURIComponent(projectId)}/export`,
      { headers: buildAuthHeaders() }
    );
    return handleApiResponse<ProjectExportPayload>(res);
  },

  async importProject(payload: unknown): Promise<ProjectResponse> {
    const res = await fetch(`${getApiBaseUrl()}/api/projects/import`, {
      method: 'POST',
      headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });
    return handleApiResponse<ProjectResponse>(res);
  },

  // Phase 2 & 3 Simulation & Artifact Endpoints
  async getUserQuotas(): Promise<UserQuotaSummaryResponse> {
    const res = await fetch(`${getApiBaseUrl()}/api/simulations/quotas`, {
      headers: buildAuthHeaders(),
    });
    return handleApiResponse<UserQuotaSummaryResponse>(res);
  },

  async submitSimulationJob(payload: {
    project_id?: string | null;
    model: CanonicalSimulationModel;
    max_element_size?: number | null;
    polynomial_order?: number;
  }): Promise<SimulationJobResponse> {
    const res = await fetch(`${getApiBaseUrl()}/api/simulations`, {
      method: 'POST',
      headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });
    return handleApiResponse<SimulationJobResponse>(res);
  },

  async getSimulationJob(jobId: string): Promise<SimulationJobResponse> {
    const res = await fetch(`${getApiBaseUrl()}/api/simulations/${encodeURIComponent(jobId)}`, {
      headers: buildAuthHeaders(),
    });
    return handleApiResponse<SimulationJobResponse>(res);
  },

  async listSimulationJobs(limit = 20): Promise<SimulationJobResponse[]> {
    const res = await fetch(`${getApiBaseUrl()}/api/simulations?limit=${limit}`, {
      headers: buildAuthHeaders(),
    });
    return handleApiResponse<SimulationJobResponse[]>(res);
  },

  async deleteSimulationJob(
    jobId: string
  ): Promise<{ deleted: boolean; job_id: string; deleted_artifacts_count: number }> {
    const res = await fetch(`${getApiBaseUrl()}/api/simulations/${encodeURIComponent(jobId)}`, {
      method: 'DELETE',
      headers: buildAuthHeaders(),
    });
    return handleApiResponse<{
      deleted: boolean;
      job_id: string;
      deleted_artifacts_count: number;
    }>(res);
  },

  async generateSimulationScript(
    model: CanonicalSimulationModel
  ): Promise<SimulationScriptResponse> {
    const res = await fetch(`${getApiBaseUrl()}/api/simulations/script`, {
      method: 'POST',
      headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(model),
    });
    return handleApiResponse<SimulationScriptResponse>(res);
  },

  async downloadSimulationPackageFromModel(model: CanonicalSimulationModel): Promise<Blob> {
    const res = await fetch(`${getApiBaseUrl()}/api/simulations/package`, {
      method: 'POST',
      headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(model),
    });
    if (!res.ok) {
      await handleApiResponse(res);
    }
    return await res.blob();
  },

  async downloadSimulationPackageFromJob(jobId: string): Promise<Blob> {
    const res = await fetch(
      `${getApiBaseUrl()}/api/simulations/${encodeURIComponent(jobId)}/package`,
      { headers: buildAuthHeaders() }
    );
    if (!res.ok) {
      await handleApiResponse(res);
    }
    return await res.blob();
  },

  async downloadVtuArtifact(jobId: string): Promise<Blob> {
    const res = await fetch(
      `${getApiBaseUrl()}/api/simulations/${encodeURIComponent(jobId)}/artifacts/vtu`,
      { headers: buildAuthHeaders() }
    );
    if (!res.ok) {
      await handleApiResponse(res);
    }
    return await res.blob();
  },

  async downloadNodalCsvArtifact(jobId: string): Promise<Blob> {
    const res = await fetch(
      `${getApiBaseUrl()}/api/simulations/${encodeURIComponent(jobId)}/artifacts/nodal-csv`,
      { headers: buildAuthHeaders() }
    );
    if (!res.ok) {
      await handleApiResponse(res);
    }
    return await res.blob();
  },

  async downloadBoundaryCsvArtifact(jobId: string): Promise<Blob> {
    const res = await fetch(
      `${getApiBaseUrl()}/api/simulations/${encodeURIComponent(jobId)}/artifacts/boundary-csv`,
      { headers: buildAuthHeaders() }
    );
    if (!res.ok) {
      await handleApiResponse(res);
    }
    return await res.blob();
  },
};
