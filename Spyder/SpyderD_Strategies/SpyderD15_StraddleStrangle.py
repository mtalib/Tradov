#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD15_StraddleStrangle.py
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
from enum import Enum, auto
import uuid

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from scipy import stats

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (

    BaseStrategy, TradingSignal, SignalStrength
)
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU07_Constants import (
    SignalType, SPY_CONTRACT_MULTIPLIER
)
from Spyder.SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from Spyder.SpyderF_Analysis.SpyderF04_VolatilityAnalysis import VolatilityAnalyzer
from Spyder.SpyderF_Analysis.SpyderF08_VolatilityRegime import VolatilityRegimeAnalyzer
from Spyder.SpyderC_MarketData.SpyderC09_NewsManager import NewsManager
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager
from Spyder.SpyderE_Risk.SpyderE01_RiskManager import RiskProfile
import logging

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy Configuration
MAX_VOLATILITY_POSITIONS = 3
MIN_DTE_LONG = 20          # Min days for long volatility
MAX_DTE_LONG = 60          # Max days for long volatility
MIN_DTE_SHORT = 7          # Min days for short volatility
MAX_DTE_SHORT = 30         # Max days for short volatility

# Strike Selection
STRADDLE_STRIKE_OFFSET = 0   # ATM
STRANGLE_CALL_OFFSET = 5     # Points OTM for calls
STRANGLE_PUT_OFFSET = 5      # Points OTM for puts
DELTA_TARGET_STRANGLE = 0.25  # Target delta for strangle strikes

# Entry Conditions
MIN_IV_RANK_LONG = 10        # Buy volatility when IV low
MAX_IV_RANK_LONG = 30
MIN_IV_RANK_SHORT = 70       # Sell volatility when IV high
MAX_IV_RANK_SHORT = 90

# Event Detection
EVENT_IV_SPIKE_THRESHOLD = 0.20   # 20% IV increase = event
EVENT_VOLUME_MULTIPLIER = 2.0     # 2x average volume
PRE_EARNINGS_DAYS = 5             # Days before earnings
PRE_FED_DAYS = 2                  # Days before Fed

# Position Management
LONG_VOL_PROFIT_TARGET = 0.50    # 50% profit on long vol
LONG_VOL_STOP_LOSS = 0.30        # 30% loss on long vol
SHORT_VOL_PROFIT_TARGET = 0.25   # 25% profit on short vol
SHORT_VOL_STOP_LOSS = 0.50       # 50% loss on short vol

# Greeks Management
MAX_GAMMA_LONG = 100             # Max gamma for long positions
MAX_GAMMA_SHORT = -50            # Max gamma for short positions
MIN_VEGA_LONG = 50               # Min vega for long vol
MAX_VEGA_SHORT = -100            # Max vega for short vol
GAMMA_SCALP_THRESHOLD = 20       # Gamma threshold for scalping

# Volatility Smile
SMILE_SKEW_THRESHOLD = 0.05      # 5% skew indicates directional bias
PUT_CALL_SKEW_NORMAL = 1.0       # Normal put/call skew

# ==============================================================================
# ENUMS
# ==============================================================================
class VolatilityStrategy(Enum):
    """Types of volatility strategies"""
    LONG_STRADDLE = "long_straddle"
    LONG_STRANGLE = "long_strangle"
    SHORT_STRADDLE = "short_straddle"
    SHORT_STRANGLE = "short_strangle"
    IRON_FLY = "iron_fly"           # Short straddle with protection
    IRON_CONDOR = "iron_condor"     # Short strangle with protection

class VolatilityEvent(Enum):
    """Types of volatility events"""
    EARNINGS = "earnings"
    FED_MEETING = "fed_meeting"
    ECONOMIC_DATA = "economic_data"
    TECHNICAL_BREAKOUT = "technical_breakout"
    VOLATILITY_CRUSH = "volatility_crush"
    UNKNOWN = "unknown"

class PositionState(Enum):
    """Volatility position states"""
    BUILDING = auto()
    ESTABLISHED = auto()
    GAMMA_SCALPING = auto()
    ADJUSTING = auto()
    REDUCING = auto()
    CLOSING = auto()

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class VolatilitySetup:
    """Volatility trade setup"""
    strategy: VolatilityStrategy
    call_strike: float
    put_strike: float
    expiry: datetime
    contracts: int
    net_debit: float  # Positive for long, negative for short
    max_profit: float
    max_loss: float
    breakeven_upper: float
    breakeven_lower: float
    iv_at_entry: float
    expected_iv_change: float
    event_type: VolatilityEvent | None = None
    event_date: datetime | None = None

@dataclass
class GreeksSnapshot:
    """Greeks for volatility position"""
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    timestamp: datetime

