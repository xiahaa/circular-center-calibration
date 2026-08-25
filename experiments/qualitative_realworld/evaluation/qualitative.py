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
    cluster_points: np.ndarray,
    methods: Mapping[str, str],
    destination: Path,
    config: Mapping[str, object],
    rotation: Optional[np.ndarray] = None,
    translation: Optional[np.ndarray] = None,
) -> Optional[float]:
    canvas = cv2.undistort(image, intrinsic, distortion, None, intrinsic)
    draw = config["draw"]
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

    reprojection_error = None
    if rotation is not None and translation is not None:
        maximum = int(draw["maximum_projected_cluster_points"])
        stride = max(1, int(np.ceil(len(cluster_points) / maximum)))
        projected_cluster, visible = _project(
            cluster_points[::stride], rotation, translation, intrinsic
        )
        height, width = canvas.shape[:2]
        inside = (
            visible
            & (projected_cluster[:, 0] >= 0.0)
            & (projected_cluster[:, 0] < width)
            & (projected_cluster[:, 1] >= 0.0)
            & (projected_cluster[:, 1] < height)
        )
        for pixel in projected_cluster[inside]:
            cv2.circle(
                canvas,
                tuple(np.rint(pixel).astype(int)),
                int(draw["projected_point_radius_px"]),
                _color(config, "projected_cluster"),
                -1,
            )
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

    label = "{} | {} | r={:.3f} m".format(
        methods["2d"], methods["3d"], circle_radius_m
    )
    if reprojection_error is not None:
        label += " | e={:.2f} px".format(reprojection_error)
    cv2.putText(
        canvas,
        label,
        (20, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        3,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        label,
        (20, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (20, 20, 20),
        1,
        cv2.LINE_AA,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(destination), canvas):
        raise OSError("failed to write {}".format(destination))
    return reprojection_error


__all__ = ["render_qualitative_frame"]
