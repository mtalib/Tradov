#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD07_BearCallSpread.py
Purpose: Bear Call Spread strategy — bearish credit spread selling OTM call verticals

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-03 Time: 00:00:00

Module Description:
    Dedicated Bear Call Spread strategy.  Sells an OTM call and buys a further-OTM
    call at the same expiry to collect premium when the underlying is expected to
    remain flat or decline.

    Extends CreditSpreadStrategy with bear-call-only logic:
    - Disables bull put spread generation.
    - Tightens delta selection to the bearish range.
    - Requires RSI > 50 and negative price momentum for entry.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD03_CreditSpread import (
    CreditSpreadStrategy,
    TradingSignal,
)
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import EventManager, RiskProfile

# ==============================================================================
# CONSTANTS
# ==============================================================================
BEAR_CALL_MIN_RSI = 50          # Only enter when RSI is above neutral
BEAR_CALL_MAX_MOMENTUM = -0.001  # Maximum upward momentum (must be declining)


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class BearCallSpreadStrategy(CreditSpreadStrategy):
    """
    Bear Call Spread strategy.

    Sells an OTM call vertical (sell lower-strike call, buy higher-strike call)
    to collect premium in a bearish or neutral market environment.

    Inherits full position management, risk controls, and signal plumbing
    from CreditSpreadStrategy.  Overrides signal generation to restrict to
    bear-call entries only and applies additional bearish-bias filters.
    """

    STRATEGY_NAME = "BearCallSpread"

    def __init__(
        self,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        config: dict[str, Any],
    ) -> None:
        """
        Initialise BearCallSpreadStrategy.

        Args:
            event_manager: System-wide event bus.
            risk_profile:  Risk profile governing position sizing and limits.
            config:        Strategy configuration dict.  Supports all keys from
                           CreditSpreadStrategy; ``use_bull_puts`` is forced to
                           False regardless of the supplied value.
        """
        # Force bear-call-only mode
        config = {**config, "use_bull_puts": False, "use_bear_calls": True}
        super().__init__(event_manager, risk_profile, config)
        self.logger.info("BearCallSpreadStrategy initialized (bear-call-only mode)")

    # --------------------------------------------------------------------------
    # SIGNAL GENERATION OVERRIDE
    # --------------------------------------------------------------------------

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """
        Generate bear-call-only trading signals.

        Applies an additional bearish-bias pre-filter on top of the parent
        CreditSpreadStrategy logic:
        - Requires RSI > BEAR_CALL_MIN_RSI (market not oversold).
        - Requires negative or flat short-term price momentum.

        Args:
            market_data: OHLCV DataFrame for the underlying (SPY).

        Returns:
            List of TradingSignal objects; empty when conditions are not met.
        """
        try:
            if market_data is None or market_data.empty:
                return []

            # --- Bearish pre-filter ---
            if "rsi" in market_data.columns:
                latest_rsi = float(market_data["rsi"].iloc[-1])
                if latest_rsi < BEAR_CALL_MIN_RSI:
                    self.logger.debug(
                        f"BearCallSpread: skipping — RSI {latest_rsi:.1f} < {BEAR_CALL_MIN_RSI}"
                    )
                    return []

            if "close" in market_data.columns and len(market_data) >= 2:
                closes = market_data["close"]
                momentum = (float(closes.iloc[-1]) - float(closes.iloc[-2])) / float(closes.iloc[-2])
                if momentum > BEAR_CALL_MAX_MOMENTUM:
                    self.logger.debug(
                        f"BearCallSpread: skipping — momentum {momentum:.4f} above threshold"
                    )
                    return []

            # Delegate to parent which is restricted to bear-calls via config
            return super().generate_signals(market_data)

        except Exception as e:
            self.logger.error("BearCallSpreadStrategy.generate_signals error: %s", e, exc_info=True)
            return []

    # --------------------------------------------------------------------------
    # FACTORY / HELPERS
    # --------------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        **kwargs: Any,
    ) -> "BearCallSpreadStrategy":
        """
        Convenience factory.

        Args:
            event_manager: Event bus instance.
            risk_profile:  Risk profile instance.
            **kwargs:      Forwarded to the config dict.

        Returns:
            Configured BearCallSpreadStrategy instance.
        """
        return cls(event_manager, risk_profile, kwargs)
