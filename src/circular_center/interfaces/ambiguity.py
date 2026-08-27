"""Contracts for resolving two projected-center candidates."""

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from circular_center.center2d import QuasiRansacResult


@dataclass(frozen=True)
class AmbiguousCorrespondences:
    """Metric 3D points paired with two image candidates per point."""

    points3d: np.ndarray
    candidate_a: np.ndarray
    candidate_b: np.ndarray
    intrinsic: np.ndarray

    def __post_init__(self) -> None:
        points3d = np.asarray(self.points3d, dtype=float)
        candidate_a = np.asarray(self.candidate_a, dtype=float)
        candidate_b = np.asarray(self.candidate_b, dtype=float)
        intrinsic = np.asarray(self.intrinsic, dtype=float)
        if points3d.ndim != 2 or points3d.shape[1] != 3:
            raise ValueError("points3d must have shape (N, 3)")
        if candidate_a.shape != (len(points3d), 2) or candidate_b.shape != candidate_a.shape:
            raise ValueError("candidate arrays must both have shape (N, 2)")
        if intrinsic.shape != (3, 3):
            raise ValueError("intrinsic must have shape (3, 3)")
        if not all(
            np.isfinite(value).all()
            for value in (points3d, candidate_a, candidate_b, intrinsic)
        ):
            raise ValueError("ambiguous correspondences must be finite")
        object.__setattr__(self, "points3d", points3d)
        object.__setattr__(self, "candidate_a", candidate_a)
        object.__setattr__(self, "candidate_b", candidate_b)
        object.__setattr__(self, "intrinsic", intrinsic)


class AmbiguityMethod(Protocol):
    """Protocol for cross-frame candidate disambiguation methods."""

    name: str

    def resolve(self, correspondences: AmbiguousCorrespondences) -> QuasiRansacResult:
        ...


__all__ = ["AmbiguityMethod", "AmbiguousCorrespondences"]
