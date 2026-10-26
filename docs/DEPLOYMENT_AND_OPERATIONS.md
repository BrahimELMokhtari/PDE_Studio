# Deployment, Security, Backup, Recovery & Scaling Guide

**Application**: PDE Simulation Studio (`v3.0.0`)

---

## 1. Production Architecture on Render

PDE Simulation Studio is architected for zero-ephemeral-state cloud deployment via [`render.yaml`](../render.yaml):

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Render Static Site (CDN / Edge)                      │
│     React 18 + TypeScript + Three.js WebGL + VTU/Colormap Post-Proc   │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │ HTTPS + OIDC Bearer JWT
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│             Render Web Service (FastAPI API Container)                  │
│   OIDC Auth (Fail-Closed) • Rate Limiter • Quota Guard • REST Routes    │
└──────────┬────────────────────────┬──────────────────────────┬──────────┘
           │                        │                          │
           ▼                        ▼                          ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌───────────────────────┐
│  Render PostgreSQL  │  │  Render Key Value   │  │ S3-Compatible Storage │
│  Projects & Jobs DB │  │   Redis RQ Queue    │  │  VTU, CSV, ZIP, .py   │
└─────────────────────┘  └──────────┬──────────┘  └───────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│         Render Background Worker (Numerical Engine Container)           │
│     NGSolve + Netgen OpenCASCADE 3D Tetrahedral FEM (`Dockerfile.worker`)│
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Render Deployment Prerequisites & Step-by-Step Instructions

### Prerequisites
1. A **Render** account (`https://render.com`) connected to your GitHub repository.
2. An **S3-compatible Object Storage bucket** (AWS S3, Cloudflare R2, DigitalOcean Spaces, or MinIO) for durable storage of `.vtu`, `.csv`, `simulation.py`, and `.zip` simulation artifacts.
3. An **OIDC-compatible Identity Provider** (Auth0, Clerk, Okta, AWS Cognito, Keycloak, or Google Identity) providing a `JWKS` endpoint (`OIDC_JWKS_URL`), issuer URL (`OIDC_ISSUER_URL`), and audience (`OIDC_AUDIENCE`).

### Step-by-Step Render Blueprint Deployment
1. Push the repository containing [`render.yaml`](../render.yaml), [`backend/Dockerfile`](../backend/Dockerfile), and [`backend/Dockerfile.worker`](../backend/Dockerfile.worker) to GitHub.
2. In the Render Dashboard, click **New + -> Blueprint** and select the repository.
3. Render will detect `render.yaml` and provision:
   - `pde-simulation-studio-frontend` (Static Site)
   - `pde-simulation-studio-api` (Docker Web Service)
   - `pde-simulation-studio-worker` (Docker Background Worker)
   - `pde-simulation-studio-redis` (Render Key Value)
   - `pde-simulation-studio-db` (Render PostgreSQL)
4. Provide the prompted secret environment variables (`sync: false`):
   - `VITE_API_BASE_URL`: Public URL of `pde-simulation-studio-api` (e.g. `https://pde-simulation-studio-api.onrender.com`).
   - `CORS_ORIGINS`: Public URL of `pde-simulation-studio-frontend`.
   - `OIDC_ISSUER_URL`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL`: Your OIDC provider configuration.
   - `S3_ENDPOINT_URL`, `S3_BUCKET_NAME`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION`: Your S3-compatible bucket credentials.
5. Verify deployment health by querying `GET /api/health` on the API service and confirming:
   - `"database": {"backend": "postgresql", "connected": true}`
   - `"storage": {"backend": "s3", "connected": true}`
   - `"security": {"auth_required": true, "oidc_configured": true}`

---

## 3. Estimated Cloud Resource Requirements

| Component | Recommended Render Plan | vCPU / RAM | Workload Characteristics |
| :--- | :--- | :--- | :--- |
| **Frontend (`static`)** | Free / Starter Static | CDN Edge | Serves static JS/CSS/WebGL assets; 3D rendering runs on client GPU. |
| **Backend API (`web`)** | Starter / Standard | 1 vCPU / 2 GB RAM | Lightweight async FastAPI I/O, Pydantic validation, PostgreSQL & S3 metadata queries. |
| **Numerical Worker (`worker`)** | Standard / Pro | 2–4 vCPU / 4–8 GB RAM | CPU- and memory-intensive 3D OpenCASCADE meshing and Sparse Cholesky factorization (`ngsolve`). A 50,000-tetrahedra P2 solve uses ~1.2 GB RAM; 250,000 tetrahedra P1 uses ~2.5 GB RAM. |
| **PostgreSQL (`db`)** | Basic-256mb / Pro-4gb | Shared / 4 GB RAM | Stores canonical JSON models, job logs, and scalar summaries (large mesh files are offloaded to S3). |
| **Redis (`redis`)** | Starter (256 MB) | 256 MB RAM | Holds active RQ job pointers and worker heartbeats (`maxmemoryPolicy: noeviction`). |