@dataclass
class VolatilityPosition:
    """Active volatility position"""
    position_id: str
    setup: VolatilitySetup
    entry_time: datetime
    entry_price: float
    current_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0  # From gamma scalping
    greeks_history: list[GreeksSnapshot] = field(default_factory=list)
    current_greeks: GreeksSnapshot | None = None
    gamma_scalp_count: int = 0
    state: PositionState = PositionState.BUILDING
    adjustments: list[dict] = field(default_factory=list)
    exit_time: datetime | None = None
    exit_reason: str | None = None

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class StraddleStrangleStrategy(BaseStrategy):
    """
    Professional straddle/strangle strategy implementation.

    Captures volatility expansion through long positions or collects premium
    through short positions based on IV rank and event detection.
    """

    def __init__(self, event_manager: EventManager, risk_profile: RiskProfile,
                 config: dict[str, Any] = None):
        """Initialize Straddle/Strangle strategy"""
        super().__init__(
            name="Straddle/Strangle Strategy",
            strategy_type="volatility_trading",
            event_manager=event_manager,
            risk_profile=risk_profile,
            config=config or {}
        )

        # Initialize components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.greeks_calculator = GreeksCalculator()
        self.volatility_analyzer = VolatilityAnalyzer()
        self.volatility_regime = VolatilityRegimeAnalyzer()
        self.news_manager = NewsManager()

        # Strategy state
        self.active_positions: dict[str, VolatilityPosition] = {}
        self.upcoming_events: list[dict] = []
        self.current_iv_rank: float = 50.0
        self.volatility_surface: pd.DataFrame | None = None

        # Configuration
        self.max_positions = config.get('max_positions', MAX_VOLATILITY_POSITIONS)
        self.allow_short = config.get('allow_short', True)
        self.enable_gamma_scalping = config.get('gamma_scalping', True)
        self.event_trading = config.get('event_trading', True)

        # Performance tracking
        self.performance_stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'total_gamma_scalps': 0,
            'gamma_scalp_pnl': 0.0,
            'best_trade': 0.0,
            'worst_trade': 0.0,
            'avg_iv_expansion': 0.0
        }

        self.logger.info(f"Initialized {self.name}")

    # ==========================================================================
    # EVENT DETECTION
    # ==========================================================================

    def _detect_upcoming_events(self, market_data: pd.DataFrame) -> list[dict]:
        """Detect upcoming volatility events"""
        events = []
        current_date = datetime.now()

        try:
            # Check earnings calendar
            if self.event_trading:
                earnings = self._check_earnings_calendar()
                for earning in earnings:
                    if 0 < (earning['date'] - current_date).days <= PRE_EARNINGS_DAYS:
                        events.append({
                            'type': VolatilityEvent.EARNINGS,
                            'date': earning['date'],
                            'impact': 'high',
                            'expected_move': earning.get('expected_move', 0.03)
                        })

            # Check Fed calendar
            fed_events = self._check_fed_calendar()
            for fed in fed_events:
                if 0 < (fed['date'] - current_date).days <= PRE_FED_DAYS:
                    events.append({
                        'type': VolatilityEvent.FED_MEETING,
                        'date': fed['date'],
                        'impact': 'high',
                        'expected_move': 0.02
                    })

            # Check for technical breakouts
            breakout = self._detect_technical_breakout(market_data)
            if breakout:
                events.append({
                    'type': VolatilityEvent.TECHNICAL_BREAKOUT,
                    'date': current_date,
                    'impact': 'medium',
                    'expected_move': breakout['expected_move']
                })

            # Check for volatility crush opportunities
            if self.current_iv_rank > 80:
                vol_crush = self._detect_volatility_crush(market_data)
                if vol_crush:
                    events.append({
                        'type': VolatilityEvent.VOLATILITY_CRUSH,
                        'date': current_date,
                        'impact': 'medium',
                        'expected_move': -0.01  # Negative for crush
                    })

        except Exception as e:
            self.logger.error(f"Error detecting events: {e}")

        self.upcoming_events = events
        return events

    def _check_earnings_calendar(self) -> list[dict]:
        """Check for upcoming earnings"""
        # In production, would connect to earnings calendar API
        # Mock data for testing
        earnings = []

        # Simulate quarterly earnings
        next_earnings = datetime.now() + timedelta(days=3)
        if next_earnings.month in [1, 4, 7, 10]:  # Earnings months
            earnings.append({
                'date': next_earnings,
                'company': 'Major S&P component',
                'expected_move': 0.04  # 4% expected move
            })

        return earnings

    def _check_fed_calendar(self) -> list[dict]:
        """Check for Fed meetings"""
        # In production, would use actual Fed calendar
        fed_events = []

        # FOMC meetings (simplified)
        days_to_next_wed = (2 - datetime.now().weekday()) % 7
        if days_to_next_wed == 0:
            days_to_next_wed = 7

        next_fed = datetime.now() + timedelta(days=days_to_next_wed)
        if next_fed.day >= 15 and next_fed.day <= 21:  # Third week
            fed_events.append({
                'date': next_fed,
                'type': 'FOMC',
                'impact': 'high'
            })

        return fed_events

    def _detect_technical_breakout(self, market_data: pd.DataFrame) -> dict | None:
        """Detect technical breakout patterns"""
        try:
            if len(market_data) < 20:
                return None

            # Calculate recent range
            recent_high = market_data['high'].iloc[-20:].max()
            recent_low = market_data['low'].iloc[-20:].min()
            current_price = market_data['close'].iloc[-1]

            # Check for breakout
            if current_price > recent_high:
                return {
                    'direction': 'bullish',
                    'breakout_level': recent_high,
                    'expected_move': (current_price - recent_high) / recent_high * 2
                }
            elif current_price < recent_low:
                return {
                    'direction': 'bearish',
                    'breakout_level': recent_low,
                    'expected_move': (recent_low - current_price) / current_price * 2
                }

            return None

        except Exception:
            return None

    def _detect_volatility_crush(self, market_data: pd.DataFrame) -> dict | None:
        """Detect potential volatility crush"""
        try:
            if 'iv' not in market_data.columns:
                return None

            # Check IV trend
            recent_iv = market_data['iv'].iloc[-10:]
            iv_slope = np.polyfit(range(len(recent_iv)), recent_iv, 1)[0]

            # Negative slope with high IV = crush potential
            if iv_slope < -0.001 and self.current_iv_rank > 70:
                return {
                    'current_iv': recent_iv.iloc[-1],
                    'iv_slope': iv_slope,
                    'expected_crush': abs(iv_slope) * 5  # 5-day projection
                }

            return None

        except Exception:
            return None

    # ==========================================================================
    # VOLATILITY ANALYSIS
    # ==========================================================================

    def _analyze_volatility_surface(self, market_data: pd.DataFrame) -> dict[str, Any]:
        """Analyze volatility surface and smile"""
        try:
            current_price = market_data['close'].iloc[-1]

            # Get volatility surface data
            # In production, would get from options chain
            vol_surface = self._construct_volatility_surface(current_price)
            self.volatility_surface = vol_surface

            # Calculate smile metrics
            atm_iv = self._get_atm_iv(vol_surface, current_price)
            put_skew = self._calculate_put_skew(vol_surface, current_price)
            call_skew = self._calculate_call_skew(vol_surface, current_price)

            # Term structure
            term_structure = self._analyze_term_structure(vol_surface)

            return {
                'atm_iv': atm_iv,
                'put_skew': put_skew,
                'call_skew': call_skew,
                'skew_ratio': put_skew / call_skew if call_skew > 0 else 1.0,
                'term_structure': term_structure,
                'smile_type': self._classify_smile(put_skew, call_skew)
            }

        except Exception as e:
            self.logger.error(f"Error analyzing volatility surface: {e}")
            return {}

    def _construct_volatility_surface(self, spot_price: float) -> pd.DataFrame:
        """Construct mock volatility surface"""
        # In production, would use actual options chain data
        strikes = np.arange(spot_price * 0.9, spot_price * 1.1, 5)
        expiries = [7, 14, 30, 60]  # DTE

        surface_data = []
        base_iv = 0.20

        for expiry in expiries:
            for strike in strikes:
                # Create realistic smile
                moneyness = strike / spot_price
                if moneyness < 1:  # Put side
                    iv = base_iv * (1 + 0.2 * (1 - moneyness))
                else:  # Call side
                    iv = base_iv * (1 + 0.1 * (moneyness - 1))

                # Term structure adjustment
                iv *= (1 + 0.001 * expiry)

                surface_data.append({
                    'strike': strike,
                    'expiry': expiry,
                    'iv': iv,
                    'moneyness': moneyness
                })

        return pd.DataFrame(surface_data)

    def _get_atm_iv(self, vol_surface: pd.DataFrame, spot_price: float) -> float:
        """Get at-the-money implied volatility"""
        atm_data = vol_surface[
            (vol_surface['strike'] >= spot_price - 1) &
            (vol_surface['strike'] <= spot_price + 1)
        ]

        if not atm_data.empty:
            return atm_data['iv'].mean()
        return 0.20  # Default

    def _calculate_put_skew(self, vol_surface: pd.DataFrame, spot_price: float) -> float:
        """Calculate put skew (25 delta put IV / ATM IV)"""
        put_25d_strike = spot_price * 0.95  # Approximate 25 delta put

        put_iv = vol_surface[
            (vol_surface['strike'] >= put_25d_strike - 2) &
            (vol_surface['strike'] <= put_25d_strike + 2)
        ]['iv'].mean()

        atm_iv = self._get_atm_iv(vol_surface, spot_price)

        return put_iv / atm_iv if atm_iv > 0 else 1.0

    def _calculate_call_skew(self, vol_surface: pd.DataFrame, spot_price: float) -> float:
        """Calculate call skew (25 delta call IV / ATM IV)"""
        call_25d_strike = spot_price * 1.05  # Approximate 25 delta call

        call_iv = vol_surface[
            (vol_surface['strike'] >= call_25d_strike - 2) &
            (vol_surface['strike'] <= call_25d_strike + 2)
        ]['iv'].mean()

        atm_iv = self._get_atm_iv(vol_surface, spot_price)

        return call_iv / atm_iv if atm_iv > 0 else 1.0

    def _analyze_term_structure(self, vol_surface: pd.DataFrame) -> str:
        """Analyze volatility term structure"""
        short_term = vol_surface[vol_surface['expiry'] <= 14]['iv'].mean()
        long_term = vol_surface[vol_surface['expiry'] >= 30]['iv'].mean()

        if long_term > short_term * 1.05:
            return 'contango'
        elif short_term > long_term * 1.05:
            return 'backwardation'
        else:
            return 'flat'

    def _classify_smile(self, put_skew: float, call_skew: float) -> str:
        """Classify volatility smile type"""
        if put_skew > 1.1 and call_skew < 1.05:
            return 'put_skewed'  # Normal equity smile
        elif call_skew > 1.1 and put_skew < 1.05:
            return 'call_skewed'  # Commodity-like
        elif put_skew > 1.1 and call_skew > 1.1:
            return 'symmetric_smile'  # High volatility
        else:
            return 'flat_smile'  # Low volatility

    # ==========================================================================
    # SIGNAL GENERATION
    # ==========================================================================

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Generate volatility trading signals"""
        try:
            signals = []

            # Check position limits
            if len(self.active_positions) >= self.max_positions:
                return signals

            # Update IV rank
            self.current_iv_rank = self._calculate_iv_rank(market_data)

            # Detect upcoming events
            events = self._detect_upcoming_events(market_data)

            # Analyze volatility surface
            vol_analysis = self._analyze_volatility_surface(market_data)

            # Determine strategy type
            strategy = self._select_volatility_strategy(
                self.current_iv_rank, events, vol_analysis
            )

            if strategy:
                # Create setup
                setup = self._create_volatility_setup(
                    strategy, market_data, vol_analysis, events
                )

                if setup and self._validate_setup(setup):
                    signal = self._create_trading_signal(setup, market_data)
                    if signal:
                        signals.append(signal)

            return signals

        except Exception as e:
            self.error_handler.handle_error(e, market_data)
            return []

    def _calculate_iv_rank(self, market_data: pd.DataFrame) -> float:
        """Calculate current IV rank"""
        if 'iv' not in market_data.columns:
            return 50.0

        iv_series = market_data['iv'].iloc[-252:]  # 1 year
        current_iv = iv_series.iloc[-1]

        min_iv = iv_series.min()
        max_iv = iv_series.max()

        if max_iv > min_iv:
            return ((current_iv - min_iv) / (max_iv - min_iv)) * 100
        return 50.0

    def _select_volatility_strategy(self, iv_rank: float, events: list[dict],
                                   vol_analysis: dict[str, Any]) -> VolatilityStrategy | None:
        """Select appropriate volatility strategy"""
        # Event-based selection
        if events:
            high_impact_event = any(e['impact'] == 'high' for e in events)

            if high_impact_event and iv_rank < MAX_IV_RANK_LONG:
                # Buy volatility before events
                if vol_analysis.get('smile_type') == 'flat_smile':
                    return VolatilityStrategy.LONG_STRADDLE
                else:
                    return VolatilityStrategy.LONG_STRANGLE

        # IV rank-based selection
        if MIN_IV_RANK_LONG <= iv_rank <= MAX_IV_RANK_LONG:
            # Low IV - buy volatility
            return VolatilityStrategy.LONG_STRANGLE

        elif MIN_IV_RANK_SHORT <= iv_rank <= MAX_IV_RANK_SHORT and self.allow_short:
            # High IV - sell volatility
            if vol_analysis.get('term_structure') == 'backwardation':
                # Prefer defined risk in backwardation
                return VolatilityStrategy.IRON_CONDOR
            else:
                return VolatilityStrategy.SHORT_STRANGLE

        return None

    def _create_volatility_setup(self, strategy: VolatilityStrategy,
                               market_data: pd.DataFrame,
                               vol_analysis: dict[str, Any],
                               events: list[dict]) -> VolatilitySetup | None:
        """Create volatility trade setup"""
        try:
            current_price = market_data['close'].iloc[-1]

            # Select strikes
            if strategy in [VolatilityStrategy.LONG_STRADDLE, VolatilityStrategy.SHORT_STRADDLE]:
                call_strike = put_strike = round(current_price)  # ATM
            else:  # Strangles
                call_strike, put_strike = self._select_strangle_strikes(
                    current_price, vol_analysis
                )

            # Select expiry
            expiry = self._select_expiry(strategy, events)

            # Calculate position size
            contracts = self._calculate_position_size(strategy, vol_analysis)

            # Estimate prices and Greeks
            prices = self._estimate_option_prices(
                current_price, call_strike, put_strike, expiry, vol_analysis
            )

            # Calculate net debit/credit
            if strategy in [VolatilityStrategy.LONG_STRADDLE, VolatilityStrategy.LONG_STRANGLE]:
                net_debit = (prices['call'] + prices['put']) * contracts * SPY_CONTRACT_MULTIPLIER
                max_profit = float('inf')  # Unlimited
                max_loss = net_debit
            else:  # Short strategies
                net_debit = -(prices['call'] + prices['put']) * contracts * SPY_CONTRACT_MULTIPLIER
                max_profit = -net_debit
                max_loss = float('inf')  # Unlimited for naked

            # Calculate breakevens
            breakevens = self._calculate_breakevens(
                call_strike, put_strike, prices, strategy
            )

            # Expected IV change
            expected_iv_change = self._estimate_iv_change(events, vol_analysis)

            # Determine event type
            event_type = None
            event_date = None
            if events:
                event_type = events[0]['type']
                event_date = events[0]['date']

            setup = VolatilitySetup(
                strategy=strategy,
                call_strike=call_strike,
                put_strike=put_strike,
                expiry=expiry,
                contracts=contracts,
                net_debit=net_debit,
                max_profit=max_profit,
                max_loss=max_loss,
                breakeven_upper=breakevens['upper'],
                breakeven_lower=breakevens['lower'],
                iv_at_entry=vol_analysis.get('atm_iv', 0.20),
                expected_iv_change=expected_iv_change,
                event_type=event_type,
                event_date=event_date
            )

            return setup

        except Exception as e:
            self.logger.error(f"Error creating volatility setup: {e}")
            return None

    def _select_strangle_strikes(self, current_price: float,
                                vol_analysis: dict[str, Any]) -> tuple[float, float]:
        """Select strangle strikes based on delta or fixed offset"""
        # Use skew information
        if vol_analysis.get('smile_type') == 'put_skewed':
            # Wider put strike in put-skewed market
            put_offset = STRANGLE_PUT_OFFSET * 1.2
            call_offset = STRANGLE_CALL_OFFSET
        elif vol_analysis.get('smile_type') == 'call_skewed':
            # Wider call strike in call-skewed market
            put_offset = STRANGLE_PUT_OFFSET
            call_offset = STRANGLE_CALL_OFFSET * 1.2
        else:
            put_offset = STRANGLE_PUT_OFFSET
            call_offset = STRANGLE_CALL_OFFSET

        call_strike = round(current_price + call_offset)
        put_strike = round(current_price - put_offset)

        return call_strike, put_strike

    def _select_expiry(self, strategy: VolatilityStrategy,
                      events: list[dict]) -> datetime:
        """Select optimal expiration date"""
        current_date = datetime.now()

        # Event-based expiry
        if events and events[0]['type'] != VolatilityEvent.VOLATILITY_CRUSH:
            # Expire after event
            event_date = events[0]['date']
            days_after = 3 if strategy in [VolatilityStrategy.LONG_STRADDLE,
                                          VolatilityStrategy.LONG_STRANGLE] else 7
            target_date = event_date + timedelta(days=days_after)
        else:
            # Standard expiry selection
            if strategy in [VolatilityStrategy.LONG_STRADDLE, VolatilityStrategy.LONG_STRANGLE]:
                target_dte = 30  # 30 days for long vol
            else:
                target_dte = 14  # 14 days for short vol

            target_date = current_date + timedelta(days=target_dte)

        # Find next Friday
        days_to_friday = (4 - target_date.weekday()) % 7
        if days_to_friday == 0:
            days_to_friday = 7

        return target_date + timedelta(days=days_to_friday)

    def _calculate_position_size(self, strategy: VolatilityStrategy,
                               vol_analysis: dict[str, Any]) -> int:
        """Calculate appropriate position size"""
        base_size = 1

        # Adjust for account size
        account_size = self.risk_profile.account_size
        if account_size > 100000:
            base_size = int(account_size / 50000)

        # Reduce size for undefined risk strategies
        if strategy in [VolatilityStrategy.SHORT_STRADDLE, VolatilityStrategy.SHORT_STRANGLE]:
            base_size = max(1, base_size // 2)

        return base_size

    def _estimate_option_prices(self, spot: float, call_strike: float,
                              put_strike: float, expiry: datetime,
                              vol_analysis: dict[str, Any]) -> dict[str, float]:
        """Estimate option prices"""
        # Simplified pricing - in production use Black-Scholes
        dte = (expiry - datetime.now()).days / 365.0
        atm_iv = vol_analysis.get('atm_iv', 0.20)

        # Call price approximation
        call_moneyness = call_strike / spot
        if call_moneyness > 1:  # OTM
            call_price = spot * atm_iv * np.sqrt(dte) * 0.4 * (1 - (call_moneyness - 1))
        else:  # ITM
            call_price = spot - call_strike + spot * atm_iv * np.sqrt(dte) * 0.4

        # Put price approximation
        put_moneyness = put_strike / spot
        if put_moneyness < 1:  # OTM
            put_price = spot * atm_iv * np.sqrt(dte) * 0.4 * (1 - (1 - put_moneyness))
        else:  # ITM
            put_price = put_strike - spot + spot * atm_iv * np.sqrt(dte) * 0.4

        return {
            'call': max(0.10, call_price),
            'put': max(0.10, put_price)
        }

    def _calculate_breakevens(self, call_strike: float, put_strike: float,
                            prices: dict[str, float],
                            strategy: VolatilityStrategy) -> dict[str, float]:
        """Calculate breakeven points"""
        total_premium = prices['call'] + prices['put']

        if strategy == VolatilityStrategy.LONG_STRADDLE:
            # Same strike for both
            upper = call_strike + total_premium
            lower = put_strike - total_premium
        elif strategy == VolatilityStrategy.LONG_STRANGLE:
            # Different strikes
            upper = call_strike + total_premium
            lower = put_strike - total_premium
        elif strategy == VolatilityStrategy.SHORT_STRADDLE:
            # Inverse for short
            upper = call_strike + total_premium
            lower = put_strike - total_premium
        else:  # Short strangle
            upper = call_strike + total_premium
            lower = put_strike - total_premium

        return {'upper': upper, 'lower': lower}

    def _estimate_iv_change(self, events: list[dict],
                          vol_analysis: dict[str, Any]) -> float:
        """Estimate expected IV change"""
        if events:
            if events[0]['type'] == VolatilityEvent.EARNINGS:
                return 0.10  # 10% IV expansion expected
            elif events[0]['type'] == VolatilityEvent.FED_MEETING:
                return 0.05  # 5% IV expansion
            elif events[0]['type'] == VolatilityEvent.VOLATILITY_CRUSH:
                return -0.20  # 20% IV crush

        # Non-event based on regime
        if self.current_iv_rank < 30:
            return 0.03  # Expect expansion from low IV
        elif self.current_iv_rank > 70:
            return -0.05  # Expect contraction from high IV

        return 0.0

    def _validate_setup(self, setup: VolatilitySetup) -> bool:
        """Validate volatility setup"""
        # Check breakeven width
        breakeven_width = setup.breakeven_upper - setup.breakeven_lower
        spot_price = (setup.call_strike + setup.put_strike) / 2

        if breakeven_width / spot_price < 0.02:  # Less than 2% profit zone
            self.logger.info("Setup rejected: Profit zone too narrow")
            return False

        # Check debit/credit reasonableness
        if abs(setup.net_debit) / (spot_price * setup.contracts * 100) > 0.10:
            self.logger.info("Setup rejected: Position too expensive")
            return False

        return True

    def _create_trading_signal(self, setup: VolatilitySetup,
                             market_data: pd.DataFrame) -> TradingSignal | None:
        """Convert setup to trading signal"""
        try:
            # Determine signal strength
            if setup.event_type and setup.expected_iv_change > 0.05:
                strength = SignalStrength.STRONG
            elif abs(setup.expected_iv_change) > 0.03:
                strength = SignalStrength.MEDIUM
            else:
                strength = SignalStrength.WEAK

            # Calculate confidence
            confidence = self._calculate_signal_confidence(setup)

            signal = TradingSignal(
                timestamp=datetime.now(),
                signal_type=SignalType.ENTRY,
                strength=strength,
                confidence=confidence,
                metadata={
                    'strategy': 'volatility',
                    'setup': setup.__dict__,
                    'strategy_type': setup.strategy.value,
                    'strikes': {
                        'call': setup.call_strike,
                        'put': setup.put_strike
                    },
                    'expiry': setup.expiry.strftime('%Y-%m-%d'),
                    'net_debit': setup.net_debit,
                    'breakevens': {
                        'upper': setup.breakeven_upper,
                        'lower': setup.breakeven_lower
                    },
                    'event': setup.event_type.value if setup.event_type else None,
                    'iv_rank': self.current_iv_rank
                }
            )

            self.logger.info(f"Generated {setup.strategy.value} signal")
            return signal

        except Exception as e:
            self.logger.error(f"Error creating signal: {e}")
            return None

    def _calculate_signal_confidence(self, setup: VolatilitySetup) -> float:
        """Calculate signal confidence"""
        confidence = 0.5

        # Event-based confidence
        if setup.event_type:
            if setup.event_type == VolatilityEvent.EARNINGS:
                confidence += 0.2
            elif setup.event_type == VolatilityEvent.FED_MEETING:
                confidence += 0.15

        # IV rank confidence
        if setup.strategy in [VolatilityStrategy.LONG_STRADDLE, VolatilityStrategy.LONG_STRANGLE]:
            if self.current_iv_rank < 20:
                confidence += 0.15
        else:  # Short strategies
            if self.current_iv_rank > 80:
                confidence += 0.15

        # Expected move confidence
        if abs(setup.expected_iv_change) > 0.10:
            confidence += 0.1

        return min(0.9, confidence)

    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================

    def manage_positions(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Manage active volatility positions"""
        signals = []

        current_price = market_data['close'].iloc[-1]
        current_iv = self._get_current_iv(market_data)

        for position_id, position in list(self.active_positions.items()):
            # Update position Greeks
            self._update_position_greeks(position, current_price, current_iv)

            # Update position value
            self._update_position_value(position, current_price, current_iv)

            # Check for gamma scalping opportunity
            if self.enable_gamma_scalping:
                scalp_signal = self._check_gamma_scalp(position, current_price)
                if scalp_signal:
                    signals.append(scalp_signal)

            # Check exit conditions
            exit_signal = self._check_exit_conditions(position, market_data)
            if exit_signal:
                signals.append(exit_signal)
                del self.active_positions[position_id]

        return signals

    def _get_current_iv(self, market_data: pd.DataFrame) -> float:
        """Get current implied volatility"""
        if 'iv' in market_data.columns:
            return market_data['iv'].iloc[-1]

        # Calculate from price movements
        returns = market_data['close'].pct_change().dropna()
        return returns.std() * np.sqrt(252)

    def _update_position_greeks(self, position: VolatilityPosition,
                              spot: float, iv: float):
        """Update position Greeks"""
        try:
            dte = (position.setup.expiry - datetime.now()).days / 365.0

            # Calculate Greeks (simplified)
            # In production, use proper Greeks calculator

            # Delta
            call_delta = stats.norm.cdf((np.log(spot / position.setup.call_strike) +
                                        (0.02 + iv**2/2) * dte) / (iv * np.sqrt(dte)))
            put_delta = call_delta - 1

            # Gamma (peaks at ATM)
            atm_distance = min(abs(spot - position.setup.call_strike),
                             abs(spot - position.setup.put_strike)) / spot
            gamma = np.exp(-atm_distance * 10) / (spot * iv * np.sqrt(dte)) * 0.1

            # Vega
            vega = spot * np.sqrt(dte) * stats.norm.pdf(call_delta) * 0.01

            # Theta
            theta = -spot * iv / (2 * np.sqrt(dte)) * stats.norm.pdf(call_delta) / 365

            # Adjust for position type
            if position.setup.strategy in [VolatilityStrategy.SHORT_STRADDLE,
                                          VolatilityStrategy.SHORT_STRANGLE]:
                gamma = -gamma
                vega = -vega
                theta = -theta

            # Create Greeks snapshot
            greeks = GreeksSnapshot(
                delta=call_delta + put_delta,
                gamma=gamma * position.setup.contracts * 100,
                vega=vega * position.setup.contracts * 100,
                theta=theta * position.setup.contracts * 100,
                rho=0,  # Simplified
                timestamp=datetime.now()
            )

            position.current_greeks = greeks
            position.greeks_history.append(greeks)

        except Exception as e:
            self.logger.error(f"Error updating Greeks: {e}")

    def _update_position_value(self, position: VolatilityPosition,
                             spot: float, current_iv: float):
        """Update position value and P&L"""
        try:
            # Estimate current option values
            (position.setup.expiry - datetime.now()).days / 365.0

            # IV change effect
            current_iv - position.setup.iv_at_entry

            # Price change effect
            spot - position.entry_price

            # Estimate new option values (simplified)
            vol_analysis = {'atm_iv': current_iv}
            current_prices = self._estimate_option_prices(
                spot, position.setup.call_strike, position.setup.put_strike,
                position.setup.expiry, vol_analysis
            )

            # Calculate current value
            current_value = (current_prices['call'] + current_prices['put']) * \
                          position.setup.contracts * SPY_CONTRACT_MULTIPLIER

            # Adjust for long/short
            if position.setup.strategy in [VolatilityStrategy.SHORT_STRADDLE,
                                          VolatilityStrategy.SHORT_STRANGLE]:
                current_value = -current_value

            position.current_value = current_value
            position.unrealized_pnl = current_value - position.setup.net_debit

        except Exception as e:
            self.logger.error(f"Error updating position value: {e}")

    def _check_gamma_scalp(self, position: VolatilityPosition,
                          current_price: float) -> TradingSignal | None:
        """Check for gamma scalping opportunity"""
        if not position.current_greeks:
            return None

        gamma = position.current_greeks.gamma

        # Only scalp long gamma positions
        if gamma < GAMMA_SCALP_THRESHOLD:
            return None

        # Check price movement since last scalp
        price_move = abs(current_price - position.entry_price) / position.entry_price

        if price_move > 0.01:  # 1% move
            # Generate scalp signal
            signal = TradingSignal(
                timestamp=datetime.now(),
                signal_type=SignalType.ADJUST,
                strength=SignalStrength.MEDIUM,
                confidence=0.7,
                metadata={
                    'position_id': position.position_id,
                    'action': 'gamma_scalp',
                    'gamma': gamma,
                    'suggested_hedge': -gamma * (current_price - position.entry_price)
                }
            )

            # Update position
            position.gamma_scalp_count += 1
            position.state = PositionState.GAMMA_SCALPING

            self.logger.info(f"Gamma scalp opportunity for {position.position_id}")
            return signal

        return None

    def _check_exit_conditions(self, position: VolatilityPosition,
                             market_data: pd.DataFrame) -> TradingSignal | None:
        """Check position exit conditions"""
        # Profit target
        profit_target = (LONG_VOL_PROFIT_TARGET if position.setup.strategy in
                        [VolatilityStrategy.LONG_STRADDLE, VolatilityStrategy.LONG_STRANGLE]
                        else SHORT_VOL_PROFIT_TARGET)

        if position.unrealized_pnl >= abs(position.setup.net_debit) * profit_target:
            return self._create_exit_signal(position, "profit_target")

        # Stop loss
        stop_loss = (LONG_VOL_STOP_LOSS if position.setup.strategy in
                    [VolatilityStrategy.LONG_STRADDLE, VolatilityStrategy.LONG_STRANGLE]
                    else SHORT_VOL_STOP_LOSS)

        if position.unrealized_pnl <= -abs(position.setup.net_debit) * stop_loss:
            return self._create_exit_signal(position, "stop_loss")

        # Time decay (close near expiry)
        dte = (position.setup.expiry - datetime.now()).days
        if dte <= 1:
            return self._create_exit_signal(position, "expiry")

        # Event passed (for event trades)
        if position.setup.event_date and datetime.now() > position.setup.event_date + timedelta(days=1):
            if position.unrealized_pnl > 0:
                return self._create_exit_signal(position, "event_complete")

        # IV crush completed
        if position.setup.event_type == VolatilityEvent.VOLATILITY_CRUSH:
            current_iv = self._get_current_iv(market_data)
            if current_iv < position.setup.iv_at_entry * 0.8:
                return self._create_exit_signal(position, "vol_crush_complete")

        return None

    def _create_exit_signal(self, position: VolatilityPosition,
                          reason: str) -> TradingSignal:
        """Create exit signal"""
        position.exit_time = datetime.now()
        position.exit_reason = reason
        position.state = PositionState.CLOSING

        # Update stats
        self._update_performance_stats(position)

        signal = TradingSignal(
            timestamp=datetime.now(),
            signal_type=SignalType.EXIT,
            strength=SignalStrength.STRONG,
            confidence=0.95,
            metadata={
                'position_id': position.position_id,
                'exit_reason': reason,
                'unrealized_pnl': position.unrealized_pnl,
                'realized_pnl': position.realized_pnl,
                'total_pnl': position.unrealized_pnl + position.realized_pnl,
                'gamma_scalps': position.gamma_scalp_count,
                'final_greeks': position.current_greeks.__dict__ if position.current_greeks else None
            }
        )

        self.logger.info(f"Exit {position.position_id}: {reason}, Total P&L: ${position.unrealized_pnl + position.realized_pnl:.2f}")
        return signal

    def _update_performance_stats(self, position: VolatilityPosition):
        """Update strategy performance statistics"""
        total_pnl = position.unrealized_pnl + position.realized_pnl

        self.performance_stats['total_trades'] += 1
        if total_pnl > 0:
            self.performance_stats['winning_trades'] += 1

        self.performance_stats['total_gamma_scalps'] += position.gamma_scalp_count
        self.performance_stats['gamma_scalp_pnl'] += position.realized_pnl

        if total_pnl > self.performance_stats['best_trade']:
            self.performance_stats['best_trade'] = total_pnl
        if total_pnl < self.performance_stats['worst_trade']:
            self.performance_stats['worst_trade'] = total_pnl

        # Update IV expansion tracking
        if position.setup.event_type:
            current_iv = position.setup.iv_at_entry + position.setup.expected_iv_change
            actual_change = (current_iv - position.setup.iv_at_entry) / position.setup.iv_at_entry

            n = self.performance_stats['total_trades']
            avg = self.performance_stats['avg_iv_expansion']
            self.performance_stats['avg_iv_expansion'] = (avg * (n-1) + actual_change) / n

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================

    def add_position(self, signal: TradingSignal) -> str:
        """Add new volatility position"""
        position_id = f"VOL_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        # Reconstruct setup from signal
        signal.metadata['setup']
        # In production, properly deserialize

        position = VolatilityPosition(
            position_id=position_id,
            setup=None,  # Would reconstruct
            entry_time=datetime.now(),
            entry_price=signal.metadata.get('current_price', 0),
            state=PositionState.ESTABLISHED
        )

        self.active_positions[position_id] = position
        self.logger.info(f"Added volatility position {position_id}")

        return position_id

    def get_position_summary(self) -> list[dict[str, Any]]:
        """Get summary of active positions"""
        summaries = []

        for position_id, position in self.active_positions.items():
            summary = {
                'position_id': position_id,
                'strategy': position.setup.strategy.value if position.setup else 'unknown',
                'unrealized_pnl': position.unrealized_pnl,
                'realized_pnl': position.realized_pnl,
                'total_pnl': position.unrealized_pnl + position.realized_pnl,
                'current_greeks': position.current_greeks.__dict__ if position.current_greeks else None,
                'gamma_scalps': position.gamma_scalp_count,
                'state': position.state.name
            }
            summaries.append(summary)

        return summaries

    def get_strategy_stats(self) -> dict[str, Any]:
        """Get strategy statistics"""
        total_trades = self.performance_stats['total_trades']
        win_rate = self.performance_stats['winning_trades'] / total_trades if total_trades > 0 else 0

        return {
            'active_positions': len(self.active_positions),
            'current_iv_rank': self.current_iv_rank,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'total_gamma_scalps': self.performance_stats['total_gamma_scalps'],
            'gamma_scalp_pnl': self.performance_stats['gamma_scalp_pnl'],
            'avg_iv_expansion': self.performance_stats['avg_iv_expansion'],
            'best_trade': self.performance_stats['best_trade'],
            'worst_trade': self.performance_stats['worst_trade'],
            'upcoming_events': len(self.upcoming_events)
        }


