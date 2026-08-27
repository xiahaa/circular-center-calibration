# Qualitative real-world experiment

[中文](README_zh.md)

This experiment detects the circular target in camera images and high-intensity
LiDAR points, estimates the LiDAR-camera extrinsic transform, and renders the
projected point cloud and centers corresponding to paper Figure 11.

## 1. Download the data

Download
[`circular-center-calibration-data.zip`](https://drive.google.com/file/d/1dgud8KO8id8efYu2VCKPBQoMfGRreUxE/view?usp=sharing).
The archive contains the Lab, Office, and `insta_hesai_outdoor` real-world
datasets. It can also be downloaded from
the repository root with:

```bash
mkdir -p data/downloads
curl --fail --location \
  'https://drive.usercontent.google.com/download?id=1dgud8KO8id8efYu2VCKPBQoMfGRreUxE&export=download&confirm=t' \
  --output data/downloads/circular-center-calibration-data.zip
```

Extract the archive and place its three dataset directories under `data/`:

```bash
unzip -q data/downloads/circular-center-calibration-data.zip -d data/downloads
mv data/downloads/circular-center-calibration-data/orbbec_livox_lab data/
mv data/downloads/circular-center-calibration-data/orbbec_livox_office data/
mv data/downloads/circular-center-calibration-data/insta_hesai_outdoor data/
```

## 2. Check the data layout

The extracted data should have this structure:

```text
data/
├── orbbec_livox_office/
│   ├── dataset.yaml
│   ├── camera_info.yaml
│   ├── img/*.png             # 37 images
│   └── pcd/*.pcd             # 37 point clouds
├── orbbec_livox_lab/
│   ├── dataset.yaml
│   ├── camera_info.yaml
│   ├── img/*.png             # 67 images
│   └── pcd/*.pcd             # 67 point clouds
└── insta_hesai_outdoor/
    ├── dataset.yaml          # dataset: insta_hesai_outdoor
    ├── camera_info.yaml      # undistorted CamBack intrinsics
    ├── img/*.png             # 7 images
    └── pcd/*.pcd             # 7 Hesai point clouds
```

Each image and point cloud pair has the same numeric filename. Confirm the pair
counts with:

```bash
find data/orbbec_livox_office/img -name '*.png' -type f | wc -l
find data/orbbec_livox_office/pcd -name '*.pcd' -type f | wc -l
find data/orbbec_livox_lab/img -name '*.png' -type f | wc -l
find data/orbbec_livox_lab/pcd -name '*.pcd' -type f | wc -l
find data/insta_hesai_outdoor/img -name '*.png' -type f | wc -l
find data/insta_hesai_outdoor/pcd -name '*.pcd' -type f | wc -l
```

The expected output is `37`, `37`, `67`, `67`, `7`, and `7`.

## 3. Run the experiment

Complete the root [Installation](../../../README.md#installation), then build
the optional official AAMED extension:

```bash
git submodule update --init --recursive thirdparty/AAMED
python tools/build_aamed.py
```

The helper builds the pinned `thirdparty/AAMED` submodule against the active
Conda environment. AAMED remains a separately licensed GPL-2.0 component; the
top-level Apache-2.0 license does not apply to that submodule.

Run a 10-frame pass for each dataset:

```bash
circular-center-run \
  configs/experiments/qualitative_realworld/orbbec_livox.yaml \
  --max-frames 10 \
  --output-dir outputs/qualitative_realworld_orbbec_livox_preview
```

Run all 104 image/point-cloud pairs with:

```bash
circular-center-run \
  configs/experiments/qualitative_realworld/orbbec_livox.yaml \
  --output-dir outputs/qualitative_realworld_orbbec_livox
```

Run all seven `insta_hesai_outdoor` Insta360/Hesai pairs with:

```bash
circular-center-run \
  configs/experiments/qualitative_realworld/insta_hesai_outdoor.yaml \
  --output-dir outputs/qualitative_realworld_insta_hesai_outdoor
```

The preprocessing uses AAMED for ellipse detection. The experiment then
applies `Refined Center`, `CGA-RANSAC`, and `Quasi-RANSAC`. Change the selected
methods or datasets in the corresponding experiment YAML.

The ellipse detector is selected by `backend` in
`experiments/qualitative_realworld/detection2d/config.yaml`. Set it to
`opencv_red_board` to run the previous closed-contour detector.

For each dataset, all successfully extracted `Refined Center` 2D observations
and `CGA-RANSAC` 3D centers enter one joint calibration. `Quasi-RANSAC` resolves
the two 2D candidates and the final iterative PnP uses every consensus inlier.
The `CGA-RANSAC` and `Quasi-RANSAC` random seeds are both fixed to `2025` in
their central method configurations.

## 4. Outputs

```text
outputs/qualitative_realworld_orbbec_livox/
├── summary.json
├── orbbec_livox_office/
│   ├── 00001.png
│   └── ...
└── orbbec_livox_lab/
    ├── 00001.png
    └── ...
```

This command writes `summary.json` and seven overlays under
`outputs/qualitative_realworld_insta_hesai_outdoor/insta_hesai_outdoor/`.

`summary.json` records the 2D candidates, selected center, fitted 3D center and
radius, circle inliers, calibration inliers, extrinsic transform, and
reprojection error for every frame.

## 5. Results

A complete comparison with identical 2D-center, 3D-center, and calibration
methods produced:

| Ellipse detector | Dataset | Attempted | Successful centers | Calibration inliers | Mean reprojection error |
| --- | --- | ---: | ---: | ---: | ---: |
| OpenCV red-board contour | `orbbec_livox_lab` | 67 | 60 | 57 | 3.094 px |
| AAMED | `orbbec_livox_lab` | 67 | 65 | 62 | 2.255 px |
| OpenCV red-board contour | `orbbec_livox_office` | 37 | 27 | 27 | 2.734 px |
| AAMED | `orbbec_livox_office` | 37 | 34 | 33 | 1.696 px |
| AAMED | `insta_hesai_outdoor` | 7 | 7 | 7 | 2.149 px |

Weighted over all calibration inliers, AAMED reduces the mean reprojection
error from `2.978 px` to `2.061 px` (`30.8%`).

The complete LiDAR scan is projected with intensity coloring from blue (low) to
red (high). The yellow curve is the detected image ellipse, green marks the
selected 2D center, and the cyan cross is the projected 3D circle center.

### Lab

![Lab projection result](assets/lab-00026.png)

### Office

![Office projection result](assets/office-00033.png)

### `insta_hesai_outdoor`

![Insta360/Hesai outdoor projection result](assets/insta_hesai_outdoor-00006.png)
