# Synthetic 2D Pose Experiment: Configuration and Usage

[中文](README_zh.md)

Run all commands below from the repository root. This experiment generates the
pose-error chart corresponding to paper Figure 9 and the per-trial PnP results.

## 1. Prepare the environment

Complete the repository [README Installation](../../../README.md#installation).
This experiment does not require the optional PCL build.

## 2. Run the quick check

```bash
circular-center-run \
  configs/experiments/synthetic_2d_pose/ci.yaml \
  --output-dir outputs/synthetic_2d_pose_ci
```

The CI profile runs one four-circle trial. It checks generation, method
dispatch, ambiguity resolution, PnP evaluation, CSV output, and plotting; it is
the reduced form of the full execution path.

## 3. Run the full experiment

```bash
circular-center-run \
  configs/experiments/synthetic_2d_pose/paper.yaml \
  --output-dir outputs/synthetic_2d_pose
```

The `paper` profile runs 50 unique trials with 20 circle correspondences per
trial. It evaluates `Ellipse Center`, `Mass Center`, and `Refined Center` with
PnP-RANSAC. `Quasi-RANSAC` resolves the two branches returned by `Refined
Center`; the generated Figure 9 label remains `RANSAC Center` for consistency
with the released figure.

Use the existing `paper` configuration without changing
`experiments/synthetic_2d_pose/protocol.yaml` or
`experiments/synthetic_2d_pose/profiles/paper.yaml` when reproducing the
experiment.

## 4. Configure methods

The outer configuration only selects participating methods:

```yaml
schema_version: 1
experiment: synthetic_2d_pose
datasets: [paper]
methods:
  2d: [Ellipse Center, Mass Center, Refined Center]
  3d: null
  ambiguity: [Homography Validation, Quasi-RANSAC]
```

Register additional 2D or ambiguity methods under `configs/methods/`, then add
their exact paper-facing names to the corresponding list. Figure-specific
generation, PnP, and compatibility parameters remain in the experiment
directory.

## 5. Outputs

```text
outputs/synthetic_2d_pose/
├── summary.json
└── paper/
    ├── error_bar_comparison.png
    ├── raw_results.csv
    ├── method_summary.csv
    └── paper_comparison.csv
```

`raw_results.csv` contains one header row and 200 method records:

```bash
wc -l outputs/synthetic_2d_pose/paper/raw_results.csv
```

`paper_comparison.csv` records the observed and archived Figure 9 mean for all
three pose metrics without applying a pass/fail tolerance.

## 6. Results

One full run produced the figure and values below.

![Full run for paper Figure 9](assets/reference-run.svg)

| Method | Reprojection (px) | Rotation (rad) | Translation |
| --- | ---: | ---: | ---: |
| Ellipse Center | 1.5106 | 0.03507 | 0.4956 |
| Mass Center | 1.3966 | 0.03271 | 0.4862 |
| Refined Center | 0.4208 | 0.00526 | 0.0507 |
| RANSAC Center (`Quasi-RANSAC`) | 0.3945 | 0.00101 | 0.0051 |

Both baselines agree with the archived means within 0.3%. Both proposed methods
remain substantially below the baselines. Their relative ordering differs from
the archived chart: the released 99-row CSV contains only 50 unique generated
trials, while the required intermediate NPZ files and the legacy unseeded
RANSAC state were not released. The repository regenerates each unique seed
once and uses deterministic sampling; all numerical differences are retained in
`paper_comparison.csv`.

## Troubleshooting

- `Refined Center ... multiple candidates`: keep `Homography Validation` in
  `methods.ambiguity`.
- `OpenCV is required`: activate the environment installed from the root
  README.
- The CI profile uses 4 correspondences; the paper profile uses 20 per trial.
