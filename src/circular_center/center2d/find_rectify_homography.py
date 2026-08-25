# SPDX-License-Identifier: Apache-2.0
"""Homography construction used to disambiguate projected-center candidates."""

import numpy as np

from .ellipse_center_refinement import get_ellipse_polynomial_coeff


def normalize_matrix_determinant(matrix: np.ndarray):
    """Scale a square matrix so that its determinant is one."""
    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("matrix must be square")
    determinant = float(np.linalg.det(matrix))
    if not np.isfinite(determinant) or abs(determinant) <= np.finfo(float).eps:
        raise ValueError("matrix must have a finite non-zero determinant")
    scale = np.sign(determinant) / abs(determinant) ** (1.0 / matrix.shape[0])
    return scale * matrix, scale


def _construct_rectifying_homography(
    q11,
    q22,
    q33,
    center_x,
    center_y,
    *,
    clamp_degenerate=False,
):
    if clamp_degenerate:
        # Historical CCFinder experiments clamp a non-real affine scale instead
        # of rejecting the candidate.  Keep that numerical behavior available
        # only when an experiment explicitly asks for paper compatibility.
        projective_denominator = q11 * center_x**2 + q33 + 1e-10
        projective = np.array(
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [q11 * center_x, q22 * center_y, q33]]
        )
        shear = q22 * center_x * center_y / projective_denominator
        radicand = (
            q22
            * q33
            / (q11 + 1e-10)
            * (q11 * center_x**2 + q22 * center_y**2 + q33)
            / projective_denominator**2
            - shear**2
        )
        scale = np.sqrt(radicand) if radicand > 1e-10 else 1e-10
        affine = np.array(
            [[1.0 / scale, -shear / scale, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        )
        conic_value = q11 * center_x**2 + q22 * center_y**2 + q33
        translate_x = (-center_x / scale + center_y * shear / scale) / conic_value
        translate_y = -center_y / conic_value
        euclidean = np.array(
            [[1.0, 0.0, translate_x], [0.0, 1.0, translate_y], [0.0, 0.0, 1.0]]
        )
        return euclidean @ affine @ projective

    denominator = q11 * center_x**2 + q33
    conic_value = q11 * center_x**2 + q22 * center_y**2 + q33
    epsilon = 1e-10
    if abs(denominator) <= epsilon or abs(q11) <= epsilon:
        raise ValueError("candidate produces a degenerate rectifying homography")

    projective = np.array(
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [q11 * center_x, q22 * center_y, q33]]
    )
    shear = q22 * center_x * center_y / denominator
    radicand = q22 * q33 / q11 * conic_value / denominator**2 - shear**2
    if not np.isfinite(radicand) or radicand <= epsilon:
        raise ValueError("candidate produces a non-real affine rectification")
    scale = np.sqrt(radicand)
    affine = np.array([[1.0 / scale, -shear / scale, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    translate_x = (-center_x / scale + center_y * shear / scale) / conic_value
    translate_y = -center_y / conic_value
    euclidean = np.array(
        [[1.0, 0.0, translate_x], [0.0, 1.0, translate_y], [0.0, 0.0, 1.0]]
    )
    return euclidean @ affine @ projective


def ellipse_to_canonical_conic(ellipse):
    """Return the image-to-canonical transform and conic matrix."""
    polynomial = get_ellipse_polynomial_coeff(ellipse)
    conic = np.array(
        [
            [polynomial[0], polynomial[1] / 2.0, polynomial[3] / 2.0],
            [polynomial[1] / 2.0, polynomial[2], polynomial[4] / 2.0],
            [polynomial[3] / 2.0, polynomial[4] / 2.0, polynomial[5]],
        ]
    )
    center_x, center_y = ellipse[0]
    angle = np.deg2rad(ellipse[2])
    rotate = np.array(
        [
            [np.cos(angle), np.sin(angle), 0.0],
            [-np.sin(angle), np.cos(angle), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    translate = np.array(
        [[1.0, 0.0, -center_x], [0.0, 1.0, -center_y], [0.0, 0.0, 1.0]]
    )
    transform = rotate @ translate
    inverse = np.linalg.inv(transform)
    canonical = inverse.T @ conic @ inverse
    return transform, canonical, conic


def find_homography(ellipse, center, *, clamp_degenerate=False):
    """Construct a circle-plane rectification for one center candidate."""
    transform, canonical, _ = ellipse_to_canonical_conic(ellipse)
    homogeneous_center = np.append(np.asarray(center, dtype=float).reshape(2), 1.0)
    canonical_center = transform @ homogeneous_center
    homography = _construct_rectifying_homography(
        canonical[0, 0],
        canonical[1, 1],
        canonical[2, 2],
        canonical_center[0],
        canonical_center[1],
        clamp_degenerate=clamp_degenerate,
    )
    return homography, canonical, transform


__all__ = [
    "ellipse_to_canonical_conic",
    "find_homography",
    "normalize_matrix_determinant",
]
