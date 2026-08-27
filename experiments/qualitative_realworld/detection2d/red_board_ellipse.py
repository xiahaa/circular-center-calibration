"""Detect the bright circular insert as a hole in the red board mask."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

import cv2
import numpy as np

from circular_center.center2d import get_ellipse_polynomial_coeff, rectify_contour


@dataclass(frozen=True)
class DetectedTarget:
    ellipse: np.ndarray
    polynomial: np.ndarray
    rectified_contour: np.ndarray
    rectified_cv_ellipse: tuple
    board_area_px2: float
    circle_area_px2: float
    axis_ratio: float
    detector: str
    detector_score: Optional[float] = None
    red_annulus_fraction: Optional[float] = None
    neutral_interior_fraction: Optional[float] = None


def _red_mask(image: np.ndarray, config: Mapping[str, object]) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, saturation, value = cv2.split(hsv)
    mask = (
        ((hue <= int(config["low_hue_max"])) | (hue >= int(config["high_hue_min"])))
        & (saturation >= int(config["minimum_saturation"]))
        & (value >= int(config["minimum_value"]))
    )
    kernel_size = int(config["close_kernel_px"])
    if kernel_size < 1 or kernel_size % 2 == 0:
        raise ValueError("close_kernel_px must be a positive odd integer")
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    return cv2.morphologyEx(
        mask.astype(np.uint8) * 255,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=int(config["close_iterations"]),
    )


def detect_red_board_ellipse(
    image: np.ndarray,
    intrinsic: np.ndarray,
    distortion: np.ndarray,
    distortion_model: str,
    config: Mapping[str, object],
) -> DetectedTarget:
    if image is None or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("image must be a BGR array")
    mask_config = config["red_mask"]
    candidate_config = config["ellipse_candidate"]
    if not isinstance(mask_config, Mapping) or not isinstance(candidate_config, Mapping):
        raise ValueError("invalid 2D detection configuration")
    contours, hierarchy = cv2.findContours(
        _red_mask(image, mask_config), cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE
    )
    if hierarchy is None:
        raise ValueError("red calibration board was not detected")
    hierarchy = hierarchy[0]
    ratio_min, ratio_max = (
        float(value) for value in candidate_config["hole_to_board_area_ratio"]
    )
    candidates = []
    for index, contour in enumerate(contours):
        parent = int(hierarchy[index, 3])
        if parent < 0 or len(contour) < 5:
            continue
        circle_area = abs(float(cv2.contourArea(contour)))
        board_area = abs(float(cv2.contourArea(contours[parent])))
        if circle_area < float(candidate_config["minimum_hole_area_px2"]):
            continue
        if board_area < float(candidate_config["minimum_board_area_px2"]):
            continue
        area_ratio = circle_area / board_area
        if not ratio_min <= area_ratio <= ratio_max:
            continue
        raw_ellipse = cv2.fitEllipse(contour)
        first_axis, second_axis = (float(value) for value in raw_ellipse[1])
        axis_ratio = min(first_axis, second_axis) / max(first_axis, second_axis)
        if axis_ratio < float(candidate_config["minimum_axis_ratio"]):
            continue
        score = circle_area * axis_ratio * axis_ratio
        candidates.append((score, contour.reshape(-1, 2), board_area, circle_area, axis_ratio))
    if not candidates:
        raise ValueError("no ellipse-shaped hole was found inside the red board")
    _, raw_contour, board_area, circle_area, axis_ratio = max(
        candidates, key=lambda candidate: candidate[0]
    )

    if distortion_model not in {"plumb_bob", "rational_polynomial"}:
        raise ValueError("unsupported camera distortion model {!r}".format(distortion_model))
    rectified, _ = rectify_contour(
        raw_contour,
        intrinsic,
        distortion,
        model="pinhole",
        rectified_K=intrinsic,
    )
    rectified_cv_ellipse = cv2.fitEllipse(rectified.astype(np.float32).reshape(-1, 1, 2))
    ellipse = np.array(
        [
            rectified_cv_ellipse[0][0],
            rectified_cv_ellipse[0][1],
            rectified_cv_ellipse[1][0] / 2.0,
            rectified_cv_ellipse[1][1] / 2.0,
            np.deg2rad(rectified_cv_ellipse[2]),
        ],
        dtype=float,
    )
    return DetectedTarget(
        ellipse=ellipse,
        polynomial=get_ellipse_polynomial_coeff(rectified_cv_ellipse),
        rectified_contour=rectified,
        rectified_cv_ellipse=rectified_cv_ellipse,
        board_area_px2=board_area,
        circle_area_px2=circle_area,
        axis_ratio=axis_ratio,
        detector="opencv_red_board",
    )


__all__ = ["DetectedTarget", "detect_red_board_ellipse"]
