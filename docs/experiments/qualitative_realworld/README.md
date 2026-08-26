# Qualitative real-world experiment

This experiment detects the circular target in camera images and high-intensity
LiDAR points, estimates the LiDAR-camera extrinsic transform, and renders the
projected point cloud and centers corresponding to paper Figure 11.

## 1. Download the data

Download
[`circular-center-calibration-data.zip`](https://drive.google.com/file/d/15KnnDbFxnf1pKnCbVjomoJlxTrxz39tC/view?usp=sharing).
The reproducibility package must contain the 67-frame lab sequence, not a
mixture of the earlier `far-*`, `front-*`, and `mid-*` exports. Faces may remain
privacy-masked: the included partial-arc detector was designed and tested on
that release.

From the repository root, the archive can also be downloaded with:

```bash
mkdir -p data/downloads
curl --fail --location \
  'https://drive.usercontent.google.com/download?id=15KnnDbFxnf1pKnCbVjomoJlxTrxz39tC&export=download&confirm=t' \
  --output data/downloads/circular-center-calibration-data.zip
```

Extract the archive and move its three dataset directories under `data/`:

```bash
unzip -q data/downloads/circular-center-calibration-data.zip -d data/downloads
mv data/downloads/circular-center-calibration-data/orbbec_livox_lab data/
mv data/downloads/circular-center-calibration-data/orbbec_livox_office data/
mv data/downloads/circular-center-calibration-data/zju data/
```

## 2. Check the data

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
└── zju/
    ├── dataset.yaml
    ├── camera_info.yaml
    ├── img/*.png             # 7 images
    └── pcd/*.pcd             # 7 point clouds
```

Each image and point-cloud pair has the same numeric filename. The public
package contains 67 lab pairs, 37 office pairs, and seven ZJU pairs. The
unmasked lab images used for the author-side audit are not required for public
reproduction.

The ZJU images are already-undistorted `CamBack` frames produced by the
historical `src/undistort.py`. Its normalized `camera_info.yaml` deliberately
uses the CamBack intrinsic matrix with zero distortion and is the complete
runtime camera description. No source fisheye configuration is required.

### Automatic versus historical manual ellipses

The old pipeline used AAMED proposals followed by manual selection of the
ellipse on the board. The included detector performs that selection
automatically using red-board support and, when the closed-contour test is
occluded, a deterministic partial-arc fit.

On the recovered unmasked 67-frame sequence, the automatic detector finds all
67 ellipses. In 66 frames it selects the same board target as the historical
manual list. The center difference has a median of 0.304 px and a 95th
percentile of 0.472 px. Frame `00060` is the exception: visual inspection shows
that the historical manual row selected a background ring, while the automatic
ellipse is on the calibration board. This rules out manual selection as the
source of the reproducibility gap.

Privacy edits do overlap the former closed-contour detector's search area in
frames `00018`, `00050`, and `00066`. The partial-arc fallback now recovers all
three. Across all 67 frames, the included detector's raw-to-masked ellipse
center change is 0 px at the median, 0.021 px at the 95th percentile, and
0.579 px at maximum.

## 3. Run the experiment

Complete the root [Installation](../../../README.md#installation), then run a
10-frame preview:

```bash
circular-center-run \
  configs/experiments/qualitative_realworld/paper.yaml \
  --max-frames 10 \
  --output-dir outputs/qualitative_realworld_preview
```

Run all 67 image/point-cloud pairs with:

```bash
circular-center-run \
  configs/experiments/qualitative_realworld/paper.yaml \
  --output-dir outputs/qualitative_realworld
```

Run the optional seven-pair ZJU validation with:

```bash
circular-center-run \
  configs/experiments/qualitative_realworld/zju.yaml \
  --output-dir outputs/qualitative_realworld_zju
```

Run the office sequence alone with:

```bash
circular-center-run \
  configs/experiments/qualitative_realworld/office.yaml \
  --output-dir outputs/qualitative_realworld_office
```

The paper configuration selects `Refined Center`, `CGA-RANSAC`, and
`Quasi-RANSAC`. All stochastic stages use seed `2025`; the partial-arc detector
and CGA-RANSAC have explicit seeds, and OpenCV's RNG is reset before pose
estimation. Each unordered 2D candidate pair is canonicalized before
calibration. Quasi-RANSAC then evaluates a fixed 2,000 hypotheses with MSAC
scoring, preventing input order or adaptive early stopping from making detector
comparisons follow different ambiguity branches.

PCL is not called by this real-world configuration. Its version therefore
cannot explain this experiment's mismatch; PCL only affects the separate
`PCL SACMODEL` baseline.

For each dataset, all successfully extracted `Refined Center` 2D observations
and `CGA-RANSAC` 3D centers enter one joint calibration. Quasi-RANSAC resolves
the two 2D candidates and the final iterative PnP uses all consensus inliers.

## 4. Outputs

```text
outputs/qualitative_realworld/
├── summary.json
└── orbbec_livox_lab/
    ├── 00001.png
    └── ...
```

`summary.json` records the detector proposal source, 2D candidates, selected
center, fitted 3D center and radius, circle inliers, calibration inliers,
extrinsic transform, and per-frame reprojection error.

The compatibility field `mean_reprojection_error_px` is the inlier-only mean.
New summaries also provide the unambiguous
`mean_reprojection_error_all_px` and
`mean_reprojection_error_inliers_px` fields.

## 5. Reproducible result

The public, privacy-masked 67-frame sequence with seed `2025` produces:

| Attempted | Image ellipses | 3D/2D correspondences | Calibration inliers | Mean error, all | Mean error, inliers |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 67 | 67 | 65 | 61 | 2.634 px | 2.195 px |

The two missing correspondences are `00052` and `00063`, where the independent
LiDAR 3D circle fit fails; they are not image-detection failures.

The private unmasked audit copy produces 65 correspondences, 62 inliers,
2.603 px over all correspondences, and 2.270 px over inliers. The small
raw-to-masked change shows that privacy masking is no longer a material source
of the reported calibration error.

The ZJU sequence produces seven correspondences and seven inliers, with
1.950571 px mean reprojection error over both all correspondences and inliers.
All seven ellipses use the automatic HSV board detector. Compared with the
recovered historical AAMED/manual list, their center difference is 1.284 px at
the median and 1.526 px at maximum.

The office sequence produces 34 correspondences and 33 inliers. Its mean
reprojection error is 1.820509 px over all correspondences and 1.583410 px over
inliers. Frames `00014`, `00023`, and `00028` fail the independent 3D target
extraction.

## 6. Included detector versus external AAMED

AAMED is GPL-2.0 and is not bundled into this Apache-2.0 repository. It remains
an optional external detector pinned for comparison at upstream tag `v1.0`,
commit `7c8345a01eeb5c852585676fbe414703504bff04`. See
[`docs/dependencies/aamed.md`](../../dependencies/aamed.md) for provenance and
the detector-audit protocol.

Both detectors find all 67 image ellipses. Only the ellipse detector changes in
this table; the data, 3D centers, seeds, fixed 2,000-hypothesis MSAC solver, and
PnP stages are identical.

| Images | Detector | Correspondences | Inliers | Mean error, all | Mean error, inliers |
| --- | --- | ---: | ---: | ---: | ---: |
| unmasked audit | HSV + partial arc | 65 | 62 | 2.603 px | 2.270 px |
| unmasked audit | external AAMED v1 | 65 | 62 | 2.644 px | 2.321 px |
| privacy-masked release | HSV + partial arc | 65 | 61 | 2.634 px | 2.195 px |
| privacy-masked release | external AAMED v1 | 65 | 62 | 2.642 px | 2.320 px |

The all-correspondence difference on the released images is only 0.008 px, so
the two detectors are indeed equivalent at the calibration level for this
dataset. The inlier-only means should not be subtracted directly because their
inlier sets contain 61 and 62 observations respectively.

An earlier preliminary comparison reported approximately 2.29 px for HSV and
3.03 px for AAMED. That was not a detector-only comparison: adaptive early
stopping and non-canonical candidate ordering led Quasi-RANSAC to two different
ambiguity solutions. Canonical pair ordering plus fixed-budget MSAC removes
that solver confound. AAMED is still more mask-invariant at the ellipse level
(maximum center change 0.061 px versus 0.579 px), so it is a reasonable external
choice when GPL terms are acceptable or the red-board color prior is absent.

The rendered image projects the complete LiDAR scan with intensity coloring
from blue (low) to red (high). The yellow curve is the detected image ellipse,
green marks the selected 2D center, and the cyan cross is the projected 3D
circle center.

### Lab

![Lab projection result](assets/lab-00026.png)

### Office

![Office projection result](assets/office-00033.png)
