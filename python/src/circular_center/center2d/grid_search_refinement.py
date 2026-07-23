# SPDX-License-Identifier: Apache-2.0
"""Vectorized coarse-to-fine search for the two projected-center candidates."""

from time import perf_counter
from typing import Optional, Sequence

import numpy as np

from . import find_rectify_homography as frh
from .ellipse_center_refinement import eval_distance_f0_batch
from .types import (
    ProjectedCenterError,
    ProjectedCenterResult,
    ProjectedCenterStatus,
)


def _validate_ellipse(ellipse: np.ndarray) -> np.ndarray:
    values = np.asarray(ellipse, dtype=float).reshape(-1)
    if values.shape != (5,) or not np.isfinite(values).all():
        raise ProjectedCenterError(
            ProjectedCenterStatus.INVALID_INPUT,
            "ellipse must contain finite (cx, cy, semi_a, semi_b, angle_radians)",
        )
    if values[2] <= 0.0 or values[3] <= 0.0:
        raise ProjectedCenterError(
            ProjectedCenterStatus.INVALID_INPUT,
            "ellipse semi-axes must be positive",
        )
    return values


def _rotation(angle: float) -> np.ndarray:
    return np.array(
        [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]],
        dtype=float,
    )


def _inside_search_ellipse(
    candidates: np.ndarray,
    ellipse: np.ndarray,
    search_ratio: float,
) -> np.ndarray:
    center = ellipse[:2]
    local = (candidates - center) @ _rotation(ellipse[4])
    semi_axes = ellipse[2:4] * search_ratio
    return np.sum(np.square(local / semi_axes), axis=1) <= 1.0 + 1e-12


def generate_masked_points(
    ellipse: np.ndarray,
    search_ratio: float,
    K: Optional[np.ndarray] = None,
    step: float = 2.0,
) -> np.ndarray:
    """Generate a floating-point grid inside the scaled fitted ellipse.

    ``K`` is retained for source compatibility and is intentionally unused.
    Unlike the original routine, candidates are not rounded to integer pixels.
    """
    del K
    ellipse = _validate_ellipse(ellipse)
    if not 0.0 < search_ratio <= 1.0 or step <= 0.0:
        raise ProjectedCenterError(
            ProjectedCenterStatus.INVALID_INPUT,
            "search_ratio must be in (0, 1] and step must be positive",
        )
    semi_a, semi_b = ellipse[2:4] * search_ratio
    x = np.arange(-semi_a, semi_a + 0.5 * step, step)
    y = np.arange(-semi_b, semi_b + 0.5 * step, step)
    xx, yy = np.meshgrid(x, y, indexing="xy")
    local = np.column_stack((xx.ravel(), yy.ravel()))
    inside = np.sum(np.square(local / np.array([semi_a, semi_b])), axis=1) <= 1.0
    return local[inside] @ _rotation(ellipse[4]).T + ellipse[:2]


def _minimum_indices(
    centers: np.ndarray,
    scores: np.ndarray,
    k: int,
    suppress_radius: float,
) -> list:
    scores = np.asarray(scores, dtype=float).reshape(-1)
    order = np.argsort(scores, kind="stable")
    selected = []
    for index in order:
        if not np.isfinite(scores[index]):
            continue
        if all(np.linalg.norm(centers[index] - centers[chosen]) >= suppress_radius for chosen in selected):
            selected.append(int(index))
            if len(selected) == k:
                break
    if len(selected) < k:
        for index in order:
            if np.isfinite(scores[index]) and int(index) not in selected:
                selected.append(int(index))
                if len(selected) == k:
                    break
    return selected


def select_minima_with_suppression(
    centers: np.ndarray,
    scores: np.ndarray,
    k: int = 2,
    suppress_radius: float = 15.0,
) -> list:
    """Compatibility helper returning score-ordered NMS center locations."""
    centers = np.asarray(centers, dtype=float)
    if centers.ndim != 2 or centers.shape[1] != 2 or len(centers) == 0:
        return []
    return [
        centers[index]
        for index in _minimum_indices(centers, scores, k, suppress_radius)
    ]


