# SPDX-License-Identifier: Apache-2.0
"""Deterministic confidence-driven quasi-RANSAC for two 2D branches."""

from dataclasses import dataclass
from enum import Enum
from time import perf_counter

import numpy as np


class QuasiRansacStatus(str, Enum):
    SUCCESS = "success"
    INVALID_INPUT = "invalid_input"
    NO_CONSENSUS = "no_consensus"
    POSE_FAILURE = "pose_failure"


class QuasiRansacError(RuntimeError):
    def __init__(self, status: QuasiRansacStatus, message: str):
        super().__init__(message)
        self.status = QuasiRansacStatus(status)


@dataclass(frozen=True)
class QuasiRansacResult:
    rotation: np.ndarray
    translation: np.ndarray
    mean_reprojection_error: float
    selected_points: np.ndarray
    inlier_mask: np.ndarray
    iterations: int
    iteration_limit: int
    confidence: float
    pose_failures: int
    status: QuasiRansacStatus
    elapsed_seconds: float


def quasi_ransac_iteration_bound(
    valid_correspondence_ratio: float,
    confidence: float = 0.99,
    sample_size: int = 4,
    maximum: int = 2000,
) -> int:
    """Return ceil(log(1-eta) / log(1-(q/2)^s))."""
    q = float(valid_correspondence_ratio)
    if not 0.0 <= q <= 1.0 or not 0.0 < confidence < 1.0:
        raise QuasiRansacError(
            QuasiRansacStatus.INVALID_INPUT,
            "q must be in [0, 1] and confidence in (0, 1)",
        )
    if sample_size <= 0 or maximum <= 0:
        raise QuasiRansacError(
            QuasiRansacStatus.INVALID_INPUT,
            "sample_size and maximum must be positive",
        )
    success_probability = (q / 2.0) ** sample_size
    if success_probability <= np.finfo(float).eps:
        return maximum
    required = int(
        np.ceil(np.log1p(-confidence) / np.log1p(-success_probability))
    )
    return min(maximum, max(1, required))


def _validate_inputs(p3, p2, p2_alt, K):
    p3 = np.asarray(p3, dtype=float)
    p2 = np.asarray(p2, dtype=float)
    p2_alt = np.asarray(p2_alt, dtype=float)
    intrinsic = np.asarray(K, dtype=float)
    if p3.ndim != 2 or p3.shape[1] != 3 or p3.shape[0] < 4:
        raise QuasiRansacError(
            QuasiRansacStatus.INVALID_INPUT,
            "p3 must have shape (N, 3) with N >= 4",
        )
    if p2.shape != (p3.shape[0], 2) or p2_alt.shape != p2.shape:
        raise QuasiRansacError(
            QuasiRansacStatus.INVALID_INPUT,
            "both 2D candidate arrays must have shape (N, 2)",
        )
    if intrinsic.shape != (3, 3):
        raise QuasiRansacError(
            QuasiRansacStatus.INVALID_INPUT,
            "K must have shape (3, 3)",
        )
    if not all(np.isfinite(array).all() for array in (p3, p2, p2_alt, intrinsic)):
        raise QuasiRansacError(
            QuasiRansacStatus.INVALID_INPUT,
            "quasi-RANSAC inputs must be finite",
        )
    return p3, p2, p2_alt, intrinsic


def _project(points, rotation, translation, intrinsic):
    camera = rotation @ points.T + np.asarray(translation, dtype=float).reshape(3, 1)
    if np.any(camera[2] <= np.finfo(float).eps):
        return None
    projected = intrinsic @ camera
    return (projected[:2] / projected[2]).T


def _branch_errors(projected, candidate_a, candidate_b):
    error_a = np.linalg.norm(projected - candidate_a, axis=1)
    error_b = np.linalg.norm(projected - candidate_b, axis=1)
    choose_a = error_a <= error_b
    errors = np.where(choose_a, error_a, error_b)
    selected = np.where(choose_a[:, None], candidate_a, candidate_b)
    return errors, selected


