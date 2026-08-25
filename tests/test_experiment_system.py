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
from circular_center.experiments.runner import _instantiate_methods  # noqa: E402
from circular_center.registry import MethodCatalog  # noqa: E402
from experiments.qualitative_realworld.data_io import read_pcd  # noqa: E402
from experiments.qualitative_realworld.detection2d import (  # noqa: E402
    detect_target_ellipse,
)
from experiments.qualitative_realworld.extraction3d import (  # noqa: E402
    extract_directional_boundary,
    select_target_cluster,
)
from experiments.synthetic_3d_accuracy.generators import (  # noqa: E402
    add_reference_outliers,
    generate_monte_carlo_sample,
    make_generator,
)
from experiments.synthetic_3d_accuracy.protocol import (  # noqa: E402
    load_profile,
    load_protocol,
)


class ExperimentSystemTest(unittest.TestCase):
    def test_outer_configs_are_grouped_by_experiment(self):
        config_root = REPOSITORY_ROOT / "configs" / "experiments"
        self.assertEqual(list(config_root.glob("*.yaml")), [])

        config_paths = sorted(config_root.glob("*/*.yaml"))
        self.assertTrue(config_paths)
        for config_path in config_paths:
            document = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            self.assertEqual(document["experiment"], config_path.parent.name)
            self.assertIn(config_path.name, {"paper.yaml", "ci.yaml", "default.yaml"})

    def test_outer_config_stays_small_and_uses_paper_names(self):
        source = (
            REPOSITORY_ROOT
            / "configs"
            / "experiments"
            / "qualitative_realworld"
            / "default.yaml"
        )
        document = yaml.safe_load(source.read_text(encoding="utf-8"))
        self.assertEqual(
            set(document), {"schema_version", "experiment", "datasets", "methods"}
        )
        selection = load_experiment_selection(source)
        self.assertEqual(selection.name, "qualitative_realworld")
        self.assertEqual(selection.center2d_methods, ("Refined Center",))
        self.assertEqual(selection.center3d_methods, ("CGA-RANSAC",))
        self.assertEqual(selection.ambiguity_methods, ("Quasi-RANSAC",))

    def test_outer_config_supports_multiple_methods_and_null_stages(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "experiment.yaml"
            source.write_text(
                "schema_version: 1\n"
                "experiment: synthetic_3d_accuracy\n"
                "datasets: [synthetic]\n"
                "methods:\n"
                "  2d: null\n"
                "  3d: [CGA, CGA-RANSAC, PCL SACMODEL]\n"
                "  ambiguity: null\n",
                encoding="utf-8",
            )
            selection = load_experiment_selection(source)

        self.assertEqual(selection.center2d_methods, ())
        self.assertEqual(
            selection.center3d_methods,
            ("CGA", "CGA-RANSAC", "PCL SACMODEL"),
        )
        self.assertEqual(selection.ambiguity_methods, ())
        catalog = MethodCatalog.from_directory(
            REPOSITORY_ROOT / "configs" / "methods"
        )
        methods = _instantiate_methods(catalog, selection)
        self.assertEqual(methods["2d"], ())
        self.assertEqual(
            tuple(method.name for method in methods["3d"]),
            ("CGA", "CGA-RANSAC", "PCL SACMODEL"),
        )
        self.assertEqual(methods["ambiguity"], ())

    def test_synthetic_paper_profile_matches_released_protocol(self):
        directory = REPOSITORY_ROOT / "experiments" / "synthetic_3d_accuracy"
        protocol = load_protocol(directory)
        profile = load_profile(directory, "paper")

        self.assertEqual(profile["monte_carlo_trials"], 1000)
        self.assertEqual(profile["outlier_trials"], 100)
        self.assertEqual(profile["outlier_ratios"], [0.1, 0.2, 0.3, 0.4, 0.5])
        scenarios = {item["name"]: item for item in protocol["monte_carlo"]["scenarios"]}
        self.assertEqual(scenarios["limited_arc"]["arc_degrees"], 70.0)
        self.assertEqual(scenarios["sparse_points"]["point_count"], 12)
        self.assertEqual(scenarios["symmetric_distribution"]["point_count"], 20)
        self.assertEqual(
            protocol["paper_outputs"]["outlier"]["CGA"], "CGA-RANSAC"
        )

    def test_synthetic_generators_are_deterministic_and_use_integer_outliers(self):
        directory = REPOSITORY_ROOT / "experiments" / "synthetic_3d_accuracy"
        protocol = load_protocol(directory)
        scenario = protocol["monte_carlo"]["scenarios"][0]
        first = generate_monte_carlo_sample(make_generator(42), scenario)
        second = generate_monte_carlo_sample(make_generator(42), scenario)
        np.testing.assert_array_equal(first.points, second.points)

        contaminated = add_reference_outliers(first, 0.3, make_generator(43), 10, 20)
        outliers = contaminated.points[len(first.points) :]
        self.assertEqual(len(outliers), 30)
        self.assertTrue(np.all((outliers >= 10.0) & (outliers <= 20.0)))
        np.testing.assert_array_equal(outliers, np.floor(outliers))

    def test_outer_config_rejects_duplicate_method_names(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "experiment.yaml"
            source.write_text(
                "schema_version: 1\n"
                "experiment: synthetic_3d_accuracy\n"
                "datasets: [synthetic]\n"
                "methods:\n"
                "  2d: null\n"
                "  3d: [CGA, CGA]\n"
                "  ambiguity: null\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ExperimentConfigurationError, "must be unique"):
                load_experiment_selection(source)

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
