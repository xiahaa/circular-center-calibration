"""Load and validate the experiment-owned synthetic 3D protocol YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

import yaml


class ProtocolConfigurationError(ValueError):
    """Raised when an experiment-local protocol or profile is malformed."""


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ProtocolConfigurationError("cannot read {}: {}".format(path, error)) from error
    if not isinstance(document, dict):
        raise ProtocolConfigurationError("{}: document must be a mapping".format(path))
    return document


def _expect_keys(document: Mapping[str, Any], expected, path: Path) -> None:
    actual = set(document)
    expected = set(expected)
    if actual != expected:
        raise ProtocolConfigurationError(
            "{}: expected exactly {}, got {}".format(path, sorted(expected), sorted(actual))
        )


def load_protocol(experiment_directory: Path) -> Dict[str, Any]:
    """Return the shared paper protocol after structural validation."""

    path = Path(experiment_directory) / "protocol.yaml"
    document = _load_yaml(path)
    _expect_keys(
        document,
        {
            "schema_version",
            "seed",
            "monte_carlo",
            "outlier",
            "method_applicability",
            "method_parameters",
            "paper_outputs",
            "paper_reference",
            "reproducibility",
        },
        path,
    )
    if document["schema_version"] != 1:
        raise ProtocolConfigurationError("{}: unsupported schema_version".format(path))
    if not isinstance(document["seed"], int):
        raise ProtocolConfigurationError("{}: seed must be an integer".format(path))
    scenarios = document["monte_carlo"].get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ProtocolConfigurationError(
            "{}: monte_carlo.scenarios must be a non-empty list".format(path)
        )
    scenario_names = []
    for scenario in scenarios:
        if not isinstance(scenario, Mapping):
            raise ProtocolConfigurationError("{}: each scenario must be a mapping".format(path))
        _expect_keys(
            scenario,
            {"name", "panel", "point_count", "noise_sigma_m", "distribution", "arc_degrees"},
            path,
        )
        scenario_names.append(scenario["name"])
        if int(scenario["point_count"]) < 3 or float(scenario["noise_sigma_m"]) < 0.0:
            raise ProtocolConfigurationError("{}: invalid scenario counts or noise".format(path))
    if len(set(scenario_names)) != len(scenario_names):
        raise ProtocolConfigurationError("{}: scenario names must be unique".format(path))

    outlier = document["outlier"]
    _expect_keys(
        outlier,
        {"base_circle", "integer_coordinate_min", "integer_coordinate_max"},
        path,
    )
    _expect_keys(
        outlier["base_circle"],
        {
            "point_count",
            "noise_sigma_m",
            "center_min_m",
            "center_max_m",
            "radius_min_m",
            "radius_max_m",
        },
        path,
    )
    for key in (
        "method_applicability",
        "method_parameters",
        "paper_outputs",
        "paper_reference",
        "reproducibility",
    ):
        if not isinstance(document[key], Mapping):
            raise ProtocolConfigurationError("{}: {} must be a mapping".format(path, key))
    return document


def load_profile(experiment_directory: Path, name: str) -> Dict[str, Any]:
    """Load one small execution profile selected through outer ``datasets``."""

    path = Path(experiment_directory) / "profiles" / "{}.yaml".format(name)
    if not path.is_file():
        available = sorted(item.stem for item in path.parent.glob("*.yaml"))
        raise ProtocolConfigurationError(
            "unknown synthetic profile {!r}; available profiles: {}".format(
                name, ", ".join(available)
            )
        )
    document = _load_yaml(path)
    _expect_keys(
        document,
        {
            "schema_version",
            "name",
            "monte_carlo_trials",
            "outlier_trials",
            "outlier_ratios",
            "compare_to_paper_reference",
        },
        path,
    )
    if document["schema_version"] != 1 or document["name"] != name:
        raise ProtocolConfigurationError("{}: profile identity is inconsistent".format(path))
    for key in ("monte_carlo_trials", "outlier_trials"):
        if not isinstance(document[key], int) or document[key] <= 0:
            raise ProtocolConfigurationError("{}: {} must be positive".format(path, key))
    ratios = document["outlier_ratios"]
    if not isinstance(ratios, list) or not ratios:
        raise ProtocolConfigurationError("{}: outlier_ratios must be non-empty".format(path))
    if any(not 0.0 < float(ratio) <= 1.0 for ratio in ratios):
        raise ProtocolConfigurationError("{}: outlier ratios must be in (0, 1]".format(path))
    if not isinstance(document["compare_to_paper_reference"], bool):
        raise ProtocolConfigurationError(
            "{}: compare_to_paper_reference must be boolean".format(path)
        )
    return document


__all__ = [
    "ProtocolConfigurationError",
    "load_profile",
    "load_protocol",
]
