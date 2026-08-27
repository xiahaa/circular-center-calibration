# Synthetic 3D Target Tolerance: Configuration and Usage

[中文](README_zh.md)

Run all commands below from the repository root. This experiment generates the
curves and trial-level results corresponding to paper Figure 7.

## 1. Prepare the environment

Complete the repository [README Installation](../../../README.md#installation),
including the PCL baseline build.

## 2. Run the quick check

```bash
circular-center-run \
  configs/experiments/synthetic_3d_target_tolerance/ci.yaml \
  --output-dir outputs/synthetic_3d_target_tolerance_ci
```

The CI profile uses only deformation magnitudes `0` and `0.05`, with 2 trials
per setting. It verifies all three 3D plugins, aggregation, comparison, and
plotting.

## 3. Run the full experiment

```bash
circular-center-run \
  configs/experiments/synthetic_3d_target_tolerance/paper.yaml \
  --output-dir outputs/synthetic_3d_target_tolerance
```

The `paper` profile sweeps normal warp and ellipse-axis deviation over
`{0,0.0025,0.005,0.01,0.02,0.05}`, with 300 paired trials per setting. It uses
a `0.12 m` radius, 64 points over a 180-degree arc, and `sigma=0.005r` noise,
producing 10,800 records for `PCL SACMODEL`, `CGA`, and `CGA-RANSAC`.

## 4. Configure methods

```yaml
schema_version: 1
experiment: synthetic_3d_target_tolerance
datasets: [paper]
methods:
  2d: null
  3d: [PCL SACMODEL, CGA, CGA-RANSAC]
  ambiguity: null
```

The recovered deformation model and paper-specific overrides are contained in
`experiments/synthetic_3d_target_tolerance/`. Registered 3D methods can be added
to `methods.3d` without changing the runner.

## 5. Outputs

```text
outputs/synthetic_3d_target_tolerance/
├── summary.json
└── paper/
    ├── target_tolerance.pdf
    ├── target_tolerance.png
    ├── raw_results.csv
    ├── tolerance_summary.csv
    └── paper_comparison.csv
```

```bash
wc -l \
  outputs/synthetic_3d_target_tolerance/paper/raw_results.csv \
  outputs/synthetic_3d_target_tolerance/paper/tolerance_summary.csv
```

Expected counts, including headers, are 10,801 and 37 lines.

![Generated Figure 7 curves](../../../outputs/synthetic_3d_target_tolerance/paper/target_tolerance.png)

## 6. Results

At magnitude `0.05`, one full development run produced the following mean
center errors (mm):

| Deformation | PCL SACMODEL | CGA | CGA-RANSAC |
| --- | ---: | ---: | ---: |
| Normal warp | 5.773 | 5.347 | 5.325 |
| Axis deviation | 11.298 | 9.786 | 10.625 |

The direct-CGA curve agrees closely with the vector PDF (mean absolute
difference below `0.07 mm`) and reproduces the paper's main conclusion that
axis error is more damaging than warp. The original generator and robust-method
thresholds were not published; the PCL and CGA-RANSAC endpoint errors are about
`3.4 mm` below the plotted reference. Exact differences are recorded in
`paper_comparison.csv`.

## Troubleshooting

- `PCL SACMODEL ... unavailable`: build the PCL library from the root README or
  set `CIRCULAR_CENTER_PCL_LIBRARY`.
- The CI profile uses two deformation magnitudes; the paper profile uses all six.
