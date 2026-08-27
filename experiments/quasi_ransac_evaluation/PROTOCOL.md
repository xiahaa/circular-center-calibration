# Protocol notes

The protocol is transcribed from the Quasi-RANSAC Evaluation paragraph and
Table II. The paper does not release per-trial data. Points are sampled directly
in the camera-coordinate volume stated by the paper, so the expected pose is
identity. The number of outliers is `round(n * ratio)`, which reproduces the
iteration regimes shown in the table for small correspondence counts.

All three stated confidence values are evaluated. The generated TeX table uses
the paper's displayed `0.99` confidence; `full_summary.csv` retains every cell.
