#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD06_BullPutSpread.py
Purpose: Bull Put Spread strategy — bullish credit spread selling OTM put verticals

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-03 Time: 00:00:00

Module Description:
    Dedicated Bull Put Spread strategy.  Sells an OTM put and buys a further-OTM
    put at the same expiry to collect premium when the underlying is expected to
    remain flat or rise.

    Extends CreditSpreadStrategy with bull-put-only logic:
    - Disables bear call spread generation.
    - Tightens delta selection to the bullish range.
    - Requires RSI < 50 and positive price momentum for entry.
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
BULL_PUT_MAX_RSI = 50          # Only enter when RSI is below neutral
BULL_PUT_MIN_MOMENTUM = 0.001  # Minimum upward price momentum (%)


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class BullPutSpreadStrategy(CreditSpreadStrategy):
    """
    Bull Put Spread strategy.

    Sells an OTM put vertical (sell higher-strike put, buy lower-strike put)
    to collect premium in a bullish or neutral market environment.

    Inherits full position management, risk controls, and signal plumbing
    from CreditSpreadStrategy.  Overrides signal generation to restrict to
    bull-put entries only and applies additional bullish-bias filters.
    """

    STRATEGY_NAME = "BullPutSpread"

    def __init__(
        self,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        config: dict[str, Any],
    ) -> None:
        """
        Initialise BullPutSpreadStrategy.

        Args:
            event_manager: System-wide event bus.
            risk_profile:  Risk profile governing position sizing and limits.
            config:        Strategy configuration dict.  Supports all keys from
                           CreditSpreadStrategy; ``use_bear_calls`` is forced to
                           False regardless of the supplied value.
        """
        # Force bull-put-only mode
        config = {**config, "use_bull_puts": True, "use_bear_calls": False}
        super().__init__(event_manager, risk_profile, config)
        self.logger.info("BullPutSpreadStrategy initialized (bull-put-only mode)")

    # --------------------------------------------------------------------------
    # SIGNAL GENERATION OVERRIDE
    # --------------------------------------------------------------------------

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """
        Generate bull-put-only trading signals.

        Applies an additional bullish-bias pre-filter on top of the parent
        CreditSpreadStrategy logic:
        - Requires RSI < BULL_PUT_MAX_RSI (market not overbought).
        - Requires positive short-term price momentum.

        Args:
            market_data: OHLCV DataFrame for the underlying (SPY).

        Returns:
            List of TradingSignal objects; empty when conditions are not met.
        """
        try:
            if market_data is None or market_data.empty:
                return []

            # --- Bullish pre-filter ---
            if "rsi" in market_data.columns:
                latest_rsi = float(market_data["rsi"].iloc[-1])
                if latest_rsi > BULL_PUT_MAX_RSI:
                    self.logger.debug(
                        f"BullPutSpread: skipping — RSI {latest_rsi:.1f} > {BULL_PUT_MAX_RSI}"
                    )
                    return []

            if "close" in market_data.columns and len(market_data) >= 2:
                closes = market_data["close"]
                momentum = (float(closes.iloc[-1]) - float(closes.iloc[-2])) / float(closes.iloc[-2])  # noqa: E501
                if momentum < BULL_PUT_MIN_MOMENTUM:
                    self.logger.debug(
                        f"BullPutSpread: skipping — momentum {momentum:.4f} below threshold"
                    )
                    return []

            # Delegate to parent which is restricted to bull-puts via config
            return super().generate_signals(market_data)

        except Exception as e:
            self.logger.error("BullPutSpreadStrategy.generate_signals error: %s", e, exc_info=True)
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
    ) -> "BullPutSpreadStrategy":
        """
        Convenience factory.

        Args:
            event_manager: Event bus instance.
            risk_profile:  Risk profile instance.
            **kwargs:      Forwarded to the config dict.

        Returns:
            Configured BullPutSpreadStrategy instance.
        """
        return cls(event_manager, risk_profile, kwargs)
