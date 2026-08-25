"""CGA-RANSAC method from the paper."""

from typing import Optional

import numpy as np

from circular_center.center3d import CircleFitResult, fit_circle_ransac


class CGARANSAC:
    name = "CGA-RANSAC"

    def __init__(
        self,
        residual_threshold_m: float,
        max_iterations: int = 500,
        sample_size: int = 5,
        minimum_inliers: Optional[int] = None,
        confidence: float = 0.99,
        seed: int = 0,
    ) -> None:
        self.residual_threshold_m = float(residual_threshold_m)
        self.max_iterations = int(max_iterations)
        self.sample_size = int(sample_size)
        self.minimum_inliers = (
            None if minimum_inliers is None else int(minimum_inliers)
        )
        self.confidence = float(confidence)
        self.seed = int(seed)

    def fit(self, points: np.ndarray) -> CircleFitResult:
        return fit_circle_ransac(
            points,
            residual_threshold=self.residual_threshold_m,
            max_iterations=self.max_iterations,
            sample_size=self.sample_size,
            minimum_inliers=self.minimum_inliers,
            confidence=self.confidence,
            seed=self.seed,
        )


__all__ = ["CGARANSAC"]
