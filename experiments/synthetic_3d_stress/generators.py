"""Deterministic generators for the Figure 6 angular-support study."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass(frozen=True)
class StressSample:
    """One noisy observation of a physical 3D circle."""

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


def derive_trial_seed(
    base_seed: int,
    distribution_index: int,
    point_count: int,
    arc_degrees: int,
    trial: int,
) -> int:
    """Derive a stable seed without depending on Python's randomized hash."""

    sequence = np.random.SeedSequence(
        [
            int(base_seed),
            int(distribution_index),
            int(point_count),
            int(arc_degrees),
            int(trial),
        ]
    )
    return int(sequence.generate_state(1, dtype=np.uint32)[0])


def _angles(
    generator: np.random.Generator,
    distribution: str,
    point_count: int,
    arc_degrees: float,
    band_jitter_degrees: float,
) -> np.ndarray:
    span = float(np.deg2rad(arc_degrees))
    phase = float(generator.uniform(0.0, 2.0 * np.pi))
    if distribution == "full_circle_uniform":
        return generator.uniform(0.0, 2.0 * np.pi, point_count)
    if distribution == "single_arc":
        return phase + generator.uniform(-0.5 * span, 0.5 * span, point_count)
    if distribution == "dual_opposite_arcs":
        first_count = (point_count + 1) // 2
        second_count = point_count - first_count
        half_arc_width = 0.5 * span
        first = generator.uniform(
            -0.5 * half_arc_width, 0.5 * half_arc_width, first_count
        )
        second = generator.uniform(
            -0.5 * half_arc_width, 0.5 * half_arc_width, second_count
        )
        return phase + np.concatenate((first, second + np.pi))
    if distribution == "hdl64_type_bands":
        band_count = min(16, max(2, int(np.floor(np.sqrt(point_count)))))
        centers = np.linspace(-0.5 * span, 0.5 * span, band_count)
        assignments = generator.integers(0, band_count, size=point_count)
        jitter = generator.normal(
            0.0, np.deg2rad(float(band_jitter_degrees)), size=point_count
        )
        return phase + centers[assignments] + jitter
    raise ValueError("unknown stress distribution {!r}".format(distribution))


def generate_sample(
    seed: int,
    *,
    distribution: str,
    point_count: int,
    arc_degrees: float,
    radius_m: float,
    noise_sigma_m: float,
    center_min_m: float,
    center_max_m: float,
    band_jitter_degrees: float,
) -> StressSample:
    """Generate one trial using the four distributions defined in the paper."""

    generator = make_generator(seed)
    center = generator.uniform(float(center_min_m), float(center_max_m), 3)
    normal = generator.normal(0.0, 1.0, 3)
    normal /= np.linalg.norm(normal)
    basis_u, basis_v = circle_basis(normal)
    angles = _angles(
        generator,
        distribution,
        int(point_count),
        float(arc_degrees),
        float(band_jitter_degrees),
    )
    points = center + float(radius_m) * (
        np.cos(angles)[:, None] * basis_u + np.sin(angles)[:, None] * basis_v
    )
    points += generator.normal(0.0, float(noise_sigma_m), size=points.shape)
    return StressSample(center, float(radius_m), normal, points)


__all__ = [
    "StressSample",
    "circle_basis",
    "derive_trial_seed",
    "generate_sample",
    "make_generator",
]
