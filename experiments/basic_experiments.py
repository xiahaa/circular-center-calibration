# SPDX-License-Identifier: Apache-2.0
"""Small deterministic validation of the public circular-center methods."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from circular_center.center2d import (  # noqa: E402
    QuasiRansacError,
    fit_quasi_ransac,
    get_ellipse_polynomial_coeff,
    refine_projected_center,
)
from circular_center.center3d import (  # noqa: E402
    CircleFitError,
    fit_cga_circle,
    fit_circle_ransac,
)

INTRINSIC = np.array(
    [[600.0, 0.0, 640.0], [0.0, 600.0, 480.0], [0.0, 0.0, 1.0]]
)


def circle_basis(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    normal = np.asarray(normal, dtype=float)
    normal /= np.linalg.norm(normal)
    reference = np.array([1.0, 0.0, 0.0])
    if abs(float(normal @ reference)) > 0.9:
        reference = np.array([0.0, 1.0, 0.0])
    basis_u = np.cross(normal, reference)
    basis_u /= np.linalg.norm(basis_u)
    return basis_u, np.cross(normal, basis_u)


def project(points: np.ndarray, rotation: np.ndarray, translation: np.ndarray) -> np.ndarray:
    camera = (rotation @ points.T).T + translation.reshape(1, 3)
    pixels = (INTRINSIC @ camera.T).T
    return pixels[:, :2] / pixels[:, 2, None]


def percentile_summary(values: list[float]) -> dict:
    array = np.asarray(values, dtype=float)
    if array.size == 0:
        return {"count": 0, "mean": None, "median": None, "p95": None}
    return {
        "count": int(array.size),
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "p95": float(np.percentile(array, 95.0)),
    }


def run_3d_trial(generator: np.random.Generator, trial_seed: int):
    center = generator.uniform([-0.5, -0.5, 1.0], [0.5, 0.5, 2.0])
    radius = 0.12
    normal = generator.normal(size=3)
    normal /= np.linalg.norm(normal)
    basis_u, basis_v = circle_basis(normal)
    start = generator.uniform(0.0, 2.0 * np.pi)
    angles = start + np.linspace(0.0, np.pi, 64, endpoint=False)
    inliers = center + radius * (
        np.cos(angles)[:, None] * basis_u
        + np.sin(angles)[:, None] * basis_v
    )
    inliers += generator.normal(0.0, 0.0006, size=inliers.shape)
    outliers = center + generator.uniform(-0.25, 0.25, size=(16, 3))

    clean = fit_cga_circle(inliers)
    contaminated = np.vstack((inliers, outliers))
    direct = fit_cga_circle(contaminated)
    robust = fit_circle_ransac(
        contaminated,
        residual_threshold=0.004,
        minimum_inliers=56,
        confidence=0.99,
        seed=trial_seed,
    )
    return (
        np.linalg.norm(clean.center - center),
        np.linalg.norm(direct.center - center),
        np.linalg.norm(robust.center - center),
    )


def run_2d_trial(generator: np.random.Generator):
    center = np.array(
        [generator.uniform(-0.3, 0.3), generator.uniform(-0.2, 0.2), generator.uniform(2.5, 4.0)]
    )
    tilt = generator.uniform(np.deg2rad(20.0), np.deg2rad(70.0))
    azimuth = generator.uniform(0.0, 2.0 * np.pi)
    normal = np.array(
        [np.sin(tilt) * np.cos(azimuth), np.sin(tilt) * np.sin(azimuth), np.cos(tilt)]
    )
    basis_u, basis_v = circle_basis(normal)
    angles = np.linspace(0.0, 2.0 * np.pi, 200, endpoint=False)
    circle = center + 0.12 * (
        np.cos(angles)[:, None] * basis_u
        + np.sin(angles)[:, None] * basis_v
    )
    contour = project(circle, np.eye(3), np.zeros(3))
    contour += generator.normal(0.0, 0.5, size=contour.shape)
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
    result = refine_projected_center(
        ellipse,
        get_ellipse_polynomial_coeff(ellipse_cv),
        INTRINSIC,
        marker_diameter=0.24,
        input_is_rectified=True,
    )
    true_center = project(center[None, :], np.eye(3), np.zeros(3))[0]
    ellipse_error = np.linalg.norm(np.asarray(ellipse_cv[0]) - true_center)
    proposed_error = np.min(np.linalg.norm(result.candidates - true_center, axis=1))
    return ellipse_error, proposed_error


def run_pose_trial(generator: np.random.Generator, trial_seed: int):
    points = generator.uniform([-0.9, -0.7, -0.5], [0.9, 0.7, 0.8], size=(12, 3))
    rotation_vector = generator.normal(0.0, 0.08, size=3)
    rotation = cv2.Rodrigues(rotation_vector)[0]
    translation = np.array([0.15, -0.08, 4.0])
    correct = project(points, rotation, translation)
    correct += generator.normal(0.0, 0.3, size=correct.shape)
    direction = generator.normal(size=correct.shape)
    direction /= np.linalg.norm(direction, axis=1, keepdims=True)
    alternative = correct + direction * generator.uniform(35.0, 70.0, size=(len(points), 1))
    swap = generator.integers(0, 2, size=len(points)).astype(bool)
    first = np.where(swap[:, None], alternative, correct)
    second = np.where(swap[:, None], correct, alternative)

    result = fit_quasi_ransac(
        points,
        first,
        second,
        INTRINSIC,
        confidence=0.999,
        inlier_threshold=3.0,
        seed=trial_seed,
    )
    relative = result.rotation @ rotation.T
    rotation_error = np.arccos(np.clip((np.trace(relative) - 1.0) / 2.0, -1.0, 1.0))
    translation_error = np.linalg.norm(result.translation.reshape(3) - translation)
    return np.rad2deg(rotation_error), translation_error


def run(trials: int, seed: int) -> dict:
    generator = np.random.default_rng(seed)
    measurements: dict[str, list[float]] = {
        "cga_clean_center_error_m": [],
        "cga_outlier_center_error_m": [],
        "cga_ransac_center_error_m": [],
        "ellipse_center_error_px": [],
        "proposed_candidate_error_px": [],
        "quasi_ransac_rotation_error_deg": [],
        "quasi_ransac_translation_error_m": [],
    }
    failures = {"3d": 0, "2d": 0, "quasi_ransac": 0}
    for index in range(trials):
        trial_seed = seed + index
        try:
            clean_error, direct_error, robust_error = run_3d_trial(generator, trial_seed)
            measurements["cga_clean_center_error_m"].append(float(clean_error))
            measurements["cga_outlier_center_error_m"].append(float(direct_error))
            measurements["cga_ransac_center_error_m"].append(float(robust_error))
        except CircleFitError:
            failures["3d"] += 1
        try:
            ellipse_error, proposed_error = run_2d_trial(generator)
            measurements["ellipse_center_error_px"].append(float(ellipse_error))
            measurements["proposed_candidate_error_px"].append(float(proposed_error))
        except (ValueError, FloatingPointError, cv2.error):
            failures["2d"] += 1
        try:
            rotation_error, translation_error = run_pose_trial(generator, trial_seed)
            measurements["quasi_ransac_rotation_error_deg"].append(float(rotation_error))
            measurements["quasi_ransac_translation_error_m"].append(float(translation_error))
        except (QuasiRansacError, ValueError, cv2.error):
            failures["quasi_ransac"] += 1

    return {
        "configuration": {"trials": trials, "seed": seed},
        "failures": failures,
        "metrics": {name: percentile_summary(values) for name, values in measurements.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--seed", type=int, default=2025)
    parser.add_argument("--output", type=Path, default=Path("outputs/basic_results.json"))
    arguments = parser.parse_args()
    if arguments.trials <= 0:
        parser.error("--trials must be positive")

    summary = run(arguments.trials, arguments.seed)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"wrote {arguments.output}")


if __name__ == "__main__":
    main()
