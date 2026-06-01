"""Focused regressions for D31 paper Jade Lizard Zero routing."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta

from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (
    SignalStrength,
    SignalType,
    TradingSignal,
)


class _StubEM:
    def subscribe(self, *args, **kwargs):
        return None

    def emit(self, *args, **kwargs):
        return None

    def publish(self, *args, **kwargs):
        return None

    def unsubscribe(self, *args, **kwargs):
        return None


def _make_orchestrator():
    mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )
    return mod.StrategyOrchestrator(event_manager=_StubEM())


def _wrapped_jade_lizard_zero_signal(target_dte: int = 0) -> dict[str, object]:
    now = datetime.now(UTC)
    expiration = now + timedelta(days=target_dte, hours=4)
    return {
        "signal": TradingSignal(
            signal_id="wrapped-jlz-1",
            signal_type=SignalType.SELL,
            symbol="SPY",
            strength=SignalStrength.STRONG,
            confidence=0.74,
            entry_price=600.0,
            stop_loss=0.0,
            take_profit=0.0,
            position_size=1,
            timestamp=now,
            expires_at=now + timedelta(minutes=10),
            metadata={
                "strategy_id": "JadeLizardZero",
                "strategy_type": "jade_lizard_zero",
                "action": "sell",
                "target_dte": target_dte,
                "expiration_date": expiration.date().isoformat(),
                "legs": [
                    {
                        "role": "short_put",
                        "option_type": "put",
                        "strike": 596.0,
                        "position": "short",
                        "contracts": 1,
                        "premium": 0.95,
                        "expiration": expiration.date().isoformat(),
                    },
                    {
                        "role": "short_call",
                        "option_type": "call",
                        "strike": 603.0,
                        "position": "short",
                        "contracts": 1,
                        "premium": 0.62,
                        "expiration": expiration.date().isoformat(),
                    },
                    {
                        "role": "long_call",
                        "option_type": "call",
                        "strike": 604.0,
                        "position": "long",
                        "contracts": 1,
                        "premium": 0.24,
                        "expiration": expiration.date().isoformat(),
                    },
                ],
            },
        )
    }


def test_d31_defaults_jade_lizard_zero_to_ultra_short() -> None:
    orch = _make_orchestrator()

    resolved = orch._apply_strategy_runtime_config_defaults("JadeLizardZero", {})

    assert resolved["target_dte"] == 0
    assert orch._resolve_horizon_bucket("JadeLizardZero", resolved) == "ultra_short"


def test_build_paper_jade_lizard_zero_leg_orders_for_entry() -> None:
    orch = _make_orchestrator()
    orch.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")

    raw_signal = _wrapped_jade_lizard_zero_signal()["signal"].to_dict()
    leg_orders = orch._build_paper_serialized_multileg_leg_orders(
        raw_signal,
        "SPY",
        1,
        "JadeLizardZero",
    )

    expiry_code = datetime.now(UTC).strftime("%y%m%d")
    assert len(leg_orders) == 3
    assert [order["side"] for order in leg_orders] == [
        "sell_to_open",
        "sell_to_open",
        "buy_to_open",
    ]
    assert [order["quantity"] for order in leg_orders] == [1, 1, 1]
    assert [order["symbol"] for order in leg_orders] == [
        f"SPXW{expiry_code}P00596000",
        f"SPXW{expiry_code}C00603000",
        f"SPXW{expiry_code}C00604000",
    ]
    assert all(order["multileg_parent_symbol"] == "SPX" for order in leg_orders)
    assert all(order["strategy_id"] == "JadeLizardZero" for order in leg_orders)
    assert all(order["multileg_leg_execution"] is True for order in leg_orders)
