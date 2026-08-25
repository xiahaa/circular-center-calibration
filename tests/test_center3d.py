# SPDX-License-Identifier: Apache-2.0

import sys
import unittest
from pathlib import Path

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from circular_center.center3d import (  # noqa: E402
    CircleFitError,
    FitStatus,
    circle_residuals,
    fit_cga_circle,
    fit_circle_ransac,
    ransac_iteration_bound,
)


class Center3dTest(unittest.TestCase):
    @staticmethod
    def make_circle(center, radius, normal, sample_count=64, arc=2.0 * np.pi):
        normal = np.asarray(normal, dtype=float)
        normal /= np.linalg.norm(normal)
        reference_axis = np.eye(3)[np.argmin(np.abs(normal))]
        basis_u = np.cross(normal, reference_axis)
        basis_u /= np.linalg.norm(basis_u)
        basis_v = np.cross(normal, basis_u)
        angles = 0.37 + np.linspace(0.0, arc, sample_count, endpoint=False)
        points = center + radius * (
            np.cos(angles)[:, None] * basis_u
            + np.sin(angles)[:, None] * basis_v
        )
        return points, normal

    def test_cga_recovers_exact_circle(self):
        center = np.array([1.5, -0.7, 2.0])
        points, normal = self.make_circle(center, 0.8, [0.3, -0.4, 0.866])
        result = fit_cga_circle(points)

        np.testing.assert_allclose(result.center, center, atol=1e-8)
        self.assertAlmostEqual(result.radius, 0.8, places=8)
        self.assertGreater(abs(np.dot(result.normal, normal)), 1.0 - 1e-8)
        self.assertEqual(result.status, FitStatus.SUCCESS)
        self.assertTrue(np.isfinite(result.condition_number))

    def test_cga_recovers_partial_arc(self):
        center = np.array([1.2, -2.4, 0.7])
        points, _ = self.make_circle(
            center,
            1.1,
            [0.31, -0.52, 0.79],
            arc=2.0 * np.pi / 3.0,
        )
        result = fit_cga_circle(points)
        np.testing.assert_allclose(result.center, center, atol=1e-8)
        self.assertAlmostEqual(result.radius, 1.1, places=8)

    def test_cga_rejects_collinear_points(self):
        coordinates = np.linspace(-1.0, 1.0, 10)
        points = np.column_stack((coordinates, 2.0 * coordinates, -coordinates))
        with self.assertRaises(CircleFitError) as context:
            fit_cga_circle(points)
        self.assertEqual(context.exception.status, FitStatus.DEGENERATE)

    def test_residual_is_zero_on_exact_circle(self):
        center = np.array([1.5, -0.7, 2.0])
        points, normal = self.make_circle(center, 0.8, [0.2, -0.5, 0.7])
        np.testing.assert_allclose(
            circle_residuals(points, center, 0.8, normal),
            0.0,
            atol=1e-14,
        )

    def test_normalized_cga_handles_scale_and_translation(self):
        for radius, translation in ((1e-6, 1e3), (1.0, 1e6), (1e6, 1e6)):
            center = np.array([translation, -0.5 * translation, 0.25 * translation])
            points, normal = self.make_circle(center, radius, [0.3, 0.4, 0.5], 128)
            result = fit_cga_circle(points)
            tolerance = max(1e-8 * radius, 5e-10 * max(1.0, translation))
            self.assertLess(np.linalg.norm(result.center - center), tolerance)
            self.assertLess(abs(result.radius - radius), tolerance)
            self.assertGreater(abs(np.dot(result.normal, normal)), 1.0 - 1e-9)

    def test_ransac_iteration_bound_matches_formula(self):
        expected = int(np.ceil(np.log(1.0 - 0.99) / np.log(1.0 - 0.8**5)))
        self.assertEqual(ransac_iteration_bound(0.8, 5, 0.99, 500), expected)
        self.assertEqual(ransac_iteration_bound(1.0, 5, 0.99, 500), 1)

    def test_deterministic_ransac_rejects_outliers(self):
        center = np.array([1.5, -0.7, 2.0])
        circle_points, normal = self.make_circle(center, 0.8, [0.3, -0.4, 0.8], 80)
        generator = np.random.default_rng(9)
        circle_points += generator.normal(scale=0.002, size=circle_points.shape)
        outliers = center + generator.uniform(-2.0, 2.0, size=(20, 3))
        points = np.vstack((circle_points, outliers))

        first = fit_circle_ransac(
            points,
            residual_threshold=0.015,
            max_iterations=250,
            minimum_inliers=60,
            seed=77,
        )
        second = fit_circle_ransac(
            points,
            residual_threshold=0.015,
            max_iterations=250,
            minimum_inliers=60,
            seed=77,
        )

        self.assertLess(np.linalg.norm(first.center - center), 0.002)
        self.assertLess(abs(first.radius - 0.8), 0.002)
        self.assertGreater(abs(np.dot(first.normal, normal)), 0.99999)
        self.assertGreaterEqual(np.count_nonzero(first.inlier_mask), 75)
        np.testing.assert_allclose(first.center, second.center, atol=1e-12)
        np.testing.assert_array_equal(first.inlier_mask, second.inlier_mask)


if __name__ == "__main__":
    unittest.main()
