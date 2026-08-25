"""Refined Center method from the paper."""

from typing import Sequence

from circular_center.center2d import refine_projected_center
from circular_center.interfaces import Center2DMethodResult, EllipseObservation


class RefinedCenter:
    name = "Refined Center"

    def __init__(
        self,
        search_ratio: float = 0.5,
        directions: int = 16,
        levels_px: Sequence[float] = (2.0, 0.5, 0.1),
        nms_scale: float = 0.08,
    ) -> None:
        self.search_ratio = float(search_ratio)
        self.directions = int(directions)
        self.levels = tuple(float(value) for value in levels_px)
        self.nms_scale = float(nms_scale)

    def estimate(self, observation: EllipseObservation) -> Center2DMethodResult:
        result = refine_projected_center(
            observation.ellipse,
            observation.polynomial,
            observation.intrinsic,
            observation.marker_diameter,
            input_is_rectified=observation.input_is_rectified,
            search_ratio=self.search_ratio,
            directions=self.directions,
            levels=self.levels,
            nms_scale=self.nms_scale,
        )
        return Center2DMethodResult(
            method=self.name,
            candidates=result.candidates,
            scores=result.scores,
            selected_index=None,
            status=result.status.value,
            diagnostics={
                "confidence": result.confidence,
                "ambiguous": result.ambiguous,
                "score_gap": result.score_gap,
                "evaluations": result.evaluations,
                "directions": result.directions,
                "elapsed_seconds": result.elapsed_seconds,
            },
        )


__all__ = ["RefinedCenter"]
