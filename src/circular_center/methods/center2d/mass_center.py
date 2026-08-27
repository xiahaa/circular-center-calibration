"""Mass Center baseline computed from the filled contour moments."""

import numpy as np

from circular_center.interfaces import Center2DMethodResult, EllipseObservation


class MassCenter:
    name = "Mass Center"

    def estimate(self, observation: EllipseObservation) -> Center2DMethodResult:
        if observation.contour is None or len(observation.contour) < 3:
            raise ValueError("Mass Center requires a contour with at least three points")
        points = observation.contour
        following = np.roll(points, -1, axis=0)
        cross = points[:, 0] * following[:, 1] - following[:, 0] * points[:, 1]
        doubled_area = float(np.sum(cross))
        scale = max(1.0, float(np.max(np.abs(points))))
        if abs(doubled_area) <= np.finfo(float).eps * scale * scale:
            center = np.mean(points, axis=0)
            degenerate = True
        else:
            center = np.array(
                [
                    np.sum((points[:, 0] + following[:, 0]) * cross),
                    np.sum((points[:, 1] + following[:, 1]) * cross),
                ]
            ) / (3.0 * doubled_area)
            degenerate = False
        return Center2DMethodResult(
            method=self.name,
            candidates=center.reshape(1, 2),
            scores=np.zeros(1),
            selected_index=0,
            diagnostics={"used_mean_fallback": degenerate},
        )


__all__ = ["MassCenter"]
