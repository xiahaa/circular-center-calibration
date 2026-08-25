"""Data passed from the generic runner to a repository-owned experiment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from .config import ExperimentSelection


@dataclass(frozen=True)
class ExperimentContext:
    """Shared resources passed to an experiment without leaking runner details."""

    selection: ExperimentSelection
    repository_root: Path
    experiment_directory: Path
    output_directory: Path
    methods: Mapping[str, Any]
    max_frames: Optional[int] = None


__all__ = ["ExperimentContext"]
