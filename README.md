# PDE Simulation Studio (Phase 1, 2 & 3 Complete)

A commercial-grade 3D CAD/CAE pre-processor, **NGSolve / Netgen OpenCASCADE** 3D tetrahedral Finite Element Method (FEM) solver, and scientific post-processing platform for steady-state heat conduction:

$$-\nabla \cdot (k \nabla T) = Q \quad \text{in } \Omega \subset \mathbb{R}^3$$

---

## Key Capabilities

### 1. Interactive 3D CAD/CAE Pre-Processor & Semantic Face Engine
- **Parametric 3D Rectangular Cuboid**: Real-time dimensions (`length_x`, `length_y`, `length_z`), translation (`position`), and Euler orientation (`rotation_deg`) in `m`, `cm`, or `mm`.
- **Stable Semantic Boundary Tagging (`X_MIN`, `X_MAX`, `Y_MIN`, `Y_MAX`, `Z_MIN`, `Z_MAX`)**: Never relies on unstable triangle indices. Boundary tags are preserved from the Three.js GUI through OpenCASCADE (`netgen.occ`) into `ngsolve.Mesh.GetBoundaries()`.
- **Boundary Conditions**: Dirichlet fixed temperature ($T = T_0$), Neumann outward heat flux ($-\mathbf{n} \cdot k \nabla T = q_{\text{out}}$), Robin convection ($-\mathbf{n} \cdot k \nabla T = h(T - T_\infty)$), and Insulated ($\mathbf{n} \cdot k \nabla T = 0$).

### 2. Validated 3D NGSolve Tetrahedral FEM Engine & Reproducible Python Packaging
- **3D OpenCASCADE Meshing & $H^1$ FEM**: Generates 3D tetrahedral meshes with configurable `max_element_size` ($h_{\max}$) and polynomial order $p \in \{1, 2, 3\}$.
- **Scientific Validation**: Verified against analytical 1D linear conduction, quadratic internal heat generation ($Q > 0$), outward flux sign conventions, SI unit conversions (`mm`/`cm`/`m`, `°C`/`K`), and ill-posed/singular problem detection.
- **Reproducible Python Export**: Generates standalone `simulation.py` scripts and `.zip` packages (`simulation.py`, `model.json`, `solution.vtu`, `nodal_results.csv`, `boundary_summary.csv`, `requirements.txt`, `README.md`).

### 3. Scientific Post-Processing & Exports
- **Interactive 3D Temperature Field Visualization**: Renders the computed 3D FEM temperature distribution in Three.js with 5 scientific colormaps (`Viridis`, `Inferno`, `CoolWarm`, `Plasma`, `Jet`), scalar legend (`Min`, `Mean`, `Max`), and element wireframe overlay.
- **Interactive 3D Cross-Section Slicing & Clipping Planes**: Slice the 3D domain along the `X`, `Y`, or `Z` axis with a live offset slider (`-45%` to `+45%`) and flip toggle, displaying both the hardware-clipped 3D shell and an interpolated interior cross-sectional contour slice.
- **Convergence & Mesh Quality Telemetry**: Displays linear solver relative residual $\|K u - f\|_2 / \|f\|_2$, global energy conservation residual, stage timings, and surface triangle aspect ratios.
- **VTK/VTU & CSV Exports**: Direct one-click export of ASCII VTK XML UnstructuredGrid (`solution.vtu`) compatible with **ParaView** and `vtk.js`, plus `nodal_results.csv` and `boundary_summary.csv`.

### 4. Production Persistence, Security & Render Cloud Readiness
- **Database Abstraction**: `SQLiteProjectRepository` / `SQLiteSimulationJobRepository` for local development and `PostgresProjectRepository` / `PostgresSimulationJobRepository` (`psycopg` v3) for production PostgreSQL.
- **Durable Object Storage Abstraction**: `LocalFilesystemStorage` for local development and `S3CompatibleStorage` (`boto3`) for production S3/R2/MinIO storage.
- **Fail-Closed OIDC Authentication & Multi-Tenant Authorization**: Configurable OIDC JWT validation (`PyJWT`) that fails closed in production (`APP_ENV=production`), per-user `owner_id` isolation, sliding-window rate limiting (`HTTP 429`), upload size limits (`HTTP 413`), and per-user resource quotas (`GET /api/simulations/quotas`).

---

## Quick Start (Local Development)

### 1. Start the Backend API (FastAPI + NGSolve)
```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2. Start the Frontend Studio (React + Three.js + Vite)
```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```
Open `http://127.0.0.1:5173` in your browser.

### 3. Run Automated Tests
```powershell
# Backend unit, scientific validation, security, and E2E workflow tests:
cd backend
python -m pytest -v

# Frontend unit, VTU parser, and UI component tests + production build:
cd ../frontend
npm test
npm run build
```

---

## Documentation & Compliance Artifacts

- **Deployment, Backup, Recovery & Scaling Guide**: [`docs/DEPLOYMENT_AND_OPERATIONS.md`](docs/DEPLOYMENT_AND_OPERATIONS.md)
- **Render Cloud Blueprint**: [`render.yaml`](render.yaml)
- **Third-Party License Audit**: [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md)
- **CycloneDX Software Bill of Materials (SBOM)**: [`sbom.cdx.json`](sbom.cdx.json)
- **GitHub Actions CI**: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)
