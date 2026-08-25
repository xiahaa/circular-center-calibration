# Qualitative real-world experiment

This experiment detects the circular target in camera images and high-intensity
LiDAR points, estimates the LiDAR-camera extrinsic transform, and renders the
projected point cloud and centers corresponding to paper Figure 11.

## 1. Download the data

Download
[`circular-center-calibration-data.zip`](https://drive.google.com/file/d/15KnnDbFxnf1pKnCbVjomoJlxTrxz39tC/view?usp=sharing).
The archive contains both real-world datasets. It can also be downloaded from
the repository root with:

```bash
mkdir -p data/downloads
curl --fail --location \
  'https://drive.usercontent.google.com/download?id=15KnnDbFxnf1pKnCbVjomoJlxTrxz39tC&export=download&confirm=t' \
  --output data/downloads/circular-center-calibration-data.zip
```

Extract the archive and move its two dataset directories under `data/`:

```bash
unzip -q data/downloads/circular-center-calibration-data.zip -d data/downloads
mv data/downloads/circular-center-calibration-data/orbbec_livox_lab data/
mv data/downloads/circular-center-calibration-data/orbbec_livox_office data/
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
└── orbbec_livox_lab/
    ├── dataset.yaml
    ├── camera_info.yaml
    ├── img/*.png             # 67 images
    └── pcd/*.pcd             # 67 point clouds
```

Each image and point cloud pair has the same numeric filename. Confirm the pair
counts with:

```bash
find data/orbbec_livox_office/img -name '*.png' -type f | wc -l
find data/orbbec_livox_office/pcd -name '*.pcd' -type f | wc -l
find data/orbbec_livox_lab/img -name '*.png' -type f | wc -l
find data/orbbec_livox_lab/pcd -name '*.pcd' -type f | wc -l
```

The expected output is `37`, `37`, `67`, and `67`.

## 3. Run the experiment

Complete the root [Installation](../../../README.md#installation), then run a
10-frame pass for each dataset:

```bash
circular-center-run \
  configs/experiments/qualitative_realworld/default.yaml \
  --max-frames 10 \
  --output-dir outputs/qualitative_realworld_preview
```

Run all 104 image/point-cloud pairs with:

```bash
circular-center-run \
  configs/experiments/qualitative_realworld/default.yaml \
  --output-dir outputs/qualitative_realworld
```

The default configuration selects `Refined Center`, `CGA-RANSAC`, and
`Quasi-RANSAC`. Change the selected methods or datasets in
`configs/experiments/qualitative_realworld/default.yaml`.

For each dataset, all successfully extracted `Refined Center` 2D observations
and `CGA-RANSAC` 3D centers enter one joint calibration. `Quasi-RANSAC` resolves
the two 2D candidates and the final iterative PnP uses every consensus inlier.

## 4. Outputs

```text
outputs/qualitative_realworld/
├── summary.json
├── orbbec_livox_office/
│   ├── 00001.png
│   └── ...
└── orbbec_livox_lab/
    ├── 00001.png
    └── ...
```

`summary.json` records the 2D candidates, selected center, fitted 3D center and
radius, circle inliers, calibration inliers, extrinsic transform, and
reprojection error for every frame.

## 5. Results

A complete run produced:

| Dataset | Attempted | Successful centers | Calibration inliers | Mean reprojection error |
| --- | ---: | ---: | ---: | ---: |
| `orbbec_livox_lab` | 67 | 60 | 57 | 3.094 px |
| `orbbec_livox_office` | 37 | 27 | 27 | 2.734 px |

The complete LiDAR scan is projected with intensity coloring from blue (low) to
red (high). The yellow curve is the detected image ellipse, green marks the
selected 2D center, and the cyan cross is the projected 3D circle center.

### Lab

![Lab projection result](assets/lab-00026.png)

### Office

![Office projection result](assets/office-00033.png)
