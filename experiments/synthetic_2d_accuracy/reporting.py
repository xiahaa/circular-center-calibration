"""CSV, summary, comparison, and Figure 8 output generation."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import numpy as np

RECORD_FIELDS = (
    "trial",
    "seed",
    "method",
    "success",
    "estimate_x_px",
    "estimate_y_px",
    "ground_truth_x_px",
    "ground_truth_y_px",
    "error_x_px",
    "error_y_px",
    "error_magnitude_px",
    "candidate_count",
    "selected_candidate",
    "rejected_x_px",
    "rejected_y_px",
    "estimate_seconds",
    "selection_seconds",
    "status",
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


def _metric(values: Iterable[float]) -> Mapping[str, Any]:
    array = np.asarray(tuple(values), dtype=float)
    if not len(array):
        return {
            "mean": None,
            "std": None,
            "median": None,
            "p95": None,
            "max": None,
        }
    return {
        "mean": float(np.mean(array)),
        "std": float(np.std(array)),
        "median": float(np.median(array)),
        "p95": float(np.percentile(array, 95.0)),
        "max": float(np.max(array)),
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
                "attempts": len(values),
                "successes": len(successful),
                "success_rate": len(successful) / float(len(values)),
                "error_x_px": _metric(value["error_x_px"] for value in successful),
                "error_y_px": _metric(value["error_y_px"] for value in successful),
                "error_magnitude_px": _metric(
                    value["error_magnitude_px"] for value in successful
                ),
                "estimate_seconds": _metric(
                    value["estimate_seconds"] for value in successful
                ),
                "selection_seconds": _metric(
                    value["selection_seconds"] for value in successful
                ),
            }
        )
    return groups


def write_method_summary(path: Path, groups: Sequence[Mapping[str, Any]]) -> None:
    fields = (
        "method",
        "attempts",
        "successes",
        "success_rate",
        "mean_error_px",
        "std_error_px",
        "median_error_px",
        "p95_error_px",
        "max_error_px",
    )
    rows = []
    for group in groups:
        metric = group["error_magnitude_px"]
        rows.append(
            {
                "method": group["method"],
                "attempts": group["attempts"],
                "successes": group["successes"],
                "success_rate": group["success_rate"],
                "mean_error_px": metric["mean"],
                "std_error_px": metric["std"],
                "median_error_px": metric["median"],
                "p95_error_px": metric["p95"],
                "max_error_px": metric["max"],
            }
        )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def compare_with_reference(
    groups: Sequence[Mapping[str, Any]], reference: Mapping[str, Any]
) -> List[Mapping[str, Any]]:
    by_method = {str(group["method"]): group for group in groups}
    comparisons = []
    for method, expected_metrics in reference["error_magnitude_px"].items():
        observed_group = by_method.get(str(method))
        for metric_name, expected in expected_metrics.items():
            observed = (
                None
                if observed_group is None
                else observed_group["error_magnitude_px"].get(metric_name)
            )
            expected = float(expected)
            absolute = None if observed is None else abs(float(observed) - expected)
            comparisons.append(
                {
                    "method": method,
                    "metric": metric_name,
                    "observed_px": observed,
                    "paper_reference_px": expected,
                    "absolute_difference_px": absolute,
                    "relative_difference": (
                        None if absolute is None or expected == 0.0 else absolute / expected
                    ),
                }
            )
    return comparisons


def write_comparison_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = (
        "method",
        "metric",
        "observed_px",
        "paper_reference_px",
        "absolute_difference_px",
        "relative_difference",
    )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def plot_error_distribution(
    path: Path,
    records: Sequence[Mapping[str, Any]],
    method_order: Sequence[str],
    *,
    bins: int,
    dpi: int,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    successful = [record for record in records if record["success"]]
    available = {
        str(record["method"])
        for record in successful
    }
    methods = [method for method in method_order if method in available]
    methods.extend(sorted(available - set(methods)))
    if not methods:
        raise ValueError("cannot plot an experiment with no successful records")

    errors = {
        method: np.array(
            [
                [record["error_x_px"], record["error_y_px"]]
                for record in successful
                if record["method"] == method
            ],
            dtype=float,
        )
        for method in methods
    }
    all_magnitudes = np.concatenate(
        [np.linalg.norm(values, axis=1) for values in errors.values()]
    )
    color_norm = plt.Normalize(
        vmin=float(np.min(all_magnitudes)), vmax=float(np.max(all_magnitudes))
    )
    color_map = plt.get_cmap("viridis")

    figure, axes = plt.subplots(
        len(methods),
        2,
        figsize=(10.0, 4.6 * len(methods)),
        squeeze=False,
        facecolor="white",
    )
    figure.subplots_adjust(left=0.22, right=0.97, top=0.96, bottom=0.07, hspace=0.34)
    for row, method in enumerate(methods):
        values = errors[method]
        magnitudes = np.linalg.norm(values, axis=1)
        scatter_axis, histogram_axis = axes[row]
        scatter_axis.scatter(
            values[:, 0],
            values[:, 1],
            c=magnitudes,
            cmap=color_map,
            norm=color_norm,
            alpha=0.62,
            s=20,
            edgecolors="#222222",
            linewidth=0.35,
        )
        scatter_axis.axhline(0.0, color="red", linestyle="--", alpha=0.65)
        scatter_axis.axvline(0.0, color="red", linestyle="--", alpha=0.65)
        scatter_axis.grid(True, alpha=0.28)
        scatter_axis.set_title(method, fontweight="bold", pad=12)
        scatter_axis.set_xlabel("Error in X (pixels)")
        scatter_axis.set_ylabel("Error in Y (pixels)")

        histogram_axis.hist(
            magnitudes,
            bins=int(bins),
            color="#8E3A99",
            edgecolor="#222222",
            alpha=0.82,
        )
        mean = float(np.mean(magnitudes))
        median = float(np.median(magnitudes))
        histogram_axis.axvline(
            mean, color="orange", linewidth=2.0, label="Mean: {:.2f}".format(mean)
        )
        histogram_axis.axvline(
            median,
            color="red",
            linestyle="--",
            linewidth=2.0,
            label="Median: {:.2f}".format(median),
        )
        histogram_axis.set_xlabel("Error Magnitude (pixels)")
        histogram_axis.set_ylabel("Frequency")
        histogram_axis.grid(True, alpha=0.28)
        histogram_axis.legend()

    colorbar_axis = figure.add_axes([0.075, 0.16, 0.018, 0.68])
    scalar_map = plt.cm.ScalarMappable(cmap=color_map, norm=color_norm)
    scalar_map.set_array([])
    colorbar = figure.colorbar(scalar_map, cax=colorbar_axis)
    colorbar.ax.yaxis.set_label_position("left")
    colorbar.set_label("Error Magnitude (pixels)", rotation=90, labelpad=10)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=int(dpi), bbox_inches="tight", facecolor="white")
    plt.close(figure)


__all__ = [
    "compare_with_reference",
    "plot_error_distribution",
    "summarize_records",
    "write_comparison_csv",
    "write_method_summary",
    "write_raw_records",
]
