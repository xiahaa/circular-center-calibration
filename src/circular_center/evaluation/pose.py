"""PnP-RANSAC fitting and pose metrics used by synthetic experiments."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PoseEstimate:
    rotation: np.ndarray
    translation: np.ndarray
    inlier_mask: np.ndarray
    mean_reprojection_error_px: float


@dataclass(frozen=True)
class PoseMetrics:
    reprojection_error_px: float
    rotation_error_rad: float
    translation_error: float


def _opencv():
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError("OpenCV is required for PnP evaluation") from error
    return cv2


def _validated_correspondences(points3d, points2d, intrinsic):
    points3d = np.asarray(points3d, dtype=float)
    points2d = np.asarray(points2d, dtype=float)
    intrinsic = np.asarray(intrinsic, dtype=float)
    if points3d.ndim != 2 or points3d.shape[1] != 3 or len(points3d) < 4:
        raise ValueError("points3d must have shape (N, 3) with N >= 4")
    if points2d.shape != (len(points3d), 2):
        raise ValueError("points2d must have shape (N, 2)")
    if intrinsic.shape != (3, 3):
        raise ValueError("intrinsic must have shape (3, 3)")
    if not all(np.isfinite(value).all() for value in (points3d, points2d, intrinsic)):
        raise ValueError("PnP inputs must be finite")
    return points3d, points2d, intrinsic


def project_points(points3d, rotation, translation, intrinsic) -> np.ndarray:
    points3d = np.asarray(points3d, dtype=float)
    camera_points = (
        np.asarray(rotation, dtype=float) @ points3d.T
        + np.asarray(translation, dtype=float).reshape(3, 1)
    )
    if np.any(np.abs(camera_points[2]) <= np.finfo(float).eps):
        raise ValueError("pose projects a point onto the camera plane")
    projected = np.asarray(intrinsic, dtype=float) @ camera_points
    return (projected[:2] / projected[2]).T


def fit_pnp_ransac(
    points3d,
    points2d,
    intrinsic,
    *,
    iterations: int = 100,
    reprojection_threshold_px: float = 5.0,
    confidence: float = 0.99,
    seed: int = 2025,
) -> PoseEstimate:
    """Fit a camera pose and report mean error over OpenCV's inlier set."""

    cv2 = _opencv()
    points3d, points2d, intrinsic = _validated_correspondences(
        points3d, points2d, intrinsic
    )
    if iterations <= 0 or reprojection_threshold_px <= 0.0:
        raise ValueError("iterations and reprojection_threshold_px must be positive")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0, 1)")
    cv2.setRNGSeed(int(seed) & 0x7FFFFFFF)
    try:
        success, rotation_vector, translation, inliers = cv2.solvePnPRansac(
            points3d.astype(np.float32),
            points2d.astype(np.float32),
            intrinsic,
            np.zeros(5),
            flags=cv2.SOLVEPNP_ITERATIVE,
            iterationsCount=int(iterations),
            reprojectionError=float(reprojection_threshold_px),
            confidence=float(confidence),
        )
    except cv2.error as error:
        raise RuntimeError("OpenCV solvePnPRansac failed") from error
    if not success or inliers is None or len(inliers) < 4:
        raise RuntimeError("OpenCV solvePnPRansac found fewer than four inliers")
    rotation = cv2.Rodrigues(rotation_vector)[0]
    inlier_mask = np.zeros(len(points3d), dtype=bool)
    inlier_mask[np.asarray(inliers, dtype=int).reshape(-1)] = True
    projected = project_points(
        points3d[inlier_mask], rotation, translation, intrinsic
    )
    mean_error = float(
        np.mean(np.linalg.norm(projected - points2d[inlier_mask], axis=1))
    )
    return PoseEstimate(
        rotation=np.asarray(rotation, dtype=float),
        translation=np.asarray(translation, dtype=float).reshape(3, 1),
        inlier_mask=inlier_mask,
        mean_reprojection_error_px=mean_error,
    )


def evaluate_pose(
    estimate: PoseEstimate,
    expected_rotation,
    expected_translation,
) -> PoseMetrics:
    cv2 = _opencv()
    relative = (
        np.asarray(expected_rotation, dtype=float).T
        @ np.asarray(estimate.rotation, dtype=float)
    )
    rotation_vector = cv2.Rodrigues(relative)[0]
    translation_error = np.linalg.norm(
        np.asarray(estimate.translation, dtype=float).reshape(3, 1)
        - np.asarray(expected_translation, dtype=float).reshape(3, 1)
    )
    return PoseMetrics(
        reprojection_error_px=float(estimate.mean_reprojection_error_px),
        rotation_error_rad=float(np.linalg.norm(rotation_vector)),
        translation_error=float(translation_error),
    )


__all__ = [
    "PoseEstimate",
    "PoseMetrics",
    "evaluate_pose",
    "fit_pnp_ransac",
    "project_points",
]
