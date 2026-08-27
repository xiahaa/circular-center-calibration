"""Self-contained synthetic point generators for the paper protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Tuple

import numpy as np


@dataclass(frozen=True)
class CircleSample:
    center: np.ndarray
    radius: float
    normal: np.ndarray
    points: np.ndarray


def make_generator(seed: int) -> np.random.Generator:
    """Use MT19937, matching the engine selected by the reference C++ code."""

    return np.random.Generator(np.random.MT19937(int(seed)))


def circle_basis(normal: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    normal = np.asarray(normal, dtype=float)
    normal /= np.linalg.norm(normal)
    reference = np.array([0.0, 0.0, 1.0]) if abs(normal[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    basis_u = np.cross(normal, reference)
    basis_u /= np.linalg.norm(basis_u)
    basis_v = np.cross(normal, basis_u)
    basis_v /= np.linalg.norm(basis_v)
    return basis_u, basis_v


def _scenario_angles(
    generator: np.random.Generator,
    distribution: str,
    point_count: int,
    arc_degrees: float,
) -> np.ndarray:
    arc_radians = np.deg2rad(arc_degrees)
    if distribution == "uniform":
        return generator.uniform(0.0, 2.0 * np.pi, point_count)
    if distribution == "limited_nonuniform":
        values = generator.uniform(0.0, 1.0, point_count)
        return np.square(values) * arc_radians - 0.2 * arc_radians
    if distribution == "sparse_clusters":
        cluster_count = min(3, point_count // 4)
        if cluster_count == 0:
            raise ValueError("sparse_clusters requires at least four points")
        angles = []
        for cluster_index in range(cluster_count):
            cluster_center = generator.uniform(0.0, 2.0 * np.pi)
            cluster_width = generator.uniform(np.pi / 30.0, np.pi / 9.0)
            count = point_count // cluster_count
            if cluster_index == cluster_count - 1:
                count = point_count - len(angles)
            angles.extend(generator.normal(cluster_center, cluster_width, count))
        return np.asarray(angles, dtype=float)
    if distribution == "symmetric_nonuniform":
        if point_count <= 1:
            return np.zeros(point_count)
        half = point_count // 2
        intervals = generator.uniform(0.8, 1.2, half)
        intervals *= (0.5 * arc_radians) / np.sum(intervals)
        cumulative = np.concatenate(([0.0], np.cumsum(intervals)))
        return np.concatenate((-cumulative[::-1], cumulative[1:]))[:point_count]
    raise ValueError("unknown synthetic distribution {!r}".format(distribution))


def generate_monte_carlo_sample(
    truth_generator: np.random.Generator,
    scenario: Mapping[str, Any],
) -> CircleSample:
    """Generate one trial from the paper's four-scenario benchmark."""

    center = truth_generator.uniform(-2.0, 2.0, 3)
    radius = float(truth_generator.uniform(1.0, 5.0))
    normal = truth_generator.normal(0.0, 1.0, 3)
    normal /= np.linalg.norm(normal)
    point_seed = int(truth_generator.integers(0, 2**32, dtype=np.uint64))
    point_generator = make_generator(point_seed)
    point_count = int(scenario["point_count"])
    angles = _scenario_angles(
        point_generator,
        str(scenario["distribution"]),
        point_count,
        float(scenario["arc_degrees"]),
    )
    basis_u, basis_v = circle_basis(normal)
    points = center + radius * (
        np.cos(angles)[:, None] * basis_u + np.sin(angles)[:, None] * basis_v
    )
    points += point_generator.normal(
        0.0, float(scenario["noise_sigma_m"]), size=points.shape
    )
    return CircleSample(center, radius, normal, points)


def _axis_angle_rotation(vector: np.ndarray) -> np.ndarray:
    angle = float(np.linalg.norm(vector))
    if angle <= np.finfo(float).eps:
        return np.eye(3)
    axis = np.asarray(vector, dtype=float) / angle
    cross = np.array(
        [
            [0.0, -axis[2], axis[1]],
            [axis[2], 0.0, -axis[0]],
            [-axis[1], axis[0], 0.0],
        ]
    )
    return np.eye(3) + np.sin(angle) * cross + (1.0 - np.cos(angle)) * (cross @ cross)


def generate_outlier_base_samples(
    seed: int,
    count: int,
    configuration: Mapping[str, Any],
) -> Tuple[CircleSample, ...]:
    """Regenerate the unreleased base point clouds used by the outlier benchmark."""

    generator = make_generator(seed)
    samples = []
    point_count = int(configuration["point_count"])
    angles = np.linspace(0.0, 2.0 * np.pi, point_count, endpoint=True)
    local_unit_circle = np.column_stack(
        (np.cos(angles), np.sin(angles), np.zeros(point_count))
    )
    for _ in range(count):
        radius = float(
            generator.uniform(
                float(configuration["radius_min_m"]),
                float(configuration["radius_max_m"]),
            )
        )
        rotation = _axis_angle_rotation(generator.normal(0.0, 1.0, 3))
        center = generator.uniform(
            float(configuration["center_min_m"]),
            float(configuration["center_max_m"]),
            3,
        )
        points = (rotation @ (radius * local_unit_circle).T).T + center
        points += generator.normal(
            0.0, float(configuration["noise_sigma_m"]), size=points.shape
        )
        samples.append(CircleSample(center, radius, rotation[:, 2], points))
    return tuple(samples)


def add_reference_outliers(
    sample: CircleSample,
    ratio: float,
    generator: np.random.Generator,
    coordinate_min: int,
    coordinate_max: int,
) -> CircleSample:
    """Append integer outliers, including the effective zero perturbation bug."""

    outlier_count = int(float(ratio) * len(sample.points))
    outliers = generator.integers(
        int(coordinate_min),
        int(coordinate_max) + 1,
        size=(outlier_count, 3),
    ).astype(float)
    points = np.vstack((sample.points, outliers))
    return CircleSample(sample.center, sample.radius, sample.normal, points)


__all__ = [
    "CircleSample",
    "add_reference_outliers",
    "circle_basis",
    "generate_monte_carlo_sample",
    "generate_outlier_base_samples",
    "make_generator",
]
