#!/usr/bin/env python3
"""Build the official AAMED Python extension from its Git submodule."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _opencv_include_directory() -> Path:
    include_root = Path(sys.prefix) / "include"
    candidates = sorted(include_root.glob("opencv[0-9]*"), reverse=True)
    for candidate in candidates:
        if (candidate / "opencv2" / "opencv.hpp").is_file():
            return candidate
    raise RuntimeError(
        "OpenCV C++ headers were not found under {}; use the Conda installation "
        "from environment.yml".format(include_root)
    )


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    checkout = repository_root / "thirdparty" / "AAMED"
    if not (checkout / "python" / "setup.py").is_file():
        raise RuntimeError(
            "AAMED submodule is not initialized; run `git submodule update --init "
            "--recursive thirdparty/AAMED` from the repository root"
        )

    python_directory = checkout / "python"
    environment = os.environ.copy()
    include_directory = _opencv_include_directory()
    existing = environment.get("CPLUS_INCLUDE_PATH")
    environment["CPLUS_INCLUDE_PATH"] = (
        str(include_directory)
        if not existing
        else os.pathsep.join((str(include_directory), existing))
    )
    subprocess.run(
        [sys.executable, "setup.py", "build_ext", "--inplace", "--force"],
        cwd=python_directory,
        env=environment,
        check=True,
    )
    artifacts = tuple(python_directory.glob("pyAAMED*.so")) + tuple(
        python_directory.glob("pyAAMED*.pyd")
    )
    if not artifacts:
        raise RuntimeError("AAMED build completed without producing a Python extension")
    test_environment = environment.copy()
    existing_python_path = test_environment.get("PYTHONPATH")
    test_environment["PYTHONPATH"] = (
        str(python_directory)
        if not existing_python_path
        else os.pathsep.join((str(python_directory), existing_python_path))
    )
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from pyAAMED import pyAAMED; print('AAMED import: OK')",
        ],
        env=test_environment,
        check=True,
    )
    print("built {}".format(artifacts[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
