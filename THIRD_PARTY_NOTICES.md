# Third-party dependencies

This public branch does not vendor third-party source code.

The following libraries are installed separately and retain their respective
copyrights and license terms:

- Eigen, used by the header-only C++ implementation;
- NumPy, used by the Python implementation;
- OpenCV, optionally used for ellipse fitting, contour rectification, PnP, and
  quasi-RANSAC.
- Matplotlib, optionally used to plot synthetic experiment summaries.

AAMED, Miniball, ROS, Gazebo, PCL, real datasets, and internal-only evaluation
tooling are not included or required by this branch.
