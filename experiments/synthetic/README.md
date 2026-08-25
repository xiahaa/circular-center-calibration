# Synthetic paper experiments

This directory contains a deterministic, public-API-only rewrite of the
synthetic experiments used while developing the paper. It replaces the legacy
scripts that depended on hard-coded data paths, duplicated algorithm code, and
an internal PCL/third-party RANSAC workspace.

The runner covers three studies:

- 3D circle fitting under Gaussian noise, limited visible arcs, outliers, and
  the four legacy stress scenarios;
- 2D projected-center estimation under contour noise and circle-plane tilt,
  including two-circle homography disambiguation;
- camera-pose recovery using ellipse centers, oracle candidates, and the
  released quasi-RANSAC implementation.

Install the experiment dependencies and run the paper profile:

```bash
python -m pip install -e '.[experiments,dev]'
python experiments/synthetic/run_experiments.py \
  --profile paper \
  --trials 100 \
  --output-directory outputs/synthetic
python experiments/synthetic/plot_results.py \
  outputs/synthetic/summary.json \
  --output outputs/synthetic/summary.png
```

For a fast installation check, use `--profile smoke --trials 1`. All random
generators are derived from the requested seed. The runner writes every trial
to `raw_results.csv` and grouped mean, median, p95, and success-rate statistics
to `summary.json`.

The experiment records are synthetic measurements produced by the current
released implementation. They do not claim bit-for-bit reproduction of the
legacy result files. In particular, the PCL baseline is intentionally absent:
PCL is not part of the minimal core package, and no third-party source is
vendored on this branch.
