#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Plot the principal metrics from a synthetic experiment summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


PANELS = (
    ("3d_circle", "noise_sigma_m", "center_error_m", "3D center error (m)"),
    ("2d_center", "tilt_degrees", "pixel_error", "2D center error (px)"),
    ("pose", "image_noise_px", "rotation_error_deg", "Rotation error (deg)"),
)


def _series(groups, study, sweep, metric):
    methods = {}
    for group in groups:
        if group["study"] != study or group["sweep"] != sweep:
            continue
        metric_summary = group["metrics"].get(metric)
        if metric_summary is None:
            continue
        methods.setdefault(group["method"], []).append(
            (float(group["setting"]), float(metric_summary["median"]))
        )
    return {method: sorted(values) for method, values in methods.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("--output", type=Path, default=Path("outputs/synthetic/summary.png"))
    arguments = parser.parse_args()

    document = json.loads(arguments.summary.read_text(encoding="utf-8"))
    figure, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for axis, (study, sweep, metric, ylabel) in zip(axes, PANELS):
        series = _series(document["groups"], study, sweep, metric)
        for method, values in series.items():
            axis.plot(
                [value[0] for value in values],
                [value[1] for value in values],
                marker="o",
                label=method.replace("_", " "),
            )
        axis.set_xlabel(sweep.replace("_", " "))
        axis.set_ylabel(ylabel)
        axis.grid(True, alpha=0.3)
        if sweep == "noise_sigma_m":
            axis.set_xscale("log")
            axis.set_yscale("log")
        axis.legend(fontsize=8)
    figure.tight_layout()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(arguments.output, dpi=200, bbox_inches="tight")
    plt.close(figure)
    print(f"wrote {arguments.output}")


if __name__ == "__main__":
    main()
