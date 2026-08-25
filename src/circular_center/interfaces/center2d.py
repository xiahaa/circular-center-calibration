"""Contracts shared by 2D center-measurement methods."""

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Protocol

import numpy as np


@dataclass(frozen=True)
class EllipseObservation:
    """A rectified ellipse observation consumed by 2D center methods."""

    ellipse: np.ndarray
    polynomial: np.ndarray
    intrinsic: np.ndarray
    marker_diameter: float
    contour: Optional[np.ndarray] = None
    input_is_rectified: bool = True

    def __post_init__(self) -> None:
        ellipse = np.asarray(self.ellipse, dtype=float).reshape(-1)
        polynomial = np.asarray(self.polynomial, dtype=float).reshape(-1)
        intrinsic = np.asarray(self.intrinsic, dtype=float)
        if ellipse.shape != (5,) or not np.isfinite(ellipse).all():
            raise ValueError(
                "ellipse must contain finite (cx, cy, semi_a, semi_b, angle_radians)"
            )
        if polynomial.shape != (6,) or not np.isfinite(polynomial).all():
            raise ValueError("polynomial must contain six finite conic coefficients")
        if intrinsic.shape != (3, 3) or not np.isfinite(intrinsic).all():
            raise ValueError("intrinsic must be a finite 3x3 matrix")
        if not np.isfinite(self.marker_diameter) or self.marker_diameter <= 0.0:
            raise ValueError("marker_diameter must be finite and positive")
        contour = None
        if self.contour is not None:
            contour = np.asarray(self.contour, dtype=float)
            if contour.ndim != 2 or contour.shape[1] != 2:
                raise ValueError("contour must have shape (N, 2)")
            if not np.isfinite(contour).all():
                raise ValueError("contour must be finite")
        object.__setattr__(self, "ellipse", ellipse)
        object.__setattr__(self, "polynomial", polynomial)
        object.__setattr__(self, "intrinsic", intrinsic)
        object.__setattr__(self, "contour", contour)
        object.__setattr__(self, "marker_diameter", float(self.marker_diameter))


@dataclass(frozen=True)
class Center2DMethodResult:
    """Method-independent 2D result supporting one or multiple candidates."""

    method: str
    candidates: np.ndarray
    scores: np.ndarray
    selected_index: Optional[int] = None
    status: str = "success"
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        candidates = np.asarray(self.candidates, dtype=float)
        scores = np.asarray(self.scores, dtype=float).reshape(-1)
        if candidates.ndim != 2 or candidates.shape[1] != 2 or len(candidates) == 0:
            raise ValueError("candidates must have shape (N, 2) with N >= 1")
        if scores.shape != (len(candidates),):
            raise ValueError("one score is required for every 2D candidate")
        if not np.isfinite(candidates).all():
            raise ValueError("2D candidates must be finite")
        if self.selected_index is not None and not 0 <= self.selected_index < len(candidates):
            raise ValueError("selected_index is outside the candidate array")
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "scores", scores)

    @property
    def primary(self) -> np.ndarray:
        index = 0 if self.selected_index is None else self.selected_index
        return self.candidates[index]


class Center2DMethod(Protocol):
    """Protocol implemented by interchangeable paper 2D methods."""

    name: str

    def estimate(self, observation: EllipseObservation) -> Center2DMethodResult:
        ...


__all__ = ["Center2DMethod", "Center2DMethodResult", "EllipseObservation"]
