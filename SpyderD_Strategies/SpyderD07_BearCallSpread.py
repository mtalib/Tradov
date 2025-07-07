#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD07_BearCallSpread.py
Group: D (Trading Strategies)
Purpose: Directional bear call spread strategy

Description:
    This module implements a directional bear call spread strategy for SPY options.
    The strategy sells out-of-the-money call spreads when bearish market conditions
    are detected. It incorporates resistance level analysis, momentum indicators,
    and volatility regime detection to optimize entry and exit timing.

Author: Mohamed Talib
Date: 2025-01-10
Version: 2.0 (Production-Ready)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
import uuid

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderD_Strategies.SpyderD03_CreditSpread import (
    CreditSpreadStrategy, CreditSpread, SpreadType, SpreadState,
    MarketCondition, OptionLeg
)
from SpyderD_Strategies.SpyderD01_BaseStrategy import (
    TradingSignal, SignalType, SignalStrength,
    EventManager, RiskProfile, Event, EventType
)
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import (
    BEAR_CALL_SPREAD_PROFIT_TARGET,
    OPTIMAL_ENTRY_START,
    OPTIMAL_ENTRY_END,
    SPY_CONTRACT_MULTIPLIER
)
from SpyderU_Utilities.SpyderU13_TechnicalIndicators import TechnicalIndicators
from SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from SpyderF_Analysis.SpyderF05_TrendDetection import TrendDetector
from SpyderF_Analysis.SpyderF02_PriceAction import PriceActionAnalyzer

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Bear call spread specific parameters
MIN_BEARISH_STRENGTH = -0.3  # Minimum bearish trend strength
MIN_RSI = 30  # Minimum RSI (avoid oversold)
MAX_RSI = 70  # Maximum RSI (prefer overbought)
MIN_VOLUME_RATIO = 1.2  # Higher volume on down moves

# Strike selection
SHORT_CALL_DELTA_TARGET = 0.25  # Target delta for short call
LONG_CALL_DELTA_TARGET = 0.10   # Target delta for long call
PREFERRED_SPREAD_WIDTH = 5.0    # Preferred $5 wide spreads
MAX_SPREAD_WIDTH = 10.0        # Maximum spread width

# Entry filters
MIN_RESISTANCE_DISTANCE = 0.01  # Minimum 1% below resistance
MAX_VOLATILITY_RANK = 80       # Higher IV acceptable for bear calls
PREFERRED_DTE = 30             # Preferred days to expiry

# Risk management
MAX_PORTFOLIO_DELTA = 100      # Maximum positive delta exposure
PROFIT_TARGET = 0.40          # 40% of max profit
STOP_LOSS = 2.0              # 200% of credit received
DELTA_HEDGE_THRESHOLD = 30    # Delta threshold for hedging

# Distribution days
DISTRIBUTION_DAY_THRESHOLD = 3  # Number of distribution days to confirm
DISTRIBUTION_VOLUME_INCREASE = 1.5  # Volume increase on down days

# ==============================================================================
# ENUMS
# ==============================================================================
class BearishSignalType(Enum):
    """Types of bearish signals"""
    OVERBOUGHT_REVERSAL = auto()
    TREND_BREAKDOWN = auto()
    RESISTANCE_REJECTION = auto()
    DISTRIBUTION_DAY = auto()
    FAILED_BREAKOUT = auto()
    NEGATIVE_DIVERGENCE = auto()

class BearishStrength(Enum):
    """Bearish trend strength classification"""
    WEAK = auto()
    MODERATE = auto()
    STRONG = auto()
    VERY_STRONG = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class BearishAnalysis:
    """Bearish market analysis"""
    trend_strength: BearishStrength
    trend_score: float  # Negative for bearish
    resistance_levels: List[float]
    nearest_resistance: float
    distance_to_resistance: float
    rsi: float
    volume_ratio: float
    momentum: float  # Negative for bearish
    bearish_signals: List[BearishSignalType]
    distribution_days: int
    divergence_detected: bool
    confidence: float
    entry_score: float

