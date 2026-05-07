"""T193 — D31 dispatch is robust when walk_result lacks standard attributes.

Regression guard for the ``dispatch_exception`` signal-drop observed in
``logs/decisions/2026-05-02.jsonl`` and documented in v9 section 10.4.

Root cause:  ``_dispatch_approved_signal`` accessed ``walk_result.message``
and ``walk_result.error_code`` directly.  When ``submit_limit_with_walk``
returns a ``SimpleNamespace`` or plain dict that omits those attributes, a
``dispatch_exception`` drop fires — blocking the order *after* all
pre-dispatch gates have passed.

Fix (2026-05-05): safe ``getattr`` extraction in D31 lines ~4356-4380.

These tests must be GREEN after the fix ships.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _StubEM:
    def subscribe(self, *a, **k): return None
    def emit(self, *a, **k): return None
    def publish(self, *a, **k): return None
    def unsubscribe(self, *a, **k): return None


def _make_orchestrator():
    mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )
    orc = mod.StrategyOrchestrator(event_manager=_StubEM())
    return orc


def _stub_signal(symbol="SPY", quantity=1, bid=0.95, ask=1.05):
    return {
        "symbol": symbol,
        "quantity": quantity,
        "action": "buy",
        "bid": bid,
        "ask": ask,
        "option_symbol": "SPY_20260505C00530000",
        "strategy_id": "test_strategy",
        "strategy_type": "bull_put_spread",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDispatchResultHardening:
    """Dispatch path must not raise AttributeError on result objects without
    standard attributes."""

    def test_simplenamespace_success_only_does_not_raise(self):
        """SimpleNamespace with only ``success=True`` must not raise."""
        orc = _make_orchestrator()
        walk_result = SimpleNamespace(success=True)  # no message, no error_code

        mock_om = MagicMock()
        mock_om.submit_limit_with_walk.return_value = walk_result
        orc._order_manager = mock_om

        dropped = []
        orc._record_signal_drop = lambda stage, reason, **kw: dropped.append(reason)
        dispatched = []
        orc._record_signal_dispatch_outcome = lambda outcome: dispatched.append(outcome)

        orc._dispatch_approved_signal(_stub_signal())

        assert "dispatch_exception" not in dropped, (
            "dispatch_exception recorded — attribute access must be safe"
        )
        assert dispatched == ["dispatch_submitted"], (
            f"Expected dispatch_submitted, got {dispatched}"
        )

    def test_simplenamespace_failure_only_does_not_raise(self):
        """SimpleNamespace with only ``success=False`` must not raise."""
        orc = _make_orchestrator()
        walk_result = SimpleNamespace(success=False)  # no message, no error_code

        mock_om = MagicMock()
        mock_om.submit_limit_with_walk.return_value = walk_result
        orc._order_manager = mock_om

        dropped = []
        orc._record_signal_drop = lambda stage, reason, **kw: dropped.append(reason)
        dispatched = []
        orc._record_signal_dispatch_outcome = lambda outcome: dispatched.append(outcome)

        orc._dispatch_approved_signal(_stub_signal())

        assert "dispatch_exception" not in dropped
        assert dispatched == ["dispatch_rejected"]

    def test_plain_dict_result_success(self):
        """dict result with ``success`` key must work without AttributeError."""
        orc = _make_orchestrator()
        walk_result = {"success": True, "message": "filled", "error_code": None}

        mock_om = MagicMock()
        mock_om.submit_limit_with_walk.return_value = walk_result
        orc._order_manager = mock_om

        dropped = []
        orc._record_signal_drop = lambda stage, reason, **kw: dropped.append(reason)
        dispatched = []
        orc._record_signal_dispatch_outcome = lambda outcome: dispatched.append(outcome)

        orc._dispatch_approved_signal(_stub_signal())

        assert "dispatch_exception" not in dropped
        assert dispatched == ["dispatch_submitted"]

    def test_plain_dict_result_failure(self):
        """dict result with ``success=False`` and no error_code must record rejected."""
        orc = _make_orchestrator()
        walk_result = {"success": False}

        mock_om = MagicMock()
        mock_om.submit_limit_with_walk.return_value = walk_result
        orc._order_manager = mock_om

        dropped = []
        orc._record_signal_drop = lambda stage, reason, **kw: dropped.append(reason)
        dispatched = []
        orc._record_signal_dispatch_outcome = lambda outcome: dispatched.append(outcome)

        orc._dispatch_approved_signal(_stub_signal())

        assert "dispatch_exception" not in dropped
        assert dispatched == ["dispatch_rejected"]

    def test_full_namespace_success(self):
        """Full SimpleNamespace with all attributes must still work normally."""
        orc = _make_orchestrator()
        walk_result = SimpleNamespace(
            success=True,
            message="mid-price walk filled at 1.00",
            error_code=None,
        )

        mock_om = MagicMock()
        mock_om.submit_limit_with_walk.return_value = walk_result
        orc._order_manager = mock_om

        dropped = []
        orc._record_signal_drop = lambda stage, reason, **kw: dropped.append(reason)
        dispatched = []
        orc._record_signal_dispatch_outcome = lambda outcome: dispatched.append(outcome)

        orc._dispatch_approved_signal(_stub_signal())

        assert "dispatch_exception" not in dropped
        assert dispatched == ["dispatch_submitted"]

    def test_no_bid_ask_falls_through_to_live_engine(self):
        """Signal with no bid/ask must not invoke the walk path at all."""
        orc = _make_orchestrator()

        mock_om = MagicMock()
        orc._order_manager = mock_om
        orc._live_engine = None  # no engine → expect no_live_engine drop

        dropped = []
        orc._record_signal_drop = lambda stage, reason, **kw: dropped.append(reason)
        dispatched = []
        orc._record_signal_dispatch_outcome = lambda outcome: dispatched.append(outcome)

        orc._dispatch_approved_signal(_stub_signal(bid=0.0, ask=0.0))

        mock_om.submit_limit_with_walk.assert_not_called()
        assert "no_live_engine_for_market_fallback" in dropped


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
