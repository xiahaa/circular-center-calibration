# Qualitative real-world experiment

This experiment owns only dataset-specific preprocessing and visualization:

- high-reflectance and distance filtering;
- Euclidean clustering and target-size validation;
- directional boundary extraction for 3D circle fitting;
- red-board/bright-disk ellipse detection in images;
- per-dataset extrinsic estimation and qualitative overlays.

The actual 2D, 3D, and ambiguity algorithms are selected by
`configs/experiments/qualitative_realworld/default.yaml` and loaded from the
central `configs/methods` catalog. Adding a new interchangeable method does not
require editing this experiment.

Download, configuration, execution, and result documentation:

- [English](../../docs/experiments/qualitative_realworld/README.md)
- [中文](../../docs/experiments/qualitative_realworld/README_zh.md)
