# SPDX-License-Identifier: Apache-2.0

import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from circular_center.center2d import (  # noqa: E402
    fit_quasi_ransac,
    get_ellipse_polynomial_coeff,
    refine_projected_center,
)
from circular_center.center3d import fit_cga_circle, fit_circle_ransac  # noqa: E402
from circular_center.interfaces import (  # noqa: E402
    AmbiguousCorrespondences,
    EllipseObservation,
)
from circular_center.methods.center3d import PCLUnavailableError  # noqa: E402
from circular_center.registry import (  # noqa: E402
    MethodCatalog,
    MethodConfigurationError,
)

METHOD_CONFIG_ROOT = REPOSITORY_ROOT / "configs" / "methods"


class MethodRegistryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = MethodCatalog.from_directory(METHOD_CONFIG_ROOT)

    def test_catalog_uses_exact_paper_names(self):
        self.assertEqual(
            self.catalog.names("center2d"),
            ("Ellipse Center", "Mass Center", "Refined Center"),
        )
        self.assertEqual(
            self.catalog.names("center3d"),
            ("CGA", "CGA-RANSAC", "PCL SACMODEL"),
        )
        self.assertEqual(
            self.catalog.names("ambiguity"),
            ("Homography Validation", "Quasi-RANSAC"),
        )

    def test_kind_mismatch_is_rejected_before_import(self):
        with self.assertRaisesRegex(MethodConfigurationError, "expected 'center3d'"):
            self.catalog.create("Ellipse Center", "center3d")

    def test_ellipse_and_mass_center_share_the_2d_contract(self):
        ellipse = np.array([12.0, 8.0, 4.0, 2.0, 0.0])
        observation = EllipseObservation(
            ellipse=ellipse,
            polynomial=np.ones(6),
            intrinsic=np.eye(3),
            marker_diameter=0.2,
            contour=np.array([[1.0, 2.0], [5.0, 2.0], [5.0, 6.0], [1.0, 6.0]]),
        )
        ellipse_result = self.catalog.create(
            "Ellipse Center", "center2d"
        ).estimate(observation)
        mass_result = self.catalog.create("Mass Center", "center2d").estimate(observation)

        np.testing.assert_array_equal(ellipse_result.primary, [12.0, 8.0])
        np.testing.assert_allclose(mass_result.primary, [3.0, 4.0], atol=1e-12)
        self.assertEqual(ellipse_result.method, "Ellipse Center")
        self.assertEqual(mass_result.method, "Mass Center")

    def test_refined_center_wrapper_preserves_legacy_result(self):
        ellipse = np.array([64.0, 48.0, 20.0, 10.0, np.deg2rad(25.0)])
        polynomial = get_ellipse_polynomial_coeff(
            ((64.0, 48.0), (40.0, 20.0), 25.0)
        )
        intrinsic = np.array(
            [[80.0, 0.0, 64.0], [0.0, 80.0, 48.0], [0.0, 0.0, 1.0]]
        )
        observation = EllipseObservation(
            ellipse=ellipse,
            polynomial=polynomial,
            intrinsic=intrinsic,
            marker_diameter=0.24,
        )
        legacy = refine_projected_center(
            ellipse,
            polynomial,
            intrinsic,
            0.24,
            input_is_rectified=True,
        )
        plugin = self.catalog.create("Refined Center", "center2d").estimate(observation)

        np.testing.assert_array_equal(plugin.candidates, legacy.candidates)
        np.testing.assert_array_equal(plugin.scores, legacy.scores)
        self.assertEqual(plugin.status, legacy.status.value)
        self.assertEqual(plugin.diagnostics["evaluations"], legacy.evaluations)

    def test_3d_wrappers_preserve_legacy_results(self):
        angles = np.linspace(0.0, 2.0 * np.pi, 32, endpoint=False)
        inliers = np.column_stack(
            (0.4 + 0.2 * np.cos(angles), -0.3 + 0.2 * np.sin(angles), np.ones(32))
        )
        outliers = np.array([[1.1, 0.4, 1.4], [-0.8, 0.2, 0.1]])
        contaminated = np.vstack((inliers, outliers))

        legacy_cga = fit_cga_circle(inliers)
        plugin_cga = self.catalog.create("CGA", "center3d").fit(inliers)
        np.testing.assert_array_equal(plugin_cga.center, legacy_cga.center)
        self.assertEqual(plugin_cga.radius, legacy_cga.radius)

        arguments = {
            "residual_threshold_m": 0.001,
            "minimum_inliers": 28,
            "seed": 17,
        }
        legacy_robust = fit_circle_ransac(
            contaminated,
            residual_threshold=arguments["residual_threshold_m"],
            minimum_inliers=arguments["minimum_inliers"],
            seed=arguments["seed"],
        )
        plugin_robust = self.catalog.create(
            "CGA-RANSAC", "center3d", arguments
        ).fit(contaminated)
        np.testing.assert_array_equal(plugin_robust.center, legacy_robust.center)
        np.testing.assert_array_equal(plugin_robust.inlier_mask, legacy_robust.inlier_mask)

    def test_pcl_plugin_is_lazy_and_reports_a_missing_library(self):
        angles = np.linspace(0.0, 2.0 * np.pi, 16, endpoint=False)
        points = np.column_stack(
            (np.cos(angles), np.sin(angles), np.zeros_like(angles))
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing = Path(temporary_directory) / "missing-pcl-library.so"
            plugin = self.catalog.create(
                "PCL SACMODEL", "center3d", {"library_path": str(missing)}
            )
            self.assertEqual(plugin.name, "PCL SACMODEL")
            with self.assertRaisesRegex(PCLUnavailableError, "shared library is unavailable"):
                plugin.fit(points)

    @unittest.skipUnless(
        os.environ.get("CIRCULAR_CENTER_PCL_LIBRARY"),
        "PCL integration library is not configured",
    )
    def test_pcl_plugin_fits_an_exact_circle(self):
        angles = np.linspace(0.0, 2.0 * np.pi, 64, endpoint=False)
        expected_center = np.array([0.4, -0.3, 1.2])
        points = expected_center + np.column_stack(
            (0.8 * np.cos(angles), 0.8 * np.sin(angles), np.zeros_like(angles))
        )
        plugin = self.catalog.create(
            "PCL SACMODEL",
            "center3d",
            {
                "library_path": os.environ["CIRCULAR_CENTER_PCL_LIBRARY"],
                "residual_threshold_m": 0.001,
            },
        )
        result = plugin.fit(points)
        np.testing.assert_allclose(result.center, expected_center, atol=1e-3)
        self.assertAlmostEqual(result.radius, 0.8, delta=1e-3)
        self.assertEqual(np.count_nonzero(result.inlier_mask), len(points))

    def test_quasi_ransac_wrapper_matches_core_result(self):
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
            ]
        )
        intrinsic = np.array(
            [[600.0, 0.0, 640.0], [0.0, 600.0, 480.0], [0.0, 0.0, 1.0]]
        )
        camera = points + np.array([0.1, -0.2, 5.0])
        homogeneous = (intrinsic @ camera.T).T
        projected = homogeneous[:, :2] / homogeneous[:, 2, None]
        alternative = projected + np.array([35.0, -25.0])
        inputs = AmbiguousCorrespondences(points, projected, alternative, intrinsic)
        arguments = {"inlier_threshold_px": 2.0, "seed": 2025}

        core = fit_quasi_ransac(
            points,
            projected,
            alternative,
            intrinsic,
            inlier_threshold=2.0,
            max_iterations=2000,
            seed=2025,
            adaptive=False,
            scoring="msac",
        )
        plugin = self.catalog.create(
            "Quasi-RANSAC", "ambiguity", arguments
        ).resolve(inputs)
        np.testing.assert_array_equal(plugin.rotation, core.rotation)
        np.testing.assert_array_equal(plugin.translation, core.translation)
        np.testing.assert_array_equal(plugin.inlier_mask, core.inlier_mask)

    def test_invalid_yaml_is_rejected_with_its_source(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "invalid.yaml"
            source.write_text("name: incomplete\n", encoding="utf-8")
            with self.assertRaisesRegex(MethodConfigurationError, "invalid.yaml"):
                MethodCatalog.from_directory(Path(temporary_directory))


if __name__ == "__main__":
    unittest.main()
