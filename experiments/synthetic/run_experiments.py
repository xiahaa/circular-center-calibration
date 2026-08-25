#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run deterministic paper-style synthetic circular-center experiments."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
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
    if distribution == "limited_nonuniform":
        return np.square(generator.uniform(0.0, 1.0, count)) * span - 0.2 * span
    if distribution == "sparse_clusters":
        cluster_count = min(3, count // 4)
        if cluster_count == 0:
            raise ValueError("the legacy sparse distribution requires at least four points")
        angles = []
        for cluster in range(cluster_count):
            center = generator.uniform(0.0, 2.0 * np.pi)
            width = generator.uniform(np.pi / 30.0, np.pi / 9.0)
            points_in_cluster = count // cluster_count
            if cluster == cluster_count - 1:
                points_in_cluster = count - len(angles)
            angles.extend(generator.normal(center, width, points_in_cluster))
        return np.asarray(angles)
    if distribution == "symmetric_nonuniform":
        if count <= 1:
            return np.zeros(count)
        half = count // 2
        intervals = generator.uniform(0.8, 1.2, half)
        intervals *= (0.5 * span) / np.sum(intervals)
        cumulative = np.concatenate(([0.0], np.cumsum(intervals)))
        values = np.concatenate((-cumulative[::-1], cumulative[1:]))
        return values[:count]
    return generator.uniform(0.0, span, count)


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


def _configuration(
    sweep,
    setting,
    count,
    span,
    noise,
    outlier_ratio,
    distribution,
    generator_kind,
    default_trials,
    pcl_threshold,
):
    return {
        "sweep": sweep,
        "setting": setting,
        "count": count,
        "span": span,
        "noise": noise,
        "outlier_ratio": outlier_ratio,
        "distribution": distribution,
        "generator_kind": generator_kind,
        "default_trials": default_trials,
        "pcl_threshold": pcl_threshold,
    }


def _three_dimensional_configurations(profile):
    if profile == "smoke":
        return [
            _configuration(
                "noise_sigma_m", 0.01, 50, None, 0.01, 0.0, None,
                "legacy_random_span", 1, 0.01,
            ),
            _configuration(
                "visible_arc_degrees", 180.0, 50, 180.0, 0.1, 0.0, None,
                "legacy_grid", 1, 0.1,
            ),
            _configuration(
                "outlier_ratio", 0.3, 50, 360.0, 0.1, 0.3, None,
                "legacy_grid", 1, 0.1,
            ),
            _configuration(
                "legacy_scenario", "limited_arc", 100, 70.0, 0.2, 0.0,
                "limited_nonuniform", "legacy_stress", 1, 0.1,
            ),
        ]
    configurations = []
    for noise in (1e-4, 1e-3, 1e-2, 1e-1, 1.0):
        configurations.append(
            _configuration(
                "noise_sigma_m", noise, 50, None, noise, 0.0, None,
                "legacy_random_span", 500, noise,
            )
        )
    for span in (90.0, 135.0, 180.0, 225.0, 270.0, 315.0, 360.0):
        configurations.append(
            _configuration(
                "visible_arc_degrees", span, 50, span, 0.1, 0.0, None,
                "legacy_grid", 500, 0.1,
            )
        )
    for ratio in (0.1, 0.2, 0.3, 0.4, 0.5):
        configurations.append(
            _configuration(
                "outlier_ratio", ratio, 50, 360.0, 0.1, ratio, None,
                "legacy_grid", 100, 0.1,
            )
        )
    configurations.extend(
        [
            _configuration(
                "legacy_scenario", "isotropic_noise", 100, 360.0, 0.2, 0.0,
                "uniform", "legacy_stress", 1000, 0.1,
            ),
            _configuration(
                "legacy_scenario", "limited_arc", 100, 70.0, 0.2, 0.0,
                "limited_nonuniform", "legacy_stress", 1000, 0.1,
            ),
            _configuration(
                "legacy_scenario", "sparse_points", 12, 360.0, 0.2, 0.0,
                "sparse_clusters", "legacy_stress", 1000, 0.1,
            ),
            _configuration(
                "legacy_scenario", "symmetric_distribution", 20, 200.0, 0.2, 0.0,
                "symmetric_nonuniform", "legacy_stress", 1000, 0.1,
            ),
        ]
    )
    return configurations


def _generate_three_dimensional_sample(generator, configuration):
    count = configuration["count"]
    noise = configuration["noise"]
    if configuration["generator_kind"] in ("legacy_random_span", "legacy_grid"):
        radius = float(generator.uniform(2.0, 5.0))
        if configuration["generator_kind"] == "legacy_random_span":
            span = float(generator.uniform(90.0, 360.0))
        else:
            span = configuration["span"]
        angles = np.linspace(0.0, np.deg2rad(span), count)
        local_points = np.column_stack(
            (radius * np.cos(angles), radius * np.sin(angles), np.zeros(count))
        )
        rotation = cv2.Rodrigues(generator.normal(size=3))[0]
        center = generator.uniform(0.0, 5.0, 3)
        normal = rotation[:, 2]
        points = (rotation @ local_points.T).T + center
        points += generator.normal(0.0, noise, points.shape)
    else:
        center = generator.uniform(-2.0, 2.0, 3)
        radius = float(generator.uniform(1.0, 5.0))
        normal = generator.normal(size=3)
        normal /= np.linalg.norm(normal)
        point_seed = int(generator.integers(0, np.iinfo(np.uint32).max, dtype=np.uint32))
        point_generator = np.random.default_rng(point_seed)
        points = _generate_circle_points(
            point_generator,
            center,
            radius,
            normal,
            count,
            configuration["span"],
            noise,
            configuration["distribution"],
        )

    outlier_count = int(configuration["outlier_ratio"] * count)
    if outlier_count:
        # The legacy source declares `int Perturb = 0.01`, so the effective
        # perturbation is zero and the outlier coordinates are integers in [10, 20].
        outliers = generator.integers(10, 21, size=(outlier_count, 3)).astype(float)
        points = np.vstack((points, outliers))
    return center, radius, normal, points


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


def _run_pcl_batch(samples, executable):
    executable = Path(executable).resolve()
    if not executable.is_file():
        raise FileNotFoundError(f"PCL executable does not exist: {executable}")

    with tempfile.TemporaryDirectory(prefix="circular-center-pcl-") as directory:
        input_path = Path(directory) / "points.csv"
        output_path = Path(directory) / "fits.csv"
        with input_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(("sample_id", "distance_threshold", "x", "y", "z"))
            for sample in samples:
                for point in sample["points"]:
                    writer.writerow(
                        (sample["id"], sample["pcl_threshold"], point[0], point[1], point[2])
                    )

        completed = subprocess.run(
            (str(executable), str(input_path), str(output_path)),
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"PCL batch fitting failed: {message}")

        with output_path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))

    results = {}
    for row in rows:
        sample_id = int(row["sample_id"])
        if sample_id in results:
            raise RuntimeError(f"duplicate PCL result for sample {sample_id}")
        results[sample_id] = row
    return results


