# Synthetic 3D accuracy

This directory contains the complete implementation of the first experiment in
the paper. It does not read or import code, data, or configuration from a
separate reference project. `protocol.yaml` owns the geometry and method
budgets; `profiles/paper.yaml` and `profiles/ci.yaml` only select execution
sizes. The full protocol and the historical implementation details preserved
during migration are documented in `PROTOCOL.md`.

The paper experiment has two details that are easy to miss:

- the PCL baseline is `SACMODEL_CIRCLE3D`, not a plane-plus-2D implementation;
- the four-scenario figure uses direct `CGA`, while the outlier table uses
  `CGA-RANSAC` and labels it “CGA”.

The archive does not contain the 100 base point-cloud files read by the outlier
program. This implementation regenerates those inputs deterministically and
records the resulting comparison in `paper_comparison.csv`.

Run the quick profile:

```bash
circular-center-run configs/experiments/synthetic_3d_accuracy/ci.yaml
```

Run the full paper profile:

```bash
circular-center-run configs/experiments/synthetic_3d_accuracy/paper.yaml
```

The profile output contains `raw_results.csv`, `3d-monte.pdf`,
`outlier_summary.csv`, and `outlier_table.tex`. The paper profile also writes
`paper_comparison.csv` against the values recovered from the reference project.
