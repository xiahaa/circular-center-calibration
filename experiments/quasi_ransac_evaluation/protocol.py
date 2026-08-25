"""Strict protocol and profile loading for paper Table II."""

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
            "volume",
            "candidates",
            "success_criteria",
            "table",
            "method_parameters",
            "paper_reference",
            "reproducibility",
        },
        path,
    )
    if value["schema_version"] != 1 or not isinstance(value["seed"], int):
        raise ProtocolConfigurationError("{}: invalid schema version or seed".format(path))
    _keys(value["camera"], {"fx_px", "fy_px", "cx_px", "cy_px"}, path)
    _keys(
        value["volume"],
        {"width_m", "height_m", "minimum_depth_m", "maximum_depth_m"},
        path,
    )
    _keys(
        value["candidates"],
        {
            "correct_noise_sigma_px",
            "false_minimum_px",
            "false_maximum_px",
            "outlier_coordinate_displacement_px",
        },
        path,
    )
    _keys(
        value["success_criteria"],
        {"maximum_rotation_error_deg", "maximum_translation_error_m"},
        path,
    )
    _keys(value["table"], {"method", "confidence", "tex_filename"}, path)
    for key in ("method_parameters", "paper_reference", "reproducibility"):
        if not isinstance(value[key], Mapping):
            raise ProtocolConfigurationError("{}: {} must be a mapping".format(path, key))
    if not isinstance(value["paper_reference"].get("rows"), list):
        raise ProtocolConfigurationError("{}: paper_reference.rows must be a list".format(path))
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
            "trials_per_cell",
            "point_counts",
            "outlier_ratios",
            "confidences",
            "compare_to_paper_reference",
        },
        path,
    )
    if value["schema_version"] != 1 or value["name"] != name:
        raise ProtocolConfigurationError("{}: profile identity is inconsistent".format(path))
    if int(value["trials_per_cell"]) <= 0:
        raise ProtocolConfigurationError("{}: trials_per_cell must be positive".format(path))
    if not value["point_counts"] or min(int(item) for item in value["point_counts"]) < 4:
        raise ProtocolConfigurationError("{}: point counts must be at least four".format(path))
    if not value["outlier_ratios"] or not all(
        0.0 <= float(item) < 1.0 for item in value["outlier_ratios"]
    ):
        raise ProtocolConfigurationError("{}: invalid outlier ratio".format(path))
    if not value["confidences"] or not all(
        0.0 < float(item) < 1.0 for item in value["confidences"]
    ):
        raise ProtocolConfigurationError("{}: invalid confidence".format(path))
    if not isinstance(value["compare_to_paper_reference"], bool):
        raise ProtocolConfigurationError("{}: comparison flag must be boolean".format(path))
    return value


__all__ = ["ProtocolConfigurationError", "load_profile", "load_protocol"]
