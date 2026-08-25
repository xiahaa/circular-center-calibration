"""Homography Validation ambiguity resolver from the paper."""

from __future__ import annotations

import numpy as np

from circular_center.center2d import select_projected_center_by_homography


class HomographyValidation:
    name = "Homography Validation"

    def __init__(self, nominal_radius_ratio: float = 1.0) -> None:
        self.nominal_radius_ratio = float(nominal_radius_ratio)

    def select(
        self,
        ellipse: np.ndarray,
        polynomial: np.ndarray,
        contour: np.ndarray,
        coplanar_contour: np.ndarray,
        intrinsic: np.ndarray,
        radius: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        return select_projected_center_by_homography(
            ellipse,
            polynomial,
            contour,
            coplanar_contour,
            intrinsic,
            radius,
            nominal_radius_ratio=self.nominal_radius_ratio,
        )


__all__ = ["HomographyValidation"]
