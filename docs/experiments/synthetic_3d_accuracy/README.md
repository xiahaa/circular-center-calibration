# Synthetic 3D Circle-Center Accuracy: Configuration and Usage

[中文](README_zh.md)

Run all commands below from the repository root. This experiment generates the
results corresponding to paper Figure 5 (3D center error under four sampling
scenarios) and Table I (mean 3D center error at different outlier ratios), plus
the per-trial records.

## 1. Prepare the environment

Complete the environment installation and PCL baseline build described in the
repository [README Installation](../../../README.md#installation).

## 2. Run the quick check

```bash
circular-center-run \
  configs/experiments/synthetic_3d_accuracy/ci.yaml \
  --output-dir outputs/synthetic_3d_accuracy_ci
```

This configuration runs only a few samples to verify method loading, data
generation, statistics, and plotting.

## 3. Run the full experiment

```bash
circular-center-run \
  configs/experiments/synthetic_3d_accuracy/paper.yaml \
  --output-dir outputs/synthetic_3d_accuracy
```

The full configuration runs:

- four 3D sampling scenarios (A-D), with 1000 trials per scenario;
- five outlier ratios from `10%` to `50%`, with 100 trials per ratio;
- `CGA` and `PCL SACMODEL` for Figure 5;
- `CGA-RANSAC` and `PCL SACMODEL` for the outlier study.

Use the existing `paper` configuration without changing
`experiments/synthetic_3d_accuracy/protocol.yaml` or
`experiments/synthetic_3d_accuracy/profiles/paper.yaml` when reproducing the
experiment.

## 4. Configure methods

The outer configuration selects the participating methods:

```yaml
schema_version: 1
experiment: synthetic_3d_accuracy
datasets: [paper]
methods:
  2d: null
  3d: [CGA, CGA-RANSAC, PCL SACMODEL]
  ambiguity: null
```

To test a new method, first register it under `configs/methods/3d/`, then add its
name to `methods.3d`. Experiment parameters remain managed by the experiment
directory.

## 5. Outputs

```text
outputs/synthetic_3d_accuracy/
├── summary.json
└── paper/
    ├── 3d-monte.pdf
    ├── 3d-monte.png
    ├── raw_results.csv
    ├── outlier_summary.csv
    ├── outlier_table.tex
    └── paper_comparison.csv
```

`raw_results.csv` should contain one header row and 9000 experiment records:

```bash
wc -l outputs/synthetic_3d_accuracy/paper/raw_results.csv
```

## 6. Results

One full run produced the following figure and table.

![Four-scenario results from one full run](assets/reference-run.svg)

| Method | 10% | 20% | 30% | 40% | 50% |
| --- | ---: | ---: | ---: | ---: | ---: |
| PCL SACMODEL | 0.0707 | 0.0676 | 0.0683 | 0.0736 | 0.0681 |
| CGA-RANSAC | 0.0340 | 0.0356 | 0.0342 | 0.0340 | 0.0343 |

`CGA-RANSAC` remains between `0.0340 m` and `0.0356 m` across all outlier
ratios, while `PCL SACMODEL` remains between `0.0676 m` and `0.0736 m`.
`paper_comparison.csv` records the corresponding paper values and differences.

## Troubleshooting

- `PCL SACMODEL ... unavailable`: repeat the PCL build steps in the root README,
  or set `CIRCULAR_CENTER_PCL_LIBRARY`.
- `circular-center-run` is not found: activate the Conda environment and finish
  the Installation steps in the root README.
- The CI configuration uses 2 Monte Carlo and 2 outlier trials per setting; the
  paper profile uses the complete published scale.
