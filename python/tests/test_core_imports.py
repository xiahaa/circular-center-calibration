# SPDX-License-Identifier: Apache-2.0

import importlib
import sys
import unittest
from pathlib import Path

import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "python" / "src"))

from circular_center.center2d import get_ellipse_polynomial_coeff  # noqa: E402
from circular_center.center2d import find_rectify_homography  # noqa: E402
from circular_center.center3d import circle_residuals  # noqa: E402


class CoreImportTest(unittest.TestCase):
    def test_circle_ellipse_coefficients_are_finite(self):
        ellipse = ((320.0, 240.0), (80.0, 80.0), 0.0)
        coefficients = get_ellipse_polynomial_coeff(ellipse)
        self.assertEqual(coefficients.shape, (6,))
        self.assertTrue(np.isfinite(coefficients).all())

    def test_homography_module_uses_package_imports(self):
        normalized, scale = find_rectify_homography.normalize_matrix_determinant(
            np.eye(3)
        )
        np.testing.assert_allclose(normalized, np.eye(3))
        self.assertEqual(scale, 1.0)

    def test_python38_can_import_migrated_modules(self):
        module_names = [
            "circular_center.center2d.grid_search_refinement",
            "circular_center.center2d.ransac_validation",
            "circular_center.center3d.fitting",
        ]
        for module_name in module_names:
            with self.subTest(module=module_name):
                importlib.import_module(module_name)

    def test_exact_3d_circle_has_zero_fitting_error(self):
        angles = np.linspace(0.0, 2.0 * np.pi, 32, endpoint=False)
        points = np.column_stack((np.cos(angles), np.sin(angles), np.zeros_like(angles)))
        residuals = circle_residuals(
            points,
            center=np.zeros(3),
            radius=1.0,
            normal=np.array([0.0, 0.0, 1.0]),
        )
        np.testing.assert_allclose(residuals, 0.0, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
