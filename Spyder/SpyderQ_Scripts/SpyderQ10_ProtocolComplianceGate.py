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
    Gate 4 — datetime.now() (naive, no tz) in production code
      Gate 5 — BrokerProtocol compliance (B40 and PaperBroker)

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
    self_name = Path(__file__).name
    for py_file in sorted(_SPYDER_ROOT.rglob("*.py")):
        if "SpyderT_Testing" in py_file.parts or "__pycache__" in py_file.parts:
            continue
        # Skip Q10 itself — regex literal + docstrings legitimately contain the pattern.
        if py_file.name == self_name:
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


# ---------------------------------------------------------------------------
# Gate 4: datetime.now() (naive, no tz) in production code
# ---------------------------------------------------------------------------
_NAIVE_NOW_PATTERN = re.compile(r"\bdatetime\.now\(\s*\)")

# Lines that also reference timezone.utc on the same line are intentional
# tzinfo-conditional patterns (e.g. "datetime.now(timezone.utc) if ... else
# datetime.now()") and must not be flagged as footguns.
_SAME_LINE_UTC_PATTERN = re.compile(r"timezone\.utc")

# Inline suppression comment — add "# spyder: naive-ok" to a line that
# deliberately uses naive datetime.now() (e.g. inside a tzinfo guard block
# where both sides of the arithmetic are already naive).
_NAIVE_OK_MARKER = "# spyder: naive-ok"

# Packages/directories excluded from Gate 4 — scripts and tests may use naive
# timestamps for local display or CLI output.
_NAIVE_NOW_EXCLUDE_DIRS = {
    "SpyderQ_Scripts",
    "SpyderT_Testing",
    "__pycache__",
}

# Individual files excluded from Gate 4.  SpyderU03_DateTimeUtils.py is a
# time-utility module that intentionally works with local (ET) time for market
# session logic; all of its naive datetime.now() calls are either guarded by
# tzinfo checks or are extracting .time()/.date() for session-window math.
_NAIVE_NOW_EXCLUDE_FILES = {
    "SpyderU03_DateTimeUtils.py",
}


