"""Deterministic nonplanar and noncircular target generators for Figure 7."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass(frozen=True)
class ToleranceSample:
    center: np.ndarray
    radius: float
    normal: np.ndarray
    points: np.ndarray


def make_generator(seed: int) -> np.random.Generator:
    return np.random.Generator(np.random.MT19937(int(seed)))


def circle_basis(normal: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    normal = np.asarray(normal, dtype=float)
    normal /= np.linalg.norm(normal)
    reference = (
        np.array([0.0, 0.0, 1.0])
        if abs(float(normal[2])) < 0.9
        else np.array([1.0, 0.0, 0.0])
    )
    basis_u = np.cross(normal, reference)
    basis_u /= np.linalg.norm(basis_u)
    basis_v = np.cross(normal, basis_u)
    basis_v /= np.linalg.norm(basis_v)
    return basis_u, basis_v


def derive_trial_seed(base_seed: int, trial: int) -> int:
    sequence = np.random.SeedSequence([int(base_seed), int(trial)])
    return int(sequence.generate_state(1, dtype=np.uint32)[0])


def generate_sample(
    seed: int,
    *,
    deformation: str,
    magnitude: float,
    point_count: int,
    arc_degrees: float,
    radius_m: float,
    noise_sigma_m: float,
    center_min_m: float,
    center_max_m: float,
    axis_semiaxis_scale: float,
) -> ToleranceSample:
    """Generate one paired target-quality trial.

    The quadratic warp and the 180-degree observation arc are the smallest
    deterministic model that recovers the normalized-CGA curve embedded in the
    published Figure 7. The original generator was not released.
    """

    if deformation not in {"normal_warp", "axis_deviation"}:
        raise ValueError("unknown deformation {!r}".format(deformation))
    generator = make_generator(seed)
    center = generator.uniform(float(center_min_m), float(center_max_m), 3)
    normal = generator.normal(0.0, 1.0, 3)
    normal /= np.linalg.norm(normal)
    basis_u, basis_v = circle_basis(normal)
    phase = float(generator.uniform(0.0, 2.0 * np.pi))
    half_arc = 0.5 * float(np.deg2rad(arc_degrees))
    local_angles = generator.uniform(-half_arc, half_arc, int(point_count))

    if deformation == "normal_warp":
        angles = local_angles + phase
        points = center + float(radius_m) * (
            np.cos(angles)[:, None] * basis_u
            + np.sin(angles)[:, None] * basis_v
        )
        normalized_arc = local_angles / half_arc
        warp_profile = 2.0 * np.square(normalized_arc) - 1.0
        points += (
            float(magnitude) * float(radius_m) * warp_profile
        )[:, None] * normal
    else:
        scale = float(axis_semiaxis_scale) * float(magnitude)
        major = float(radius_m) * (1.0 + scale)
        minor = float(radius_m) * (1.0 - scale)
        points = center + (
            major * np.cos(local_angles)[:, None] * basis_u
            + minor * np.sin(local_angles)[:, None] * basis_v
        )

    points += generator.normal(0.0, float(noise_sigma_m), size=points.shape)
    return ToleranceSample(center, float(radius_m), normal, points)


__all__ = [
    "ToleranceSample",
    "circle_basis",
    "derive_trial_seed",
    "generate_sample",
    "make_generator",
]