def _local_candidates(
    seeds: np.ndarray,
    half_width: float,
    step: float,
    ellipse: np.ndarray,
    search_ratio: float,
) -> np.ndarray:
    # Express the local windows on the same ellipse-aligned lattice used by
    # ``generate_masked_points``.  Offsetting a fresh grid from every seed
    # creates many sub-pixel lattice phases: an optimized minimum may then be
    # better than, but several pixels away from, the dense reference.
    # A shared origin makes the 0.1-px final candidates directly comparable
    # while still evaluating only windows around the retained coarse basins.
    rotation = _rotation(ellipse[4])
    local_seeds = (np.asarray(seeds, dtype=float) - ellipse[:2]) @ rotation
    semi_axes = ellipse[2:4] * search_ratio
    origin = -semi_axes
    local_batches = []
    for local_seed in local_seeds:
        lower = np.ceil((local_seed - half_width - origin) / step).astype(int)
        upper = np.floor((local_seed + half_width - origin) / step).astype(int)
        x = origin[0] + step * np.arange(lower[0], upper[0] + 1)
        y = origin[1] + step * np.arange(lower[1], upper[1] + 1)
        xx, yy = np.meshgrid(x, y, indexing="xy")
        local_batches.append(np.column_stack((xx.ravel(), yy.ravel())))
    local = np.vstack(local_batches)
    inside = np.sum(np.square(local / semi_axes), axis=1) <= 1.0 + 1e-12
    candidates = local[inside] @ rotation.T + ellipse[:2]
    return np.unique(np.round(candidates, decimals=10), axis=0)


def _make_result(
    candidates: np.ndarray,
    scores: np.ndarray,
    evaluations: int,
    directions: int,
    elapsed_seconds: float,
) -> ProjectedCenterResult:
    score_gap = float(abs(scores[1] - scores[0]))
    scale = max(float(abs(scores[0])), float(abs(scores[1])), np.finfo(float).eps)
    confidence = float(np.clip(score_gap / scale, 0.0, 1.0))
    ambiguous = confidence < 0.05
    return ProjectedCenterResult(
        candidates=np.asarray(candidates, dtype=float),
        scores=np.asarray(scores, dtype=float),
        confidence=confidence,
        ambiguous=ambiguous,
        score_gap=score_gap,
        evaluations=int(evaluations),
        directions=int(directions),
        status=(
            ProjectedCenterStatus.AMBIGUOUS
            if ambiguous
            else ProjectedCenterStatus.SUCCESS
        ),
        elapsed_seconds=float(elapsed_seconds),
    )


def refine_projected_center(
    ellipse: np.ndarray,
    polynomial: np.ndarray,
    rectified_K: np.ndarray,
    marker_diameter: float,
    *,
    input_is_rectified: bool,
    search_ratio: float = 0.5,
    directions: int = 16,
    levels: Sequence[float] = (2.0, 0.5, 0.1),
    nms_scale: float = 0.08,
) -> ProjectedCenterResult:
    """Find both candidates on an undistorted contour with its rectified ``K``.

    Raw pinhole- or fisheye-distorted contours are generally not conics.  The
    pipeline must therefore undistort the contour (or image) first and pass the
    corresponding rectified intrinsic matrix.  The explicit boolean prevents
    a caller from silently omitting that preprocessing decision.
    """
    start = perf_counter()
    ellipse = _validate_ellipse(ellipse)
    intrinsic = np.asarray(rectified_K, dtype=float)
    polynomial = np.asarray(polynomial, dtype=float).reshape(-1)
    levels = tuple(float(level) for level in levels)
    if not input_is_rectified:
        raise ProjectedCenterError(
            ProjectedCenterStatus.INVALID_INPUT,
            "distorted contours are unsupported; undistort before conic fitting",
        )
    if intrinsic.shape != (3, 3) or not np.isfinite(intrinsic).all():
        raise ProjectedCenterError(
            ProjectedCenterStatus.INVALID_INPUT,
            "rectified_K must be a finite 3x3 matrix",
        )
    if polynomial.shape != (6,) or not np.isfinite(polynomial).all():
        raise ProjectedCenterError(
            ProjectedCenterStatus.INVALID_INPUT,
            "polynomial must contain six finite conic coefficients",
        )
    if marker_diameter <= 0.0 or directions <= 0:
        raise ProjectedCenterError(
            ProjectedCenterStatus.INVALID_INPUT,
            "marker_diameter and directions must be positive",
        )
    if levels != (2.0, 0.5, 0.1):
        raise ProjectedCenterError(
            ProjectedCenterStatus.INVALID_INPUT,
            "supported search levels are (2.0, 0.5, 0.1) pixels",
        )
    try:
        inverse_intrinsic = np.linalg.inv(intrinsic)
    except np.linalg.LinAlgError as error:
        raise ProjectedCenterError(
            ProjectedCenterStatus.INVALID_INPUT,
            "rectified_K must be invertible",
        ) from error

    suppression = max(0.2, nms_scale * float(min(ellipse[2], ellipse[3])))
    candidates = generate_masked_points(
        ellipse,
        search_ratio,
        step=levels[0],
    )
    evaluations = 0
    selected_centers = None
    selected_scores = None
    previous_step = levels[0]
    # Retaining only two coarse seeds can place both in the same attraction
    # basin when the ellipse is small relative to the 2-px grid.  Preserve a
    # wider deterministic beam at the two coarse levels and collapse to the
    # two reported minima only after 0.1-px refinement.
    retained_seed_counts = (32, 16, 2)
    for level_index, step in enumerate(levels):
        if level_index > 0:
            candidates = _local_candidates(
                selected_centers,
                half_width=previous_step,
                step=step,
                ellipse=ellipse,
                search_ratio=search_ratio,
            )
        scores = eval_distance_f0_batch(
            polynomial,
            candidates,
            intrinsic,
            marker_diameter,
            N=directions,
            inverse_intrinsic=inverse_intrinsic,
        )
        evaluations += len(candidates)
        requested = min(retained_seed_counts[level_index], len(candidates))
        indices = _minimum_indices(candidates, scores, requested, suppression)
        if len(indices) < 2:
            raise ProjectedCenterError(
                ProjectedCenterStatus.NUMERICAL_FAILURE,
                "fewer than two finite projected-center candidates were found",
            )
        selected_centers = candidates[indices]
        selected_scores = scores[indices]
        previous_step = step

    order = np.argsort(selected_scores, kind="stable")[:2]
    return _make_result(
        selected_centers[order],
        selected_scores[order],
        evaluations,
        directions,
        perf_counter() - start,
    )