def _append_pcl_records(records, samples, executable):
    results = _run_pcl_batch(samples, executable)
    for sample in samples:
        record = _base_record(*sample["metadata"], "pcl_ransac")
        row = results.get(sample["id"])
        if row is None:
            records.append(record)
            continue
        record["elapsed_seconds"] = float(row["elapsed_seconds"])
        values = np.array(
            [
                float(row["center_x"]),
                float(row["center_y"]),
                float(row["center_z"]),
                float(row["radius"]),
                float(row["normal_x"]),
                float(row["normal_y"]),
                float(row["normal_z"]),
            ]
        )
        normal_norm = np.linalg.norm(values[4:])
        if row["success"] == "1" and np.all(np.isfinite(values)) and normal_norm > 0.0:
            record.update(
                success=True,
                center_error_m=float(np.linalg.norm(values[:3] - sample["center"])),
                radius_error_m=float(abs(values[3] - sample["radius"])),
                normal_error_deg=_unoriented_normal_error(
                    values[4:] / normal_norm,
                    sample["normal"],
                ),
            )
        records.append(record)


def run_three_dimensional_study(trials, seed, profile, pcl_executable=None):
    records = []
    pcl_samples = []
    sample_id = 0
    for configuration_index, configuration in enumerate(_three_dimensional_configurations(profile)):
        attempts = trials if trials is not None else configuration["default_trials"]
        for trial in range(attempts):
            trial_seed = seed + 100_000 * configuration_index + trial
            generator = np.random.default_rng(trial_seed)
            center, radius, normal, points = _generate_three_dimensional_sample(
                generator,
                configuration,
            )
            metadata = (
                "3d_circle",
                configuration["sweep"],
                configuration["setting"],
                trial,
            )
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
                    configuration["noise"],
                )
            if pcl_executable is not None:
                pcl_samples.append(
                    {
                        "id": sample_id,
                        "metadata": metadata,
                        "points": points,
                        "center": center,
                        "radius": radius,
                        "normal": normal,
                        "pcl_threshold": configuration["pcl_threshold"],
                    }
                )
                sample_id += 1
    if pcl_executable is not None:
        _append_pcl_records(records, pcl_samples, pcl_executable)
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
    parser.add_argument(
        "--trials",
        type=int,
        default=None,
        help="override trials per configuration; omit to use legacy paper counts",
    )
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
    parser.add_argument(
        "--pcl-executable",
        type=Path,
        help="optional circular_center_pcl_batch executable for the PCL RANSAC baseline",
    )
    arguments = parser.parse_args()
    if arguments.trials is not None and arguments.trials <= 0:
        parser.error("--trials must be positive")

    records = []
    if "3d" in arguments.studies:
        records.extend(
            run_three_dimensional_study(
                arguments.trials,
                arguments.seed,
                arguments.profile,
                arguments.pcl_executable,
            )
        )
    non_legacy_trials = 100 if arguments.trials is None else arguments.trials
    if "2d" in arguments.studies:
        records.extend(run_two_dimensional_study(non_legacy_trials, arguments.seed, arguments.profile))
    if "pose" in arguments.studies:
        records.extend(run_pose_study(non_legacy_trials, arguments.seed, arguments.profile))

    arguments.output_directory.mkdir(parents=True, exist_ok=True)
    raw_path = arguments.output_directory / "raw_results.csv"
    summary_path = arguments.output_directory / "summary.json"
    configuration = {
        "profile": arguments.profile,
        "trials_per_configuration": arguments.trials,
        "seed": arguments.seed,
        "studies": list(arguments.studies),
        "intrinsic_matrix": INTRINSIC.tolist(),
        "pcl_executable": (
            str(arguments.pcl_executable.resolve())
            if arguments.pcl_executable is not None
            else None
        ),
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
