"""Distance and reflectance filtering described by the paper preprocessing stage."""

from __future__ import annotations

from typing import Tuple

import numpy as np


def filter_reflective_points(
    points: np.ndarray,
    intensity: np.ndarray,
    *,
    minimum_intensity: float,
    distance_range_m: Tuple[float, float],
) -> Tuple[np.ndarray, np.ndarray]:
    coordinates = np.asarray(points, dtype=float)
    reflectance = np.asarray(intensity, dtype=float).reshape(-1)
    if coordinates.ndim != 2 or coordinates.shape[1] != 3:
        raise ValueError("points must have shape (N, 3)")
    if reflectance.shape != (len(coordinates),):
        raise ValueError("intensity must have one value per point")
    near, far = (float(value) for value in distance_range_m)
    if not 0.0 <= near < far or not np.isfinite(minimum_intensity):
        raise ValueError("invalid reflectance-filter configuration")
    distance = np.linalg.norm(coordinates, axis=1)
    mask = (
        np.isfinite(coordinates).all(axis=1)
        & np.isfinite(reflectance)
        & (reflectance >= minimum_intensity)
        & (distance >= near)
        & (distance <= far)
    )
    return coordinates[mask], reflectance[mask]


__all__ = ["filter_reflective_points"]
