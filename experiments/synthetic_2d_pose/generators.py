"""Synthetic circle correspondences used by paper Figure 9."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Tuple

import numpy as np

from experiments.synthetic_2d_accuracy.generators import (
    FittedEllipse,
    fit_projected_ellipse,
    make_trial_seeds,
)


@dataclass(frozen=True)
class CirclePairObservation:
    point3d: np.ndarray
    ground_truth_2d: np.ndarray
    primary: FittedEllipse
    validation: FittedEllipse


@dataclass(frozen=True)
class PoseTrial:
    seed: int
    intrinsic: np.ndarray
    rotation: np.ndarray
    translation: np.ndarray
    primary_radius: float
    validation_radius: float
    observations: Tuple[CirclePairObservation, ...]


def _opencv():
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError("OpenCV is required by synthetic_2d_pose") from error
    return cv2


def generate_camera_pose(generator: np.random.Generator):
    """Preserve the draw order and distributions in CCFinder utility.py."""

    rx, ry, rz = np.deg2rad(
        [
            35.0 + (generator.standard_normal() * 10.0 - 5.0),
            -25.0 + (generator.standard_normal() * 10.0 - 5.0),
            10.0 + (generator.standard_normal() * 10.0 - 5.0),
        ]
    )
    rotation_x = np.array(
        [[1.0, 0.0, 0.0], [0.0, np.cos(rx), -np.sin(rx)], [0.0, np.sin(rx), np.cos(rx)]]
    )
    rotation_y = np.array(
        [[np.cos(ry), 0.0, np.sin(ry)], [0.0, 1.0, 0.0], [-np.sin(ry), 0.0, np.cos(ry)]]
    )
    rotation_z = np.array(
        [[np.cos(rz), -np.sin(rz), 0.0], [np.sin(rz), np.cos(rz), 0.0], [0.0, 0.0, 1.0]]
    )
    rotation = rotation_z @ rotation_y @ rotation_x
    translation = np.array(
        [
            [1.6 + (generator.standard_normal() * 0.5 - 0.25)],
            [-0.9 + (generator.standard_normal() * 0.5 - 0.25)],
            [3.5 + (generator.standard_normal() * 0.5 - 0.25)],
        ]
    )
    return rotation, translation


def _circle_points(
    radius: float,
    point_count: int,
    generator: np.random.Generator,
):
    theta = np.linspace(0.0, 2.0 * np.pi, point_count, endpoint=True)
    center = generator.random((3, 1)) * 5.0
    points = np.vstack(
        (radius * np.cos(theta), radius * np.sin(theta), np.zeros(point_count))
    )
    return points + center, center


def generate_trial(
    seed: int,
    protocol: Mapping[str, Any],
    circle_count: int,
) -> PoseTrial:
    generator = np.random.default_rng(int(seed))
    camera = protocol["camera"]
    geometry = protocol["geometry"]
    sampling = protocol["sampling"]
    intrinsic = np.array(
        [
            [camera["fx_px"], 0.0, camera["cx_px"]],
            [0.0, camera["fy_px"], camera["cy_px"]],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    rotation, translation = generate_camera_pose(generator)
    primary_radius = float(geometry["primary_radius"])
    validation_radius = float(geometry["validation_radius"])
    contour_points = int(sampling["contour_points"])
    noise_sigma = float(sampling["image_noise_sigma_px"])
    observations = []

    def project(points: np.ndarray) -> np.ndarray:
        camera_points = rotation @ points + translation
        normalized = camera_points / camera_points[-1, :]
        projected = intrinsic @ normalized
        projected += np.vstack(
            (
                generator.standard_normal((2, contour_points)) * noise_sigma,
                np.zeros((1, contour_points)),
            )
        )
        return projected[:2].astype(np.float32)

    for _ in range(int(circle_count)):
        while True:
            primary_points, primary_center = _circle_points(
                primary_radius, contour_points, generator
            )
            primary = fit_projected_ellipse(
                project(primary_points),
                contour_points=contour_points,
                image_width=int(camera["image_width_px"]),
                image_height=int(camera["image_height_px"]),
                compute_mass_contour=True,
            )
            validation_points, validation_center = _circle_points(
                validation_radius, contour_points, generator
            )
            validation = fit_projected_ellipse(
                project(validation_points),
                contour_points=contour_points,
                image_width=int(camera["image_width_px"]),
                image_height=int(camera["image_height_px"]),
                compute_mass_contour=False,
            )
            if np.linalg.norm(primary_center - validation_center) > float(
                geometry["minimum_center_separation"]
            ):
                break

        camera_center = rotation @ primary_center + translation
        ground_truth = intrinsic @ (camera_center / camera_center[-1, :])
        observations.append(
            CirclePairObservation(
                point3d=primary_center.reshape(3).astype(float),
                ground_truth_2d=ground_truth.reshape(-1)[:2].astype(float),
                primary=primary,
                validation=validation,
            )
        )

    return PoseTrial(
        seed=int(seed),
        intrinsic=intrinsic,
        rotation=rotation,
        translation=translation,
        primary_radius=primary_radius,
        validation_radius=validation_radius,
        observations=tuple(observations),
    )


__all__ = [
    "CirclePairObservation",
    "PoseTrial",
    "generate_camera_pose",
    "generate_trial",
    "make_trial_seeds",
]