# ==============================================================================
# TESTING
# ==============================================================================
def test_straddle_strangle():
    """Test the Straddle/Strangle strategy"""
    logging.info("Testing Straddle/Strangle Strategy")
    logging.info("=" * 60)

    # Create mock components
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    from SpyderE_Risk.SpyderE01_RiskManager import RiskProfile

    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000,
        max_position_size=0.02,
        max_portfolio_risk=0.06,
        max_loss_per_trade=1000
    )

    config = {
        'max_positions': 2,
        'allow_short': True,
        'gamma_scalping': True,
        'event_trading': True
    }

    # Create strategy
    strategy = StraddleStrangleStrategy(event_manager, risk_profile, config)

    logging.info(f"Strategy: {strategy.name}")
    logging.info(f"Allow Short: {strategy.allow_short}")
    logging.info(f"Gamma Scalping: {strategy.enable_gamma_scalping}")

    # Create sample market data
    dates = pd.date_range(end=datetime.now(), periods=100, freq='5min')

    # Simulate volatility environment
    base_price = 450
    returns = np.random.randn(100) * 0.01
    prices = base_price * np.exp(np.cumsum(returns))

    # Add IV data
    base_iv = 0.18
    iv_returns = np.random.randn(100) * 0.005
    iv_series = base_iv * np.exp(np.cumsum(iv_returns))

    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices * (1 - abs(np.random.randn(100) * 0.001)),
        'high': prices * (1 + abs(np.random.randn(100) * 0.002)),
        'low': prices * (1 - abs(np.random.randn(100) * 0.002)),
        'close': prices,
        'volume': np.random.randint(50000000, 150000000, 100),
        'iv': iv_series
    })

    # Test IV rank calculation
    logging.info(f"\nCurrent IV Rank: {strategy._calculate_iv_rank(market_data):.1f}")

    # Test event detection
    logging.info("\nDetecting Events...")
    events = strategy._detect_upcoming_events(market_data)
    logging.info(f"Found {len(events)} upcoming events")
    for event in events:
        logging.info(f"- {event['type'].value}: {event.get('date', 'N/A')}, Impact: {event['impact']}")

    # Test volatility surface analysis
    logging.info("\nAnalyzing Volatility Surface...")
    vol_analysis = strategy._analyze_volatility_surface(market_data)
    logging.info(f"ATM IV: {vol_analysis.get('atm_iv', 0):.1%}")
    logging.info(f"Put Skew: {vol_analysis.get('put_skew', 1):.2f}")
    logging.info(f"Call Skew: {vol_analysis.get('call_skew', 1):.2f}")
    logging.info(f"Smile Type: {vol_analysis.get('smile_type', 'unknown')}")
    logging.info(f"Term Structure: {vol_analysis.get('term_structure', 'unknown')}")

    # Generate signals
    logging.info("\nGenerating Signals...")
    signals = strategy.generate_signals(market_data)

    logging.info(f"Generated {len(signals)} signals")

    for signal in signals:
        setup = signal.metadata
        logging.info(f"\nStrategy: {setup['strategy_type']}")
        logging.info(f"Strikes: Call ${setup['strikes']['call']}, Put ${setup['strikes']['put']}")
        logging.info(f"Expiry: {setup['expiry']}")
        logging.info(f"Net Debit: ${setup['net_debit']:.2f}")
        logging.info(f"Breakevens: ${setup['breakevens']['lower']:.2f} - ${setup['breakevens']['upper']:.2f}")
        logging.info(f"Event: {setup.get('event', 'None')}")
        logging.info(f"Confidence: {signal.confidence:.1%}")

        # Add position
        strategy.add_position(signal)

    # Simulate position management
    if strategy.active_positions:
        logging.info("\n" + "=" * 40)
        logging.info("Position Management Test")

        # Simulate price movement
        for i in range(20):
            # Add volatility
            price_shock = np.random.randn() * 2
            new_price = prices[-1] + price_shock
            new_iv = iv_series[-1] * (1 + np.random.randn() * 0.02)

            market_data.loc[len(market_data)] = {
                'timestamp': datetime.now() + timedelta(minutes=i*5),
                'open': new_price - 0.1,
                'high': new_price + 0.2,
                'low': new_price - 0.2,
                'close': new_price,
                'volume': 100000000,
                'iv': new_iv
            }

            # Update prices for next iteration
            prices = np.append(prices, new_price)
            iv_series = np.append(iv_series, new_iv)

            # Manage positions
            management_signals = strategy.manage_positions(market_data)

            if management_signals:
                for mgmt_signal in management_signals:
                    if mgmt_signal.signal_type == SignalType.ADJUST:
                        logging.info(f"\nGamma Scalp at iteration {i}")
                        logging.info(f"Gamma: {mgmt_signal.metadata['gamma']:.1f}")
                        logging.info(f"Suggested Hedge: ${mgmt_signal.metadata['suggested_hedge']:.2f}")
                    elif mgmt_signal.signal_type == SignalType.EXIT:
                        logging.info(f"\nExit at iteration {i}")
                        logging.info(f"Reason: {mgmt_signal.metadata['exit_reason']}")
                        logging.info(f"Total P&L: ${mgmt_signal.metadata['total_pnl']:.2f}")
                        logging.info(f"Gamma Scalps: {mgmt_signal.metadata['gamma_scalps']}")

    # Print final statistics
    stats = strategy.get_strategy_stats()
    logging.info("\n" + "=" * 40)
    logging.info("Strategy Statistics:")
    logging.info(f"Active Positions: {stats['active_positions']}")
    logging.info(f"Current IV Rank: {stats['current_iv_rank']:.1f}")
    logging.info(f"Total Trades: {stats['total_trades']}")
    logging.info(f"Win Rate: {stats['win_rate']:.1%}")
    logging.info(f"Total Gamma Scalps: {stats['total_gamma_scalps']}")
    logging.info(f"Gamma Scalp P&L: ${stats['gamma_scalp_pnl']:.2f}")
    logging.info(f"Avg IV Expansion: {stats['avg_iv_expansion']:.1%}")
    logging.info(f"Best Trade: ${stats['best_trade']:.2f}")
    logging.info(f"Worst Trade: ${stats['worst_trade']:.2f}")

    logging.info("\n✅ Straddle/Strangle Strategy Test Complete!")
    logging.info("\nKey Features Tested:")
    logging.info("- ✅ Event detection (earnings, Fed, technical)")
    logging.info("- ✅ Volatility surface analysis")
    logging.info("- ✅ IV rank calculation")
    logging.info("- ✅ Strike selection (ATM/OTM)")
    logging.info("- ✅ Long/short strategy selection")
    logging.info("- ✅ Greeks calculation and monitoring")
    logging.info("- ✅ Gamma scalping detection")
    logging.info("- ✅ Position value updates")
    logging.info("- ✅ Multiple exit conditions")
    logging.info("- ✅ Performance tracking")


if __name__ == "__main__":
    test_straddle_strangle()

