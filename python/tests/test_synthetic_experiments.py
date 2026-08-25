# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "experiments" / "synthetic" / "run_experiments.py"


def _load_runner():
    specification = importlib.util.spec_from_file_location("synthetic_experiments", SCRIPT)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_paper_profile_matches_legacy_3d_configuration_counts() -> None:
    runner = _load_runner()
    configurations = runner._three_dimensional_configurations("paper")

    noise = [item for item in configurations if item["sweep"] == "noise_sigma_m"]
    spans = [item for item in configurations if item["sweep"] == "visible_arc_degrees"]
    outliers = [item for item in configurations if item["sweep"] == "outlier_ratio"]
    stress = [item for item in configurations if item["sweep"] == "legacy_scenario"]

    assert [item["setting"] for item in noise] == [1e-4, 1e-3, 1e-2, 1e-1, 1.0]
    assert all(item["count"] == 50 and item["default_trials"] == 500 for item in noise)
    assert [item["setting"] for item in spans] == [90, 135, 180, 225, 270, 315, 360]
    assert all(item["count"] == 50 and item["default_trials"] == 500 for item in spans)
    assert [item["setting"] for item in outliers] == [0.1, 0.2, 0.3, 0.4, 0.5]
    assert all(item["count"] == 50 and item["default_trials"] == 100 for item in outliers)
    assert [item["default_trials"] for item in stress] == [1000, 1000, 1000, 1000]


def test_legacy_outliers_reproduce_effective_integer_distribution() -> None:
    runner = _load_runner()
    configuration = next(
        item
        for item in runner._three_dimensional_configurations("paper")
        if item["sweep"] == "outlier_ratio" and item["setting"] == 0.3
    )
    _, _, _, points = runner._generate_three_dimensional_sample(
        np.random.default_rng(17),
        configuration,
    )

    outliers = points[configuration["count"] :]
    assert points.shape == (65, 3)
    assert np.all((outliers >= 10.0) & (outliers <= 20.0))
    assert np.array_equal(outliers, np.floor(outliers))


def test_symmetric_stress_angles_follow_legacy_interval_construction() -> None:
    runner = _load_runner()
    angles = runner._angles(
        np.random.default_rng(11),
        count=20,
        span_degrees=200.0,
        distribution="symmetric_nonuniform",
    )

    assert angles.shape == (20,)
    assert np.isclose(angles[0], -np.deg2rad(100.0))
    assert np.isclose(angles[10], 0.0)
    assert np.all(np.diff(angles[:11]) >= 0.0)
    assert np.all(np.diff(angles[10:]) >= 0.0)
