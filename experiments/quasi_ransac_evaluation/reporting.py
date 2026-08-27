"""CSV and TeX reporting for paper Table II."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

import numpy as np

RECORD_FIELDS = (
    "point_count",
    "outlier_ratio",
    "outlier_count",
    "confidence",
    "trial",
    "sample_seed",
    "method_seed",
    "method",
    "fit_success",
    "pose_success",
    "theoretical_confidence",
    "planned_iterations",
    "iterations",
    "inlier_count",
    "reprojection_error_px",
    "rotation_error_deg",
    "translation_error_m",
    "elapsed_seconds",
    "error_type",
    "error",
)

SUMMARY_FIELDS = (
    "method",
    "point_count",
    "outlier_ratio",
    "outlier_count",
    "confidence",
    "attempts",
    "fit_successes",
    "pose_successes",
    "observed_success_rate",
    "mean_iterations",
    "mean_elapsed_ms",
    "mean_rotation_error_deg",
    "mean_translation_error_m",
)


def write_raw_records(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=RECORD_FIELDS)
        writer.writeheader()
        writer.writerows(
            {field: record.get(field) for field in RECORD_FIELDS} for record in records
        )


def summarize_records(records: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    grouped = defaultdict(list)
    for record in records:
        key = (
            str(record["method"]),
            int(record["point_count"]),
            float(record["outlier_ratio"]),
            float(record["confidence"]),
        )
        grouped[key].append(record)
    rows = []
    for key, values in sorted(grouped.items()):
        fit = [value for value in values if value["fit_success"]]
        pose = [value for value in values if value["pose_success"]]
        rows.append(
            {
                "method": key[0],
                "point_count": key[1],
                "outlier_ratio": key[2],
                "outlier_count": values[0]["outlier_count"],
                "confidence": key[3],
                "attempts": len(values),
                "fit_successes": len(fit),
                "pose_successes": len(pose),
                "observed_success_rate": len(pose) / float(len(values)),
                "mean_iterations": float(
                    np.mean([value["iterations"] for value in values])
                ),
                "mean_elapsed_ms": float(
                    1000.0 * np.mean([value["elapsed_seconds"] for value in values])
                ),
                "mean_rotation_error_deg": (
                    None
                    if not fit
                    else float(np.mean([value["rotation_error_deg"] for value in fit]))
                ),
                "mean_translation_error_m": (
                    None
                    if not fit
                    else float(np.mean([value["translation_error_m"] for value in fit]))
                ),
            }
        )
    return rows


def write_summary(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows({field: row.get(field) for field in SUMMARY_FIELDS} for row in rows)


def table_rows(rows, method: str, confidence: float):
    return [
        row
        for row in rows
        if row["method"] == method
        and np.isclose(float(row["confidence"]), float(confidence))
    ]


def write_tex_table(path: Path, rows, confidence: float) -> None:
    lines = [
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Corr. & Outliers (\%) & Theory & Observed & Iterations & Time (ms) \\",
        r"\midrule",
    ]
    for row in sorted(rows, key=lambda value: (value["point_count"], value["outlier_ratio"])):
        lines.append(
            "{} & {:.0f} & {:.3f} & {:.3f} & {:.1f} & {:.2f} \\\\".format(
                row["point_count"],
                100.0 * float(row["outlier_ratio"]),
                float(confidence),
                float(row["observed_success_rate"]),
                float(row["mean_iterations"]),
                float(row["mean_elapsed_ms"]),
            )
        )
    lines.extend((r"\bottomrule", r"\end{tabular}"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def compare_with_reference(rows, reference_rows):
    lookup = {
        (int(row["point_count"]), float(row["outlier_ratio"])): row for row in rows
    }
    comparisons = []
    metrics = (
        ("observed_success_rate", "observed_success_rate"),
        ("mean_iterations", "mean_iterations"),
        ("mean_elapsed_ms", "mean_elapsed_ms"),
    )
    for expected in reference_rows:
        key = (int(expected["point_count"]), float(expected["outlier_ratio"]))
        observed_row = lookup.get(key)
        for output_metric, reference_metric in metrics:
            observed = None if observed_row is None else observed_row[output_metric]
            paper = float(expected[reference_metric])
            difference = None if observed is None else abs(float(observed) - paper)
            comparisons.append(
                {
                    "point_count": key[0],
                    "outlier_ratio": key[1],
                    "metric": output_metric,
                    "observed": observed,
                    "paper_reference": paper,
                    "absolute_difference": difference,
                    "relative_difference": (
                        None if difference is None or paper == 0.0 else difference / paper
                    ),
                }
            )
    return comparisons


def write_comparison(path: Path, rows) -> None:
    fields = (
        "point_count",
        "outlier_ratio",
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


__all__ = [
    "compare_with_reference",
    "summarize_records",
    "table_rows",
    "write_comparison",
    "write_raw_records",
    "write_summary",
    "write_tex_table",
]
