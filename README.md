# Circular Center Calibration

Modular reference implementation for 3D/2D circular-center measurement and
LiDAR-camera extrinsic calibration.

AAMED is GPL-2.0 and is therefore kept as an
optional external dependency rather than bundled into this Apache-2.0
distribution. Its exact public version and comparison protocol are documented
in [`docs/dependencies/aamed.md`](docs/dependencies/aamed.md). Instead, we provide an alternative HSV + partial-arc detector, which works similarly.


## Installation

### Conda

```bash
conda env create -f environment.yml
conda activate circular-center-calibration
```

### Pip

From the repository root:

```bash
python -m pip install -e '.[all]'
```

### PCL SACMODEL

The PCL baseline uses C++. After the Conda installation, build it once:

```bash
cmake -S . -B build -G Ninja -DCCC_BUILD_PCL_BASELINE=ON
cmake --build build
```

Python experiments load the library automatically. Other methods do not need
this step. Set `CIRCULAR_CENTER_PCL_LIBRARY` only for a custom library path.