@dataclass
class ResistanceTest:
    """Resistance level test information"""
    level: float
    test_date: datetime
    rejection_strength: float  # 0-1 scale
    volume_on_test: float
    failed_breakout: bool

# ==============================================================================
# BEAR CALL SPREAD STRATEGY CLASS
# ==============================================================================
class BearCallSpreadStrategy(CreditSpreadStrategy):
    """
    Bear call spread strategy implementation.
    
    Specializes the credit spread base class for bearish directional trades
    using call spreads with enhanced resistance analysis and distribution detection.
    """
    
    def __init__(self, event_manager: EventManager, risk_profile: RiskProfile,
                 config: Dict[str, Any]):
        """Initialize bear call spread strategy"""
        # Override config for bear calls only
        config['use_bull_puts'] = False
        config['use_bear_calls'] = True
        
        super().__init__(event_manager, risk_profile, config)
        
        # Update strategy name
        self.name = "BearCallSpread"
        
        # Additional components
        self.trend_detector = TrendDetector()
        self.price_action = PriceActionAnalyzer()
        self.greeks_calculator = GreeksCalculator()
        
        # Bear call specific configuration
        self.min_bearish_strength = config.get('min_bearish_strength', MIN_BEARISH_STRENGTH)
        self.profit_target = config.get('profit_target', PROFIT_TARGET)
        self.stop_loss = config.get('stop_loss', STOP_LOSS)
        self.enable_delta_hedging = config.get('enable_delta_hedging', True)
        
        # Delta hedging tracking (opposite of bull puts)
        self.active_hedges: Dict[str, Any] = {}
        self.portfolio_delta = 0.0
        
        # Enhanced bearish analysis
        self.bearish_analysis: Optional[BearishAnalysis] = None
        self.resistance_tests: List[ResistanceTest] = []
        self.distribution_day_count = 0
        self.last_distribution_check = None
        
        # Performance tracking
        self.bear_call_metrics = {
            'total_spreads': 0,
            'winning_spreads': 0,
            'avg_credit': 0.0,
            'avg_days_held': 0.0,
            'resistance_rejections': 0,
            'trend_breakdowns': 0,
            'distribution_trades': 0,
            'hedged_positions': 0,
            'failed_breakout_trades': 0
        }
        
        self.logger.info("BearCallSpreadStrategy initialized with enhanced bearish analysis")
    
    # ==========================================================================
    # OVERRIDDEN METHODS
    # ==========================================================================
    
    def generate_signals(self, market_data: pd.DataFrame) -> List[TradingSignal]:
        """Generate bear call spread signals with enhanced analysis"""
        signals = []
        
        try:
            # Perform bearish analysis
            self._analyze_bearish_conditions(market_data)
            
            # Check distribution days
            self._check_distribution_days(market_data)
            
            # Check if we should open bear calls
            if not self._should_open_bear_call_enhanced():
                return signals
            
            # Call parent method to check basic conditions
            parent_signals = super().generate_signals(market_data)
            
            # Filter and enhance signals
            for signal in parent_signals:
                if self._validate_bearish_signal(signal):
                    enhanced_signal = self._enhance_bear_call_signal(signal)
                    if enhanced_signal:
                        signals.append(enhanced_signal)
            
            # Check for delta hedging needs
            self._check_delta_hedging_needs()
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'generate_signals',
                'market_data_shape': market_data.shape
            })
        
        return signals
    
    def should_exit_position(self, position: StrategyPosition,
                           market_data: pd.DataFrame) -> Tuple[bool, str]:
        """Enhanced exit logic for bear calls"""
        try:
            # First check parent exit conditions
            should_exit, reason = super().should_exit_position(position, market_data)
            if should_exit:
                return should_exit, reason
            
            # Get spread position
            spread = self.active_spreads.get(position.position_id)
            if not spread:
                return False, ""
            
            # Check if trend has reversed to bullish
            if self.bearish_analysis and self.bearish_analysis.trend_score > 0.3:
                return True, "Trend reversal to bullish detected"
            
            # Check if resistance has been broken
            current_price = market_data['close'].iloc[-1]
            if self.bearish_analysis and self.bearish_analysis.nearest_resistance > 0:
                if current_price > self.bearish_analysis.nearest_resistance * 1.01:
                    return True, "Resistance level broken"
            
            # Check delta exposure
            if spread.net_delta > 50:  # Too positive
                return True, "Delta exposure too high"
            
            # Check for strong bullish volume
            volume_ratio = market_data['volume'].iloc[-1] / market_data['volume'].rolling(20).mean().iloc[-1]
            if current_price > market_data['close'].iloc[-2] and volume_ratio > 2:
                return True, "Strong bullish volume detected"
            
            # Check profit target (tighter for bear calls)
            profit_pct = spread.profit_percentage
            if profit_pct >= self.profit_target:
                return True, f"Profit target reached: {profit_pct:.1%}"
            
            return False, ""
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'should_exit_position',
                'position_id': position.position_id
            })
            return False, ""
    
    # ==========================================================================
    # BEARISH ANALYSIS METHODS
    # ==========================================================================
    
    def _analyze_bearish_conditions(self, market_data: pd.DataFrame) -> None:
        """Perform comprehensive bearish market analysis"""
        try:
            close_prices = market_data['close']
            current_price = close_prices.iloc[-1]
            
            # Trend analysis (looking for negative trend)
            trend_data = self.trend_detector.detect_trend(market_data)
            trend_score = -abs(trend_data.get('strength', 0)) if trend_data.get('direction') == 'down' else trend_data.get('strength', 0)
            
            # Classify bearish strength
            if trend_score <= -0.7:
                trend_strength = BearishStrength.VERY_STRONG
            elif trend_score <= -0.5:
                trend_strength = BearishStrength.STRONG
            elif trend_score <= -0.3:
                trend_strength = BearishStrength.MODERATE
            else:
                trend_strength = BearishStrength.WEAK
            
            # Get resistance levels from parent
            resistance_levels = self.support_resistance.get('resistance', [])
            nearest_resistance = resistance_levels[0] if resistance_levels else current_price * 1.03
            distance_to_resistance = (nearest_resistance - current_price) / current_price
            
            # Technical indicators
            rsi = self.tech_indicators.calculate_rsi(close_prices, 14).iloc[-1]
            
            # Volume analysis (looking for distribution)
            volume = market_data['volume']
            avg_volume = volume.rolling(20).mean().iloc[-1]
            current_volume = volume.iloc[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Check if down day with high volume
            if close_prices.iloc[-1] < close_prices.iloc[-2] and volume_ratio > DISTRIBUTION_VOLUME_INCREASE:
                volume_ratio *= 1.5  # Emphasize distribution
            
            # Momentum (negative for bearish)
            momentum = close_prices.pct_change(10).iloc[-1]  # 10-period momentum
            
            # Identify bearish signals
            bearish_signals = []
            
            if rsi > 65:
                bearish_signals.append(BearishSignalType.OVERBOUGHT_REVERSAL)
            
            if trend_score < -0.5 and momentum < 0:
                bearish_signals.append(BearishSignalType.TREND_BREAKDOWN)
            
            if distance_to_resistance < 0.02:  # Within 2% of resistance
                bearish_signals.append(BearishSignalType.RESISTANCE_REJECTION)
            
            if self.distribution_day_count >= DISTRIBUTION_DAY_THRESHOLD:
                bearish_signals.append(BearishSignalType.DISTRIBUTION_DAY)
            
            # Check for failed breakout
            if self._check_failed_breakout(market_data):
                bearish_signals.append(BearishSignalType.FAILED_BREAKOUT)
            
            # Check for negative divergence
            divergence = self._check_negative_divergence(market_data)
            if divergence:
                bearish_signals.append(BearishSignalType.NEGATIVE_DIVERGENCE)
            
            # Calculate confidence
            confidence = 0.5  # Base confidence
            confidence += len(bearish_signals) * 0.08
            confidence += min(0.2, abs(trend_score) * 0.3) if trend_score < 0 else 0
            confidence = min(0.95, confidence)
            
            # Calculate entry score
            entry_score = 0
            entry_score += abs(trend_score) * 30 if trend_score < 0 else 0
            entry_score += max(0, (rsi - 50) / 50 * 20)  # Higher RSI better
            entry_score += min(20, distance_to_resistance * 1000)  # Distance from resistance
            entry_score += min(20, volume_ratio * 10) if momentum < 0 else 0
            entry_score += len(bearish_signals) * 10
            
            # Create analysis object
            self.bearish_analysis = BearishAnalysis(
                trend_strength=trend_strength,
                trend_score=trend_score,
                resistance_levels=resistance_levels,
                nearest_resistance=nearest_resistance,
                distance_to_resistance=distance_to_resistance,
                rsi=rsi,
                volume_ratio=volume_ratio,
                momentum=momentum,
                bearish_signals=bearish_signals,
                distribution_days=self.distribution_day_count,
                divergence_detected=divergence,
                confidence=confidence,
                entry_score=entry_score
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_analyze_bearish_conditions'})
    
    def _check_distribution_days(self, market_data: pd.DataFrame) -> None:
        """Check for distribution days (institutional selling)"""
        try:
            today = datetime.now().date()
            
            # Reset counter if new day
            if self.last_distribution_check != today:
                self.distribution_day_count = 0
                self.last_distribution_check = today
            
            # Look at last 10 days
            recent_data = market_data.tail(10)
            
            distribution_days = 0
            for i in range(1, len(recent_data)):
                close_change = recent_data['close'].iloc[i] / recent_data['close'].iloc[i-1] - 1
                volume_ratio = recent_data['volume'].iloc[i] / recent_data['volume'].rolling(20).mean().iloc[i]
                
                # Distribution day: down >0.5% on heavy volume
                if close_change < -0.005 and volume_ratio > DISTRIBUTION_VOLUME_INCREASE:
                    distribution_days += 1
            
            self.distribution_day_count = distribution_days
            
        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_check_distribution_days'})
    
    def _check_failed_breakout(self, market_data: pd.DataFrame) -> bool:
        """Check for failed breakout pattern"""
        try:
            if len(market_data) < 10:
                return False
            
            recent_high = market_data['high'].rolling(20).max()
            current_price = market_data['close'].iloc[-1]
            
            # Check if price broke above recent high but failed
            for i in range(-5, -1):
                if (market_data['high'].iloc[i] > recent_high.iloc[i-1] and 
                    market_data['close'].iloc[i] < recent_high.iloc[i-1]):
                    # Failed breakout detected
                    return True
            
            return False
            
        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_check_failed_breakout'})
            return False
    
    def _check_negative_divergence(self, market_data: pd.DataFrame) -> bool:
        """Check for negative RSI divergence"""
        try:
            if len(market_data) < 20:
                return False
            
            close_prices = market_data['close']
            rsi = self.tech_indicators.calculate_rsi(close_prices, 14)
            
            # Find recent peaks
            price_peaks = []
            rsi_peaks = []
            
            for i in range(5, len(close_prices) - 5):
                if (close_prices.iloc[i] > close_prices.iloc[i-2] and 
                    close_prices.iloc[i] > close_prices.iloc[i+2]):
                    price_peaks.append((i, close_prices.iloc[i]))
                    rsi_peaks.append((i, rsi.iloc[i]))
            
            # Check for divergence
            if len(price_peaks) >= 2:
                # Higher price high but lower RSI high
                if (price_peaks[-1][1] > price_peaks[-2][1] and 
                    rsi_peaks[-1][1] < rsi_peaks[-2][1]):
                    return True
            
            return False
            
        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_check_negative_divergence'})
            return False
    
    def _should_open_bear_call_enhanced(self) -> bool:
        """Enhanced check for bear call entry conditions"""
        if not self.bearish_analysis:
            return False
        
        # Check trend strength
        if self.bearish_analysis.trend_score > self.min_bearish_strength:
            self.logger.debug(f"Trend not bearish enough: {self.bearish_analysis.trend_score:.2f}")
            return False
        
        # Check RSI not oversold
        if self.bearish_analysis.rsi < MIN_RSI:
            self.logger.debug(f"RSI oversold: {self.bearish_analysis.rsi:.0f}")
            return False
        
        # Check volume confirmation
        if self.bearish_analysis.momentum >= 0 and self.bearish_analysis.volume_ratio < MIN_VOLUME_RATIO:
            self.logger.debug(f"Insufficient bearish volume: {self.bearish_analysis.volume_ratio:.2f}")
            return False
        
        # Check distance from resistance
        if self.bearish_analysis.distance_to_resistance < MIN_RESISTANCE_DISTANCE:
            self.logger.debug("Too close to resistance level")
            return False
        
        # Check volatility rank
        if self.volatility_rank > MAX_VOLATILITY_RANK:
            self.logger.debug(f"IV rank too high: {self.volatility_rank:.0f}")
            return False
        
        # Need at least one bearish signal
        if not self.bearish_analysis.bearish_signals:
            self.logger.debug("No bearish signals detected")
            return False
        
        # Check entry score
        if self.bearish_analysis.entry_score < 40:
            self.logger.debug(f"Entry score too low: {self.bearish_analysis.entry_score:.0f}")
            return False
        
        return True
    
    def _validate_bearish_signal(self, signal: TradingSignal) -> bool:
        """Validate signal is appropriate for bear call spread"""
        spread_data = signal.metadata.get('spread_data', {})
        
        # Ensure it's a bear call spread
        if spread_data.get('spread_type') != SpreadType.BEAR_CALL:
            return False
        
        # Additional bearish validation
        if self.bearish_analysis:
            if self.bearish_analysis.confidence < 0.6:
                return False
        
        return True
    
    def _enhance_bear_call_signal(self, signal: TradingSignal) -> Optional[TradingSignal]:
        """Enhance signal with bear call specific data"""
        try:
            # Add bearish analysis to metadata
            signal.metadata['bearish_analysis'] = {
                'trend_strength': self.bearish_analysis.trend_strength.name,
                'trend_score': self.bearish_analysis.trend_score,
                'resistance_distance': self.bearish_analysis.distance_to_resistance,
                'rsi': self.bearish_analysis.rsi,
                'momentum': self.bearish_analysis.momentum,
                'bearish_signals': [s.name for s in self.bearish_analysis.bearish_signals],
                'distribution_days': self.bearish_analysis.distribution_days,
                'divergence': self.bearish_analysis.divergence_detected,
                'confidence': self.bearish_analysis.confidence
            }
            
            # Adjust signal strength based on bearish analysis
            if self.bearish_analysis.entry_score >= 80:
                signal.strength = SignalStrength.VERY_STRONG
            elif self.bearish_analysis.entry_score >= 60:
                signal.strength = SignalStrength.STRONG
            elif self.bearish_analysis.entry_score >= 40:
                signal.strength = SignalStrength.MODERATE
            else:
                signal.strength = SignalStrength.WEAK
            
            # Update confidence
            signal.confidence = self.bearish_analysis.confidence
            
            return signal
            
        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_enhance_bear_call_signal'})
            return None
    
    # ==========================================================================
    # DELTA HEDGING METHODS
    # ==========================================================================
    
    def _check_delta_hedging_needs(self) -> None:
        """Check if delta hedging is needed for bear calls"""
        if not self.enable_delta_hedging:
            return
        
        try:
            # Calculate portfolio delta
            self._update_portfolio_delta()
            
            # Check if hedging needed (opposite of bull puts)
            if self.portfolio_delta > MAX_PORTFOLIO_DELTA:
                self.logger.info(f"Portfolio delta too positive: {self.portfolio_delta:.0f}")
                self._create_delta_hedge()
            
            # Check existing hedges
            self._manage_existing_hedges()
            
        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_check_delta_hedging_needs'})
    
    def _create_delta_hedge(self) -> Optional[Dict[str, Any]]:
        """Create delta hedge position for bear calls"""
        try:
            # Calculate hedge size needed
            delta_excess = self.portfolio_delta - MAX_PORTFOLIO_DELTA
            
            # For bear calls, hedge with long puts
            current_price = self.market_data['close'].iloc[-1] if hasattr(self, 'market_data') else 450
            
            hedge = {
                'hedge_id': str(uuid.uuid4()),
                'hedge_type': 'long_put',
                'strike': current_price - 5,  # 5 points OTM
                'quantity': int(delta_excess / 50),  # Assuming -0.5 delta per put
                'entry_time': datetime.now(),
                'cost': delta_excess * 2  # Simplified
            }
            
            self.active_hedges[hedge['hedge_id']] = hedge
            self.bear_call_metrics['hedged_positions'] += 1
            
            self.logger.info(f"Created delta hedge: {hedge['hedge_type']} x{hedge['quantity']}")
            return hedge
            
        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_create_delta_hedge'})
            return None
    
    # ==========================================================================
    # POSITION MANAGEMENT OVERRIDES
    # ==========================================================================
    
    def open_credit_spread(self, signal: TradingSignal) -> Optional[CreditSpread]:
        """Open bear call spread with enhanced tracking"""
        spread = super().open_credit_spread(signal)
        
        if spread:
            # Update bear call specific metrics
            self.bear_call_metrics['total_spreads'] += 1
            
            # Track signal type
            bearish_signals = signal.metadata.get('bearish_analysis', {}).get('bearish_signals', [])
            if BearishSignalType.RESISTANCE_REJECTION.name in bearish_signals:
                self.bear_call_metrics['resistance_rejections'] += 1
            elif BearishSignalType.TREND_BREAKDOWN.name in bearish_signals:
                self.bear_call_metrics['trend_breakdowns'] += 1
            elif BearishSignalType.DISTRIBUTION_DAY.name in bearish_signals:
                self.bear_call_metrics['distribution_trades'] += 1
            elif BearishSignalType.FAILED_BREAKOUT.name in bearish_signals:
                self.bear_call_metrics['failed_breakout_trades'] += 1
        
        return spread
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    
    def _update_portfolio_delta(self) -> None:
        """Update total portfolio delta"""
        total_delta = 0.0
        
        # Sum deltas from active spreads
        for spread in self.active_spreads.values():
            spread.update_greeks()
            total_delta += spread.net_delta * spread.quantity * SPY_CONTRACT_MULTIPLIER
        
        # Add deltas from hedges
        for hedge in self.active_hedges.values():
            if hedge['hedge_type'] == 'long_put':
                total_delta -= hedge['quantity'] * 50  # Simplified
        
        self.portfolio_delta = total_delta
    
    def _manage_existing_hedges(self) -> None:
        """Manage existing delta hedges"""
        hedges_to_close = []
        
        for hedge_id, hedge in self.active_hedges.items():
            # Check if hedge still needed
            if self.portfolio_delta < DELTA_HEDGE_THRESHOLD:
                hedges_to_close.append(hedge_id)
        
        # Close unneeded hedges
        for hedge_id in hedges_to_close:
            del self.active_hedges[hedge_id]
            self.logger.info(f"Closed hedge {hedge_id}")
    
    def get_strategy_summary(self) -> Dict[str, Any]:
        """Get comprehensive strategy summary"""
        # Get parent summary
        summary = super().get_strategy_summary()
        
        # Add bear call specific data
        summary['bear_call_analysis'] = {
            'trend_strength': self.bearish_analysis.trend_strength.name if self.bearish_analysis else 'UNKNOWN',
            'trend_score': self.bearish_analysis.trend_score if self.bearish_analysis else 0,
            'nearest_resistance': self.bearish_analysis.nearest_resistance if self.bearish_analysis else 0,
            'distribution_days': self.distribution_day_count,
            'portfolio_delta': self.portfolio_delta,
            'active_hedges': len(self.active_hedges)
        }
        
        summary['bear_call_metrics'] = self.bear_call_metrics.copy()
        
        return summary

# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":
    # Test bear call spread strategy
    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000,
        max_position_size=0.02,
        max_portfolio_risk=0.06,
        max_loss_per_trade=0.01
    )
    
    config = {
        'max_spreads': 5,
        'spread_width': 5.0,
        'target_premium': 1.0,
        'min_bearish_strength': -0.3,
        'enable_delta_hedging': True
    }
    
    strategy = BearCallSpreadStrategy(event_manager, risk_profile, config)
    strategy.start()
    
    # Create bearish market data
    dates = pd.date_range(end=datetime.now(), periods=100, freq='5min')
    base_price = 455
    
    # Downtrend with resistance tests
    trend = np.linspace(0, -10, 100)  # Downtrend
    resistance_tests = np.sin(np.linspace(0, 4*np.pi, 100)) * 2  # Oscillation
    noise = np.random.randn(100) * 0.5
    prices = base_price + trend + resistance_tests + noise
    
    # Ensure prices don't go above resistance
    resistance_level = 455
    prices = np.minimum(prices, resistance_level)
    
    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices + 0.1,
        'high': prices + abs(np.random.randn(100) * 0.3),
        'low': prices - abs(np.random.randn(100) * 0.3),
        'close': prices,
        'volume': np.random.randint(50000000, 150000000, 100)
    })
    
    # Add volume surge on down moves
    for i in range(1, len(market_data)):
        if market_data['close'].iloc[i] < market_data['close'].iloc[i-1]:
            market_data.loc[i, 'volume'] *= 1.5
    
    # Process market data
    signals = strategy.generate_signals(market_data)
    
    # Print results
    print(f"Strategy: {strategy.name}")
    
    if strategy.bearish_analysis:
        print(f"\nBearish Analysis:")
        print(f"Trend Strength: {strategy.bearish_analysis.trend_strength.name}")
        print(f"Trend Score: {strategy.bearish_analysis.trend_score:.2f}")
        print(f"RSI: {strategy.bearish_analysis.rsi:.0f}")
        print(f"Distance to Resistance: {strategy.bearish_analysis.distance_to_resistance:.2%}")
        print(f"Momentum: {strategy.bearish_analysis.momentum:.3f}")
        print(f"Distribution Days: {strategy.bearish_analysis.distribution_days}")
        print(f"Bearish Signals: {[s.name for s in strategy.bearish_analysis.bearish_signals]}")
        print(f"Confidence: {strategy.bearish_analysis.confidence:.2%}")
    
    print(f"\nSignals Generated: {len(signals)}")
    
    for signal in signals:
        spread_data = signal.metadata.get('spread_data', {})
        bearish_data = signal.metadata.get('bearish_analysis', {})
        
        print(f"\nBear Call Spread Signal:")
        print(f"Strength: {signal.strength.name}")
        print(f"Short Strike: ${spread_data.get('short_strike', 0)}")
        print(f"Long Strike: ${spread_data.get('long_strike', 0)}")
        print(f"Credit: ${spread_data.get('credit', 0):.2f}")
        print(f"Max Loss: ${spread_data.get('max_loss', 0):.2f}")
        print(f"Probability: {spread_data.get('probability_profit', 0):.2%}")
        print(f"Bearish Signals: {bearish_data.get('bearish_signals', [])}")
    
    # Get strategy summary
    summary = strategy.get_strategy_summary()
    print(f"\nStrategy Summary:")
    print(f"Portfolio Delta: {summary['bear_call_analysis']['portfolio_delta']:.0f}")
    print(f"Distribution Days: {summary['bear_call_analysis']['distribution_days']}")
    print(f"Total Spreads: {summary['bear_call_metrics']['total_spreads']}")
    print(f"Resistance Rejections: {summary['bear_call_metrics']['resistance_rejections']}")
    print(f"Failed Breakouts: {summary['bear_call_metrics']['failed_breakout_trades']}")
    
    strategy.stop()
    print("\nBearCallSpreadStrategy test completed!")