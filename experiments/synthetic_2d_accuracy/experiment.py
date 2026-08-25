"""Runner for the paper's direct 2D projected-center experiment."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Dict, Mapping, Sequence

import numpy as np

from circular_center.experiments import ExperimentContext
from circular_center.interfaces import EllipseObservation

from .generators import Synthetic2DSample, generate_sample, make_trial_seeds
from .protocol import load_profile, load_protocol
from .reporting import (
    compare_with_reference,
    plot_error_distribution,
    summarize_records,
    write_comparison_csv,
    write_method_summary,
    write_raw_records,
)


def _create_methods(
    context: ExperimentContext,
    protocol: Mapping[str, Any],
    kind: str,
) -> Sequence[Any]:
    overrides = protocol["method_parameters"].get(kind, {})
    return tuple(
        context.create_method(kind, name, overrides.get(name, {}))
        for name in context.selection.method_names(kind)
    )


def _empty_record(trial: int, seed: int, method: str) -> Dict[str, Any]:
    return {
        "trial": int(trial),
        "seed": int(seed),
        "method": method,
        "success": False,
        "estimate_x_px": None,
        "estimate_y_px": None,
        "ground_truth_x_px": None,
        "ground_truth_y_px": None,
        "error_x_px": None,
        "error_y_px": None,
        "error_magnitude_px": None,
        "candidate_count": None,
        "selected_candidate": None,
        "rejected_x_px": None,
        "rejected_y_px": None,
        "estimate_seconds": None,
        "selection_seconds": None,
        "status": None,
        "error_type": None,
        "error": None,
    }


def _evaluate_method(
    method: Any,
    ambiguity: Any,
    sample: Synthetic2DSample,
    *,
    trial: int,
) -> Mapping[str, Any]:
    record = _empty_record(trial, sample.seed, method.name)
    observation = EllipseObservation(
        ellipse=sample.primary.parameters,
        polynomial=sample.primary.polynomial,
        intrinsic=sample.intrinsic,
        marker_diameter=2.0 * sample.marker_radius,
        contour=sample.primary.mass_contour,
        input_is_rectified=True,
    )
    try:
        started = perf_counter()
        result = method.estimate(observation)
        estimate_seconds = perf_counter() - started
        selection_seconds = 0.0
        rejected = None
        if len(result.candidates) == 1 or result.selected_index is not None:
            selected_index = 0 if result.selected_index is None else result.selected_index
            estimate = result.candidates[selected_index]
        else:
            if ambiguity is None or not callable(getattr(ambiguity, "select", None)):
                raise ValueError(
                    "{} returned multiple candidates but no homography ambiguity method "
                    "was selected".format(method.name)
                )
            selection_started = perf_counter()
            estimate, rejected = ambiguity.select(
                sample.primary.parameters,
                sample.primary.polynomial,
                sample.primary.contour,
                sample.coplanar.contour,
                sample.intrinsic,
                sample.marker_radius,
                candidates=result.candidates,
            )
            selection_seconds = perf_counter() - selection_started
            selected_index = int(
                np.argmin(np.linalg.norm(result.candidates - estimate, axis=1))
            )

        error = np.asarray(estimate, dtype=float) - sample.ground_truth
        record.update(
            success=True,
            estimate_x_px=float(estimate[0]),
            estimate_y_px=float(estimate[1]),
            ground_truth_x_px=float(sample.ground_truth[0]),
            ground_truth_y_px=float(sample.ground_truth[1]),
            error_x_px=float(error[0]),
            error_y_px=float(error[1]),
            error_magnitude_px=float(np.linalg.norm(error)),
            candidate_count=len(result.candidates),
            selected_candidate=selected_index,
            rejected_x_px=(None if rejected is None else float(rejected[0])),
            rejected_y_px=(None if rejected is None else float(rejected[1])),
            estimate_seconds=float(estimate_seconds),
            selection_seconds=float(selection_seconds),
            status=result.status,
        )
    except Exception as error:
        record["error_type"] = type(error).__name__
        record["error"] = str(error)
    return record


def _run_profile(
    context: ExperimentContext,
    protocol: Mapping[str, Any],
    profile_name: str,
    methods: Sequence[Any],
    ambiguity: Any,
) -> Mapping[str, Any]:
    profile = load_profile(context.experiment_directory, profile_name)
    trial_count = int(profile["trials"])
    if context.max_frames is not None:
        trial_count = min(trial_count, context.max_frames)
    output_directory = context.output_directory / profile_name
    output_directory.mkdir(parents=True, exist_ok=True)

    records = []
    seeds = make_trial_seeds(int(protocol["seed"]), trial_count)
    progress_interval = max(1, min(100, trial_count))
    for trial, seed in enumerate(seeds):
        try:
            sample = generate_sample(seed, protocol)
        except Exception as error:
            for method in methods:
                record = _empty_record(trial, seed, method.name)
                record["error_type"] = type(error).__name__
                record["error"] = str(error)
                records.append(record)
        else:
            records.extend(
                _evaluate_method(method, ambiguity, sample, trial=trial)
                for method in methods
            )
        if (trial + 1) % progress_interval == 0 or trial + 1 == trial_count:
            print(
                "synthetic_2d_accuracy: {}/{} trials".format(trial + 1, trial_count),
                flush=True,
            )

    groups = summarize_records(records)
    raw_path = output_directory / "raw_results.csv"
    method_summary_path = output_directory / "method_summary.csv"
    figure_path = output_directory / str(protocol["paper_outputs"]["figure"])
    comparison_path = output_directory / "paper_comparison.csv"
    write_raw_records(raw_path, records)
    write_method_summary(method_summary_path, groups)
    plot_error_distribution(
        figure_path,
        records,
        protocol["paper_outputs"]["method_order"],
        bins=int(protocol["paper_outputs"]["histogram_bins"]),
        dpi=int(protocol["paper_outputs"]["dpi"]),
    )

    comparisons = []
    if profile["compare_to_paper_reference"]:
        comparisons = compare_with_reference(groups, protocol["paper_reference"])
        write_comparison_csv(comparison_path, comparisons)

    return {
        "profile": profile_name,
        "trials": trial_count,
        "record_count": len(records),
        "groups": groups,
        "paper_comparison": comparisons,
        "artifacts": {
            "raw_results_csv": raw_path.relative_to(context.output_directory),
            "method_summary_csv": method_summary_path.relative_to(
                context.output_directory
            ),
            "figure_png": figure_path.relative_to(context.output_directory),
            "paper_comparison_csv": (
                comparison_path.relative_to(context.output_directory)
                if comparisons
                else None
            ),
        },
    }


def run(context: ExperimentContext) -> Dict[str, Any]:
    if context.methods_for("3d"):
        raise ValueError("synthetic_2d_accuracy requires methods.3d to be null")
    if not context.methods_for("2d"):
        raise ValueError("synthetic_2d_accuracy requires at least one 2D method")
    if len(context.methods_for("ambiguity")) > 1:
        raise ValueError("synthetic_2d_accuracy accepts at most one ambiguity method")

    protocol = load_protocol(context.experiment_directory)
    methods = _create_methods(context, protocol, "2d")
    ambiguity_methods = _create_methods(context, protocol, "ambiguity")
    ambiguity = None if not ambiguity_methods else ambiguity_methods[0]
    profiles = [
        _run_profile(context, protocol, name, methods, ambiguity)
        for name in context.selection.datasets
    ]
    method_names = [method.name for method in methods]
    ambiguity_name = None if ambiguity is None else ambiguity.name
    return {
        "schema_version": 1,
        "experiment": context.selection.name,
        "paper_correspondence": "Figure 8",
        "methods": {
            "2d": method_names,
            "3d": None,
            "ambiguity": ambiguity_name,
        },
        "profiles": profiles,
        "reproducibility": protocol["reproducibility"],
        "console_summary": {
            "experiment": context.selection.name,
            "methods": method_names,
            "ambiguity": ambiguity_name,
            "profiles": [
                {
                    "profile": profile["profile"],
                    "trials": profile["trials"],
                    "records": profile["record_count"],
                    "methods": {
                        group["method"]: {
                            "success_rate": group["success_rate"],
                            "mean_error_px": group["error_magnitude_px"]["mean"],
                            "median_error_px": group["error_magnitude_px"]["median"],
                        }
                        for group in profile["groups"]
                    },
                }
                for profile in profiles
            ],
        },
    }


__all__ = ["run"]
