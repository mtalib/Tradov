#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderQ_Scripts
Module: SpyderQ10_ProtocolComplianceGate.py
Purpose: CI gate — RNG hygiene, protocol compliance, datetime hygiene
Author: SPYDER Trading System
Year Created: 2026
Last Updated: 2026-04-16

Module Description:
    Run as a pre-merge / CI step. Three independent gates, all must pass:

      Gate 1 — np.random in production risk/portfolio packages
      Gate 2 — T129 protocol-compliance unittest suite
      Gate 3 — datetime.utcnow() in production code (use timezone.utc)

    Usage:
        python -m Spyder.SpyderQ_Scripts.SpyderQ10_ProtocolComplianceGate

    Exit codes:
        0 — all gates pass
        1 — at least one failure
        2 — harness/setup error (tests couldn't run)
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path


# ---------------------------------------------------------------------------
# Gate 1: np.random in production risk/portfolio packages
# ---------------------------------------------------------------------------

_RNG_SCAN_PACKAGES = [
    "SpyderE_Risk",
    "SpyderP_PortfolioMgmt",
]

_ALLOWED_FUNCTION_PREFIXES = (
    "create_sample", "generate_sample", "test_", "demo_",
    "_generate_random_scenarios", "_monte_carlo", "run_monte_carlo", "_simulate_var",
    "_calculate_monte_carlo_var",
    "reset", "step",
    "_perturb_",
    "_calculate_ultrametric",
)

_RNG_PATTERN = re.compile(r"np\.random\.")
_MAIN_GUARD = re.compile(r"^\s*if\s+__name__\s*==\s*['\"]__main__['\"]")
_FUNCDEF_PATTERN = re.compile(r"^\s*def\s+(\w+)")


def _file_has_ungated_rng(path: Path) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return hits

    in_main_block = False
    current_func: str = ""

    for lineno, raw in enumerate(lines, start=1):
        if _MAIN_GUARD.match(raw):
            in_main_block = True
        func_match = _FUNCDEF_PATTERN.match(raw)
        if func_match:
            current_func = func_match.group(1)
        if _RNG_PATTERN.search(raw):
            if in_main_block:
                continue
            if current_func and any(current_func.startswith(p) for p in _ALLOWED_FUNCTION_PREFIXES):
                continue
            hits.append((lineno, raw.rstrip()))

    return hits


def check_no_rng_in_production() -> bool:
    """Scan production E/P packages for unguarded np.random usage."""
    spyder_root = Path(__file__).resolve().parents[1]
    violations: list[str] = []

    for pkg_name in _RNG_SCAN_PACKAGES:
        pkg_dir = spyder_root / pkg_name
        if not pkg_dir.is_dir():
            continue
        for py_file in sorted(pkg_dir.glob("*.py")):
            hits = _file_has_ungated_rng(py_file)
            for lineno, line in hits:
                violations.append(f"  {py_file.relative_to(spyder_root)}:{lineno}: {line}")

    if violations:
        print(
            "[Q10] FAIL — np.random in production code:\n" + "\n".join(violations),
            file=sys.stderr,
        )
        return False

    print("[Q10] RNG gate OK — no unguarded np.random in production packages", file=sys.stderr)
    return True


# ---------------------------------------------------------------------------
# Gate 3: datetime.utcnow() in production code
# ---------------------------------------------------------------------------
_UTCNOW_PATTERN = re.compile(r"\bdatetime\.utcnow\b")
_SPYDER_ROOT = Path(__file__).resolve().parent.parent


def check_no_datetime_utcnow() -> bool:
    """Return True when no production file calls datetime.utcnow."""
    violations: list[str] = []
    for py_file in sorted(_SPYDER_ROOT.rglob("*.py")):
        if "SpyderT_Testing" in py_file.parts or "__pycache__" in py_file.parts:
            continue
        try:
            text = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if _UTCNOW_PATTERN.search(line):
                rel = py_file.relative_to(_SPYDER_ROOT.parent)
                violations.append(f"  {rel}:{lineno}: {line.strip()}")

    if violations:
        print(
            "[Q10] datetime.utcnow() found in production code "
            f"({len(violations)} occurrence(s)):",
            file=sys.stderr,
        )
        for v in violations:
            print(v, file=sys.stderr)
        print(
            "[Q10] Use datetime.now(timezone.utc) or SpyderU03.now_utc() instead.",
            file=sys.stderr,
        )
        return False

    print("[Q10] datetime hygiene OK — no utcnow() in production code.", file=sys.stderr)
    return True


def main() -> int:
    exit_code = 0

    # Gate 1: np.random
    if not check_no_rng_in_production():
        exit_code = 1

    # Gate 2: Protocol compliance (T129)
    try:
        from Spyder.SpyderT_Testing import SpyderT129_ProtocolCompliance as suite_module
    except Exception as exc:  # pragma: no cover
        print(f"[Q10] Unable to import T129 suite: {exc}", file=sys.stderr)
        return 2

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(suite_module)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if not result.wasSuccessful():
        print(
            f"[Q10] Protocol compliance FAILED "
            f"({len(result.failures)} failures, {len(result.errors)} errors)",
            file=sys.stderr,
        )
        exit_code = 1
    else:
        print("[Q10] Protocol compliance OK", file=sys.stderr)

    # Gate 3: datetime.utcnow()
    if not check_no_datetime_utcnow():
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
