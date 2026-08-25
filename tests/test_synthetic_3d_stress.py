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
from experiments.synthetic_3d_stress.generators import (  # noqa: E402
    derive_trial_seed,
    generate_sample,
)
from experiments.synthetic_3d_stress.protocol import (  # noqa: E402
    load_profile,
    load_protocol,
)


class Synthetic3DStressTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = REPOSITORY_ROOT / "experiments" / "synthetic_3d_stress"
        cls.protocol = load_protocol(cls.directory)

    def test_paper_profile_matches_figure_6(self):
        profile = load_profile(self.directory, "paper")
        self.assertEqual(profile["trials_per_cell"], 300)
        self.assertEqual(profile["point_counts"], [5, 8, 16, 32, 64, 128])
        self.assertEqual(profile["arc_degrees"], [45, 60, 90, 120, 180, 270, 360])
        self.assertEqual(len(profile["distributions"]), 4)
        self.assertAlmostEqual(self.protocol["circle"]["radius_m"], 0.12)
        self.assertAlmostEqual(self.protocol["success_threshold_m"], 0.01)

    def test_generator_is_deterministic_and_respects_radius(self):
        seed = derive_trial_seed(2025, 1, 16, 90, 3)
        options = dict(
            distribution="single_arc",
            point_count=16,
            arc_degrees=90,
            radius_m=0.12,
            noise_sigma_m=0.0,
            center_min_m=-2.0,
            center_max_m=2.0,
            band_jitter_degrees=0.5,
        )
        first = generate_sample(seed, **options)
        second = generate_sample(seed, **options)
        np.testing.assert_array_equal(first.points, second.points)
        distances = np.linalg.norm(first.points - first.center, axis=1)
        np.testing.assert_allclose(distances, 0.12, atol=1e-12)

    @unittest.skipUnless(
        os.environ.get("CIRCULAR_CENTER_PCL_LIBRARY"),
        "PCL integration library is not configured",
    )
    def test_ci_profile_writes_heatmap(self):
        config = (
            REPOSITORY_ROOT
            / "configs"
            / "experiments"
            / "synthetic_3d_stress"
            / "ci.yaml"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory)
            result = run_experiment(config, output_directory=output)
            profile = result["profiles"][0]
            self.assertEqual(profile["record_count"], 64)
            self.assertEqual(profile["cell_count"], 32)
            self.assertTrue((output / "ci" / "raw_results.csv").is_file())
            self.assertTrue((output / "ci" / "cell_summary.csv").is_file())
            self.assertTrue(
                (output / "ci" / "stress_heatmap_nominal_noise.pdf").is_file()
            )
            self.assertTrue((output / "summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
