# Circular Center Estimation

Minimal reference implementation for the paper **Accurate Measurement of 3D and
2D Circular Centers With Application to LiDAR-Camera Extrinsic Calibration**.

The repository contains only the reusable contributions:

- normalized conformal-geometric-algebra (CGA) fitting of a 3D circle;
- deterministic CGA-RANSAC for noisy and outlier-contaminated 3D points;
- perspective-aware recovery of the two possible image projections of a
  physical circular center;
- homography-based or quasi-RANSAC disambiguation of the two 2D candidates.

It intentionally excludes large-scale evaluation infrastructure, Gazebo and
ROS capture pipelines, real datasets, paper-figure generation, and historical
prototypes. Those components are not required to use or verify the algorithms.

## Repository layout

```text
cpp/                  Header-only C++ implementation of normalized 3D CGA fitting
python/src/           Python package for 3D and 2D circular-center estimation
examples/             Small, readable examples of the public APIs
experiments/          One deterministic synthetic benchmark for basic validation
python/tests/         Numerical and API regression tests
```

All 3D coordinates are metric. Image coordinates are pixels. The 2D estimator
accepts only a rectified contour or ellipse together with the corresponding
rectified intrinsic matrix. Raw distorted contours are not conics and must be
undistorted before calling the estimator.

## Installation

Ubuntu 20.04 or newer is recommended.

### Python

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[vision,dev]'
python -m pytest -q
```

NumPy is sufficient for the 3D core. OpenCV is installed by the `vision` extra
and is required for contour rectification, ellipse fitting, and quasi-RANSAC.

### C++

The C++ core requires C++17, CMake 3.16+, and Eigen 3.3+.

```bash
cmake -S . -B build -G Ninja \
  -DCCC_BUILD_TESTS=ON \
  -DCCC_BUILD_EXAMPLES=ON
cmake --build build
cmake --build build --target test
./build/cpp/circular_center_fit_circle
```

## Minimal examples

Run both the robust 3D fit and the perspective-aware 2D candidate estimator:

```bash
python examples/minimal_demo.py
```

Run a small deterministic Monte Carlo validation and write a JSON summary:

```bash
python experiments/basic_experiments.py \
  --trials 100 \
  --seed 2025 \
  --output outputs/basic_results.json
```

The basic experiment compares direct CGA with CGA-RANSAC under outliers,
compares the fitted ellipse center with the proposed 2D candidate set, and
checks quasi-RANSAC pose recovery. It is a compact functional validation, not
the full internal evaluation suite.

## Python API

```python
from circular_center.center3d import fit_cga_circle, fit_circle_ransac
from circular_center.center2d import (
    fit_quasi_ransac,
    get_ellipse_polynomial_coeff,
    refine_projected_center,
    select_projected_center_by_homography,
)
```

`fit_cga_circle` and `fit_circle_ransac` return `CircleFitResult`, including the
center, radius, unoriented normal, residuals, inliers, status, condition number,
iteration count, and elapsed time. `refine_projected_center` returns both 2D
candidates because one projected ellipse is geometrically ambiguous.

## License

Original code in this public branch is licensed under Apache-2.0. No GPL code,
AAMED source, dataset, or vendored third-party implementation is included. See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for separately installed
dependencies.