def _recover_pose(cv2, points, image_points, intrinsic, *, initial=None):
    """Solve PnP, optionally refining an existing pose with every input point."""
    distortion = np.zeros(5, dtype=np.float64)
    object_points = np.ascontiguousarray(points, dtype=np.float64)
    observed_points = np.ascontiguousarray(image_points, dtype=np.float64)
    camera_matrix = np.ascontiguousarray(intrinsic, dtype=np.float64)
    try:
        if initial is None:
            success, rotation_vector, translation = cv2.solvePnP(
                object_points,
                observed_points,
                camera_matrix,
                distortion,
                flags=cv2.SOLVEPNP_EPNP,
            )
        else:
            rotation, translation = initial
            rotation_vector = cv2.Rodrigues(
                np.asarray(rotation, dtype=np.float64)
            )[0]
            success, rotation_vector, translation = cv2.solvePnP(
                object_points,
                observed_points,
                camera_matrix,
                distortion,
                rvec=rotation_vector,
                tvec=np.asarray(translation, dtype=np.float64).reshape(3, 1).copy(),
                useExtrinsicGuess=True,
                flags=cv2.SOLVEPNP_ITERATIVE,
            )
        if not success:
            raise RuntimeError("cv2.solvePnP failed")
    except cv2.error as error:
        raise RuntimeError("OpenCV PnP failed") from error
    if not np.isfinite(rotation_vector).all() or not np.isfinite(translation).all():
        raise RuntimeError("cv2.solvePnP returned a non-finite pose")
    return cv2.Rodrigues(rotation_vector)[0], translation


def _score_pose(errors, inlier_mask, scoring, sample_size):
    inlier_count = int(np.count_nonzero(inlier_mask))
    if scoring == "mean_error":
        return (-float(np.mean(errors)),)
    if inlier_count < sample_size:
        return None
    return (
        inlier_count,
        -float(np.median(errors[inlier_mask])),
        -float(np.mean(errors[inlier_mask])),
    )


