#!/usr/bin/env python3
"""Operator live-readiness checks for Tradov."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass


SAFETY_TESTS = [
    "Tradov/TradovT_Testing/TradovT188_B02_OrderManagerSubmissionHardening.py",
    "Tradov/TradovT_Testing/TradovT189_PairOrderExecutorSafety.py",
    "Tradov/TradovT_Testing/TradovT190_S07_MarketConditionAvailability.py",
    "Tradov/TradovT_Testing/TradovT191_RuntimeContextIsolation.py",
    "Tradov/TradovT_Testing/TradovT196_LiveOnlyPolicyRegression.py",
]


@dataclass(frozen=True)
class CheckResult:
    name: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _run(name: str, args: list[str]) -> CheckResult:
    print(f"[readiness] running {name}: {' '.join(args)}", flush=True)
    completed = subprocess.run(args, check=False)
    return CheckResult(name=name, returncode=completed.returncode)


def run_readiness_checks(*, include_full_tests: bool = False) -> list[CheckResult]:
    """Run local pre-live checks and return individual results."""
    python = sys.executable
    checks = [
        _run("compile", [python, "-m", "compileall", "-q", "Tradov"]),
        _run("safety-tests", [python, "-m", "pytest", "-q", "-o", "addopts=", *SAFETY_TESTS]),
        _run(
            "config-validation",
            [
                python,
                "-c",
                "from config.config import validate_startup_config; validate_startup_config(); print('config ok')",
            ],
        ),
    ]
    if include_full_tests:
        checks.append(
            _run(
                "full-tests",
                [python, "-m", "pytest", "-q", "-o", "addopts=", "Tradov/TradovT_Testing"],
            )
        )
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Tradov live-readiness checks.")
    parser.add_argument(
        "--full-tests",
        action="store_true",
        help="Also run the full local TradovT test suite without coverage.",
    )
    args = parser.parse_args(argv)

    results = run_readiness_checks(include_full_tests=args.full_tests)
    failed = [result for result in results if not result.ok]
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"[readiness] {status} {result.name} rc={result.returncode}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
