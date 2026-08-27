"""Self-contained runner for the paper's first 3D center experiment."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Dict, Mapping, Sequence

import numpy as np

from circular_center.experiments import ExperimentContext
from circular_center.methods.center3d import PCLUnavailableError

from .generators import (
    CircleSample,
    add_reference_outliers,
    generate_monte_carlo_sample,
    generate_outlier_base_samples,
    make_generator,
)
from .protocol import load_profile, load_protocol
from .reporting import (
    compare_with_reference,
    plot_monte_carlo,
    summarize_records,
    write_comparison_csv,
    write_outlier_table,
    write_raw_records,
)


def _normal_error_degrees(actual: np.ndarray, expected: np.ndarray) -> float:
    actual = np.asarray(actual, dtype=float)
    expected = np.asarray(expected, dtype=float)
    actual /= np.linalg.norm(actual)
    expected /= np.linalg.norm(expected)
    cosine = abs(float(np.dot(actual, expected)))
    return float(np.rad2deg(np.arccos(np.clip(cosine, -1.0, 1.0))))


def _fit_record(
    method: Any,
    sample: CircleSample,
    *,
    study: str,
    setting: str,
    panel: str,
    trial: int,
) -> Mapping[str, Any]:
    record = {
        "study": study,
        "setting": setting,
        "panel": panel,
        "trial": trial,
        "method": method.name,
        "success": False,
        "center_error_m": None,
        "radius_error_m": None,
        "normal_error_deg": None,
        "inlier_count": None,
        "iterations": None,
        "elapsed_seconds": None,
        "error_type": None,
        "error": None,
    }
    started = perf_counter()
    try:
        result = method.fit(sample.points)
    except PCLUnavailableError:
        raise
    except Exception as error:
        record["elapsed_seconds"] = perf_counter() - started
        record["error_type"] = type(error).__name__
        record["error"] = str(error)
        return record

    record.update(
        success=True,
        center_error_m=float(np.linalg.norm(result.center - sample.center)),
        radius_error_m=float(abs(result.radius - sample.radius)),
        normal_error_deg=_normal_error_degrees(result.normal, sample.normal),
        inlier_count=int(np.count_nonzero(result.inlier_mask)),
        iterations=int(result.iterations),
        elapsed_seconds=float(result.elapsed_seconds),
    )
    return record


def _study_method_names(
    selected: Sequence[str], protocol: Mapping[str, Any], study: str
) -> Sequence[str]:
    applicability = protocol["method_applicability"]
    return tuple(
        name
        for name in selected
        if name not in applicability or study in applicability[name]
    )


def _create_methods(
    context: ExperimentContext,
    protocol: Mapping[str, Any],
    study: str,
) -> Sequence[Any]:
    selected = tuple(method.name for method in context.methods_for("3d"))
    parameters = protocol["method_parameters"].get(study, {})
    return tuple(
        context.create_method("3d", name, parameters.get(name, {}))
        for name in _study_method_names(selected, protocol, study)
    )


def _run_monte_carlo(
    context: ExperimentContext,
    protocol: Mapping[str, Any],
    trial_count: int,
) -> Sequence[Mapping[str, Any]]:
    methods = _create_methods(context, protocol, "monte_carlo")
    if not methods:
        raise ValueError("synthetic monte_carlo has no applicable selected 3D methods")
    records = []
    for scenario in protocol["monte_carlo"]["scenarios"]:
        scenario_name = str(scenario["name"])
        print("monte_carlo {}: {} trials".format(scenario_name, trial_count), flush=True)
        truth_generator = make_generator(int(protocol["seed"]))
        for trial in range(trial_count):
            sample = generate_monte_carlo_sample(truth_generator, scenario)
            for method in methods:
                records.append(
                    _fit_record(
                        method,
                        sample,
                        study="monte_carlo",
                        setting=scenario_name,
                        panel=str(scenario["panel"]),
                        trial=trial,
                    )
                )
    return records


def _run_outlier(
    context: ExperimentContext,
    protocol: Mapping[str, Any],
    profile: Mapping[str, Any],
    trial_count: int,
) -> Sequence[Mapping[str, Any]]:
    methods = _create_methods(context, protocol, "outlier")
    if not methods:
        raise ValueError("synthetic outlier study has no applicable selected 3D methods")
    configuration = protocol["outlier"]
    base_samples = generate_outlier_base_samples(
        int(protocol["seed"]), trial_count, configuration["base_circle"]
    )
    outlier_generator = make_generator(int(protocol["seed"]) + 1)
    records = []
    for ratio in profile["outlier_ratios"]:
        ratio = float(ratio)
        print("outlier {:.0f}%: {} trials".format(100.0 * ratio, trial_count), flush=True)
        for trial, base_sample in enumerate(base_samples):
            sample = add_reference_outliers(
                base_sample,
                ratio,
                outlier_generator,
                int(configuration["integer_coordinate_min"]),
                int(configuration["integer_coordinate_max"]),
            )
            for method in methods:
                records.append(
                    _fit_record(
                        method,
                        sample,
                        study="outlier",
                        setting=str(ratio),
                        panel="",
                        trial=trial,
                    )
                )
    return records


def _run_profile(
    context: ExperimentContext,
    protocol: Mapping[str, Any],
    profile_name: str,
) -> Mapping[str, Any]:
    profile = load_profile(context.experiment_directory, profile_name)
    monte_carlo_trials = int(profile["monte_carlo_trials"])
    outlier_trials = int(profile["outlier_trials"])
    if context.max_frames is not None:
        monte_carlo_trials = min(monte_carlo_trials, context.max_frames)
        outlier_trials = min(outlier_trials, context.max_frames)

    output_directory = context.output_directory / profile_name
    output_directory.mkdir(parents=True, exist_ok=True)
    records = list(_run_monte_carlo(context, protocol, monte_carlo_trials))
    records.extend(_run_outlier(context, protocol, profile, outlier_trials))
    groups = summarize_records(records)

    raw_path = output_directory / "raw_results.csv"
    monte_pdf_path = output_directory / "3d-monte.pdf"
    monte_png_path = output_directory / "3d-monte.png"
    outlier_csv_path = output_directory / "outlier_summary.csv"
    outlier_tex_path = output_directory / "outlier_table.tex"
    comparison_path = output_directory / "paper_comparison.csv"
    write_raw_records(raw_path, records)
    plot_monte_carlo(
        monte_pdf_path,
        monte_png_path,
        groups,
        protocol["monte_carlo"]["scenarios"],
        protocol["paper_outputs"]["monte_carlo"],
    )
    write_outlier_table(
        outlier_csv_path,
        outlier_tex_path,
        groups,
        tuple(float(value) for value in profile["outlier_ratios"]),
        protocol["paper_outputs"]["outlier"],
    )

    comparisons = []
    if profile["compare_to_paper_reference"]:
        comparisons = compare_with_reference(
            groups, protocol["paper_reference"], protocol["paper_outputs"]
        )
        write_comparison_csv(comparison_path, comparisons)

    return {
        "profile": profile_name,
        "monte_carlo_trials_per_scenario": monte_carlo_trials,
        "outlier_trials_per_ratio": outlier_trials,
        "outlier_ratios": tuple(float(value) for value in profile["outlier_ratios"]),
        "record_count": len(records),
        "groups": groups,
        "paper_comparison": comparisons,
        "artifacts": {
            "raw_results_csv": raw_path.relative_to(context.output_directory),
            "monte_carlo_pdf": monte_pdf_path.relative_to(context.output_directory),
            "monte_carlo_png": monte_png_path.relative_to(context.output_directory),
            "outlier_summary_csv": outlier_csv_path.relative_to(context.output_directory),
            "outlier_table_tex": outlier_tex_path.relative_to(context.output_directory),
            "paper_comparison_csv": (
                comparison_path.relative_to(context.output_directory)
                if comparisons
                else None
            ),
        },
    }


def run(context: ExperimentContext) -> Dict[str, Any]:
    if context.methods_for("2d") or context.methods_for("ambiguity"):
        raise ValueError("synthetic_3d_accuracy requires methods.2d and ambiguity to be null")
    if not context.methods_for("3d"):
        raise ValueError("synthetic_3d_accuracy requires at least one 3D method")

    protocol = load_protocol(context.experiment_directory)
    profiles = [
        _run_profile(context, protocol, profile_name)
        for profile_name in context.selection.datasets
    ]
    selected_methods = [method.name for method in context.methods_for("3d")]
    return {
        "schema_version": 1,
        "experiment": context.selection.name,
        "methods": {"2d": None, "3d": selected_methods, "ambiguity": None},
        "profiles": profiles,
        "reproducibility": protocol["reproducibility"],
        "console_summary": {
            "experiment": context.selection.name,
            "methods": selected_methods,
            "profiles": [
                {
                    "profile": profile["profile"],
                    "records": profile["record_count"],
                    "monte_carlo_trials_per_scenario": profile[
                        "monte_carlo_trials_per_scenario"
                    ],
                    "outlier_trials_per_ratio": profile["outlier_trials_per_ratio"],
                }
                for profile in profiles
            ],
        },
    }


__all__ = ["run"]
