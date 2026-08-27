"""Resolve plugins and delegate execution to an experiment-owned module."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Tuple

import numpy as np

from circular_center.registry import MethodCatalog

from .config import ExperimentSelection, load_experiment_selection
from .context import ExperimentContext

_METHOD_KINDS = {"2d": "center2d", "3d": "center3d", "ambiguity": "ambiguity"}


def _find_repository_root(config_path: Path) -> Path:
    for parent in (config_path.parent, *config_path.parents):
        if (parent / "pyproject.toml").is_file() and (parent / "configs").is_dir():
            return parent.resolve()
    raise RuntimeError("cannot locate repository root from {}".format(config_path))


def _load_experiment_module(repository_root: Path, name: str):
    expected = repository_root / "experiments" / name / "experiment.py"
    if not expected.is_file():
        raise RuntimeError("experiment module does not exist: {}".format(expected))
    root_string = str(repository_root)
    if root_string not in sys.path:
        sys.path.insert(0, root_string)
    module = importlib.import_module("experiments.{}.experiment".format(name))
    actual = Path(module.__file__).resolve()
    if actual != expected.resolve():
        raise RuntimeError(
            "loaded experiment module from {}, expected {}".format(actual, expected)
        )
    if not callable(getattr(module, "run", None)):
        raise RuntimeError("{} must define run(context)".format(expected))
    return module


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _instantiate_methods(
    catalog: MethodCatalog, selection: ExperimentSelection
) -> Mapping[str, Tuple[Any, ...]]:
    return {
        stage: tuple(
            catalog.create(name, expected_kind)
            for name in selection.method_names(stage)
        )
        for stage, expected_kind in _METHOD_KINDS.items()
    }


def run_experiment(
    config_path: Path,
    *,
    output_directory: Optional[Path] = None,
    max_frames: Optional[int] = None,
) -> Mapping[str, Any]:
    """Run one selected experiment and persist a JSON-serializable summary."""

    if max_frames is not None and max_frames <= 0:
        raise ValueError("max_frames must be positive")
    selection = load_experiment_selection(config_path)
    repository_root = _find_repository_root(selection.source)
    experiment_directory = repository_root / "experiments" / selection.name
    destination = (
        repository_root / "outputs" / selection.name
        if output_directory is None
        else Path(output_directory).expanduser().resolve()
    )
    destination.mkdir(parents=True, exist_ok=True)

    catalog = MethodCatalog.from_directory(repository_root / "configs" / "methods")
    methods = _instantiate_methods(catalog, selection)
    context = ExperimentContext(
        selection=selection,
        repository_root=repository_root,
        experiment_directory=experiment_directory,
        output_directory=destination,
        methods=methods,
        method_catalog=catalog,
        max_frames=max_frames,
    )
    result = _jsonable(_load_experiment_module(repository_root, selection.name).run(context))
    if not isinstance(result, Mapping):
        raise RuntimeError("experiment run(context) must return a mapping")
    summary_path = destination / "summary.json"
    summary_path.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return result


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a modular circular-center experiment from a small YAML selection."
    )
    parser.add_argument("config", type=Path, help="outer experiment YAML")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="maximum number of image/point-cloud pairs per dataset",
    )
    return parser


def _console_summary(result: Mapping[str, Any]) -> Mapping[str, Any]:
    supplied = result.get("console_summary")
    if isinstance(supplied, Mapping):
        return supplied

    datasets = []
    for dataset in result["datasets"]:
        calibration = dataset["calibration"]
        summary = {
            "dataset": dataset["dataset"],
            "attempted_frames": dataset["attempted_frames"],
            "successful_frames": dataset["successful_frames"],
            "failed_frames": dataset["failed_frames"],
        }
        if calibration is not None:
            summary["calibration"] = {
                "status": calibration["status"],
                "correspondences": calibration["correspondence_count"],
                "inliers": calibration["inlier_count"],
                "mean_reprojection_error_px": calibration[
                    "mean_reprojection_error_px"
                ],
            }
        elif dataset["calibration_failure"] is not None:
            summary["calibration"] = dataset["calibration_failure"]
        else:
            summary["calibration"] = {"status": "insufficient_correspondences"}
        datasets.append(summary)
    return {
        "experiment": result["experiment"],
        "methods": result["methods"],
        "datasets": datasets,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = build_argument_parser().parse_args(argv)
    result = run_experiment(
        arguments.config,
        output_directory=arguments.output_dir,
        max_frames=arguments.max_frames,
    )
    print(json.dumps(_console_summary(result), indent=2, sort_keys=True, allow_nan=False))
    selection = load_experiment_selection(arguments.config)
    destination = (
        _find_repository_root(selection.source) / "outputs" / selection.name
        if arguments.output_dir is None
        else arguments.output_dir.expanduser().resolve()
    )
    print("wrote {}".format(destination / "summary.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["ExperimentContext", "main", "run_experiment"]
