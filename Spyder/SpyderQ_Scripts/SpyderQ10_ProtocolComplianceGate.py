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

import sys
import unittest


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
    return 0


if __name__ == "__main__":
    sys.exit(main())
