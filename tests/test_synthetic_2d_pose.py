# SPDX-License-Identifier: Apache-2.0

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from circular_center.evaluation import (  # noqa: E402
    evaluate_pose,
    fit_pnp_ransac,
)
from circular_center.experiments.runner import run_experiment  # noqa: E402
from experiments.synthetic_2d_pose.generators import (  # noqa: E402
    generate_trial,
    make_trial_seeds,
)
from experiments.synthetic_2d_pose.protocol import (  # noqa: E402
    load_profile,
    load_protocol,
)


class Synthetic2DPoseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = REPOSITORY_ROOT / "experiments" / "synthetic_2d_pose"
        cls.protocol = load_protocol(cls.directory)

    def test_paper_profile_matches_figure_9_protocol(self):
        profile = load_profile(self.directory, "paper")
        self.assertEqual(profile["trials"], 50)
        self.assertEqual(profile["circles_per_trial"], 20)
        self.assertEqual(self.protocol["paper_reference"]["archived_unique_trials"], 50)
        self.assertEqual(self.protocol["pnp"]["reprojection_threshold_px"], 5.0)
        self.assertEqual(
            self.protocol["paper_outputs"]["method_order"],
            [
                "Ellipse Center",
                "Mass Center",
                "Refined Center",
                "Quasi-RANSAC",
            ],
        )
        quasi = self.protocol["method_parameters"]["ambiguity"]["Quasi-RANSAC"]
        self.assertEqual(quasi["max_iterations"], 1000)
        self.assertFalse(quasi["adaptive"])
        self.assertEqual(quasi["scoring"], "mean_error")

    def test_generator_is_deterministic(self):
        seed = make_trial_seeds(self.protocol["seed"], 1)[0]
        first = generate_trial(seed, self.protocol, 4)
        second = generate_trial(seed, self.protocol, 4)
        np.testing.assert_array_equal(first.rotation, second.rotation)
        np.testing.assert_array_equal(first.translation, second.translation)
        np.testing.assert_allclose(
            first.translation.reshape(-1),
            [0.9769548, -1.17304815, 3.14276315],
            atol=1e-8,
        )
        np.testing.assert_allclose(
            first.observations[0].ground_truth_2d,
            [784.05510563, 443.34091208],
            atol=1e-8,
        )

    def test_pose_evaluation_round_trip(self):
        points = np.array(
            [
                [-0.8, -0.6, 0.1],
                [0.8, -0.5, -0.1],
                [-0.7, 0.6, 0.2],
                [0.7, 0.7, -0.2],
                [-0.4, -0.2, 0.8],
                [0.5, -0.1, 0.6],
                [-0.3, 0.4, 0.9],
                [0.4, 0.3, 0.7],
            ],
            dtype=float,
        )
        intrinsic = np.array(
            [[600.0, 0.0, 640.0], [0.0, 600.0, 480.0], [0.0, 0.0, 1.0]]
        )
        rotation = np.eye(3)
        translation = np.array([[0.1], [-0.2], [5.0]])
        camera = rotation @ points.T + translation
        homogeneous = intrinsic @ camera
        image = (homogeneous[:2] / homogeneous[2]).T
        estimate = fit_pnp_ransac(points, image, intrinsic, seed=2025)
        metrics = evaluate_pose(estimate, rotation, translation)
        self.assertLess(metrics.reprojection_error_px, 1e-3)
        self.assertLess(metrics.rotation_error_rad, 1e-4)
        self.assertLess(metrics.translation_error, 1e-3)

    def test_ci_profile_runs_four_methods_and_writes_figure(self):
        config = (
            REPOSITORY_ROOT
            / "configs"
            / "experiments"
            / "synthetic_2d_pose"
            / "ci.yaml"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory)
            result = run_experiment(config, output_directory=output)
            profile = result["profiles"][0]
            self.assertEqual(profile["trials"], 1)
            self.assertEqual(profile["circles_per_trial"], 4)
            self.assertEqual(profile["record_count"], 4)
            self.assertTrue(
                (output / "ci" / "error_bar_comparison.png").is_file()
            )
            self.assertTrue((output / "ci" / "raw_results.csv").is_file())
            self.assertTrue((output / "summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
