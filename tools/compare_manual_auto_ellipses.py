#!/usr/bin/env python3
"""Compare legacy manually selected ellipses with automatic board detections."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Mapping

import numpy as np
import yaml

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
for _source_root in (_REPOSITORY_ROOT, _REPOSITORY_ROOT / "src"):
    if str(_source_root) not in sys.path:
        sys.path.insert(0, str(_source_root))

from experiments.qualitative_realworld.data_io import (  # noqa: E402
    load_dataset,
    read_image,
)
from experiments.qualitative_realworld.detection2d import (  # noqa: E402
    detect_target_ellipse,
)


def _load_yaml(path: Path) -> Mapping[str, object]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, Mapping):
        raise ValueError(f"{path} must contain a YAML mapping")
    return document


def _load_manual(path: Path) -> dict[int, tuple[float, float, float, float, float]]:
    ellipses = {}
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            values = [float(value) for value in line.split(",")]
            if len(values) != 12:
                raise ValueError(f"{path}:{line_number} must contain 12 values")
            ellipses[int(values[0])] = tuple(values[1:6])
    return ellipses


def _major_axis_angle(width: float, height: float, angle_degrees: float) -> float:
    angle = angle_degrees if width >= height else angle_degrees + 90.0
    return angle % 180.0


def _angle_distance(first: float, second: float) -> float:
    difference = abs(first - second) % 180.0
    return min(difference, 180.0 - difference)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("manual_ellipses", type=Path)
    parser.add_argument(
        "--detection-config",
        type=Path,
        default=Path("experiments/qualitative_realworld/detection2d/config.yaml"),
    )
    parser.add_argument("--output-csv", type=Path)
    args = parser.parse_args()

    dataset_root = args.dataset.expanduser().resolve()
    dataset = load_dataset(dataset_root.parent, dataset_root.name)
    manual = _load_manual(args.manual_ellipses)
    detection_config = _load_yaml(args.detection_config)

    records = []
    failures = []
    for pair in dataset.pairs:
        manual_index = int(pair.frame_id) - 1
        if manual_index not in manual:
            failures.append({"frame_id": pair.frame_id, "error": "manual row missing"})
            continue
        image = read_image(pair.image_path)
        try:
            detected = detect_target_ellipse(
                image,
                dataset.intrinsic,
                dataset.distortion,
                dataset.distortion_model,
                detection_config,
            )
        except Exception as error:
            failures.append({"frame_id": pair.frame_id, "error": str(error)})
            continue

        manual_x, manual_y, manual_width, manual_height, manual_angle = manual[
            manual_index
        ]
        (auto_x, auto_y), (auto_width, auto_height), auto_angle = (
            detected.raw_cv_ellipse
        )
        manual_axes = sorted((manual_width, manual_height), reverse=True)
        auto_axes = sorted((auto_width, auto_height), reverse=True)
        records.append(
            {
                "frame_id": pair.frame_id,
                "manual_x_px": manual_x,
                "manual_y_px": manual_y,
                "manual_major_axis_px": manual_axes[0],
                "manual_minor_axis_px": manual_axes[1],
                "manual_major_angle_deg": _major_axis_angle(
                    manual_width, manual_height, manual_angle
                ),
                "auto_x_px": auto_x,
                "auto_y_px": auto_y,
                "auto_major_axis_px": auto_axes[0],
                "auto_minor_axis_px": auto_axes[1],
                "auto_major_angle_deg": _major_axis_angle(
                    auto_width, auto_height, auto_angle
                ),
                "center_difference_px": float(
                    np.hypot(manual_x - auto_x, manual_y - auto_y)
                ),
                "major_axis_difference_px": abs(manual_axes[0] - auto_axes[0]),
                "minor_axis_difference_px": abs(manual_axes[1] - auto_axes[1]),
                "major_angle_difference_deg": _angle_distance(
                    _major_axis_angle(manual_width, manual_height, manual_angle),
                    _major_axis_angle(auto_width, auto_height, auto_angle),
                ),
            }
        )

    if not records:
        print(json.dumps({"automatic_detection_failures": failures}, indent=2))
        return 1

    if args.output_csv is not None:
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        with args.output_csv.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)

    center_differences = np.asarray(
        [record["center_difference_px"] for record in records], dtype=float
    )
    major_axis_differences = np.asarray(
        [record["major_axis_difference_px"] for record in records], dtype=float
    )
    minor_axis_differences = np.asarray(
        [record["minor_axis_difference_px"] for record in records], dtype=float
    )
    angle_differences = np.asarray(
        [record["major_angle_difference_deg"] for record in records], dtype=float
    )
    worst = sorted(records, key=lambda record: record["center_difference_px"], reverse=True)
    summary = {
        "dataset": dataset.name,
        "paired_frames": len(dataset.pairs),
        "compared_frames": len(records),
        "automatic_detection_failures": failures,
        "center_difference_px": {
            "median": float(np.median(center_differences)),
            "p95": float(np.percentile(center_differences, 95)),
            "maximum": float(np.max(center_differences)),
            "over_10_px": int(np.count_nonzero(center_differences > 10.0)),
        },
        "major_axis_difference_px": {
            "median": float(np.median(major_axis_differences)),
            "p95": float(np.percentile(major_axis_differences, 95)),
            "maximum": float(np.max(major_axis_differences)),
        },
        "minor_axis_difference_px": {
            "median": float(np.median(minor_axis_differences)),
            "p95": float(np.percentile(minor_axis_differences, 95)),
            "maximum": float(np.max(minor_axis_differences)),
        },
        "major_angle_difference_deg": {
            "median": float(np.median(angle_differences)),
            "p95": float(np.percentile(angle_differences, 95)),
            "maximum": float(np.max(angle_differences)),
        },
        "worst_center_differences": [
            {
                "frame_id": record["frame_id"],
                "center_difference_px": record["center_difference_px"],
                "manual_center_px": [record["manual_x_px"], record["manual_y_px"]],
                "auto_center_px": [record["auto_x_px"], record["auto_y_px"]],
            }
            for record in worst[:5]
        ],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
