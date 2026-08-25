"""CSV, LaTeX, JSON-summary, and paper-style figure generation."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np

RECORD_FIELDS = (
    "study",
    "setting",
    "panel",
    "trial",
    "method",
    "success",
    "center_error_m",
    "radius_error_m",
    "normal_error_deg",
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
        writer.writerows({field: record.get(field) for field in RECORD_FIELDS} for record in records)


def _metric_summary(values: Iterable[float]) -> Mapping[str, Any]:
    array = np.asarray(tuple(values), dtype=float)
    if not len(array):
        return {"mean": None, "median": None, "p95": None}
    return {
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "p95": float(np.percentile(array, 95.0)),
    }


def summarize_records(records: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    grouped: Dict[Tuple[str, str, str, str], List[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        key = (
            str(record["study"]),
            str(record["setting"]),
            str(record.get("panel", "")),
            str(record["method"]),
        )
        grouped[key].append(record)

    summaries = []
    for (study, setting, panel, method), values in sorted(grouped.items()):
        successful = [value for value in values if value["success"]]
        summaries.append(
            {
                "study": study,
                "setting": setting,
                "panel": panel or None,
                "method": method,
                "attempts": len(values),
                "successes": len(successful),
                "success_rate": len(successful) / float(len(values)),
                "center_error_m": _metric_summary(
                    value["center_error_m"] for value in successful
                ),
                "radius_error_m": _metric_summary(
                    value["radius_error_m"] for value in successful
                ),
                "normal_error_deg": _metric_summary(
                    value["normal_error_deg"] for value in successful
                ),
                "elapsed_seconds": _metric_summary(
                    value["elapsed_seconds"] for value in successful
                ),
            }
        )
    return summaries


def _lookup_mean(
    groups: Sequence[Mapping[str, Any]], study: str, setting: str, method: str
) -> Any:
    for group in groups:
        if (
            group["study"] == study
            and str(group["setting"]) == str(setting)
            and group["method"] == method
        ):
            return group["center_error_m"]["mean"]
    return None


def compare_with_reference(
    groups: Sequence[Mapping[str, Any]],
    reference: Mapping[str, Any],
    outputs: Mapping[str, Any],
) -> List[Mapping[str, Any]]:
    comparisons = []
    for scenario, values in reference["monte_carlo_mean_center_error_m"].items():
        for paper_label, expected in values.items():
            method = outputs["monte_carlo"][paper_label]
            observed = _lookup_mean(groups, "monte_carlo", scenario, method)
            comparisons.append(
                _comparison_row("monte_carlo", scenario, paper_label, method, observed, expected)
            )
    for ratio, values in reference["outlier_mean_center_error_m"].items():
        for paper_label, expected in values.items():
            method = outputs["outlier"][paper_label]
            observed = _lookup_mean(groups, "outlier", str(ratio), method)
            comparisons.append(
                _comparison_row("outlier", str(ratio), paper_label, method, observed, expected)
            )
    return comparisons


def _comparison_row(study, setting, paper_label, method, observed, expected):
    expected = float(expected)
    absolute = None if observed is None else abs(float(observed) - expected)
    relative = None if absolute is None else absolute / expected
    return {
        "study": study,
        "setting": setting,
        "paper_label": paper_label,
        "implementation": method,
        "observed_mean_center_error_m": observed,
        "reference_mean_center_error_m": expected,
        "absolute_difference_m": absolute,
        "relative_difference": relative,
    }


def write_comparison_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = (
        "study",
        "setting",
        "paper_label",
        "implementation",
        "observed_mean_center_error_m",
        "reference_mean_center_error_m",
        "absolute_difference_m",
        "relative_difference",
    )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_outlier_table(
    csv_path: Path,
    tex_path: Path,
    groups: Sequence[Mapping[str, Any]],
    ratios: Sequence[float],
    method_mapping: Mapping[str, str],
) -> None:
    fields = ("outlier_ratio", "paper_label", "implementation", "mean_center_error_m")
    rows = []
    for paper_label, method in method_mapping.items():
        for ratio in ratios:
            rows.append(
                {
                    "outlier_ratio": float(ratio),
                    "paper_label": paper_label,
                    "implementation": method,
                    "mean_center_error_m": _lookup_mean(
                        groups, "outlier", str(float(ratio)), method
                    ),
                }
            )
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "% Generated by experiments/synthetic_3d_accuracy.",
        "\\begin{tabular}{c|" + "c" * len(ratios) + "}",
        "\\toprule",
        "Method & " + " & ".join("{:.0f}\\%".format(100.0 * ratio) for ratio in ratios) + " \\\\",
        "\\midrule",
    ]
    for paper_label, method in method_mapping.items():
        values = [_lookup_mean(groups, "outlier", str(float(ratio)), method) for ratio in ratios]
        formatted = ["--" if value is None else "{:.4f}".format(value) for value in values]
        lines.append("{} & {} \\\\".format(paper_label, " & ".join(formatted)))
    lines.extend(("\\bottomrule", "\\end{tabular}", ""))
    tex_path.write_text("\n".join(lines), encoding="utf-8")


def plot_monte_carlo(
    pdf_path: Path,
    png_path: Path,
    groups: Sequence[Mapping[str, Any]],
    scenarios: Sequence[Mapping[str, Any]],
    method_mapping: Mapping[str, str],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    panels = [str(scenario["panel"]) for scenario in scenarios]
    settings = [str(scenario["name"]) for scenario in scenarios]
    x_values = np.arange(len(settings), dtype=float)
    method_count = len(method_mapping)
    width = 0.8 / max(1, method_count)
    colors = ("#AFC6E9", "#FFD7B1", "#B9E4C9", "#D4C2F0")

    figure, axis = plt.subplots(figsize=(8.0, 4.6))
    for method_index, (paper_label, method) in enumerate(method_mapping.items()):
        means = [_lookup_mean(groups, "monte_carlo", setting, method) for setting in settings]
        heights = [0.0 if value is None else value for value in means]
        positions = x_values - 0.4 + 0.5 * width + method_index * width
        axis.bar(
            positions,
            heights,
            width,
            label=paper_label,
            color=colors[method_index % len(colors)],
            edgecolor="#444444",
            linewidth=0.5,
        )
    axis.set_xticks(x_values)
    axis.set_xticklabels(panels)
    axis.set_xlabel("Scenario")
    axis.set_ylabel("Mean center error (m)")
    axis.grid(axis="y", alpha=0.25)
    axis.legend(frameon=False)
    figure.tight_layout()
    figure.savefig(pdf_path, bbox_inches="tight")
    figure.savefig(png_path, dpi=240, bbox_inches="tight")
    plt.close(figure)


__all__ = [
    "compare_with_reference",
    "plot_monte_carlo",
    "summarize_records",
    "write_comparison_csv",
    "write_outlier_table",
    "write_raw_records",
]
