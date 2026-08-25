"""CSV and paper-style heatmap output for Figure 6."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple

import numpy as np

RECORD_FIELDS = (
    "distribution",
    "point_count",
    "arc_degrees",
    "trial",
    "method",
    "fit_success",
    "center_error_m",
    "below_threshold",
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
    grouped: Dict[Tuple[str, int, int, str], list] = defaultdict(list)
    for record in records:
        key = (
            str(record["distribution"]),
            int(record["point_count"]),
            int(record["arc_degrees"]),
            str(record["method"]),
        )
        grouped[key].append(record)
    rows = []
    for (distribution, point_count, arc_degrees, method), values in sorted(grouped.items()):
        fitted = [value for value in values if value["fit_success"]]
        errors = np.asarray([value["center_error_m"] for value in fitted], dtype=float)
        threshold_successes = sum(bool(value["below_threshold"]) for value in values)
        rows.append(
            {
                "distribution": distribution,
                "point_count": point_count,
                "arc_degrees": arc_degrees,
                "method": method,
                "attempts": len(values),
                "fit_successes": len(fitted),
                "threshold_successes": threshold_successes,
                "success_probability": threshold_successes / float(len(values)),
                "mean_center_error_m": None if not len(errors) else float(np.mean(errors)),
                "median_center_error_m": None if not len(errors) else float(np.median(errors)),
            }
        )
    return rows


def write_summary_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = (
        "distribution",
        "point_count",
        "arc_degrees",
        "method",
        "attempts",
        "fit_successes",
        "threshold_successes",
        "success_probability",
        "mean_center_error_m",
        "median_center_error_m",
    )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _lookup_probability(
    rows: Sequence[Mapping[str, Any]],
    distribution: str,
    point_count: int,
    arc_degrees: int,
    method: str,
) -> float:
    for row in rows:
        if (
            row["distribution"] == distribution
            and int(row["point_count"]) == int(point_count)
            and int(row["arc_degrees"]) == int(arc_degrees)
            and row["method"] == method
        ):
            return float(row["success_probability"])
    return float("nan")


def plot_heatmap(
    pdf_path: Path,
    png_path: Path,
    rows: Sequence[Mapping[str, Any]],
    point_counts: Sequence[int],
    arc_degrees: Sequence[int],
    distributions: Sequence[Mapping[str, str]],
    methods: Sequence[str],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    colormap = LinearSegmentedColormap.from_list(
        "paper_success", ("lightcoral", "lightyellow", "seagreen")
    )
    figure, axes = plt.subplots(
        len(methods),
        len(distributions),
        figsize=(10.4, 5.15),
        sharex=True,
        sharey=True,
        constrained_layout=True,
        squeeze=False,
    )
    image = None
    for method_index, method in enumerate(methods):
        for distribution_index, distribution in enumerate(distributions):
            matrix = np.asarray(
                [
                    [
                        _lookup_probability(
                            rows,
                            str(distribution["name"]),
                            int(point_count),
                            int(arc),
                            method,
                        )
                        for arc in arc_degrees
                    ]
                    for point_count in point_counts
                ],
                dtype=float,
            )
            axis = axes[method_index, distribution_index]
            image = axis.imshow(
                matrix,
                origin="lower",
                aspect="auto",
                vmin=0.0,
                vmax=1.0,
                cmap=colormap,
                interpolation="nearest",
            )
            if method_index == 0:
                axis.set_title(str(distribution["label"]), fontsize=10)
            axis.set_xticks(range(len(arc_degrees)), [str(value) for value in arc_degrees])
            axis.set_yticks(range(len(point_counts)), [str(value) for value in point_counts])
            if distribution_index == 0:
                axis.set_ylabel("{}\nPoint count".format(method))
            if method_index == len(methods) - 1:
                axis.set_xlabel("Visible arc (deg)")
    if image is not None:
        figure.colorbar(image, ax=axes, label="P(center error < 1 cm)", shrink=0.88)
    figure.savefig(pdf_path, bbox_inches="tight")
    figure.savefig(png_path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def compare_with_reference(
    rows: Sequence[Mapping[str, Any]],
    reference: Mapping[str, Any],
    point_counts: Sequence[int],
    arc_degrees: Sequence[int],
) -> Sequence[Mapping[str, Any]]:
    comparisons = []
    denominator = float(reference["trials_per_cell"])
    for method, distributions in reference["success_counts"].items():
        for distribution, matrix in distributions.items():
            for point_index, point_count in enumerate(point_counts):
                for arc_index, arc in enumerate(arc_degrees):
                    expected = float(matrix[point_index][arc_index]) / denominator
                    observed = _lookup_probability(
                        rows, distribution, int(point_count), int(arc), method
                    )
                    comparisons.append(
                        {
                            "method": method,
                            "distribution": distribution,
                            "point_count": int(point_count),
                            "arc_degrees": int(arc),
                            "observed_success_probability": observed,
                            "figure_reference_probability": expected,
                            "absolute_difference": abs(observed - expected),
                        }
                    )
    return comparisons


def write_comparison_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = (
        "method",
        "distribution",
        "point_count",
        "arc_degrees",
        "observed_success_probability",
        "figure_reference_probability",
        "absolute_difference",
    )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


__all__ = [
    "compare_with_reference",
    "plot_heatmap",
    "summarize_records",
    "write_comparison_csv",
    "write_raw_records",
    "write_summary_csv",
]
