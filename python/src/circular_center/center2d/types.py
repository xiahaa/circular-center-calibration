# SPDX-License-Identifier: Apache-2.0
"""Public result types for projected circular-center estimation."""

from dataclasses import dataclass
from enum import Enum

import numpy as np


class ProjectedCenterStatus(str, Enum):
    SUCCESS = "success"
    AMBIGUOUS = "ambiguous"
    INVALID_INPUT = "invalid_input"
    NUMERICAL_FAILURE = "numerical_failure"


class ProjectedCenterError(ValueError):
    def __init__(self, status: ProjectedCenterStatus, message: str):
        super().__init__(message)
        self.status = ProjectedCenterStatus(status)


@dataclass(frozen=True)
class ProjectedCenterResult:
    """Two geometry-derived candidates plus score and search diagnostics."""

    candidates: np.ndarray
    scores: np.ndarray
    confidence: float
    ambiguous: bool
    score_gap: float
    evaluations: int
    directions: int
    status: ProjectedCenterStatus
    elapsed_seconds: float

    @property
    def primary(self) -> np.ndarray:
        return self.candidates[0]

    @property
    def alternative(self) -> np.ndarray:
        return self.candidates[1]


__all__ = [
    "ProjectedCenterError",
    "ProjectedCenterResult",
    "ProjectedCenterStatus",
]
