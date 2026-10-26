import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import App from '../App';

// Mock fetch for health check and solver endpoints in component tests
globalThis.fetch = vi.fn((url: string | URL | Request) => {
  const urlStr = String(url);
  if (urlStr.includes('/api/simulations/script')) {
    return Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve({
          filename: 'simulation.py',
          schema_version: '1.0.0',
          script_content: 'import ngsolve as ngs\n# Reproducible 3D FEM Script',
          instructions: 'Run python simulation.py',
        }),
    } as Response);
  }
  return Promise.resolve({
    ok: true,
    json: () =>
      Promise.resolve({
        status: 'ok',
        service: 'PDE Simulation Studio API',
        version: '2.0.0-phase2',
        schema_version: '1.0.0',
        database: { backend: 'sqlite', connected: true, abstraction: 'ProjectRepository' },
        capabilities: {
          phase: 2,
          pde_solver_execution: true,
          solver_engine: 'NGSolve 6.2 / Netgen OpenCASCADE',
        },
      }),
  } as Response);
});

describe('PDE Simulation Studio Application UI (Phase 2)', () => {
  it('renders top toolbar, geometry panel, 3D viewport, properties inspector, and status bar', () => {
    render(<App />);

    expect(screen.getByText('PDE Simulation Studio')).toBeInTheDocument();
    expect(screen.getByText('Parametric Geometry')).toBeInTheDocument();
    expect(screen.getByTestId('three-viewport-canvas')).toBeInTheDocument();
    expect(screen.getByText('Boundary Condition Inspector')).toBeInTheDocument();
    expect(screen.getByTestId('run-simulation-btn')).toBeInTheDocument();
  });

  it('allows selecting semantic faces and changing boundary condition types', () => {
    render(<App />);

    const zMaxBtn = screen.getByTestId('tree-face-Z_MAX');
    fireEvent.click(zMaxBtn);

    const bcSelect = screen.getByTestId('bc-type-select') as HTMLSelectElement;
    expect(bcSelect.value).toBe('insulated');

    fireEvent.change(bcSelect, { target: { value: 'dirichlet' } });
    expect(bcSelect.value).toBe('dirichlet');

    const tempInput = screen.getByTestId('bc-temperature-input') as HTMLInputElement;
    fireEvent.change(tempInput, { target: { value: '420' } });
    expect(tempInput.value).toBe('420');
  });

  it('opens the Phase 2 NGSolve 3D FEM Solver modal and displays simulation controls', () => {
    render(<App />);

    const solverBtn = screen.getByTestId('open-solver-dashboard-btn');
    fireEvent.click(solverBtn);

    expect(
      screen.getByText(/NGSolve 3D Steady-State Heat Conduction Solver/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Reproducible Python Script \(simulation.py\)/i)
    ).toBeInTheDocument();
  });
});
