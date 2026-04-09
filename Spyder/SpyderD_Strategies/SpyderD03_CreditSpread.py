#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD03_CreditSpread.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta
from typing import Any
from dataclasses import dataclass, field
import uuid
from enum import Enum, auto

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (

    BaseStrategy, TradingSignal, SignalType, SignalStrength,
    StrategyPosition, EventManager, RiskProfile, Event, EventType
)
from Spyder.SpyderU_Utilities.SpyderU07_Constants import (
    CREDIT_SPREAD_PROFIT_TARGET,
    CREDIT_SPREAD_STOP_LOSS,
    OPTIMAL_ENTRY_START,
    OPTIMAL_ENTRY_END,
    SPY_CONTRACT_MULTIPLIER
)
from Spyder.SpyderU_Utilities.SpyderU13_TechnicalIndicators import TechnicalIndicators

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy parameters
MIN_PREMIUM_COLLECTED = 0.50  # Minimum credit to collect
MAX_SPREAD_WIDTH = 5.0  # Maximum spread width in dollars
MIN_PROBABILITY_PROFIT = 0.65  # Minimum probability of profit
MAX_DAYS_TO_EXPIRY = 45  # Maximum DTE
MIN_DAYS_TO_EXPIRY = 20  # Minimum DTE

# Delta targets
BULL_PUT_SHORT_DELTA = -0.30  # Short put delta target
BULL_PUT_LONG_DELTA = -0.15   # Long put delta target
BEAR_CALL_SHORT_DELTA = 0.30   # Short call delta target
BEAR_CALL_LONG_DELTA = 0.15    # Long call delta target

# Risk parameters
MAX_RISK_REWARD_RATIO = 3.0  # Maximum risk to reward ratio
MIN_CREDIT_TO_WIDTH_RATIO = 0.25  # Minimum credit/width ratio

# Technical indicators
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
VOLUME_THRESHOLD = 1.5  # Volume relative to average

# Position limits
MAX_CREDIT_SPREAD_POSITIONS = 5
POSITION_SIZE_PERCENT = 0.02  # 2% of capital per position

# ==============================================================================
# ENUMS
# ==============================================================================
class SpreadType(Enum):
    """Credit spread types"""
    BULL_PUT = auto()
    BEAR_CALL = auto()

class MarketCondition(Enum):
    """Market condition classification"""
    STRONGLY_BULLISH = auto()
    MODERATELY_BULLISH = auto()
    NEUTRAL = auto()
    MODERATELY_BEARISH = auto()
    STRONGLY_BEARISH = auto()

class SpreadState(Enum):
    """Credit spread position states"""
    PENDING = auto()
    ACTIVE = auto()
    THREATENED = auto()  # Near short strike
    ADJUSTING = auto()
    CLOSING = auto()
    CLOSED = auto()
    EXPIRED = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OptionLeg:
    """Single option leg"""
    symbol: str
    strike: float
    expiry: datetime
    option_type: str  # 'call' or 'put'
    position: str  # 'long' or 'short'
    quantity: int
    entry_price: float
    current_price: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    iv: float = 0.0

@dataclass
class CreditSpread:
    """Credit spread structure"""
    spread_id: str
    spread_type: SpreadType
    short_leg: OptionLeg
    long_leg: OptionLeg
    entry_time: datetime
    expiry: datetime
    quantity: int
    state: SpreadState

    # Pricing
    credit_received: float
    current_value: float = 0.0

    # P&L
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    # Risk metrics
    max_profit: float = 0.0
    max_loss: float = 0.0
    breakeven: float = 0.0
    probability_profit: float = 0.0

    # Greeks
    net_delta: float = 0.0
    net_gamma: float = 0.0
    net_theta: float = 0.0
    net_vega: float = 0.0

    # Management
    days_in_trade: int = 0
    exit_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def spread_width(self) -> float:
        """Width of the spread"""
        return abs(self.short_leg.strike - self.long_leg.strike)

    @property
    def credit_to_width_ratio(self) -> float:
        """Credit received as percentage of spread width"""
        return self.credit_received / self.spread_width if self.spread_width > 0 else 0

    @property
    def profit_percentage(self) -> float:
        """Current profit as percentage of max profit"""
        return self.unrealized_pnl / self.max_profit if self.max_profit > 0 else 0

    def update_greeks(self) -> None:
        """Update net Greeks"""
        self.net_delta = self.short_leg.delta + self.long_leg.delta
        self.net_gamma = self.short_leg.gamma + self.long_leg.gamma
        self.net_theta = self.short_leg.theta + self.long_leg.theta
        self.net_vega = self.short_leg.vega + self.long_leg.vega

    def update_pnl(self) -> None:
        """Update P&L calculations"""
        short_value = self.short_leg.current_price * self.quantity * SPY_CONTRACT_MULTIPLIER
        long_value = self.long_leg.current_price * self.quantity * SPY_CONTRACT_MULTIPLIER
        self.current_value = short_value - long_value
        self.unrealized_pnl = self.credit_received - self.current_value

