"""SPEC-9 — E01 daily-loss kill switch must read broker P&L, not local zeros.

Audit reference: 2026-05-02_Codebase_Audit_v27.md → SPEC-9.

The bug: ``_calculate_risk_metrics`` (E01:1522) computes daily P&L as:

    daily_pnl = sum(pos.unrealized_pnl + pos.realized_pnl
                    for pos in self._positions.values())

But ``_handle_position_update`` (E01:1455-1456) writes both fields from the
Tradier ``positions`` endpoint payload — which has NO ``UnrealizedPNL`` or
``RealizedPNL`` field, so ``data.get("UnrealizedPNL", 0.0)`` is ALWAYS 0.0.
Result: ``daily_pnl`` is always 0.0 in production, and the daily-loss kill
switch (E01:814, 1220, 1274) NEVER trips.

This is the most dangerous defect in the v27 audit: the headline daily-loss
circuit breaker is silently unenforceable in live mode.

Required behavior after SPEC-9:
- ``_calculate_risk_metrics`` reads daily P&L from
  ``self._cached_account_balances`` (key: ``close_pl`` or ``day_change``),
  not from summing local Position objects.
- A balance-fed daily P&L of -$100 (with a max_daily_loss limit of $50)
  must trip the daily-loss circuit and reject ``validate_signal``.
- ``_handle_position_update`` must STOP overwriting position P&L fields
  with 0.0 from a Tradier endpoint that doesn't return those fields.

These tests are RED until SPEC-9 ships.
"""

from __future__ import annotations

from threading import RLock
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from Spyder.SpyderE_Risk.SpyderE01_RiskManager import RiskManager


def _make_minimal_manager(
    cached_balances: dict | None = None,
    positions: dict | None = None,
    max_daily_loss: float = 50.0,
):
    """Construct an E01 RiskManager bypassing the heavyweight constructor."""
    mgr = RiskManager.__new__(RiskManager)
    mgr._risk_lock = RLock()
    mgr._positions = positions or {}
    mgr._cached_account_balances = cached_balances or {}
    mgr._account_state_synced = True
    mgr._data_stale = False
    mgr._y03_veto_state = "ok"
    mgr._observe_only_agents = True
    mgr._enforce_decision_quality_slo = False
    mgr._last_portfolio_greeks = None
    mgr._risk_metrics = None
    mgr._config = {}
    mgr.config = SimpleNamespace(
        risk_limits={
            "max_daily_loss": max_daily_loss,
            "max_total_exposure": 1_000_000.0,
            "max_concentration_ratio": 1.0,
            "max_options_exposure": 1_000_000.0,
            "max_margin_usage": 1.0,
        }
    )
    mgr.tradier_client = None
    mgr.metrics = {"position_updates": 0}
    mgr.logger = SimpleNamespace(
        debug=lambda *a, **k: None,
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )
    mgr.error_handler = SimpleNamespace(handle_error=lambda *a, **k: None)
    # Optional N04 dependency — stub it out to None so risk-metrics doesn't crash.
    mgr._get_n04 = lambda: None
    return mgr


class TestDailyLossFromBrokerPnL:
    """SPEC-9: a broker-fed loss must trip the kill switch."""

    def test_broker_close_pl_negative_yields_negative_daily_pnl(self):
        """A negative close_pl in cached balances must produce negative daily_pnl."""
        # Cached balances reflect a -$100 day, but local positions have zero PnL.
        mgr = _make_minimal_manager(
            cached_balances={
                "net_liquidation": 100_000.0,
                "total_cash": 50_000.0,
                "margin_used": 0.0,
                "margin_available": 100_000.0,
                "close_pl": -100.0,   # Tradier balances field — actual day P&L
                "day_change": -100.0,  # Some Tradier responses use day_change
            },
            positions={},  # No local positions — proves daily_pnl comes from balances
        )

        metrics = mgr._calculate_risk_metrics()

        assert metrics.daily_pnl == pytest.approx(-100.0), (
            f"SPEC-9: daily_pnl must be sourced from cached_account_balances "
            f"(close_pl/day_change), not from summing local Position objects. "
            f"Currently the position-PnL sum is always 0.0 because Tradier's "
            f"positions endpoint doesn't return PnL fields. Got daily_pnl={metrics.daily_pnl}."
        )

    def test_broker_loss_above_limit_trips_kill_switch(self):
        """A broker-fed loss exceeding max_daily_loss must trigger CRITICAL risk level."""
        from Spyder.SpyderE_Risk.SpyderE01_RiskManager import RiskLevel

        mgr = _make_minimal_manager(
            cached_balances={
                "net_liquidation": 100_000.0,
                "total_cash": 50_000.0,
                "margin_used": 0.0,
                "margin_available": 100_000.0,
                "close_pl": -150.0,   # exceeds max_daily_loss=50
                "day_change": -150.0,
            },
            max_daily_loss=50.0,
        )

        metrics = mgr._calculate_risk_metrics()

        assert metrics.risk_level == RiskLevel.CRITICAL, (
            f"SPEC-9: a broker-fed loss exceeding max_daily_loss MUST set "
            f"risk_level to CRITICAL so the kill switch trips. "
            f"Got risk_level={metrics.risk_level!r}, daily_pnl={metrics.daily_pnl}. "
            f"This is the headline circuit breaker — it must work."
        )


class TestPositionUpdateDoesNotZeroBrokerPnL:
    """SPEC-9 secondary: _handle_position_update must not write 0.0 to PnL fields.

    The Tradier positions endpoint returns no PnL fields. The current code
    does ``unrealized_pnl=float(data.get("UnrealizedPNL", 0.0))`` which
    silently writes 0.0 every cycle, masking any true PnL stored elsewhere.
    """

    def test_position_update_preserves_existing_pnl_when_payload_lacks_field(self):
        """When the Tradier payload has no PnL field, existing values must be kept."""
        import asyncio
        from Spyder.SpyderE_Risk.SpyderE01_RiskManager import Position

        mgr = _make_minimal_manager()
        # Pre-seed a position with non-zero PnL.
        existing = Position(
            symbol="SPY",
            quantity=10,
            market_price=500.0,
            market_value=5_000.0,
            average_fill_price=499.0,
            unrealized_pnl=10.0,
            realized_pnl=5.0,
            currency="USD",
            security_type="STK",
        )
        mgr._positions["SPY"] = existing

        # Tradier-style payload with NO UnrealizedPNL / RealizedPNL keys.
        tradier_payload = {
            "Symbol": "SPY",
            "Position": 10,
            "MarketPrice": 501.0,
            "MarketValue": 5_010.0,
            "AverageCost": 499.0,
            "Currency": "USD",
            "SecurityType": "STK",
            # NO "UnrealizedPNL" key — Tradier doesn't return it on this endpoint.
            # NO "RealizedPNL" key.
        }

        asyncio.run(mgr._handle_position_update(tradier_payload))

        updated = mgr._positions["SPY"]
        assert updated.unrealized_pnl != 0.0 or updated.realized_pnl != 0.0, (
            "SPEC-9: when the position-update payload lacks PnL fields, "
            "_handle_position_update must NOT silently write 0.0 — that "
            "destroys any PnL stored elsewhere. Either preserve the existing "
            "value, or stop overwriting these fields from this code path."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
