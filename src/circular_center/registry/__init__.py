"""Configuration-backed discovery of interchangeable methods."""

from .methods import (
    MethodCatalog,
    MethodConfigurationError,
    MethodSpec,
    default_method_config_root,
)

__all__ = [
    "MethodCatalog",
    "MethodConfigurationError",
    "MethodSpec",
    "default_method_config_root",
]
