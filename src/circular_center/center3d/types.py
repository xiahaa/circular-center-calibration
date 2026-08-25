# SPDX-License-Identifier: Apache-2.0
"""Public status, exception, and result types for 3D circle fitting."""

from dataclasses import dataclass
from enum import Enum

import numpy as np


class FitStatus(str, Enum):
    """Machine-readable outcome categories shared by fitting methods."""

    SUCCESS = "success"
    INVALID_INPUT = "invalid_input"
    DEGENERATE = "degenerate"
    NUMERICAL_FAILURE = "numerical_failure"
    NO_CONSENSUS = "no_consensus"


class CircleFitError(ValueError):
    """Raised when a Python circle fit cannot return a valid result."""

    def __init__(self, status: FitStatus, message: str):
        super().__init__(message)
        self.status = FitStatus(status)


@dataclass(frozen=True)
class CircleFitResult:
    """Method-independent result with residuals and reproducibility metadata."""

    method: str
    center: np.ndarray
    radius: float
    normal: np.ndarray
    residuals: np.ndarray
    inlier_mask: np.ndarray
    status: FitStatus = FitStatus.SUCCESS
    condition_number: float = float("nan")
    iterations: int = 1
    elapsed_seconds: float = float("nan")

    @property
    def rmse(self) -> float:
        if self.residuals.size == 0:
            return float("nan")
        return float(np.sqrt(np.mean(np.square(self.residuals))))

    @property
    def inlier_rmse(self) -> float:
        selected = self.residuals[self.inlier_mask]
        if selected.size == 0:
            return float("nan")
        return float(np.sqrt(np.mean(np.square(selected))))


__all__ = ["CircleFitError", "CircleFitResult", "FitStatus"]
