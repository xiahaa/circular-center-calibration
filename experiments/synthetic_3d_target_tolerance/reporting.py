"""Write Figure 7 trial data, summaries, comparisons, and plots."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple

import numpy as np

RECORD_FIELDS = (
    "deformation",
    "magnitude",
    "trial",
    "method",
    "success",
    "center_error_m",
    "elapsed_seconds",
    "error_type",
    "error",
)


def write_raw_records(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=RECORD_FIELDS)
        writer.writeheader()
        writer.writerows(
            {field: record.get(field) for field in RECORD_FIELDS} for record in records
        )


def summarize_records(records: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]:
    grouped: Dict[Tuple[str, float, str], list] = defaultdict(list)
    for record in records:
        grouped[
            (
                str(record["deformation"]),
                float(record["magnitude"]),
                str(record["method"]),
            )
        ].append(record)
    rows = []
    for (deformation, magnitude, method), values in sorted(grouped.items()):
        successful = [value for value in values if value["success"]]
        errors = np.asarray([value["center_error_m"] for value in successful], dtype=float)
        rows.append(
            {
                "deformation": deformation,
                "magnitude": magnitude,
                "method": method,
                "attempts": len(values),
                "successes": len(successful),
                "mean_center_error_m": None if not len(errors) else float(np.mean(errors)),
                "median_center_error_m": None if not len(errors) else float(np.median(errors)),
                "p95_center_error_m": None if not len(errors) else float(np.percentile(errors, 95.0)),
            }
        )
    return rows


def write_summary_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = (
        "deformation",
        "magnitude",
        "method",
        "attempts",
        "successes",
        "mean_center_error_m",
        "median_center_error_m",
        "p95_center_error_m",
    )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _lookup_mean(
    rows: Sequence[Mapping[str, Any]], deformation: str, magnitude: float, method: str
) -> float:
    for row in rows:
        if (
            row["deformation"] == deformation
            and float(row["magnitude"]) == float(magnitude)
            and row["method"] == method
        ):
            value = row["mean_center_error_m"]
            return float("nan") if value is None else float(value)
    return float("nan")


def plot_tolerance(
    pdf_path: Path,
    png_path: Path,
    rows: Sequence[Mapping[str, Any]],
    magnitudes: Sequence[float],
    methods: Sequence[str],
    boundary_m: float,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"PCL SACMODEL": "blue", "CGA": "green", "CGA-RANSAC": "red"}
    figure, axes = plt.subplots(1, 2, figsize=(9.0, 3.6), constrained_layout=True)
    panels = (
        ("normal_warp", "Normal warp / r"),
        ("axis_deviation", "Axis deviation e"),
    )
    for axis, (deformation, label) in zip(axes, panels):
        for method in methods:
            values = [
                1000.0 * _lookup_mean(rows, deformation, magnitude, method)
                for magnitude in magnitudes
            ]
            axis.plot(
                magnitudes,
                values,
                marker="o",
                linewidth=2.0,
                label=method,
                color=colors.get(method),
                markerfacecolor={
                    "PCL SACMODEL": "lightblue",
                    "CGA": "lightgreen",
                    "CGA-RANSAC": "lightcoral",
                }.get(method),
            )
        axis.axhline(
            1000.0 * float(boundary_m),
            color="black",
            linestyle="--",
            linewidth=1.0,
            label="1-cm boundary",
        )
        axis.set_xlabel(label)
        axis.set_ylabel("Mean center error (mm)")
        axis.grid(True, alpha=0.25)
    handles, labels = axes[0].get_legend_handles_labels()
    axes[0].legend(handles, labels, loc="lower right", fontsize=8)
    figure.savefig(pdf_path, bbox_inches="tight")
    figure.savefig(png_path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def compare_with_reference(
    rows: Sequence[Mapping[str, Any]],
    reference: Mapping[str, Any],
    magnitudes: Sequence[float],
) -> Sequence[Mapping[str, Any]]:
    comparisons = []
    for deformation, methods in reference["mean_center_error_mm"].items():
        for method, expected_values in methods.items():
            for magnitude, expected_mm in zip(magnitudes, expected_values):
                observed_m = _lookup_mean(rows, deformation, magnitude, method)
                observed_mm = 1000.0 * observed_m
                comparisons.append(
                    {
                        "deformation": deformation,
                        "magnitude": float(magnitude),
                        "method": method,
                        "observed_mean_center_error_mm": observed_mm,
                        "figure_reference_mean_center_error_mm": float(expected_mm),
                        "absolute_difference_mm": abs(observed_mm - float(expected_mm)),
                    }
                )
    return comparisons


def write_comparison_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = (
        "deformation",
        "magnitude",
        "method",
        "observed_mean_center_error_mm",
        "figure_reference_mean_center_error_mm",
        "absolute_difference_mm",
    )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


__all__ = [
    "compare_with_reference",
    "plot_tolerance",
    "summarize_records",
    "write_comparison_csv",
    "write_raw_records",
    "write_summary_csv",
]
