#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run deterministic paper-style synthetic circular-center experiments."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from time import perf_counter

import cv2
import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "python" / "src"))

from circular_center.center2d import (  # noqa: E402
    ProjectedCenterError,
    QuasiRansacError,
    fit_quasi_ransac,
    get_ellipse_polynomial_coeff,
    refine_projected_center,
    select_projected_center_by_homography,
)
from circular_center.center3d import (  # noqa: E402
    CircleFitError,
    fit_cga_circle,
    fit_circle_ransac,
)


INTRINSIC = np.array(
    [[600.0, 0.0, 640.0], [0.0, 600.0, 480.0], [0.0, 0.0, 1.0]],
    dtype=float,
)
RECORD_FIELDS = (
    "study",
    "sweep",
    "setting",
    "trial",
    "method",
    "success",
    "center_error_m",
    "radius_error_m",
    "normal_error_deg",
    "pixel_error",
    "candidate_separation_px",
    "reprojection_rmse_px",
    "rotation_error_deg",
    "translation_error_m",
    "elapsed_seconds",
)
METRIC_FIELDS = RECORD_FIELDS[6:]


def _circle_basis(normal: np.ndarray):
    normal = np.asarray(normal, dtype=float)
    normal /= np.linalg.norm(normal)
    reference = np.eye(3)[int(np.argmin(np.abs(normal)))]
    basis_u = np.cross(normal, reference)
    basis_u /= np.linalg.norm(basis_u)
    return basis_u, np.cross(normal, basis_u)


def _project(points: np.ndarray, rotation=None, translation=None):
    points = np.asarray(points, dtype=float)
    rotation = np.eye(3) if rotation is None else np.asarray(rotation, dtype=float)
    translation = np.zeros(3) if translation is None else np.asarray(translation, dtype=float)
    camera = (rotation @ points.T).T + translation.reshape(1, 3)
    if np.any(camera[:, 2] <= 0.0):
        raise ValueError("a generated point is behind the camera")
    homogeneous = (INTRINSIC @ camera.T).T
    return homogeneous[:, :2] / homogeneous[:, 2, None]


def _unoriented_normal_error(actual: np.ndarray, expected: np.ndarray):
    cosine = abs(float(np.asarray(actual) @ np.asarray(expected)))
    return float(np.rad2deg(np.arccos(np.clip(cosine, -1.0, 1.0))))


def _rotation_error(actual: np.ndarray, expected: np.ndarray):
    relative = np.asarray(actual) @ np.asarray(expected).T
    cosine = (np.trace(relative) - 1.0) * 0.5
    return float(np.rad2deg(np.arccos(np.clip(cosine, -1.0, 1.0))))


def _base_record(study, sweep, setting, trial, method):
    return {
        "study": study,
        "sweep": sweep,
        "setting": setting,
        "trial": trial,
        "method": method,
        "success": False,
        **{field: None for field in METRIC_FIELDS},
    }


