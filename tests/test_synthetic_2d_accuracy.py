# SPDX-License-Identifier: Apache-2.0

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from circular_center.center2d import generate_rounded_masked_points  # noqa: E402
from circular_center.experiments.runner import run_experiment  # noqa: E402
from circular_center.interfaces import EllipseObservation  # noqa: E402
from circular_center.registry import MethodCatalog  # noqa: E402
from experiments.synthetic_2d_accuracy.generators import (  # noqa: E402
    generate_sample,
    make_trial_seeds,
)
from experiments.synthetic_2d_accuracy.protocol import (  # noqa: E402
    load_profile,
    load_protocol,
)


class Synthetic2DAccuracyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = REPOSITORY_ROOT / "experiments" / "synthetic_2d_accuracy"
        cls.protocol = load_protocol(cls.directory)

    def test_paper_profile_matches_figure_8_protocol(self):
        profile = load_profile(self.directory, "paper")
        self.assertEqual(profile["trials"], 1000)
        self.assertEqual(self.protocol["camera"]["fx_px"], 600.0)
        self.assertEqual(self.protocol["camera"]["cx_px"], 640.0)
        self.assertEqual(self.protocol["sampling"]["image_noise_sigma_px"], 1.0)
        self.assertEqual(
            self.protocol["paper_outputs"]["method_order"],
            ["Refined Center", "Ellipse Center", "Mass Center"],
        )
        refined = self.protocol["method_parameters"]["2d"]["Refined Center"]
        self.assertEqual(refined["search_mode"], "paper_integer_grid")
        self.assertEqual(refined["directions"], 4)

    def test_generator_reproduces_first_released_trial(self):
        seed = make_trial_seeds(self.protocol["seed"], 1)[0]
        first = generate_sample(seed, self.protocol)
        second = generate_sample(seed, self.protocol)
        np.testing.assert_array_equal(first.primary.parameters, second.primary.parameters)
        np.testing.assert_allclose(
            first.ground_truth,
            [659.56781725, 476.44753846],
            atol=1e-8,
        )
        np.testing.assert_allclose(
            first.primary.parameters[:2],
            [672.59545898, 460.03530884],
            atol=1e-8,
        )

    def test_fast_integer_grid_matches_historical_dense_construction(self):
        ellipse = np.array([101.3, 79.8, 12.0, 18.0, 0.63])
        ratio = 0.5
        semi_a, semi_b = ellipse[2:4] * ratio
        x = np.arange(-semi_a, semi_a, 0.1)
        y = np.arange(-semi_b, semi_b, 0.1)
        xx, yy = np.meshgrid(x, y, indexing="xy")
        inside = np.square(xx / semi_a) + np.square(yy / semi_b) <= 1.0
        local = np.column_stack((xx[inside], yy[inside]))
        angle = ellipse[4]
        rotation = np.array(
            [
                [np.cos(angle), -np.sin(angle)],
                [np.sin(angle), np.cos(angle)],
            ]
        )
        expected = np.unique(
            np.rint(local @ rotation.T + ellipse[:2]).astype(int), axis=0
        )
        actual = generate_rounded_masked_points(ellipse, ratio).astype(int)
        np.testing.assert_array_equal(actual, expected)

    def test_paper_mode_is_selected_through_plugin_overrides(self):
        seed = make_trial_seeds(self.protocol["seed"], 1)[0]
        sample = generate_sample(seed, self.protocol)
        catalog = MethodCatalog.from_directory(REPOSITORY_ROOT / "configs" / "methods")
        method = catalog.create(
            "Refined Center",
            "center2d",
            self.protocol["method_parameters"]["2d"]["Refined Center"],
        )
        ambiguity = catalog.create(
            "Homography Validation",
            "ambiguity",
            self.protocol["method_parameters"]["ambiguity"][
                "Homography Validation"
            ],
        )
        observation = EllipseObservation(
            sample.primary.parameters,
            sample.primary.polynomial,
            sample.intrinsic,
            2.0 * sample.marker_radius,
            contour=sample.primary.mass_contour,
        )
        result = method.estimate(observation)
        np.testing.assert_array_equal(result.candidates, np.rint(result.candidates))
        selected, rejected = ambiguity.select(
            sample.primary.parameters,
            sample.primary.polynomial,
            sample.primary.contour,
            sample.coplanar.contour,
            sample.intrinsic,
            sample.marker_radius,
            candidates=result.candidates,
        )
        self.assertEqual(selected.shape, (2,))
        self.assertEqual(rejected.shape, (2,))
        self.assertFalse(np.array_equal(selected, rejected))

    def test_ci_profile_runs_all_selected_methods_and_writes_figure(self):
        config = (
            REPOSITORY_ROOT
            / "configs"
            / "experiments"
            / "synthetic_2d_accuracy"
            / "ci.yaml"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory)
            result = run_experiment(config, output_directory=output)
            profile = result["profiles"][0]
            self.assertEqual(profile["trials"], 2)
            self.assertEqual(profile["record_count"], 6)
            self.assertTrue(
                (output / "ci" / "validation_error_distribution.png").is_file()
            )
            self.assertTrue((output / "ci" / "raw_results.csv").is_file())
            self.assertTrue((output / "summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
