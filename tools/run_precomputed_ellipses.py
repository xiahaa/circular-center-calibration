"""Run the real-world pipeline with externally generated raw-image ellipses."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from circular_center.experiments.runner import run_experiment  # noqa: E402
from experiments.qualitative_realworld import experiment  # noqa: E402
from experiments.qualitative_realworld.detection2d import (  # noqa: E402
    detected_target_from_raw_ellipse,
)

RawEllipse = Tuple[Tuple[float, float], Tuple[float, float], float]


def _load_ellipses(source: Path) -> Dict[int, RawEllipse]:
    rows: Dict[int, RawEllipse] = {}
    for line_number, line in enumerate(
        Path(source).read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        values = [value.strip() for value in line.split(",")]
        if len(values) < 6:
            raise ValueError(
                "{}:{} must contain index,x,y,width,height,angle".format(
                    source, line_number
                )
            )
        index = int(values[0])
        numeric = np.asarray([float(value) for value in values[1:6]], dtype=float)
        if not np.all(np.isfinite(numeric)):
            raise ValueError("{}:{} contains a non-finite ellipse".format(source, line_number))
        if index in rows:
            raise ValueError("{} contains duplicate index {}".format(source, index))
        rows[index] = (
            (float(numeric[0]), float(numeric[1])),
            (float(numeric[2]), float(numeric[3])),
            float(numeric[4]),
        )
    if not rows:
        raise ValueError("{} contains no ellipses".format(source))
    expected = set(range(len(rows)))
    if set(rows) != expected:
        raise ValueError("{} indices must be contiguous and zero-based".format(source))
    return rows


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the same refactored calibration downstream of a zero-based "
            "index,x,y,width,height,angle ellipse file."
        )
    )
    parser.add_argument("config", type=Path)
    parser.add_argument("ellipses", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--proposal-source", default="precomputed")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = build_argument_parser().parse_args(argv)
    ellipses = _load_ellipses(arguments.ellipses)
    call_index = 0

    def precomputed_detector(
        image: np.ndarray,
        intrinsic: np.ndarray,
        distortion: np.ndarray,
        distortion_model: str,
        config,
    ):
        del image, config
        nonlocal call_index
        try:
            raw_ellipse = ellipses[call_index]
        except KeyError as error:
            raise ValueError(
                "ellipse file ended before detector call {}".format(call_index)
            ) from error
        call_index += 1
        return detected_target_from_raw_ellipse(
            raw_ellipse,
            intrinsic,
            distortion,
            distortion_model,
            proposal_source=arguments.proposal_source,
        )

    original_detector = experiment.detect_target_ellipse
    experiment.detect_target_ellipse = precomputed_detector
    try:
        result = run_experiment(
            arguments.config,
            output_directory=arguments.output_dir,
        )
    finally:
        experiment.detect_target_ellipse = original_detector
    if call_index != len(ellipses):
        raise ValueError(
            "used {} of {} precomputed ellipses".format(call_index, len(ellipses))
        )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
