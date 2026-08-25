#!/usr/bin/env python3
"""Capture deterministic numerical and timing baselines for the public core.

The probe intentionally supports both the legacy ``python/src`` layout and the
refactored ``src`` layout so that the exact same program can be run before and
after a structural refactor.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from time import perf_counter_ns
from typing import Callable

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
for source_root in (REPOSITORY_ROOT / "src", REPOSITORY_ROOT / "python" / "src"):
    if source_root.is_dir():
        sys.path.insert(0, str(source_root))
        break

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from circular_center.center2d import (  # noqa: E402
    fit_quasi_ransac,
    get_ellipse_polynomial_coeff,
    refine_projected_center,
)
from circular_center.center3d import fit_cga_circle, fit_circle_ransac  # noqa: E402

INTRINSIC = np.array(
    [[600.0, 0.0, 640.0], [0.0, 600.0, 480.0], [0.0, 0.0, 1.0]],
    dtype=float,
)


def circle_basis(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    normal = np.asarray(normal, dtype=float)
    normal /= np.linalg.norm(normal)
    reference = np.eye(3)[int(np.argmin(np.abs(normal)))]
    basis_u = np.cross(normal, reference)
    basis_u /= np.linalg.norm(basis_u)
    return basis_u, np.cross(normal, basis_u)


def project(
    points: np.ndarray,
    rotation: np.ndarray,
    translation: np.ndarray,
) -> np.ndarray:
    camera = (rotation @ points.T).T + np.asarray(translation).reshape(1, 3)
    homogeneous = (INTRINSIC @ camera.T).T
    return homogeneous[:, :2] / homogeneous[:, 2, None]


def benchmark(function: Callable[[], object], repetitions: int) -> dict[str, float | int]:
    for _ in range(3):
        function()
    elapsed_ms = np.empty(repetitions, dtype=float)
    for index in range(repetitions):
        start = perf_counter_ns()
        function()
        elapsed_ms[index] = (perf_counter_ns() - start) / 1_000_000.0
    return {
        "repetitions": repetitions,
        "median_ms": float(np.median(elapsed_ms)),
        "p95_ms": float(np.percentile(elapsed_ms, 95.0)),
        "minimum_ms": float(np.min(elapsed_ms)),
    }


def make_3d_fixtures() -> dict[str, object]:
    generator = np.random.default_rng(2025)
    center = np.array([0.4, -0.3, 1.2])
    radius = 0.12
    normal = np.array([0.3, -0.4, 0.8660254])
    normal /= np.linalg.norm(normal)
    basis_u, basis_v = circle_basis(normal)
    angles = 0.23 + np.linspace(0.0, np.pi, 64, endpoint=False)
    inliers = center + radius * (
        np.cos(angles)[:, None] * basis_u
        + np.sin(angles)[:, None] * basis_v
    )
    inliers += generator.normal(0.0, 0.0006, size=inliers.shape)
    outliers = center + generator.uniform(-0.25, 0.25, size=(16, 3))
    return {
        "center": center,
        "radius": radius,
        "normal": normal,
        "inliers": inliers,
        "contaminated": np.vstack((inliers, outliers)),
    }


def make_2d_fixture() -> dict[str, np.ndarray | float]:
    generator = np.random.default_rng(2025)
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
    contour = project(circle, np.eye(3), np.zeros(3))
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
    return {
        "ellipse": ellipse,
        "polynomial": get_ellipse_polynomial_coeff(ellipse_cv),
        "true_center": project(center[None, :], np.eye(3), np.zeros(3))[0],
        "diameter": 2.0 * radius,
    }


def make_quasi_ransac_fixture() -> dict[str, np.ndarray]:
    generator = np.random.default_rng(311)
    points = generator.uniform([-0.9, -0.7, -0.5], [0.9, 0.7, 0.8], size=(12, 3))
    rotation_vector = np.array([0.055, -0.032, 0.041])
    rotation = cv2.Rodrigues(rotation_vector)[0]
    translation = np.array([0.15, -0.08, 4.0])
    correct = project(points, rotation, translation)
    correct += generator.normal(0.0, 0.3, size=correct.shape)
    direction = generator.normal(size=correct.shape)
    direction /= np.linalg.norm(direction, axis=1, keepdims=True)
    alternative = correct + direction * generator.uniform(35.0, 70.0, size=(len(points), 1))
    swap = generator.integers(0, 2, size=len(points)).astype(bool)
    return {
        "points": points,
        "first": np.where(swap[:, None], alternative, correct),
        "second": np.where(swap[:, None], correct, alternative),
        "rotation": rotation,
        "translation": translation,
    }


def capture(repetition_scale: float) -> dict[str, object]:
    fixture_3d = make_3d_fixtures()
    fixture_2d = make_2d_fixture()
    fixture_pose = make_quasi_ransac_fixture()

    def run_cga():
        return fit_cga_circle(fixture_3d["inliers"])

    def run_cga_ransac():
        return fit_circle_ransac(
            fixture_3d["contaminated"],
            residual_threshold=0.004,
            minimum_inliers=56,
            confidence=0.99,
            seed=2025,
        )

    def run_refined_center():
        return refine_projected_center(
            fixture_2d["ellipse"],
            fixture_2d["polynomial"],
            INTRINSIC,
            marker_diameter=fixture_2d["diameter"],
            input_is_rectified=True,
        )

    def run_quasi_ransac():
        return fit_quasi_ransac(
            fixture_pose["points"],
            fixture_pose["first"],
            fixture_pose["second"],
            INTRINSIC,
            confidence=0.999,
            inlier_threshold=3.0,
            seed=2025,
        )

    cga = run_cga()
    robust = run_cga_ransac()
    refined = run_refined_center()
    quasi = run_quasi_ransac()

    relative_rotation = quasi.rotation @ fixture_pose["rotation"].T
    rotation_error = np.arccos(
        np.clip((np.trace(relative_rotation) - 1.0) / 2.0, -1.0, 1.0)
    )

    repetitions = {
        "CGA": max(5, int(round(300 * repetition_scale))),
        "CGA-RANSAC": max(3, int(round(80 * repetition_scale))),
        "Refined Center": max(3, int(round(80 * repetition_scale))),
        "Quasi-RANSAC": max(3, int(round(30 * repetition_scale))),
    }
    return {
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "opencv": cv2.__version__,
        },
        "numeric": {
            "CGA": {
                "center": cga.center.tolist(),
                "radius": cga.radius,
                "normal": cga.normal.tolist(),
                "center_error_m": float(np.linalg.norm(cga.center - fixture_3d["center"])),
                "radius_error_m": float(abs(cga.radius - fixture_3d["radius"])),
                "rmse_m": cga.rmse,
                "condition_number": cga.condition_number,
            },
            "CGA-RANSAC": {
                "center": robust.center.tolist(),
                "radius": robust.radius,
                "normal": robust.normal.tolist(),
                "center_error_m": float(
                    np.linalg.norm(robust.center - fixture_3d["center"])
                ),
                "radius_error_m": float(abs(robust.radius - fixture_3d["radius"])),
                "inlier_count": int(np.count_nonzero(robust.inlier_mask)),
                "iterations": robust.iterations,
                "inlier_rmse_m": robust.inlier_rmse,
            },
            "Refined Center": {
                "candidates": refined.candidates.tolist(),
                "scores": refined.scores.tolist(),
                "status": refined.status.value,
                "evaluations": refined.evaluations,
                "candidate_error_px": float(
                    np.min(
                        np.linalg.norm(
                            refined.candidates - fixture_2d["true_center"], axis=1
                        )
                    )
                ),
            },
            "Quasi-RANSAC": {
                "rotation": quasi.rotation.tolist(),
                "translation": quasi.translation.reshape(3).tolist(),
                "rotation_error_deg": float(np.rad2deg(rotation_error)),
                "translation_error_m": float(
                    np.linalg.norm(
                        quasi.translation.reshape(3) - fixture_pose["translation"]
                    )
                ),
                "mean_reprojection_error_px": quasi.mean_reprojection_error,
                "inlier_count": int(np.count_nonzero(quasi.inlier_mask)),
                "iterations": quasi.iterations,
            },
        },
        "timing": {
            "CGA": benchmark(run_cga, repetitions["CGA"]),
            "CGA-RANSAC": benchmark(run_cga_ransac, repetitions["CGA-RANSAC"]),
            "Refined Center": benchmark(
                run_refined_center, repetitions["Refined Center"]
            ),
            "Quasi-RANSAC": benchmark(run_quasi_ransac, repetitions["Quasi-RANSAC"]),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--repetition-scale",
        type=float,
        default=1.0,
        help="Scale timing repetitions while retaining at least three samples.",
    )
    arguments = parser.parse_args()
    if arguments.repetition_scale <= 0.0:
        parser.error("--repetition-scale must be positive")
    result = capture(arguments.repetition_scale)
    serialized = json.dumps(result, indent=2, sort_keys=True)
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
