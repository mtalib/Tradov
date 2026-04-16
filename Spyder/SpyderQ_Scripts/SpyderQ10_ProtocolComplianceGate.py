#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderQ_Scripts
Module: SpyderQ10_ProtocolComplianceGate.py
Purpose: CI gate that runs the T129 protocol-compliance suite and exits nonzero on failure
Author: SPYDER Trading System
Year Created: 2026
Last Updated: 2026-04-14

Module Description:
    Run as a pre-merge / CI step. Invokes the T129 protocol-compliance
    unittest suite and exits nonzero on any failure. Designed to catch the
    exact v5/v3 audit class of regressions:

      - Protocol renames that break implementors silently
      - Stub methods that satisfy structural checks but return useless data
      - Runtime-invalid enum member references (CRIT-01-style)

    Usage:
        python -m Spyder.SpyderQ_Scripts.SpyderQ10_ProtocolComplianceGate

    Exit codes:
        0 — all protocol tests pass
        1 — at least one failure
        2 — harness/setup error (tests couldn't run)
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

# Production packages whose source must not contain ungated np.random calls.
_RNG_SCAN_PACKAGES = [
    "SpyderE_Risk",
    "SpyderP_PortfolioMgmt",
]

# np.random calls inside these function names are intentional (algorithmic or RL).
_ALLOWED_FUNCTION_PREFIXES = (
    # Test / demo helpers
    "create_sample", "generate_sample", "test_", "demo_",
    # Monte Carlo and scenario generation — stochastic by design
    "_generate_random_scenarios", "_monte_carlo", "run_monte_carlo", "_simulate_var",
    "_calculate_monte_carlo_var",
    # Gym reinforcement-learning environments — RNG is inherent in reset/step
    "reset", "step",
    # Black-Litterman scenario perturbation — legitimate quant technique
    "_perturb_",
    # Statistical correlation sampling — efficient approximation, not production decision
    "_calculate_ultrametric",
)

_RNG_PATTERN = re.compile(r"np\.random\.")
_MAIN_GUARD = re.compile(r"^\s*if\s+__name__\s*==\s*['\"]__main__['\"]")
_FUNCDEF_PATTERN = re.compile(r"^\s*def\s+(\w+)")


def _file_has_ungated_rng(path: Path) -> list[tuple[int, str]]:
    """Return (lineno, line) pairs where np.random is used outside a safe context.

    'Safe' means:
      • inside an ``if __name__ == "__main__":`` block, OR
      • inside a function whose name starts with a known test/demo prefix.
    """
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
    """Scan production E/P packages for unguarded np.random usage.

    Returns True (pass) when no violations are found, False otherwise.
    """
    spyder_root = Path(__file__).resolve().parents[1]  # …/Spyder/
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



def main() -> int:
    exit_code = 0

    # --- Gate 1: np.random in production code --------------------------------
    if not check_no_rng_in_production():
        exit_code = 1

    # --- Gate 2: Protocol compliance (T129) ----------------------------------
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

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
