# Quasi-RANSAC Evaluation: Configuration and Usage

[中文](README_zh.md)

Run all commands below from the repository root. This experiment generates the
per-trial results and TeX table corresponding to paper Table II.

## 1. Prepare the environment

Complete the repository [README Installation](../../../README.md#installation).
This experiment does not require the optional PCL build.

## 2. Run the quick check

```bash
circular-center-run \
  configs/experiments/quasi_ransac_evaluation/ci.yaml \
  --output-dir outputs/quasi_ransac_evaluation_ci
```

The CI profile runs eight parameter cells with one trial each. It checks data
generation, method dispatch, pose criteria, CSV aggregation, and TeX output; it
uses the same execution path as the full profile.

## 3. Run the full experiment

```bash
circular-center-run \
  configs/experiments/quasi_ransac_evaluation/paper.yaml \
  --output-dir outputs/quasi_ransac_evaluation
```

The `paper` profile evaluates:

- correspondence counts `n = {8, 12, 20}`;
- outlier ratios `{0, 0.1, 0.2, 0.3}`;
- confidence values `{0.95, 0.99, 0.999}`;
- 1000 trials per parameter cell, for 36,000 trials in total.

The generated TeX table uses confidence `0.99`, matching Table II. The CSV
summary retains all 36 cells. Use the existing `paper` profile without changing
the experiment protocol when reproducing the result.

## 4. Configure methods

The outer configuration selects the ambiguity method and leaves unused stages
as `null`:

```yaml
schema_version: 1
experiment: quasi_ransac_evaluation
datasets: [paper]
methods:
  2d: null
  3d: null
  ambiguity: Quasi-RANSAC
```

The paper-specific candidate distributions, success criteria, and method
overrides are stored under `experiments/quasi_ransac_evaluation/`.

## 5. Outputs

```text
outputs/quasi_ransac_evaluation/
├── summary.json
└── paper/
    ├── raw_results.csv
    ├── full_summary.csv
    ├── quasi_ransac_table.tex
    └── paper_comparison.csv
```

Check the expected record and summary counts with:

```bash
wc -l \
  outputs/quasi_ransac_evaluation/paper/raw_results.csv \
  outputs/quasi_ransac_evaluation/paper/full_summary.csv
```

The expected counts are 36,001 and 37 lines, including headers.

## 6. Results

One full run produced the following values.

| Corr. | Outliers | Observed | Iterations | Time (ms) |
| ---: | ---: | ---: | ---: | ---: |
| 8 | 0% | 0.984 | 72.0 | 3.83 |
| 8 | 10% | 0.947 | 123.5 | 6.45 |
| 8 | 20% | 0.879 | 228.4 | 11.77 |
| 8 | 30% | 0.858 | 229.0 | 11.79 |
| 12 | 0% | 0.997 | 72.0 | 3.85 |
| 12 | 10% | 0.992 | 102.9 | 5.41 |
| 12 | 20% | 0.987 | 150.4 | 7.81 |
| 12 | 30% | 0.928 | 367.0 | 18.74 |
| 20 | 0% | 1.000 | 72.0 | 3.90 |
| 20 | 10% | 1.000 | 109.7 | 5.84 |
| 20 | 20% | 0.998 | 176.9 | 9.24 |
| 20 | 30% | 0.992 | 302.9 | 15.61 |

At confidence `0.99`, every observed success rate is within 0.02 absolute of
the archived table, and the mean iteration counts follow the same planning
bounds. Runtime is hardware dependent: this run on an Intel Core i9-14900K is
about four times faster than the paper's Xeon reference. Exact differences are
stored in `paper_comparison.csv`.

## Troubleshooting

- The full profile performs 36,000 pose fits; the CI profile reduces the grid to
  eight cells.
- `OpenCV is required`: activate the environment installed from the root
  README.
- `Time (ms)` varies with CPU; success rates and iteration counts are determined
  by the experiment protocol.
