#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD37_BullishStrangle.py
Purpose: Bullish Strangle strategy - bullish long strangle with downside hedge

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-05-27 Time: 00:00:00

Module Description:
    Dedicated Bullish Strangle strategy. Buys an OTM call and an OTM put with
    a bullish tilt by keeping the call strike closer to spot than the put
    strike. This expresses upside participation while retaining a defined-risk
    downside hedge.

    Entry intent:
    - Bullish momentum confirmation via price action and optional RSI.
    - Debit-defined risk through a long two-leg options structure.
    - Reuses shared U14 strangle payoff utilities instead of embedding custom
      payoff math in the strategy module.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta, UTC
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
from Spyder.SpyderU_Utilities.SpyderU14_OptionStrategies import get_option_strategies


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class BullishStrangleStrategy(BaseStrategy):
    """Bullish long-strangle strategy with a closer upside strike."""

    STRATEGY_NAME = "BullishStrangle"

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
            strategy_type="bullish_strangle",
        )
        self.symbol = str(self.config.get("symbol", "SPY")).upper()
        self.rsi_floor = float(self.config.get("rsi_floor", 52.0))
        self.min_momentum = float(self.config.get("min_momentum", 0.0010))
        self.call_otm_pct = max(float(self.config.get("call_otm_pct", 0.010)), 0.001)
        self.put_otm_pct = max(
            float(self.config.get("put_otm_pct", 0.020)),
            self.call_otm_pct + 0.001,
        )
        self.target_debit = max(abs(float(self.config.get("target_debit", 9.0))), 0.05)
        self.call_weight = min(max(float(self.config.get("call_weight", 0.60)), 0.50), 0.85)
        self.stop_multiple = min(max(float(self.config.get("stop_multiple", 0.50)), 0.10), 0.95)
        self.target_multiple = max(float(self.config.get("target_multiple", 1.65)), 1.05)
        self.signal_expiry_seconds = int(self.config.get("signal_expiry_seconds", 300))
        self.dte_days = max(int(self.config.get("dte_days", 30)), 1)
        self.max_contracts = max(int(self.config.get("max_contracts", 6)), 1)
        self.strike_increment = max(float(self.config.get("strike_increment", 1.0)), 0.5)
        self.bullish_stop_pct = max(float(self.config.get("bullish_stop_pct", 0.0060)), 0.001)

        self.option_strategies = get_option_strategies()

        self.logger.info("BullishStrangleStrategy initialized")

    @staticmethod
    def _extract_series(market_data: pd.DataFrame, candidates: tuple[str, ...]) -> pd.Series:
        for column in candidates:
            if column in market_data.columns:
                return market_data[column].dropna()
        return pd.Series(dtype=float)

    def _snap_strike(self, price: float) -> float:
        snapped = round(price / self.strike_increment) * self.strike_increment
        return round(snapped, 2)

    def _resolve_premiums(self) -> tuple[float, float]:
        configured_call = self.config.get("call_premium")
        configured_put = self.config.get("put_premium")
        if configured_call is not None and configured_put is not None:
            return max(float(configured_call), 0.01), max(float(configured_put), 0.01)

        call_premium = round(max(self.target_debit * self.call_weight, 0.01), 2)
        put_premium = round(max(self.target_debit - call_premium, 0.01), 2)
        return call_premium, put_premium

    def _build_structure(self, spot_now: float) -> tuple[Any, float, float, datetime, float, float]:
        call_strike = self._snap_strike(spot_now * (1.0 + self.call_otm_pct))
        put_strike = self._snap_strike(spot_now * (1.0 - self.put_otm_pct))
        call_premium, put_premium = self._resolve_premiums()
        expiry = datetime.now(UTC) + timedelta(days=self.dte_days)

        structure = self.option_strategies.create_strangle(
            call_strike=call_strike,
            put_strike=put_strike,
            expiry=expiry,
            call_premium=call_premium,
            put_premium=put_premium,
            underlying_price=spot_now,
            position_type="LONG",
        )
        return structure, call_strike, put_strike, expiry, call_premium, put_premium

    @staticmethod
    def _strength_from_confidence(confidence: float) -> SignalStrength:
        if confidence >= 0.85:
            return SignalStrength.VERY_STRONG
        if confidence >= 0.72:
            return SignalStrength.STRONG
        return SignalStrength.MODERATE

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Generate bullish long-strangle entries when the tape is supportive."""
        try:
            if market_data is None or market_data.empty:
                return []

            closes = self._extract_series(market_data, ("close", "Close", "SPY", "price", "last"))
            if len(closes) < 3:
                return []

            spot_now = float(closes.iloc[-1])
            spot_prev = float(closes.iloc[-2])
            if spot_prev <= 0:
                return []

            momentum = (spot_now - spot_prev) / spot_prev
            if momentum < self.min_momentum:
                return []

            rsi_series = self._extract_series(market_data, ("rsi", "RSI"))
            rsi_value = float(rsi_series.iloc[-1]) if not rsi_series.empty else None
            if rsi_value is not None and rsi_value < self.rsi_floor:
                return []

            structure, call_strike, put_strike, expiry, call_premium, put_premium = self._build_structure(spot_now)
            if not (put_strike < spot_now < call_strike):
                return []

            total_debit = abs(float(structure.net_premium))
            breakevens = self.option_strategies.calculate_breakeven_points(structure)
            if len(breakevens) >= 2:
                lower_breakeven = float(min(breakevens))
                upper_breakeven = float(max(breakevens))
            else:
                lower_breakeven = round(put_strike - total_debit, 2)
                upper_breakeven = round(call_strike + total_debit, 2)

            rsi_bonus = 0.0
            if rsi_value is not None:
                rsi_bonus = max(0.0, min(0.15, (rsi_value - self.rsi_floor) * 0.0075))
            confidence = min(0.95, max(0.55, 0.58 + momentum * 25.0 + rsi_bonus))
            strength = self._strength_from_confidence(confidence)

            signal = TradingSignal(
                signal_id=f"BSTRANGLE_{uuid.uuid4().hex[:10]}",
                signal_type=SignalType.BUY,
                symbol=self.symbol,
                strength=strength,
                confidence=confidence,
                entry_price=total_debit,
                stop_loss=max(total_debit * self.stop_multiple, 0.01),
                take_profit=max(total_debit * self.target_multiple, total_debit + 0.01),
                position_size=0,
                timestamp=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(seconds=self.signal_expiry_seconds),
                metadata={
                    "strategy": "bullish_strangle",
                    "strategy_name": self.STRATEGY_NAME,
                    "strategy_type": "bullish_strangle",
                    "structure": "strangle",
                    "direction": "bullish",
                    "underlying_spot": spot_now,
                    "call_strike": call_strike,
                    "put_strike": put_strike,
                    "call_premium": call_premium,
                    "put_premium": put_premium,
                    "total_debit": total_debit,
                    "max_loss": float(structure.max_loss or total_debit),
                    "max_profit": structure.max_profit,
                    "upper_breakeven": upper_breakeven,
                    "lower_breakeven": lower_breakeven,
                    "call_otm_pct": self.call_otm_pct,
                    "put_otm_pct": self.put_otm_pct,
                    "expiry": expiry.isoformat(),
                    "legs": [
                        {
                            "option_type": "call",
                            "position": "long",
                            "strike": call_strike,
                            "premium": call_premium,
                        },
                        {
                            "option_type": "put",
                            "position": "long",
                            "strike": put_strike,
                            "premium": put_premium,
                        },
                    ],
                    "momentum": momentum,
                    "rsi": rsi_value,
                    "strangle_data": {
                        "bias": "bullish",
                        "expiry_days": self.dte_days,
                        "breakevens": {
                            "upper": upper_breakeven,
                            "lower": lower_breakeven,
                        },
                    },
                },
            )
            return [signal]

        except Exception as e:
            self.logger.error("BullishStrangleStrategy.generate_signals error: %s", e, exc_info=True)
            return []

    def validate_signal(self, signal: TradingSignal) -> bool:
        """Validate the bullish strangle signal shape and risk assumptions."""
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

        metadata = signal.metadata or {}
        if metadata.get("strategy_type") != "bullish_strangle":
            return False

        spot = float(metadata.get("underlying_spot", 0.0) or 0.0)
        call_strike = float(metadata.get("call_strike", 0.0) or 0.0)
        put_strike = float(metadata.get("put_strike", 0.0) or 0.0)
        call_otm_pct = float(metadata.get("call_otm_pct", 0.0) or 0.0)
        put_otm_pct = float(metadata.get("put_otm_pct", 0.0) or 0.0)

        if not (put_strike < spot < call_strike):
            return False
        if call_otm_pct >= put_otm_pct:
            return False

        return signal.confidence >= 0.50

    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Risk-based contract sizing for a debit long strangle."""
        debit_per_contract = max(signal.entry_price * 100.0, 1.0)
        account_size = float(getattr(self.risk_profile, "account_size", 0.0) or 0.0)
        max_loss_per_trade = float(getattr(self.risk_profile, "max_loss_per_trade", 0.01) or 0.01)
        risk_budget = account_size * max_loss_per_trade
        contracts = int(risk_budget // debit_per_contract)
        return max(1, min(self.max_contracts, contracts))

    def should_exit_position(
        self,
        position: StrategyPosition,
        market_data: pd.DataFrame,
    ) -> tuple[bool, str]:
        """Exit on profitable breakout or early bullish-thesis failure."""
        try:
            if market_data is None or market_data.empty:
                return False, ""

            closes = self._extract_series(market_data, ("close", "Close", "SPY", "price", "last"))
            if closes.empty:
                return False, ""

            spot = float(closes.iloc[-1])
            upper_breakeven = float(position.metadata.get("upper_breakeven", float("inf")))
            lower_breakeven = float(position.metadata.get("lower_breakeven", float("-inf")))
            entry_spot = float(position.metadata.get("underlying_spot", spot))

            if spot >= upper_breakeven:
                return True, "upper_breakeven_reached"
            if spot <= lower_breakeven:
                return True, "lower_breakeven_reached"
            if spot <= entry_spot * (1.0 - self.bullish_stop_pct):
                return True, "bullish_thesis_failed"

            return False, ""

        except Exception as e:
            self.logger.error("BullishStrangleStrategy.should_exit_position error: %s", e, exc_info=True)
            return False, ""

    @classmethod
    def create(
        cls,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        **kwargs: Any,
    ) -> "BullishStrangleStrategy":
        """Convenience factory."""
        return cls(event_manager, risk_profile, kwargs)
