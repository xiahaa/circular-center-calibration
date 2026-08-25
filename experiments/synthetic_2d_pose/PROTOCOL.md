# Protocol recovery notes

Figure 9 combines the 20-correspondence generator in
`monte_carlo_2d_refinement.py` with the PnP and candidate-RANSAC evaluation in
`main_ransac_exp.py`. The archived result has 99 rows but only 50 unique
generated trials: 49 appear twice and one appears once. Its intermediate
`p3ds.npz/p2ds.npz/Rs.npz/ts.npz` files were not released. This experiment
therefore regenerates the 50 unique seeds deterministically and evaluates each
once instead of reproducing the accidental duplicate weighting.

The figure's historical `RANSAC Center` label corresponds to the paper's
current `Quasi-RANSAC` ambiguity plugin. Runtime code is self-contained and has
no CCFinder dependency.
