# SPDX-License-Identifier: Apache-2.0
"""Public normalized-CGA and CGA-RANSAC interfaces for 3D circles."""

from time import perf_counter
from typing import Callable, Optional, Tuple, Union

import numpy as np

from .cga_joint_fitting import (
    canonicalize_normal,
    cga_circle_fitting_joint,
    cga_circle_fitting_joint_with_diagnostics,
)
from .types import CircleFitError, CircleFitResult, FitStatus


CircleTuple = Tuple[np.ndarray, float, np.ndarray]
CircleFitter = Callable[[np.ndarray], Union[CircleTuple, CircleFitResult]]


def _validate_points(points: np.ndarray, minimum_count: int = 3) -> np.ndarray:
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3:
        raise CircleFitError(FitStatus.INVALID_INPUT, "points must have shape (N, 3)")
    if points.shape[0] < minimum_count:
        raise CircleFitError(
            FitStatus.INVALID_INPUT,
            f"at least {minimum_count} points are required",
        )
    if not np.isfinite(points).all():
        raise CircleFitError(FitStatus.INVALID_INPUT, "points must contain only finite values")
    return points


def circle_residuals(
    points: np.ndarray,
    center: np.ndarray,
    radius: float,
    normal: np.ndarray,
) -> np.ndarray:
    """Return Euclidean distances from 3D points to a circle."""
    points = _validate_points(points)
    center = np.asarray(center, dtype=float).reshape(3)
    radius = float(radius)
    if not np.isfinite(center).all():
        raise CircleFitError(FitStatus.INVALID_INPUT, "circle center must be finite")
    if not np.isfinite(radius) or radius < 0.0:
        raise CircleFitError(
            FitStatus.INVALID_INPUT,
            "circle radius must be finite and non-negative",
        )
    normal = canonicalize_normal(normal)
    offsets = points - center
    plane = offsets @ normal
    in_plane = offsets - plane[:, None] * normal
    radial = np.linalg.norm(in_plane, axis=1) - radius
    return np.hypot(plane, radial)


def _make_result(
    method: str,
    points: np.ndarray,
    center: np.ndarray,
    radius: float,
    normal: np.ndarray,
    *,
    inlier_mask: Optional[np.ndarray] = None,
    condition_number: float = float("nan"),
    iterations: int = 1,
    elapsed_seconds: float = float("nan"),
) -> CircleFitResult:
    points = _validate_points(points)
    center = np.asarray(center, dtype=float).reshape(3)
    radius = float(radius)
    if not np.isfinite(center).all() or not np.isfinite(radius) or radius < 0.0:
        raise CircleFitError(FitStatus.NUMERICAL_FAILURE, "fitted circle is not finite")
    normal = canonicalize_normal(normal)
    residuals = circle_residuals(points, center, radius, normal)
    if inlier_mask is None:
        inlier_mask = np.ones(points.shape[0], dtype=bool)
    else:
        inlier_mask = np.asarray(inlier_mask, dtype=bool).reshape(-1)
        if inlier_mask.shape[0] != points.shape[0]:
            raise CircleFitError(
                FitStatus.INVALID_INPUT,
                "inlier_mask length must match the point count",
            )
    return CircleFitResult(
        method=method,
        center=center,
        radius=radius,
        normal=normal,
        residuals=residuals,
        inlier_mask=inlier_mask,
        status=FitStatus.SUCCESS,
        condition_number=float(condition_number),
        iterations=int(iterations),
        elapsed_seconds=float(elapsed_seconds),
    )


def fit_cga_circle(points: np.ndarray) -> CircleFitResult:
    """Fit a 3D circle with normalized CGA."""
    points = _validate_points(points)
    start = perf_counter()
    center, radius, normal, condition = cga_circle_fitting_joint_with_diagnostics(points)
    return _make_result(
        "normalized_cga",
        points,
        center,
        radius,
        normal,
        condition_number=condition,
        elapsed_seconds=perf_counter() - start,
    )


def _coerce_fit_tuple(value: Union[CircleTuple, CircleFitResult]) -> CircleTuple:
    if isinstance(value, CircleFitResult):
        return value.center, value.radius, value.normal
    center, radius, normal = value
    return (
        np.asarray(center, dtype=float).reshape(3),
        float(radius),
        np.asarray(normal, dtype=float).reshape(3),
    )


