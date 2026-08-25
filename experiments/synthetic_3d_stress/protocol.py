"""Load and validate the experiment-owned Figure 6 protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

import yaml


class ProtocolConfigurationError(ValueError):
    """Raised when the stress protocol or a profile is malformed."""


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
            "circle",
            "distributions",
            "success_threshold_m",
            "method_parameters",
            "paper_outputs",
            "paper_reference",
            "reproducibility",
        },
        path,
    )
    if document["schema_version"] != 1 or not isinstance(document["seed"], int):
        raise ProtocolConfigurationError("{}: invalid schema version or seed".format(path))
    circle = document["circle"]
    _expect_keys(
        circle,
        {
            "radius_m",
            "noise_sigma_over_radius",
            "center_min_m",
            "center_max_m",
            "band_jitter_degrees",
        },
        path,
    )
    if float(circle["radius_m"]) <= 0.0 or float(circle["noise_sigma_over_radius"]) < 0.0:
        raise ProtocolConfigurationError("{}: invalid circle dimensions".format(path))
    distributions = document["distributions"]
    if not isinstance(distributions, list) or not distributions:
        raise ProtocolConfigurationError("{}: distributions must be non-empty".format(path))
    names = []
    for distribution in distributions:
        _expect_keys(distribution, {"name", "label"}, path)
        names.append(str(distribution["name"]))
    if len(names) != len(set(names)):
        raise ProtocolConfigurationError("{}: distribution names must be unique".format(path))
    if float(document["success_threshold_m"]) <= 0.0:
        raise ProtocolConfigurationError("{}: success threshold must be positive".format(path))
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
            "unknown stress profile {!r}; available profiles: {}".format(
                name, ", ".join(available)
            )
        )
    document = _load_yaml(path)
    _expect_keys(
        document,
        {
            "schema_version",
            "name",
            "trials_per_cell",
            "point_counts",
            "arc_degrees",
            "distributions",
            "compare_to_paper_reference",
        },
        path,
    )
    if document["schema_version"] != 1 or document["name"] != name:
        raise ProtocolConfigurationError("{}: profile identity is inconsistent".format(path))
    if not isinstance(document["trials_per_cell"], int) or document["trials_per_cell"] <= 0:
        raise ProtocolConfigurationError("{}: trials_per_cell must be positive".format(path))
    if any(int(value) < 3 for value in document["point_counts"]):
        raise ProtocolConfigurationError("{}: point counts must be at least three".format(path))
    if any(not 0.0 < float(value) <= 360.0 for value in document["arc_degrees"]):
        raise ProtocolConfigurationError("{}: arcs must be in (0, 360]".format(path))
    if not isinstance(document["compare_to_paper_reference"], bool):
        raise ProtocolConfigurationError("{}: comparison flag must be boolean".format(path))
    return document


__all__ = ["ProtocolConfigurationError", "load_profile", "load_protocol"]
