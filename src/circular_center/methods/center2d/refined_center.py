"""Refined Center method from the paper."""

from typing import Sequence

from circular_center.center2d import (
    integer_grid_search_reference,
    refine_projected_center,
)
from circular_center.interfaces import Center2DMethodResult, EllipseObservation


class RefinedCenter:
    name = "Refined Center"

    def __init__(
        self,
        search_ratio: float = 0.5,
        directions: int = 16,
        levels_px: Sequence[float] = (2.0, 0.5, 0.1),
        nms_scale: float = 0.08,
        search_mode: str = "coarse_to_fine",
        integer_lattice_step_px: float = 0.1,
        integer_nms_radius_px: float = 10.0,
    ) -> None:
        self.search_ratio = float(search_ratio)
        self.directions = int(directions)
        self.levels = tuple(float(value) for value in levels_px)
        self.nms_scale = float(nms_scale)
        if search_mode not in {"coarse_to_fine", "paper_integer_grid"}:
            raise ValueError(
                "search_mode must be 'coarse_to_fine' or 'paper_integer_grid'"
            )
        self.search_mode = search_mode
        self.integer_lattice_step_px = float(integer_lattice_step_px)
        self.integer_nms_radius_px = float(integer_nms_radius_px)

    def estimate(self, observation: EllipseObservation) -> Center2DMethodResult:
        if self.search_mode == "paper_integer_grid":
            result = integer_grid_search_reference(
                observation.ellipse,
                observation.polynomial,
                observation.intrinsic,
                observation.marker_diameter,
                input_is_rectified=observation.input_is_rectified,
                search_ratio=self.search_ratio,
                directions=self.directions,
                lattice_step=self.integer_lattice_step_px,
                suppress_radius=self.integer_nms_radius_px,
            )
        else:
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
                "search_mode": self.search_mode,
            },
        )


__all__ = ["RefinedCenter"]
