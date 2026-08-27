"""Run Table III with sequential, process-isolated method measurements."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import numpy as np

from circular_center.experiments import ExperimentContext

from .protocol import load_profile, load_protocol
from .reporting import (
    compare_with_reference,
    order_rows,
    summarize_workers,
    write_comparison_csv,
    write_process_csv,
    write_raw_csv,
    write_summary_csv,
    write_tex_table,
)


def _cpu_model() -> str:
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("model name") and ":" in line:
                return line.split(":", 1)[1].strip()
    return platform.processor() or "unknown"


def _pcl_version() -> str:
    try:
        completed = subprocess.run(
            ["pkg-config", "--modversion", "pcl_common"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        completed = None
    if completed is not None and completed.stdout.strip():
        return completed.stdout.strip()
    package_file = Path(sys.prefix) / "lib" / "pkgconfig" / "pcl_common.pc"
    if package_file.is_file():
        for line in package_file.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
    return "unknown"


def _environment_metadata() -> Mapping[str, Any]:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "cpu_model": _cpu_model(),
        "logical_cpu_count": os.cpu_count(),
        "pcl": _pcl_version(),
        "thread_limits": {
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        },
    }


def _split_repetitions(total: int, processes: int) -> Sequence[int]:
    base, remainder = divmod(int(total), int(processes))
    return tuple(base + (1 if index < remainder else 0) for index in range(processes))


def _run_worker(
    context: ExperimentContext,
    protocol: Mapping[str, Any],
    method: str,
    process_index: int,
    timed_repetitions: int,
    warmup_repetitions: int,
) -> Mapping[str, Any]:
    input_configuration = protocol["input"]
    command = [
        sys.executable,
        "-m",
        "experiments.benchmark_3d_runtime.worker",
        "--method",
        method,
        "--method-config-root",
        str(context.repository_root / "configs" / "methods"),
        "--overrides-json",
        json.dumps(protocol["method_parameters"].get(method, {}), separators=(",", ":")),
        "--process-index",
        str(process_index),
        "--timed-repetitions",
        str(timed_repetitions),
        "--warmup-repetitions",
        str(warmup_repetitions),
        "--seed",
        str(protocol["seed"]),
        "--point-count",
        str(input_configuration["point_count"]),
        "--radius-m",
        str(input_configuration["radius_m"]),
        "--noise-sigma-m",
        str(input_configuration["noise_sigma_m"]),
    ]
    environment = os.environ.copy()
    environment.update(
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
    )
    completed = subprocess.run(
        command,
        cwd=context.repository_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "runtime worker failed for {} process {}: {}".format(
                method, process_index, completed.stderr.strip() or completed.stdout.strip()
            )
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "runtime worker returned invalid JSON for {}: {}".format(
                method, completed.stdout
            )
        ) from error


def _run_profile(
    context: ExperimentContext,
    protocol: Mapping[str, Any],
    profile_name: str,
) -> Mapping[str, Any]:
    profile = load_profile(context.experiment_directory, profile_name)
    total = int(profile["timed_repetitions"])
    if context.max_frames is not None:
        total = min(total, context.max_frames)
    process_count = min(int(profile["process_repetitions"]), total)
    repetitions = _split_repetitions(total, process_count)
    selected = {method.name for method in context.methods_for("3d")}
    method_order = [name for name in protocol["method_order"] if name in selected]
    unknown = sorted(selected - set(protocol["method_order"]))
    method_order.extend(unknown)
    workers = []
    for method in method_order:
        for process_index, count in enumerate(repetitions):
            print(
                "{}: isolated process {}/{}, {} timed fits".format(
                    method, process_index + 1, process_count, count
                ),
                flush=True,
            )
            workers.append(
                _run_worker(
                    context,
                    protocol,
                    method,
                    process_index,
                    count,
                    int(profile["warmup_repetitions_per_process"]),
                )
            )

    rows = order_rows(summarize_workers(workers), method_order)
    output = context.output_directory / profile_name
    output.mkdir(parents=True, exist_ok=True)
    raw_path = output / "runtime_records.csv"
    process_path = output / "process_rss.csv"
    summary_path = output / "runtime_summary.csv"
    tex_path = output / str(protocol["paper_outputs"]["tex"])
    environment_path = output / "environment.json"
    comparison_path = output / "paper_comparison.csv"
    write_raw_csv(raw_path, workers)
    write_process_csv(process_path, workers)
    write_summary_csv(summary_path, rows)
    write_tex_table(tex_path, rows, int(protocol["input"]["point_count"]))
    environment_metadata = _environment_metadata()
    environment_path.write_text(
        json.dumps(environment_metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    comparisons = []
    if profile["compare_to_paper_reference"]:
        comparisons = compare_with_reference(rows, protocol["paper_reference"])
        write_comparison_csv(comparison_path, comparisons)
    return {
        "profile": profile_name,
        "timed_repetitions_per_method": total,
        "process_repetitions_per_method": process_count,
        "warmup_repetitions_per_process": int(
            profile["warmup_repetitions_per_process"]
        ),
        "runtime_summary": rows,
        "paper_comparison": comparisons,
        "environment": environment_metadata,
        "artifacts": {
            "runtime_records_csv": raw_path.relative_to(context.output_directory),
            "process_rss_csv": process_path.relative_to(context.output_directory),
            "runtime_summary_csv": summary_path.relative_to(context.output_directory),
            "runtime_table_tex": tex_path.relative_to(context.output_directory),
            "environment_json": environment_path.relative_to(context.output_directory),
            "paper_comparison_csv": (
                comparison_path.relative_to(context.output_directory)
                if comparisons
                else None
            ),
        },
    }


def run(context: ExperimentContext) -> Dict[str, Any]:
    if context.methods_for("2d") or context.methods_for("ambiguity"):
        raise ValueError("benchmark_3d_runtime requires methods.2d and ambiguity to be null")
    if not context.methods_for("3d"):
        raise ValueError("benchmark_3d_runtime requires at least one 3D method")
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
                    "timed_repetitions_per_method": profile[
                        "timed_repetitions_per_method"
                    ],
                    "runtime_summary": profile["runtime_summary"],
                }
                for profile in profiles
            ],
        },
    }


__all__ = ["run"]
