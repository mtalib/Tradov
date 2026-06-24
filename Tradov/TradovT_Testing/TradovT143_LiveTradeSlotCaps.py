from __future__ import annotations

from types import SimpleNamespace

from Tradov.TradovR_Runtime.TradovR04_LiveEngine import (
    ExecutionState,
    LiveEngine,
    LiveTradingConfig,
    SafetyCheckResult,
)


class _FakeEventManager:
    def subscribe(self, *_args, **_kwargs) -> None:
        return None


class _FakeBroker:
    pass


def _make_engine(
    *,
    max_live_trades: int = 3,
    max_pair_trades: int = 3,
    max_directional_trades: int = 0,
) -> LiveEngine:
    config = LiveTradingConfig(
        account_id="PAPER-TEST",
        max_live_trades=max_live_trades,
        max_pair_trades=max_pair_trades,
        max_directional_trades=max_directional_trades,
    )
    engine = LiveEngine(_FakeBroker(), SimpleNamespace(), config, event_manager=_FakeEventManager())
    engine.state = ExecutionState.TRADING
    return engine


def test_collect_live_trade_slots_dedupes_pair_keys_and_directional_strategies() -> None:
    engine = _make_engine()
    engine.pending_orders = {
        "pending-pair": {
            "order": {
                "strategy_id": "pair-alpha",
                "strategy_type": "pair_trading",
                "metadata": {
                    "strategy_id": "pair-alpha",
                    "strategy_type": "pair_trading",
                    "pair_key": "pair-a",
                },
            }
        }
    }
    engine.active_positions = {
        "AAA": {
            "strategy_id": "pair-alpha",
            "strategy_type": "pair_trading",
            "pair_key": "pair-a",
        },
        "BBB": {
            "strategy_id": "pair-alpha",
            "strategy_type": "pair_trading",
            "pair_key": "pair-a",
        },
        "CCC": {
            "strategy_id": "trend-alpha",
            "strategy_type": "directional",
        },
        "DDD": {
            "strategy_id": "trend-alpha",
            "strategy_type": "directional",
        },
    }

    live_slots = engine._collect_live_trade_slots()

    assert live_slots["pair"] == {"pair-a"}
    assert live_slots["directional"] == {"trend-alpha"}


def test_perform_order_safety_checks_rejects_when_pair_limit_exceeded() -> None:
    engine = _make_engine(max_live_trades=5, max_pair_trades=3, max_directional_trades=5)
    engine.active_positions = {
        "AAA": {"strategy_id": "pair-alpha", "strategy_type": "pair_trading", "pair_key": "pair-a"},
        "BBB": {"strategy_id": "pair-beta", "strategy_type": "pair_trading", "pair_key": "pair-b"},
        "CCC": {"strategy_id": "pair-gamma", "strategy_type": "pair_trading", "pair_key": "pair-c"},
    }

    result = engine._perform_order_safety_checks(
        {
            "symbol": "DDD",
            "quantity": 1,
            "strategy_id": "pair-delta",
            "strategy_type": "pair_trading",
            "metadata": {"strategy_id": "pair-delta", "strategy_type": "pair_trading", "pair_key": "pair-d"},
        }
    )

    assert result.result == SafetyCheckResult.FAILED
    assert result.check_name == "pair_trade_limit"


def test_perform_order_safety_checks_rejects_when_directional_limit_exceeded() -> None:
    engine = _make_engine(max_live_trades=5, max_pair_trades=5, max_directional_trades=0)
    engine.active_positions = {
        "AAA": {"strategy_id": "trend-alpha", "strategy_type": "directional"},
    }
    engine.pending_orders = {
        "pending-trend": {
            "order": {
                "strategy_id": "trend-alpha",
                "strategy_type": "directional",
                "metadata": {"strategy_id": "trend-alpha", "strategy_type": "directional"},
            }
        }
    }

    result = engine._perform_order_safety_checks(
        {
            "symbol": "BBB",
            "quantity": 1,
            "strategy_id": "trend-beta",
            "strategy_type": "directional",
            "metadata": {"strategy_id": "trend-beta", "strategy_type": "directional"},
        }
    )

    assert result.result == SafetyCheckResult.FAILED
    assert result.check_name == "directional_trade_limit"
