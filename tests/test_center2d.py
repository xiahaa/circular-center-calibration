# SPDX-License-Identifier: Apache-2.0

import sys
import unittest
from pathlib import Path

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from circular_center.center2d import (  # noqa: E402
    ProjectedCenterError,
    ProjectedCenterStatus,
    QuasiRansacStatus,
    dense_grid_search_reference,
    fit_quasi_ransac,
    quasi_ransac_iteration_bound,
    rectify_contour,
    refine_projected_center,
)
from circular_center.center2d.ellipse_center_refinement import (  # noqa: E402
    eval_distance_f0,
    eval_distance_f0_batch,
    get_ellipse_polynomial_coeff,
)


class Center2dTest(unittest.TestCase):
    def test_batched_scores_match_scalar_reference(self):
        ellipse = ((640.0, 480.0), (240.0, 120.0), 30.0)
        polynomial = get_ellipse_polynomial_coeff(ellipse)
        intrinsic = np.array(
            [[600.0, 0.0, 640.0], [0.0, 600.0, 480.0], [0.0, 0.0, 1.0]]
        )
        candidates = np.array(
            [[640.0, 480.0], [645.0, 478.0], [620.0, 490.0], [660.0, 470.0]]
        )

        scalar_scores = np.array(
            [eval_distance_f0(polynomial, center, intrinsic, 4.0) for center in candidates]
        )
        batch_scores = eval_distance_f0_batch(polynomial, candidates, intrinsic, 4.0)

        np.testing.assert_allclose(batch_scores, scalar_scores, rtol=1e-8, atol=1e-10)

    def test_batched_scores_reject_invalid_shape(self):
        with self.assertRaisesRegex(ValueError, "shape"):
            eval_distance_f0_batch(np.ones(6), np.ones(2), np.eye(3), 1.0)

    def test_coarse_to_fine_matches_dense_reference(self):
        ellipse = np.array([64.0, 48.0, 20.0, 10.0, np.deg2rad(25.0)])
        ellipse_cv = ((64.0, 48.0), (40.0, 20.0), 25.0)
        polynomial = get_ellipse_polynomial_coeff(ellipse_cv)
        intrinsic = np.array(
            [[80.0, 0.0, 64.0], [0.0, 80.0, 48.0], [0.0, 0.0, 1.0]]
        )

        refined = refine_projected_center(
            ellipse,
            polynomial,
            intrinsic,
            0.24,
            input_is_rectified=True,
        )
        dense = dense_grid_search_reference(
            ellipse,
            polynomial,
            intrinsic,
            0.24,
            input_is_rectified=True,
        )

        direct = max(
            np.linalg.norm(refined.candidates[0] - dense.candidates[0]),
            np.linalg.norm(refined.candidates[1] - dense.candidates[1]),
        )
        swapped = max(
            np.linalg.norm(refined.candidates[0] - dense.candidates[1]),
            np.linalg.norm(refined.candidates[1] - dense.candidates[0]),
        )
        self.assertLessEqual(min(direct, swapped), 0.05 + 1e-12)
        self.assertEqual(refined.directions, 16)
        self.assertLess(refined.evaluations, dense.evaluations)
        self.assertIn(
            refined.status,
            (ProjectedCenterStatus.SUCCESS, ProjectedCenterStatus.AMBIGUOUS),
        )

    def test_coarse_to_fine_keeps_both_small_ellipse_basins(self):
        ellipse = np.array(
            [640.129517, 479.924622, 10.3184061, 14.7390337, 0.030352642]
        )
        ellipse_cv = (
            (ellipse[0], ellipse[1]),
            (2.0 * ellipse[2], 2.0 * ellipse[3]),
            np.rad2deg(ellipse[4]),
        )
        polynomial = get_ellipse_polynomial_coeff(ellipse_cv)
        intrinsic = np.array(
            [[600.0, 0.0, 640.0], [0.0, 600.0, 480.0], [0.0, 0.0, 1.0]]
        )
        refined = refine_projected_center(
            ellipse,
            polynomial,
            intrinsic,
            0.24,
            input_is_rectified=True,
        )
        dense = dense_grid_search_reference(
            ellipse,
            polynomial,
            intrinsic,
            0.24,
            input_is_rectified=True,
        )
        direct = max(
            np.linalg.norm(refined.candidates[0] - dense.candidates[0]),
            np.linalg.norm(refined.candidates[1] - dense.candidates[1]),
        )
        swapped = max(
            np.linalg.norm(refined.candidates[0] - dense.candidates[1]),
            np.linalg.norm(refined.candidates[1] - dense.candidates[0]),
        )
        self.assertLessEqual(min(direct, swapped), 0.05 + 1e-12)

    def test_projected_center_requires_rectified_input_contract(self):
        ellipse = np.array([64.0, 48.0, 20.0, 10.0, 0.0])
        polynomial = get_ellipse_polynomial_coeff(((64.0, 48.0), (40.0, 20.0), 0.0))
        with self.assertRaises(ProjectedCenterError) as context:
            refine_projected_center(
                ellipse,
                polynomial,
                np.eye(3),
                0.24,
                input_is_rectified=False,
            )
        self.assertEqual(context.exception.status, ProjectedCenterStatus.INVALID_INPUT)

    def test_pinhole_and_fisheye_zero_distortion_rectify_to_identity(self):
        import cv2

        contour = np.array([[50.0, 40.0], [64.0, 48.0], [80.0, 55.0]])
        intrinsic = np.array(
            [[80.0, 0.0, 64.0], [0.0, 80.0, 48.0], [0.0, 0.0, 1.0]]
        )
        pinhole, pinhole_K = rectify_contour(
            contour,
            intrinsic,
            np.zeros(8),
            model="pinhole",
        )
        normalized = np.column_stack(
            (
                (contour[:, 0] - intrinsic[0, 2]) / intrinsic[0, 0],
                (contour[:, 1] - intrinsic[1, 2]) / intrinsic[1, 1],
            )
        )
        fisheye_pixels = cv2.fisheye.distortPoints(
            normalized.reshape(-1, 1, 2),
            intrinsic,
            np.zeros(4),
        ).reshape(-1, 2)
        fisheye, fisheye_K = rectify_contour(
            fisheye_pixels,
            intrinsic,
            np.zeros(4),
            model="fisheye",
        )
        np.testing.assert_allclose(pinhole, contour, atol=1e-10)
        np.testing.assert_allclose(fisheye, contour, atol=1e-10)
        np.testing.assert_array_equal(pinhole_K, intrinsic)
        np.testing.assert_array_equal(fisheye_K, intrinsic)

    def test_quasi_ransac_confidence_formula_and_deterministic_pose(self):
        expected = int(np.ceil(np.log(1.0 - 0.99) / np.log(1.0 - (0.5) ** 4)))
        self.assertEqual(quasi_ransac_iteration_bound(1.0, 0.99, 4, 2000), expected)

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
        translation = np.array([[0.1], [-0.2], [5.0]])
        camera = points.T + translation
        projected = (intrinsic @ camera)
        projected = (projected[:2] / projected[2]).T
        alternative = projected + np.array([35.0, -25.0])

        first = fit_quasi_ransac(
            points,
            projected,
            alternative,
            intrinsic,
            inlier_threshold=2.0,
            seed=2025,
        )
        second = fit_quasi_ransac(
            points,
            projected,
            alternative,
            intrinsic,
            inlier_threshold=2.0,
            seed=2025,
        )
        self.assertEqual(first.status, QuasiRansacStatus.SUCCESS)
        self.assertEqual(first.iterations, second.iterations)
        np.testing.assert_allclose(first.rotation, second.rotation, atol=1e-10)
        np.testing.assert_allclose(first.translation, second.translation, atol=1e-10)
        self.assertLess(np.linalg.norm(first.translation - translation), 1e-3)
        self.assertLess(first.mean_reprojection_error, 1e-3)
        fitted_camera = first.rotation @ points.T + first.translation
        fitted_pixels = intrinsic @ fitted_camera
        fitted_pixels = (fitted_pixels[:2] / fitted_pixels[2]).T
        primary_error = np.linalg.norm(fitted_pixels - projected, axis=1)
        alternative_error = np.linalg.norm(fitted_pixels - alternative, axis=1)
        expected_selection = np.where(
            (primary_error <= alternative_error)[:, None], projected, alternative
        )
        np.testing.assert_array_equal(first.selected_points, expected_selection)

    def test_quasi_ransac_is_invariant_to_per_row_candidate_order(self):
        rng = np.random.default_rng(17)
        points3d = rng.normal(size=(30, 3))
        points3d[:, 2] += 8.0
        intrinsic = np.array(
            [[700.0, 0.0, 640.0], [0.0, 700.0, 360.0], [0.0, 0.0, 1.0]]
        )
        projected = (intrinsic @ points3d.T).T
        candidate_a = projected[:, :2] / projected[:, 2, None]
        candidate_b = candidate_a + np.column_stack(
            [np.full(len(points3d), 12.0), np.full(len(points3d), -7.0)]
        )
        swap = rng.random(len(points3d)) < 0.5
        shuffled_a = np.where(swap[:, None], candidate_b, candidate_a)
        shuffled_b = np.where(swap[:, None], candidate_a, candidate_b)

        reference = fit_quasi_ransac(
            points3d,
            candidate_a,
            candidate_b,
            intrinsic,
            seed=2025,
            adaptive=False,
            max_iterations=200,
        )
        shuffled = fit_quasi_ransac(
            points3d,
            shuffled_a,
            shuffled_b,
            intrinsic,
            seed=2025,
            adaptive=False,
            max_iterations=200,
        )

        np.testing.assert_allclose(reference.rotation, shuffled.rotation)
        np.testing.assert_allclose(reference.translation, shuffled.translation)
        np.testing.assert_allclose(reference.selected_points, shuffled.selected_points)
        np.testing.assert_array_equal(reference.inlier_mask, shuffled.inlier_mask)


if __name__ == "__main__":
    unittest.main()
