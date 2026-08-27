# Synthetic 3D Stress: Configuration and Usage

[中文](README_zh.md)

Run all commands below from the repository root. This experiment generates the
heatmap and trial-level results corresponding to paper Figure 6.

## 1. Prepare the environment

Complete the repository [README Installation](../../../README.md#installation),
including the PCL baseline build.

## 2. Run the quick check

```bash
circular-center-run \
  configs/experiments/synthetic_3d_stress/ci.yaml \
  --output-dir outputs/synthetic_3d_stress_ci
```

The CI profile runs 2 trials in a reduced 2-by-2 grid for all four angular
distributions. It checks generation, both 3D plugins, aggregation, and plotting.

## 3. Run the full experiment

```bash
circular-center-run \
  configs/experiments/synthetic_3d_stress/paper.yaml \
  --output-dir outputs/synthetic_3d_stress
```

The `paper` profile uses radius `0.12 m`, noise `sigma=0.005r`, point counts
`{5,8,16,32,64,128}`, visible arcs `{45,60,90,120,180,270,360}` degrees, four
sampling distributions, and 300 trials per cell. `CGA` and `PCL SACMODEL` are
evaluated on the same samples, producing 100,800 records.

## 4. Configure methods

```yaml
schema_version: 1
experiment: synthetic_3d_stress
datasets: [paper]
methods:
  2d: null
  3d: [CGA, PCL SACMODEL]
  ambiguity: null
```

The paper grid, distributions, success criterion, and method overrides live in
`experiments/synthetic_3d_stress/`. Add a registered 3D method to `methods.3d`
to include it in the same sweep.

## 5. Outputs

```text
outputs/synthetic_3d_stress/
├── summary.json
└── paper/
    ├── stress_heatmap_nominal_noise.pdf
    ├── stress_heatmap_nominal_noise.png
    ├── raw_results.csv
    ├── cell_summary.csv
    └── paper_comparison.csv
```

```bash
wc -l \
  outputs/synthetic_3d_stress/paper/raw_results.csv \
  outputs/synthetic_3d_stress/paper/cell_summary.csv
```

Expected counts, including headers, are 100,801 and 337 lines.

![Generated Figure 6 heatmap](../../../outputs/synthetic_3d_stress/paper/stress_heatmap_nominal_noise.png)

## 6. Results

One full development run reproduced the paper's main transition cells: CGA
reached `0.950` at 8 points/90 degrees and `1.000` at 16 points/90 degrees;
PCL reached `1.000` at 32 points/120 degrees. Mean absolute probability
differences for CGA were `0.020` (single arc) and `0.029` (banded); for PCL they
were `0.088` and `0.092`.

The paper does not release its generator, within-band jitter, fitting thresholds,
or trial records. `paper_comparison.csv` therefore compares this deterministic
implementation with values approximately decoded from the published heatmap.

## Troubleshooting

- `PCL SACMODEL ... unavailable`: build the PCL library as described in the root
  README or set `CIRCULAR_CENTER_PCL_LIBRARY`.
- The CI profile uses a reduced 2-by-2 grid; the paper profile uses the complete
  parameter grid.
