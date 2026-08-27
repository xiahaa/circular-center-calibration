"""AAMED-backed ellipse detection for the real-world calibration target."""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import cv2
import numpy as np

from circular_center.center2d import get_ellipse_polynomial_coeff

from .red_board_ellipse import DetectedTarget, _red_mask


class AAMEDUnavailableError(RuntimeError):
    """Raised when the optional external AAMED extension cannot be imported."""


@dataclass(frozen=True)
class _Candidate:
    ellipse: tuple
    detector_score: float
    red_annulus_fraction: float
    neutral_interior_fraction: float
    selection_score: float
    board_area_px2: float
    circle_area_px2: float
    axis_ratio: float


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_aamed(config: Mapping[str, object]):
    module_name = str(config.get("module", "pyAAMED"))
    search_paths = config.get("module_search_paths", ["thirdparty/AAMED/python"])
    if not isinstance(search_paths, list):
        raise ValueError("aamed.module_search_paths must be a list")
    for entry in reversed(search_paths):
        path = Path(str(entry)).expanduser()
        if not path.is_absolute():
            path = _repository_root() / path
        if path.is_dir() and str(path) not in sys.path:
            sys.path.insert(0, str(path))
    try:
        module = importlib.import_module(module_name)
    except ImportError as error:
        raise AAMEDUnavailableError(
            "AAMED is not available; run `python tools/build_aamed.py` from the "
            "repository root"
        ) from error
    detector_class = getattr(module, "pyAAMED", None)
    if detector_class is None:
        raise AAMEDUnavailableError(
            "{} does not expose the official pyAAMED class".format(module_name)
        )
    return detector_class


def _ellipse_mask(shape: tuple, ellipse: tuple, scale: float) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    center = tuple(int(round(value)) for value in ellipse[0])
    axes = tuple(max(1, int(round(float(value) * scale))) for value in ellipse[1])
    cv2.ellipse(mask, (center, axes, float(ellipse[2])), 255, -1, cv2.LINE_8)
    return mask.astype(bool)


def _board_component_area(red_mask: np.ndarray, annulus: np.ndarray) -> float:
    count, labels, statistics, _ = cv2.connectedComponentsWithStats(
        red_mask.astype(np.uint8), connectivity=8
    )
    if count <= 1:
        return 0.0
    overlap = labels[annulus & red_mask]
    overlap = overlap[overlap > 0]
    if len(overlap) == 0:
        return 0.0
    component = int(np.bincount(overlap, minlength=count).argmax())
    return float(statistics[component, cv2.CC_STAT_AREA])


def _sample_ellipse(ellipse: tuple, sample_count: int) -> np.ndarray:
    if sample_count < 5:
        raise ValueError("aamed.contour_samples must be at least five")
    angles = np.linspace(0.0, 2.0 * np.pi, sample_count, endpoint=False)
    local = np.column_stack(
        (
            0.5 * float(ellipse[1][0]) * np.cos(angles),
            0.5 * float(ellipse[1][1]) * np.sin(angles),
        )
    )
    rotation_angle = np.deg2rad(float(ellipse[2]))
    cosine, sine = np.cos(rotation_angle), np.sin(rotation_angle)
    rotation = np.array([[cosine, -sine], [sine, cosine]])
    return local @ rotation.T + np.asarray(ellipse[0], dtype=float)


def _convert_aamed_ellipse(raw: np.ndarray) -> tuple:
    # The official Python binding exposes the detector's row/column coordinate
    # convention.  Convert it to OpenCV's (x, y), (width, height), angle form.
    return (
        (float(raw[1]), float(raw[0])),
        (float(raw[3]), float(raw[2])),
        float(-raw[4]),
    )


