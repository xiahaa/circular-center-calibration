# SPDX-License-Identifier: Apache-2.0
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _version(path: str, pattern: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    match = re.search(pattern, text, flags=re.MULTILINE)
    assert match is not None, f"version not found in {path}"
    return match.group(1)


def test_release_versions_match() -> None:
    versions = {
        "CMakeLists.txt": _version(
            "CMakeLists.txt",
            r"^project\(circular_center_calibration VERSION ([0-9]+\.[0-9]+\.[0-9]+)",
        ),
        "CITATION.cff": _version(
            "CITATION.cff",
            r"^version:\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$",
        ),
        "pyproject.toml": _version(
            "pyproject.toml",
            r'^version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"\s*$',
        ),
    }

    assert len(set(versions.values())) == 1, f"release versions differ: {versions}"