def _is_degenerate_sample(points: np.ndarray) -> bool:
    centered = points - np.mean(points, axis=0)
    singular_values = np.linalg.svd(centered, compute_uv=False)
    tolerance = (
        np.finfo(float).eps
        * max(centered.shape)
        * max(1.0, float(singular_values[0]))
    )
    return bool(singular_values[1] <= tolerance)


def ransac_iteration_bound(
    inlier_ratio: float,
    sample_size: int,
    confidence: float,
    maximum: int,
) -> int:
    """Return the confidence-driven RANSAC iteration upper bound."""
    if not 0.0 <= inlier_ratio <= 1.0:
        raise CircleFitError(FitStatus.INVALID_INPUT, "inlier_ratio must be in [0, 1]")
    if sample_size <= 0 or maximum <= 0 or not 0.0 < confidence < 1.0:
        raise CircleFitError(FitStatus.INVALID_INPUT, "invalid RANSAC bound parameters")
    all_inlier_probability = inlier_ratio**sample_size
    if all_inlier_probability >= 1.0:
        return 1
    if all_inlier_probability <= np.finfo(float).eps:
        return maximum
    required = int(
        np.ceil(np.log1p(-confidence) / np.log1p(-all_inlier_probability))
    )
    return min(maximum, max(1, required))


def fit_circle_ransac(
    points: np.ndarray,
    residual_threshold: float,
    max_iterations: int = 500,
    sample_size: int = 5,
    minimum_inliers: Optional[int] = None,
    confidence: float = 0.99,
    seed: int = 0,
    fitter: CircleFitter = cga_circle_fitting_joint,
) -> CircleFitResult:
    """Robustly fit a 3D circle using deterministic, adaptive RANSAC."""
    points = _validate_points(points, minimum_count=sample_size)
    if residual_threshold <= 0.0 or max_iterations <= 0 or sample_size < 3:
        raise CircleFitError(FitStatus.INVALID_INPUT, "invalid RANSAC thresholds or counts")
    if not 0.0 < confidence < 1.0:
        raise CircleFitError(FitStatus.INVALID_INPUT, "confidence must be in (0, 1)")
    if minimum_inliers is None:
        minimum_inliers = max(sample_size, int(np.ceil(0.4 * points.shape[0])))
    if minimum_inliers < sample_size or minimum_inliers > points.shape[0]:
        raise CircleFitError(
            FitStatus.INVALID_INPUT,
            "minimum_inliers must be between sample_size and point count",
        )

    start = perf_counter()
    generator = np.random.default_rng(seed)
    best_mask = None
    best_score = None
    adaptive_limit = max_iterations
    iterations = 0
    while iterations < adaptive_limit:
        iterations += 1
        sample_indices = generator.choice(points.shape[0], sample_size, replace=False)
        sample = points[sample_indices]
        if _is_degenerate_sample(sample):
            continue
        try:
            center, radius, normal = _coerce_fit_tuple(fitter(sample))
            residuals = circle_residuals(points, center, radius, normal)
        except (CircleFitError, ValueError, np.linalg.LinAlgError, FloatingPointError):
            continue
        inlier_mask = residuals <= residual_threshold
        inlier_count = int(np.count_nonzero(inlier_mask))
        if inlier_count < minimum_inliers:
            continue
        score = (inlier_count, -float(np.median(residuals[inlier_mask])))
        if best_score is None or score > best_score:
            best_score = score
            best_mask = inlier_mask
            adaptive_limit = min(
                adaptive_limit,
                ransac_iteration_bound(
                    inlier_count / float(points.shape[0]),
                    sample_size,
                    confidence,
                    max_iterations,
                ),
            )

    if best_mask is None:
        raise CircleFitError(
            FitStatus.NO_CONSENSUS,
            "RANSAC did not find a valid circle consensus set",
        )

    center, radius, normal = _coerce_fit_tuple(fitter(points[best_mask]))
    refined_mask = circle_residuals(points, center, radius, normal) <= residual_threshold
    if np.count_nonzero(refined_mask) >= minimum_inliers:
        center, radius, normal = _coerce_fit_tuple(fitter(points[refined_mask]))
        best_mask = circle_residuals(points, center, radius, normal) <= residual_threshold

    return _make_result(
        "cga_ransac",
        points,
        center,
        radius,
        normal,
        inlier_mask=best_mask,
        iterations=iterations,
        elapsed_seconds=perf_counter() - start,
    )


__all__ = [
    "CircleFitError",
    "CircleFitResult",
    "FitStatus",
    "circle_residuals",
    "fit_cga_circle",
    "fit_circle_ransac",
    "ransac_iteration_bound",
]
