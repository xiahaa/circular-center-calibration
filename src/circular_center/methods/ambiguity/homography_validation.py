"""Homography Validation ambiguity resolver from the paper."""

from __future__ import annotations

import numpy as np

from circular_center.center2d import (
    select_projected_center_by_homography,
    select_projected_center_candidates_by_homography,
)


class HomographyValidation:
    name = "Homography Validation"

    def __init__(
        self,
        nominal_radius_ratio: float = 1.0,
        clamp_degenerate_homography: bool = False,
    ) -> None:
        self.nominal_radius_ratio = float(nominal_radius_ratio)
        self.clamp_degenerate_homography = bool(clamp_degenerate_homography)

    def select(
        self,
        ellipse: np.ndarray,
        polynomial: np.ndarray,
        contour: np.ndarray,
        coplanar_contour: np.ndarray,
        intrinsic: np.ndarray,
        radius: float,
        *,
        candidates: np.ndarray = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        if candidates is not None:
            return select_projected_center_candidates_by_homography(
                candidates,
                ellipse,
                contour,
                coplanar_contour,
                nominal_radius_ratio=self.nominal_radius_ratio,
                clamp_degenerate=self.clamp_degenerate_homography,
            )
        return select_projected_center_by_homography(
            ellipse,
            polynomial,
            contour,
            coplanar_contour,
            intrinsic,
            radius,
            nominal_radius_ratio=self.nominal_radius_ratio,
            clamp_degenerate=self.clamp_degenerate_homography,
        )


__all__ = ["HomographyValidation"]
