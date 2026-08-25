# Synthetic experiments

This directory contains a deterministic rewrite of the synthetic experiments
used while developing the paper. It replaces hard-coded data paths and
duplicated algorithm code. PCL remains an optional, separately installed
baseline and is never vendored into this repository.

The runner covers three studies:

- 3D circle fitting under Gaussian noise, limited visible arcs, outliers, and
  the four legacy stress scenarios, with an optional PCL RANSAC baseline;
- 2D projected-center estimation under contour noise and circle-plane tilt,
  including two-circle homography disambiguation;
- camera-pose recovery using ellipse centers, oracle candidates, and the
  released quasi-RANSAC implementation.

Install the experiment dependencies and run the paper profile:

```bash
python -m pip install -e '.[experiments,dev]'
python experiments/synthetic/run_experiments.py \
  --profile paper --trials 100 \
  --output-directory outputs/synthetic
python experiments/synthetic/plot_results.py \
  outputs/synthetic/summary.json \
  --output outputs/synthetic/summary.png
```

For a fast installation check, use `--profile smoke --trials 1`. All random
generators are derived from the requested seed. The runner writes every trial
to `raw_results.csv` and grouped mean, median, p95, and success-rate statistics
to `summary.json`.

| Study | Samples per setting | Geometry and noise |
| --- | ---: | --- |
| Noise sweep | 500 | 50 points, radius 2–5 m, center 0–5 m, random 90°–360° arc, sigma 1e-4–1 m |
| Visible-arc sweep | 500 | 50 points, radius 2–5 m, center 0–5 m, 90°–360° arc, sigma 0.1 m |
| Outlier sweep | 100 | Same 50-point 360° data, 10%–50% integer-coordinate outliers in [10, 20] m |
| Four stress scenarios | 1000 | Original isotropic, 70° nonuniform, 12-point sparse, and 200° symmetric generators |

Omit `--trials` to use those per-study counts, or set it to override every
configuration. 

## Optional PCL baseline

On Ubuntu, install PCL and the build tools:

```bash
sudo apt-get update
sudo apt-get install -y libeigen3-dev libpcl-dev ninja-build
```

Build the optional batch adapter without adding PCL to the core library:

```bash
cmake -S . -B build-pcl -G Ninja \
  -DCCC_BUILD_PCL_EXPERIMENTS=ON \
  -DCCC_BUILD_TESTS=OFF \
  -DCCC_BUILD_EXAMPLES=OFF
cmake --build build-pcl --target circular_center_pcl_batch
```

Pass the adapter to the same Python runner. PCL and CGA then receive exactly the
same generated point sets:

```bash
python experiments/synthetic/run_experiments.py \
  --profile paper \
  --studies 3d \
  --pcl-executable build-pcl/experiments/synthetic/circular_center_pcl_batch \
  --output-directory outputs/synthetic-pcl
python experiments/synthetic/plot_results.py \
  outputs/synthetic-pcl/summary.json \
  --output outputs/synthetic-pcl/summary.png
```

The adapter uses `pcl::SACSegmentation`, `SACMODEL_CIRCLE3D`, `SAC_RANSAC`,
coefficient optimization, 1000 iterations, probability 0.99, and the distance
thresholds from the legacy experiments. Use `--trials 1` for a quick smoke run.

The experiment records are synthetic measurements produced by the current
released implementation and, when requested, the installed PCL version.
