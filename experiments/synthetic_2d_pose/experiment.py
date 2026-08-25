"""Runner for the paper's Figure 9 pose-sensitivity experiment."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Dict, Sequence

import numpy as np

from circular_center.evaluation import PoseEstimate, evaluate_pose, fit_pnp_ransac
from circular_center.experiments import ExperimentContext
from circular_center.interfaces import AmbiguousCorrespondences, EllipseObservation

from .generators import PoseTrial, generate_trial, make_trial_seeds
from .protocol import load_profile, load_protocol
from .reporting import (
    compare_with_reference,
    plot_error_bars,
    summarize_records,
    write_comparison,
    write_method_summary,
    write_raw_records,
)


def _create_methods(context, protocol, kind):
    overrides = protocol["method_parameters"].get(kind, {})
    return tuple(
        context.create_method(kind, name, overrides.get(name, {}))
        for name in context.selection.method_names(kind)
    )


def _empty_record(trial, seed, method, paper_label):
    return {
        "trial": int(trial),
        "seed": int(seed),
        "method": method,
        "paper_label": paper_label,
        "success": False,
        "reprojection_error_px": None,
        "rotation_error_rad": None,
        "translation_error": None,
        "inlier_count": None,
        "iterations": None,
        "elapsed_seconds": None,
        "error_type": None,
        "error": None,
    }


def _measure_centers(
    trial: PoseTrial,
    methods: Sequence[Any],
    homography: Any,
    candidate_source: str,
):
    points3d = []
    points2d = {method.name: [] for method in methods}
    candidate_a = []
    candidate_b = []
    for circle in trial.observations:
        points3d.append(circle.point3d)
        observation = EllipseObservation(
            circle.primary.parameters,
            circle.primary.polynomial,
            trial.intrinsic,
            2.0 * trial.primary_radius,
            contour=circle.primary.mass_contour,
            input_is_rectified=True,
        )
        for method in methods:
            result = method.estimate(observation)
            if len(result.candidates) == 1 or result.selected_index is not None:
                points2d[method.name].append(result.primary)
                continue
            if homography is None:
                raise ValueError(
                    "{} returned multiple candidates but Homography Validation is not "
                    "selected".format(method.name)
                )
            selected, _ = homography.select(
                circle.primary.parameters,
                circle.primary.polynomial,
                circle.primary.contour,
                circle.validation.contour,
                trial.intrinsic,
                trial.primary_radius,
                candidates=result.candidates,
            )
            points2d[method.name].append(selected)
            if method.name == candidate_source:
                candidate_a.append(result.candidates[0])
                candidate_b.append(result.candidates[1])

    if candidate_source not in points2d:
        raise ValueError(
            "candidate_source {!r} is not among the selected 2D methods".format(
                candidate_source
            )
        )
    if len(candidate_a) != len(points3d):
        raise ValueError(
            "candidate source {!r} did not return two candidates for every circle".format(
                candidate_source
            )
        )
    return (
        np.asarray(points3d, dtype=float),
        {name: np.asarray(values, dtype=float) for name, values in points2d.items()},
        np.asarray(candidate_a, dtype=float),
        np.asarray(candidate_b, dtype=float),
    )


def _pnp_record(
    trial_index,
    trial,
    method,
    paper_label,
    points3d,
    points2d,
    pnp,
):
    record = _empty_record(trial_index, trial.seed, method, paper_label)
    started = perf_counter()
    try:
        estimate = fit_pnp_ransac(
            points3d,
            points2d,
            trial.intrinsic,
            iterations=int(pnp["iterations"]),
            reprojection_threshold_px=float(pnp["reprojection_threshold_px"]),
            confidence=float(pnp["confidence"]),
            seed=trial.seed,
        )
        metrics = evaluate_pose(estimate, trial.rotation, trial.translation)
        record.update(
            success=True,
            reprojection_error_px=metrics.reprojection_error_px,
            rotation_error_rad=metrics.rotation_error_rad,
            translation_error=metrics.translation_error,
            inlier_count=int(np.count_nonzero(estimate.inlier_mask)),
            iterations=int(pnp["iterations"]),
            elapsed_seconds=perf_counter() - started,
        )
    except Exception as error:
        record["elapsed_seconds"] = perf_counter() - started
        record["error_type"] = type(error).__name__
        record["error"] = str(error)
    return record


def _quasi_record(
    trial_index,
    trial,
    method,
    paper_label,
    points3d,
    candidate_a,
    candidate_b,
):
    record = _empty_record(trial_index, trial.seed, method.name, paper_label)
    started = perf_counter()
    try:
        result = method.resolve(
            AmbiguousCorrespondences(
                points3d=points3d,
                candidate_a=candidate_a,
                candidate_b=candidate_b,
                intrinsic=trial.intrinsic,
            )
        )
        estimate = PoseEstimate(
            rotation=result.rotation,
            translation=result.translation,
            inlier_mask=result.inlier_mask,
            mean_reprojection_error_px=result.mean_reprojection_error,
        )
        metrics = evaluate_pose(estimate, trial.rotation, trial.translation)
        record.update(
            success=True,
            reprojection_error_px=metrics.reprojection_error_px,
            rotation_error_rad=metrics.rotation_error_rad,
            translation_error=metrics.translation_error,
            inlier_count=int(np.count_nonzero(result.inlier_mask)),
            iterations=int(result.iterations),
            elapsed_seconds=perf_counter() - started,
        )
    except Exception as error:
        record["elapsed_seconds"] = perf_counter() - started
        record["error_type"] = type(error).__name__
        record["error"] = str(error)
    return record


def _run_profile(context, protocol, name, center_methods, ambiguity_methods):
    profile = load_profile(context.experiment_directory, name)
    trial_count = int(profile["trials"])
    if context.max_frames is not None:
        trial_count = min(trial_count, context.max_frames)
    circle_count = int(profile["circles_per_trial"])
    labels = protocol["paper_outputs"]["paper_labels"]
    homography = next(
        (method for method in ambiguity_methods if method.name == "Homography Validation"),
        None,
    )
    quasi_methods = [
        method for method in ambiguity_methods if method.name == "Quasi-RANSAC"
    ]
    result_method_names = [method.name for method in center_methods] + [
        method.name for method in quasi_methods
    ]
    records = []
    seeds = make_trial_seeds(int(protocol["seed"]), trial_count)
    progress_interval = max(1, min(10, trial_count))
    for trial_index, seed in enumerate(seeds):
        try:
            trial = generate_trial(seed, protocol, circle_count)
            points3d, points2d, candidate_a, candidate_b = _measure_centers(
                trial,
                center_methods,
                homography,
                str(protocol["candidate_source"]),
            )
        except Exception as error:
            for method_name in result_method_names:
                record = _empty_record(
                    trial_index, seed, method_name, labels.get(method_name, method_name)
                )
                record["error_type"] = type(error).__name__
                record["error"] = str(error)
                records.append(record)
        else:
            for method in center_methods:
                records.append(
                    _pnp_record(
                        trial_index,
                        trial,
                        method.name,
                        labels.get(method.name, method.name),
                        points3d,
                        points2d[method.name],
                        protocol["pnp"],
                    )
                )
            for method in quasi_methods:
                records.append(
                    _quasi_record(
                        trial_index,
                        trial,
                        method,
                        labels.get(method.name, method.name),
                        points3d,
                        candidate_a,
                        candidate_b,
                    )
                )
        if (trial_index + 1) % progress_interval == 0 or trial_index + 1 == trial_count:
            print(
                "synthetic_2d_pose: {}/{} trials".format(
                    trial_index + 1, trial_count
                ),
                flush=True,
            )

    output = context.output_directory / name
    output.mkdir(parents=True, exist_ok=True)
    groups = summarize_records(records)
    raw_path = output / "raw_results.csv"
    summary_path = output / "method_summary.csv"
    comparison_path = output / "paper_comparison.csv"
    figure_path = output / str(protocol["paper_outputs"]["figure"])
    write_raw_records(raw_path, records)
    write_method_summary(summary_path, groups)
    plot_error_bars(
        figure_path,
        groups,
        protocol["paper_outputs"]["method_order"],
        labels,
        int(protocol["paper_outputs"]["dpi"]),
    )
    comparisons = []
    if profile["compare_to_paper_reference"]:
        comparisons = compare_with_reference(groups, protocol["paper_reference"])
        write_comparison(comparison_path, comparisons)
    return {
        "profile": name,
        "trials": trial_count,
        "circles_per_trial": circle_count,
        "record_count": len(records),
        "groups": groups,
        "paper_comparison": comparisons,
        "artifacts": {
            "raw_results_csv": raw_path.relative_to(context.output_directory),
            "method_summary_csv": summary_path.relative_to(context.output_directory),
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
        raise ValueError("synthetic_2d_pose requires methods.3d to be null")
    if not context.methods_for("2d"):
        raise ValueError("synthetic_2d_pose requires at least one 2D method")
    protocol = load_protocol(context.experiment_directory)
    center_methods = _create_methods(context, protocol, "2d")
    ambiguity_methods = _create_methods(context, protocol, "ambiguity")
    if str(protocol["candidate_source"]) in [
        method.name for method in center_methods
    ] and not any(
        method.name == "Homography Validation" for method in ambiguity_methods
    ):
        raise ValueError(
            "synthetic_2d_pose requires Homography Validation for Refined Center"
        )
    profiles = [
        _run_profile(
            context,
            protocol,
            name,
            center_methods,
            ambiguity_methods,
        )
        for name in context.selection.datasets
    ]
    center_names = [method.name for method in center_methods]
    ambiguity_names = [method.name for method in ambiguity_methods]
    return {
        "schema_version": 1,
        "experiment": context.selection.name,
        "paper_correspondence": "Figure 9",
        "methods": {
            "2d": center_names,
            "3d": None,
            "ambiguity": ambiguity_names,
        },
        "profiles": profiles,
        "reproducibility": protocol["reproducibility"],
        "console_summary": {
            "experiment": context.selection.name,
            "profiles": [
                {
                    "profile": profile["profile"],
                    "trials": profile["trials"],
                    "circles_per_trial": profile["circles_per_trial"],
                    "methods": {
                        group["method"]: {
                            "success_rate": group["success_rate"],
                            "mean_reprojection_error_px": group[
                                "reprojection_error_px"
                            ]["mean"],
                            "mean_rotation_error_rad": group[
                                "rotation_error_rad"
                            ]["mean"],
                            "mean_translation_error": group[
                                "translation_error"
                            ]["mean"],
                        }
                        for group in profile["groups"]
                    },
                }
                for profile in profiles
            ],
        },
    }


__all__ = ["run"]
