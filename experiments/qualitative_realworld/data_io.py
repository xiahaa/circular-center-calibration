"""Dataset and PCD readers owned by the real-world experiment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import cv2
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


def read_image(path: Path) -> np.ndarray:
    """Read a BGR image without OpenCV's Windows Unicode-path limitation."""

    source = Path(path)
    try:
        encoded = np.fromfile(source, dtype=np.uint8)
    except OSError as error:
        raise ValueError("cannot read image {}: {}".format(source, error)) from error
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("cannot decode image {}".format(source))
    return image


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
    """Read uncompressed ASCII or binary PCD with scalar x/y/z/intensity fields.

    Other fields may be vector-valued. Livox PCD files commonly use repeated
    anonymous ``_`` fields with COUNT greater than one for alignment padding.
    """

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
        required = {"x", "y", "z", "intensity"}
        if not required.issubset(fields):
            raise ValueError("{} must contain x, y, z, and intensity".format(path))
        if any(counts[fields.index(field)] != 1 for field in required):
            raise ValueError("{} uses a vector-valued required field".format(path))

        internal_names = []
        used_names = set()
        for index, field in enumerate(fields):
            internal_name = field
            if internal_name in used_names:
                internal_name = "{}_{}".format(field, index)
            used_names.add(internal_name)
            internal_names.append(internal_name)
        try:
            dtype_fields = []
            for internal_name, field_type, size, count in zip(
                internal_names, types, sizes, counts
            ):
                scalar_dtype = _PCD_DTYPES[(field_type, size)]
                descriptor = (
                    (internal_name, scalar_dtype)
                    if count == 1
                    else (internal_name, scalar_dtype, (count,))
                )
                dtype_fields.append(descriptor)
            dtype = np.dtype(dtype_fields)
        except KeyError as error:
            raise ValueError("{} uses an unsupported PCD field type".format(path)) from error
        point_count = int(header.get("POINTS", header.get("WIDTH", ["0"]))[0])
        if storage == "binary":
            records = np.fromfile(stream, dtype=dtype, count=point_count)
        elif storage == "ascii":
            values = np.loadtxt(stream, dtype=float, ndmin=2)
            if values.shape[1] != sum(counts):
                raise ValueError("{} has inconsistent ASCII point rows".format(path))
            records = np.empty(len(values), dtype=dtype)
            column = 0
            for internal_name, count in zip(internal_names, counts):
                if count == 1:
                    records[internal_name] = values[:, column]
                else:
                    records[internal_name] = values[:, column : column + count]
                column += count
        else:
            raise ValueError("{} uses unsupported DATA {}".format(path, storage))
    if len(records) != point_count:
        raise ValueError(
            "{} declares {} points but contains {}".format(path, point_count, len(records))
        )
    required_names = {
        field: internal_names[fields.index(field)] for field in required
    }
    points = np.column_stack(
        (
            records[required_names["x"]],
            records[required_names["y"]],
            records[required_names["z"]],
        )
    ).astype(float, copy=False)
    intensity = np.asarray(records[required_names["intensity"]], dtype=float)
    valid = (
        np.isfinite(points).all(axis=1)
        & np.isfinite(intensity)
        & (np.linalg.norm(points, axis=1) > 0.0)
    )
    return PointCloud(points=points[valid], intensity=intensity[valid])


__all__ = [
    "Dataset",
    "FramePair",
    "PointCloud",
    "load_dataset",
    "read_image",
    "read_pcd",
]
