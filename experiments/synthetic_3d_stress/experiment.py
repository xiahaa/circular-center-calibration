"""Run the synthetic 3D angular-support stress experiment from Figure 6."""

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
    plot_heatmap,
    summarize_records,
    write_comparison_csv,
    write_raw_records,
    write_summary_csv,
)


@contextmanager
def _silence_native_stderr(enabled: bool):
    """Suppress repetitive PCL optimizer diagnostics while preserving restoration."""

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
        context.create_method("3d", selection.name, parameters.get(selection.name, {}))
        for selection in context.methods_for("3d")
    )


def _fit_record(
    method: Any,
    sample: Any,
    *,
    distribution: str,
    point_count: int,
    arc_degrees: int,
    trial: int,
    threshold_m: float,
) -> Mapping[str, Any]:
    record = {
        "distribution": distribution,
        "point_count": point_count,
        "arc_degrees": arc_degrees,
        "trial": trial,
        "method": method.name,
        "fit_success": False,
        "center_error_m": None,
        "below_threshold": False,
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
    center_error = float(np.linalg.norm(result.center - sample.center))
    record.update(
        fit_success=True,
        center_error_m=center_error,
        below_threshold=center_error < float(threshold_m),
        elapsed_seconds=float(result.elapsed_seconds),
    )
    return record


def _run_profile(
    context: ExperimentContext,
    protocol: Mapping[str, Any],
    profile_name: str,
) -> Mapping[str, Any]:
    profile = load_profile(context.experiment_directory, profile_name)
    trials = int(profile["trials_per_cell"])
    if context.max_frames is not None:
        trials = min(trials, context.max_frames)
    methods = _create_methods(context, protocol)
    selected_distributions = tuple(str(value) for value in profile["distributions"])
    by_name = {str(value["name"]): value for value in protocol["distributions"]}
    unknown = sorted(set(selected_distributions) - set(by_name))
    if unknown:
        raise ValueError("unknown stress distributions: {}".format(", ".join(unknown)))

    point_counts = tuple(int(value) for value in profile["point_counts"])
    arc_degrees = tuple(int(value) for value in profile["arc_degrees"])
    radius = float(protocol["circle"]["radius_m"])
    noise_sigma = radius * float(protocol["circle"]["noise_sigma_over_radius"])
    threshold = float(protocol["success_threshold_m"])
    records = []
    has_pcl = any(method.name == "PCL SACMODEL" for method in methods)
    with _silence_native_stderr(has_pcl):
        for distribution_index, distribution in enumerate(selected_distributions):
            for point_count in point_counts:
                for arc in arc_degrees:
                    print(
                        "{}: n={}, arc={} deg, {} trials".format(
                            distribution, point_count, arc, trials
                        ),
                        flush=True,
                    )
                    seed_arc = 0 if distribution == "full_circle_uniform" else arc
                    for trial in range(trials):
                        seed = derive_trial_seed(
                            int(protocol["seed"]),
                            distribution_index,
                            point_count,
                            seed_arc,
                            trial,
                        )
                        sample = generate_sample(
                            seed,
                            distribution=distribution,
                            point_count=point_count,
                            arc_degrees=arc,
                            radius_m=radius,
                            noise_sigma_m=noise_sigma,
                            center_min_m=float(protocol["circle"]["center_min_m"]),
                            center_max_m=float(protocol["circle"]["center_max_m"]),
                            band_jitter_degrees=float(
                                protocol["circle"]["band_jitter_degrees"]
                            ),
                        )
                        for method in methods:
                            records.append(
                                _fit_record(
                                    method,
                                    sample,
                                    distribution=distribution,
                                    point_count=point_count,
                                    arc_degrees=arc,
                                    trial=trial,
                                    threshold_m=threshold,
                                )
                            )

    rows = summarize_records(records)
    output = context.output_directory / profile_name
    output.mkdir(parents=True, exist_ok=True)
    raw_path = output / "raw_results.csv"
    summary_path = output / "cell_summary.csv"
    pdf_path = output / str(protocol["paper_outputs"]["pdf"])
    png_path = output / str(protocol["paper_outputs"]["png"])
    comparison_path = output / "paper_comparison.csv"
    write_raw_records(raw_path, records)
    write_summary_csv(summary_path, rows)
    plot_heatmap(
        pdf_path,
        png_path,
        rows,
        point_counts,
        arc_degrees,
        tuple(by_name[name] for name in selected_distributions),
        tuple(method.name for method in methods),
    )
    comparisons = []
    if profile["compare_to_paper_reference"]:
        comparisons = compare_with_reference(
            rows, protocol["paper_reference"], point_counts, arc_degrees
        )
        write_comparison_csv(comparison_path, comparisons)
    return {
        "profile": profile_name,
        "trials_per_cell": trials,
        "point_counts": point_counts,
        "arc_degrees": arc_degrees,
        "distributions": selected_distributions,
        "cell_count": len(rows),
        "record_count": len(records),
        "cell_summary": rows,
        "paper_comparison": comparisons,
        "artifacts": {
            "raw_results_csv": raw_path.relative_to(context.output_directory),
            "cell_summary_csv": summary_path.relative_to(context.output_directory),
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
        raise ValueError("synthetic_3d_stress requires methods.2d and ambiguity to be null")
    if not context.methods_for("3d"):
        raise ValueError("synthetic_3d_stress requires at least one 3D method")
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
                    "cells": profile["cell_count"],
                    "trials_per_cell": profile["trials_per_cell"],
                }
                for profile in profiles
            ],
        },
    }


__all__ = ["run"]
