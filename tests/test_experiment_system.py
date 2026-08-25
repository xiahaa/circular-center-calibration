# SPDX-License-Identifier: Apache-2.0

import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from circular_center.center3d import fit_circle_ransac  # noqa: E402
from circular_center.experiments.config import (  # noqa: E402
    ExperimentConfigurationError,
    load_experiment_selection,
)
from experiments.qualitative_realworld.data_io import read_pcd  # noqa: E402
from experiments.qualitative_realworld.detection2d import (  # noqa: E402
    detect_target_ellipse,
)
from experiments.qualitative_realworld.extraction3d import (  # noqa: E402
    extract_directional_boundary,
    select_target_cluster,
)


class ExperimentSystemTest(unittest.TestCase):
    def test_outer_config_stays_small_and_uses_paper_names(self):
        source = REPOSITORY_ROOT / "configs" / "experiments" / "qualitative_realworld.yaml"
        document = yaml.safe_load(source.read_text(encoding="utf-8"))
        self.assertEqual(
            set(document), {"schema_version", "experiment", "datasets", "methods"}
        )
        selection = load_experiment_selection(source)
        self.assertEqual(selection.name, "qualitative_realworld")
        self.assertEqual(selection.center2d_method, "Refined Center")
        self.assertEqual(selection.center3d_method, "CGA-RANSAC")
        self.assertEqual(selection.ambiguity_method, "Quasi-RANSAC")

    def test_outer_config_rejects_experiment_specific_parameters(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "experiment.yaml"
            source.write_text(
                "schema_version: 1\n"
                "experiment: qualitative_realworld\n"
                "datasets: [sample]\n"
                "methods: {2d: 'Ellipse Center', 3d: CGA, ambiguity: null}\n"
                "threshold: 17\n",
                encoding="utf-8",
            )
            with self.assertRaises(ExperimentConfigurationError):
                load_experiment_selection(source)

    def test_red_board_detector_returns_rectified_ellipse(self):
        image = np.full((480, 640, 3), 40, dtype=np.uint8)
        cv2.rectangle(image, (100, 60), (540, 420), (0, 0, 255), -1)
        cv2.ellipse(image, (320, 240), (90, 70), 18.0, 0.0, 360.0, (245, 245, 245), -1)
        intrinsic = np.array(
            [[600.0, 0.0, 320.0], [0.0, 600.0, 240.0], [0.0, 0.0, 1.0]]
        )
        config = yaml.safe_load(
            (
                REPOSITORY_ROOT
                / "experiments"
                / "qualitative_realworld"
                / "detection2d"
                / "config.yaml"
            ).read_text(encoding="utf-8")
        )
        detected = detect_target_ellipse(
            image, intrinsic, np.zeros(5), "plumb_bob", config
        )
        np.testing.assert_allclose(detected.ellipse[:2], [320.0, 240.0], atol=1.0)
        np.testing.assert_allclose(
            np.sort(detected.ellipse[2:4]), np.sort([70.0, 90.0]), atol=1.5
        )
        self.assertGreater(detected.axis_ratio, 0.7)

    def test_high_reflectance_cluster_boundary_recovers_circle(self):
        generator = np.random.default_rng(2025)
        normal = np.array([0.3, -0.4, 0.8660254])
        normal /= np.linalg.norm(normal)
        reference = np.eye(3)[np.argmin(np.abs(normal))]
        basis_u = np.cross(normal, reference)
        basis_u /= np.linalg.norm(basis_u)
        basis_v = np.cross(normal, basis_u)
        sample_count = 600
        angles = generator.uniform(0.0, 2.0 * np.pi, sample_count)
        radii = 0.175 * np.sqrt(generator.uniform(0.0, 1.0, sample_count))
        center = np.array([1.5, -0.7, 0.4])
        target = center + radii[:, None] * (
            np.cos(angles)[:, None] * basis_u
            + np.sin(angles)[:, None] * basis_v
        )
        target += generator.normal(0.0, 0.0015, size=(sample_count, 1)) * normal
        false_cluster = np.column_stack(
            (
                np.linspace(-0.5, 0.5, 100),
                np.zeros(100),
                np.zeros(100),
            )
        ) + np.array([-2.0, 1.0, 0.0])
        selected = select_target_cluster(
            np.vstack((target, false_cluster)),
            marker_diameter_m=0.35,
            neighbor_radius_m=0.05,
            minimum_points=20,
            diameter_tolerance_m=0.10,
            maximum_plane_rmse_m=0.02,
        )
        boundary = extract_directional_boundary(
            selected.points, angular_bins=24, minimum_points=12
        )
        fitted = fit_circle_ransac(
            boundary,
            residual_threshold=0.015,
            minimum_inliers=12,
            seed=2025,
        )
        self.assertLess(np.linalg.norm(fitted.center - center), 0.015)
        self.assertLess(abs(fitted.radius - 0.175), 0.015)

    def test_binary_pcd_reader_keeps_valid_xyzi_points(self):
        dtype = np.dtype(
            [("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("intensity", "<f4")]
        )
        records = np.array(
            [(1.0, 2.0, 3.0, 255.0), (0.0, 0.0, 0.0, 0.0), (4.0, 5.0, 6.0, 180.0)],
            dtype=dtype,
        )
        header = (
            "VERSION 0.7\n"
            "FIELDS x y z intensity\n"
            "SIZE 4 4 4 4\n"
            "TYPE F F F F\n"
            "COUNT 1 1 1 1\n"
            "WIDTH 3\n"
            "HEIGHT 1\n"
            "POINTS 3\n"
            "DATA binary\n"
        ).encode("ascii")
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "sample.pcd"
            source.write_bytes(header + records.tobytes())
            cloud = read_pcd(source)
        np.testing.assert_array_equal(cloud.points, [[1, 2, 3], [4, 5, 6]])
        np.testing.assert_array_equal(cloud.intensity, [255, 180])


if __name__ == "__main__":
    unittest.main()
