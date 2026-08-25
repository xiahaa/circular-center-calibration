"""Quasi-RANSAC ambiguity resolver from the paper."""

from circular_center.center2d import QuasiRansacResult, fit_quasi_ransac
from circular_center.interfaces import AmbiguousCorrespondences


class QuasiRANSAC:
    name = "Quasi-RANSAC"

    def __init__(
        self,
        confidence: float = 0.99,
        valid_correspondence_ratio: float = 1.0,
        inlier_threshold_px: float = 8.0,
        max_iterations: int = 2000,
        seed: int = 2025,
    ) -> None:
        self.confidence = float(confidence)
        self.valid_correspondence_ratio = float(valid_correspondence_ratio)
        self.inlier_threshold_px = float(inlier_threshold_px)
        self.max_iterations = int(max_iterations)
        self.seed = int(seed)

    def resolve(
        self,
        correspondences: AmbiguousCorrespondences,
    ) -> QuasiRansacResult:
        return fit_quasi_ransac(
            correspondences.points3d,
            correspondences.candidate_a,
            correspondences.candidate_b,
            correspondences.intrinsic,
            confidence=self.confidence,
            valid_correspondence_ratio=self.valid_correspondence_ratio,
            inlier_threshold=self.inlier_threshold_px,
            max_iterations=self.max_iterations,
            seed=self.seed,
        )


__all__ = ["QuasiRANSAC"]
