# SPDX-License-Identifier: Apache-2.0

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from circular_center.experiments.runner import run_experiment  # noqa: E402
from experiments.quasi_ransac_evaluation.generators import (  # noqa: E402
    derive_trial_seeds,
    generate_trial,
    rounded_outlier_count,
)
from experiments.quasi_ransac_evaluation.protocol import (  # noqa: E402
    load_profile,
    load_protocol,
)


class QuasiRansacEvaluationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = (
            REPOSITORY_ROOT / "experiments" / "quasi_ransac_evaluation"
        )
        cls.protocol = load_protocol(cls.directory)

    def test_paper_profile_matches_table_ii(self):
        profile = load_profile(self.directory, "paper")
        self.assertEqual(profile["trials_per_cell"], 1000)
        self.assertEqual(profile["point_counts"], [8, 12, 20])
        self.assertEqual(profile["outlier_ratios"], [0.0, 0.1, 0.2, 0.3])
        self.assertEqual(profile["confidences"], [0.95, 0.99, 0.999])
        self.assertEqual(self.protocol["table"]["method"], "Quasi-RANSAC")
        self.assertEqual(len(self.protocol["paper_reference"]["rows"]), 12)

    def test_small_count_outliers_use_paper_rounding(self):
        self.assertEqual(rounded_outlier_count(8, 0.1), 1)
        self.assertEqual(rounded_outlier_count(8, 0.2), 2)
        self.assertEqual(rounded_outlier_count(8, 0.3), 2)
        self.assertEqual(rounded_outlier_count(12, 0.3), 4)
        self.assertEqual(rounded_outlier_count(20, 0.3), 6)

    def test_generator_is_deterministic_and_swaps_candidate_order(self):
        seeds = derive_trial_seeds(self.protocol["seed"], 8, 0.1, 0)
        first = generate_trial(*seeds, 8, 0.1, self.protocol)
        second = generate_trial(*seeds, 8, 0.1, self.protocol)
        np.testing.assert_array_equal(first.points3d, second.points3d)
        np.testing.assert_array_equal(first.candidate_a, second.candidate_a)
        np.testing.assert_array_equal(first.candidate_b, second.candidate_b)
        self.assertEqual(int(np.count_nonzero(first.outlier_mask)), 1)
        self.assertGreaterEqual(float(np.min(first.points3d[:, 2])), 2.0)
        self.assertLessEqual(float(np.max(first.points3d[:, 2])), 5.0)

    def test_ci_profile_writes_all_outputs(self):
        config = (
            REPOSITORY_ROOT
            / "configs"
            / "experiments"
            / "quasi_ransac_evaluation"
            / "ci.yaml"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory)
            result = run_experiment(config, output_directory=output)
            profile = result["profiles"][0]
            self.assertEqual(profile["cell_count"], 8)
            self.assertEqual(profile["record_count"], 8)
            self.assertEqual(len(profile["table_rows"]), 4)
            self.assertTrue((output / "ci" / "raw_results.csv").is_file())
            self.assertTrue((output / "ci" / "full_summary.csv").is_file())
            self.assertTrue((output / "ci" / "quasi_ransac_table.tex").is_file())
            self.assertTrue((output / "summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
