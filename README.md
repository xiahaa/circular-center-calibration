# Circular Center Calibration

Modular reference implementation for 3D/2D circular-center measurement and
LiDAR-camera extrinsic calibration.

## Installation

### Conda: all features (recommended)

```bash
conda env create -f environment.yml
conda activate circular-center-calibration
```

### Pip

From the repository root:

```bash
python -m pip install -e '.[all]'
```

### PCL SACMODEL

The PCL baseline uses C++. After the Conda installation, build it once:

```bash
cmake -S . -B build -G Ninja -DCCC_BUILD_PCL_BASELINE=ON
cmake --build build
```

Python experiments load the library automatically. Other methods do not need
this step. Set `CIRCULAR_CENTER_PCL_LIBRARY` only for a custom library path.

## Run the real-world experiment

The outer experiment YAML intentionally contains only the dataset and method
choices:

```yaml
schema_version: 1
experiment: qualitative_realworld
datasets: [orbbec_livox_lab, orbbec_livox_office]
methods:
  2d: "Refined Center"
  3d: "CGA-RANSAC"
  ambiguity: "Quasi-RANSAC"
```

Run a ten-frame smoke test per dataset, or omit `--max-frames` for all frames:

```bash
circular-center-run \
  configs/experiments/qualitative_realworld.yaml \
  --max-frames 10
```

Results are written to `outputs/qualitative_realworld/summary.json` together
with rectified qualitative overlays. Each failed frame remains in the summary
with its preprocessing or fitting error.

The experiment expects `data/orbbec_livox_lab` and
`data/orbbec_livox_office`, each containing matching `img/*.png` and
`pcd/*.pcd` files plus `dataset.yaml` and `camera_info.yaml`. The released data
are available from [Google Drive](https://drive.google.com/drive/folders/1HV0tRHV02f392ATqT-y375Ww-NH_-186?usp=drive_link).

## Pluggable methods

Method names match the paper. The current catalog contains:

| Stage | Available names |
| --- | --- |
| 2D | `Ellipse Center`, `Mass Center`, `Refined Center` |
| 3D | `CGA`, `CGA-RANSAC`, `PCL SACMODEL` |
| Ambiguity | `Homography Validation`, `Quasi-RANSAC` |

`PCL SACMODEL` calls PCL's `SACSegmentation` with `SACMODEL_CIRCLE3D` and
`SAC_RANSAC` through the optional C++ shared library; it is not a Python
reimplementation.

Each method entry in an outer experiment YAML accepts one name, a list of names,
or `null`. For example, a 3D-only comparison can select all paper baselines
without dummy 2D methods:

```yaml
methods:
  2d: null
  3d: ["CGA", "CGA-RANSAC", "PCL SACMODEL"]
  ambiguity: null
```

The runner normalizes these values to tuples. Experiment code can iterate over
all selected methods, or explicitly require exactly one method when its protocol
does not support comparisons.

A *fast CI configuration* is a deliberately reduced experiment profile, such as
one seed, one parameter value, and one or two frames. It only verifies that data
generation, method dispatch, metrics, and output writing remain connected. It
must not be used as a paper result; the full paper profile retains the published
trial counts and parameter grid.

To add a method:

1. implement the corresponding interface under `src/circular_center/methods`;
2. add one central YAML file under `configs/methods/2d`, `3d`, or `ambiguity`;
3. select its exact `name` in an experiment YAML.

No experiment code or generic runner change is required. Constructor defaults
belong to the central method YAML. Dataset-specific extraction, detection, and
evaluation settings belong to the relevant `experiments/<name>` directory.

## Repository layout

```text
src/circular_center/
  interfaces/             Stable method contracts
  methods/                Reusable 2D, 3D, and ambiguity plugins
  registry/               Central YAML discovery and dynamic loading
  experiments/            Generic experiment configuration and runner
configs/
  methods/                One centrally managed YAML per method
  experiments/            Small outer experiment selections
experiments/
  qualitative_realworld/  Experiment-owned extraction, detection, evaluation
  basic_experiments.py    Deterministic synthetic regression experiment
tests/                     Core, plugin, and experiment-system tests
cpp/                       Header-only C++ 3D implementation and tests
```

The pre-refactor documentation is preserved in
[`README.legacy.md`](README.legacy.md).

## Core API

The original low-level API remains available for compatibility:

```python
from circular_center.center3d import fit_cga_circle, fit_circle_ransac
from circular_center.center2d import (
    fit_quasi_ransac,
    get_ellipse_polynomial_coeff,
    refine_projected_center,
    select_projected_center_by_homography,
)
```

All 3D coordinates are metric and image coordinates are pixels. The 2D methods
operate on rectified contours/ellipses and the matching rectified intrinsic
matrix; raw distorted contours must be undistorted first.

## Reproducibility and license

`tools/core_baseline_probe.py` captures deterministic core outputs and timing
statistics. Pre-refactor reference artifacts are stored in
`benchmarks/baselines/` and are used to audit structural changes.

Original code is licensed under Apache-2.0. See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for separately installed
dependencies.
