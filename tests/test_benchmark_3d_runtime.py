# SPDX-License-Identifier: Apache-2.0

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from circular_center.experiments.runner import run_experiment  # noqa: E402
from experiments.benchmark_3d_runtime.protocol import (  # noqa: E402
    load_profile,
    load_protocol,
)
from experiments.benchmark_3d_runtime.reporting import summarize_workers  # noqa: E402


class Benchmark3DRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = REPOSITORY_ROOT / "experiments" / "benchmark_3d_runtime"
        cls.protocol = load_protocol(cls.directory)

    def test_paper_profile_matches_table_iii(self):
        profile = load_profile(self.directory, "paper")
        self.assertEqual(profile["timed_repetitions"], 1000)
        self.assertEqual(profile["process_repetitions"], 5)
        self.assertEqual(self.protocol["input"]["point_count"], 64)
        self.assertEqual(
            self.protocol["method_order"], ["CGA", "CGA-RANSAC", "PCL SACMODEL"]
        )

    def test_worker_aggregation_uses_latency_percentiles_and_median_rss(self):
        workers = [
            {
                "method": "CGA",
                "latencies_ms": [1.0, 2.0],
                "peak_rss_mib": 30.0,
            },
            {
                "method": "CGA",
                "latencies_ms": [3.0, 4.0],
                "peak_rss_mib": 40.0,
            },
        ]
        row = summarize_workers(workers)[0]
        self.assertEqual(row["timed_repetitions"], 4)
        self.assertAlmostEqual(row["p50_ms"], 2.5)
        self.assertAlmostEqual(row["median_peak_rss_mib"], 35.0)

    @unittest.skipUnless(
        os.environ.get("CIRCULAR_CENTER_PCL_LIBRARY"),
        "PCL integration library is not configured",
    )
    def test_ci_profile_writes_runtime_table(self):
        config = (
            REPOSITORY_ROOT
            / "configs"
            / "experiments"
            / "benchmark_3d_runtime"
            / "ci.yaml"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory)
            result = run_experiment(config, output_directory=output)
            profile = result["profiles"][0]
            self.assertEqual(profile["timed_repetitions_per_method"], 9)
            self.assertEqual(len(profile["runtime_summary"]), 3)
            self.assertTrue((output / "ci" / "runtime_records.csv").is_file())
            self.assertTrue((output / "ci" / "runtime_summary.csv").is_file())
            self.assertTrue((output / "ci" / "runtime_table.tex").is_file())
            self.assertTrue((output / "ci" / "environment.json").is_file())
            self.assertTrue((output / "summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
