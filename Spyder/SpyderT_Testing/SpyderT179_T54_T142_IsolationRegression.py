#!/usr/bin/env python3
"""Deterministic in-process isolation regression for T54/T142.

Runs representative G05 prelude tests first, then executes the historically
order-sensitive T54/T142 checks in the same Python process.
"""

from __future__ import annotations

import importlib
import unittest


def _run_selected_t54_checks() -> None:
    t54 = importlib.import_module("Spyder.SpyderT_Testing.SpyderT54_StartupConfigValidation_Test")
    cls = t54.TestG05StartupReadinessHelpers
    names = [
        "test_append_banner_unavailable_when_readiness_not_checked",
        "test_collect_state_marks_safe_fallback_in_paper_mode",
        "test_emit_logs_styles_button_for_safe_mode",
    ]
    suite = unittest.TestSuite(cls(name) for name in names)
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    assert result.wasSuccessful(), f"T54 readiness checks failed: {result.failures} {result.errors}"


def _run_selected_t142_checks() -> None:
    t142 = importlib.import_module("Spyder.SpyderT_Testing.SpyderT142_D31_StrategyRegistryWiring")
    t142.test_d31_registry_includes_first_wave_base_strategies()
    t142.test_d31_configure_regime_selects_newly_wired_strategies()
    t142.test_d31_current_regime_weights_are_registry_reachable_and_constructible()


def test_t54_t142_survive_representative_preludes_in_same_process() -> None:
    """Prove representative preludes do not poison later T54/T142 checks."""
    t151 = importlib.import_module("Spyder.SpyderT_Testing.SpyderT151_G05_EventClockHandlerIntegration")
    t153 = importlib.import_module("Spyder.SpyderT_Testing.SpyderT153_G05_GoNoGoCheck")

    # Representative prelude sequence observed in targeted troubleshooting runs.
    t151.test_g05_consumes_a04_live_payload_and_updates_labels()
    t153.test_go_no_go_returns_go_when_core_checks_pass()
    t153.test_go_no_go_returns_conditional_go_during_event_window()

    # Historically order-sensitive targets must still pass in-process.
    _run_selected_t54_checks()
    _run_selected_t142_checks()
