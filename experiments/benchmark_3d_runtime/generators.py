"""Deterministic 64-point input used by the runtime workers."""

from __future__ import annotations

import numpy as np


def generate_benchmark_points(
    seed: int,
    *,
    point_count: int,
    radius_m: float,
    noise_sigma_m: float,
) -> np.ndarray:
    generator = np.random.Generator(np.random.MT19937(int(seed)))
    center = generator.uniform(-2.0, 2.0, 3)
    normal = generator.normal(0.0, 1.0, 3)
    normal /= np.linalg.norm(normal)
    reference = (
        np.array([0.0, 0.0, 1.0])
        if abs(float(normal[2])) < 0.9
        else np.array([1.0, 0.0, 0.0])
    )
    basis_u = np.cross(normal, reference)
    basis_u /= np.linalg.norm(basis_u)
    basis_v = np.cross(normal, basis_u)
    angles = np.linspace(0.0, 2.0 * np.pi, int(point_count), endpoint=False)
    points = center + float(radius_m) * (
        np.cos(angles)[:, None] * basis_u + np.sin(angles)[:, None] * basis_v
    )
    points += generator.normal(0.0, float(noise_sigma_m), size=points.shape)
    return points


__all__ = ["generate_benchmark_points"]
