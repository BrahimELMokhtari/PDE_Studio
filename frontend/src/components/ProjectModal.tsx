/**
 * Modal for Opening & Managing Saved Projects from the Backend SQLite Database.
 * Includes loading state, error alert, search filter, and empty state.
 */

import React, { useState } from 'react';
import { ProjectListItem } from '../types/model';

export interface ProjectModalProps {
  isOpen: boolean;
  projects: ProjectListItem[];
  isLoading: boolean;
  error: string | null;
  activeProjectId: string | null;
  onClose: () => void;
  onRefresh: () => void;
  onSelectProject: (projectId: string) => void;
  onDeleteProject: (projectId: string) => void;
}

export const ProjectModal: React.FC<ProjectModalProps> = ({
  isOpen,
  projects,
  isLoading,
  error,
  activeProjectId,
  onClose,
  onRefresh,
  onSelectProject,
  onDeleteProject,
}) => {
  const [searchQuery, setSearchQuery] = useState('');

  if (!isOpen) return null;

  const filtered = projects.filter(
    (p) =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.material_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Open Saved Project">
      <div className="modal-container">
        <div className="modal-header">
          <div>
            <h2>Saved Simulation Projects</h2>
            <p className="modal-subtitle">
              Stored in SQLite repository (PostgreSQL-ready abstraction)
            </p>
          </div>
          <div className="modal-header-actions">
            <button type="button" className="toolbar-btn" onClick={onRefresh} disabled={isLoading}>
              {isLoading ? 'Refreshing...' : 'Refresh'}
            </button>
            <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Close">
              ✕
            </button>
          </div>
        </div>

        <div className="modal-body">
          <div className="modal-search-bar">
            <input
              type="search"
              placeholder="Filter projects by name, description, or material..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Filter saved projects"
            />
          </div>

          {error && (
            <div className="alert-banner alert-error" role="alert">
              <strong>Database Connection Error:</strong> {error}
            </div>
          )}

          {isLoading ? (
            <div className="modal-empty-state">
              <div className="loading-spinner" />
              <p>Loading projects from repository...</p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="modal-empty-state">
              <p className="empty-title">No saved projects found</p>
              <p className="empty-desc">
                {projects.length === 0
                  ? 'Save your current 3D model using the "Save" button in the top toolbar, or import a canonical JSON file.'
                  : 'No projects match your current search filter.'}
              </p>
            </div>
          ) : (
            <div className="project-list-table">
              {filtered.map((proj) => (
                <div
                  key={proj.id}
                  className={`project-row-card ${
                    activeProjectId === proj.id ? 'active-project-row' : ''
                  }`}
                >
                  <div className="project-row-info">
                    <div className="project-row-title-line">
                      <strong>{proj.name}</strong>
                      <span className="project-schema-pill">v{proj.schema_version}</span>
                      {activeProjectId === proj.id && (
                        <span className="active-tag">Currently Open</span>
                      )}
                    </div>
                    {proj.description && (
                      <p className="project-row-desc">{proj.description}</p>
                    )}
                    <div className="project-row-meta">
                      <span>Domain: {proj.dimensions_summary}</span>
                      <span>•</span>
                      <span>Material: {proj.material_name}</span>
                      <span>•</span>
                      <span>Updated: {new Date(proj.updated_at).toLocaleString()}</span>
                    </div>
                  </div>
                  <div className="project-row-actions">
                    <button
                      type="button"
                      className="toolbar-btn toolbar-btn-primary"
                      onClick={() => onSelectProject(proj.id)}
                    >
                      Open
                    </button>
                    <button
                      type="button"
                      className="toolbar-btn btn-danger"
                      onClick={() => onDeleteProject(proj.id)}
                      title="Delete project from repository"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
