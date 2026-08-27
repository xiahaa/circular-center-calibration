"""Ellipse Center baseline from the paper."""

import numpy as np

from circular_center.interfaces import (
    Center2DMethodResult,
    EllipseObservation,
)


class EllipseCenter:
    name = "Ellipse Center"

    def estimate(self, observation: EllipseObservation) -> Center2DMethodResult:
        return Center2DMethodResult(
            method=self.name,
            candidates=observation.ellipse[None, :2],
            scores=np.zeros(1),
            selected_index=0,
        )


__all__ = ["EllipseCenter"]