def fit_quasi_ransac(
    p3: np.ndarray,
    p2: np.ndarray,
    p2_alt: np.ndarray,
    K: np.ndarray,
    *,
    confidence: float = 0.99,
    valid_correspondence_ratio: float = 1.0,
    inlier_threshold: float = 8.0,
    max_iterations: int = 2000,
    seed: int = 2025,
    adaptive: bool = True,
    scoring: str = "consensus",
) -> QuasiRansacResult:
    """Estimate metric ``T_camera_lidar`` from two candidates per target."""
    try:
        import cv2
    except ImportError as error:
        raise QuasiRansacError(
            QuasiRansacStatus.INVALID_INPUT,
            "OpenCV is required; install the package with the 'vision' extra",
        ) from error

    start = perf_counter()
    p3, candidate_a, candidate_b, intrinsic = _validate_inputs(p3, p2, p2_alt, K)
    if inlier_threshold <= 0.0:
        raise QuasiRansacError(
            QuasiRansacStatus.INVALID_INPUT,
            "inlier_threshold must be positive",
        )
    if scoring not in {"consensus", "mean_error"}:
        raise QuasiRansacError(
            QuasiRansacStatus.INVALID_INPUT,
            "scoring must be 'consensus' or 'mean_error'",
        )
    sample_size = 4
    generator = np.random.default_rng(seed)
    cv2.setRNGSeed(int(seed) & 0x7FFFFFFF)
    initial_limit = quasi_ransac_iteration_bound(
        valid_correspondence_ratio,
        confidence,
        sample_size,
        max_iterations,
    )
    planned_limit = initial_limit if adaptive else int(max_iterations)
    adaptive_limit = planned_limit
    best_score = None
    best_pose = None
    best_selected = None
    best_mask = None
    pose_failures = 0
    iterations = 0

    while iterations < adaptive_limit:
        iterations += 1
        indices = generator.choice(p3.shape[0], sample_size, replace=False)
        choose_first = generator.integers(0, 2, size=sample_size).astype(bool)
        image_sample = np.where(
            choose_first[:, None],
            candidate_a[indices],
            candidate_b[indices],
        )
        try:
            rotation, translation = _recover_pose(
                cv2,
                p3[indices],
                image_sample,
                intrinsic,
            )
        except (RuntimeError, ValueError, np.linalg.LinAlgError):
            pose_failures += 1
            continue
        projected = _project(p3, rotation, translation, intrinsic)
        if projected is None or not np.isfinite(projected).all():
            pose_failures += 1
            continue
        errors, selected = _branch_errors(projected, candidate_a, candidate_b)
        inlier_mask = errors <= inlier_threshold
        inlier_count = int(np.count_nonzero(inlier_mask))
        score = _score_pose(errors, inlier_mask, scoring, sample_size)
        if score is None:
            continue
        if best_score is None or score > best_score:
            best_score = score
            best_pose = (rotation, translation)
            best_selected = selected
            best_mask = inlier_mask
            if adaptive and scoring == "consensus":
                observed_q = inlier_count / float(p3.shape[0])
                adaptive_limit = min(
                    adaptive_limit,
                    quasi_ransac_iteration_bound(
                        observed_q,
                        confidence,
                        sample_size,
                        max_iterations,
                    ),
                )

    if best_pose is None:
        raise QuasiRansacError(
            QuasiRansacStatus.NO_CONSENSUS,
            f"no valid pose after {iterations} iterations ({pose_failures} pose failures)",
        )

    rotation, translation = best_pose
    projected = _project(p3, rotation, translation, intrinsic)
    if projected is None or not np.isfinite(projected).all():
        raise QuasiRansacError(
            QuasiRansacStatus.POSE_FAILURE,
            "the selected pose places one or more targets behind the camera",
        )
    errors, selected = _branch_errors(projected, candidate_a, candidate_b)
    inlier_mask = errors <= inlier_threshold
    final_score = _score_pose(errors, inlier_mask, scoring, sample_size)
    final_state = (rotation, translation, selected, inlier_mask, errors)

    # Quasi-RANSAC supplies the robust hypothesis. As in the calibration
    # pipeline, finish by repeatedly selecting the nearest candidate and using
    # every current consensus inlier in an ITERATIVE PnP refinement.
    for _ in range(5):
        if np.count_nonzero(inlier_mask) < sample_size:
            break
        previous_selected = selected
        previous_mask = inlier_mask
        try:
            rotation, translation = _recover_pose(
                cv2,
                p3[inlier_mask],
                selected[inlier_mask],
                intrinsic,
                initial=(rotation, translation),
            )
        except (RuntimeError, ValueError, np.linalg.LinAlgError):
            pose_failures += 1
            break
        projected = _project(p3, rotation, translation, intrinsic)
        if projected is None or not np.isfinite(projected).all():
            pose_failures += 1
            break
        errors, selected = _branch_errors(projected, candidate_a, candidate_b)
        inlier_mask = errors <= inlier_threshold
        score = _score_pose(errors, inlier_mask, scoring, sample_size)
        if score is not None and (final_score is None or score >= final_score):
            final_score = score
            final_state = (rotation, translation, selected, inlier_mask, errors)
        if np.array_equal(selected, previous_selected) and np.array_equal(
            inlier_mask, previous_mask
        ):
            break

    rotation, translation, selected, inlier_mask, errors = final_state
    if np.count_nonzero(inlier_mask) < sample_size:
        rotation, translation = best_pose
        selected = best_selected
        inlier_mask = best_mask
        projected = _project(p3, rotation, translation, intrinsic)
        errors = np.linalg.norm(projected - selected, axis=1)
    mean_error = float(np.mean(errors[inlier_mask]))
    return QuasiRansacResult(
        rotation=np.asarray(rotation, dtype=float),
        translation=np.asarray(translation, dtype=float).reshape(3, 1),
        mean_reprojection_error=mean_error,
        selected_points=np.asarray(selected, dtype=float),
        inlier_mask=np.asarray(inlier_mask, dtype=bool),
        iterations=iterations,
        iteration_limit=planned_limit,
        confidence=float(confidence),
        pose_failures=pose_failures,
        status=QuasiRansacStatus.SUCCESS,
        elapsed_seconds=perf_counter() - start,
    )


__all__ = [
    "QuasiRansacError",
    "QuasiRansacResult",
    "QuasiRansacStatus",
    "fit_quasi_ransac",
    "quasi_ransac_iteration_bound",
]
