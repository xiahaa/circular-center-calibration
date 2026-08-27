# SPDX-License-Identifier: Apache-2.0

import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from circular_center.experiments.runner import run_experiment  # noqa: E402
from experiments.synthetic_3d_target_tolerance.generators import (  # noqa: E402
    derive_trial_seed,
    generate_sample,
)
from experiments.synthetic_3d_target_tolerance.protocol import (  # noqa: E402
    load_profile,
    load_protocol,
)


class Synthetic3DTargetToleranceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = (
            REPOSITORY_ROOT / "experiments" / "synthetic_3d_target_tolerance"
        )
        cls.protocol = load_protocol(cls.directory)

    def test_paper_profile_matches_figure_7(self):
        profile = load_profile(self.directory, "paper")
        self.assertEqual(profile["trials_per_setting"], 300)
        self.assertEqual(
            profile["magnitudes"], [0.0, 0.0025, 0.005, 0.01, 0.02, 0.05]
        )
        self.assertEqual(self.protocol["target"]["point_count"], 64)
        self.assertAlmostEqual(self.protocol["target"]["radius_m"], 0.12)
        self.assertEqual(len(self.protocol["paper_reference"]["mean_center_error_mm"]), 2)

    def test_generator_is_deterministic_and_deforms_target(self):
        options = dict(
            deformation="axis_deviation",
            magnitude=0.05,
            point_count=64,
            arc_degrees=180.0,
            radius_m=0.12,
            noise_sigma_m=0.0,
            center_min_m=-2.0,
            center_max_m=2.0,
            axis_semiaxis_scale=0.75,
        )
        seed = derive_trial_seed(2025, 4)
        first = generate_sample(seed, **options)
        second = generate_sample(seed, **options)
        np.testing.assert_array_equal(first.points, second.points)
        radii = np.linalg.norm(first.points - first.center, axis=1)
        self.assertGreater(float(np.ptp(radii)), 0.005)

    @unittest.skipUnless(
        os.environ.get("CIRCULAR_CENTER_PCL_LIBRARY"),
        "PCL integration library is not configured",
    )
    def test_ci_profile_writes_figure(self):
        config = (
            REPOSITORY_ROOT
            / "configs"
            / "experiments"
            / "synthetic_3d_target_tolerance"
            / "ci.yaml"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory)
            result = run_experiment(config, output_directory=output)
            profile = result["profiles"][0]
            self.assertEqual(profile["record_count"], 24)
            self.assertEqual(profile["setting_count"], 12)
            self.assertTrue((output / "ci" / "raw_results.csv").is_file())
            self.assertTrue((output / "ci" / "target_tolerance.pdf").is_file())
            self.assertTrue((output / "summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
