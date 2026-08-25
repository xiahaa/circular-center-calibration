# 3D Runtime Benchmark: Configuration and Usage

[中文](README_zh.md)

Run all commands below from the repository root. This experiment generates the
runtime and process-memory results corresponding to paper Table III.

## 1. Prepare the environment

Complete the repository [README Installation](../../../README.md#installation),
including the PCL baseline build.

## 2. Run the quick check

```bash
circular-center-run \
  configs/experiments/benchmark_3d_runtime/ci.yaml \
  --output-dir outputs/benchmark_3d_runtime_ci
```

The CI profile performs 9 timed fits per method in one isolated process. It
checks worker startup, method loading, latency/RSS collection, CSV aggregation,
and TeX output.

## 3. Run the full benchmark

Stop unrelated CPU-heavy jobs, then run:

```bash
circular-center-run \
  configs/experiments/benchmark_3d_runtime/paper.yaml \
  --output-dir outputs/benchmark_3d_runtime
```

For each method, the `paper` profile executes exactly 1000 timed fits of the
same 64-point circle. The fits are split across five sequential isolated
processes, with 20 untimed warmups per process. p50/p95 use all 1000 samples;
Peak RSS is the median of the five process peaks. BLAS/OpenMP thread counts are
fixed to one inside each worker.

## 4. Configure methods

```yaml
schema_version: 1
experiment: benchmark_3d_runtime
datasets: [paper]
methods:
  2d: null
  3d: [CGA, CGA-RANSAC, PCL SACMODEL]
  ambiguity: null
```

The fixed input, warmup policy, RANSAC budget, and paper reference values are in
`experiments/benchmark_3d_runtime/`. Add a registered 3D method to `methods.3d`
to benchmark it under the same isolation policy.

## 5. Outputs

```text
outputs/benchmark_3d_runtime/
├── summary.json
└── paper/
    ├── runtime_records.csv
    ├── process_rss.csv
    ├── runtime_summary.csv
    ├── runtime_table.tex
    ├── environment.json
    └── paper_comparison.csv
```

```bash
wc -l \
  outputs/benchmark_3d_runtime/paper/runtime_records.csv \
  outputs/benchmark_3d_runtime/paper/process_rss.csv \
  outputs/benchmark_3d_runtime/paper/runtime_summary.csv
```

Expected counts, including headers, are 3001, 16, and 4 lines.

## 6. Results

One run on an Intel Core i9-14900K produced:

| Method | p50 (ms) | p95 (ms) | Peak RSS (MiB) |
| --- | ---: | ---: | ---: |
| CGA | 0.110 | 0.118 | 42.5 |
| CGA-RANSAC | 2.967 | 3.017 | 44.5 |
| PCL SACMODEL | 0.118 | 0.121 | 69.4 |

The paper used an Intel Xeon Gold 5218 and reported `1.407/1.489 ms` for CGA,
`6.130/7.769 ms` for CGA-RANSAC, and `0.098/0.100 ms` for PCL. PCL latency is
the same order of magnitude, while the current optimized Python CGA paths are
faster. PCL RSS is higher here because the isolated process maps this build's
dynamic PCL dependency set. `environment.json` records the hardware and build
information associated with the table.

## Troubleshooting

- Close competing workloads before a full run; CI performs 9 timed fits per
  method.
- `PCL SACMODEL ... unavailable`: build the PCL library from the root README or
  set `CIRCULAR_CENTER_PCL_LIBRARY`.
