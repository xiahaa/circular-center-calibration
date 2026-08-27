"""Deterministic ambiguous-correspondence generation for paper Table II."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Tuple

import numpy as np


@dataclass(frozen=True)
class AmbiguousPoseTrial:
    sample_seed: int
    method_seed: int
    points3d: np.ndarray
    candidate_a: np.ndarray
    candidate_b: np.ndarray
    intrinsic: np.ndarray
    expected_rotation: np.ndarray
    expected_translation: np.ndarray
    outlier_mask: np.ndarray


def derive_trial_seeds(
    seed: int,
    point_count: int,
    outlier_ratio: float,
    trial: int,
) -> Tuple[int, int]:
    sequence = np.random.SeedSequence(
        [int(seed), int(point_count), int(round(1000.0 * outlier_ratio)), int(trial)]
    )
    values = sequence.generate_state(2, dtype=np.uint32)
    return int(values[0]), int(values[1])


def rounded_outlier_count(point_count: int, outlier_ratio: float) -> int:
    return int(np.floor(float(point_count) * float(outlier_ratio) + 0.5))


def generate_trial(
    sample_seed: int,
    method_seed: int,
    point_count: int,
    outlier_ratio: float,
    protocol: Mapping[str, Any],
) -> AmbiguousPoseTrial:
    generator = np.random.default_rng(int(sample_seed))
    camera = protocol["camera"]
    volume = protocol["volume"]
    candidates = protocol["candidates"]
    intrinsic = np.array(
        [
            [camera["fx_px"], 0.0, camera["cx_px"]],
            [0.0, camera["fy_px"], camera["cy_px"]],
            [0.0, 0.0, 1.0],
        ],
        dtype=float,
    )
    points3d = generator.uniform(
        [
            -0.5 * float(volume["width_m"]),
            -0.5 * float(volume["height_m"]),
            float(volume["minimum_depth_m"]),
        ],
        [
            0.5 * float(volume["width_m"]),
            0.5 * float(volume["height_m"]),
            float(volume["maximum_depth_m"]),
        ],
        size=(int(point_count), 3),
    )
    homogeneous = (intrinsic @ points3d.T).T
    projected = homogeneous[:, :2] / homogeneous[:, 2, None]
    correct = projected + generator.normal(
        0.0,
        float(candidates["correct_noise_sigma_px"]),
        size=projected.shape,
    )
    directions = generator.normal(size=projected.shape)
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    false = correct + directions * generator.uniform(
        float(candidates["false_minimum_px"]),
        float(candidates["false_maximum_px"]),
        size=(int(point_count), 1),
    )

    outlier_count = rounded_outlier_count(point_count, outlier_ratio)
    outlier_mask = np.zeros(int(point_count), dtype=bool)
    if outlier_count:
        indices = generator.choice(int(point_count), outlier_count, replace=False)
        outlier_mask[indices] = True
        displacement = float(candidates["outlier_coordinate_displacement_px"])
        correct[indices] = projected[indices] + generator.uniform(
            -displacement,
            displacement,
            size=(outlier_count, 2),
        )
        false[indices] = projected[indices] + generator.uniform(
            -displacement,
            displacement,
            size=(outlier_count, 2),
        )

    swap = generator.integers(0, 2, int(point_count)).astype(bool)
    candidate_a = np.where(swap[:, None], false, correct)
    candidate_b = np.where(swap[:, None], correct, false)
    return AmbiguousPoseTrial(
        sample_seed=int(sample_seed),
        method_seed=int(method_seed),
        points3d=np.asarray(points3d, dtype=float),
        candidate_a=np.asarray(candidate_a, dtype=float),
        candidate_b=np.asarray(candidate_b, dtype=float),
        intrinsic=intrinsic,
        expected_rotation=np.eye(3),
        expected_translation=np.zeros((3, 1)),
        outlier_mask=outlier_mask,
    )


__all__ = [
    "AmbiguousPoseTrial",
    "derive_trial_seeds",
    "generate_trial",
    "rounded_outlier_count",
]
