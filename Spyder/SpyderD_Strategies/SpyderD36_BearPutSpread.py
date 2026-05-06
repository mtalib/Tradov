#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD36_BearPutSpread.py
Purpose: Bear Put Spread strategy - bearish debit spread with defined risk

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-05-05 Time: 00:00:00

Module Description:
    Dedicated Bear Put Spread strategy. Buys a put debit spread
    (buy higher-strike put, sell lower-strike put) to express bearish
    directional bias with capped downside.

    Entry intent:
    - Bear trend confirmation via RSI and short-term momentum.
    - Controlled risk through fixed debit and stop/target exits.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (
    BaseStrategy,
    EventManager,
    RiskProfile,
    SignalStrength,
    SignalType,
    StrategyPosition,
    TradingSignal,
)


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class BearPutSpreadStrategy(BaseStrategy):
    """Bear put debit spread strategy."""

    STRATEGY_NAME = "BearPutSpread"

    def __init__(
        self,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        config: dict[str, Any],
        name: str | None = None,
    ) -> None:
        super().__init__(
            name=name or self.STRATEGY_NAME,
            event_manager=event_manager,
            risk_profile=risk_profile,
            config=config,
            strategy_type="bear_put_spread",
        )
        self.rsi_ceiling = float(self.config.get("rsi_ceiling", 50.0))
        self.max_momentum = float(self.config.get("max_momentum", -0.0005))
        self.target_debit = float(self.config.get("target_debit", 1.00))
        self.target_multiple = float(self.config.get("target_multiple", 1.80))
        self.stop_multiple = float(self.config.get("stop_multiple", 0.50))
        self.signal_expiry_seconds = int(self.config.get("signal_expiry_seconds", 300))
        self.max_contracts = int(self.config.get("max_contracts", 10))

        self.logger.info("BearPutSpreadStrategy initialized")

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Generate bearish debit spread entries."""
        try:
            if market_data is None or market_data.empty or "close" not in market_data.columns:
                return []

            closes = market_data["close"].dropna()
            if len(closes) < 2:
                return []

            spot_now = float(closes.iloc[-1])
            spot_prev = float(closes.iloc[-2])
            if spot_prev <= 0:
                return []

            momentum = (spot_now - spot_prev) / spot_prev
            if momentum > self.max_momentum:
                return []

            if "rsi" in market_data.columns:
                rsi_value = float(market_data["rsi"].iloc[-1])
                if rsi_value > self.rsi_ceiling:
                    return []

            entry = max(self.target_debit, 0.05)
            stop_loss = max(entry * self.stop_multiple, 0.01)
            take_profit = max(entry * self.target_multiple, entry + 0.01)

            signal = TradingSignal(
                signal_id=f"BPS_{uuid.uuid4().hex[:10]}",
                signal_type=SignalType.BUY,
                symbol="SPY",
                strength=SignalStrength.STRONG,
                confidence=min(0.95, max(0.55, 0.60 + abs(momentum) * 10.0)),
                entry_price=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                position_size=0,
                timestamp=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=self.signal_expiry_seconds),
                metadata={
                    "strategy_type": "bear_put_spread",
                    "structure": "put_debit_vertical",
                    "direction": "bearish",
                    "underlying_spot": spot_now,
                    "momentum": momentum,
                },
            )
            return [signal]

        except Exception as e:
            self.logger.error("BearPutSpreadStrategy.generate_signals error: %s", e, exc_info=True)
            return []

    def validate_signal(self, signal: TradingSignal) -> bool:
        """Validate signal shape and risk sanity."""
        if signal is None or not signal.is_valid():
            return False
        if signal.signal_type != SignalType.BUY:
            return False
        if signal.entry_price <= 0:
            return False
        if signal.stop_loss <= 0 or signal.stop_loss >= signal.entry_price:
            return False
        if signal.take_profit <= signal.entry_price:
            return False
        return signal.confidence >= 0.50

    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Risk-based contract sizing for debit spreads."""
        debit_per_contract = max(signal.entry_price * 100.0, 1.0)
        risk_budget = self.risk_profile.account_size * self.risk_profile.max_loss_per_trade
        contracts = int(risk_budget // debit_per_contract)
        return max(1, min(self.max_contracts, contracts))

    def should_exit_position(
        self,
        position: StrategyPosition,
        market_data: pd.DataFrame,
    ) -> tuple[bool, str]:
        """Evaluate stop/target and simple trend-failure exits."""
        try:
            if market_data is None or market_data.empty or "close" not in market_data.columns:
                return False, ""

            spot = float(market_data["close"].iloc[-1])
            entry_spot = float(position.metadata.get("underlying_spot", spot))
            downside_target_pct = float(self.config.get("underlying_target_pct", 0.0060))
            upside_stop_pct = float(self.config.get("underlying_stop_pct", 0.0035))

            if spot <= entry_spot * (1.0 - downside_target_pct):
                return True, "underlying_target_reached"
            if spot >= entry_spot * (1.0 + upside_stop_pct):
                return True, "underlying_stop_triggered"

            return False, ""

        except Exception as e:
            self.logger.error("BearPutSpreadStrategy.should_exit_position error: %s", e, exc_info=True)
            return False, ""

    @classmethod
    def create(
        cls,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        **kwargs: Any,
    ) -> "BearPutSpreadStrategy":
        """Convenience factory."""
        return cls(event_manager, risk_profile, kwargs)
