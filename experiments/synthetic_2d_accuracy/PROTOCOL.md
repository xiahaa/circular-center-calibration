# Protocol recovery notes

The implementation was migrated from CCFinder's
`python/exp/monte_carlo_validation_homograph.py` and its 2D utilities. The
runtime implementation in this repository is self-contained and does not
import or require CCFinder.

The paper and archived trial data establish 1000 trials. Each trial projects
two radius-2 coplanar circles, offsets the validation circle by `(4, 4, 0)`,
uses `K=(600, 600, 640, 480)`, adds independent 1-pixel Gaussian contour
noise, and fits both ellipses with OpenCV. The second fitted ellipse resolves
the two `Refined Center` candidates by rectified radius ratio.

The released script's CLI default still says 500 trials and contains unused
radius arguments; the paper text and archived Figure 8 data are authoritative
for the `paper` profile. The archived refined-center tail also differs from the
late source snapshot for a small set of degenerate searches. Golden aggregate
statistics are retained in `protocol.yaml`, and `paper_comparison.csv` exposes
the remaining difference instead of hiding it.
