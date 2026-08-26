#!/usr/bin/env python3
"""Verify a real-world dataset against a tracked SHA-256 manifest."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import yaml


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dataset", type=Path, help="dataset directory containing img/ and pcd/"
    )
    parser.add_argument(
        "manifests",
        type=Path,
        nargs="+",
        help="SHA-256 manifests covering all released images and point clouds",
    )
    args = parser.parse_args()

    dataset_manifest = yaml.safe_load(
        (args.dataset / "dataset.yaml").read_text(encoding="utf-8")
    )
    if not isinstance(dataset_manifest, dict) or "pair_count" not in dataset_manifest:
        parser.error("dataset.yaml must declare pair_count")
    declared_count = int(dataset_manifest["pair_count"])
    if declared_count <= 0:
        parser.error("dataset.yaml pair_count must be positive")

    expected: dict[Path, str] = {}
    for manifest in args.manifests:
        manifest_lines = manifest.read_text(encoding="utf-8").splitlines()
        for line_number, raw_line in enumerate(manifest_lines, 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                checksum, relative_name = line.split(maxsplit=1)
            except ValueError:
                parser.error(
                    f"invalid manifest line {manifest}:{line_number}: {raw_line!r}"
                )
            relative_path = Path(relative_name)
            if relative_path in expected:
                parser.error(f"duplicate manifest entry: {relative_path.as_posix()}")
            expected[relative_path] = checksum.lower()

    errors: list[str] = []
    for relative_name, checksum in expected.items():
        path = args.dataset / relative_name
        if not path.is_file():
            errors.append(f"missing: {relative_name.as_posix()}")
            continue
        actual = _sha256(path)
        if actual != checksum:
            errors.append(
                f"hash mismatch: {relative_name.as_posix()} "
                f"(expected {checksum}, got {actual})"
            )

    actual_images = {
        path.relative_to(args.dataset) for path in (args.dataset / "img").glob("*.png")
    }
    actual_point_clouds = {
        path.relative_to(args.dataset) for path in (args.dataset / "pcd").glob("*.pcd")
    }
    expected_images = {
        path for path in expected if path.parent == Path("img") and path.suffix == ".png"
    }
    expected_point_clouds = {
        path for path in expected if path.parent == Path("pcd") and path.suffix == ".pcd"
    }
    if len(actual_images) != declared_count:
        errors.append(
            f"expected {declared_count} PNG images, found {len(actual_images)}"
        )
    if len(actual_point_clouds) != declared_count:
        errors.append(
            f"expected {declared_count} PCD files, found {len(actual_point_clouds)}"
        )
    if expected_images != actual_images:
        errors.append("image manifest does not list exactly the declared dataset images")
    if expected_point_clouds != actual_point_clouds:
        errors.append(
            "point-cloud manifest does not list exactly the declared dataset clouds"
        )
    expected_entry_count = 2 * declared_count
    if len(expected) != expected_entry_count:
        errors.append(
            f"expected {expected_entry_count} manifest entries, found {len(expected)}"
        )

    if errors:
        print("Dataset verification failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(
        f"Verified {len(expected_images)} image hashes and "
        f"{len(expected_point_clouds)} point-cloud hashes in {args.dataset}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