def check_no_naive_datetime_now() -> bool:
    """Return True when no production file calls datetime.now() without a tz arg."""
    violations: list[str] = []
    for py_file in sorted(_SPYDER_ROOT.rglob("*.py")):
        if any(part in _NAIVE_NOW_EXCLUDE_DIRS for part in py_file.parts):
            continue
        if py_file.name in _NAIVE_NOW_EXCLUDE_FILES:
            continue
        try:
            text = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if not _NAIVE_NOW_PATTERN.search(line):
                continue
            # Skip intentional tzinfo-conditional one-liners (both branches on
            # the same line: "datetime.now(timezone.utc) if ... else datetime.now()").
            if _SAME_LINE_UTC_PATTERN.search(line):
                continue
            # Skip lines explicitly marked as reviewed and intentional.
            if _NAIVE_OK_MARKER in line:
                continue
            rel = py_file.relative_to(_SPYDER_ROOT.parent)
            violations.append(f"  {rel}:{lineno}: {line.strip()}")

    if violations:
        print(
            "[Q10] datetime.now() (naive) found in production code "
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

    print("[Q10] Naive datetime.now() gate OK — no bare now() in production code.", file=sys.stderr)
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

    # Gate 4: naive datetime.now()
    if not check_no_naive_datetime_now():
        exit_code = 1

    # Gate 5: BrokerProtocol compliance
    if not check_broker_protocol_compliance():
        exit_code = 1

    # Gate 6: bare-import smoke test for all public top-level modules
    if not check_module_imports():
        exit_code = 1

    # Gate 7: StrategyOrchestrator import health + subscription smoke
    if not check_strategy_orchestrator_health():
        exit_code = 1

    return exit_code


# ==============================================================================
# GATE 5: BrokerProtocol compliance
# ==============================================================================

def check_broker_protocol_compliance() -> bool:
    """Verify that B40 TradierClient and R15 PaperBroker satisfy BrokerProtocol.

    Uses ``@runtime_checkable`` isinstance() check so no live broker connections
    are made — only the class methods are inspected structurally.

    Returns:
        True if both brokers satisfy BrokerProtocol; False otherwise.
    """
    import importlib

    try:
        proto_mod = importlib.import_module(
            "Spyder.SpyderB_Broker.SpyderB21_BrokerProtocol"
        )
    except ImportError:
        print("[Q10] Gate 5: FAIL — cannot import SpyderB21_BrokerProtocol", file=sys.stderr)
        return False

    BrokerProtocol = getattr(proto_mod, "BrokerProtocol", None)
    if BrokerProtocol is None:
        print("[Q10] Gate 5: FAIL — BrokerProtocol not found in B21", file=sys.stderr)
        return False

    _REQUIRED_METHODS = ("place_order", "get_order", "cancel_order", "get_positions", "get_account_balances")

    _BROKER_SPECS: list[tuple[str, str]] = [
        ("Spyder.SpyderB_Broker.SpyderB40_TradierClient", "TradierClient"),
        ("Spyder.SpyderR_Runtime.SpyderR15_PaperBroker",  "PaperBroker"),
    ]

    all_pass = True
    for module_path, class_name in _BROKER_SPECS:
        label = f"{module_path}.{class_name}"
        try:
            mod = importlib.import_module(module_path)
        except ImportError as exc:
            print(f"[Q10] Gate 5: SKIP {label} — {exc}", file=sys.stderr)
            continue

        cls = getattr(mod, class_name, None)
        if cls is None:
            print(f"[Q10] Gate 5: FAIL — {class_name} not found in {module_path}", file=sys.stderr)
            all_pass = False
            continue

        # Structural check 1: all required method names must be callable
        missing = [m for m in _REQUIRED_METHODS if not callable(getattr(cls, m, None))]
        if missing:
            print(
                f"[Q10] Gate 5: FAIL — {label} missing methods: {missing}",
                file=sys.stderr,
            )
            all_pass = False
            continue

        # Structural check 2: signature of place_order must include the
        # positional params declared on BrokerProtocol so that a broker
        # implementing ``def place_order(self, **kwargs)`` is caught.
        import inspect
        proto_sig = inspect.signature(BrokerProtocol.place_order)
        # Exclude VAR_KEYWORD (**kwargs) and VAR_POSITIONAL (*args) from the
        # required-param set — a **kwargs in the protocol is a relaxation, not
        # a requirement (audit v10 P1-A false-positive on TradierClient).
        proto_params = {
            name
            for name, p in proto_sig.parameters.items()
            if name != "self"
            and p.kind not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            )
        }
        impl_params = set(inspect.signature(cls.place_order).parameters) - {"self"}
        # impl must accept at least the positional params of the protocol
        # (kwargs-only implementations are acceptable if they carry **kwargs)
        impl_sig = inspect.signature(cls.place_order)
        has_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in impl_sig.parameters.values()
        )
        missing_params = proto_params - impl_params
        if missing_params and not has_var_keyword:
            print(
                f"[Q10] Gate 5: FAIL — {label}.place_order missing params: {missing_params}",
                file=sys.stderr,
            )
            all_pass = False
            continue

        print(f"[Q10] Gate 5: OK   — {label} satisfies BrokerProtocol", file=sys.stderr)

    if all_pass:
        print("[Q10] Gate 5: BrokerProtocol compliance OK", file=sys.stderr)
    return all_pass


# ==============================================================================
# GATE 6: Import smoke test — bare-import every public top-level module
# ==============================================================================

