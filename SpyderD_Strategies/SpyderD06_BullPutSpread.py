#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD06_BullPutSpread.py
Group: D (Trading Strategies)
Purpose: Directional bull put spread strategy

Description:
    This module implements a directional bull put spread strategy for SPY options.
    The strategy sells out-of-the-money put spreads when bullish market conditions
    are detected. It incorporates volatility regime analysis, optimal entry timing,
    and research-driven profit targets. The strategy is designed to collect premium
    while limiting risk through the protective long put.:

Author: Mohamed Talib
Date: 2025-01-10
Version: 2.0 (Production-Ready)
"""

import uuid
from dataclasses import dataclass, field
# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, time, timedelta
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

from SpyderD_Strategies.SpyderD01_BaseStrategy import (Event, EventManager,
                                                       EventType, RiskProfile,
                                                       SignalStrength,
                                                       SignalType,
                                                    TradingSignal)
# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderD_Strategies.SpyderD03_CreditSpread import (CreditSpread,
                                                    CreditSpreadStrategy,
                                                       MarketCondition,
                                                       OptionLeg, SpreadState,
                                                       SpreadType)
from SpyderF_Analysis.SpyderF05_TrendDetection import TrendDetector
from SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import (
    BULL_PUT_SPREAD_PROFIT_TARGET, OPTIMAL_ENTRY_END, OPTIMAL_ENTRY_START,
    SPY_CONTRACT_MULTIPLIER)
from SpyderU_Utilities.SpyderU13_TechnicalIndicators import TechnicalIndicators

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Bull put spread specific parameters
MIN_TREND_STRENGTH = 0.3  # Minimum bullish trend strength
MAX_RSI = 70  # Maximum RSI (avoid overbought)
MIN_RSI = 30  # Minimum RSI (prefer oversold bounce)
MIN_VOLUME_RATIO = 1.0  # Minimum volume vs average

# Strike selection
SHORT_PUT_DELTA_TARGET = -0.25  # Target delta for short put
LONG_PUT_DELTA_TARGET = -0.10  # Target delta for long put
PREFERRED_SPREAD_WIDTH = 5.0  # Preferred $5 wide spreads
MAX_SPREAD_WIDTH = 10.0  # Maximum spread width

# Entry filters
MIN_SUPPORT_DISTANCE = 0.01  # Minimum 1% above support
MAX_VOLATILITY_RANK = 70  # Maximum IV rank
PREFERRED_DTE = 30  # Preferred days to expiry

# Risk management
MAX_PORTFOLIO_DELTA = -100  # Maximum negative delta exposure
PROFIT_TARGET = 0.35  # 35% of max profit
STOP_LOSS = 2.0  # 200% of credit received
DELTA_HEDGE_THRESHOLD = -30  # Delta threshold for hedging

# ==============================================================================
# ENUMS
# ==============================================================================


class BullishSignalType(Enum):
    """Types of bullish signals"""

    OVERSOLD_BOUNCE = auto()
    TREND_CONTINUATION = auto()
    SUPPORT_BOUNCE = auto()
    VOLATILITY_CRUSH = auto()
    BREAKOUT = auto()


class TrendStrength(Enum):
    """Bullish trend strength classification"""

    WEAK = auto()
    MODERATE = auto()
    STRONG = auto()
    VERY_STRONG = auto()


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class BullishAnalysis:
    """Bullish market analysis"""

    trend_strength: TrendStrength
    trend_score: float
    support_levels: List[float]
    nearest_support: float
    distance_to_support: float
    rsi: float
    volume_ratio: float
    momentum: float
    bullish_signals: List[BullishSignalType]
    confidence: float
    entry_score: float


@dataclass
class DeltaHedge:
    """Delta hedge information"""

    hedge_id: str
    parent_position_id: str
    hedge_type: str  # 'long_call', 'long_stock'
    quantity: int
    entry_price: float
    current_delta: float
    target_delta: float
    cost: float
    current_value: float = 0.0
    pnl: float = 0.0


# ==============================================================================
# BULL PUT SPREAD STRATEGY CLASS
# ==============================================================================


class BullPutSpreadStrategy(CreditSpreadStrategy):
    """
    Bull put spread strategy implementation.

    Specializes the credit spread base class for bullish directional trades
    using put spreads with enhanced trend analysis and delta hedging.
    """

    def __init__(
        self, event_manager: EventManager, risk_profile: RiskProfile, config: Dict[str, Any]
    ):
        """Initialize bull put spread strategy"""
        # Override config for bull puts only
        config["use_bull_puts"] = True
        config["use_bear_calls"] = False

        super().__init__(event_manager, risk_profile, config)

        # Update strategy name
        self.name = "BullPutSpread"

        # Additional components
        self.trend_detector = TrendDetector()
        self.greeks_calculator = GreeksCalculator()

        # Bull put specific configuration
        self.min_trend_strength = config.get("min_trend_strength", MIN_TREND_STRENGTH)
        self.profit_target = config.get("profit_target", PROFIT_TARGET)
        self.stop_loss = config.get("stop_loss", STOP_LOSS)
        self.enable_delta_hedging = config.get("enable_delta_hedging", True)

        # Delta hedging tracking
        self.active_hedges: Dict[str, DeltaHedge] = {}
        self.portfolio_delta = 0.0

        # Enhanced bullish analysis
        self.bullish_analysis: Optional[BullishAnalysis] = None

        # Performance tracking
        self.bull_put_metrics = {
            "total_spreads": 0,
            "winning_spreads": 0,
            "avg_credit": 0.0,
            "avg_days_held": 0.0,
            "support_bounces": 0,
            "trend_trades": 0,
            "hedged_positions": 0,
            "total_hedge_cost": 0.0,
        }

        self.logger.info("BullPutSpreadStrategy initialized with enhanced bullish analysis")

    # ==========================================================================
    # OVERRIDDEN METHODS
    # ==========================================================================

    def generate_signals(self, market_data: pd.DataFrame) -> List[TradingSignal]:
        """Generate bull put spread signals with enhanced analysis"""
        signals = []

        try:
            # Perform bullish analysis
            self._analyze_bullish_conditions(market_data)

            # Check if we should open bull puts
            if not self._should_open_bull_put_enhanced():
                return signals

            # Call parent method to check basic conditions
            parent_signals = super().generate_signals(market_data)

            # Filter and enhance signals
            for signal in parent_signals:
                if self._validate_bullish_signal(signal):
                    enhanced_signal = self._enhance_bull_put_signal(signal)
                    if enhanced_signal:
                        signals.append(enhanced_signal)

            # Check for delta hedging needs
            self._check_delta_hedging_needs()

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "generate_signals", "market_data_shape": market_data.shape}
            )

        return signals

    def should_exit_position(
        self, position: StrategyPosition, market_data: pd.DataFrame
    ) -> Tuple[bool, str]:
        """Enhanced exit logic for bull puts"""
        try:
            # First check parent exit conditions
            should_exit, reason = super().should_exit_position(position, market_data)
            if should_exit:
                return should_exit, reason

            # Get spread position
            spread = self.active_spreads.get(position.position_id)
            if not spread:
                return False, ""

            # Check if trend has reversed
            if self.bullish_analysis and self.bullish_analysis.trend_strength == TrendStrength.WEAK:
                if self.bullish_analysis.trend_score < 0:
                    return True, "Trend reversal detected"

            # Check if support has been broken
            current_price = market_data["close"].iloc[-1]
            if self.bullish_analysis and self.bullish_analysis.nearest_support > 0:
                if current_price < self.bullish_analysis.nearest_support * 0.99:
                    return True, "Support level broken"

            # Check delta exposure
            if spread.net_delta < -50:  # Too negative
                return True, "Delta exposure too high"

            # Check profit target (tighter for bull puts)
            profit_pct = spread.profit_percentage
            if profit_pct >= self.profit_target:
                return True, f"Profit target reached: {profit_pct:.1%}"

            return False, ""

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "should_exit_position", "position_id": position.position_id}
            )
            return False, ""

    # ==========================================================================
    # BULLISH ANALYSIS METHODS
    # ==========================================================================

    def _analyze_bullish_conditions(self, market_data: pd.DataFrame) -> None:
        """Perform comprehensive bullish market analysis"""
        try:
            close_prices = market_data["close"]
            current_price = close_prices.iloc[-1]

            # Trend analysis
            trend_data = self.trend_detector.detect_trend(market_data)
            trend_score = trend_data.get("strength", 0)

            # Classify trend strength
            if trend_score >= 0.7:
                trend_strength = TrendStrength.VERY_STRONG
            elif trend_score >= 0.5:
                trend_strength = TrendStrength.STRONG
            elif trend_score >= 0.3:
                trend_strength = TrendStrength.MODERATE
            else:
                trend_strength = TrendStrength.WEAK

            # Get support levels from parent
            support_levels = self.support_resistance.get("support", [])
            nearest_support = support_levels[0] if support_levels else current_price * 0.97
            distance_to_support = (current_price - nearest_support) / current_price

            # Technical indicators
            rsi = self.tech_indicators.calculate_rsi(close_prices, 14).iloc[-1]

            # Volume analysis
            volume = market_data["volume"]
            avg_volume = volume.rolling(20).mean().iloc[-1]
            current_volume = volume.iloc[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            # Momentum
            momentum = close_prices.pct_change(10).iloc[-1]  # 10-period momentum

            # Identify bullish signals
            bullish_signals = []

            if rsi < 35:
                bullish_signals.append(BullishSignalType.OVERSOLD_BOUNCE)

            if trend_score > 0.5 and momentum > 0:
                bullish_signals.append(BullishSignalType.TREND_CONTINUATION)

            if distance_to_support < 0.02:  # Within 2% of support
                bullish_signals.append(BullishSignalType.SUPPORT_BOUNCE)

            if self.volatility_rank < 30:  # IV coming down
                bullish_signals.append(BullishSignalType.VOLATILITY_CRUSH)

            if close_prices.iloc[-1] > close_prices.rolling(20).max().iloc[-2]:
                bullish_signals.append(BullishSignalType.BREAKOUT)

            # Calculate confidence
            confidence = 0.5  # Base confidence
            confidence += len(bullish_signals) * 0.1
            confidence += min(0.2, trend_score * 0.3)
            confidence = min(0.95, confidence)

            # Calculate entry score
            entry_score = 0
            entry_score += trend_score * 30
            entry_score += (1 - abs(rsi - 50) / 50) * 20  # RSI not extreme
            entry_score += min(20, distance_to_support * 1000)  # Distance from support
            entry_score += min(20, volume_ratio * 10)  # Volume confirmation
            entry_score += len(bullish_signals) * 10

            # Create analysis object
            self.bullish_analysis = BullishAnalysis(
                trend_strength=trend_strength,
                trend_score=trend_score,
                support_levels=support_levels,
                nearest_support=nearest_support,
                distance_to_support=distance_to_support,
                rsi=rsi,
                volume_ratio=volume_ratio,
                momentum=momentum,
                bullish_signals=bullish_signals,
                confidence=confidence,
                entry_score=entry_score,
            )

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "_analyze_bullish_conditions"})

    def _should_open_bull_put_enhanced(self) -> bool:
        """Enhanced check for bull put entry conditions"""
        if not self.bullish_analysis:
            return False

        # Check trend strength
        if self.bullish_analysis.trend_score < self.min_trend_strength:
            self.logger.debug(f"Trend too weak: {self.bullish_analysis.trend_score:.2f}")
            return False

        # Check RSI not overbought
        if self.bullish_analysis.rsi > MAX_RSI:
            self.logger.debug(f"RSI overbought: {self.bullish_analysis.rsi:.0f}")
            return False

        # Check volume confirmation
        if self.bullish_analysis.volume_ratio < MIN_VOLUME_RATIO:
            self.logger.debug(f"Insufficient volume: {self.bullish_analysis.volume_ratio:.2f}")
            return False

        # Check distance from support
        if self.bullish_analysis.distance_to_support < MIN_SUPPORT_DISTANCE:
            self.logger.debug("Too close to support level")
            return False

        # Check volatility rank
        if self.volatility_rank > MAX_VOLATILITY_RANK:
            self.logger.debug(f"IV rank too high: {self.volatility_rank:.0f}")
            return False

        # Need at least one bullish signal
        if not self.bullish_analysis.bullish_signals:
            self.logger.debug("No bullish signals detected")
            return False

        # Check entry score
        if self.bullish_analysis.entry_score < 40:
            self.logger.debug(f"Entry score too low: {self.bullish_analysis.entry_score:.0f}")
            return False

        return True

    def _validate_bullish_signal(self, signal: TradingSignal) -> bool:
        """Validate signal is appropriate for bull put spread"""
        spread_data = signal.metadata.get("spread_data", {})

        # Ensure it's a bull put spread
        if spread_data.get("spread_type") != SpreadType.BULL_PUT:
            return False

        # Additional bullish validation
        if self.bullish_analysis:
            if self.bullish_analysis.confidence < 0.6:
                return False

        return True

    def _enhance_bull_put_signal(self, signal: TradingSignal) -> Optional[TradingSignal]:
        """Enhance signal with bull put specific data"""
        try:
            # Add bullish analysis to metadata
            signal.metadata["bullish_analysis"] = {
                "trend_strength": self.bullish_analysis.trend_strength.name,
                "trend_score": self.bullish_analysis.trend_score,
                "support_distance": self.bullish_analysis.distance_to_support,
                "rsi": self.bullish_analysis.rsi,
                "momentum": self.bullish_analysis.momentum,
                "bullish_signals": [s.name for s in self.bullish_analysis.bullish_signals],
                "confidence": self.bullish_analysis.confidence,
            }

            # Adjust signal strength based on bullish analysis
            if self.bullish_analysis.entry_score >= 80:
                signal.strength = SignalStrength.VERY_STRONG
            elif self.bullish_analysis.entry_score >= 60:
                signal.strength = SignalStrength.STRONG
            elif self.bullish_analysis.entry_score >= 40:
                signal.strength = SignalStrength.MODERATE
            else:
                signal.strength = SignalStrength.WEAK

            # Update confidence
            signal.confidence = self.bullish_analysis.confidence

            return signal

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "_enhance_bull_put_signal"})
            return None

    # ==========================================================================
    # DELTA HEDGING METHODS
    # ==========================================================================

    def _check_delta_hedging_needs(self) -> None:
        """Check if delta hedging is needed"""
        if not self.enable_delta_hedging:
            return

        try:
            # Calculate portfolio delta
            self._update_portfolio_delta()

            # Check if hedging needed
            if self.portfolio_delta < MAX_PORTFOLIO_DELTA:
                self.logger.info(f"Portfolio delta too negative: {self.portfolio_delta:.0f}")
                self._create_delta_hedge()

            # Check existing hedges
            self._manage_existing_hedges()

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "_check_delta_hedging_needs"})

    def _update_portfolio_delta(self) -> None:
        """Update total portfolio delta"""
        total_delta = 0.0

        # Sum deltas from active spreads
        for spread in self.active_spreads.values():
            spread.update_greeks()
            total_delta += spread.net_delta * spread.quantity * SPY_CONTRACT_MULTIPLIER

        # Add deltas from hedges
        for hedge in self.active_hedges.values():
            total_delta += hedge.current_delta

        self.portfolio_delta = total_delta

    def _create_delta_hedge(self) -> Optional[DeltaHedge]:
        """Create delta hedge position"""
        try:
            # Calculate hedge size needed
            delta_deficit = abs(MAX_PORTFOLIO_DELTA - self.portfolio_delta)

            # Determine hedge type (prefer calls over stock)
            current_price = (
                self.market_data["close"].iloc[-1] if hasattr(self, "market_data") else 450
            )

            # Create long call hedge
            hedge = DeltaHedge(
                hedge_id=str(uuid.uuid4()),
                parent_position_id="portfolio",
                hedge_type="long_call",
                quantity=int(delta_deficit / 50),  # Assuming 0.5 delta per call
                entry_price=current_price + 5,  # 5 points OTM
                current_delta=delta_deficit,
                target_delta=0,
                cost=delta_deficit * 2,  # Simplified cost
            )

            self.active_hedges[hedge.hedge_id] = hedge
            self.bull_put_metrics["hedged_positions"] += 1
            self.bull_put_metrics["total_hedge_cost"] += hedge.cost

            self.logger.info(f"Created delta hedge: {hedge.hedge_type} x{hedge.quantity}")
            return hedge

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "_create_delta_hedge"})
            return None

    def _manage_existing_hedges(self) -> None:
        """Manage existing delta hedges"""
        hedges_to_close = []

        for hedge_id, hedge in self.active_hedges.items():
            # Update hedge value
            hedge.current_value = hedge.quantity * 100 * 2  # Simplified
            hedge.pnl = hedge.current_value - hedge.cost

            # Check if hedge still needed
            if self.portfolio_delta > DELTA_HEDGE_THRESHOLD:
                hedges_to_close.append(hedge_id)

        # Close unneeded hedges
        for hedge_id in hedges_to_close:
            self._close_hedge(hedge_id)

    def _close_hedge(self, hedge_id: str) -> bool:
        """Close delta hedge position"""
        try:
            hedge = self.active_hedges.get(hedge_id)
            if not hedge:
                return False

            del self.active_hedges[hedge_id]

            self.logger.info(f"Closed hedge {hedge_id}: P&L ${hedge.pnl:.2f}")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "_close_hedge"})
            return False

    # ==========================================================================
    # POSITION MANAGEMENT OVERRIDES
    # ==========================================================================

    def open_credit_spread(self, signal: TradingSignal) -> Optional[CreditSpread]:
        """Open bull put spread with enhanced tracking"""
        spread = super().open_credit_spread(signal)

        if spread:
            # Update bull put specific metrics
            self.bull_put_metrics["total_spreads"] += 1

            # Track signal type
            bullish_signals = signal.metadata.get("bullish_analysis", {}).get("bullish_signals", [])
            if BullishSignalType.SUPPORT_BOUNCE.name in bullish_signals:
                self.bull_put_metrics["support_bounces"] += 1
            elif BullishSignalType.TREND_CONTINUATION.name in bullish_signals:
                self.bull_put_metrics["trend_trades"] += 1

        return spread

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def get_strategy_summary(self) -> Dict[str, Any]:
        """Get comprehensive strategy summary"""
        # Get parent summary
        summary = super().get_strategy_summary()

        # Add bull put specific data
        summary["bull_put_analysis"] = {
            "trend_strength": (
                self.bullish_analysis.trend_strength.name if self.bullish_analysis else "UNKNOWN"
            ),
            "trend_score": self.bullish_analysis.trend_score if self.bullish_analysis else 0,
            "nearest_support": (
                self.bullish_analysis.nearest_support if self.bullish_analysis else 0
            ),
            "portfolio_delta": self.portfolio_delta,
            "active_hedges": len(self.active_hedges),
            "hedge_pnl": sum(h.pnl for h in self.active_hedges.values()),
        }

        summary["bull_put_metrics"] = self.bull_put_metrics.copy()

        return summary


# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":
    # Test bull put spread strategy
    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000,
        max_position_size=0.02,
        max_portfolio_risk=0.06,
        max_loss_per_trade=0.01,
    )

    config = {
        "max_spreads": 5,
        "spread_width": 5.0,
        "target_premium": 1.0,
        "min_trend_strength": 0.3,
        "enable_delta_hedging": True,
    }

    strategy = BullPutSpreadStrategy(event_manager, risk_profile, config)
    strategy.start()

    # Create bullish market data
    dates = pd.date_range(end=datetime.now(), periods=100, freq="5min")
    base_price = 445

    # Uptrend with support bounces
    trend = np.linspace(0, 10, 100)  # Uptrend
    support_bounce = np.sin(np.linspace(0, 4 * np.pi, 100)) * 2  # Oscillation
    noise = np.random.randn(100) * 0.5
    prices = base_price + trend + support_bounce + noise

    # Ensure prices don't go below support
    support_level = 445
    prices = np.maximum(prices, support_level)

    market_data = pd.DataFrame(
        {
            "timestamp": dates,
            "open": prices - 0.1,
            "high": prices + abs(np.random.randn(100) * 0.3),
            "low": prices - abs(np.random.randn(100) * 0.3),
            "close": prices,
            "volume": np.random.randint(50000000, 150000000, 100),
        }
    )

    # Add volume surge on bounces
    bounce_points = np.where(np.diff(np.sign(np.diff(prices))) > 0)[0]
    for point in bounce_points:
        if 0 < point < len(market_data):
            market_data.loc[point, "volume"] *= 2

    # Process market data
    signals = strategy.generate_signals(market_data)

    # Print results
    print(f"Strategy: {strategy.name}")

    if strategy.bullish_analysis:
        print(f"\nBullish Analysis:")
        print(f"Trend Strength: {strategy.bullish_analysis.trend_strength.name}")
        print(f"Trend Score: {strategy.bullish_analysis.trend_score:.2f}")
        print(f"RSI: {strategy.bullish_analysis.rsi:.0f}")
        print(f"Distance to Support: {strategy.bullish_analysis.distance_to_support:.2%}")
        print(f"Momentum: {strategy.bullish_analysis.momentum:.3f}")
        print(f"Bullish Signals: {[s.name for s in strategy.bullish_analysis.bullish_signals]}")
        print(f"Confidence: {strategy.bullish_analysis.confidence:.2%}")

    print(f"\nSignals Generated: {len(signals)}")

    for signal in signals:
        spread_data = signal.metadata.get("spread_data", {})
        bullish_data = signal.metadata.get("bullish_analysis", {})

        print(f"\nBull Put Spread Signal:")
        print(f"Strength: {signal.strength.name}")
        print(f"Short Strike: ${spread_data.get('short_strike', 0)}")
        print(f"Long Strike: ${spread_data.get('long_strike', 0)}")
        print(f"Credit: ${spread_data.get('credit', 0):.2f}")
        print(f"Max Loss: ${spread_data.get('max_loss', 0):.2f}")
        print(f"Probability: {spread_data.get('probability_profit', 0):.2%}")
        print(f"Bullish Signals: {bullish_data.get('bullish_signals', [])}")

    # Get strategy summary
    summary = strategy.get_strategy_summary()
    print(f"\nStrategy Summary:")
    print(f"Portfolio Delta: {summary['bull_put_analysis']['portfolio_delta']:.0f}")
    print(f"Active Hedges: {summary['bull_put_analysis']['active_hedges']}")
    print(f"Total Spreads: {summary['bull_put_metrics']['total_spreads']}")
    print(f"Support Bounces: {summary['bull_put_metrics']['support_bounces']}")
    print(f"Trend Trades: {summary['bull_put_metrics']['trend_trades']}")

    strategy.stop()
    print("\nBullPutSpreadStrategy test completed!")
