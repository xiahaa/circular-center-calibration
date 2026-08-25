"""PCL SACMODEL_CIRCLE3D baseline exposed through an optional C++ library."""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys
from pathlib import Path
from time import perf_counter
from typing import Iterable, Optional, Tuple, Union

import numpy as np

from circular_center.center3d import (
    CircleFitError,
    CircleFitResult,
    FitStatus,
    circle_residuals,
)


class PCLUnavailableError(RuntimeError):
    """Raised when the optional PCL-backed shared library cannot be loaded."""


def _library_names() -> Tuple[str, ...]:
    if sys.platform == "win32":
        return ("circular_center_pcl_sacmodel.dll",)
    if sys.platform == "darwin":
        return ("libcircular_center_pcl_sacmodel.dylib",)
    return ("libcircular_center_pcl_sacmodel.so",)


def _library_candidates(configured: Optional[str]) -> Iterable[Union[Path, str]]:
    names = _library_names()
    if configured:
        path = Path(configured).expanduser()
        if path.is_dir():
            for name in names:
                yield path / name
        else:
            yield path
        return

    environment_path = os.environ.get("CIRCULAR_CENTER_PCL_LIBRARY")
    if environment_path:
        path = Path(environment_path).expanduser()
        if path.is_dir():
            for name in names:
                yield path / name
        else:
            yield path
        return

    repository_root = Path(__file__).resolve().parents[4]
    for build_directory in sorted(repository_root.glob("build*")):
        for relative in (Path("cpp"), Path()):
            for name in names:
                yield build_directory / relative / name

    discovered = ctypes.util.find_library("circular_center_pcl_sacmodel")
    if discovered:
        yield discovered


def _load_library(configured: Optional[str]) -> ctypes.CDLL:
    attempted = []
    for candidate in _library_candidates(configured):
        candidate_string = str(candidate)
        attempted.append(candidate_string)
        if isinstance(candidate, Path) and not candidate.is_file():
            continue
        try:
            library = ctypes.CDLL(candidate_string)
        except OSError:
            continue
        try:
            abi_version = library.ccc_pcl_sacmodel_abi_version
            abi_version.argtypes = []
            abi_version.restype = ctypes.c_int
            if abi_version() != 1:
                raise PCLUnavailableError(
                    "unsupported circular-center PCL baseline ABI in {}".format(
                        candidate_string
                    )
                )
            fit = library.ccc_pcl_sacmodel_fit_circle3d
        except AttributeError as error:
            raise PCLUnavailableError(
                "{} is not a circular-center PCL baseline library".format(candidate_string)
            ) from error
        fit.argtypes = [
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_size_t,
            ctypes.c_double,
            ctypes.c_int,
            ctypes.c_double,
            ctypes.c_double,
            ctypes.c_double,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_char),
            ctypes.c_size_t,
        ]
        fit.restype = ctypes.c_int
        return library
    details = ", ".join(attempted) if attempted else "no candidate paths"
    raise PCLUnavailableError(
        "PCL SACMODEL is registered but its shared library is unavailable; "
        "install PCL and build with -DCCC_BUILD_PCL_BASELINE=ON. Tried: {}".format(
            details
        )
    )


def _canonical_normal(normal: np.ndarray) -> np.ndarray:
    normal = np.asarray(normal, dtype=float).reshape(3)
    norm = float(np.linalg.norm(normal))
    if not np.isfinite(norm) or norm <= np.finfo(float).eps:
        raise CircleFitError(FitStatus.NUMERICAL_FAILURE, "PCL returned an invalid normal")
    normal = normal / norm
    pivot = int(np.argmax(np.abs(normal)))
    return -normal if normal[pivot] < 0.0 else normal


class PCLSACMODEL:
    """Fit a 3D circle with PCL SACSegmentation and SACMODEL_CIRCLE3D."""

    name = "PCL SACMODEL"

    def __init__(
        self,
        residual_threshold_m: float,
        max_iterations: int = 500,
        confidence: float = 0.99,
        minimum_radius_m: float = 0.0,
        maximum_radius_m: Optional[float] = None,
        library_path: Optional[str] = None,
    ) -> None:
        self.residual_threshold_m = float(residual_threshold_m)
        self.max_iterations = int(max_iterations)
        self.confidence = float(confidence)
        self.minimum_radius_m = float(minimum_radius_m)
        self.maximum_radius_m = (
            None if maximum_radius_m is None else float(maximum_radius_m)
        )
        self.library_path = None if library_path is None else str(library_path)
        if self.residual_threshold_m <= 0.0 or self.max_iterations <= 0:
            raise ValueError("PCL threshold and max_iterations must be positive")
        if not 0.0 < self.confidence < 1.0:
            raise ValueError("PCL confidence must be in (0, 1)")
        if self.minimum_radius_m < 0.0:
            raise ValueError("minimum_radius_m must be non-negative")
        if (
            self.maximum_radius_m is not None
            and self.maximum_radius_m < self.minimum_radius_m
        ):
            raise ValueError("maximum_radius_m must not be smaller than minimum_radius_m")
        self._library: Optional[ctypes.CDLL] = None

    def fit(self, points: np.ndarray) -> CircleFitResult:
        points = np.ascontiguousarray(points, dtype=np.float64)
        if points.ndim != 2 or points.shape[1] != 3:
            raise CircleFitError(FitStatus.INVALID_INPUT, "points must have shape (N, 3)")
        if len(points) < 3:
            raise CircleFitError(FitStatus.INVALID_INPUT, "at least three points are required")
        if not np.isfinite(points).all():
            raise CircleFitError(
                FitStatus.INVALID_INPUT, "points must contain only finite values"
            )
        if self._library is None:
            self._library = _load_library(self.library_path)

        coefficients = np.empty(7, dtype=np.float64)
        inliers = np.zeros(len(points), dtype=np.uint8)
        error = ctypes.create_string_buffer(1024)
        started = perf_counter()
        status = self._library.ccc_pcl_sacmodel_fit_circle3d(
            points.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            len(points),
            self.residual_threshold_m,
            self.max_iterations,
            self.confidence,
            self.minimum_radius_m,
            0.0 if self.maximum_radius_m is None else self.maximum_radius_m,
            coefficients.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
            inliers.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
            error,
            len(error),
        )
        elapsed = perf_counter() - started
        if status != 0:
            fit_status = {
                1: FitStatus.INVALID_INPUT,
                2: FitStatus.NO_CONSENSUS,
                3: FitStatus.NUMERICAL_FAILURE,
            }.get(status, FitStatus.NUMERICAL_FAILURE)
            message = error.value.decode("utf-8", errors="replace")
            raise CircleFitError(fit_status, message or "PCL SACMODEL failed")
        if not np.isfinite(coefficients).all() or coefficients[3] < 0.0:
            raise CircleFitError(
                FitStatus.NUMERICAL_FAILURE, "PCL returned invalid circle coefficients"
            )

        center = coefficients[:3].copy()
        radius = float(coefficients[3])
        normal = _canonical_normal(coefficients[4:])
        residuals = circle_residuals(points, center, radius, normal)
        return CircleFitResult(
            method="pcl_sacmodel",
            center=center,
            radius=radius,
            normal=normal,
            residuals=residuals,
            inlier_mask=inliers.astype(bool),
            status=FitStatus.SUCCESS,
            # SACSegmentation does not expose the completed iteration count.
            iterations=0,
            elapsed_seconds=elapsed,
        )


__all__ = ["PCLSACMODEL", "PCLUnavailableError"]
