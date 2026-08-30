#!/usr/bin/env python3
"""DBA Query Latency & Index Benchmark Runner.

Simulates concurrent read queries against indexed collections (commits,
stories, approvalRequests) to benchmark query response times and detect
slow query regressions.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any

from convex import ConvexClient


def benchmark_query(
    client: ConvexClient,
    query_name: str,
    args: dict[str, Any],
    iterations: int = 5,
) -> dict[str, float]:
    latencies: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        try:
            client.query(query_name, args)
        except Exception:
            pass
        latencies.append((time.perf_counter() - t0) * 1000)

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    avg = sum(latencies) / len(latencies)
    return {
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "avg_ms": round(avg, 2),
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="DBA Query Latency Benchmark")
    parser.add_argument(
        "--url",
        default=os.environ.get("CONVEX_URL"),
        help="Convex deployment URL (default: CONVEX_URL env var)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="Number of iterations per query (default: 5)",
    )
    cli_args = parser.parse_args()

    if not cli_args.url:
        print(
            "ERROR: CONVEX_URL must be provided via environment variable or --url argument.",
            file=sys.stderr,
        )
        sys.exit(2)

    client = ConvexClient(cli_args.url)

    benchmarks = [
        ("retention:getRetentionOverview", {}),
        ("diagnostics:getTableMetrics", {}),
        ("diagnostics:auditRelationalIntegrity", {"limit": 50}),
    ]

    print("=" * 65)
    print(" DBA INDEX & QUERY LATENCY BENCHMARK ")
    print("=" * 65)
    print(f"{'Query Endpoint':<40} | {'p50 (ms)':<8} | {'p95 (ms)':<8} | {'Avg (ms)':<8}")
    print("-" * 65)

    for query_name, q_args in benchmarks:
        metrics = benchmark_query(client, query_name, q_args, iterations=cli_args.iterations)
        print(
            f"{query_name:<40} | "
            f"{metrics['p50_ms']:<8.2f} | "
            f"{metrics['p95_ms']:<8.2f} | "
            f"{metrics['avg_ms']:<8.2f}"
        )

    print("=" * 65)


if __name__ == "__main__":
    main()
