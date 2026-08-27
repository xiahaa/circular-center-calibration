"""Experiment-specific image preprocessing for the red calibration board."""

from typing import Mapping

import numpy as np

from .aamed_ellipse import AAMEDUnavailableError, detect_aamed_ellipse
from .red_board_ellipse import DetectedTarget, detect_red_board_ellipse


def detect_target_ellipse(
    image: np.ndarray,
    intrinsic: np.ndarray,
    distortion: np.ndarray,
    distortion_model: str,
    config: Mapping[str, object],
) -> DetectedTarget:
    """Dispatch to the experiment-configured ellipse detector."""

    backend = str(config.get("backend", "opencv_red_board"))
    if backend == "aamed":
        return detect_aamed_ellipse(
            image, intrinsic, distortion, distortion_model, config
        )
    if backend == "opencv_red_board":
        return detect_red_board_ellipse(
            image, intrinsic, distortion, distortion_model, config
        )
    raise ValueError("unknown 2D detection backend {!r}".format(backend))


__all__ = [
    "AAMEDUnavailableError",
    "DetectedTarget",
    "detect_aamed_ellipse",
    "detect_red_board_ellipse",
    "detect_target_ellipse",
]
