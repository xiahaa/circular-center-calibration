"""Dataset and PCD readers owned by the real-world experiment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import yaml


@dataclass(frozen=True)
class FramePair:
    frame_id: str
    image_path: Path
    point_cloud_path: Path


@dataclass(frozen=True)
class Dataset:
    name: str
    root: Path
    pairs: Tuple[FramePair, ...]
    intrinsic: np.ndarray
    distortion: np.ndarray
    distortion_model: str
    marker_diameter_m: float


@dataclass(frozen=True)
class PointCloud:
    points: np.ndarray
    intensity: np.ndarray


def _load_yaml(source: Path) -> Dict[str, object]:
    try:
        document = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValueError("cannot read {}: {}".format(source, error)) from error
    if not isinstance(document, dict):
        raise ValueError("{} must contain a YAML mapping".format(source))
    return document


def load_dataset(data_root: Path, name: str) -> Dataset:
    root = (Path(data_root) / name).resolve()
    manifest = _load_yaml(root / "dataset.yaml")
    camera = _load_yaml(root / str(manifest["camera_info"]))
    if manifest.get("dataset") != name:
        raise ValueError("dataset name mismatch in {}".format(root / "dataset.yaml"))
    image_directory = root / str(manifest["image_dir"])
    point_cloud_directory = root / str(manifest["point_cloud_dir"])
    images = {path.stem: path for path in image_directory.glob("*.png")}
    clouds = {path.stem: path for path in point_cloud_directory.glob("*.pcd")}
    frame_ids = sorted(set(images) & set(clouds))
    if not frame_ids:
        raise ValueError("{} contains no paired PNG/PCD frames".format(root))
    declared_count = int(manifest.get("pair_count", len(frame_ids)))
    if declared_count != len(frame_ids):
        raise ValueError(
            "{} declares {} pairs but {} were found".format(root, declared_count, len(frame_ids))
        )
    intrinsic = np.asarray(camera["K"], dtype=float).reshape(3, 3)
    distortion = np.asarray(camera["D"], dtype=float).reshape(-1)
    if not np.isfinite(intrinsic).all() or not np.isfinite(distortion).all():
        raise ValueError("camera calibration must be finite")
    marker_diameter = float(manifest["marker_diameter_m"])
    if marker_diameter <= 0.0:
        raise ValueError("marker_diameter_m must be positive")
    return Dataset(
        name=name,
        root=root,
        pairs=tuple(FramePair(frame, images[frame], clouds[frame]) for frame in frame_ids),
        intrinsic=intrinsic,
        distortion=distortion,
        distortion_model=str(camera["distortion_model"]),
        marker_diameter_m=marker_diameter,
    )


_PCD_DTYPES = {
    ("F", 4): "<f4",
    ("F", 8): "<f8",
    ("I", 1): "<i1",
    ("I", 2): "<i2",
    ("I", 4): "<i4",
    ("I", 8): "<i8",
    ("U", 1): "<u1",
    ("U", 2): "<u2",
    ("U", 4): "<u4",
    ("U", 8): "<u8",
}


def read_pcd(source: Path) -> PointCloud:
    """Read uncompressed ASCII or binary PCD with scalar x/y/z/intensity fields."""

    path = Path(source)
    header: Dict[str, list[str]] = {}
    with path.open("rb") as stream:
        while True:
            raw_line = stream.readline()
            if not raw_line:
                raise ValueError("{} has no DATA header".format(path))
            try:
                line = raw_line.decode("ascii").strip()
            except UnicodeDecodeError as error:
                raise ValueError("{} has a malformed PCD header".format(path)) from error
            if not line or line.startswith("#"):
                continue
            key, *values = line.split()
            key = key.upper()
            if key == "DATA":
                if len(values) != 1:
                    raise ValueError("{} has an invalid DATA declaration".format(path))
                storage = values[0].lower()
                break
            header[key] = values

        fields = header.get("FIELDS", [])
        sizes = [int(value) for value in header.get("SIZE", [])]
        types = [value.upper() for value in header.get("TYPE", [])]
        counts = [int(value) for value in header.get("COUNT", ["1"] * len(fields))]
        if not (len(fields) == len(sizes) == len(types) == len(counts)):
            raise ValueError("{} has inconsistent field metadata".format(path))
        if any(count != 1 for count in counts):
            raise ValueError("{} uses unsupported vector-valued PCD fields".format(path))
        required = {"x", "y", "z", "intensity"}
        if not required.issubset(fields):
            raise ValueError("{} must contain x, y, z, and intensity".format(path))
        try:
            dtype = np.dtype(
                [(field, _PCD_DTYPES[(field_type, size)]) for field, field_type, size in zip(fields, types, sizes)]
            )
        except KeyError as error:
            raise ValueError("{} uses an unsupported PCD field type".format(path)) from error
        point_count = int(header.get("POINTS", header.get("WIDTH", ["0"]))[0])
        if storage == "binary":
            records = np.fromfile(stream, dtype=dtype, count=point_count)
        elif storage == "ascii":
            values = np.loadtxt(stream, dtype=float, ndmin=2)
            if values.shape[1] != len(fields):
                raise ValueError("{} has inconsistent ASCII point rows".format(path))
            records = np.empty(len(values), dtype=dtype)
            for index, field in enumerate(fields):
                records[field] = values[:, index]
        else:
            raise ValueError("{} uses unsupported DATA {}".format(path, storage))
    if len(records) != point_count:
        raise ValueError(
            "{} declares {} points but contains {}".format(path, point_count, len(records))
        )
    points = np.column_stack((records["x"], records["y"], records["z"])).astype(
        float, copy=False
    )
    intensity = np.asarray(records["intensity"], dtype=float)
    valid = (
        np.isfinite(points).all(axis=1)
        & np.isfinite(intensity)
        & (np.linalg.norm(points, axis=1) > 0.0)
    )
    return PointCloud(points=points[valid], intensity=intensity[valid])


__all__ = ["Dataset", "FramePair", "PointCloud", "load_dataset", "read_pcd"]
