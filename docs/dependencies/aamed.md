# AAMED version provenance

The original image-preparation pipeline used AAMED to generate ellipse
proposals, followed by manual selection of the proposal on the calibration
board. The public version used for the detector audit is:

- upstream: <https://github.com/Li-Zhaoxi/AAMED>;
- tag: `v1.0`;
- commit: `7c8345a01eeb5c852585676fbe414703504bff04`;
- license: GPL-2.0.

AAMED is not included as a submodule and is not imported by the default
experiment. GPL-2.0 does allow redistribution under its terms, but this
Apache-2.0 repository keeps AAMED external so that the default package does not
bundle or link a GPL component. Users who accept AAMED's license terms can
clone and build the pinned commit separately:

```bash
git clone https://github.com/Li-Zhaoxi/AAMED.git /path/to/AAMED
git -C /path/to/AAMED checkout 7c8345a01eeb5c852585676fbe414703504bff04
```

The recovered local tree contained two unpublished project-specific commits.
They were not used as public provenance because fresh users cannot fetch those
objects from upstream. The detector comparison instead uses the public commit
above and automatic red-board support scoring to select one AAMED proposal per
frame.

## Detector-audit protocol

AAMED remains outside this repository. For the author-side audit, the
automatically selected AAMED ellipse for each frame was passed through the same
3D fitting and calibration stages as the built-in detector. Detector proposals
were the only variable: the dataset, CGA-RANSAC seed, ambiguity candidates,
Quasi-RANSAC/MSAC budget, PnP, and error calculation were identical.

The project-specific export and audit tooling, along with the full-precision
intermediate measurements, are internal validation artifacts and are not
distributed.

## Seed-2025 comparison

On the same 67 frames, both automatic detectors find all 67 image ellipses;
frames `00052` and `00063` are later rejected by the independent 3D LiDAR
circle fit, leaving 65 calibration correspondences.

| Images | Detector | Correspondences | Inliers | Mean error, all | Mean error, inliers |
| --- | --- | ---: | ---: | ---: | ---: |
| raw audit copy | HSV + partial arc | 65 | 62 | 2.603 px | 2.270 px |
| raw audit copy | external AAMED v1 | 65 | 62 | 2.644 px | 2.321 px |
| privacy-masked release | HSV + partial arc | 65 | 61 | 2.634 px | 2.195 px |
| privacy-masked release | external AAMED v1 | 65 | 62 | 2.642 px | 2.320 px |

The two detectors are therefore similar on this red-board dataset. Their
raw-image ellipse centers differ by 0.318 px at the median and 0.478 px at the
95th percentile. AAMED is more invariant to the privacy mask at the ellipse
level: its maximum raw-to-masked center change is 0.061 px, versus 0.579 px for
HSV + partial arc. It remains a useful optional choice for data without the
red-board color prior, while the included detector reproduces this released
experiment without a GPL runtime dependency.