def dense_grid_search_reference(
    ellipse: np.ndarray,
    polynomial: np.ndarray,
    rectified_K: np.ndarray,
    marker_diameter: float,
    *,
    input_is_rectified: bool,
    search_ratio: float = 0.5,
    directions: int = 16,
    step: float = 0.1,
) -> ProjectedCenterResult:
    """Dense vectorized reference retained only for accuracy/performance tests."""
    if not input_is_rectified:
        raise ProjectedCenterError(
            ProjectedCenterStatus.INVALID_INPUT,
            "dense reference also requires an undistorted contour",
        )
    start = perf_counter()
    ellipse = _validate_ellipse(ellipse)
    candidates = generate_masked_points(ellipse, search_ratio, step=step)
    intrinsic = np.asarray(rectified_K, dtype=float)
    scores = eval_distance_f0_batch(
        polynomial,
        candidates,
        intrinsic,
        marker_diameter,
        N=directions,
        inverse_intrinsic=np.linalg.inv(intrinsic),
    )
    suppression = max(0.2, 0.08 * float(min(ellipse[2], ellipse[3])))
    indices = _minimum_indices(candidates, scores, 2, suppression)
    if len(indices) < 2:
        raise ProjectedCenterError(
            ProjectedCenterStatus.NUMERICAL_FAILURE,
            "dense reference found fewer than two finite candidates",
        )
    chosen_scores = scores[indices]
    order = np.argsort(chosen_scores, kind="stable")
    return _make_result(
        candidates[indices][order],
        chosen_scores[order],
        len(candidates),
        directions,
        perf_counter() - start,
    )


def select_projected_center_by_homography(
    ell,
    poly,
    ep,
    ep_alt,
    K,
    radius,
    nominal_radius_ratio=1.0,
):
    """Select between two candidates using a second coplanar circle.

    ``ep`` and ``ep_alt`` are rectified ellipse contours with shape ``(2, N)``.
    The nominal ratio is the physical radius of the first circle divided by
    that of the second circle.
    """
    result = refine_projected_center(
        ell,
        poly,
        K,
        marker_diameter=2.0 * radius,
        input_is_rectified=True,
        search_ratio=0.5,
    )
    candidates = result.candidates
    ratio_errors = []
    ex, ey, ea, eb, angle = ell
    ellipse_cv = [[ex, ey], [ea * 2.0, eb * 2.0], angle * 180.0 / np.pi]
    for candidate in candidates:
        homography, _, transform = frh.find_homography(ellipse_cv, candidate[:2])
        transformed_sets = []
        for points in (ep, ep_alt):
            homogeneous = np.vstack((points, np.ones((1, points.shape[1]))))
            transformed = homography @ transform @ homogeneous
            transformed_sets.append(transformed / transformed[-1, :])
        radii = []
        for transformed in transformed_sets:
            center = np.mean(transformed, axis=1, keepdims=True)
            radii.append(float(np.mean(np.linalg.norm(transformed - center, axis=0))))
        ratio_errors.append(
            abs(radii[0] / (radii[1] + 1e-8) - nominal_radius_ratio)
        )
    chosen = int(np.argmin(ratio_errors))
    return candidates[chosen].copy(), candidates[1 - chosen].copy()


__all__ = [
    "dense_grid_search_reference",
    "generate_masked_points",
    "refine_projected_center",
    "select_minima_with_suppression",
    "select_projected_center_by_homography",
]
