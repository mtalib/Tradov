"""Regression for D31 _paper_fail_closed_selector_reason overly broad guard.

BLOCKER: The guard used ``"fallback" in normalized_reason`` which blocked D30's
legitimate typed-regime fallback paths such as
``"Range/calm fallback regime — Iron Condor"`` even though the regime IS
classified.  Fixed to only block truly untyped fallbacks:
``"fallback_lean_mapping"`` and ``"fallback neutral posture"``.
"""
from __future__ import annotations

import importlib


def _make_orchestrator():
    mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )

    class _StubEM:
        def subscribe(self, *a, **k):
            return None
        def emit(self, *a, **k):
            return None
        def publish(self, *a, **k):
            return None
        def unsubscribe(self, *a, **k):
            return None

    orch = mod.StrategyOrchestrator.__new__(mod.StrategyOrchestrator)
    orch.event_manager = _StubEM()
    orch.logger = __import__("logging").getLogger("test_d31_guard")
    # Force paper mode so the guard is exercised
    import os
    os.environ.setdefault("TRADING_MODE", "paper")
    return orch


class TestPaperFailClosedSelectorReason:
    """_paper_fail_closed_selector_reason must distinguish typed from untyped fallbacks."""

    # ------------------------------------------------------------------ setup
    def setup_method(self):
        self.orch = _make_orchestrator()
        # Ensure live-mode check returns False (paper mode)
        self.orch._audit_run_mode = "paper"

    def _call(self, strategy_name, selector_reason):
        return self.orch._paper_fail_closed_selector_reason(strategy_name, selector_reason)

    # ------------------------------------------------------------------ non-IronCondor pass-through
    def test_non_iron_condor_always_passes(self):
        assert self._call("CreditSpread", "fallback_lean_mapping") is None
        assert self._call("Straddle", "fallback neutral posture — Iron Condor") is None

    # ------------------------------------------------------------------ live mode pass-through
    def test_live_mode_never_blocks(self, monkeypatch):
        monkeypatch.setattr(self.orch, "_is_live_mode", lambda: True)
        assert self._call("IronCondor", "fallback_lean_mapping") is None
        assert self._call("IronCondor", "fallback neutral posture — Iron Condor") is None

    # ------------------------------------------------------------------ MUST BLOCK (truly untyped)
    def test_blocks_plain_fallback_lean_mapping(self):
        result = self._call("IronCondor", "fallback_lean_mapping")
        assert result is not None, "Must block untyped fallback_lean_mapping"
        assert "fallback_lean_mapping" in result

    def test_blocks_fallback_neutral_posture(self):
        """D30 untyped else-branch reason must be blocked."""
        result = self._call("IronCondor", "Fallback neutral posture — Iron Condor")
        assert result is not None, "Must block untyped 'Fallback neutral posture' reason"

    def test_blocks_fallback_neutral_posture_lowercase(self):
        result = self._call("IronCondor", "fallback neutral posture — iron condor")
        assert result is not None

    # ------------------------------------------------------------------ MUST ALLOW (typed regime fallbacks)
    def test_allows_range_calm_fallback_regime(self):
        """D30 fallback path when L09 unavailable — still regime-typed, must be allowed."""
        result = self._call("IronCondor", "Range/calm fallback regime — Iron Condor")
        assert result is None, (
            "Range/calm fallback regime is a typed D30 selection and must NOT be blocked"
        )

    def test_allows_range_calm_fallback_pivot(self):
        result = self._call(
            "IronCondor",
            "Range/calm fallback regime — Pivot Mean Reversion (pivot signal firing)",
        )
        assert result is None

    def test_allows_bear_fallback_regime(self):
        result = self._call("IronCondor", "Bear fallback regime — Bear Call Spread")
        assert result is None

    def test_allows_high_vol_fallback_regime(self):
        result = self._call("IronCondor", "High-vol fallback regime — Iron Butterfly")
        assert result is None

    def test_allows_range_calm_primary_path(self):
        """D30 primary path (L09 confident SIDEWAYS_RANGE) must always be allowed."""
        result = self._call("IronCondor", "Range/calm — Iron Condor")
        assert result is None

    def test_allows_empty_reason(self):
        """Empty reason is not 'fallback_lean_mapping' — must not be blocked."""
        result = self._call("IronCondor", "")
        assert result is None
