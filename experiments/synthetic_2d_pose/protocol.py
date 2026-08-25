"""Strict loading for the Figure 9 protocol and profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

import yaml


class ProtocolConfigurationError(ValueError):
    pass


def _load(path: Path) -> Dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ProtocolConfigurationError("cannot read {}: {}".format(path, error)) from error
    if not isinstance(value, dict):
        raise ProtocolConfigurationError("{} must contain a mapping".format(path))
    return value


def _keys(value: Mapping[str, Any], expected, path: Path) -> None:
    if set(value) != set(expected):
        raise ProtocolConfigurationError(
            "{}: expected {}, got {}".format(path, sorted(expected), sorted(value))
        )


def load_protocol(directory: Path) -> Dict[str, Any]:
    path = Path(directory) / "protocol.yaml"
    value = _load(path)
    _keys(
        value,
        {
            "schema_version",
            "seed",
            "camera",
            "geometry",
            "sampling",
            "pnp",
            "candidate_source",
            "method_parameters",
            "paper_outputs",
            "paper_reference",
            "reproducibility",
        },
        path,
    )
    if value["schema_version"] != 1 or not isinstance(value["seed"], int):
        raise ProtocolConfigurationError("{}: invalid schema version or seed".format(path))
    _keys(
        value["camera"],
        {"fx_px", "fy_px", "cx_px", "cy_px", "image_width_px", "image_height_px"},
        path,
    )
    _keys(
        value["geometry"],
        {"primary_radius", "validation_radius", "minimum_center_separation"},
        path,
    )
    _keys(value["sampling"], {"contour_points", "image_noise_sigma_px"}, path)
    _keys(
        value["pnp"],
        {"iterations", "reprojection_threshold_px", "confidence"},
        path,
    )
    for key in ("method_parameters", "paper_outputs", "paper_reference", "reproducibility"):
        if not isinstance(value[key], Mapping):
            raise ProtocolConfigurationError("{}: {} must be a mapping".format(path, key))
    return value


def load_profile(directory: Path, name: str) -> Dict[str, Any]:
    path = Path(directory) / "profiles" / "{}.yaml".format(name)
    if not path.is_file():
        available = sorted(item.stem for item in path.parent.glob("*.yaml"))
        raise ProtocolConfigurationError(
            "unknown profile {!r}; available: {}".format(name, ", ".join(available))
        )
    value = _load(path)
    _keys(
        value,
        {
            "schema_version",
            "name",
            "trials",
            "circles_per_trial",
            "compare_to_paper_reference",
        },
        path,
    )
    if value["schema_version"] != 1 or value["name"] != name:
        raise ProtocolConfigurationError("{}: profile identity is inconsistent".format(path))
    if int(value["trials"]) <= 0 or int(value["circles_per_trial"]) < 4:
        raise ProtocolConfigurationError("{}: invalid trial or circle count".format(path))
    if not isinstance(value["compare_to_paper_reference"], bool):
        raise ProtocolConfigurationError("{}: comparison flag must be boolean".format(path))
    return value


__all__ = ["ProtocolConfigurationError", "load_profile", "load_protocol"]
