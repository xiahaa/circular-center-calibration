"""Render rectified images with measured centers and LiDAR projections."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Optional

import cv2
import numpy as np


def _color(config: Mapping[str, object], name: str) -> tuple[int, int, int]:
    values = config["colors_bgr"][name]
    return tuple(int(value) for value in values)


def _project(
    points: np.ndarray,
    rotation: np.ndarray,
    translation: np.ndarray,
    intrinsic: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    camera = (rotation @ np.asarray(points, dtype=float).T).T + np.asarray(
        translation, dtype=float
    ).reshape(1, 3)
    visible = camera[:, 2] > np.finfo(float).eps
    projected = np.empty((len(camera), 2), dtype=float)
    projected.fill(np.nan)
    homogeneous = (intrinsic @ camera[visible].T).T
    projected[visible] = homogeneous[:, :2] / homogeneous[:, 2, None]
    return projected, visible


def _draw_projected_cloud(
    canvas: np.ndarray,
    points: np.ndarray,
    intensity: np.ndarray,
    rotation: np.ndarray,
    translation: np.ndarray,
    intrinsic: np.ndarray,
    draw: Mapping[str, object],
) -> None:
    points = np.asarray(points, dtype=float)
    intensity = np.asarray(intensity, dtype=float).reshape(-1)
    if len(points) != len(intensity):
        raise ValueError("point-cloud points and intensity must have the same length")

    maximum = int(draw["maximum_projected_points"])
    stride = max(1, int(np.ceil(len(points) / maximum)))
    points = points[::stride]
    intensity = intensity[::stride]
    projected, visible = _project(points, rotation, translation, intrinsic)
    height, width = canvas.shape[:2]
    inside = (
        visible
        & (projected[:, 0] >= 0.0)
        & (projected[:, 0] < width)
        & (projected[:, 1] >= 0.0)
        & (projected[:, 1] < height)
    )
    pixels = np.rint(projected[inside]).astype(int)
    if len(pixels) == 0:
        return

    minimum, maximum = (float(value) for value in draw["intensity_range"])
    scaled = np.clip((intensity[inside] - minimum) / (maximum - minimum), 0.0, 1.0)
    colors = cv2.applyColorMap(
        np.rint(255.0 * scaled).astype(np.uint8).reshape(-1, 1),
        cv2.COLORMAP_JET,
    ).reshape(-1, 3)
    overlay = canvas.copy()
    radius = int(draw["projected_point_radius_px"])
    for pixel, color in zip(pixels, colors):
        cv2.circle(
            overlay,
            tuple(pixel),
            radius,
            tuple(int(value) for value in color),
            -1,
            cv2.LINE_AA,
        )
    opacity = float(draw["projected_point_opacity"])
    cv2.addWeighted(overlay, opacity, canvas, 1.0 - opacity, 0.0, canvas)


def _draw_label(canvas: np.ndarray, lines: list[str], draw: Mapping[str, object]) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = float(draw["label_font_scale"])
    thickness = int(draw["label_thickness_px"])
    padding = int(draw["label_padding_px"])
    line_gap = int(draw["label_line_gap_px"])
    sizes = [cv2.getTextSize(line, font, scale, thickness)[0] for line in lines]
    line_height = max(height for _, height in sizes)
    panel_width = max(width for width, _ in sizes) + 2 * padding
    panel_height = len(lines) * line_height + (len(lines) - 1) * line_gap + 2 * padding
    left, top = 12, 12
    overlay = canvas.copy()
    cv2.rectangle(
        overlay,
        (left, top),
        (left + panel_width, top + panel_height),
        (15, 15, 15),
        -1,
    )
    opacity = float(draw["label_background_opacity"])
    cv2.addWeighted(overlay, opacity, canvas, 1.0 - opacity, 0.0, canvas)
    baseline_y = top + padding + line_height
    for index, line in enumerate(lines):
        cv2.putText(
            canvas,
            line,
            (left + padding, baseline_y + index * (line_height + line_gap)),
            font,
            scale,
            (245, 245, 245),
            thickness,
            cv2.LINE_AA,
        )


def render_qualitative_frame(
    image: np.ndarray,
    *,
    intrinsic: np.ndarray,
    distortion: np.ndarray,
    rectified_cv_ellipse: tuple,
    candidates: np.ndarray,
    selected_center: np.ndarray,
    center3d: np.ndarray,
    circle_radius_m: float,
    point_cloud_points: np.ndarray,
    point_cloud_intensity: np.ndarray,
    methods: Mapping[str, Optional[str]],
    destination: Path,
    config: Mapping[str, object],
    rotation: Optional[np.ndarray] = None,
    translation: Optional[np.ndarray] = None,
    calibration_inlier: Optional[bool] = None,
) -> Optional[float]:
    canvas = cv2.undistort(image, intrinsic, distortion, None, intrinsic)
    draw = config["draw"]

    reprojection_error = None
    if rotation is not None and translation is not None:
        _draw_projected_cloud(
            canvas,
            point_cloud_points,
            point_cloud_intensity,
            rotation,
            translation,
            intrinsic,
            draw,
        )

    cv2.ellipse(
        canvas,
        rectified_cv_ellipse,
        _color(config, "ellipse"),
        int(draw["ellipse_thickness_px"]),
        cv2.LINE_AA,
    )
    for candidate in np.asarray(candidates, dtype=float):
        cv2.circle(
            canvas,
            tuple(np.rint(candidate).astype(int)),
            int(draw["center_radius_px"]),
            _color(config, "candidate"),
            1,
            cv2.LINE_AA,
        )
    selected_pixel = tuple(np.rint(selected_center).astype(int))
    cv2.circle(
        canvas,
        selected_pixel,
        int(draw["center_radius_px"]),
        _color(config, "selected_center"),
        -1,
        cv2.LINE_AA,
    )

    if rotation is not None and translation is not None:
        projected_center, center_visible = _project(
            np.asarray(center3d).reshape(1, 3), rotation, translation, intrinsic
        )
        if center_visible[0]:
            lidar_pixel = tuple(np.rint(projected_center[0]).astype(int))
            cv2.drawMarker(
                canvas,
                lidar_pixel,
                _color(config, "projected_3d_center"),
                cv2.MARKER_CROSS,
                14,
                2,
                cv2.LINE_AA,
            )
            cv2.line(
                canvas,
                selected_pixel,
                lidar_pixel,
                _color(config, "projected_3d_center"),
                1,
                cv2.LINE_AA,
            )
            reprojection_error = float(np.linalg.norm(projected_center[0] - selected_center))

    method_line = " + ".join(
        methods[name] for name in ("2d", "3d", "ambiguity") if methods.get(name)
    )
    metric_line = "radius={:.3f} m".format(circle_radius_m)
    if reprojection_error is not None:
        metric_line += " | reprojection={:.2f} px".format(reprojection_error)
    if calibration_inlier is not None:
        metric_line += " | {}".format("inlier" if calibration_inlier else "outlier")
    _draw_label(canvas, [method_line, metric_line], draw)
    destination.parent.mkdir(parents=True, exist_ok=True)
    extension = destination.suffix or ".png"
    success, encoded = cv2.imencode(extension, canvas)
    if not success:
        raise OSError("failed to write {}".format(destination))
    try:
        encoded.tofile(destination)
    except OSError as error:
        raise OSError("failed to write {}: {}".format(destination, error)) from error
    return reprojection_error


__all__ = ["render_qualitative_frame"]
