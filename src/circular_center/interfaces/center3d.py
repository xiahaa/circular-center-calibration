"""Contracts shared by 3D circle-measurement methods."""

from typing import Protocol

import numpy as np

from circular_center.center3d import CircleFitResult


class Center3DMethod(Protocol):
    """Protocol implemented by interchangeable paper 3D methods."""

    name: str

    def fit(self, points: np.ndarray) -> CircleFitResult:
        ...


__all__ = ["Center3DMethod"]
