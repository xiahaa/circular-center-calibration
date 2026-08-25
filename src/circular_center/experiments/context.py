"""Data passed from the generic runner to a repository-owned experiment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Optional, Tuple

from .config import ExperimentSelection

if TYPE_CHECKING:
    from circular_center.registry import MethodCatalog


_METHOD_KINDS = {"2d": "center2d", "3d": "center3d", "ambiguity": "ambiguity"}


@dataclass(frozen=True)
class ExperimentContext:
    """Shared resources passed to an experiment without leaking runner details."""

    selection: ExperimentSelection
    repository_root: Path
    experiment_directory: Path
    output_directory: Path
    methods: Mapping[str, Tuple[Any, ...]]
    method_catalog: "MethodCatalog"
    max_frames: Optional[int] = None

    def methods_for(self, kind: str) -> Tuple[Any, ...]:
        """Return all instantiated methods selected for one stage."""

        try:
            return self.methods[kind]
        except KeyError as error:
            raise ValueError("unknown experiment method kind {!r}".format(kind)) from error

    def require_single_method(self, kind: str) -> Any:
        """Return one method or reject an incompatible experiment selection."""

        methods = self.methods_for(kind)
        if len(methods) != 1:
            raise ValueError(
                "experiment {!r} requires exactly one {} method, got {}".format(
                    self.selection.name, kind, len(methods)
                )
            )
        return methods[0]

    def optional_single_method(self, kind: str) -> Optional[Any]:
        """Return zero or one method, rejecting ambiguous multi-selection."""

        methods = self.methods_for(kind)
        if len(methods) > 1:
            raise ValueError(
                "experiment {!r} accepts at most one {} method, got {}".format(
                    self.selection.name, kind, len(methods)
                )
            )
        return None if not methods else methods[0]

    def create_method(
        self,
        kind: str,
        name: str,
        overrides: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        """Create a selected method with experiment-protocol parameter overrides."""

        try:
            expected_kind = _METHOD_KINDS[kind]
        except KeyError as error:
            raise ValueError("unknown experiment method kind {!r}".format(kind)) from error
        if name not in self.selection.method_names(kind):
            raise ValueError(
                "method {!r} was not selected for experiment {!r}".format(
                    name, self.selection.name
                )
            )
        return self.method_catalog.create(name, expected_kind, overrides)


__all__ = ["ExperimentContext"]