@dataclass
class SpreadAnalysis:
    """Spread analysis results"""
    recommended_spreads: list[CreditSpread]
    market_condition: MarketCondition
    trend_strength: float
    volatility_rank: float
    support_levels: list[float]
    resistance_levels: list[float]
    entry_score: float

# ==============================================================================
# CREDIT SPREAD STRATEGY CLASS
# ==============================================================================
class CreditSpreadStrategy(BaseStrategy):
    """
    Credit spread strategy implementation.

    Implements bull put spreads and bear call spreads based on:
    - Market trend and momentum
    - Support/resistance levels
    - Volatility conditions
    - Technical indicators
    """

    def __init__(self, event_manager: EventManager, risk_profile: RiskProfile,
                 config: dict[str, Any]):
        """
        Initialize credit spread strategy.

        Args:
            event_manager: Event management system
            risk_profile: Risk management profile
            config: Strategy configuration
        """
        super().__init__("CreditSpread", event_manager, risk_profile, config)

        # Strategy configuration
        self.max_spreads = config.get('max_spreads', MAX_CREDIT_SPREAD_POSITIONS)
        self.spread_width = config.get('spread_width', MAX_SPREAD_WIDTH)
        self.target_premium = config.get('target_premium', MIN_PREMIUM_COLLECTED)
        self.use_bull_puts = config.get('use_bull_puts', True)
        self.use_bear_calls = config.get('use_bear_calls', True)

        # Technical analysis
        self.tech_indicators = TechnicalIndicators()

        # Position tracking
        self.active_spreads: dict[str, CreditSpread] = {}
        self.spread_history: list[CreditSpread] = []

        # Market analysis
        self.market_condition = MarketCondition.NEUTRAL
        self.trend_strength = 0.0
        self.volatility_rank = 0.0
        self.support_resistance: dict[str, list[float]] = {
            'support': [],
            'resistance': []
        }

        # Performance metrics
        self.spread_metrics = {
            'bull_put_count': 0,
            'bear_call_count': 0,
            'win_rate': 0.0,
            'avg_credit': 0.0,
            'avg_days_held': 0.0,
            'total_profit': 0.0
        }

        self.logger.info("CreditSpreadStrategy initialized")

    # ==========================================================================
    # REQUIRED ABSTRACT METHOD IMPLEMENTATIONS
    # ==========================================================================

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Generate credit spread trading signals"""
        signals = []

        try:
            # Update market analysis
            self._analyze_market_conditions(market_data)

            # Check if we can open new positions
            if len(self.active_spreads) >= self.max_spreads:
                return signals

            # Check entry time window
            current_time = datetime.now().time()
            if not (OPTIMAL_ENTRY_START <= current_time <= OPTIMAL_ENTRY_END):
                return signals

            # Get current price
            current_price = market_data['close'].iloc[-1]

            # Generate bull put spread signals
            if self.use_bull_puts and self._should_open_bull_put():
                bull_put_signal = self._generate_bull_put_signal(current_price, market_data)
                if bull_put_signal:
                    signals.append(bull_put_signal)

            # Generate bear call spread signals
            if self.use_bear_calls and self._should_open_bear_call():
                bear_call_signal = self._generate_bear_call_signal(current_price, market_data)
                if bear_call_signal:
                    signals.append(bear_call_signal)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'generate_signals',
                'market_data_shape': market_data.shape
            })

        return signals

    def validate_signal(self, signal: TradingSignal) -> bool:
        """Validate credit spread signal"""
        try:
            # Check basic signal validity
            if not signal.is_valid():
                return False

            # Check spread parameters
            spread_data = signal.metadata.get('spread_data')
            if not spread_data:
                return False

            # Validate strikes
            if spread_data['spread_type'] == SpreadType.BULL_PUT:
                if spread_data['short_strike'] <= spread_data['long_strike']:
                    return False
            else:  # BEAR_CALL
                if spread_data['short_strike'] >= spread_data['long_strike']:
                    return False

            # Validate premium
            if spread_data['credit'] < self.target_premium:
                return False

            # Validate probability of profit
            if spread_data['probability_profit'] < MIN_PROBABILITY_PROFIT:
                return False

            # Validate risk/reward
            risk_reward = spread_data['max_loss'] / spread_data['max_profit']
            return not risk_reward > MAX_RISK_REWARD_RATIO

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'validate_signal',
                'signal_id': signal.signal_id
            })
            return False

    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Calculate position size for credit spread"""
        try:
            # Get account value and max loss
            account_value = self.risk_profile.account_size
            max_loss = signal.metadata['spread_data']['max_loss']

            # Calculate contracts based on risk
            max_risk_amount = account_value * POSITION_SIZE_PERCENT
            contracts = int(max_risk_amount / (max_loss * SPY_CONTRACT_MULTIPLIER))

            # Apply limits
            contracts = max(1, min(contracts, 10))

            # Adjust for signal strength
            if signal.strength == SignalStrength.WEAK:
                contracts = max(1, contracts // 2)
            elif signal.strength == SignalStrength.VERY_STRONG:
                contracts = min(10, int(contracts * 1.5))

            return contracts

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'calculate_position_size',
                'signal_id': signal.signal_id
            })
            return 1

    def should_exit_position(self, position: StrategyPosition,
                           market_data: pd.DataFrame) -> tuple[bool, str]:
        """Determine if credit spread should be exited"""
        try:
            # Get spread position
            spread = self.active_spreads.get(position.position_id)
            if not spread:
                return False, ""

            # Update spread pricing
            self._update_spread_pricing(spread, market_data)

            # Check profit target
            profit_pct = spread.profit_percentage
            if profit_pct >= CREDIT_SPREAD_PROFIT_TARGET:
                return True, f"Profit target reached: {profit_pct:.1%}"

            # Check stop loss
            loss_pct = abs(spread.unrealized_pnl) / spread.max_loss
            if loss_pct >= CREDIT_SPREAD_STOP_LOSS:
                return True, f"Stop loss triggered: {loss_pct:.1%}"

            # Check days to expiry
            dte = (spread.expiry - datetime.now()).days
            if dte <= 5 and profit_pct > 0.25:
                return True, f"Near expiry with profit: {dte} DTE"

            # Check if short strike is threatened
            current_price = market_data['close'].iloc[-1]
            if spread.spread_type == SpreadType.BULL_PUT:
                if current_price <= spread.short_leg.strike * 1.02:
                    return True, "Short put strike threatened"
            else:  # BEAR_CALL
                if current_price >= spread.short_leg.strike * 0.98:
                    return True, "Short call strike threatened"

            return False, ""

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'should_exit_position',
                'position_id': position.position_id
            })
            return False, ""

    # ==========================================================================
    # MARKET ANALYSIS METHODS
    # ==========================================================================

    def _analyze_market_conditions(self, market_data: pd.DataFrame) -> None:
        """Analyze current market conditions"""
        try:
            # Calculate technical indicators
            close_prices = market_data['close']

            # RSI
            rsi = self.tech_indicators.calculate_rsi(close_prices, period=14)
            rsi.iloc[-1] if not rsi.empty else 50

            # Moving averages
            sma_20 = close_prices.rolling(20).mean()
            sma_50 = close_prices.rolling(50).mean()

            # Current price relative to MAs
            current_price = close_prices.iloc[-1]
            price_vs_sma20 = (current_price - sma_20.iloc[-1]) / sma_20.iloc[-1]
            (current_price - sma_50.iloc[-1]) / sma_50.iloc[-1]

            # Trend analysis
            if sma_20.iloc[-1] > sma_50.iloc[-1]:
                if price_vs_sma20 > 0.01:
                    self.market_condition = MarketCondition.STRONGLY_BULLISH
                    self.trend_strength = 0.8
                else:
                    self.market_condition = MarketCondition.MODERATELY_BULLISH
                    self.trend_strength = 0.6
            elif sma_20.iloc[-1] < sma_50.iloc[-1]:
                if price_vs_sma20 < -0.01:
                    self.market_condition = MarketCondition.STRONGLY_BEARISH
                    self.trend_strength = -0.8
                else:
                    self.market_condition = MarketCondition.MODERATELY_BEARISH
                    self.trend_strength = -0.6
            else:
                self.market_condition = MarketCondition.NEUTRAL
                self.trend_strength = 0.0

            # Support and resistance
            self._identify_support_resistance(market_data)

            # Volatility rank (simplified)
            returns = close_prices.pct_change().dropna()
            current_vol = returns.rolling(20).std().iloc[-1]
            vol_90d = returns.rolling(90).std()
            self.volatility_rank = (vol_90d <= current_vol).sum() / len(vol_90d) * 100

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_analyze_market_conditions'})

    def _identify_support_resistance(self, market_data: pd.DataFrame) -> None:
        """Identify support and resistance levels"""
        try:
            high_prices = market_data['high']
            low_prices = market_data['low']

            # Simple peak/trough detection
            window = 10

            # Resistance levels (peaks)
            resistance = []
            for i in range(window, len(high_prices) - window):
                if high_prices.iloc[i] == high_prices.iloc[i-window:i+window+1].max():
                    resistance.append(high_prices.iloc[i])

            # Support levels (troughs)
            support = []
            for i in range(window, len(low_prices) - window):
                if low_prices.iloc[i] == low_prices.iloc[i-window:i+window+1].min():
                    support.append(low_prices.iloc[i])

            # Keep only recent and significant levels
            current_price = market_data['close'].iloc[-1]

            self.support_resistance['resistance'] = sorted(
                [r for r in resistance if r > current_price * 0.98]
            )[:3]

            self.support_resistance['support'] = sorted(
                [s for s in support if s < current_price * 1.02],
                reverse=True
            )[:3]

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_identify_support_resistance'})

    # ==========================================================================
    # SIGNAL GENERATION METHODS
    # ==========================================================================

    def _should_open_bull_put(self) -> bool:
        """Check if conditions favor bull put spread"""
        return self.market_condition in [
            MarketCondition.MODERATELY_BULLISH,
            MarketCondition.STRONGLY_BULLISH,
            MarketCondition.NEUTRAL
        ] and self.volatility_rank > 30

    def _should_open_bear_call(self) -> bool:
        """Check if conditions favor bear call spread"""
        return self.market_condition in [
            MarketCondition.MODERATELY_BEARISH,
            MarketCondition.STRONGLY_BEARISH,
            MarketCondition.NEUTRAL
        ] and self.volatility_rank > 30

    def _generate_bull_put_signal(self, current_price: float,
                                 market_data: pd.DataFrame) -> TradingSignal | None:
        """Generate bull put spread signal"""
        try:
            # Find support level for short strike
            support_levels = self.support_resistance.get('support', [])
            if not support_levels:
                short_strike = current_price * 0.98  # 2% below current
            else:
                short_strike = support_levels[0] * 0.99  # Just below support

            # Round to nearest valid strike
            short_strike = round(short_strike)
            long_strike = short_strike - self.spread_width

            # Calculate spread metrics
            spread_data = self._calculate_spread_metrics(
                SpreadType.BULL_PUT,
                short_strike,
                long_strike,
                current_price,
                30  # DTE
            )

            if not spread_data:
                return None

            # Create signal
            signal = TradingSignal(
                signal_id=str(uuid.uuid4()),
                signal_type=SignalType.BUY,
                symbol='SPY',
                strength=self._calculate_signal_strength(spread_data),
                confidence=spread_data['probability_profit'],
                entry_price=current_price,
                stop_loss=0,  # Managed differently for spreads
                take_profit=0,  # Managed differently for spreads
                position_size=1,  # Will be calculated later
                timestamp=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=5),
                metadata={
                    'strategy': 'credit_spread',
                    'spread_data': spread_data
                }
            )

            return signal

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_generate_bull_put_signal'})
            return None

    def _generate_bear_call_signal(self, current_price: float,
                                  market_data: pd.DataFrame) -> TradingSignal | None:
        """Generate bear call spread signal"""
        try:
            # Find resistance level for short strike
            resistance_levels = self.support_resistance.get('resistance', [])
            if not resistance_levels:
                short_strike = current_price * 1.02  # 2% above current
            else:
                short_strike = resistance_levels[0] * 1.01  # Just above resistance

            # Round to nearest valid strike
            short_strike = round(short_strike)
            long_strike = short_strike + self.spread_width

            # Calculate spread metrics
            spread_data = self._calculate_spread_metrics(
                SpreadType.BEAR_CALL,
                short_strike,
                long_strike,
                current_price,
                30  # DTE
            )

            if not spread_data:
                return None

            # Create signal
            signal = TradingSignal(
                signal_id=str(uuid.uuid4()),
                signal_type=SignalType.BUY,
                symbol='SPY',
                strength=self._calculate_signal_strength(spread_data),
                confidence=spread_data['probability_profit'],
                entry_price=current_price,
                stop_loss=0,  # Managed differently for spreads
                take_profit=0,  # Managed differently for spreads
                position_size=1,  # Will be calculated later
                timestamp=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=5),
                metadata={
                    'strategy': 'credit_spread',
                    'spread_data': spread_data
                }
            )

            return signal

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_generate_bear_call_signal'})
            return None

    def _calculate_spread_metrics(self, spread_type: SpreadType,
                                 short_strike: float, long_strike: float,
                                 current_price: float, dte: int) -> dict[str, Any] | None:
        """Calculate credit spread metrics"""
        try:
            # Simplified calculation - in production would use actual option prices
            spread_width = abs(short_strike - long_strike)

            # Estimate credit based on delta and time
            if spread_type == SpreadType.BULL_PUT:
                distance_pct = (current_price - short_strike) / current_price
                credit = spread_width * 0.3 * (1 + distance_pct)  # Simplified
                breakeven = short_strike - credit
                probability_profit = 0.65 + distance_pct * 10  # Simplified
            else:  # BEAR_CALL
                distance_pct = (short_strike - current_price) / current_price
                credit = spread_width * 0.3 * (1 + distance_pct)  # Simplified
                breakeven = short_strike + credit
                probability_profit = 0.65 + distance_pct * 10  # Simplified

            # Ensure reasonable values
            credit = min(credit, spread_width * 0.4)
            probability_profit = min(0.85, max(0.5, probability_profit))

            return {
                'spread_type': spread_type,
                'short_strike': short_strike,
                'long_strike': long_strike,
                'spread_width': spread_width,
                'credit': credit,
                'max_profit': credit,
                'max_loss': spread_width - credit,
                'breakeven': breakeven,
                'probability_profit': probability_profit,
                'dte': dte,
                'credit_to_width': credit / spread_width
            }

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_calculate_spread_metrics'})
            return None

    def _calculate_signal_strength(self, spread_data: dict[str, Any]) -> SignalStrength:
        """Calculate signal strength based on spread metrics"""
        score = 0

        # Credit to width ratio
        if spread_data['credit_to_width'] >= 0.35:
            score += 30
        elif spread_data['credit_to_width'] >= 0.30:
            score += 20
        elif spread_data['credit_to_width'] >= 0.25:
            score += 10

        # Probability of profit
        if spread_data['probability_profit'] >= 0.75:
            score += 30
        elif spread_data['probability_profit'] >= 0.70:
            score += 20
        elif spread_data['probability_profit'] >= 0.65:
            score += 10

        # Market condition alignment
        if self.market_condition in [MarketCondition.MODERATELY_BULLISH, MarketCondition.MODERATELY_BEARISH]:
            score += 20
        elif self.market_condition == MarketCondition.NEUTRAL:
            score += 10

        # Volatility rank
        if self.volatility_rank >= 50:
            score += 20
        elif self.volatility_rank >= 40:
            score += 10

        # Convert score to strength
        if score >= 80:
            return SignalStrength.VERY_STRONG
        elif score >= 60:
            return SignalStrength.STRONG
        elif score >= 40:
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK

    # ==========================================================================
    # POSITION MANAGEMENT METHODS
    # ==========================================================================

    def open_credit_spread(self, signal: TradingSignal) -> CreditSpread | None:
        """Open a new credit spread position"""
        try:
            spread_data = signal.metadata['spread_data']

            # Create option legs
            if spread_data['spread_type'] == SpreadType.BULL_PUT:
                short_leg = OptionLeg(
                    symbol=f"SPY_P_{spread_data['short_strike']}",
                    strike=spread_data['short_strike'],
                    expiry=datetime.now() + timedelta(days=spread_data['dte']),
                    option_type='put',
                    position='short',
                    quantity=signal.position_size,
                    entry_price=1.5  # Placeholder
                )
                long_leg = OptionLeg(
                    symbol=f"SPY_P_{spread_data['long_strike']}",
                    strike=spread_data['long_strike'],
                    expiry=datetime.now() + timedelta(days=spread_data['dte']),
                    option_type='put',
                    position='long',
                    quantity=signal.position_size,
                    entry_price=0.5  # Placeholder
                )
            else:  # BEAR_CALL
                short_leg = OptionLeg(
                    symbol=f"SPY_C_{spread_data['short_strike']}",
                    strike=spread_data['short_strike'],
                    expiry=datetime.now() + timedelta(days=spread_data['dte']),
                    option_type='call',
                    position='short',
                    quantity=signal.position_size,
                    entry_price=1.5  # Placeholder
                )
                long_leg = OptionLeg(
                    symbol=f"SPY_C_{spread_data['long_strike']}",
                    strike=spread_data['long_strike'],
                    expiry=datetime.now() + timedelta(days=spread_data['dte']),
                    option_type='call',
                    position='long',
                    quantity=signal.position_size,
                    entry_price=0.5  # Placeholder
                )

            # Create spread position
            spread = CreditSpread(
                spread_id=str(uuid.uuid4()),
                spread_type=spread_data['spread_type'],
                short_leg=short_leg,
                long_leg=long_leg,
                entry_time=datetime.now(),
                expiry=short_leg.expiry,
                quantity=signal.position_size,
                state=SpreadState.ACTIVE,
                credit_received=spread_data['credit'] * signal.position_size * SPY_CONTRACT_MULTIPLIER,
                max_profit=spread_data['max_profit'] * signal.position_size * SPY_CONTRACT_MULTIPLIER,
                max_loss=spread_data['max_loss'] * signal.position_size * SPY_CONTRACT_MULTIPLIER,
                breakeven=spread_data['breakeven'],
                probability_profit=spread_data['probability_profit']
            )

            # Add to tracking
            self.active_spreads[spread.spread_id] = spread

            # Update metrics
            if spread.spread_type == SpreadType.BULL_PUT:
                self.spread_metrics['bull_put_count'] += 1
            else:
                self.spread_metrics['bear_call_count'] += 1

            # Publish event
            self.event_manager.publish(Event.create(
                EventType.POSITION_OPENED,
                self.name,
                {
                    'spread_id': spread.spread_id,
                    'spread_type': spread.spread_type.name,
                    'credit': spread.credit_received,
                    'max_profit': spread.max_profit,
                    'max_loss': spread.max_loss
                }
            ))

            self.logger.info("Opened %s spread: %s", spread.spread_type.name, spread.spread_id)
            return spread

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'open_credit_spread',
                'signal_id': signal.signal_id
            })
            return None

    def _update_spread_pricing(self, spread: CreditSpread, market_data: pd.DataFrame) -> None:
        """Update spread pricing and Greeks"""
        try:
            # In production, would fetch actual option prices
            # For now, simulate based on market movement
            current_price = market_data['close'].iloc[-1]

            # Simple P&L calculation based on price movement
            if spread.spread_type == SpreadType.BULL_PUT:
                # Bull put profits if price stays above short strike
                if current_price > spread.short_leg.strike:
                    # Time decay in our favor
                    days_held = (datetime.now() - spread.entry_time).days
                    time_decay_pct = min(0.9, days_held / 30)
                    spread.unrealized_pnl = spread.max_profit * time_decay_pct
                else:
                    # Price moved against us
                    breach_amount = spread.short_leg.strike - current_price
                    loss_pct = breach_amount / spread.spread_width
                    spread.unrealized_pnl = -spread.max_loss * min(1.0, loss_pct)

            else:  # BEAR_CALL
                # Bear call profits if price stays below short strike
                if current_price < spread.short_leg.strike:
                    # Time decay in our favor
                    days_held = (datetime.now() - spread.entry_time).days
                    time_decay_pct = min(0.9, days_held / 30)
                    spread.unrealized_pnl = spread.max_profit * time_decay_pct
                else:
                    # Price moved against us
                    breach_amount = current_price - spread.short_leg.strike
                    loss_pct = breach_amount / spread.spread_width
                    spread.unrealized_pnl = -spread.max_loss * min(1.0, loss_pct)

            # Update state if threatened
            if spread.unrealized_pnl < -spread.max_loss * 0.5:
                spread.state = SpreadState.THREATENED

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_spread_pricing',
                'spread_id': spread.spread_id
            })

    def close_credit_spread(self, spread_id: str, reason: str) -> bool:
        """Close a credit spread position"""
        try:
            spread = self.active_spreads.get(spread_id)
            if not spread:
                return False

            # Update final P&L
            spread.realized_pnl = spread.unrealized_pnl
            spread.state = SpreadState.CLOSED
            spread.exit_reason = reason
            spread.days_in_trade = (datetime.now() - spread.entry_time).days

            # Move to history
            self.spread_history.append(spread)
            del self.active_spreads[spread_id]

            # Update metrics
            self.spread_metrics['total_profit'] += spread.realized_pnl
            if spread.realized_pnl > 0:
                wins = sum(1 for s in self.spread_history if s.realized_pnl > 0)
                self.spread_metrics['win_rate'] = wins / len(self.spread_history)

            total_days = sum(s.days_in_trade for s in self.spread_history)
            self.spread_metrics['avg_days_held'] = total_days / len(self.spread_history)

            total_credit = sum(s.credit_received for s in self.spread_history)
            self.spread_metrics['avg_credit'] = total_credit / len(self.spread_history)

            # Publish event
            self.event_manager.publish(Event.create(
                EventType.POSITION_CLOSED,
                self.name,
                {
                    'spread_id': spread_id,
                    'realized_pnl': spread.realized_pnl,
                    'exit_reason': reason
                }
            ))

            self.logger.info(f"Closed spread {spread_id}: PnL ${spread.realized_pnl:.2f}")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'close_credit_spread',
                'spread_id': spread_id
            })
            return False

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def get_strategy_summary(self) -> dict[str, Any]:
        """Get comprehensive strategy summary"""
        active_bull_puts = sum(1 for s in self.active_spreads.values()
                              if s.spread_type == SpreadType.BULL_PUT)
        active_bear_calls = sum(1 for s in self.active_spreads.values()
                               if s.spread_type == SpreadType.BEAR_CALL)

        total_credit = sum(s.credit_received for s in self.active_spreads.values())
        total_risk = sum(s.max_loss for s in self.active_spreads.values())

        return {
            'strategy': 'CreditSpread',
            'state': self.state,
            'market_condition': self.market_condition.name,
            'trend_strength': self.trend_strength,
            'volatility_rank': self.volatility_rank,
            'active_positions': {
                'bull_puts': active_bull_puts,
                'bear_calls': active_bear_calls,
                'total': len(self.active_spreads)
            },
            'exposure': {
                'total_credit': total_credit,
                'total_risk': total_risk,
                'net_credit': total_credit - sum(s.unrealized_pnl for s in self.active_spreads.values())
            },
            'performance': self.spread_metrics,
            'support_resistance': self.support_resistance
        }

# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":
    # Test credit spread strategy
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    from SpyderE_Risk.SpyderE01_RiskManager import RiskProfile

    # Initialize components
    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000,
        max_position_size=0.02,
        max_portfolio_risk=0.06,
        max_loss_per_trade=0.01
    )

    # Create strategy
    config = {
        'max_spreads': 3,
        'spread_width': 5.0,
        'target_premium': 1.0,
        'use_bull_puts': True,
        'use_bear_calls': True
    }

    strategy = CreditSpreadStrategy(event_manager, risk_profile, config)

    # Start strategy
    strategy.start()

    # Create sample market data
    dates = pd.date_range(end=datetime.now(), periods=100, freq='5min')
    base_price = 450  # SPY price
    trend = np.linspace(0, 5, 100)  # Slight uptrend
    noise = np.random.randn(100) * 2
    prices = base_price + trend + noise

    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices + np.random.randn(100) * 0.5,
        'high': prices + abs(np.random.randn(100)),
        'low': prices - abs(np.random.randn(100)),
        'close': prices,
        'volume': np.random.randint(50000000, 150000000, 100)
    })

    # Process market data
    signals = strategy.generate_signals(market_data)

    # Print results

    for signal in signals:
        spread_data = signal.metadata.get('spread_data', {})

    # Get strategy summary
    summary = strategy.get_strategy_summary()

    # Stop strategy
    strategy.stop()

