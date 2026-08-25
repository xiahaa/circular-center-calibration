"""Runner for the paper's Table II quasi-RANSAC evaluation."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Dict

import numpy as np

from circular_center.center2d import quasi_ransac_iteration_bound
from circular_center.evaluation import PoseEstimate, evaluate_pose
from circular_center.experiments import ExperimentContext
from circular_center.interfaces import AmbiguousCorrespondences

from .generators import (
    derive_trial_seeds,
    generate_trial,
    rounded_outlier_count,
)
from .protocol import load_profile, load_protocol
from .reporting import (
    compare_with_reference,
    summarize_records,
    table_rows,
    write_comparison,
    write_raw_records,
    write_summary,
    write_tex_table,
)


def _empty_record(point_count, ratio, confidence, trial, sample_seed, method_seed, method):
    outlier_count = rounded_outlier_count(point_count, ratio)
    valid_ratio = (point_count - outlier_count) / float(point_count)
    return {
        "point_count": int(point_count),
        "outlier_ratio": float(ratio),
        "outlier_count": int(outlier_count),
        "confidence": float(confidence),
        "trial": int(trial),
        "sample_seed": int(sample_seed),
        "method_seed": int(method_seed),
        "method": method,
        "fit_success": False,
        "pose_success": False,
        "theoretical_confidence": float(confidence),
        "planned_iterations": None,
        "iterations": None,
        "inlier_count": None,
        "reprojection_error_px": None,
        "rotation_error_deg": None,
        "translation_error_m": None,
        "elapsed_seconds": None,
        "error_type": None,
        "error": None,
        "valid_correspondence_ratio": valid_ratio,
    }


def _run_profile(context, protocol, name, method_names):
    profile = load_profile(context.experiment_directory, name)
    trials = int(profile["trials_per_cell"])
    if context.max_frames is not None:
        trials = min(trials, context.max_frames)
    records = []
    cells = [
        (int(point_count), float(ratio), float(confidence))
        for point_count in profile["point_counts"]
        for ratio in profile["outlier_ratios"]
        for confidence in profile["confidences"]
    ]
    for cell_index, (point_count, ratio, confidence) in enumerate(cells):
        outlier_count = rounded_outlier_count(point_count, ratio)
        valid_ratio = (point_count - outlier_count) / float(point_count)
        for trial_index in range(trials):
            sample_seed, method_seed = derive_trial_seeds(
                int(protocol["seed"]), point_count, ratio, trial_index
            )
            trial = generate_trial(
                sample_seed,
                method_seed,
                point_count,
                ratio,
                protocol,
            )
            for method_name in method_names:
                record = _empty_record(
                    point_count,
                    ratio,
                    confidence,
                    trial_index,
                    sample_seed,
                    method_seed,
                    method_name,
                )
                parameters = dict(protocol["method_parameters"].get(method_name, {}))
                parameters.update(
                    confidence=confidence,
                    valid_correspondence_ratio=valid_ratio,
                    seed=method_seed,
                )
                planned = quasi_ransac_iteration_bound(
                    valid_ratio,
                    confidence,
                    4,
                    int(parameters.get("max_iterations", 2000)),
                )
                record["planned_iterations"] = planned
                started = perf_counter()
                try:
                    method = context.create_method(
                        "ambiguity", method_name, parameters
                    )
                    result = method.resolve(
                        AmbiguousCorrespondences(
                            points3d=trial.points3d,
                            candidate_a=trial.candidate_a,
                            candidate_b=trial.candidate_b,
                            intrinsic=trial.intrinsic,
                        )
                    )
                    estimate = PoseEstimate(
                        rotation=result.rotation,
                        translation=result.translation,
                        inlier_mask=result.inlier_mask,
                        mean_reprojection_error_px=result.mean_reprojection_error,
                    )
                    metrics = evaluate_pose(
                        estimate,
                        trial.expected_rotation,
                        trial.expected_translation,
                    )
                    rotation_error_deg = float(np.rad2deg(metrics.rotation_error_rad))
                    translation_error = float(metrics.translation_error)
                    criteria = protocol["success_criteria"]
                    record.update(
                        fit_success=True,
                        pose_success=(
                            rotation_error_deg
                            < float(criteria["maximum_rotation_error_deg"])
                            and translation_error
                            < float(criteria["maximum_translation_error_m"])
                        ),
                        iterations=int(result.iterations),
                        inlier_count=int(np.count_nonzero(result.inlier_mask)),
                        reprojection_error_px=metrics.reprojection_error_px,
                        rotation_error_deg=rotation_error_deg,
                        translation_error_m=translation_error,
                        elapsed_seconds=float(result.elapsed_seconds),
                    )
                except Exception as error:
                    record["iterations"] = planned
                    record["elapsed_seconds"] = perf_counter() - started
                    record["error_type"] = type(error).__name__
                    record["error"] = str(error)
                records.append(record)
        print(
            "quasi_ransac_evaluation: {}/{} cells (n={}, outliers={:.0f}%, "
            "confidence={})".format(
                cell_index + 1,
                len(cells),
                point_count,
                100.0 * ratio,
                confidence,
            ),
            flush=True,
        )

    output = context.output_directory / name
    output.mkdir(parents=True, exist_ok=True)
    raw_path = output / "raw_results.csv"
    summary_path = output / "full_summary.csv"
    tex_path = output / str(protocol["table"]["tex_filename"])
    comparison_path = output / "paper_comparison.csv"
    summaries = summarize_records(records)
    selected_rows = table_rows(
        summaries,
        str(protocol["table"]["method"]),
        float(protocol["table"]["confidence"]),
    )
    write_raw_records(raw_path, records)
    write_summary(summary_path, summaries)
    write_tex_table(tex_path, selected_rows, float(protocol["table"]["confidence"]))
    comparisons = []
    if profile["compare_to_paper_reference"]:
        comparisons = compare_with_reference(
            selected_rows, protocol["paper_reference"]["rows"]
        )
        write_comparison(comparison_path, comparisons)
    return {
        "profile": name,
        "trials_per_cell": trials,
        "cell_count": len(cells),
        "record_count": len(records),
        "groups": summaries,
        "table_rows": selected_rows,
        "paper_comparison": comparisons,
        "artifacts": {
            "raw_results_csv": raw_path.relative_to(context.output_directory),
            "full_summary_csv": summary_path.relative_to(context.output_directory),
            "table_tex": tex_path.relative_to(context.output_directory),
            "paper_comparison_csv": (
                comparison_path.relative_to(context.output_directory)
                if comparisons
                else None
            ),
        },
    }


def run(context: ExperimentContext) -> Dict[str, Any]:
    if context.methods_for("2d") or context.methods_for("3d"):
        raise ValueError("quasi_ransac_evaluation requires 2d and 3d methods to be null")
    method_names = context.selection.method_names("ambiguity")
    if not method_names:
        raise ValueError("quasi_ransac_evaluation requires an ambiguity method")
    protocol = load_protocol(context.experiment_directory)
    table_method = str(protocol["table"]["method"])
    if table_method not in method_names:
        raise ValueError("the Table II method {!r} must be selected".format(table_method))
    profiles = [
        _run_profile(context, protocol, name, method_names)
        for name in context.selection.datasets
    ]
    return {
        "schema_version": 1,
        "experiment": context.selection.name,
        "paper_correspondence": "Table II",
        "methods": {"2d": None, "3d": None, "ambiguity": list(method_names)},
        "profiles": profiles,
        "reproducibility": protocol["reproducibility"],
        "console_summary": {
            "experiment": context.selection.name,
            "profiles": [
                {
                    "profile": profile["profile"],
                    "trials_per_cell": profile["trials_per_cell"],
                    "cell_count": profile["cell_count"],
                    "table_rows": profile["table_rows"],
                }
                for profile in profiles
            ],
        },
    }


__all__ = ["run"]
