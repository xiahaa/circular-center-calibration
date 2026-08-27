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


def _resolve_dataset_root(data_root: Path, name: str) -> Path:
    data_root = Path(data_root).expanduser().resolve()
    direct = data_root / name
    if direct.is_dir():
        return direct
    matches = []
    for manifest_path in sorted(data_root.glob("*/dataset.yaml")):
        manifest = _load_yaml(manifest_path)
        if manifest.get("dataset") == name:
            matches.append(manifest_path.parent)
    if not matches:
        raise ValueError("dataset {!r} was not found under {}".format(name, data_root))
    if len(matches) > 1:
        raise ValueError(
            "dataset {!r} has multiple directories under {}: {}".format(
                name,
                data_root,
                ", ".join(str(path.name) for path in matches),
            )
        )
    return matches[0]


def load_dataset(data_root: Path, name: str) -> Dataset:
    root = _resolve_dataset_root(data_root, name)
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
        if any(count <= 0 for count in counts):
            raise ValueError("{} has a non-positive PCD field count".format(path))
        required = {"x", "y", "z", "intensity"}
        if not required.issubset(fields):
            raise ValueError("{} must contain x, y, z, and intensity".format(path))
        required_indices = {field: fields.index(field) for field in required}
        if any(counts[index] != 1 for index in required_indices.values()):
            raise ValueError("{} must use scalar x, y, z, and intensity fields".format(path))
        try:
            scalar_dtypes = [
                _PCD_DTYPES[(field_type, size)]
                for field_type, size in zip(types, sizes)
            ]
        except KeyError as error:
            raise ValueError("{} uses an unsupported PCD field type".format(path)) from error
        internal_names = ["field_{}".format(index) for index in range(len(fields))]
        dtype = np.dtype(
            [
                (internal_name, scalar_dtype)
                if count == 1
                else (internal_name, scalar_dtype, (count,))
                for internal_name, scalar_dtype, count in zip(
                    internal_names, scalar_dtypes, counts
                )
            ]
        )
        point_count = int(header.get("POINTS", header.get("WIDTH", ["0"]))[0])
        if storage == "binary":
            records = np.fromfile(stream, dtype=dtype, count=point_count)
        elif storage == "ascii":
            values = np.loadtxt(stream, dtype=float, ndmin=2)
            if values.shape[1] != sum(counts):
                raise ValueError("{} has inconsistent ASCII point rows".format(path))
            records = np.empty(len(values), dtype=dtype)
            offset = 0
            for internal_name, count in zip(internal_names, counts):
                if count == 1:
                    records[internal_name] = values[:, offset]
                else:
                    records[internal_name] = values[:, offset : offset + count]
                offset += count
        else:
            raise ValueError("{} uses unsupported DATA {}".format(path, storage))
    if len(records) != point_count:
        raise ValueError(
            "{} declares {} points but contains {}".format(path, point_count, len(records))
        )
    points = np.column_stack(
        tuple(records[internal_names[required_indices[field]]] for field in ("x", "y", "z"))
    ).astype(float, copy=False)
    intensity = np.asarray(
        records[internal_names[required_indices["intensity"]]], dtype=float
    )
    valid = (
        np.isfinite(points).all(axis=1)
        & np.isfinite(intensity)
        & (np.linalg.norm(points, axis=1) > 0.0)
    )
    return PointCloud(points=points[valid], intensity=intensity[valid])


__all__ = ["Dataset", "FramePair", "PointCloud", "load_dataset", "read_pcd"]
