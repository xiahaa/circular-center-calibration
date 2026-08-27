"""One isolated runtime/RSS measurement process."""

from __future__ import annotations

import argparse
import json
import resource
import sys
from pathlib import Path
from time import perf_counter_ns
from typing import Optional, Sequence

import numpy as np

from circular_center.registry import MethodCatalog

from .generators import generate_benchmark_points


def _peak_rss_mib() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # Linux reports KiB; macOS reports bytes.
    return value / (1024.0 * 1024.0) if sys.platform == "darwin" else value / 1024.0


def run_worker(arguments: argparse.Namespace) -> dict:
    catalog = MethodCatalog.from_directory(Path(arguments.method_config_root))
    overrides = json.loads(arguments.overrides_json)
    method = catalog.create(arguments.method, "center3d", overrides)
    points = generate_benchmark_points(
        arguments.seed,
        point_count=arguments.point_count,
        radius_m=arguments.radius_m,
        noise_sigma_m=arguments.noise_sigma_m,
    )
    for _ in range(arguments.warmup_repetitions):
        method.fit(points)
    latencies_ms = []
    for _ in range(arguments.timed_repetitions):
        started = perf_counter_ns()
        result = method.fit(points)
        elapsed = perf_counter_ns() - started
        if not np.isfinite(result.center).all():
            raise RuntimeError("{} returned a non-finite center".format(arguments.method))
        latencies_ms.append(float(elapsed) / 1_000_000.0)
    return {
        "method": arguments.method,
        "process_index": arguments.process_index,
        "timed_repetitions": arguments.timed_repetitions,
        "warmup_repetitions": arguments.warmup_repetitions,
        "latencies_ms": latencies_ms,
        "peak_rss_mib": _peak_rss_mib(),
    }


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", required=True)
    parser.add_argument("--method-config-root", required=True)
    parser.add_argument("--overrides-json", required=True)
    parser.add_argument("--process-index", type=int, required=True)
    parser.add_argument("--timed-repetitions", type=int, required=True)
    parser.add_argument("--warmup-repetitions", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--point-count", type=int, required=True)
    parser.add_argument("--radius-m", type=float, required=True)
    parser.add_argument("--noise-sigma-m", type=float, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    result = run_worker(build_argument_parser().parse_args(argv))
    print(json.dumps(result, allow_nan=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_argument_parser", "main", "run_worker"]
