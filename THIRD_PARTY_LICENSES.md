# Third-Party Open Source Licenses & Commercial Compatibility Audit

**Application**: PDE Simulation Studio (`v3.0.0`)
**Audit Date**: 2026-10-25
**Target Deployment Model**: Commercial SaaS / Cloud Web Application & Downloadable Simulation Packages

---

## 1. Executive Commercial Compatibility Summary

All direct and transitive dependencies in **PDE Simulation Studio** (`backend/` and `frontend/`) have been audited for commercial SaaS operation and software distribution:

1. **Zero AGPL / GPLv3 Strong-Copyleft Dependencies**: Neither the frontend bundle nor the backend/worker runtime links against GPL or AGPL libraries.
2. **Permissive Core Stack (`MIT`, `BSD-3-Clause`, `Apache-2.0`, `ISC`)**: FastAPI, Starlette, Pydantic, Uvicorn, NumPy, SciPy, Redis-py, RQ, Boto3, PyJWT, React, Three.js, and Vite are all permissively licensed with no copyleft obligations.
3. **Weak-Copyleft Numerical & Database Libraries (`LGPL-2.1`, `MPL-2.0`)**:
   - **NGSolve (`ngsolve`), Netgen (`netgen-mesher`), and OpenCASCADE (`netgen-occt`)** are licensed under **LGPL-2.1**.
   - **Psycopg 3 (`psycopg`, `psycopg-binary`)** is licensed under **MPL-2.0** (with `libpq` under the PostgreSQL License).
   - **Commercial SaaS Impact**: Running `ngsolve`, `netgen`, and `psycopg` on backend cloud servers/workers (Render Web Services and Background Workers) does **not** trigger distribution obligations under LGPL-2.1 or MPL-2.0.
   - **Distribution Obligations (if distributing container images or desktop bundles)**:
     - Keep `ngsolve`, `netgen-mesher`, and `netgen-occt` as dynamically loaded Python wheels / shared libraries (`.so` / `.dll` / `.pyd`) without modifying their C++ source code, or provide any modifications to those specific libraries under LGPL-2.1.
     - Retain copyright and license notices (this file and `sbom.cdx.json`) in distributed artifacts.

---

## 2. Backend Python Dependencies & Transitive Dependencies

| Package | Verified Version | SPDX License | Category | Commercial / Distribution Obligations |
| :--- | :--- | :--- | :--- | :--- |
| `fastapi` | `0.135.3` | `MIT` | Direct (API) | Retain copyright notice in redistributions. |
| `starlette` | `1.0.0` | `BSD-3-Clause` | Transitive (API) | Retain copyright notice in redistributions. |
| `uvicorn` | `0.44.0` | `BSD-3-Clause` | Direct (ASGI Server) | Retain copyright notice in redistributions. |
| `pydantic` | `2.13.0` | `MIT` | Direct (Validation) | Retain copyright notice in redistributions. |
| `pydantic_core` | `2.45.0` | `MIT` | Transitive (Rust Core) | Retain copyright notice in redistributions. |
| `python-dotenv` | `1.2.2` | `BSD-3-Clause` | Direct (Config) | Retain copyright notice in redistributions. |
| `ngsolve` | `6.2.2608` | `LGPL-2.1-only` | Direct (3D FEM Solver) | Weak copyleft. Dynamically imported via Python wheel. Do not statically link proprietary C++ into `libngsolve`. |
| `netgen-mesher` | `6.2.2608` | `LGPL-2.1-only` | Direct (3D Mesher) | Weak copyleft. Dynamically imported via Python wheel. |
| `netgen-occt` | `7.8.1` | `LGPL-2.1-only` | Transitive (CAD Kernel) | OpenCASCADE Technology 3D B-Rep kernel. Dynamically linked shared libraries. |
| `mkl` / `tbb` | `2025.3` / `2022.3` | `Intel-Simplified` / `Apache-2.0` | Transitive (Linear Algebra) | Redistributable binary runtime libraries under Intel Simplified Software License & Apache-2.0. |
| `numpy` | `2.5.4` | `BSD-3-Clause` | Direct (Numerical) | Retain copyright notice in redistributions. |
| `scipy` | `1.18.1` | `BSD-3-Clause` | Direct (Scientific) | Retain copyright notice in redistributions. |
| `redis` | `8.1.0` | `MIT` | Direct (Queue Client) | Retain copyright notice in redistributions. |
| `rq` | `2.12.0` | `BSD-2-Clause` | Direct (Worker Queue) | Retain copyright notice in redistributions. |
| `fakeredis` | `2.40.0` | `BSD-3-Clause` | Direct (Dev/Test Queue) | Retain copyright notice in redistributions. |
| `PyJWT` | `2.15.1` | `MIT` | Direct (OIDC Auth) | Retain copyright notice in redistributions. |
| `boto3` | `1.43.118` | `Apache-2.0` | Direct (S3 Storage) | Retain Apache-2.0 notice. |
| `botocore` | `1.43.118` | `Apache-2.0` | Transitive (S3 Core) | Retain Apache-2.0 notice. |
| `psycopg` | `3.3.6` | `MPL-2.0` | Direct (PostgreSQL) | File-level weak copyleft; unmodified PyPI package used via standard DB-API. |
| `psycopg-binary` | `3.3.6` | `MPL-2.0` | Direct (PostgreSQL) | Bundles `libpq` (PostgreSQL License). |
| `pytest` | `9.1.1` | `MIT` | Dev/Test | Development and CI testing only. |
| `httpx` | `0.28.1` | `BSD-3-Clause` | Dev/Test | Development and CI testing only. |

---

## 3. Frontend JavaScript / TypeScript Dependencies

| Package | Verified Version | SPDX License | Category | Commercial / Distribution Obligations |
| :--- | :--- | :--- | :--- | :--- |
| `react` | `18.3.1` | `MIT` | Direct (UI Runtime) | Bundled in static site; retain MIT notice. |
| `react-dom` | `18.3.1` | `MIT` | Direct (UI Runtime) | Bundled in static site; retain MIT notice. |
| `three` | `0.164.1` | `MIT` | Direct (3D WebGL Engine) | Bundled in static site; retain MIT notice. |
| `typescript` | `5.4.5` | `Apache-2.0` | Build Toolchain | Build-time compiler only. |
| `vite` | `5.2.11` | `MIT` | Build Toolchain | Build-time bundler only. |
| `vitest` | `1.6.0` | `MIT` | Dev/Test | Test runner only; not included in production bundle. |
| `@testing-library/react` | `15.0.7` | `MIT` | Dev/Test | Test utility only. |
| `jsdom` | `24.0.0` | `MIT` | Dev/Test | Test DOM environment only. |

---

## 4. License Notice Attributions

### NGSolve & Netgen (`LGPL-2.1`)
- Copyright (C) Joachim Schöberl and NGSolve/Netgen contributors (`https://ngsolve.org`).
- Licensed under the GNU Lesser General Public License v2.1 (`https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html`).

### OpenCASCADE Technology (`LGPL-2.1`)
- Copyright (C) Open CASCADE SAS (`https://dev.opencascade.org`).
- Licensed under the GNU Lesser General Public License v2.1.

### FastAPI, Pydantic, Three.js, React (`MIT`)
- Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files, to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, subject to the standard MIT copyright notice.

### NumPy, SciPy, Starlette, Uvicorn, RQ (`BSD-2-Clause` / `BSD-3-Clause`)
- Redistribution and use in source and binary forms, with or without modification, are permitted provided that the standard BSD copyright notices and disclaimers are retained.
