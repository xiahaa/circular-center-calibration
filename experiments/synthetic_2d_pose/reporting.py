"""Figure 9 CSV, summary, and bar-chart generation."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

import numpy as np

RECORD_FIELDS = (
    "trial",
    "seed",
    "method",
    "paper_label",
    "success",
    "reprojection_error_px",
    "rotation_error_rad",
    "translation_error",
    "inlier_count",
    "iterations",
    "elapsed_seconds",
    "error_type",
    "error",
)


def write_raw_records(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=RECORD_FIELDS)
        writer.writeheader()
        writer.writerows(
            {field: record.get(field) for field in RECORD_FIELDS} for record in records
        )


def _summary(values):
    array = np.asarray(values, dtype=float)
    if not len(array):
        return {"mean": None, "std": None, "median": None, "p95": None}
    return {
        "mean": float(np.mean(array)),
        "std": float(np.std(array)),
        "median": float(np.median(array)),
        "p95": float(np.percentile(array, 95.0)),
    }


def summarize_records(records: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record["method"])].append(record)
    groups = []
    for method, values in sorted(grouped.items()):
        successful = [value for value in values if value["success"]]
        groups.append(
            {
                "method": method,
                "paper_label": values[0]["paper_label"],
                "attempts": len(values),
                "successes": len(successful),
                "success_rate": len(successful) / float(len(values)),
                "reprojection_error_px": _summary(
                    [value["reprojection_error_px"] for value in successful]
                ),
                "rotation_error_rad": _summary(
                    [value["rotation_error_rad"] for value in successful]
                ),
                "translation_error": _summary(
                    [value["translation_error"] for value in successful]
                ),
                "elapsed_seconds": _summary(
                    [value["elapsed_seconds"] for value in successful]
                ),
            }
        )
    return groups


def write_method_summary(path: Path, groups: Sequence[Mapping[str, Any]]) -> None:
    fields = (
        "method",
        "paper_label",
        "attempts",
        "successes",
        "success_rate",
        "mean_reprojection_error_px",
        "mean_rotation_error_rad",
        "mean_translation_error",
    )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for group in groups:
            writer.writerow(
                {
                    "method": group["method"],
                    "paper_label": group["paper_label"],
                    "attempts": group["attempts"],
                    "successes": group["successes"],
                    "success_rate": group["success_rate"],
                    "mean_reprojection_error_px": group["reprojection_error_px"]["mean"],
                    "mean_rotation_error_rad": group["rotation_error_rad"]["mean"],
                    "mean_translation_error": group["translation_error"]["mean"],
                }
            )


def compare_with_reference(groups, reference):
    by_method = {group["method"]: group for group in groups}
    metrics = ("reprojection_error_px", "rotation_error_rad", "translation_error")
    rows = []
    for method, expected in reference["mean_errors"].items():
        group = by_method.get(method)
        for metric in metrics:
            observed = None if group is None else group[metric]["mean"]
            expected_value = float(expected[metric])
            difference = (
                None if observed is None else abs(float(observed) - expected_value)
            )
            rows.append(
                {
                    "method": method,
                    "metric": metric,
                    "observed": observed,
                    "paper_reference": expected_value,
                    "absolute_difference": difference,
                    "relative_difference": (
                        None
                        if difference is None or expected_value == 0.0
                        else difference / expected_value
                    ),
                }
            )
    return rows


def write_comparison(path: Path, rows) -> None:
    fields = (
        "method",
        "metric",
        "observed",
        "paper_reference",
        "absolute_difference",
        "relative_difference",
    )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def plot_error_bars(path: Path, groups, method_order, paper_labels, dpi: int) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    by_method = {group["method"]: group for group in groups}
    methods = [method for method in method_order if method in by_method]
    metric_keys = (
        "reprojection_error_px",
        "rotation_error_rad",
        "translation_error",
    )
    metric_labels = ("Reprojection Error", "Rotation Error", "Translation Error")
    colors = ("lightblue", "lightgreen", "lightcoral", "plum")
    edge_colors = ("blue", "green", "red", "purple")
    positions = np.arange(len(metric_keys), dtype=float)
    width = 0.8 / max(1, len(methods))

    figure, axis = plt.subplots(figsize=(10.0, 6.0), facecolor="white")
    for index, method in enumerate(methods):
        values = [by_method[method][metric]["mean"] for metric in metric_keys]
        bars = axis.bar(
            positions + index * width,
            values,
            width,
            label=paper_labels.get(method, method),
            color=colors[index % len(colors)],
            edgecolor=edge_colors[index % len(edge_colors)],
            alpha=0.72,
        )
        for bar in bars:
            height = float(bar.get_height())
            axis.text(
                bar.get_x() + 0.5 * bar.get_width(),
                height,
                "{:.3f}".format(height),
                ha="center",
                va="bottom",
                fontsize=10,
            )
    axis.set_xticks(positions + width * (len(methods) - 1) / 2.0)
    axis.set_xticklabels(metric_labels, rotation=10, ha="center")
    axis.set_ylabel("Mean Error")
    axis.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.6)
    axis.legend()
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=int(dpi), bbox_inches="tight", facecolor="white")
    plt.close(figure)


__all__ = [
    "compare_with_reference",
    "plot_error_bars",
    "summarize_records",
    "write_comparison",
    "write_method_summary",
    "write_raw_records",
]
