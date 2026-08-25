# SPDX-License-Identifier: Apache-2.0
"""Minimal end-to-end examples for the public algorithms."""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from circular_center.center2d import (  # noqa: E402
    get_ellipse_polynomial_coeff,
    refine_projected_center,
)
from circular_center.center3d import fit_circle_ransac  # noqa: E402


def circle_basis(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return an orthonormal basis of the plane perpendicular to ``normal``."""
    normal = np.asarray(normal, dtype=float)
    normal /= np.linalg.norm(normal)
    reference = np.array([1.0, 0.0, 0.0])
    if abs(float(normal @ reference)) > 0.9:
        reference = np.array([0.0, 1.0, 0.0])
    basis_u = np.cross(normal, reference)
    basis_u /= np.linalg.norm(basis_u)
    return basis_u, np.cross(normal, basis_u)


def project(points: np.ndarray, intrinsic: np.ndarray) -> np.ndarray:
    homogeneous = (intrinsic @ points.T).T
    return homogeneous[:, :2] / homogeneous[:, 2, None]


def demonstrate_3d() -> None:
    generator = np.random.default_rng(2025)
    center = np.array([0.4, -0.3, 1.2])
    radius = 0.12
    normal = np.array([0.3, -0.4, 0.8660254])
    basis_u, basis_v = circle_basis(normal)
    angles = np.linspace(0.0, np.pi, 64, endpoint=False)
    inliers = center + radius * (
        np.cos(angles)[:, None] * basis_u
        + np.sin(angles)[:, None] * basis_v
    )
    inliers += generator.normal(0.0, 0.0006, size=inliers.shape)
    outliers = center + generator.uniform(-0.25, 0.25, size=(16, 3))
    points = np.vstack((inliers, outliers))

    result = fit_circle_ransac(
        points,
        residual_threshold=0.004,
        minimum_inliers=56,
        confidence=0.99,
        seed=2025,
    )
    print("3D CGA-RANSAC")
    print(f"  center error: {np.linalg.norm(result.center - center):.6f} m")
    print(f"  radius error: {abs(result.radius - radius):.6f} m")
    print(f"  inliers: {np.count_nonzero(result.inlier_mask)}/{len(points)}")


def demonstrate_2d() -> None:
    generator = np.random.default_rng(2025)
    intrinsic = np.array(
        [[600.0, 0.0, 640.0], [0.0, 600.0, 480.0], [0.0, 0.0, 1.0]]
    )
    center = np.array([0.15, -0.08, 3.0])
    radius = 0.12
    normal = np.array([1.0, 0.0, 1.0])
    normal /= np.linalg.norm(normal)
    basis_u, basis_v = circle_basis(normal)
    angles = np.linspace(0.0, 2.0 * np.pi, 200, endpoint=False)
    circle = center + radius * (
        np.cos(angles)[:, None] * basis_u
        + np.sin(angles)[:, None] * basis_v
    )
    contour = project(circle, intrinsic)
    contour += generator.normal(0.0, 0.25, size=contour.shape)

    ellipse_cv = cv2.fitEllipse(contour.astype(np.float32).reshape(-1, 1, 2))
    ellipse = np.array(
        [
            ellipse_cv[0][0],
            ellipse_cv[0][1],
            ellipse_cv[1][0] / 2.0,
            ellipse_cv[1][1] / 2.0,
            np.deg2rad(ellipse_cv[2]),
        ]
    )
    polynomial = get_ellipse_polynomial_coeff(ellipse_cv)
    result = refine_projected_center(
        ellipse,
        polynomial,
        intrinsic,
        marker_diameter=2.0 * radius,
        input_is_rectified=True,
    )
    true_center = project(center[None, :], intrinsic)[0]
    ellipse_error = np.linalg.norm(np.asarray(ellipse_cv[0]) - true_center)
    candidate_error = np.min(np.linalg.norm(result.candidates - true_center, axis=1))

    print("2D projected center")
    print(f"  fitted ellipse-center error: {ellipse_error:.4f} px")
    print(f"  best proposed-candidate error: {candidate_error:.4f} px")
    print(f"  candidates: {np.array2string(result.candidates, precision=3)}")


if __name__ == "__main__":
    demonstrate_3d()
    demonstrate_2d()