---

## 4. Security & Commercial Readiness Controls

1. **Fail-Closed Production Authentication**:
   - When `APP_ENV=production` or `AUTH_REQUIRED=true`, [`get_current_principal`](../backend/app/security/auth.py) rejects any request lacking a valid OIDC Bearer JWT (`HTTP 401`) and returns `HTTP 503 Service Unavailable` if OIDC credentials are unconfigured.
2. **Multi-Tenant Ownership & Authorization**:
   - Every project and simulation job record stores `owner_id` (indexed in both SQLite and PostgreSQL). Users can only list, view, export, or delete their own projects and jobs (`HTTP 403 Forbidden` on cross-tenant access).
3. **Isolated Numerical Execution**:
   - The RQ worker executes **only** [`execute_trusted_fem_simulation`](../backend/app/jobs/rq_tasks.py) using structured Pydantic-validated `CanonicalSimulationModel` parameters. User-supplied strings are never passed to `eval()`, `exec()`, or shell subprocesses.
4. **Rate Limiting, Upload Size & Storage Quotas**:
   - [`SecurityAndQuotaMiddleware`](../backend/app/security/middleware.py) enforces a sliding-window rate limit (`RATE_LIMIT_PER_MINUTE`, `HTTP 429`), request body cap (`MAX_REQUEST_BODY_BYTES`, `HTTP 413`), and hardened headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`).
   - Per-user quotas (`MAX_PROJECTS_PER_USER`, `MAX_SIMULATION_JOBS_PER_USER`, `MAX_STORAGE_BYTES_PER_USER`) are enforced before job submission and exposed via `GET /api/simulations/quotas`.

---

## 5. Backup, Disaster Recovery & Scaling

### Backup & Recovery
- **PostgreSQL Database**:
  - Enable Render PostgreSQL automated daily snapshots and Point-in-Time Recovery (PITR).
  - Manual logical backup command:
    ```bash
    pg_dump --format=custom --no-owner --no-acl "$DATABASE_URL" -f pde_studio_backup_$(date +%F).dump
    ```
  - Restore command:
    ```bash
    pg_restore --clean --if-exists --no-owner -d "$DATABASE_URL" pde_studio_backup_YYYY-MM-DD.dump
    ```
- **S3 Artifact Storage**:
  - Enable S3 Bucket Versioning and Lifecycle Rules (e.g., expire non-current object versions after 30 days).
  - Even if S3 artifacts are lost, every `simulation_jobs` row in PostgreSQL retains the exact `CanonicalSimulationModel` JSON and `SimulationResultSummary`, allowing deterministic regeneration of `simulation.py`, `.vtu`, and `.csv` at any time.

### Independent Horizontal Scaling
- **API Tier**: Stateless; scale horizontally from 1 to $N$ instances behind Render's load balancer without coordination overhead.
- **Numerical Worker Tier**: Scale `pde-simulation-studio-worker` replicas independently based on Redis queue depth (`pde_simulations`). Each worker processes jobs with `SIGTERM` graceful shutdown and `JOB_TIMEOUT_SECONDS` execution bounds.

---

## 6. Known Limitations & Future Roadmap

1. **Single-Domain Parametric Cuboid Geometry**:
   - The 3D studio currently models single-material isotropic rectangular cuboids (`X_MIN..Z_MAX`) with arbitrary 3D scaling, translation, and Euler rotation. Multi-body boolean CSG assemblies and STEP/IGES CAD file import are planned for future releases.
2. **Steady-State Isotropic Linear Heat Conduction**:
   - Solves $-\nabla \cdot (k \nabla T) = Q$ with constant isotropic thermal conductivity $k$. Temperature-dependent nonlinear $k(T)$, transient heat transfer ($\rho c_p \frac{\partial T}{\partial t}$), and radiation ($T^4$) boundary conditions are not yet enabled.
3. **Inline WebGL Surface Mesh Decimation**:
   - To keep JSON responses fast, inline WebGL surface meshes are capped at `MAX_INLINE_SURFACE_TRIANGLES` (default `15,000` triangles), while the full-resolution 3D tetrahedral volume mesh is exported to `solution.vtu` for ParaView / `vtk.js` inspection.
