# SPDX-License-Identifier: Apache-2.0
"""Numerically normalized conformal-geometric-algebra circle fitting."""

from typing import Tuple

import numpy as np

from .types import CircleFitError, FitStatus

CircleTuple = Tuple[np.ndarray, float, np.ndarray]

# The last two conformal coordinates form a null pair.  The resulting
# scatter operator is real but not Euclidean-symmetric, so its near-zero
# eigenspace must not be selected with an ordinary PSD eigenvalue ordering.
_CGA_METRIC = np.array(
    [
        [1.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0, -1.0],
        [0.0, 0.0, 0.0, -1.0, 0.0],
    ]
)


def canonicalize_normal(normal: np.ndarray) -> np.ndarray:
    """Return a unit, deterministic representative of an unoriented normal."""
    normal = np.asarray(normal, dtype=float).reshape(3)
    norm = float(np.linalg.norm(normal))
    if not np.isfinite(norm) or norm <= np.finfo(float).eps:
        raise CircleFitError(FitStatus.DEGENERATE, "circle normal must be non-zero")
    normal = normal / norm
    pivot = int(np.argmax(np.abs(normal)))
    if normal[pivot] < 0.0:
        normal = -normal
    return normal


def _validate_points(points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or 3 not in points.shape:
        raise CircleFitError(
            FitStatus.INVALID_INPUT,
            "points must have shape (N, 3) or (3, N)",
        )
    if points.shape[1] != 3 and points.shape[0] == 3:
        points = points.T
    if points.shape[1] != 3:
        raise CircleFitError(FitStatus.INVALID_INPUT, "points must have three columns")
    if points.shape[0] < 3:
        raise CircleFitError(FitStatus.INVALID_INPUT, "at least three points are required")
    if not np.isfinite(points).all():
        raise CircleFitError(FitStatus.INVALID_INPUT, "points must be finite")
    return points


def construct_cga_p_from_batch(points: np.ndarray) -> np.ndarray:
    """Accumulate the fixed 5x5 conformal scatter operator without a 5xN matrix."""
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or points.shape[0] == 0:
        raise CircleFitError(FitStatus.INVALID_INPUT, "expected a non-empty (N, 3) array")
    if not np.isfinite(points).all():
        raise CircleFitError(FitStatus.INVALID_INPUT, "points must be finite")

    squared_half_norms = 0.5 * np.einsum("ij,ij->i", points, points)
    scatter = np.empty((5, 5), dtype=float)
    scatter[:3, :3] = points.T @ points
    coordinate_sums = np.sum(points, axis=0)
    scatter[:3, 3] = coordinate_sums
    scatter[3, :3] = coordinate_sums
    coordinate_quadric = points.T @ squared_half_norms
    scatter[:3, 4] = coordinate_quadric
    scatter[4, :3] = coordinate_quadric
    scatter[3, 3] = float(points.shape[0])
    scatter[3, 4] = float(np.sum(squared_half_norms))
    scatter[4, 3] = scatter[3, 4]
    scatter[4, 4] = float(np.dot(squared_half_norms, squared_half_norms))
    return (scatter @ _CGA_METRIC) / float(points.shape[0])


def _fit_normalized_cga(
    points: np.ndarray,
    verbose: bool = False,
) -> Tuple[np.ndarray, float, np.ndarray, float]:
    points = _validate_points(points)
    centroid = np.mean(points, axis=0)
    centered = points - centroid
    singular_values = np.linalg.svd(centered, compute_uv=False)
    rank_tolerance = (
        np.finfo(float).eps
        * max(centered.shape)
        * max(1.0, float(singular_values[0]))
    )
    if singular_values[1] <= rank_tolerance:
        raise CircleFitError(
            FitStatus.DEGENERATE,
            "at least three non-collinear points are required",
        )

    rms_distance = float(
        np.sqrt(np.mean(np.einsum("ij,ij->i", centered, centered)))
    )
    if rms_distance <= np.finfo(float).eps:
        raise CircleFitError(FitStatus.DEGENERATE, "point spread is too small")
    scale = np.sqrt(2.0) / rms_distance
    operator = construct_cga_p_from_batch(centered * scale)

    try:
        eigenvalues, eigenvectors = np.linalg.eig(operator)
    except np.linalg.LinAlgError as error:
        raise CircleFitError(
            FitStatus.NUMERICAL_FAILURE,
            "CGA eigendecomposition failed",
        ) from error

    null_indices = np.argsort(np.abs(eigenvalues))[:2]
    spectrum_scale = max(1.0, float(np.max(np.abs(eigenvalues))))
    if np.max(np.abs(eigenvalues[null_indices].imag)) > 1e-10 * spectrum_scale:
        raise CircleFitError(
            FitStatus.NUMERICAL_FAILURE,
            "selected CGA eigenvalues are materially complex",
        )

    selected = eigenvectors[:, null_indices]
    real_candidates = np.column_stack((selected.real, selected.imag))
    real_basis, subspace_singular_values, _ = np.linalg.svd(
        real_candidates,
        full_matrices=False,
    )
    subspace_tolerance = (
        100.0
        * np.finfo(float).eps
        * max(real_candidates.shape)
        * max(1.0, float(subspace_singular_values[0]))
    )
    if subspace_singular_values[1] <= subspace_tolerance:
        raise CircleFitError(
            FitStatus.NUMERICAL_FAILURE,
            "CGA near-zero eigenvectors do not span a real 2D subspace",
        )

    bivector = cga_outer_product(real_basis[:, 1], real_basis[:, 0])
    center, radius, normal = cga_recover_circle_parameter(bivector, verbose)
    center = center / scale + centroid
    radius = radius / scale

    operator_singular_values = np.linalg.svd(operator, compute_uv=False)
    non_null_floor = max(
        np.finfo(float).eps * operator_singular_values[0],
        np.finfo(float).tiny,
    )
    condition_number = float(
        operator_singular_values[0]
        / max(operator_singular_values[2], non_null_floor)
    )
    if verbose:
        print(f"Selected near-zero eigenvalues: {eigenvalues[null_indices]}")
        print(f"Non-null spectrum condition number: {condition_number}")
    return center, float(radius), canonicalize_normal(normal), condition_number


def cga_circle_fitting_joint(points: np.ndarray, verbose: bool = False) -> CircleTuple:
    """Return center, radius, and normal from the normalized CGA fit."""
    center, radius, normal, _ = _fit_normalized_cga(points, verbose)
    return center, radius, normal


def cga_circle_fitting_joint_with_diagnostics(
    points: np.ndarray,
    verbose: bool = False,
) -> Tuple[np.ndarray, float, np.ndarray, float]:
    """Return the tuple fit plus the normalized non-null spectrum condition."""
    return _fit_normalized_cga(points, verbose)


def cga_outer_product(y: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Compute the 10 coefficients of the wedge product ``y ^ x``."""
    y = np.asarray(y, dtype=float).reshape(5)
    x = np.asarray(x, dtype=float).reshape(5)

    def skew(vector: np.ndarray) -> np.ndarray:
        return np.array(
            [
                [0.0, -vector[2], vector[1]],
                [vector[2], 0.0, -vector[0]],
                [-vector[1], vector[0], 0.0],
            ]
        )

    matrix = np.zeros((10, 5), dtype=float)
    matrix[:3, :3] = skew(y[:3])
    matrix[3:6, :3] = y[3] * np.eye(3)
    matrix[3:6, 3] = -y[:3]
    matrix[6:9, :3] = -y[4] * np.eye(3)
    matrix[6:9, 4] = y[:3]
    matrix[9, 3] = -y[4]
    matrix[9, 4] = y[3]
    return matrix @ x


def cga_recover_circle_parameter(
    representation: np.ndarray,
    verbose: bool = False,
) -> CircleTuple:
    """Recover center, radius, and unoriented normal from a CGA bivector."""
    representation = np.asarray(representation, dtype=float).squeeze()
    if representation.shape != (10,) or not np.isfinite(representation).all():
        raise CircleFitError(
            FitStatus.NUMERICAL_FAILURE,
            "expected a finite 10-element CGA circle representation",
        )

    euclidean = representation[:3]
    origin = representation[3:6]
    infinity = representation[6:9]
    origin_infinity = -representation[9]
    tolerance = 100.0 * np.finfo(float).eps * max(
        1.0,
        float(np.linalg.norm(representation)),
    )
    alpha = float(np.linalg.norm(origin))
    if alpha <= tolerance:
        raise CircleFitError(FitStatus.DEGENERATE, "degenerate CGA normal")

    unit_normal = -origin / alpha
    normal = -origin
    normal_squared = float(np.dot(normal, normal))
    if normal_squared <= tolerance * tolerance:
        raise CircleFitError(FitStatus.DEGENERATE, "zero CGA normal magnitude")

    b0, b1, b2, b3 = (
        origin_infinity,
        euclidean[0],
        euclidean[1],
        euclidean[2],
    )
    b_matrix = (
        b0 * np.eye(3)
        + b1 * np.array([[0.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])
        + b2 * np.array([[0.0, 0.0, 1.0], [0.0, 0.0, 0.0], [-1.0, 0.0, 0.0]])
        + b3 * np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    )
    center = (b_matrix @ normal) / normal_squared
    axial_center = float(np.dot(center, unit_normal))
    radius_squared = (
        float(np.dot(center, center))
        - 2.0 * float(np.dot(unit_normal, infinity)) / alpha
        - 2.0 * axial_center * axial_center
    )
    radius_tolerance = 1e-10 * max(
        1.0,
        float(np.dot(center, center)),
        abs(radius_squared),
    )
    if radius_squared < -radius_tolerance:
        raise CircleFitError(
            FitStatus.NUMERICAL_FAILURE,
            f"CGA solution has negative squared radius: {radius_squared}",
        )
    radius = float(np.sqrt(max(0.0, radius_squared)))
    if verbose:
        print(f"Center: {center}")
        print(f"Radius: {radius}")
        print(f"Normal: {unit_normal}")
    return center, radius, canonicalize_normal(unit_normal)


__all__ = [
    "canonicalize_normal",
    "cga_circle_fitting_joint",
    "cga_circle_fitting_joint_with_diagnostics",
    "cga_outer_product",
    "cga_recover_circle_parameter",
    "construct_cga_p_from_batch",
]
