#!/usr/bin/env python3
"""Run repeatable Locust scenarios against the local benchmark application."""

from __future__ import annotations

import argparse
import csv
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class LocustBenchmark:
    """Coordinate benchmark scenarios and summarize Locust CSV output."""

    tags = (
        "baseline",
        "logs",
        "aiologger",
        "aiologger-await",
        "custom-async",
        "custom-async-await",
    )

    def __init__(
        self,
        *,
        locustfile: str = "locustfile.py",
        host: str = "http://127.0.0.1:8000",
        users: int = 50,
        spawn_rate: int = 10,
        run_time: str = "5m",
        log_volumes: list[int] | None = None,
        pause_seconds: float = 5.0,
    ) -> None:
        self.locustfile = locustfile
        self.host = host
        self.users = users
        self.spawn_rate = spawn_rate
        self.run_time = run_time
        self.log_volumes = log_volumes or [100, 400]
        self.pause_seconds = pause_seconds

    def run_locust_test(
        self, *, tag: str, n_logs: int, csv_prefix: str
    ) -> tuple[bool, str]:
        command = [
            "locust",
            "-f",
            self.locustfile,
            "--headless",
            "-u",
            str(self.users),
            "-r",
            str(self.spawn_rate),
            "-t",
            self.run_time,
            "--tag",
            tag,
            "--host",
            self.host,
            "--csv",
            csv_prefix,
            "--only-summary",
        ]
        environment = os.environ.copy()
        environment["N_LOGS"] = str(n_logs)

        print(f"\n{'=' * 80}")
        print(f"Running {tag} with {n_logs} logs per request")
        print(f"Command: {' '.join(command)}")
        print("=" * 80)

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                check=False,
                env=environment,
                text=True,
                timeout=400,
            )
        except subprocess.TimeoutExpired:
            return False, "Locust process exceeded the 400-second safety timeout"

        if result.returncode != 0:
            return False, result.stderr.strip()
        return True, ""

    @staticmethod
    def parse_stats_csv(csv_file: str) -> dict[str, float | int]:
        path = Path(csv_file)
        if not path.exists():
            return {}

        try:
            with path.open(encoding="utf-8", newline="") as file_handle:
                rows = list(csv.DictReader(file_handle))
        except (OSError, csv.Error, UnicodeError):
            return {}

        aggregated = next(
            (
                row
                for row in rows
                if row.get("Name") == "Aggregated"
                or row.get("Type") == "Aggregated"
            ),
            rows[-1] if rows else None,
        )
        if not aggregated:
            return {}

        try:
            return {
                "min": float(aggregated.get("Min Response Time", 0)),
                "median": float(aggregated.get("Median Response Time", 0)),
                "avg": float(aggregated.get("Average Response Time", 0)),
                "max": float(aggregated.get("Max Response Time", 0)),
                "rps": float(aggregated.get("Requests/s", 0)),
                "requests": int(aggregated.get("Request Count", 0)),
                "failures": int(aggregated.get("Failure Count", 0)),
            }
        except (TypeError, ValueError):
            return {}

    @staticmethod
    def format_stats(stats: dict[str, float | int]) -> str:
        if not stats:
            return "N/A"
        return "-".join(
            str(int(stats[key])) for key in ("min", "median", "avg", "max")
        )

    def run_all_tests(self) -> dict[int, dict[str, dict[str, Any] | None]]:
        results: dict[int, dict[str, dict[str, Any] | None]] = {}
        Path("results").mkdir(exist_ok=True)

        for n_logs in self.log_volumes:
            print(f"\n\n{'#' * 80}")
            print(f"# {n_logs} logs per request")
            print(f"{'#' * 80}")
            results[n_logs] = {}

            for tag in self.tags:
                csv_prefix = f"results/{n_logs}logs_{tag}"
                success, error = self.run_locust_test(
                    tag=tag, n_logs=n_logs, csv_prefix=csv_prefix
                )
                if not success:
                    print(f"FAILED: {error}")
                    results[n_logs][tag] = None
                    continue

                stats = self.parse_stats_csv(f"{csv_prefix}_stats.csv")
                results[n_logs][tag] = stats or None
                print(
                    "Completed: "
                    f"{self.format_stats(stats)} min/median/avg/max ms"
                )
                if self.pause_seconds:
                    time.sleep(self.pause_seconds)

        return results

    def print_summary(
        self, results: dict[int, dict[str, dict[str, Any] | None]]
    ) -> None:
        print(f"\n\n{'=' * 80}")
        print("BENCHMARK RESULTS")
        print("=" * 80)

        for n_logs, tag_results in sorted(results.items()):
            print(f"\n{n_logs} logs/request — min/median/avg/max ms")
            for tag in self.tags:
                stats = tag_results.get(tag)
                if not stats:
                    print(f"FAILED {tag:20s}: N/A")
                    continue
                requests = int(stats.get("requests", 0))
                failures = int(stats.get("failures", 0))
                if requests == 0:
                    status = "NO DATA"
                elif failures:
                    status = f"{failures} failures"
                else:
                    status = "OK"
                print(
                    f"{status:12s} {float(stats.get('rps', 0)):6.1f} RPS "
                    f"{tag:20s}: {self.format_stats(stats)}"
                )

        print("\nTreat results as environment-specific measurements, not a")
        print("general production recommendation. Compare repeated runs on")
        print("the same host and inspect failures and resource saturation.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the FastAPI logging microbenchmark with Locust."
    )
    parser.add_argument("--host", default="http://127.0.0.1:8000")
    parser.add_argument("--users", type=int, default=50)
    parser.add_argument("--spawn-rate", type=int, default=10)
    parser.add_argument("--run-time", default="5m")
    parser.add_argument("--log-volumes", type=int, nargs="+", default=[100, 400])
    parser.add_argument("--pause-seconds", type=float, default=5.0)
    return parser.parse_args()


def ensure_server_is_running(host: str) -> None:
    parsed = urlparse(host)
    if not parsed.hostname:
        raise ValueError(f"Host must include a hostname: {host}")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        if connection.connect_ex((parsed.hostname, port)) != 0:
            raise ConnectionError(
                f"FastAPI server is not reachable at {parsed.hostname}:{port}"
            )


def main() -> None:
    args = parse_args()
    try:
        ensure_server_is_running(args.host)
    except (ConnectionError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        print("Start it with: uv run uvicorn main:app", file=sys.stderr)
        raise SystemExit(1) from error

    benchmark = LocustBenchmark(
        host=args.host,
        users=args.users,
        spawn_rate=args.spawn_rate,
        run_time=args.run_time,
        log_volumes=args.log_volumes,
        pause_seconds=args.pause_seconds,
    )
    results = benchmark.run_all_tests()
    benchmark.print_summary(results)
    print("\nResults saved in ./results")


if __name__ == "__main__":
    main()
