"""Self-contained data generation for the paper's 2D center experiment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Tuple

import numpy as np

from circular_center.center2d import get_ellipse_polynomial_coeff


@dataclass(frozen=True)
class FittedEllipse:
    parameters: np.ndarray
    polynomial: np.ndarray
    contour: np.ndarray
    mass_contour: np.ndarray


@dataclass(frozen=True)
class Synthetic2DSample:
    seed: int
    intrinsic: np.ndarray
    marker_radius: float
    primary: FittedEllipse
    coplanar: FittedEllipse
    ground_truth: np.ndarray


def _opencv():
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError("OpenCV is required by synthetic_2d_accuracy") from error
    return cv2


def make_trial_seeds(seed: int, count: int) -> Tuple[int, ...]:
    generator = np.random.default_rng(int(seed))
    return tuple(
        int(generator.integers(0, 2**31 - 1)) for _ in range(int(count))
    )


def _fitted_contour(parameters: np.ndarray, count: int) -> np.ndarray:
    theta = np.linspace(0.0, 2.0 * np.pi, int(count), endpoint=True)
    angle = float(parameters[4])
    rotation = np.array(
        [
            [np.cos(angle), -np.sin(angle)],
            [np.sin(angle), np.cos(angle)],
        ]
    )
    return (
        rotation
        @ np.vstack(
            (
                parameters[2] * np.cos(theta),
                parameters[3] * np.sin(theta),
            )
        )
        + parameters[:2, None]
    )


def _mass_contour(
    ellipse_cv: Any,
    image_width: int,
    image_height: int,
) -> np.ndarray:
    cv2 = _opencv()
    (center_x, center_y), (diameter_a, diameter_b), angle_degrees = ellipse_cv
    mask = np.zeros((int(image_height), int(image_width)), dtype=np.uint8)
    cv2.ellipse(
        mask,
        (int(center_x), int(center_y)),
        (int(0.5 * diameter_a), int(0.5 * diameter_b)),
        float(angle_degrees),
        0.0,
        360.0,
        255,
        -1,
    )
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        raise RuntimeError("the fitted ellipse produced an empty image mask")
    return max(contours, key=cv2.contourArea).reshape(-1, 2).astype(float)


def fit_projected_ellipse(
    image_points: np.ndarray,
    *,
    contour_points: int,
    image_width: int,
    image_height: int,
    compute_mass_contour: bool = True,
) -> FittedEllipse:
    cv2 = _opencv()
    points = np.asarray(image_points, dtype=np.float32)
    if points.ndim != 2 or points.shape[0] != 2 or points.shape[1] < 5:
        raise ValueError("image_points must have shape (2, N) with N >= 5")
    ellipse_cv = cv2.fitEllipse(points.T)
    parameters = np.array(
        [
            ellipse_cv[0][0],
            ellipse_cv[0][1],
            0.5 * ellipse_cv[1][0],
            0.5 * ellipse_cv[1][1],
            np.deg2rad(ellipse_cv[2]),
        ],
        dtype=float,
    )
    fitted_contour = _fitted_contour(parameters, contour_points)
    return FittedEllipse(
        parameters=parameters,
        polynomial=get_ellipse_polynomial_coeff(ellipse_cv),
        contour=fitted_contour,
        mass_contour=(
            _mass_contour(ellipse_cv, image_width, image_height)
            if compute_mass_contour
            else fitted_contour.T
        ),
    )


def generate_sample(seed: int, protocol: Mapping[str, Any]) -> Synthetic2DSample:
    """Generate one trial with the same random draw order as CCFinder."""

    cv2 = _opencv()
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
    point_count = int(sampling["contour_points"])
    theta = np.linspace(0.0, 2.0 * np.pi, point_count, endpoint=True)
    radius = float(geometry["radius_m"])
    alternate_radius = float(geometry["coplanar_radius_m"])
    primary_points = np.vstack(
        (radius * np.cos(theta), radius * np.sin(theta), np.zeros(point_count))
    )
    coplanar_points = np.vstack(
        (
            alternate_radius * np.cos(theta),
            alternate_radius * np.sin(theta),
            np.zeros(point_count),
        )
    )
    coplanar_points += np.asarray(
        geometry["coplanar_offset_m"], dtype=float
    ).reshape(3, 1)

    rotation_vector = generator.standard_normal((3, 1)) * float(
        sampling["rotation_vector_sigma_rad"]
    )
    rotation = cv2.Rodrigues(rotation_vector)[0]
    translation = np.asarray(
        sampling["translation_mean_m"], dtype=float
    ).reshape(3, 1)
    translation += generator.standard_normal((3, 1)) * float(
        sampling["translation_sigma_m"]
    )

    noise_sigma = float(sampling["image_noise_sigma_px"])

    def project(points: np.ndarray) -> np.ndarray:
        camera_points = rotation @ points + translation
        normalized = camera_points / camera_points[-1, :]
        projected = intrinsic @ normalized
        projected += np.vstack(
            (
                generator.standard_normal((2, point_count)) * noise_sigma,
                np.zeros((1, point_count)),
            )
        )
        return projected[:2, :].astype(np.float32)

    primary = fit_projected_ellipse(
        project(primary_points),
        contour_points=point_count,
        image_width=int(camera["image_width_px"]),
        image_height=int(camera["image_height_px"]),
    )
    coplanar = fit_projected_ellipse(
        project(coplanar_points),
        contour_points=point_count,
        image_width=int(camera["image_width_px"]),
        image_height=int(camera["image_height_px"]),
        compute_mass_contour=False,
    )
    normalized_center = translation / translation[-1, :]
    ground_truth = (intrinsic @ normalized_center).reshape(-1)[:2]
    return Synthetic2DSample(
        seed=int(seed),
        intrinsic=intrinsic,
        marker_radius=radius,
        primary=primary,
        coplanar=coplanar,
        ground_truth=np.asarray(ground_truth, dtype=float),
    )


__all__ = [
    "FittedEllipse",
    "Synthetic2DSample",
    "fit_projected_ellipse",
    "generate_sample",
    "make_trial_seeds",
]
