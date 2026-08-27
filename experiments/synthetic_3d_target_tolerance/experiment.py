"""Run the Figure 7 synthetic target-tolerance experiment."""

from __future__ import annotations

import os
from contextlib import contextmanager
from time import perf_counter
from typing import Any, Dict, Mapping, Sequence

import numpy as np

from circular_center.experiments import ExperimentContext
from circular_center.methods.center3d import PCLUnavailableError

from .generators import derive_trial_seed, generate_sample
from .protocol import load_profile, load_protocol
from .reporting import (
    compare_with_reference,
    plot_tolerance,
    summarize_records,
    write_comparison_csv,
    write_raw_records,
    write_summary_csv,
)


@contextmanager
def _silence_native_stderr(enabled: bool):
    if not enabled:
        yield
        return
    saved = os.dup(2)
    null = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(null, 2)
        yield
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.close(null)


def _create_methods(context: ExperimentContext, protocol: Mapping[str, Any]) -> Sequence[Any]:
    parameters = protocol["method_parameters"]
    return tuple(
        context.create_method("3d", method.name, parameters.get(method.name, {}))
        for method in context.methods_for("3d")
    )


def _fit_record(
    method: Any,
    sample: Any,
    *,
    deformation: str,
    magnitude: float,
    trial: int,
) -> Mapping[str, Any]:
    record = {
        "deformation": deformation,
        "magnitude": magnitude,
        "trial": trial,
        "method": method.name,
        "success": False,
        "center_error_m": None,
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
        elapsed_seconds=float(result.elapsed_seconds),
    )
    return record


def _run_profile(
    context: ExperimentContext,
    protocol: Mapping[str, Any],
    profile_name: str,
) -> Mapping[str, Any]:
    profile = load_profile(context.experiment_directory, profile_name)
    trials = int(profile["trials_per_setting"])
    if context.max_frames is not None:
        trials = min(trials, context.max_frames)
    magnitudes = tuple(float(value) for value in profile["magnitudes"])
    methods = _create_methods(context, protocol)
    target = protocol["target"]
    radius = float(target["radius_m"])
    noise_sigma = radius * float(target["noise_sigma_over_radius"])
    records = []
    has_pcl = any(method.name == "PCL SACMODEL" for method in methods)
    with _silence_native_stderr(has_pcl):
        for deformation in protocol["deformations"]:
            for magnitude in magnitudes:
                print(
                    "{}: magnitude={}, {} trials".format(
                        deformation, magnitude, trials
                    ),
                    flush=True,
                )
                for trial in range(trials):
                    sample = generate_sample(
                        derive_trial_seed(int(protocol["seed"]), trial),
                        deformation=str(deformation),
                        magnitude=magnitude,
                        point_count=int(target["point_count"]),
                        arc_degrees=float(target["visible_arc_degrees"]),
                        radius_m=radius,
                        noise_sigma_m=noise_sigma,
                        center_min_m=float(target["center_min_m"]),
                        center_max_m=float(target["center_max_m"]),
                        axis_semiaxis_scale=float(target["axis_semiaxis_scale"]),
                    )
                    for method in methods:
                        records.append(
                            _fit_record(
                                method,
                                sample,
                                deformation=str(deformation),
                                magnitude=magnitude,
                                trial=trial,
                            )
                        )

    rows = summarize_records(records)
    output = context.output_directory / profile_name
    output.mkdir(parents=True, exist_ok=True)
    raw_path = output / "raw_results.csv"
    summary_path = output / "tolerance_summary.csv"
    pdf_path = output / str(protocol["paper_outputs"]["pdf"])
    png_path = output / str(protocol["paper_outputs"]["png"])
    comparison_path = output / "paper_comparison.csv"
    write_raw_records(raw_path, records)
    write_summary_csv(summary_path, rows)
    plot_tolerance(
        pdf_path,
        png_path,
        rows,
        magnitudes,
        tuple(method.name for method in methods),
        float(protocol["boundary_m"]),
    )
    comparisons = []
    if profile["compare_to_paper_reference"]:
        comparisons = compare_with_reference(
            rows, protocol["paper_reference"], magnitudes
        )
        write_comparison_csv(comparison_path, comparisons)
    return {
        "profile": profile_name,
        "trials_per_setting": trials,
        "magnitudes": magnitudes,
        "record_count": len(records),
        "setting_count": len(rows),
        "tolerance_summary": rows,
        "paper_comparison": comparisons,
        "artifacts": {
            "raw_results_csv": raw_path.relative_to(context.output_directory),
            "tolerance_summary_csv": summary_path.relative_to(context.output_directory),
            "figure_pdf": pdf_path.relative_to(context.output_directory),
            "figure_png": png_path.relative_to(context.output_directory),
            "paper_comparison_csv": (
                comparison_path.relative_to(context.output_directory)
                if comparisons
                else None
            ),
        },
    }


def run(context: ExperimentContext) -> Dict[str, Any]:
    if context.methods_for("2d") or context.methods_for("ambiguity"):
        raise ValueError(
            "synthetic_3d_target_tolerance requires methods.2d and ambiguity to be null"
        )
    if not context.methods_for("3d"):
        raise ValueError("synthetic_3d_target_tolerance requires 3D methods")
    protocol = load_protocol(context.experiment_directory)
    profiles = [
        _run_profile(context, protocol, profile_name)
        for profile_name in context.selection.datasets
    ]
    methods = [method.name for method in context.methods_for("3d")]
    return {
        "schema_version": 1,
        "experiment": context.selection.name,
        "methods": {"2d": None, "3d": methods, "ambiguity": None},
        "profiles": profiles,
        "reproducibility": protocol["reproducibility"],
        "console_summary": {
            "experiment": context.selection.name,
            "methods": methods,
            "profiles": [
                {
                    "profile": profile["profile"],
                    "records": profile["record_count"],
                    "settings": profile["setting_count"],
                    "trials_per_setting": profile["trials_per_setting"],
                }
                for profile in profiles
            ],
        },
    }


__all__ = ["run"]
