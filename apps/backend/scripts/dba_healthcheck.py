#!/usr/bin/env python3
"""DBA Diagnostic and Relational Integrity Healthcheck Tool.

Executes database latency checks, table volume telemetry, index responsiveness,
and referential integrity verification against the Convex persistence layer.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

from convex import ConvexClient


def run_healthcheck(convex_url: str, scan_limit: int = 100) -> dict[str, Any]:
    start_time = time.perf_counter()
    client = ConvexClient(convex_url)

    # 1. Connection & Ping Latency Benchmark
    t0 = time.perf_counter()
    retention_overview = client.query("retention:getRetentionOverview", {})
    t1 = time.perf_counter()
    ping_latency_ms = round((t1 - t0) * 1000, 2)

    # 2. Table Volume Telemetry
    t2 = time.perf_counter()
    table_metrics = client.query("diagnostics:getTableMetrics", {})
    t3 = time.perf_counter()
    metrics_latency_ms = round((t3 - t2) * 1000, 2)

    # 3. Referential Integrity Audit
    t4 = time.perf_counter()
    integrity_audit = client.query(
        "diagnostics:auditRelationalIntegrity",
        {"limit": scan_limit},
    )
    t5 = time.perf_counter()
    audit_latency_ms = round((t5 - t4) * 1000, 2)

    total_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

    report = {
        "status": "HEALTHY" if integrity_audit.get("healthy", False) else "DEGRADED",
        "timestamp": time.time(),
        "total_duration_ms": total_duration_ms,
        "latency": {
            "ping_ms": ping_latency_ms,
            "metrics_ms": metrics_latency_ms,
            "integrity_audit_ms": audit_latency_ms,
        },
        "table_metrics": table_metrics.get("tables", {}) if table_metrics else {},
        "retention_telemetry": retention_overview or {},
        "integrity_audit": {
            "scanned_count": integrity_audit.get("scannedCount", 0),
            "anomalies_count": integrity_audit.get("anomaliesCount", 0),
            "anomalies": integrity_audit.get("anomalies", []),
        },
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="DBA Database Healthcheck & Integrity Auditor")
    parser.add_argument(
        "--url",
        default=os.environ.get("CONVEX_URL"),
        help="Convex deployment URL (default: CONVEX_URL env var)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Scan limit per collection for integrity audit (default: 100)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON diagnostic report",
    )
    args = parser.parse_args()

    if not args.url:
        print(
            "ERROR: CONVEX_URL must be provided via environment variable or --url argument.",
            file=sys.stderr,
        )
        sys.exit(2)

    report = run_healthcheck(convex_url=args.url, scan_limit=args.limit)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=" * 60)
        print(" DBA DATABASE HEALTHCHECK REPORT ")
        print("=" * 60)
        print(f"Overall Status   : {report['status']}")
        print(f"Total Latency    : {report['total_duration_ms']} ms")
        print(f"Ping Latency     : {report['latency']['ping_ms']} ms")
        print(f"Audit Latency    : {report['latency']['integrity_audit_ms']} ms")
        print("-" * 60)
        print("TABLE VOLUME TELEMETRY:")
        for table, count in report["table_metrics"].items():
            print(f"  - {table:<20}: {count} records (sampled/max)")
        print("-" * 60)
        print("RETENTION METRICS:")
        for k, v in report["retention_telemetry"].items():
            print(f"  - {k:<30}: {v}")
        print("-" * 60)
        print(
            f"REFERENTIAL INTEGRITY: {report['integrity_audit']['anomalies_count']} anomalies in "
            f"{report['integrity_audit']['scanned_count']} records scanned."
        )
        if report["integrity_audit"]["anomalies"]:
            for anomaly in report["integrity_audit"]["anomalies"]:
                print(f"  [ALERT] {anomaly['table']} ({anomaly['id']}): {anomaly['reason']}")
        print("=" * 60)

    if report["status"] != "HEALTHY":
        sys.exit(1)


if __name__ == "__main__":
    main()
