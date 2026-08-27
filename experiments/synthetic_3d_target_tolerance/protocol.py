"""Load and validate the Figure 7 target-tolerance protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

import yaml


class ProtocolConfigurationError(ValueError):
    """Raised when the experiment-local protocol is malformed."""


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ProtocolConfigurationError("cannot read {}: {}".format(path, error)) from error
    if not isinstance(document, dict):
        raise ProtocolConfigurationError("{}: document must be a mapping".format(path))
    return document


def _expect_keys(document: Mapping[str, Any], expected, path: Path) -> None:
    if set(document) != set(expected):
        raise ProtocolConfigurationError(
            "{}: expected exactly {}, got {}".format(
                path, sorted(expected), sorted(document)
            )
        )


def load_protocol(experiment_directory: Path) -> Dict[str, Any]:
    path = Path(experiment_directory) / "protocol.yaml"
    document = _load_yaml(path)
    _expect_keys(
        document,
        {
            "schema_version",
            "seed",
            "target",
            "deformations",
            "boundary_m",
            "method_parameters",
            "paper_outputs",
            "paper_reference",
            "reproducibility",
        },
        path,
    )
    if document["schema_version"] != 1 or not isinstance(document["seed"], int):
        raise ProtocolConfigurationError("{}: invalid schema version or seed".format(path))
    _expect_keys(
        document["target"],
        {
            "radius_m",
            "point_count",
            "visible_arc_degrees",
            "noise_sigma_over_radius",
            "center_min_m",
            "center_max_m",
            "axis_semiaxis_scale",
        },
        path,
    )
    if float(document["target"]["radius_m"]) <= 0.0:
        raise ProtocolConfigurationError("{}: radius must be positive".format(path))
    deformations = document["deformations"]
    if not isinstance(deformations, list) or set(deformations) != {
        "normal_warp",
        "axis_deviation",
    }:
        raise ProtocolConfigurationError("{}: invalid deformation list".format(path))
    for key in (
        "method_parameters",
        "paper_outputs",
        "paper_reference",
        "reproducibility",
    ):
        if not isinstance(document[key], Mapping):
            raise ProtocolConfigurationError("{}: {} must be a mapping".format(path, key))
    return document


def load_profile(experiment_directory: Path, name: str) -> Dict[str, Any]:
    path = Path(experiment_directory) / "profiles" / "{}.yaml".format(name)
    if not path.is_file():
        available = sorted(item.stem for item in path.parent.glob("*.yaml"))
        raise ProtocolConfigurationError(
            "unknown tolerance profile {!r}; available profiles: {}".format(
                name, ", ".join(available)
            )
        )
    document = _load_yaml(path)
    _expect_keys(
        document,
        {
            "schema_version",
            "name",
            "trials_per_setting",
            "magnitudes",
            "compare_to_paper_reference",
        },
        path,
    )
    if document["schema_version"] != 1 or document["name"] != name:
        raise ProtocolConfigurationError("{}: profile identity is inconsistent".format(path))
    if not isinstance(document["trials_per_setting"], int) or document["trials_per_setting"] <= 0:
        raise ProtocolConfigurationError("{}: trials must be positive".format(path))
    magnitudes = document["magnitudes"]
    if not isinstance(magnitudes, list) or not magnitudes:
        raise ProtocolConfigurationError("{}: magnitudes must be non-empty".format(path))
    if any(not 0.0 <= float(value) <= 0.05 for value in magnitudes):
        raise ProtocolConfigurationError("{}: magnitudes must be in [0, 0.05]".format(path))
    if not isinstance(document["compare_to_paper_reference"], bool):
        raise ProtocolConfigurationError("{}: comparison flag must be boolean".format(path))
    return document


__all__ = ["ProtocolConfigurationError", "load_profile", "load_protocol"]
