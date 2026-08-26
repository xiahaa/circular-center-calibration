"""Real-world qualitative measurement and calibration experiment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Mapping, Optional

import cv2
import numpy as np
import yaml

from circular_center.experiments import ExperimentContext
from circular_center.interfaces import AmbiguousCorrespondences, EllipseObservation

from .data_io import Dataset, FramePair, load_dataset, read_image, read_pcd
from .detection2d import DetectedTarget, detect_target_ellipse
from .evaluation import render_qualitative_frame
from .extraction3d import (
    extract_directional_boundary,
    filter_reflective_points,
    select_target_cluster,
)


@dataclass
class Measurement:
    pair: FramePair
    detection: DetectedTarget
    center2d: Any
    center3d: Any
    cluster_points: np.ndarray
    reflective_count: int
    boundary_count: int
    cluster_diameter_m: float
    cluster_plane_rmse_m: float
    elapsed_seconds: float


def _load_config(source: Path) -> Dict[str, object]:
    try:
        document = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValueError("cannot read {}: {}".format(source, error)) from error
    if not isinstance(document, dict):
        raise ValueError("{} must contain a YAML mapping".format(source))
    return document


def _measure_frame(
    pair: FramePair,
    dataset: Dataset,
    methods: Mapping[str, Any],
    extraction_config: Mapping[str, object],
    detection_config: Mapping[str, object],
) -> Measurement:
    started = perf_counter()
    image = read_image(pair.image_path)
    detection = detect_target_ellipse(
        image,
        dataset.intrinsic,
        dataset.distortion,
        dataset.distortion_model,
        detection_config,
    )
    center2d = methods["2d"].estimate(
        EllipseObservation(
            ellipse=detection.ellipse,
            polynomial=detection.polynomial,
            intrinsic=dataset.intrinsic,
            marker_diameter=dataset.marker_diameter_m,
            contour=detection.rectified_contour,
            input_is_rectified=True,
        )
    )

    cloud = read_pcd(pair.point_cloud_path)
    reflectance_config = extraction_config["reflectance"]
    clustering_config = extraction_config["clustering"]
    boundary_config = extraction_config["boundary"]
    validation_config = extraction_config["fit_validation"]
    reflective_points, _ = filter_reflective_points(
        cloud.points,
        cloud.intensity,
        minimum_intensity=float(reflectance_config["minimum_intensity"]),
        distance_range_m=tuple(reflectance_config["distance_range_m"]),
    )
    cluster = select_target_cluster(
        reflective_points,
        marker_diameter_m=dataset.marker_diameter_m,
        neighbor_radius_m=float(clustering_config["neighbor_radius_m"]),
        minimum_points=int(clustering_config["minimum_points"]),
        diameter_tolerance_m=float(clustering_config["diameter_tolerance_m"]),
        maximum_plane_rmse_m=float(clustering_config["maximum_plane_rmse_m"]),
    )
    boundary = extract_directional_boundary(
        cluster.points,
        angular_bins=int(boundary_config["angular_bins"]),
        minimum_points=int(boundary_config["minimum_points"]),
    )
    center3d = methods["3d"].fit(boundary)
    expected_radius = dataset.marker_diameter_m / 2.0
    radius_error = abs(center3d.radius - expected_radius)
    if radius_error > float(validation_config["radius_tolerance_m"]):
        raise ValueError(
            "fitted radius {:.4f} m differs from nominal {:.4f} m".format(
                center3d.radius, expected_radius
            )
        )
    return Measurement(
        pair=pair,
        detection=detection,
        center2d=center2d,
        center3d=center3d,
        cluster_points=cluster.points,
        reflective_count=len(reflective_points),
        boundary_count=len(boundary),
        cluster_diameter_m=cluster.estimated_diameter_m,
        cluster_plane_rmse_m=cluster.plane_rmse_m,
        elapsed_seconds=perf_counter() - started,
    )


def _candidate_arrays(measurements: List[Measurement]) -> tuple[np.ndarray, np.ndarray]:
    first, second = [], []
    for measurement in measurements:
        candidates = measurement.center2d.candidates
        first.append(candidates[0])
        second.append(candidates[1] if len(candidates) > 1 else candidates[0])
    return np.asarray(first), np.asarray(second)


def _reprojection_error_statistics(
    points3d: np.ndarray,
    points2d: np.ndarray,
    intrinsic: np.ndarray,
    rotation: np.ndarray,
    translation: np.ndarray,
    inlier_mask: np.ndarray,
) -> Dict[str, float]:
    camera = (
        np.asarray(rotation, dtype=float) @ np.asarray(points3d, dtype=float).T
    ).T + np.asarray(translation, dtype=float).reshape(1, 3)
    homogeneous = (np.asarray(intrinsic, dtype=float) @ camera.T).T
    projected = homogeneous[:, :2] / homogeneous[:, 2, None]
    errors = np.linalg.norm(projected - np.asarray(points2d, dtype=float), axis=1)
    mask = np.asarray(inlier_mask, dtype=bool).reshape(-1)
    if mask.shape != (len(errors),) or not np.any(mask):
        raise ValueError("pose must contain at least one calibration inlier")
    return {
        "mean_reprojection_error_all_px": float(np.mean(errors)),
        "mean_reprojection_error_inliers_px": float(np.mean(errors[mask])),
    }


def _solve_primary_pose(
    points3d: np.ndarray,
    points2d: np.ndarray,
    intrinsic: np.ndarray,
    seed: int = 2025,
) -> Dict[str, Any]:
    cv2.setRNGSeed(int(seed) & 0x7FFFFFFF)
    success, rotation_vector, translation, inliers = cv2.solvePnPRansac(
        points3d,
        points2d,
        intrinsic,
        np.zeros(5),
        iterationsCount=1000,
        reprojectionError=8.0,
        confidence=0.99,
        flags=cv2.SOLVEPNP_EPNP,
    )
    if not success:
        raise RuntimeError("PnP-RANSAC failed for primary 2D centers")
    rotation = cv2.Rodrigues(rotation_vector)[0]
    inlier_mask = np.zeros(len(points3d), dtype=bool)
    if inliers is not None:
        inlier_mask[np.asarray(inliers).reshape(-1)] = True
    error_statistics = _reprojection_error_statistics(
        points3d,
        points2d,
        intrinsic,
        rotation,
        translation,
        inlier_mask,
    )
    return {
        "rotation": rotation,
        "translation": translation.reshape(3),
        "selected_points": points2d,
        "inlier_mask": inlier_mask,
        # Backwards-compatible alias. This metric has always been evaluated on
        # the final calibration inliers, but the old name did not say so.
        "mean_reprojection_error_px": error_statistics[
            "mean_reprojection_error_inliers_px"
        ],
        **error_statistics,
        "iterations": None,
        "status": "success",
    }


def _solve_pose(
    measurements: List[Measurement],
    dataset: Dataset,
    ambiguity_method: Optional[Any],
) -> Dict[str, Any]:
    points3d = np.asarray([measurement.center3d.center for measurement in measurements])
    candidate_a, candidate_b = _candidate_arrays(measurements)
    if ambiguity_method is None:
        return _solve_primary_pose(points3d, candidate_a, dataset.intrinsic)
    if not callable(getattr(ambiguity_method, "resolve", None)):
        raise ValueError(
            "{} cannot resolve cross-frame candidates in qualitative_realworld".format(
                ambiguity_method.name
            )
        )
    result = ambiguity_method.resolve(
        AmbiguousCorrespondences(points3d, candidate_a, candidate_b, dataset.intrinsic)
    )
    error_statistics = _reprojection_error_statistics(
        points3d,
        result.selected_points,
        dataset.intrinsic,
        result.rotation,
        result.translation,
        result.inlier_mask,
    )
    return {
        "rotation": result.rotation,
        "translation": result.translation.reshape(3),
        "selected_points": result.selected_points,
        "inlier_mask": result.inlier_mask,
        "mean_reprojection_error_px": error_statistics[
            "mean_reprojection_error_inliers_px"
        ],
        **error_statistics,
        "iterations": result.iterations,
        "status": result.status.value,
        "confidence": result.confidence,
        "pose_failures": result.pose_failures,
        "elapsed_seconds": result.elapsed_seconds,
    }


def _measurement_summary(measurement: Measurement) -> Dict[str, Any]:
    return {
        "frame_id": measurement.pair.frame_id,
        "status": "success",
        "center3d_m": measurement.center3d.center,
        "radius_m": measurement.center3d.radius,
        "circle_inliers": int(np.count_nonzero(measurement.center3d.inlier_mask)),
        "circle_inlier_rmse_m": measurement.center3d.inlier_rmse,
        "center2d_candidates_px": measurement.center2d.candidates,
        "center2d_scores": measurement.center2d.scores,
        "ellipse_proposal_source": measurement.detection.proposal_source,
        "reflective_points": measurement.reflective_count,
        "cluster_points": len(measurement.cluster_points),
        "boundary_points": measurement.boundary_count,
        "cluster_diameter_m": measurement.cluster_diameter_m,
        "cluster_plane_rmse_m": measurement.cluster_plane_rmse_m,
        "elapsed_seconds": measurement.elapsed_seconds,
    }


def _run_dataset(
    dataset: Dataset,
    context: ExperimentContext,
    methods: Mapping[str, Any],
    extraction_config: Mapping[str, object],
    detection_config: Mapping[str, object],
    evaluation_config: Mapping[str, object],
) -> Dict[str, Any]:
    pairs = dataset.pairs
    if context.max_frames is not None:
        pairs = pairs[: context.max_frames]
    measurements: List[Measurement] = []
    failures = []
    for pair in pairs:
        try:
            measurements.append(
                _measure_frame(
                    pair,
                    dataset,
                    methods,
                    extraction_config,
                    detection_config,
                )
            )
        except Exception as error:
            failures.append(
                {
                    "frame_id": pair.frame_id,
                    "status": "failed",
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )

    pose = None
    pose_failure = None
    if len(measurements) >= 4:
        try:
            pose = _solve_pose(measurements, dataset, methods["ambiguity"])
        except Exception as error:
            pose_failure = {
                "error_type": type(error).__name__,
                "error": str(error),
            }

    frame_summaries = []
    output_directory = context.output_directory / dataset.name
    method_names = {
        "2d": methods["2d"].name,
        "3d": methods["3d"].name,
        "ambiguity": (
            None if methods["ambiguity"] is None else methods["ambiguity"].name
        ),
    }
    for index, measurement in enumerate(measurements):
        image = read_image(measurement.pair.image_path)
        cloud = read_pcd(measurement.pair.point_cloud_path)
        selected = (
            measurement.center2d.primary
            if pose is None
            else np.asarray(pose["selected_points"])[index]
        )
        calibration_inlier = (
            None if pose is None else bool(pose["inlier_mask"][index])
        )
        destination = output_directory / "{}.png".format(measurement.pair.frame_id)
        reprojection_error = render_qualitative_frame(
            image,
            intrinsic=dataset.intrinsic,
            distortion=dataset.distortion,
            rectified_cv_ellipse=measurement.detection.rectified_cv_ellipse,
            candidates=measurement.center2d.candidates,
            selected_center=selected,
            center3d=measurement.center3d.center,
            circle_radius_m=measurement.center3d.radius,
            point_cloud_points=cloud.points,
            point_cloud_intensity=cloud.intensity,
            methods=method_names,
            destination=destination,
            config=evaluation_config,
            rotation=None if pose is None else pose["rotation"],
            translation=None if pose is None else pose["translation"],
            calibration_inlier=calibration_inlier,
        )
        summary = _measurement_summary(measurement)
        summary["selected_center2d_px"] = selected
        summary["qualitative_image"] = destination.relative_to(context.output_directory)
        if pose is not None:
            summary["calibration_inlier"] = calibration_inlier
        if reprojection_error is not None:
            summary["reprojection_error_px"] = reprojection_error
        frame_summaries.append(summary)

    pose_summary = None
    if pose is not None:
        pose_summary = {
            key: value
            for key, value in pose.items()
            if key != "selected_points" and key != "inlier_mask"
        }
        pose_summary["inlier_count"] = int(np.count_nonzero(pose["inlier_mask"]))
        pose_summary["correspondence_count"] = len(measurements)
    return {
        "dataset": dataset.name,
        "attempted_frames": len(pairs),
        "successful_frames": len(measurements),
        "failed_frames": len(failures),
        "calibration": pose_summary,
        "calibration_failure": pose_failure,
        "frames": sorted(
            frame_summaries + failures, key=lambda frame: frame["frame_id"]
        ),
    }


def run(context: ExperimentContext) -> Dict[str, Any]:
    directory = context.experiment_directory
    methods = {
        "2d": context.require_single_method("2d"),
        "3d": context.require_single_method("3d"),
        "ambiguity": context.optional_single_method("ambiguity"),
    }
    extraction_config = _load_config(directory / "extraction3d" / "config.yaml")
    detection_config = _load_config(directory / "detection2d" / "config.yaml")
    evaluation_config = _load_config(directory / "evaluation" / "config.yaml")
    datasets = [
        _run_dataset(
            load_dataset(context.repository_root / "data", name),
            context,
            methods,
            extraction_config,
            detection_config,
            evaluation_config,
        )
        for name in context.selection.datasets
    ]
    return {
        "schema_version": 1,
        "experiment": context.selection.name,
        "methods": {
            "2d": methods["2d"].name,
            "3d": methods["3d"].name,
            "ambiguity": (
                None
                if methods["ambiguity"] is None
                else methods["ambiguity"].name
            ),
        },
        "datasets": datasets,
    }


__all__ = ["run"]
