# OpenFOAM Portfolio

A growing collection of CFD cases I've built while teaching myself OpenFOAM. Each
case is a self-contained study of a different class of physics — external
aerodynamics, buoyancy-driven multiphase mixing, and (as ongoing work) reacting
flow in a gas turbine combustor. The goal is to demonstrate hands-on competence
with the OpenFOAM workflow end to end: meshing, boundary conditions, turbulence,
numerical scheme selection, parallel execution, and post-processing.

---

## Motivation

I'm a self-taught OpenFOAM user working toward a career in CFD, propulsion, and
energy. I started with the standard tutorials, but I learn best by building
cases from a blank directory and having to reason through every dictionary entry
myself — why a particular turbulence model, why a given time scheme, what makes
a solve diverge and how to stabilise it.

The two cases in this repository are practice studies chosen to cover very
different physics with a common advanced ingredient: **scale-resolving turbulence
(DES/LES-family models)**. They were a stepping stone toward my current flagship
project (below), and they document where I am on the learning curve — including
the honest simplifications a self-taught engineer makes on the way up.

### Flagship project (in progress, separate repo)

Alongside this portfolio I'm developing a **micro gas turbine (MGT) combustor**
simulation using `rhoReactingFoam` — a compressible reacting
solver with a PaSR (Partially Stirred Reactor) combustion model, a 9-species
Mueller H₂/O₂ mechanism, and TDAC/ISAT chemistry tabulation, running on 64 cores
under SLURM on an HPC cluster. That project is what motivated me to go deeper on
turbulence modelling, LTS/pseudo-transient stabilisation, staged relaxation
strategies, and robust restart workflows — much of which I first practised on the
smaller cases here. It's a substantially larger and messier engineering problem
(cold-start pressure collapse, turbulence blow-up, chemistry stiffness), and it's
still ongoing.

---

## Cases

### 1. NACA 0012 Airfoil — Detached Eddy Simulation

Flow separation and wake dynamics over a NACA 0012 aerofoil at a high angle of
attack, resolved with a DES turbulence model.

| | |
|---|---|
| **Solver** | `pimpleFoam` (transient, incompressible) |
| **Turbulence** | `kOmegaSSTDES` (LES simulation type, cube-root-volume filter) |
| **Angle of attack** | 15° |
| **Freestream** | U∞ = 15 m/s, ν = 1.5×10⁻⁵ m²/s (chord Re ≈ 10⁶) |
| **Mesh** | 9,600 cells, structured `blockMesh` |
| **Time scheme** | `backward` (2nd-order, required for DES) |
| **Run** | endTime 8 s, adaptive Δt (maxCo = 1.0) |
| **Post-processing** | `forceCoeffs` (lift/drag), `solverInfo` residuals |

**What it demonstrates:** transient scale-resolving turbulence, adaptive
time-stepping under a Courant constraint, a 2nd-order time scheme chosen
specifically because DES demands it, and force-coefficient extraction on the
aerofoil surface with correctly resolved lift/drag directions for 15° AoA.

> **Honest note:** this mesh is a single cell thick with `empty` front/back
> patches, i.e. it is run quasi-2D. Formally, DES is a three-dimensional method —
> a strictly correct study would use a spanwise-extruded 3D mesh. Running it
> quasi-2D here was a deliberate learning-stage / compute simplification to focus
> on the solver setup and time-scheme behaviour; extending it to a true 3D
> spanwise domain is a planned next step.

📹 `NACA0012-VelocityDistribution.mp4` — velocity field showing wake shedding.

---

### 2. Rayleigh–Taylor Instability — Multiphase DES

The classic Rayleigh–Taylor instability: a heavier fluid initialised above a
lighter one, driven unstable by gravity, developing into interpenetrating
fingers and eventually turbulent mixing.

| | |
|---|---|
| **Solver** | `interFoam` (VOF two-phase, incompressible) |
| **Turbulence** | `kOmegaSSTIDDES` (Improved Delayed DES, IDDES filter) |
| **Phases** | heavy (ρ = 1000 kg/m³) over light (ρ = 111 kg/m³), Atwood ≈ 0.8 |
| **Surface tension** | σ = 0.03 N/m |
| **Gravity** | 9.81 m/s² downward |
| **Mesh** | 128,000 cells (3D), structured `blockMesh` |
| **Time scheme** | `Euler`, adaptive Δt (maxCo = 1.0, maxAlphaCo = 0.5) |
| **Run** | endTime 5 s, `alpha.heavy` volume tracked via `volFieldValue` |

**What it demonstrates:** volume-of-fluid interface capturing with a bounded
interface Courant number, a large density ratio between phases, surface-tension
modelling, and an IDDES turbulence closure on a genuinely 3D mesh. Tracking the
integrated heavy-phase volume is a simple conservation sanity-check on the VOF
transport.

📹 `RayleighTaylorDES.mp4` — evolution of the interface into mixing fingers.

---

## Repository layout

```
OpenFOAM-Portfolio/
├── NACA0012-DES/            # Aerofoil DES case
│   ├── 0/                   # Initial & boundary conditions (U, p, k, omega, nut)
│   ├── constant/            # transportProperties, turbulenceProperties, polyMesh
│   ├── system/              # blockMeshDict, controlDict, fvSchemes, fvSolution, decomposeParDict
│   └── *.mp4                # Result animation
└── Rayleigh-Taylor-DES/     # Multiphase DES case
    ├── 0/                   # ICs/BCs (U, p_rgh, alpha.heavy, k, omega, nut)
    ├── constant/            # transportProperties (2 phases), g, turbulenceProperties, polyMesh
    ├── system/              # blockMeshDict, controlDict, fvSchemes, fvSolution, decomposeParDict
    └── *.mp4                # Result animation
```

Each case follows the standard OpenFOAM `0 / constant / system` structure and is
fully self-contained.

---

## Running a case

Each case is a standard OpenFOAM case directory. From inside a case folder:

```bash
blockMesh                       # generate the mesh
# (Rayleigh–Taylor also needs setFields if re-initialising the interface)
decomposePar                    # partition for parallel run
mpirun -np <N> <solver> -parallel   # e.g. pimpleFoam or interFoam
reconstructPar                  # merge parallel results
```

Then load the case in ParaView (`paraFoam` or `touch case.foam`) to visualise.

**Tested with OpenFOAM v2412 / v2512 (openfoam.com / ESI).**

---

## Skills demonstrated across the portfolio

- **Solvers:** `pimpleFoam` (transient incompressible), `interFoam` (VOF
  multiphase), and `rhoReactingFoam` (compressible reacting, flagship project).
- **Turbulence modelling:** the DES/LES family — `kOmegaSSTDES`,
  `kOmegaSSTIDDES` — including choosing appropriate LES filter widths
  (cube-root-volume vs IDDES) and the time schemes these models require.
- **Multiphase:** VOF interface capturing with large density ratios and surface
  tension.
- **Numerics:** Courant-limited adaptive time-stepping, 2nd-order transient
  schemes, and solver/relaxation choices for stability.
- **Workflow:** structured `blockMesh` generation, boundary-condition setup,
  parallel decomposition and execution, function-object post-processing (force
  coefficients, residuals, volume integrals), and result animation.
- **HPC & robustness (flagship):** SLURM job scripting, staged relaxation ramps,
  LTS/pseudo-transient control, and restart/checkpoint workflows for long runs.

---

## About me

Self-taught CFD engineer focused on propulsion and energy applications, currently
working on hydrogen combustion in gas turbines with OpenFOAM. I'm actively
looking for opportunities to apply and grow these skills.

**GitHub:** [olichapman05](https://github.com/olichapman05)
