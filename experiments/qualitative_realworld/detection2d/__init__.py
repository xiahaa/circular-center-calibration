"""Experiment-specific image preprocessing for the red calibration board."""

from .red_board_ellipse import (
    DetectedTarget,
    detect_target_ellipse,
    detected_target_from_raw_ellipse,
)

__all__ = [
    "DetectedTarget",
    "detect_target_ellipse",
    "detected_target_from_raw_ellipse",
]
