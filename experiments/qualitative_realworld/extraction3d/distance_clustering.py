"""Euclidean clustering and circular-target geometry selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass(frozen=True)
class TargetCluster:
    points: np.ndarray
    estimated_diameter_m: float
    plane_rmse_m: float
    score: float


def _connected_components(points: np.ndarray, radius: float) -> List[np.ndarray]:
    try:
        from scipy.spatial import cKDTree
    except ImportError as error:
        raise RuntimeError("SciPy is required for real-world distance clustering") from error

    parent = np.arange(len(points), dtype=int)
    size = np.ones(len(points), dtype=int)

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first: int, second: int) -> None:
        first_root, second_root = find(first), find(second)
        if first_root == second_root:
            return
        if size[first_root] < size[second_root]:
            first_root, second_root = second_root, first_root
        parent[second_root] = first_root
        size[first_root] += size[second_root]

    pairs = cKDTree(points).query_pairs(radius, output_type="ndarray")
    for first, second in pairs:
        union(int(first), int(second))
    groups = {}
    for index in range(len(points)):
        groups.setdefault(find(index), []).append(index)
    return [points[np.asarray(indices, dtype=int)] for indices in groups.values()]


def _cluster_geometry(points: np.ndarray) -> tuple[float, float]:
    center = np.median(points, axis=0)
    centered = points - center
    _, _, basis = np.linalg.svd(centered, full_matrices=False)
    plane_coordinates = centered @ basis[:2].T
    plane_center = np.median(plane_coordinates, axis=0)
    radii = np.linalg.norm(plane_coordinates - plane_center, axis=1)
    estimated_diameter = 2.0 * float(np.quantile(radii, 0.95))
    plane_rmse = float(np.sqrt(np.mean(np.square(centered @ basis[2]))))
    return estimated_diameter, plane_rmse


def select_target_cluster(
    points: np.ndarray,
    *,
    marker_diameter_m: float,
    neighbor_radius_m: float,
    minimum_points: int,
    diameter_tolerance_m: float,
    maximum_plane_rmse_m: float,
) -> TargetCluster:
    coordinates = np.asarray(points, dtype=float)
    if coordinates.ndim != 2 or coordinates.shape[1] != 3:
        raise ValueError("points must have shape (N, 3)")
    if len(coordinates) < minimum_points:
        raise ValueError(
            "only {} reflective points; at least {} are required".format(
                len(coordinates), minimum_points
            )
        )
    candidates = []
    for cluster in _connected_components(coordinates, float(neighbor_radius_m)):
        if len(cluster) < minimum_points:
            continue
        diameter, plane_rmse = _cluster_geometry(cluster)
        diameter_error = abs(diameter - marker_diameter_m)
        if diameter_error > diameter_tolerance_m or plane_rmse > maximum_plane_rmse_m:
            continue
        score = (
            diameter_error / diameter_tolerance_m
            + plane_rmse / maximum_plane_rmse_m
            - 0.05 * np.log(len(cluster))
        )
        candidates.append(
            TargetCluster(
                points=cluster,
                estimated_diameter_m=diameter,
                plane_rmse_m=plane_rmse,
                score=float(score),
            )
        )
    if not candidates:
        raise ValueError("no reflective cluster matches the circular target geometry")
    return min(candidates, key=lambda candidate: candidate.score)


__all__ = ["TargetCluster", "select_target_cluster"]
