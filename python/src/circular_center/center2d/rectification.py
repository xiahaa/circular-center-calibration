# SPDX-License-Identifier: Apache-2.0
"""Pinhole and fisheye contour rectification before conic fitting."""

from typing import Optional, Tuple

import numpy as np


def rectify_contour(
    contour: np.ndarray,
    K: np.ndarray,
    distortion: np.ndarray,
    *,
    model: str,
    rectified_K: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return undistorted pixel coordinates and their rectified intrinsic matrix."""
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError("OpenCV is required for contour rectification") from error

    points = np.asarray(contour, dtype=float)
    intrinsic = np.asarray(K, dtype=float)
    distortion = np.asarray(distortion, dtype=float).reshape(-1)
    target_intrinsic = (
        intrinsic.copy()
        if rectified_K is None
        else np.asarray(rectified_K, dtype=float)
    )
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("contour must have shape (N, 2)")
    if intrinsic.shape != (3, 3) or target_intrinsic.shape != (3, 3):
        raise ValueError("K and rectified_K must have shape (3, 3)")
    if not all(
        np.isfinite(array).all()
        for array in (points, intrinsic, distortion, target_intrinsic)
    ):
        raise ValueError("rectification inputs must be finite")
    shaped = points.reshape(-1, 1, 2)
    if model == "pinhole":
        rectified = cv2.undistortPoints(
            shaped,
            intrinsic,
            distortion,
            P=target_intrinsic,
        )
    elif model == "fisheye":
        if distortion.size != 4:
            raise ValueError("fisheye distortion must contain exactly four coefficients")
        rectified = cv2.fisheye.undistortPoints(
            shaped,
            intrinsic,
            distortion.reshape(4, 1),
            P=target_intrinsic,
        )
    else:
        raise ValueError("model must be 'pinhole' or 'fisheye'")
    return rectified.reshape(-1, 2), target_intrinsic


__all__ = ["rectify_contour"]