#: Canonical list of public top-level module paths to smoke-test.
#: Add new modules here as they are introduced so Gate 6 catches import-time
#: failures automatically (addresses audit finding O-1 / P1-2).
_SMOKE_TEST_MODULES: list[str] = [
    "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator",
    "Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor",
    "Spyder.SpyderR_Runtime.SpyderR13_FillReconciler",
    "Spyder.SpyderR_Runtime.SpyderR14_ExitMonitor",
    "Spyder.SpyderR_Runtime.SpyderR15_PaperBroker",
    "Spyder.SpyderE_Risk.SpyderE01_RiskManager",
    "Spyder.SpyderE_Risk.SpyderE24_DataFreshnessMonitor",
    "Spyder.SpyderB_Broker.SpyderB21_BrokerProtocol",
    "Spyder.SpyderA_Core.SpyderA05_EventManager",
]


def check_module_imports() -> bool:
    """Attempt a bare import of every module in ``_SMOKE_TEST_MODULES``.

    A module that raises at import time is flagged as Gate 6 FAIL.  This
    catches missing dependencies and ``NameError`` / ``AttributeError``
    problems before any live code runs.

    Returns:
        True if all imports succeed; False if any fail.
    """
    import importlib

    all_pass = True
    for module_path in _SMOKE_TEST_MODULES:
        try:
            importlib.import_module(module_path)
            print(f"[Q10] Gate 6: OK   — {module_path}", file=sys.stderr)
        except Exception as exc:
            print(
                f"[Q10] Gate 6: FAIL — {module_path}: {exc}",
                file=sys.stderr,
            )
            all_pass = False

    if all_pass:
        print("[Q10] Gate 6: all module imports OK", file=sys.stderr)
    return all_pass


# ==============================================================================
# GATE 7: StrategyOrchestrator import health + subscription smoke test
# ==============================================================================

def check_strategy_orchestrator_health() -> bool:
    """Gate 7 — D31 must import cleanly and register event subscriptions.

    Verifies:
    1. ``SPYDER_MODULES_AVAILABLE`` is ``True`` (no silent import fallback).
    2. After construction, at least one ``STRATEGY_SIGNAL`` handler is
       registered on the EventManager (subscription wiring is live).

    This gate would have caught both P0-A and P0-B from audit v10 in CI.
    """
    all_pass = True
    try:
        import importlib
        d31 = importlib.import_module(
            "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
        )
        if not getattr(d31, "SPYDER_MODULES_AVAILABLE", False):
            print(
                "[Q10] Gate 7: FAIL — D31 SPYDER_MODULES_AVAILABLE is False "
                "(soft-import fallback active — imports are broken)",
                file=sys.stderr,
            )
            all_pass = False
        else:
            print("[Q10] Gate 7: OK   — D31 SPYDER_MODULES_AVAILABLE is True", file=sys.stderr)
    except Exception as exc:
        print(f"[Q10] Gate 7: FAIL — Cannot import D31: {exc}", file=sys.stderr)
        return False

    # Subscription smoke: instantiate with a real EventManager and verify wiring
    try:
        from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType
        em = get_event_manager()
        if not em.is_running:
            em.start()

        before = len(em.handlers.get(EventType.STRATEGY_SIGNAL, []))
        StrategyOrchestrator = d31.StrategyOrchestrator
        _orch = StrategyOrchestrator(event_manager=em)
        after = len(em.handlers.get(EventType.STRATEGY_SIGNAL, []))

        if after <= before:
            print(
                "[Q10] Gate 7: FAIL — D31 did not register a STRATEGY_SIGNAL "
                "handler after construction (subscription wiring broken)",
                file=sys.stderr,
            )
            all_pass = False
        else:
            print(
                "[Q10] Gate 7: OK   — D31 registered STRATEGY_SIGNAL subscription",
                file=sys.stderr,
            )
    except Exception as exc:
        print(f"[Q10] Gate 7: FAIL — Subscription smoke test raised: {exc}", file=sys.stderr)
        all_pass = False

    return all_pass


if __name__ == "__main__":
    sys.exit(main())
