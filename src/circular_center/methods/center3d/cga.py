"""CGA method from the paper."""

import numpy as np

from circular_center.center3d import CircleFitResult, fit_cga_circle


class CGA:
    name = "CGA"

    def fit(self, points: np.ndarray) -> CircleFitResult:
        return fit_cga_circle(points)


__all__ = ["CGA"]
