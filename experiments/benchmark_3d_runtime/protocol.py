"""Load and validate the Table III benchmark protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

import yaml


class ProtocolConfigurationError(ValueError):
    """Raised when a runtime protocol or profile is malformed."""


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
            "input",
            "method_order",
            "method_parameters",
            "paper_outputs",
            "paper_reference",
            "reproducibility",
        },
        path,
    )
    if document["schema_version"] != 1 or not isinstance(document["seed"], int):
        raise ProtocolConfigurationError("{}: invalid schema version or seed".format(path))
    _expect_keys(document["input"], {"point_count", "radius_m", "noise_sigma_m"}, path)
    if int(document["input"]["point_count"]) != 64:
        raise ProtocolConfigurationError("{}: Table III requires n=64".format(path))
    if not isinstance(document["method_order"], list) or not document["method_order"]:
        raise ProtocolConfigurationError("{}: method_order must be non-empty".format(path))
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
            "unknown runtime profile {!r}; available profiles: {}".format(
                name, ", ".join(available)
            )
        )
    document = _load_yaml(path)
    _expect_keys(
        document,
        {
            "schema_version",
            "name",
            "timed_repetitions",
            "warmup_repetitions_per_process",
            "process_repetitions",
            "compare_to_paper_reference",
        },
        path,
    )
    if document["schema_version"] != 1 or document["name"] != name:
        raise ProtocolConfigurationError("{}: profile identity is inconsistent".format(path))
    for key in (
        "timed_repetitions",
        "warmup_repetitions_per_process",
        "process_repetitions",
    ):
        if not isinstance(document[key], int) or document[key] < (0 if key.startswith("warmup") else 1):
            raise ProtocolConfigurationError("{}: invalid {}".format(path, key))
    if document["process_repetitions"] > document["timed_repetitions"]:
        raise ProtocolConfigurationError("{}: more processes than timed repetitions".format(path))
    if not isinstance(document["compare_to_paper_reference"], bool):
        raise ProtocolConfigurationError("{}: comparison flag must be boolean".format(path))
    return document


__all__ = ["ProtocolConfigurationError", "load_profile", "load_protocol"]
