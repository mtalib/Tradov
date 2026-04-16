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


# ---------------------------------------------------------------------------
# Datetime hygiene gate
# ---------------------------------------------------------------------------
_UTCNOW_PATTERN = re.compile(r"\bdatetime\.utcnow\b")
_SPYDER_ROOT = Path(__file__).resolve().parent.parent  # Spyder/ package root


def check_no_datetime_utcnow() -> bool:
    """Return True when no production file calls ``datetime.utcnow``.

    Test files (SpyderT_Testing/) are intentionally excluded; the rule is
    production-only.  Violations are printed to stderr.
    """
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
        return 1

    print("[Q10] Protocol compliance OK", file=sys.stderr)

    # Datetime hygiene gate — run independently so both reports are visible.
    datetime_ok = check_no_datetime_utcnow()
    if not datetime_ok:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
