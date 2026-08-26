"""Detect the bright circular insert as a hole in the red board mask."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

import cv2
import numpy as np

from circular_center.center2d import get_ellipse_polynomial_coeff, rectify_contour


@dataclass(frozen=True)
class DetectedTarget:
    ellipse: np.ndarray
    polynomial: np.ndarray
    rectified_contour: np.ndarray
    raw_cv_ellipse: tuple
    rectified_cv_ellipse: tuple
    board_area_px2: float
    circle_area_px2: float
    axis_ratio: float
    proposal_source: str


def _red_mask(image: np.ndarray, config: Mapping[str, object]) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, saturation, value = cv2.split(hsv)
    mask = (
        ((hue <= int(config["low_hue_max"])) | (hue >= int(config["high_hue_min"])))
        & (saturation >= int(config["minimum_saturation"]))
        & (value >= int(config["minimum_value"]))
    )
    kernel_size = int(config["close_kernel_px"])
    if kernel_size < 1 or kernel_size % 2 == 0:
        raise ValueError("close_kernel_px must be a positive odd integer")
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    return cv2.morphologyEx(
        mask.astype(np.uint8) * 255,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=int(config["close_iterations"]),
    )


def _candidate_score(
    circle_area: float,
    axis_ratio: float,
    area_ratio: float,
    preferred_ratio: float,
    ratio_score_width: float,
) -> float:
    ratio_likelihood = float(
        np.exp(-0.5 * ((area_ratio - preferred_ratio) / ratio_score_width) ** 2)
    )
    return float(np.sqrt(circle_area) * axis_ratio * axis_ratio * ratio_likelihood)


def _ellipse_points(raw_ellipse: tuple, scale: float, count: int = 180) -> np.ndarray:
    """Return uniformly sampled raw-image points on an OpenCV ellipse."""

    (center_x, center_y), (width, height), angle_degrees = raw_ellipse
    angles = np.linspace(0.0, 2.0 * np.pi, count, endpoint=False)
    local = np.column_stack(
        [
            0.5 * float(width) * float(scale) * np.cos(angles),
            0.5 * float(height) * float(scale) * np.sin(angles),
        ]
    )
    angle = np.deg2rad(float(angle_degrees))
    rotation = np.array(
        [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]],
        dtype=float,
    )
    return local @ rotation.T + np.array([center_x, center_y], dtype=float)


def _sample_image(values: np.ndarray, points: np.ndarray) -> np.ndarray:
    rounded = np.rint(points).astype(int)
    valid = (
        (rounded[:, 0] >= 0)
        & (rounded[:, 0] < values.shape[1])
        & (rounded[:, 1] >= 0)
        & (rounded[:, 1] < values.shape[0])
    )
    if not np.any(valid):
        return np.empty(0, dtype=values.dtype)
    return values[rounded[valid, 1], rounded[valid, 0]]


def _arc_candidate_score(
    raw_ellipse: tuple,
    red_mask: np.ndarray,
    hsv: np.ndarray,
    edge_distance: np.ndarray,
) -> tuple[float, float, float, float]:
    """Score a partial-arc ellipse by board, insert, and edge support."""

    outer_red_samples = np.concatenate(
        [
            _sample_image(red_mask, _ellipse_points(raw_ellipse, scale))
            for scale in (1.10, 1.20, 1.30)
        ]
    )
    red_support = (
        0.0
        if len(outer_red_samples) == 0
        else float(np.mean(outer_red_samples > 0))
    )

    inner_points = np.vstack(
        [_ellipse_points(raw_ellipse, scale) for scale in (0.0, 0.35, 0.65)]
    )
    inner_hsv = _sample_image(hsv, inner_points)
    if len(inner_hsv) == 0:
        insert_support = 0.0
    else:
        insert_support = float(
            np.mean((inner_hsv[:, 1] <= 90) & (inner_hsv[:, 2] >= 75))
        )

    boundary_distance = _sample_image(
        edge_distance, _ellipse_points(raw_ellipse, 1.0)
    )
    edge_support = (
        0.0
        if len(boundary_distance) == 0
        else float(np.mean(boundary_distance <= 2.5))
    )
    width, height = (float(value) for value in raw_ellipse[1])
    axis_ratio = min(width, height) / max(width, height)
    area = np.pi * width * height / 4.0
    score = (
        np.sqrt(area)
        * axis_ratio**2
        * red_support**2
        * np.sqrt(max(insert_support, 0.0))
        * np.sqrt(max(edge_support, 0.0))
    )
    return float(score), red_support, insert_support, edge_support


def _detect_occluded_arc(
    image: np.ndarray,
    red_mask: np.ndarray,
    candidate_config: Mapping[str, object],
) -> tuple[tuple, np.ndarray, float, float, float]:
    """Fit the visible part of an insert when a privacy mask breaks its contour.

    This fallback uses only OpenCV. It is deliberately activated only if the
    topology-based red-board detector has no valid candidate, so intact frames
    retain the original deterministic measurement path.
    """

    arc_config = candidate_config.get("occluded_arc_fallback", {})
    if not isinstance(arc_config, Mapping) or not bool(arc_config.get("enabled", True)):
        raise ValueError("no ellipse-shaped hole was found inside the red board")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0.0)
    edges = cv2.Canny(
        blurred,
        int(arc_config.get("canny_low", 40)),
        int(arc_config.get("canny_high", 120)),
    )
    edge_distance = cv2.distanceTransform(255 - edges, cv2.DIST_L2, 3)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    minimum_axis = float(arc_config.get("minimum_axis_px", 20.0))
    maximum_axis = float(arc_config.get("maximum_axis_px", 260.0))
    minimum_red_support = float(arc_config.get("minimum_red_support", 0.20))
    minimum_insert_support = float(
        arc_config.get("minimum_insert_support", 0.20)
    )
    minimum_edge_support = float(arc_config.get("minimum_edge_support", 0.10))
    minimum_contour_points = int(arc_config.get("minimum_contour_points", 20))
    minimum_axis_ratio = float(candidate_config["minimum_axis_ratio"])

    candidates = []

    def add_candidate(raw_ellipse: tuple) -> None:
        values = np.asarray(
            [*raw_ellipse[0], *raw_ellipse[1], raw_ellipse[2]], dtype=float
        )
        if not np.all(np.isfinite(values)):
            return
        width, height = (float(value) for value in raw_ellipse[1])
        if min(width, height) < minimum_axis or max(width, height) > maximum_axis:
            return
        axis_ratio = min(width, height) / max(width, height)
        if axis_ratio < minimum_axis_ratio:
            return
        score, red_support, insert_support, edge_support = _arc_candidate_score(
            raw_ellipse, red_mask, hsv, edge_distance
        )
        if red_support < minimum_red_support:
            return
        if insert_support < minimum_insert_support:
            return
        if edge_support < minimum_edge_support:
            return
        candidates.append(
            (
                score,
                raw_ellipse,
                axis_ratio,
                red_support,
                insert_support,
                edge_support,
            )
        )

    for contour in contours:
        if len(contour) < minimum_contour_points:
            continue
        for fitter in (cv2.fitEllipse, cv2.fitEllipseAMS, cv2.fitEllipseDirect):
            try:
                raw_ellipse = fitter(contour)
            except cv2.error:
                continue
            add_candidate(raw_ellipse)

    # A rectangular face mask can split the insert boundary into several arcs.
    # In that case no individual Canny contour spans enough of the ellipse for
    # a stable direct fit. Reconstruct the board support from the convex hull of
    # its largest red component and fit deterministic five-point hypotheses to
    # the interior edge pixels. The fixed local generator avoids OpenCV/global
    # RNG state and makes this path reproducible across repeated runs.
    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(
        (red_mask > 0).astype(np.uint8)
    )
    board_edge_points = np.empty((0, 2), dtype=np.float32)
    board_hull_mask = np.zeros(red_mask.shape, dtype=np.uint8)
    board_axis_limit = maximum_axis
    if component_count > 1:
        board_label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        component = (labels == board_label).astype(np.uint8) * 255
        component_contours, _ = cv2.findContours(
            component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
        )
        if component_contours:
            hull = cv2.convexHull(max(component_contours, key=cv2.contourArea))
            cv2.fillConvexPoly(board_hull_mask, hull, 255)
            erosion_px = int(arc_config.get("board_hull_erosion_px", 9))
            if erosion_px < 1 or erosion_px % 2 == 0:
                raise ValueError("board_hull_erosion_px must be a positive odd integer")
            inner_hull = cv2.erode(
                board_hull_mask, np.ones((erosion_px, erosion_px), dtype=np.uint8)
            )
            rows, columns = np.where((edges > 0) & (inner_hull > 0))
            board_edge_points = np.column_stack([columns, rows]).astype(np.float32)
            board_axis_limit = min(
                maximum_axis,
                1.2
                * max(
                    float(stats[board_label, cv2.CC_STAT_WIDTH]),
                    float(stats[board_label, cv2.CC_STAT_HEIGHT]),
                ),
            )

    ransac_iterations = int(arc_config.get("ransac_iterations", 5000))
    if len(board_edge_points) >= 5 and ransac_iterations > 0:
        generator = np.random.default_rng(int(arc_config.get("seed", 2025)))
        for _ in range(ransac_iterations):
            sample = board_edge_points[
                generator.choice(len(board_edge_points), 5, replace=False)
            ]
            try:
                raw_ellipse = cv2.fitEllipseDirect(sample.reshape(-1, 1, 2))
            except cv2.error:
                continue
            center_x, center_y = (float(value) for value in raw_ellipse[0])
            if not (0 <= center_x < image.shape[1] and 0 <= center_y < image.shape[0]):
                continue
            center_column = min(image.shape[1] - 1, int(round(center_x)))
            center_row = min(image.shape[0] - 1, int(round(center_y)))
            if board_hull_mask[center_row, center_column] == 0:
                continue
            if max(float(value) for value in raw_ellipse[1]) > board_axis_limit:
                continue
            add_candidate(raw_ellipse)

    if not candidates:
        raise ValueError(
            "no ellipse-shaped hole or supported partial ellipse was found inside the red board"
        )
    _, raw_ellipse, axis_ratio, _, _, _ = max(
        candidates, key=lambda candidate: candidate[0]
    )

    def point_to_ellipse_distance(points: np.ndarray, ellipse: tuple) -> np.ndarray:
        (center_x, center_y), (width, height), angle_degrees = ellipse
        centered = points - np.array([center_x, center_y], dtype=float)
        angle = np.deg2rad(float(angle_degrees))
        local_x = centered[:, 0] * np.cos(angle) + centered[:, 1] * np.sin(angle)
        local_y = -centered[:, 0] * np.sin(angle) + centered[:, 1] * np.cos(angle)
        normalized_radius = np.sqrt(
            (local_x / (0.5 * float(width))) ** 2
            + (local_y / (0.5 * float(height))) ** 2
        )
        return np.abs(normalized_radius - 1.0) * 0.5 * min(width, height)

    refinement_passes = int(arc_config.get("refinement_passes", 4))
    inlier_distance = float(arc_config.get("inlier_distance_px", 2.5))
    for _ in range(refinement_passes):
        if len(board_edge_points) < 5:
            break
        residuals = point_to_ellipse_distance(board_edge_points, raw_ellipse)
        inlier_points = board_edge_points[residuals <= inlier_distance]
        if len(inlier_points) < 5:
            break
        try:
            refined = cv2.fitEllipseAMS(inlier_points.reshape(-1, 1, 2))
        except cv2.error:
            break
        refined_values = np.asarray(
            [*refined[0], *refined[1], refined[2]], dtype=float
        )
        if not np.all(np.isfinite(refined_values)):
            break
        raw_ellipse = refined

    width, height = (float(value) for value in raw_ellipse[1])
    axis_ratio = min(width, height) / max(width, height)
    raw_contour = _ellipse_points(raw_ellipse, 1.0, count=360)
    circle_area = float(np.pi * width * height / 4.0)
    preferred_ratio = float(candidate_config["preferred_hole_to_board_area_ratio"])
    board_area = circle_area / preferred_ratio
    return raw_ellipse, raw_contour, board_area, circle_area, axis_ratio


def detected_target_from_raw_ellipse(
    raw_ellipse: tuple,
    intrinsic: np.ndarray,
    distortion: np.ndarray,
    distortion_model: str,
    *,
    proposal_source: str = "precomputed",
    raw_contour: Optional[np.ndarray] = None,
    board_area_px2: Optional[float] = None,
) -> DetectedTarget:
    """Create a rectified target from an external raw-image ellipse proposal."""

    if distortion_model not in {"plumb_bob", "rational_polynomial"}:
        raise ValueError("unsupported camera distortion model {!r}".format(distortion_model))
    width, height = (float(value) for value in raw_ellipse[1])
    if width <= 0.0 or height <= 0.0:
        raise ValueError("ellipse axes must be positive")
    if raw_contour is None:
        raw_contour = _ellipse_points(raw_ellipse, 1.0, count=360)
    raw_contour = np.asarray(raw_contour, dtype=float).reshape(-1, 2)
    if len(raw_contour) < 5:
        raise ValueError("ellipse contour must contain at least five points")
    rectified, _ = rectify_contour(
        raw_contour,
        intrinsic,
        distortion,
        model="pinhole",
        rectified_K=intrinsic,
    )
    rectified_cv_ellipse = cv2.fitEllipse(
        rectified.astype(np.float32).reshape(-1, 1, 2)
    )
    ellipse = np.array(
        [
            rectified_cv_ellipse[0][0],
            rectified_cv_ellipse[0][1],
            rectified_cv_ellipse[1][0] / 2.0,
            rectified_cv_ellipse[1][1] / 2.0,
            np.deg2rad(rectified_cv_ellipse[2]),
        ],
        dtype=float,
    )
    circle_area = float(np.pi * width * height / 4.0)
    return DetectedTarget(
        ellipse=ellipse,
        polynomial=get_ellipse_polynomial_coeff(rectified_cv_ellipse),
        rectified_contour=rectified,
        raw_cv_ellipse=raw_ellipse,
        rectified_cv_ellipse=rectified_cv_ellipse,
        board_area_px2=(
            circle_area if board_area_px2 is None else float(board_area_px2)
        ),
        circle_area_px2=circle_area,
        axis_ratio=min(width, height) / max(width, height),
        proposal_source=str(proposal_source),
    )


def detect_target_ellipse(
    image: np.ndarray,
    intrinsic: np.ndarray,
    distortion: np.ndarray,
    distortion_model: str,
    config: Mapping[str, object],
) -> DetectedTarget:
    if image is None or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("image must be a BGR array")
    mask_config = config["red_mask"]
    candidate_config = config["ellipse_candidate"]
    if not isinstance(mask_config, Mapping) or not isinstance(candidate_config, Mapping):
        raise ValueError("invalid 2D detection configuration")
    red_mask = _red_mask(image, mask_config)
    contours, hierarchy = cv2.findContours(
        red_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE
    )
    hierarchy_rows = None if hierarchy is None else hierarchy[0]
    ratio_min, ratio_max = (
        float(value) for value in candidate_config["hole_to_board_area_ratio"]
    )
    preferred_ratio = float(
        candidate_config["preferred_hole_to_board_area_ratio"]
    )
    ratio_score_width = float(candidate_config["area_ratio_score_width"])
    if ratio_score_width <= 0.0:
        raise ValueError("area_ratio_score_width must be positive")
    candidates = []
    for index, contour in enumerate(contours):
        if hierarchy_rows is None:
            break
        parent = int(hierarchy_rows[index, 3])
        if parent < 0 or len(contour) < 5:
            continue
        circle_area = abs(float(cv2.contourArea(contour)))
        board_area = abs(float(cv2.contourArea(contours[parent])))
        if circle_area < float(candidate_config["minimum_hole_area_px2"]):
            continue
        if board_area < float(candidate_config["minimum_board_area_px2"]):
            continue
        area_ratio = circle_area / board_area
        if not ratio_min <= area_ratio <= ratio_max:
            continue
        raw_ellipse = cv2.fitEllipse(contour)
        first_axis, second_axis = (float(value) for value in raw_ellipse[1])
        axis_ratio = min(first_axis, second_axis) / max(first_axis, second_axis)
        if axis_ratio < float(candidate_config["minimum_axis_ratio"]):
            continue
        score = _candidate_score(
            circle_area,
            axis_ratio,
            area_ratio,
            preferred_ratio,
            ratio_score_width,
        )
        candidates.append(
            (
                score,
                raw_ellipse,
                contour.reshape(-1, 2),
                board_area,
                circle_area,
                axis_ratio,
            )
        )
    if candidates:
        _, raw_ellipse, raw_contour, board_area, circle_area, axis_ratio = max(
            candidates, key=lambda candidate: candidate[0]
        )
        proposal_source = "hsv_hole"
    else:
        raw_ellipse, raw_contour, board_area, circle_area, axis_ratio = (
            _detect_occluded_arc(image, red_mask, candidate_config)
        )
        proposal_source = "opencv_partial_arc"

    return detected_target_from_raw_ellipse(
        raw_ellipse,
        intrinsic,
        distortion,
        distortion_model,
        proposal_source=proposal_source,
        raw_contour=raw_contour,
        board_area_px2=board_area,
    )


__all__ = [
    "DetectedTarget",
    "detect_target_ellipse",
    "detected_target_from_raw_ellipse",
]