def _angles(generator, count, span_degrees, distribution):
    span = np.deg2rad(span_degrees)
    start = generator.uniform(0.0, 2.0 * np.pi)
    if distribution == "limited_nonuniform":
        return start + np.square(generator.uniform(0.0, 1.0, count)) * span - 0.2 * span
    if distribution == "sparse_clusters":
        cluster_count = min(3, max(1, count // 4))
        cluster_centers = generator.uniform(0.0, 2.0 * np.pi, cluster_count)
        cluster_ids = np.arange(count) % cluster_count
        generator.shuffle(cluster_ids)
        return start + cluster_centers[cluster_ids] + generator.normal(0.0, 0.08, count)
    if distribution == "symmetric_nonuniform":
        half = count // 2
        positive = np.sort(generator.uniform(0.0, 0.5 * span, half))
        values = np.concatenate((-positive[::-1], positive))
        if count % 2:
            values = np.concatenate((values, [0.0]))
        return start + values[:count]
    return start + np.linspace(0.0, span, count, endpoint=False)


def _generate_circle_points(
    generator,
    center,
    radius,
    normal,
    count,
    span_degrees,
    noise_sigma,
    distribution="uniform",
):
    basis_u, basis_v = _circle_basis(normal)
    angles = _angles(generator, count, span_degrees, distribution)
    points = center + radius * (
        np.cos(angles)[:, None] * basis_u + np.sin(angles)[:, None] * basis_v
    )
    return points + generator.normal(0.0, noise_sigma, size=points.shape)


def _three_dimensional_configurations(profile):
    if profile == "smoke":
        return [
            ("noise_sigma_m", 0.01, 100, 360.0, 0.01, 0.0, "uniform"),
            ("visible_arc_degrees", 180.0, 100, 180.0, 0.1, 0.0, "uniform"),
            ("outlier_ratio", 0.3, 100, 360.0, 0.1, 0.3, "uniform"),
            ("legacy_scenario", "limited_arc", 100, 70.0, 0.2, 0.0, "limited_nonuniform"),
        ]
    configurations = []
    for noise in (1e-4, 1e-3, 1e-2, 1e-1, 1.0):
        configurations.append(("noise_sigma_m", noise, 100, 360.0, noise, 0.0, "uniform"))
    for span in (90.0, 135.0, 180.0, 225.0, 270.0, 315.0, 360.0):
        configurations.append(("visible_arc_degrees", span, 100, span, 0.1, 0.0, "uniform"))
    for ratio in (0.1, 0.2, 0.3, 0.4, 0.5):
        configurations.append(("outlier_ratio", ratio, 100, 360.0, 0.1, ratio, "uniform"))
    configurations.extend(
        [
            ("legacy_scenario", "isotropic_noise", 100, 360.0, 0.2, 0.0, "uniform"),
            ("legacy_scenario", "limited_arc", 100, 70.0, 0.2, 0.0, "limited_nonuniform"),
            ("legacy_scenario", "sparse_points", 12, 360.0, 0.2, 0.0, "sparse_clusters"),
            (
                "legacy_scenario",
                "symmetric_distribution",
                20,
                200.0,
                0.2,
                0.0,
                "symmetric_nonuniform",
            ),
        ]
    )
    return configurations


def _record_circle_fit(records, points, center, radius, normal, metadata, method, seed, noise):
    record = _base_record(*metadata, method)
    start = perf_counter()
    try:
        if method == "cga":
            result = fit_cga_circle(points)
        else:
            result = fit_circle_ransac(
                points,
                residual_threshold=max(3.0 * noise, 0.01),
                max_iterations=500,
                sample_size=5,
                minimum_inliers=max(5, min(50, int(0.5 * len(points)))),
                confidence=0.99,
                seed=seed,
            )
        record.update(
            success=True,
            center_error_m=float(np.linalg.norm(result.center - center)),
            radius_error_m=float(abs(result.radius - radius)),
            normal_error_deg=_unoriented_normal_error(result.normal, normal),
            elapsed_seconds=float(result.elapsed_seconds),
        )
    except (CircleFitError, ValueError, np.linalg.LinAlgError, FloatingPointError):
        record["elapsed_seconds"] = float(perf_counter() - start)
    records.append(record)


def run_three_dimensional_study(trials, seed, profile):
    records = []
    for configuration_index, configuration in enumerate(_three_dimensional_configurations(profile)):
        sweep, setting, count, span, noise, outlier_ratio, distribution = configuration
        for trial in range(trials):
            trial_seed = seed + 100_000 * configuration_index + trial
            generator = np.random.default_rng(trial_seed)
            center = generator.uniform(-2.0, 2.0, 3)
            radius = float(generator.uniform(1.0, 5.0))
            normal = generator.normal(size=3)
            normal /= np.linalg.norm(normal)
            points = _generate_circle_points(
                generator,
                center,
                radius,
                normal,
                count,
                span,
                noise,
                distribution,
            )
            outlier_count = int(round(outlier_ratio * count))
            if outlier_count:
                outliers = center + generator.uniform(
                    -3.0 * radius,
                    3.0 * radius,
                    size=(outlier_count, 3),
                )
                points = np.vstack((points, outliers))
                generator.shuffle(points)
            metadata = ("3d_circle", sweep, setting, trial)
            for method in ("cga", "cga_ransac"):
                _record_circle_fit(
                    records,
                    points,
                    center,
                    radius,
                    normal,
                    metadata,
                    method,
                    trial_seed,
                    noise,
                )
    return records


def _circle_contour(center, radius, normal, generator, noise_sigma, count=200):
    basis_u, basis_v = _circle_basis(normal)
    angles = np.linspace(0.0, 2.0 * np.pi, count, endpoint=False)
    points = center + radius * (
        np.cos(angles)[:, None] * basis_u + np.sin(angles)[:, None] * basis_v
    )
    pixels = _project(points)
    return pixels + generator.normal(0.0, noise_sigma, pixels.shape)


def _ellipse_from_contour(contour):
    ellipse_cv = cv2.fitEllipse(np.asarray(contour, dtype=np.float32).reshape(-1, 1, 2))
    (center_x, center_y), (axis_a, axis_b), angle = ellipse_cv
    ellipse = np.array(
        [center_x, center_y, 0.5 * axis_a, 0.5 * axis_b, np.deg2rad(angle)],
        dtype=float,
    )
    return ellipse_cv, ellipse


def _two_dimensional_configurations(profile):
    if profile == "smoke":
        return [("contour_noise_px", 0.5, 55.0, 0.5), ("tilt_degrees", 55.0, 55.0, 0.5)]
    configurations = [
        ("contour_noise_px", noise, 55.0, noise) for noise in (0.0, 0.25, 0.5, 1.0, 2.0)
    ]
    configurations.extend(
        ("tilt_degrees", tilt, tilt, 0.5) for tilt in (10.0, 20.0, 35.0, 50.0, 65.0, 75.0)
    )
    return configurations


def run_two_dimensional_study(trials, seed, profile):
    records = []
    radius = 0.35
    alternative_radius = 0.25
    for configuration_index, (sweep, setting, tilt_degrees, noise) in enumerate(
        _two_dimensional_configurations(profile)
    ):
        for trial in range(trials):
            trial_seed = seed + 1_000_000 + 100_000 * configuration_index + trial
            generator = np.random.default_rng(trial_seed)
            center = np.array(
                [
                    generator.uniform(-0.5, 0.5),
                    generator.uniform(-0.3, 0.3),
                    generator.uniform(3.5, 5.0),
                ]
            )
            azimuth = generator.uniform(0.0, 2.0 * np.pi)
            tilt = np.deg2rad(tilt_degrees)
            normal = np.array(
                [np.sin(tilt) * np.cos(azimuth), np.sin(tilt) * np.sin(azimuth), np.cos(tilt)]
            )
            basis_u, _ = _circle_basis(normal)
            alternative_center = center + 1.8 * radius * basis_u
            contour = _circle_contour(center, radius, normal, generator, noise)
            alternative_contour = _circle_contour(
                alternative_center,
                alternative_radius,
                normal,
                generator,
                noise,
            )
            true_center = _project(center.reshape(1, 3))[0]
            metadata = ("2d_center", sweep, setting, trial)
            try:
                ellipse_cv, ellipse = _ellipse_from_contour(contour)
                polynomial = get_ellipse_polynomial_coeff(ellipse_cv)
                result = refine_projected_center(
                    ellipse,
                    polynomial,
                    INTRINSIC,
                    marker_diameter=2.0 * radius,
                    input_is_rectified=True,
                )
                separation = float(np.linalg.norm(result.candidates[0] - result.candidates[1]))
                candidate_errors = np.linalg.norm(result.candidates - true_center, axis=1)
                measurements = {
                    "ellipse_center": float(np.linalg.norm(ellipse[:2] - true_center)),
                    "candidate_oracle": float(np.min(candidate_errors)),
                }
                for method, error in measurements.items():
                    record = _base_record(*metadata, method)
                    record.update(
                        success=True,
                        pixel_error=error,
                        candidate_separation_px=separation,
                    )
                    if method == "candidate_oracle":
                        record["elapsed_seconds"] = float(result.elapsed_seconds)
                    records.append(record)
                try:
                    homography_start = perf_counter()
                    selected, _ = select_projected_center_by_homography(
                        ellipse,
                        polynomial,
                        contour.T,
                        alternative_contour.T,
                        INTRINSIC,
                        radius,
                        radius / alternative_radius,
                    )
                    record = _base_record(*metadata, "homography_selected")
                    record.update(
                        success=True,
                        pixel_error=float(np.linalg.norm(selected - true_center)),
                        candidate_separation_px=separation,
                        elapsed_seconds=float(perf_counter() - homography_start),
                    )
                    records.append(record)
                except (
                    ProjectedCenterError,
                    ValueError,
                    cv2.error,
                    np.linalg.LinAlgError,
                    FloatingPointError,
                ):
                    records.append(_base_record(*metadata, "homography_selected"))
            except (
                ProjectedCenterError,
                ValueError,
                cv2.error,
                np.linalg.LinAlgError,
                FloatingPointError,
            ):
                for method in ("ellipse_center", "candidate_oracle", "homography_selected"):
                    records.append(_base_record(*metadata, method))
    return records


def _pose_configurations(profile):
    values = (0.5,) if profile == "smoke" else (0.25, 0.5, 1.0, 2.0, 4.0)
    return [("image_noise_px", value) for value in values]


def _solve_pose(points, image_points):
    success, rotation_vector, translation = cv2.solvePnP(
        np.asarray(points, dtype=float),
        np.asarray(image_points, dtype=float),
        INTRINSIC,
        np.zeros(5),
        flags=cv2.SOLVEPNP_EPNP,
    )
    if not success:
        raise RuntimeError("OpenCV EPNP failed")
    success, rotation_vector, translation = cv2.solvePnP(
        np.asarray(points, dtype=float),
        np.asarray(image_points, dtype=float),
        INTRINSIC,
        np.zeros(5),
        rotation_vector,
        translation,
        True,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )
    if not success:
        raise RuntimeError("OpenCV iterative PnP refinement failed")
    return cv2.Rodrigues(rotation_vector)[0], translation.reshape(3)


def _append_pose_record(
    records,
    metadata,
    method,
    rotation,
    translation,
    expected_rotation,
    expected_translation,
    points,
    expected_pixels,
    elapsed,
):
    record = _base_record(*metadata, method)
    projected = _project(points, rotation, translation)
    record.update(
        success=True,
        reprojection_rmse_px=float(
            np.sqrt(np.mean(np.sum(np.square(projected - expected_pixels), axis=1)))
        ),
        rotation_error_deg=_rotation_error(rotation, expected_rotation),
        translation_error_m=float(np.linalg.norm(translation - expected_translation)),
        elapsed_seconds=float(elapsed),
    )
    records.append(record)


def run_pose_study(trials, seed, profile):
    records = []
    point_count = 20
    for configuration_index, (sweep, noise) in enumerate(_pose_configurations(profile)):
        for trial in range(trials):
            trial_seed = seed + 2_000_000 + 100_000 * configuration_index + trial
            generator = np.random.default_rng(trial_seed)
            points = generator.uniform([-0.9, -0.7, -0.5], [0.9, 0.7, 0.8], (point_count, 3))
            rotation_vector = generator.normal(0.0, 0.08, 3)
            expected_rotation = cv2.Rodrigues(rotation_vector)[0]
            expected_translation = np.array([0.15, -0.08, 4.0])
            expected_pixels = _project(points, expected_rotation, expected_translation)
            correct = expected_pixels + generator.normal(0.0, noise, expected_pixels.shape)
            directions = generator.normal(size=correct.shape)
            directions /= np.linalg.norm(directions, axis=1, keepdims=True)
            alternative = correct + directions * generator.uniform(35.0, 70.0, (point_count, 1))
            ellipse_centers = 0.5 * (correct + alternative)
            swap = generator.integers(0, 2, point_count).astype(bool)
            candidate_a = np.where(swap[:, None], alternative, correct)
            candidate_b = np.where(swap[:, None], correct, alternative)
            metadata = ("pose", sweep, noise, trial)

            for method, image_points in (
                ("oracle_pnp", correct),
                ("ellipse_center_pnp", ellipse_centers),
            ):
                start = perf_counter()
                try:
                    rotation, translation = _solve_pose(points, image_points)
                    _append_pose_record(
                        records,
                        metadata,
                        method,
                        rotation,
                        translation,
                        expected_rotation,
                        expected_translation,
                        points,
                        expected_pixels,
                        perf_counter() - start,
                    )
                except (RuntimeError, ValueError, cv2.error, np.linalg.LinAlgError):
                    record = _base_record(*metadata, method)
                    record["elapsed_seconds"] = float(perf_counter() - start)
                    records.append(record)

            start = perf_counter()
            try:
                result = fit_quasi_ransac(
                    points,
                    candidate_a,
                    candidate_b,
                    INTRINSIC,
                    confidence=0.999,
                    inlier_threshold=max(3.0, 3.0 * noise),
                    max_iterations=1000,
                    seed=trial_seed,
                )
                _append_pose_record(
                    records,
                    metadata,
                    "quasi_ransac",
                    result.rotation,
                    result.translation.reshape(3),
                    expected_rotation,
                    expected_translation,
                    points,
                    expected_pixels,
                    result.elapsed_seconds,
                )
            except (QuasiRansacError, ValueError, cv2.error, np.linalg.LinAlgError):
                record = _base_record(*metadata, "quasi_ransac")
                record["elapsed_seconds"] = float(perf_counter() - start)
                records.append(record)
    return records


def _percentiles(values):
    values = np.asarray(values, dtype=float)
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p95": float(np.percentile(values, 95.0)),
    }


def summarize(records, configuration):
    grouped = {}
    for record in records:
        key = (record["study"], record["sweep"], str(record["setting"]), record["method"])
        grouped.setdefault(key, []).append(record)
    groups = []
    for key in sorted(grouped):
        rows = grouped[key]
        successful = [row for row in rows if row["success"]]
        metrics = {}
        for field in METRIC_FIELDS:
            values = [row[field] for row in successful if row[field] is not None]
            if values:
                metrics[field] = _percentiles(values)
        groups.append(
            {
                "study": key[0],
                "sweep": key[1],
                "setting": rows[0]["setting"],
                "method": key[3],
                "attempts": len(rows),
                "successes": len(successful),
                "success_rate": len(successful) / float(len(rows)),
                "metrics": metrics,
            }
        )
    return {"configuration": configuration, "groups": groups}


def _write_records(path, records):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=RECORD_FIELDS)
        writer.writeheader()
        writer.writerows(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("smoke", "paper"), default="paper")
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--seed", type=int, default=2025)
    parser.add_argument(
        "--studies",
        nargs="+",
        choices=("3d", "2d", "pose"),
        default=("3d", "2d", "pose"),
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs/synthetic"),
    )
    arguments = parser.parse_args()
    if arguments.trials <= 0:
        parser.error("--trials must be positive")

    records = []
    if "3d" in arguments.studies:
        records.extend(
            run_three_dimensional_study(arguments.trials, arguments.seed, arguments.profile)
        )
    if "2d" in arguments.studies:
        records.extend(
            run_two_dimensional_study(arguments.trials, arguments.seed, arguments.profile)
        )
    if "pose" in arguments.studies:
        records.extend(run_pose_study(arguments.trials, arguments.seed, arguments.profile))

    arguments.output_directory.mkdir(parents=True, exist_ok=True)
    raw_path = arguments.output_directory / "raw_results.csv"
    summary_path = arguments.output_directory / "summary.json"
    configuration = {
        "profile": arguments.profile,
        "trials_per_configuration": arguments.trials,
        "seed": arguments.seed,
        "studies": list(arguments.studies),
        "intrinsic_matrix": INTRINSIC.tolist(),
    }
    _write_records(raw_path, records)
    summary_path.write_text(
        json.dumps(summarize(records, configuration), indent=2),
        encoding="utf-8",
    )
    print(f"wrote {len(records)} records to {raw_path}")
    print(f"wrote grouped statistics to {summary_path}")


if __name__ == "__main__":
    main()
