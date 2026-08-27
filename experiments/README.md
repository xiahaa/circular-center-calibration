# Experiment implementations

This directory contains experiment-owned data generation, preprocessing,
evaluation, and reporting code. Experiment selection belongs in
`configs/experiments/`; interchangeable method settings belong in
`configs/methods/`; user-facing commands and expected outputs belong in
`docs/experiments/`.

| Implementation | Paper result | User guide | Technical protocol |
| --- | --- | --- | --- |
| `synthetic_3d_accuracy` | Figure 5, Table I | [Guide](../docs/experiments/synthetic_3d_accuracy/README.md) | [Protocol](synthetic_3d_accuracy/PROTOCOL.md) |
| `synthetic_3d_stress` | Figure 6 | [Guide](../docs/experiments/synthetic_3d_stress/README.md) | [Protocol](synthetic_3d_stress/PROTOCOL.md) |
| `synthetic_3d_target_tolerance` | Figure 7 | [Guide](../docs/experiments/synthetic_3d_target_tolerance/README.md) | [Protocol](synthetic_3d_target_tolerance/PROTOCOL.md) |
| `synthetic_2d_accuracy` | Figure 8 | [Guide](../docs/experiments/synthetic_2d_accuracy/README.md) | [Protocol](synthetic_2d_accuracy/PROTOCOL.md) |
| `synthetic_2d_pose` | Figure 9 | [Guide](../docs/experiments/synthetic_2d_pose/README.md) | [Protocol](synthetic_2d_pose/PROTOCOL.md) |
| `quasi_ransac_evaluation` | Table II | [Guide](../docs/experiments/quasi_ransac_evaluation/README.md) | [Protocol](quasi_ransac_evaluation/PROTOCOL.md) |
| `benchmark_3d_runtime` | Table III | [Guide](../docs/experiments/benchmark_3d_runtime/README.md) | [Protocol](benchmark_3d_runtime/PROTOCOL.md) |
| `qualitative_realworld` | Figure 11 | [Guide](../docs/experiments/qualitative_realworld/README.md) | Dataset-specific pipeline |

Synthetic experiments normally separate their implementation into
`experiment.py`, `generators.py`, `protocol.py`, and `reporting.py`. These files
have distinct responsibilities and are intentionally not merged. The real-world
experiment instead groups dataset-specific 2D detection, 3D extraction, and
evaluation helpers by pipeline stage.