def _candidate_from_raw(
    raw: np.ndarray,
    image: np.ndarray,
    red_mask: np.ndarray,
    candidate_config: Mapping[str, object],
    aamed_config: Mapping[str, object],
) -> _Candidate | None:
    ellipse = _convert_aamed_ellipse(raw)
    first_axis, second_axis = (float(value) for value in ellipse[1])
    if first_axis <= 0.0 or second_axis <= 0.0:
        return None
    circle_area = float(np.pi * first_axis * second_axis / 4.0)
    axis_ratio = min(first_axis, second_axis) / max(first_axis, second_axis)
    detector_score = float(raw[5])
    if circle_area < float(candidate_config["minimum_hole_area_px2"]):
        return None
    if axis_ratio < float(candidate_config["minimum_axis_ratio"]):
        return None
    if detector_score < float(aamed_config["minimum_detector_score"]):
        return None

    inner_annulus = _ellipse_mask(
        image.shape[:2], ellipse, float(aamed_config["annulus_inner_scale"])
    )
    outer_annulus = _ellipse_mask(
        image.shape[:2], ellipse, float(aamed_config["annulus_outer_scale"])
    )
    annulus = outer_annulus & ~inner_annulus
    if not np.any(annulus):
        return None
    red_annulus_fraction = float(np.mean(red_mask[annulus]))

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    interior = _ellipse_mask(
        image.shape[:2], ellipse, float(aamed_config["interior_scale"])
    )
    neutral = (
        (hsv[:, :, 1] <= int(aamed_config["maximum_neutral_saturation"]))
        & (hsv[:, :, 2] >= int(aamed_config["minimum_neutral_value"]))
    )
    neutral_interior_fraction = float(np.mean(neutral[interior]))
    if red_annulus_fraction < float(aamed_config["minimum_red_annulus_fraction"]):
        return None
    if neutral_interior_fraction < float(
        aamed_config["minimum_neutral_interior_fraction"]
    ):
        return None

    weights = aamed_config["selection_weights"]
    if not isinstance(weights, Mapping):
        raise ValueError("aamed.selection_weights must be a mapping")
    selection_score = (
        float(weights["detector"]) * detector_score
        + float(weights["red_annulus"]) * red_annulus_fraction
        + float(weights["neutral_interior"]) * neutral_interior_fraction
    )
    return _Candidate(
        ellipse=ellipse,
        detector_score=detector_score,
        red_annulus_fraction=red_annulus_fraction,
        neutral_interior_fraction=neutral_interior_fraction,
        selection_score=selection_score,
        board_area_px2=_board_component_area(red_mask, annulus),
        circle_area_px2=circle_area,
        axis_ratio=axis_ratio,
    )


def detect_aamed_ellipse(
    image: np.ndarray,
    intrinsic: np.ndarray,
    distortion: np.ndarray,
    distortion_model: str,
    config: Mapping[str, object],
) -> DetectedTarget:
    """Detect and rank AAMED ellipses in rectified image space."""

    if image is None or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("image must be a BGR array")
    if distortion_model not in {"plumb_bob", "rational_polynomial"}:
        raise ValueError("unsupported camera distortion model {!r}".format(distortion_model))
    mask_config = config["red_mask"]
    candidate_config = config["ellipse_candidate"]
    aamed_config = config["aamed"]
    if not all(
        isinstance(item, Mapping)
        for item in (mask_config, candidate_config, aamed_config)
    ):
        raise ValueError("invalid AAMED detection configuration")

    rectified_image = cv2.undistort(
        image, intrinsic, distortion, None, intrinsic
    )
    grayscale = np.ascontiguousarray(
        cv2.cvtColor(rectified_image, cv2.COLOR_BGR2GRAY), dtype=np.uint8
    )
    detector_class = _load_aamed(aamed_config)
    detector = detector_class(grayscale.shape[0] + 1, grayscale.shape[1] + 1)
    try:
        detector.setParameters(
            float(aamed_config["theta_fsa_rad"]),
            float(aamed_config["minimum_arc_length"]),
            float(aamed_config["validation_threshold"]),
        )
        raw_results = detector.run_AAMED(grayscale)
    finally:
        detector.release()

    raw_results = np.asarray(raw_results, dtype=float)
    if raw_results.size == 0:
        raise ValueError("AAMED found no ellipse candidates")
    if raw_results.ndim != 2 or raw_results.shape[1] != 6:
        raise RuntimeError("AAMED returned an unexpected result shape")
    red_mask = _red_mask(rectified_image, mask_config) > 0
    candidates = [
        candidate
        for raw in raw_results
        if (
            candidate := _candidate_from_raw(
                raw,
                rectified_image,
                red_mask,
                candidate_config,
                aamed_config,
            )
        )
        is not None
    ]
    if not candidates:
        raise ValueError("no AAMED ellipse matches the red calibration target")
    selected = max(candidates, key=lambda candidate: candidate.selection_score)
    contour = _sample_ellipse(
        selected.ellipse, int(aamed_config["contour_samples"])
    )
    ellipse = np.array(
        [
            selected.ellipse[0][0],
            selected.ellipse[0][1],
            selected.ellipse[1][0] / 2.0,
            selected.ellipse[1][1] / 2.0,
            np.deg2rad(selected.ellipse[2]),
        ],
        dtype=float,
    )
    return DetectedTarget(
        ellipse=ellipse,
        polynomial=get_ellipse_polynomial_coeff(selected.ellipse),
        rectified_contour=contour,
        rectified_cv_ellipse=selected.ellipse,
        board_area_px2=selected.board_area_px2,
        circle_area_px2=selected.circle_area_px2,
        axis_ratio=selected.axis_ratio,
        detector="aamed",
        detector_score=selected.detector_score,
        red_annulus_fraction=selected.red_annulus_fraction,
        neutral_interior_fraction=selected.neutral_interior_fraction,
    )


__all__ = ["AAMEDUnavailableError", "detect_aamed_ellipse"]
