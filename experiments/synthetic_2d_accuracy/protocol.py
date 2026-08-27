"""Load and validate the experiment-owned synthetic 2D protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

import yaml


class ProtocolConfigurationError(ValueError):
    """Raised when the protocol or an execution profile is malformed."""


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
            "camera",
            "geometry",
            "sampling",
            "method_parameters",
            "paper_outputs",
            "paper_reference",
            "reproducibility",
        },
        path,
    )
    if document["schema_version"] != 1 or not isinstance(document["seed"], int):
        raise ProtocolConfigurationError("{}: invalid schema_version or seed".format(path))
    _expect_keys(
        document["camera"],
        {"fx_px", "fy_px", "cx_px", "cy_px", "image_width_px", "image_height_px"},
        path,
    )
    _expect_keys(
        document["geometry"],
        {"radius_m", "coplanar_radius_m", "coplanar_offset_m"},
        path,
    )
    _expect_keys(
        document["sampling"],
        {
            "contour_points",
            "rotation_vector_sigma_rad",
            "translation_mean_m",
            "translation_sigma_m",
            "image_noise_sigma_px",
        },
        path,
    )
    for key in ("method_parameters", "paper_outputs", "paper_reference", "reproducibility"):
        if not isinstance(document[key], Mapping):
            raise ProtocolConfigurationError("{}: {} must be a mapping".format(path, key))
    if int(document["sampling"]["contour_points"]) < 5:
        raise ProtocolConfigurationError("{}: at least five contour points are required".format(path))
    if float(document["sampling"]["image_noise_sigma_px"]) < 0.0:
        raise ProtocolConfigurationError("{}: image noise must be non-negative".format(path))
    return document


def load_profile(experiment_directory: Path, name: str) -> Dict[str, Any]:
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
        {"schema_version", "name", "trials", "compare_to_paper_reference"},
        path,
    )
    if document["schema_version"] != 1 or document["name"] != name:
        raise ProtocolConfigurationError("{}: profile identity is inconsistent".format(path))
    if not isinstance(document["trials"], int) or document["trials"] <= 0:
        raise ProtocolConfigurationError("{}: trials must be positive".format(path))
    if not isinstance(document["compare_to_paper_reference"], bool):
        raise ProtocolConfigurationError(
            "{}: compare_to_paper_reference must be boolean".format(path)
        )
    return document


__all__ = ["ProtocolConfigurationError", "load_profile", "load_protocol"]
