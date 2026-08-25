"""Load method implementations from the centrally managed YAML catalog."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

import yaml

METHOD_KINDS = frozenset({"center2d", "center3d", "ambiguity"})
_TOP_LEVEL_KEYS = frozenset(
    {"schema_version", "name", "kind", "implementation", "parameters", "description"}
)
_IMPLEMENTATION_KEYS = frozenset({"module", "class"})


class MethodConfigurationError(ValueError):
    """Raised when a method YAML or implementation violates the plugin contract."""


@dataclass(frozen=True)
class MethodSpec:
    """One named method and the constructor arguments used to instantiate it."""

    schema_version: int
    name: str
    kind: str
    module: str
    class_name: str
    parameters: Mapping[str, Any]
    source: Path
    description: str = ""


def default_method_config_root() -> Path:
    """Locate ``configs/methods`` in a source checkout or via an override."""

    configured = os.environ.get("CIRCULAR_CENTER_METHOD_CONFIG_DIR")
    if configured:
        path = Path(configured).expanduser().resolve()
        if path.is_dir():
            return path
        raise MethodConfigurationError(
            "CIRCULAR_CENTER_METHOD_CONFIG_DIR is not a directory: {}".format(path)
        )

    for parent in (Path.cwd(), *Path.cwd().parents):
        candidate = parent / "configs" / "methods"
        if candidate.is_dir():
            return candidate.resolve()

    source_checkout = Path(__file__).resolve().parents[3] / "configs" / "methods"
    if source_checkout.is_dir():
        return source_checkout
    raise MethodConfigurationError(
        "cannot locate configs/methods; pass a path or set "
        "CIRCULAR_CENTER_METHOD_CONFIG_DIR"
    )


def _require_string(value: Any, label: str, source: Path) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MethodConfigurationError("{}: {} must be a non-empty string".format(source, label))
    return value


def _load_spec(source: Path) -> MethodSpec:
    try:
        document = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise MethodConfigurationError("cannot read {}: {}".format(source, error)) from error
    if not isinstance(document, dict):
        raise MethodConfigurationError("{}: document must be a mapping".format(source))

    unknown = set(document) - _TOP_LEVEL_KEYS
    required = _TOP_LEVEL_KEYS - {"description"}
    missing = required - set(document)
    if unknown or missing:
        details = []
        if missing:
            details.append("missing {}".format(sorted(missing)))
        if unknown:
            details.append("unknown {}".format(sorted(unknown)))
        raise MethodConfigurationError("{}: {}".format(source, "; ".join(details)))

    schema_version = document["schema_version"]
    if schema_version != 1:
        raise MethodConfigurationError(
            "{}: unsupported schema_version {!r}; expected 1".format(source, schema_version)
        )
    name = _require_string(document["name"], "name", source)
    kind = _require_string(document["kind"], "kind", source)
    if kind not in METHOD_KINDS:
        raise MethodConfigurationError(
            "{}: kind must be one of {}".format(source, sorted(METHOD_KINDS))
        )

    implementation = document["implementation"]
    if not isinstance(implementation, dict) or set(implementation) != _IMPLEMENTATION_KEYS:
        raise MethodConfigurationError(
            "{}: implementation must contain exactly module and class".format(source)
        )
    module = _require_string(implementation["module"], "implementation.module", source)
    class_name = _require_string(
        implementation["class"], "implementation.class", source
    )
    parameters = document["parameters"]
    if not isinstance(parameters, dict):
        raise MethodConfigurationError("{}: parameters must be a mapping".format(source))
    description = document.get("description", "")
    if not isinstance(description, str):
        raise MethodConfigurationError("{}: description must be a string".format(source))
    return MethodSpec(
        schema_version=1,
        name=name,
        kind=kind,
        module=module,
        class_name=class_name,
        parameters=dict(parameters),
        source=source.resolve(),
        description=description,
    )


class MethodCatalog:
    """Validated catalog that constructs methods by their paper names."""

    def __init__(self, specs: Iterable[MethodSpec]) -> None:
        by_name: Dict[str, MethodSpec] = {}
        for spec in specs:
            if spec.name in by_name:
                raise MethodConfigurationError(
                    "duplicate method name {!r} in {} and {}".format(
                        spec.name, by_name[spec.name].source, spec.source
                    )
                )
            by_name[spec.name] = spec
        if not by_name:
            raise MethodConfigurationError("method catalog is empty")
        self._by_name = by_name

    @classmethod
    def from_directory(cls, root: Optional[Path] = None) -> "MethodCatalog":
        directory = default_method_config_root() if root is None else Path(root).resolve()
        if not directory.is_dir():
            raise MethodConfigurationError(
                "method configuration directory does not exist: {}".format(directory)
            )
        sources = sorted((*directory.rglob("*.yaml"), *directory.rglob("*.yml")))
        return cls(_load_spec(source) for source in sources)

    def names(self, kind: Optional[str] = None) -> tuple[str, ...]:
        if kind is not None and kind not in METHOD_KINDS:
            raise MethodConfigurationError("unknown method kind {!r}".format(kind))
        return tuple(
            sorted(
                name
                for name, spec in self._by_name.items()
                if kind is None or spec.kind == kind
            )
        )

    def get(self, name: str, expected_kind: Optional[str] = None) -> MethodSpec:
        try:
            spec = self._by_name[name]
        except KeyError as error:
            raise MethodConfigurationError(
                "unknown method {!r}; available methods: {}".format(
                    name, ", ".join(self.names())
                )
            ) from error
        if expected_kind is not None and spec.kind != expected_kind:
            raise MethodConfigurationError(
                "method {!r} has kind {!r}, expected {!r}".format(
                    name, spec.kind, expected_kind
                )
            )
        return spec

    def create(
        self,
        name: str,
        expected_kind: Optional[str] = None,
        overrides: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        spec = self.get(name, expected_kind)
        parameters = dict(spec.parameters)
        if overrides is not None:
            if not isinstance(overrides, Mapping):
                raise MethodConfigurationError("method overrides must be a mapping")
            parameters.update(overrides)
        try:
            module = importlib.import_module(spec.module)
            implementation = getattr(module, spec.class_name)
            method = implementation(**parameters)
        except (ImportError, AttributeError, TypeError, ValueError) as error:
            raise MethodConfigurationError(
                "cannot instantiate {!r} from {}: {}".format(name, spec.source, error)
            ) from error
        if getattr(method, "name", None) != spec.name:
            raise MethodConfigurationError(
                "{}: implementation name {!r} does not match configured name {!r}".format(
                    spec.source, getattr(method, "name", None), spec.name
                )
            )
        return method


__all__ = [
    "METHOD_KINDS",
    "MethodCatalog",
    "MethodConfigurationError",
    "MethodSpec",
    "default_method_config_root",
]
