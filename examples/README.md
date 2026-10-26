# PDE Simulation Studio — Sample Models & Reproducible Python Scripts

This directory contains canonical `v1.0.0` simulation models (`model.json`) paired with their generated, standalone **NGSolve / Netgen OpenCASCADE** Python simulation scripts (`simulation.py`).

## Included Examples

1. **[`linear_conduction_benchmark/`](./linear_conduction_benchmark/)**
   - **Physics**: 1D analytical verification in a 3D cuboid ($1.0\text{ m} \times 0.4\text{ m} \times 0.4\text{ m}$, $k = 100\text{ W/(m\cdot K)}$, $Q = 0$).
   - **Boundaries**: `X_MIN` at $400\text{ K}$ (Dirichlet), `X_MAX` at $300\text{ K}$ (Dirichlet), remaining 4 faces `insulated`.
   - **Analytical Solution**: $T(x) = 350 - 100 x\text{ K}$, $T_{\text{mean}} = 350.0\text{ K}$, conductive heat rate $Q_{\text{out, X\_MAX}} = +1600.0\text{ W}$.

2. **[`copper_convective_heatsink/`](./copper_convective_heatsink/)**
   - **Physics**: 3D Copper C11000 block ($1.2\text{ m} \times 0.7\text{ m} \times 0.5\text{ m}$, $k = 401\text{ W/(m\cdot K)}$, internal heating $Q = 1500\text{ W/m}^3$).
   - **Boundaries**:
     - `X_MIN`: Dirichlet fixed temperature $T_0 = 373.15\text{ K}$
     - `X_MAX`: Robin convection $h = 25\text{ W/(m}^2\cdot\text{K)}$, $T_\infty = 293.15\text{ K}$
     - `Y_MAX`: Neumann outward heat flux $q_{\text{out}} = -500\text{ W/m}^2$ (inward heating)
     - `Y_MIN`, `Z_MIN`, `Z_MAX`: Insulated ($q_{\text{out}} = 0$)

## Running an Example Directly

```bash
python examples/linear_conduction_benchmark/simulation.py
python examples/copper_convective_heatsink/simulation.py
```

Or import any `model.json` directly into the **PDE Simulation Studio** web interface via the **Import JSON** toolbar button.
