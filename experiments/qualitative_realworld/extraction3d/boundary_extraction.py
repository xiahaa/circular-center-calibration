"""Directional-gap boundary extraction for a planar reflective cluster."""

from __future__ import annotations

import numpy as np


def extract_directional_boundary(
    points: np.ndarray,
    *,
    angular_bins: int,
    minimum_points: int,
) -> np.ndarray:
    coordinates = np.asarray(points, dtype=float)
    if coordinates.ndim != 2 or coordinates.shape[1] != 3:
        raise ValueError("points must have shape (N, 3)")
    if angular_bins < 8 or minimum_points < 5:
        raise ValueError("angular_bins must be >= 8 and minimum_points must be >= 5")
    center = np.median(coordinates, axis=0)
    centered = coordinates - center
    _, _, basis = np.linalg.svd(centered, full_matrices=False)
    plane_coordinates = centered @ basis[:2].T
    origin = np.median(plane_coordinates, axis=0)
    offsets = plane_coordinates - origin
    angles = np.mod(np.arctan2(offsets[:, 1], offsets[:, 0]), 2.0 * np.pi)
    radii = np.linalg.norm(offsets, axis=1)
    bin_indices = np.minimum(
        (angles * angular_bins / (2.0 * np.pi)).astype(int), angular_bins - 1
    )
    selected = []
    for bin_index in range(angular_bins):
        members = np.flatnonzero(bin_indices == bin_index)
        if len(members):
            selected.append(int(members[np.argmax(radii[members])]))
    selected = np.unique(selected)
    if len(selected) < minimum_points:
        raise ValueError(
            "boundary has {} directional samples; at least {} are required".format(
                len(selected), minimum_points
            )
        )
    return coordinates[selected]


__all__ = ["extract_directional_boundary"]
