# Third-party dependencies

This public branch does not vendor third-party source code.

The following libraries are installed separately and retain their respective
copyrights and license terms:

- Eigen, used by the header-only C++ implementation;
- NumPy, used by the Python implementation;
- OpenCV, optionally used for ellipse fitting, contour rectification, PnP, and
  quasi-RANSAC;
- PCL, optionally used by the `PCL SACMODEL` comparison baseline;
- AAMED, optionally used as an external ellipse proposal detector. It is not
  included, linked, or imported by the default experiment. The comparison was
  made with upstream tag `v1.0`, commit
  `7c8345a01eeb5c852585676fbe414703504bff04`, under GPL-2.0. See
  `docs/dependencies/aamed.md`.

Miniball, ROS, Gazebo, real datasets, and internal evaluation tooling are not
included or required by this branch.
