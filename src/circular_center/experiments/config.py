"""Validation for the deliberately small outer experiment YAML."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Tuple

import yaml

_TOP_LEVEL_KEYS = frozenset({"schema_version", "experiment", "datasets", "methods"})
_METHOD_KEYS = frozenset({"2d", "3d", "ambiguity"})
_SAFE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class ExperimentConfigurationError(ValueError):
    """Raised when the outer experiment selection is malformed."""


@dataclass(frozen=True)
class ExperimentSelection:
    """Only the choices shared by all experiments live in the outer YAML."""

    name: str
    datasets: Tuple[str, ...]
    center2d_method: str
    center3d_method: str
    ambiguity_method: Optional[str]
    source: Path


def _nonempty_string(value, label: str, source: Path) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExperimentConfigurationError(
            "{}: {} must be a non-empty string".format(source, label)
        )
    return value


def load_experiment_selection(source: Path) -> ExperimentSelection:
    path = Path(source).expanduser().resolve()
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ExperimentConfigurationError(
            "cannot read experiment config {}: {}".format(path, error)
        ) from error
    if not isinstance(document, dict) or set(document) != _TOP_LEVEL_KEYS:
        raise ExperimentConfigurationError(
            "{}: expected exactly {}".format(path, sorted(_TOP_LEVEL_KEYS))
        )
    if document["schema_version"] != 1:
        raise ExperimentConfigurationError(
            "{}: unsupported schema_version {!r}".format(path, document["schema_version"])
        )

    experiment = _nonempty_string(document["experiment"], "experiment", path)
    if _SAFE_NAME.fullmatch(experiment) is None:
        raise ExperimentConfigurationError(
            "{}: experiment must use lowercase letters, digits, and underscores".format(path)
        )
    datasets = document["datasets"]
    if not isinstance(datasets, list) or not datasets:
        raise ExperimentConfigurationError("{}: datasets must be a non-empty list".format(path))
    dataset_names = tuple(
        _nonempty_string(dataset, "datasets entry", path) for dataset in datasets
    )
    if len(set(dataset_names)) != len(dataset_names):
        raise ExperimentConfigurationError("{}: datasets must be unique".format(path))

    methods = document["methods"]
    if not isinstance(methods, Mapping) or set(methods) != _METHOD_KEYS:
        raise ExperimentConfigurationError(
            "{}: methods must contain exactly {}".format(path, sorted(_METHOD_KEYS))
        )
    ambiguity = methods["ambiguity"]
    if ambiguity is not None:
        ambiguity = _nonempty_string(ambiguity, "methods.ambiguity", path)
    return ExperimentSelection(
        name=experiment,
        datasets=dataset_names,
        center2d_method=_nonempty_string(methods["2d"], "methods.2d", path),
        center3d_method=_nonempty_string(methods["3d"], "methods.3d", path),
        ambiguity_method=ambiguity,
        source=path,
    )


__all__ = [
    "ExperimentConfigurationError",
    "ExperimentSelection",
    "load_experiment_selection",
]
