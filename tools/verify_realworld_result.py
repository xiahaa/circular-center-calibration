#!/usr/bin/env python3
"""Compare a qualitative real-world summary with a tracked expected result."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("expected", type=Path)
    parser.add_argument(
        "--absolute-tolerance",
        type=float,
        default=1e-9,
        help="absolute tolerance for floating-point reprojection metrics",
    )
    args = parser.parse_args()

    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    expected = json.loads(args.expected.read_text(encoding="utf-8"))
    if len(summary.get("datasets", [])) != 1:
        parser.error("summary must contain exactly one dataset")

    actual = summary["datasets"][0]
    calibration = actual.get("calibration")
    if not isinstance(calibration, dict):
        print("Result verification failed: calibration did not succeed")
        return 1

    actual_values = {
        "attempted_frames": actual.get("attempted_frames"),
        "successful_frames": actual.get("successful_frames"),
        "failed_frames": actual.get("failed_frames"),
        "failed_frame_ids": sorted(
            frame.get("frame_id")
            for frame in actual.get("frames", [])
            if frame.get("status") != "success"
        ),
        "correspondence_count": calibration.get("correspondence_count"),
        "inlier_count": calibration.get("inlier_count"),
        "mean_reprojection_error_all_px": calibration.get(
            "mean_reprojection_error_all_px"
        ),
        "mean_reprojection_error_inliers_px": calibration.get(
            "mean_reprojection_error_inliers_px"
        ),
    }

    errors: list[str] = []
    if summary.get("methods") != expected.get("methods"):
        errors.append(
            f"methods differ: expected {expected.get('methods')}, "
            f"got {summary.get('methods')}"
        )
    for name, actual_value in actual_values.items():
        expected_value = expected.get(name)
        if isinstance(expected_value, float):
            matches = isinstance(actual_value, (int, float)) and math.isclose(
                float(actual_value),
                expected_value,
                rel_tol=0.0,
                abs_tol=args.absolute_tolerance,
            )
        else:
            matches = actual_value == expected_value
        if not matches:
            errors.append(f"{name}: expected {expected_value}, got {actual_value}")

    if errors:
        print("Result verification failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(
        "Verified real-world result: "
        f"{actual_values['inlier_count']}/{actual_values['correspondence_count']} inliers, "
        f"all={actual_values['mean_reprojection_error_all_px']:.6f} px, "
        f"inliers={actual_values['mean_reprojection_error_inliers_px']:.6f} px"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
