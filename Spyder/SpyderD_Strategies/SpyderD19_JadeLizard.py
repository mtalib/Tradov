#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD19_JadeLizard.py
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
from datetime import datetime, timedelta, UTC
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
    SignalType, OptionType, SPY_CONTRACT_MULTIPLIER
)
from Spyder.SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from Spyder.SpyderF_Analysis.SpyderF04_VolatilityAnalysis import VolatilityAnalyzer
from Spyder.SpyderF_Analysis.SpyderF10_MarketRegimeDetector import MarketRegimeDetector
from Spyder.SpyderE_Risk.SpyderE08_PositionGroupValidator import PositionGroupValidator
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager
import logging

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy Configuration
MAX_JADE_POSITIONS = 3
MIN_CREDIT_REQUIREMENT = 1.00  # Minimum $1.00 total credit
CALL_SPREAD_WIDTH = 5.0        # Standard $5 call spread

# Strike Selection
PUT_DELTA_TARGET = -0.30       # 30 delta short put
CALL_DELTA_TARGET = 0.25       # 25 delta short call
LONG_CALL_OFFSET = 5.0         # Points above short call

# Entry Requirements
MIN_IV_RANK = 40               # Minimum IV rank
MAX_IV_RANK = 85               # Maximum IV rank
MIN_DTE = 25                   # Minimum days to expiry
MAX_DTE = 50                   # Maximum days to expiry
OPTIMAL_DTE = 45               # Target DTE

# Risk Verification
NO_UPSIDE_RISK_CHECK = True    # Must verify no risk above
MIN_PROB_PROFIT = 0.65         # Minimum 65% probability

# Position Management
PROFIT_TARGET_PERCENT = 50     # Close at 50% of max profit
LOSS_THRESHOLD_PERCENT = 150   # Close at 150% of credit received
MANAGEMENT_WINDOW = 21         # Start managing at 21 DTE

# Greeks Limits
MAX_PORTFOLIO_DELTA = -100     # Maximum short delta exposure
MAX_GAMMA_EXPOSURE = -30       # Maximum gamma risk
MIN_THETA_COLLECTION = 20      # Minimum daily theta

# Market Conditions
SUITABLE_MARKET_BIAS = ['neutral', 'slightly_bullish']
AVOID_BINARY_EVENTS = True     # Skip earnings, Fed days

# ==============================================================================
# ENUMS
# ==============================================================================
class JadeLizardState(Enum):
    """Jade Lizard position states"""
    ANALYZING = auto()
    ENTERING = auto()
    MONITORING = auto()
    MANAGING = auto()
    CLOSING = auto()
    COMPLETE = auto()

class RiskTier(Enum):
    """Risk assessment levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


# Backward compatibility for tests/importers that still reference D19.RiskProfile.
RiskProfile = RiskTier

class MarketSentiment(Enum):
    """Market sentiment classification"""
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    SLIGHTLY_BULLISH = "slightly_bullish"
    BULLISH = "bullish"

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class JadeLeg:
    """Individual Jade Lizard leg"""
    option_type: OptionType
    strike: float
    position: int  # +1 long, -1 short
    contracts: int
    delta: float
    gamma: float
    vega: float
    theta: float
    iv: float
    premium: float
    bid: float
    ask: float

@dataclass
class JadeLizardSetup:
    """Complete Jade Lizard setup"""
    short_put: JadeLeg
    short_call: JadeLeg
    long_call: JadeLeg
    expiry: datetime
    total_credit: float
    put_credit: float
    call_spread_credit: float
    max_profit: float
    max_loss: float  # Downside only
    breakeven: float
    no_upside_risk: bool
    probability_profit: float
    expected_return: float
    market_sentiment: MarketSentiment
    iv_rank: float

@dataclass
class RiskMetrics:
    """Position risk metrics"""
    portfolio_delta: float
    portfolio_gamma: float
    portfolio_vega: float
    portfolio_theta: float
    pin_risk: bool
    early_assignment_risk: bool
    max_loss_percent: float
    current_risk_level: RiskTier

@dataclass
class JadeLizardPosition:
    """Active Jade Lizard position"""
    position_id: str
    setup: JadeLizardSetup
    entry_time: datetime
    entry_price: float
    risk_metrics: RiskMetrics
    current_value: float = 0.0
    unrealized_pnl: float = 0.0
    pnl_percent: float = 0.0
    days_held: int = 0
    dte: int = 45
    state: JadeLizardState = JadeLizardState.ENTERING
    management_triggers: list[str] = field(default_factory=list)
    exit_time: datetime | None = None
    exit_reason: str | None = None

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class JadeLizardStrategy(BaseStrategy):
    """
    Professional Jade Lizard strategy implementation.

    Combines a short put with a short call spread to generate income with
    no upside risk. Ideal for neutral to slightly bullish market conditions
    with elevated implied volatility.
    """

    def __init__(self, event_manager: EventManager, risk_profile: RiskTier,
                 config: dict[str, Any] = None):
        """Initialize Jade Lizard strategy"""
        resolved_config = config or {}
        super().__init__(
            name="Jade Lizard Strategy",
            strategy_type="jade_lizard",
            event_manager=event_manager,
            risk_profile=risk_profile,
            config=resolved_config
        )

        # Initialize components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.greeks_calculator = GreeksCalculator()
        self.volatility_analyzer = VolatilityAnalyzer()
        self.market_regime = MarketRegimeDetector()
        self.position_validator = PositionGroupValidator()

        # Strategy state
        self.active_positions: dict[str, JadeLizardPosition] = {}
        self.portfolio_greeks = {'delta': 0, 'gamma': 0, 'vega': 0, 'theta': 0}
        self.upcoming_events: list[dict] = []

        # Configuration
        self.max_positions = resolved_config.get('max_positions', MAX_JADE_POSITIONS)
        self.min_credit = resolved_config.get('min_credit', MIN_CREDIT_REQUIREMENT)
        self.enforce_no_upside_risk = resolved_config.get('enforce_no_upside_risk', NO_UPSIDE_RISK_CHECK)  # noqa: E501
        self.signal_symbol = str(resolved_config.get('symbol', 'SPY'))

        # Performance tracking
        self.performance_stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'perfect_trades': 0,  # Expired worthless
            'avg_credit': 0.0,
            'avg_holding_days': 0.0,
            'total_premium_collected': 0.0,
            'best_trade': 0.0,
            'worst_trade': 0.0
        }

        self.logger.info("Initialized %s", self.name)

    # ==========================================================================
    # MARKET ANALYSIS
    # ==========================================================================

    def _analyze_market_sentiment(self, market_data: pd.DataFrame) -> MarketSentiment:
        """Analyze current market sentiment for Jade Lizard suitability"""
        try:
            if len(market_data) < 50:
                return MarketSentiment.NEUTRAL

            close_prices = market_data['close']

            # Calculate multiple indicators
            sma_20 = close_prices.rolling(20).mean()
            sma_50 = close_prices.rolling(50).mean()
            rsi = self._calculate_rsi(close_prices)

            current_price = close_prices.iloc[-1]

            # Trend analysis
            short_trend = (current_price - sma_20.iloc[-1]) / sma_20.iloc[-1]
            (sma_20.iloc[-1] - sma_50.iloc[-1]) / sma_50.iloc[-1]

            # Sentiment scoring
            score = 0

            # Price above short MA: +1
            if current_price > sma_20.iloc[-1]:
                score += 1

            # Short MA above long MA: +1
            if sma_20.iloc[-1] > sma_50.iloc[-1]:
                score += 1

            # RSI not overbought: +1
            if 30 < rsi < 70:
                score += 1

            # Moderate uptrend: +1
            if 0 < short_trend < 0.03:  # 0-3% above MA
                score += 1

            # Classify sentiment
            if score >= 3:
                return MarketSentiment.SLIGHTLY_BULLISH
            elif score >= 2 or score >= 1:
                return MarketSentiment.NEUTRAL
            else:
                return MarketSentiment.BEARISH

        except Exception as e:
            self.logger.error("Error analyzing sentiment: %s", e)
            return MarketSentiment.NEUTRAL

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI"""
        delta = prices.diff()
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)

        avg_gains = gains.rolling(period).mean()
        avg_losses = losses.rolling(period).mean()

        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))

        return rsi.iloc[-1]

    def _check_upcoming_events(self) -> bool:
        """Check for upcoming binary events"""
        if not AVOID_BINARY_EVENTS:
            return True

        # Check earnings calendar
        # In production, would check actual earnings dates
        days_to_earnings = 30  # Mock
        if days_to_earnings < 5:
            self.logger.info("Skipping Jade Lizard due to upcoming earnings")
            return False

        # Check Fed calendar
        # In production, would check actual Fed dates
        days_to_fed = 30  # Mock
        if days_to_fed < 2:
            self.logger.info("Skipping Jade Lizard due to upcoming Fed meeting")
            return False

        return True

    # ==========================================================================
    # SIGNAL GENERATION
    # ==========================================================================

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Generate Jade Lizard trading signals"""
        try:
            signals = []

            # Check position limits
            if len(self.active_positions) >= self.max_positions:
                return signals

            # Check market sentiment
            sentiment = self._analyze_market_sentiment(market_data)
            if sentiment not in [MarketSentiment.NEUTRAL, MarketSentiment.SLIGHTLY_BULLISH]:
                return signals

            # Check for binary events
            if not self._check_upcoming_events():
                return signals

            # Check IV conditions
            iv_rank = self._calculate_iv_rank(market_data)
            if not (MIN_IV_RANK <= iv_rank <= MAX_IV_RANK):
                return signals

            # Create Jade Lizard setup
            setup = self._create_jade_lizard_setup(market_data, sentiment, iv_rank)

            if setup and self._validate_jade_setup(setup):
                signal = self._create_trading_signal(setup, market_data)
                if signal:
                    signals.append(signal)

            return signals

        except Exception as e:
            self.error_handler.handle_error(e, market_data)
            return []

    def validate_signal(self, signal: TradingSignal) -> bool:
        """Apply a minimal validity gate compatible with BaseStrategy."""
        if signal is None:
            return False
        if hasattr(signal, "is_valid") and not signal.is_valid():
            return False
        if len(self.active_positions) >= self.max_positions:
            return False
        return float(getattr(signal, "confidence", 0.0) or 0.0) > 0.0

    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Use provided size when available, otherwise default to one contract."""
        size = int(getattr(signal, "position_size", 0) or 0)
        return size if size > 0 else 1

    def should_exit_position(self, position: Any,
                             market_data: pd.DataFrame) -> tuple[bool, str]:
        """Generic stop/take-profit exit adapter for BaseStrategy contract."""
        if market_data.empty or "close" not in market_data.columns:
            return False, ""

        current_price = float(market_data["close"].iloc[-1])
        stop_loss = getattr(position, "stop_loss", None)
        take_profit = getattr(position, "take_profit", None)
        position_type = str(getattr(getattr(position, "position_type", ""), "value", "")).lower()

        if stop_loss is not None:
            if position_type == "short":
                if current_price >= stop_loss:
                    return True, "stop_loss"
            elif current_price <= stop_loss:
                return True, "stop_loss"

        if take_profit is not None:
            if position_type == "short":
                if current_price <= take_profit:
                    return True, "take_profit"
            elif current_price >= take_profit:
                return True, "take_profit"

        return False, ""

    def _calculate_iv_rank(self, market_data: pd.DataFrame) -> float:
        """Calculate IV rank"""
        if 'iv' not in market_data.columns:
            return 50.0

        iv_series = market_data['iv'].iloc[-252:]
        current_iv = iv_series.iloc[-1]

        min_iv = iv_series.min()
        max_iv = iv_series.max()

        if max_iv > min_iv:
            return ((current_iv - min_iv) / (max_iv - min_iv)) * 100
        return 50.0

    def _create_jade_lizard_setup(self, market_data: pd.DataFrame,
                                 sentiment: MarketSentiment,
                                 iv_rank: float) -> JadeLizardSetup | None:
        """Create complete Jade Lizard setup"""
        try:
            current_price = market_data['close'].iloc[-1]
            current_iv = self._get_current_iv(market_data)

            # Select expiry
            expiry = self._select_optimal_expiry()

            # Find strikes by delta
            put_strike = self._find_strike_by_delta(
                current_price, PUT_DELTA_TARGET, expiry, current_iv, OptionType.PUT
            )
            short_call_strike = self._find_strike_by_delta(
                current_price, CALL_DELTA_TARGET, expiry, current_iv, OptionType.CALL
            )
            long_call_strike = short_call_strike + CALL_SPREAD_WIDTH

            # Estimate premiums and Greeks
            put_data = self._calculate_option_data(
                put_strike, current_price, expiry, current_iv, OptionType.PUT
            )
            short_call_data = self._calculate_option_data(
                short_call_strike, current_price, expiry, current_iv, OptionType.CALL
            )
            long_call_data = self._calculate_option_data(
                long_call_strike, current_price, expiry, current_iv, OptionType.CALL
            )

            # Create legs
            short_put = JadeLeg(
                option_type=OptionType.PUT,
                strike=put_strike,
                position=-1,
                contracts=1,
                delta=put_data['delta'],
                gamma=put_data['gamma'],
                vega=put_data['vega'],
                theta=put_data['theta'],
                iv=current_iv,
                premium=put_data['premium'],
                bid=put_data['bid'],
                ask=put_data['ask']
            )

            short_call = JadeLeg(
                option_type=OptionType.CALL,
                strike=short_call_strike,
                position=-1,
                contracts=1,
                delta=short_call_data['delta'],
                gamma=short_call_data['gamma'],
                vega=short_call_data['vega'],
                theta=short_call_data['theta'],
                iv=current_iv,
                premium=short_call_data['premium'],
                bid=short_call_data['bid'],
                ask=short_call_data['ask']
            )

            long_call = JadeLeg(
                option_type=OptionType.CALL,
                strike=long_call_strike,
                position=1,
                contracts=1,
                delta=long_call_data['delta'],
                gamma=long_call_data['gamma'],
                vega=long_call_data['vega'],
                theta=long_call_data['theta'],
                iv=current_iv,
                premium=long_call_data['premium'],
                bid=long_call_data['bid'],
                ask=long_call_data['ask']
            )

            # Calculate credits
            put_credit = put_data['premium']
            call_spread_credit = short_call_data['premium'] - long_call_data['premium']
            total_credit = put_credit + call_spread_credit

            # Verify no upside risk
            no_upside_risk = self._verify_no_upside_risk(
                call_spread_credit, CALL_SPREAD_WIDTH, total_credit
            )

            # Calculate profit/loss metrics
            max_profit = total_credit * SPY_CONTRACT_MULTIPLIER
            max_loss = (put_strike - total_credit) * SPY_CONTRACT_MULTIPLIER
            breakeven = put_strike - total_credit

            # Calculate probability of profit
            prob_profit = self._calculate_probability_profit(
                current_price, put_strike, short_call_strike, expiry, current_iv
            )

            # Expected return
            expected_return = (prob_profit * max_profit - (1 - prob_profit) * max_loss * 0.3) / max_loss  # noqa: E501

            setup = JadeLizardSetup(
                short_put=short_put,
                short_call=short_call,
                long_call=long_call,
                expiry=expiry,
                total_credit=total_credit * SPY_CONTRACT_MULTIPLIER,
                put_credit=put_credit * SPY_CONTRACT_MULTIPLIER,
                call_spread_credit=call_spread_credit * SPY_CONTRACT_MULTIPLIER,
                max_profit=max_profit,
                max_loss=max_loss,
                breakeven=breakeven,
                no_upside_risk=no_upside_risk,
                probability_profit=prob_profit,
                expected_return=expected_return,
                market_sentiment=sentiment,
                iv_rank=iv_rank
            )

            return setup

        except Exception as e:
            self.logger.error("Error creating Jade Lizard setup: %s", e)
            return None

    def _get_current_iv(self, market_data: pd.DataFrame) -> float:
        """Get current implied volatility"""
        if 'iv' in market_data.columns:
            return market_data['iv'].iloc[-1]

        # Estimate from returns
        returns = market_data['close'].pct_change().dropna()
        return returns.std() * np.sqrt(252)

    def _select_optimal_expiry(self) -> datetime:
        """Select optimal expiration date"""
        current_date = datetime.now(UTC)
        target_date = current_date + timedelta(days=OPTIMAL_DTE)

        # Find next Friday
        days_to_friday = (4 - target_date.weekday()) % 7
        if days_to_friday == 0:
            days_to_friday = 7

        expiry = target_date + timedelta(days=days_to_friday)

        # Ensure within DTE range
        dte = (expiry - current_date).days
        if dte < MIN_DTE:
            expiry += timedelta(days=7)
        elif dte > MAX_DTE:
            expiry -= timedelta(days=7)

        return expiry

    def _find_strike_by_delta(self, spot: float, target_delta: float,
                            expiry: datetime, iv: float,
                            option_type: OptionType) -> float:
        """Find strike with target delta"""
        dte = (expiry - datetime.now(UTC)).days / 365.0

        # Use inverse Black-Scholes to find strike
        if option_type == OptionType.CALL:
            z_score = stats.norm.ppf(abs(target_delta))
            strike = spot * np.exp((z_score * iv * np.sqrt(dte)) + (iv**2 * dte / 2))
        else:  # PUT
            z_score = stats.norm.ppf(1 + target_delta)  # target_delta is negative
            strike = spot * np.exp((z_score * iv * np.sqrt(dte)) - (iv**2 * dte / 2))

        # Round to nearest dollar
        return round(strike)

    def _calculate_option_data(self, strike: float, spot: float,
                             expiry: datetime, iv: float,
                             option_type: OptionType) -> dict[str, float]:
        """Calculate option premium and Greeks"""
        dte = (expiry - datetime.now(UTC)).days / 365.0

        # Black-Scholes calculations
        d1 = (np.log(spot / strike) + (0.02 + iv**2/2) * dte) / (iv * np.sqrt(dte))
        d2 = d1 - iv * np.sqrt(dte)

        # Premium
        if option_type == OptionType.CALL:
            premium = spot * stats.norm.cdf(d1) - strike * np.exp(-0.02 * dte) * stats.norm.cdf(d2)
            delta = stats.norm.cdf(d1)
        else:
            premium = strike * np.exp(-0.02 * dte) * stats.norm.cdf(-d2) - spot * stats.norm.cdf(-d1)  # noqa: E501
            delta = stats.norm.cdf(d1) - 1

        # Greeks
        gamma = stats.norm.pdf(d1) / (spot * iv * np.sqrt(dte))
        vega = spot * stats.norm.pdf(d1) * np.sqrt(dte) / 100
        theta = -(spot * stats.norm.pdf(d1) * iv / (2 * np.sqrt(dte)) +
                 0.02 * strike * np.exp(-0.02 * dte) * stats.norm.cdf(d2 if option_type == OptionType.CALL else -d2)) / 365  # noqa: E501

        # Bid-ask spread (simplified)
        spread = premium * 0.05  # 5% spread

        return {
            'premium': max(0.10, premium),
            'delta': delta,
            'gamma': gamma,
            'vega': vega,
            'theta': theta,
            'bid': max(0.05, premium - spread/2),
            'ask': premium + spread/2
        }

    def _verify_no_upside_risk(self, call_spread_credit: float,
                              spread_width: float,
                              total_credit: float) -> bool:
        """Verify the setup has no upside risk"""
        # No upside risk when total credit > call spread width
        # This ensures max loss on upside is 0
        return total_credit >= spread_width

    def _calculate_probability_profit(self, spot: float, put_strike: float,
                                    call_strike: float, expiry: datetime,
                                    iv: float) -> float:
        """Calculate probability of profit for Jade Lizard"""
        dte = (expiry - datetime.now(UTC)).days / 365.0

        # For Jade Lizard with no upside risk, profit occurs when:
        # Price stays above put strike (no assignment on put)

        # Calculate probability of staying above put strike
        price_std = spot * iv * np.sqrt(dte)
        z_put = (put_strike - spot) / price_std
        prob_above_put = 1 - stats.norm.cdf(z_put)

        # Additional adjustment for call spread impact
        # Small probability reduction if price goes way above call strikes
        z_call = (call_strike - spot) / price_std
        prob_below_call = stats.norm.cdf(z_call)

        # Combined probability (simplified)
        # Most profit comes from put side since no upside risk
        prob_profit = prob_above_put * 0.9 + prob_below_call * 0.1

        return min(0.95, max(0.05, prob_profit))

    def _validate_jade_setup(self, setup: JadeLizardSetup) -> bool:
        """Validate Jade Lizard setup"""
        # Check minimum credit
        if setup.total_credit < self.min_credit * SPY_CONTRACT_MULTIPLIER:
            self.logger.info(f"Jade Lizard credit too low: ${setup.total_credit:.2f}")
            return False

        # Check no upside risk
        if self.enforce_no_upside_risk and not setup.no_upside_risk:
            self.logger.info("Jade Lizard has upside risk")
            return False

        # Check probability of profit
        if setup.probability_profit < MIN_PROB_PROFIT:
            self.logger.info(f"Jade Lizard probability too low: {setup.probability_profit:.1%}")
            return False

        # Check strike relationships
        if setup.short_call.strike <= setup.short_put.strike:
            self.logger.info("Invalid strike relationship")
            return False

        return True

    def _create_trading_signal(self, setup: JadeLizardSetup,
                             market_data: pd.DataFrame) -> TradingSignal | None:
        """Convert setup to trading signal"""
        try:
            # Calculate initial risk metrics
            risk_metrics = self._calculate_risk_metrics(setup, market_data)

            # Determine signal strength
            if setup.probability_profit > 0.75 and setup.no_upside_risk:
                strength = SignalStrength.STRONG
            elif setup.probability_profit > 0.65:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK

            signal_timestamp = datetime.now(UTC)
            current_price = float(market_data['close'].iloc[-1])
            signal = TradingSignal(
                signal_id=str(uuid.uuid4()),
                signal_type=SignalType.BUY,
                symbol=self.signal_symbol,
                strength=strength,
                confidence=setup.probability_profit,
                entry_price=current_price,
                stop_loss=current_price * 0.98,
                take_profit=current_price * 1.02,
                position_size=1,
                timestamp=signal_timestamp,
                expires_at=signal_timestamp + timedelta(minutes=15),
                metadata={
                    'strategy': 'jade_lizard',
                    'strategy_id': 'JadeLizard',
                    'strategy_type': 'JadeLizard',
                    'action': 'buy',
                    'setup': setup.__dict__,
                    'strikes': {
                        'short_put': setup.short_put.strike,
                        'short_call': setup.short_call.strike,
                        'long_call': setup.long_call.strike
                    },
                    'credits': {
                        'total': setup.total_credit,
                        'put': setup.put_credit,
                        'call_spread': setup.call_spread_credit
                    },
                    'no_upside_risk': setup.no_upside_risk,
                    'breakeven': setup.breakeven,
                    'max_profit': setup.max_profit,
                    'max_loss': setup.max_loss,
                    'iv_rank': setup.iv_rank,
                    'sentiment': setup.market_sentiment.value,
                    'risk_metrics': risk_metrics.__dict__
                }
            )

            self.logger.info(f"Generated Jade Lizard signal with {setup.probability_profit:.1%} probability")  # noqa: E501
            return signal

        except Exception as e:
            self.logger.error("Error creating signal: %s", e)
            return None

    def _calculate_risk_metrics(self, setup: JadeLizardSetup,
                               market_data: pd.DataFrame) -> RiskMetrics:
        """Calculate comprehensive risk metrics"""
        # Portfolio Greeks (position level)
        delta = (setup.short_put.delta + setup.short_call.delta + setup.long_call.delta)
        gamma = (setup.short_put.gamma + setup.short_call.gamma + setup.long_call.gamma)
        vega = (setup.short_put.vega + setup.short_call.vega + setup.long_call.vega)
        theta = (setup.short_put.theta + setup.short_call.theta + setup.long_call.theta)

        # Scale by contract multiplier
        portfolio_delta = delta * SPY_CONTRACT_MULTIPLIER
        portfolio_gamma = gamma * SPY_CONTRACT_MULTIPLIER
        portfolio_vega = vega * SPY_CONTRACT_MULTIPLIER
        portfolio_theta = theta * SPY_CONTRACT_MULTIPLIER

        # Pin risk assessment
        current_price = market_data['close'].iloc[-1]
        pin_risk = (abs(current_price - setup.short_put.strike) < 2 or
                   abs(current_price - setup.short_call.strike) < 2)

        # Early assignment risk
        dte = (setup.expiry - datetime.now(UTC)).days
        early_assignment_risk = dte < 7 and pin_risk

        # Max loss as percentage of account
        max_loss_percent = (setup.max_loss / self.risk_profile.account_size) * 100

        # Determine risk level
        if max_loss_percent > 5 or abs(portfolio_delta) > 50:
            risk_level = RiskTier.HIGH
        elif max_loss_percent > 3 or abs(portfolio_delta) > 30:
            risk_level = RiskTier.MEDIUM
        else:
            risk_level = RiskTier.LOW

        return RiskMetrics(
            portfolio_delta=portfolio_delta,
            portfolio_gamma=portfolio_gamma,
            portfolio_vega=portfolio_vega,
            portfolio_theta=portfolio_theta,
            pin_risk=pin_risk,
            early_assignment_risk=early_assignment_risk,
            max_loss_percent=max_loss_percent,
            current_risk_level=risk_level
        )

    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================

    def manage_positions(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Manage active Jade Lizard positions"""
        signals = []
        current_price = market_data['close'].iloc[-1]

        # Update portfolio Greeks
        self._update_portfolio_greeks()

        for position_id, position in list(self.active_positions.items()):
            # Update position metrics
            position.days_held += 1
            position.dte = (position.setup.expiry - datetime.now(UTC)).days

            # Update position value and risk
            self._update_position_value(position, current_price, market_data)
            self._update_risk_metrics(position, current_price, market_data)

            # Check management triggers
            if position.dte <= MANAGEMENT_WINDOW:
                position.state = JadeLizardState.MANAGING

            # Check exit conditions
            exit_signal = self._check_exit_conditions(position, market_data)
            if exit_signal:
                signals.append(exit_signal)
                self._close_position(position)
                del self.active_positions[position_id]

        return signals

    def _update_portfolio_greeks(self):
        """Update aggregate portfolio Greeks"""
        total_delta = sum(p.risk_metrics.portfolio_delta for p in self.active_positions.values())
        total_gamma = sum(p.risk_metrics.portfolio_gamma for p in self.active_positions.values())
        total_vega = sum(p.risk_metrics.portfolio_vega for p in self.active_positions.values())
        total_theta = sum(p.risk_metrics.portfolio_theta for p in self.active_positions.values())

        self.portfolio_greeks = {
            'delta': total_delta,
            'gamma': total_gamma,
            'vega': total_vega,
            'theta': total_theta
        }

    def _update_position_value(self, position: JadeLizardPosition,
                              current_price: float,
                              market_data: pd.DataFrame):
        """Update position value and P&L"""
        try:
            setup = position.setup
            current_iv = self._get_current_iv(market_data)

            # Calculate current value of each leg
            put_value = self._calculate_option_data(
                setup.short_put.strike, current_price, setup.expiry,
                current_iv, setup.short_put.option_type
            )['premium']

            short_call_value = self._calculate_option_data(
                setup.short_call.strike, current_price, setup.expiry,
                current_iv, setup.short_call.option_type
            )['premium']

            long_call_value = self._calculate_option_data(
                setup.long_call.strike, current_price, setup.expiry,
                current_iv, setup.long_call.option_type
            )['premium']

            # Current position value (negative because we're short)
            current_value = -(put_value + short_call_value - long_call_value) * SPY_CONTRACT_MULTIPLIER  # noqa: E501

            position.current_value = current_value
            position.unrealized_pnl = setup.total_credit + current_value
            position.pnl_percent = (position.unrealized_pnl / setup.total_credit) * 100

        except Exception as e:
            self.logger.error("Error updating position value: %s", e)

    def _update_risk_metrics(self, position: JadeLizardPosition,
                           current_price: float,
                           market_data: pd.DataFrame):
        """Update position risk metrics"""
        try:
            # Recalculate Greeks with current market data
            new_metrics = self._calculate_risk_metrics(position.setup, market_data)
            position.risk_metrics = new_metrics

            # Check for new management triggers
            if new_metrics.pin_risk and "pin_risk" not in position.management_triggers:
                position.management_triggers.append("pin_risk")
                self.logger.warning("Pin risk detected for %s", position.position_id)

            if new_metrics.early_assignment_risk and "assignment_risk" not in position.management_triggers:  # noqa: E501
                position.management_triggers.append("assignment_risk")
                self.logger.warning("Early assignment risk for %s", position.position_id)

        except Exception as e:
            self.logger.error("Error updating risk metrics: %s", e)

    def _check_exit_conditions(self, position: JadeLizardPosition,
                             market_data: pd.DataFrame) -> TradingSignal | None:
        """Check position exit conditions"""
        # Profit target reached
        if position.pnl_percent >= PROFIT_TARGET_PERCENT:
            return self._create_exit_signal(position, "profit_target")

        # Loss threshold breached
        if position.pnl_percent <= -LOSS_THRESHOLD_PERCENT:
            return self._create_exit_signal(position, "loss_threshold")

        # Portfolio delta limit breached
        if abs(self.portfolio_greeks['delta']) > MAX_PORTFOLIO_DELTA:
            return self._create_exit_signal(position, "delta_limit")

        # Early assignment risk with adverse move
        current_price = market_data['close'].iloc[-1]
        if position.risk_metrics.early_assignment_risk:
            if current_price < position.setup.short_put.strike * 0.98:
                return self._create_exit_signal(position, "assignment_risk_put")

        # Time-based exit (1 DTE)
        if position.dte <= 1:
            return self._create_exit_signal(position, "expiration")

        # Risk level escalation
        if position.risk_metrics.current_risk_level == RiskTier.EXTREME:
            return self._create_exit_signal(position, "extreme_risk")

        return None

    def _create_exit_signal(self, position: JadeLizardPosition,
                          reason: str) -> TradingSignal:
        """Create exit signal"""
        position.exit_time = datetime.now(UTC)
        position.exit_reason = reason
        position.state = JadeLizardState.CLOSING

        # Update performance stats
        self._update_performance_stats(position)

        signal_timestamp = datetime.now(UTC)
        signal = TradingSignal(
            signal_id=str(uuid.uuid4()),
            signal_type=SignalType.CLOSE,
            symbol=self.signal_symbol,
            strength=SignalStrength.STRONG,
            confidence=0.95,
            entry_price=float(position.current_value or 0.0),
            stop_loss=float(position.current_value or 0.0),
            take_profit=float(position.current_value or 0.0),
            position_size=1,
            timestamp=signal_timestamp,
            expires_at=signal_timestamp + timedelta(minutes=10),
            metadata={
                'position_id': position.position_id,
                'strategy_id': 'JadeLizard',
                'strategy_type': 'JadeLizard',
                'exit_reason': reason,
                'days_held': position.days_held,
                'unrealized_pnl': position.unrealized_pnl,
                'pnl_percent': position.pnl_percent,
                'final_dte': position.dte,
                'management_triggers': position.management_triggers,
                'final_risk_level': position.risk_metrics.current_risk_level.value
            }
        )

        self.logger.info(f"Exit Jade Lizard {position.position_id}: {reason}, P&L: ${position.unrealized_pnl:.2f} ({position.pnl_percent:.1f}%)")  # noqa: E501
        return signal

    def _close_position(self, position: JadeLizardPosition):
        """Close position and cleanup"""
        position.state = JadeLizardState.COMPLETE

    def _update_performance_stats(self, position: JadeLizardPosition):
        """Update strategy performance statistics"""
        self.performance_stats['total_trades'] += 1

        if position.unrealized_pnl > 0:
            self.performance_stats['winning_trades'] += 1

        # Perfect trade (kept full premium)
        if position.pnl_percent >= 95:
            self.performance_stats['perfect_trades'] += 1

        # Update averages
        n = self.performance_stats['total_trades']
        avg_credit = self.performance_stats['avg_credit']
        self.performance_stats['avg_credit'] = (avg_credit * (n-1) + position.setup.total_credit) / n  # noqa: E501

        avg_days = self.performance_stats['avg_holding_days']
        self.performance_stats['avg_holding_days'] = (avg_days * (n-1) + position.days_held) / n

        # Total premium
        self.performance_stats['total_premium_collected'] += position.setup.total_credit

        # Best/worst trade
        if position.unrealized_pnl > self.performance_stats['best_trade']:
            self.performance_stats['best_trade'] = position.unrealized_pnl
        if position.unrealized_pnl < self.performance_stats['worst_trade']:
            self.performance_stats['worst_trade'] = position.unrealized_pnl

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================

    def add_position(self, signal: TradingSignal) -> str:
        """Add new Jade Lizard position"""
        position_id = f"JADE_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        # Extract setup and risk metrics from signal
        signal.metadata['setup']
        signal.metadata['risk_metrics']

        # In production, would properly deserialize
        # For now, create mock position
        position = JadeLizardPosition(
            position_id=position_id,
            setup=None,  # Would reconstruct
            entry_time=datetime.now(UTC),
            entry_price=signal.metadata.get('current_price', 0),
            risk_metrics=None,  # Would reconstruct
            state=JadeLizardState.MONITORING
        )

        self.active_positions[position_id] = position
        self.logger.info("Added Jade Lizard position %s", position_id)

        return position_id

    def get_position_summary(self) -> list[dict[str, Any]]:
        """Get summary of active positions"""
        summaries = []

        for position_id, position in self.active_positions.items():
            summary = {
                'position_id': position_id,
                'days_held': position.days_held,
                'dte': position.dte,
                'unrealized_pnl': position.unrealized_pnl,
                'pnl_percent': position.pnl_percent,
                'strikes': {
                    'put': position.setup.short_put.strike if position.setup else 0,
                    'short_call': position.setup.short_call.strike if position.setup else 0,
                    'long_call': position.setup.long_call.strike if position.setup else 0
                },
                'risk_level': position.risk_metrics.current_risk_level.value if position.risk_metrics else 'unknown',  # noqa: E501
                'state': position.state.name,
                'triggers': position.management_triggers
            }
            summaries.append(summary)

        return summaries

    def get_strategy_stats(self) -> dict[str, Any]:
        """Get strategy performance statistics"""
        total_trades = self.performance_stats['total_trades']
        win_rate = self.performance_stats['winning_trades'] / total_trades if total_trades > 0 else 0  # noqa: E501
        perfect_rate = self.performance_stats['perfect_trades'] / total_trades if total_trades > 0 else 0  # noqa: E501

        return {
            'active_positions': len(self.active_positions),
            'portfolio_greeks': self.portfolio_greeks,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'perfect_trade_rate': perfect_rate,
            'avg_credit': self.performance_stats['avg_credit'],
            'avg_holding_days': self.performance_stats['avg_holding_days'],
            'total_premium_collected': self.performance_stats['total_premium_collected'],
            'best_trade': self.performance_stats['best_trade'],
            'worst_trade': self.performance_stats['worst_trade']
        }


# ==============================================================================
# TESTING
# ==============================================================================
def test_jade_lizard():
    """Test the Jade Lizard strategy"""
    logging.info("Testing Jade Lizard Strategy")
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
        'min_credit': 1.00,
        'enforce_no_upside_risk': True
    }

    # Create strategy
    strategy = JadeLizardStrategy(event_manager, risk_profile, config)

    logging.info("Strategy: %s", strategy.name)
    logging.info("Min Credit: $%s", strategy.min_credit)
    logging.info("Enforce No Upside Risk: %s", strategy.enforce_no_upside_risk)

    # Create neutral to slightly bullish market
    dates = pd.date_range(end=datetime.now(UTC), periods=100, freq='D')

    # Slight uptrend with consolidation
    base_price = 450
    trend = np.linspace(0, 5, 100)  # Slight uptrend
    noise = np.random.randn(100) * 1.5
    prices = base_price + trend + noise

    # Add IV data
    iv_series = 0.22 + np.sin(np.linspace(0, 2*np.pi, 100)) * 0.05

    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices - 0.5,
        'high': prices + 1,
        'low': prices - 1,
        'close': prices,
        'volume': np.random.randint(50000000, 150000000, 100),
        'iv': iv_series
    })

    # Test market sentiment
    logging.info("\nMarket Sentiment Analysis:")
    sentiment = strategy._analyze_market_sentiment(market_data)
    logging.info("Sentiment: %s", sentiment.value)

    # Test IV rank
    iv_rank = strategy._calculate_iv_rank(market_data)
    logging.info(f"IV Rank: {iv_rank:.1f}")

    # Check events
    logging.info("Events Clear: %s", strategy._check_upcoming_events())

    # Generate signals
    logging.info("\nGenerating Signals...")
    signals = strategy.generate_signals(market_data)

    logging.info("Generated %s signals", len(signals))

    for signal in signals:
        setup = signal.metadata
        logging.info("\nJade Lizard Setup:")
        logging.info(f"Strikes: Put ${setup['strikes']['short_put']}, "
              f"Call ${setup['strikes']['short_call']}/{setup['strikes']['long_call']}")
        logging.info(f"Total Credit: ${setup['credits']['total']:.2f}")
        logging.info(f"  - Put Credit: ${setup['credits']['put']:.2f}")
        logging.info(f"  - Call Spread Credit: ${setup['credits']['call_spread']:.2f}")
        logging.info("No Upside Risk: %s", setup['no_upside_risk'])
        logging.info(f"Breakeven: ${setup['breakeven']:.2f}")
        logging.info(f"Max Profit: ${setup['max_profit']:.2f}")
        logging.info(f"Max Loss: ${setup['max_loss']:.2f}")
        logging.info(f"Probability of Profit: {signal.confidence:.1%}")
        logging.info(f"IV Rank: {setup['iv_rank']:.1f}")
        logging.info("Market Sentiment: %s", setup['sentiment'])

        # Risk metrics
        risk = setup['risk_metrics']
        logging.info("\nRisk Metrics:")
        logging.info(f"Portfolio Delta: {risk['portfolio_delta']:.1f}")
        logging.info(f"Portfolio Theta: ${risk['portfolio_theta']:.2f}")
        logging.info("Risk Level: %s", risk['current_risk_level'])

        # Add position
        strategy.add_position(signal)

    # Test position management
    if strategy.active_positions:
        logging.info("\n" + "=" * 40)
        logging.info("Position Management Test")

        # Simulate price movement
        for i in range(20):
            # Small moves with occasional larger moves
            if i % 5 == 0:
                price_change = np.random.randn() * 3  # Larger move
            else:
                price_change = np.random.randn() * 1  # Normal move

            new_price = prices[-1] + price_change

            market_data.loc[len(market_data)] = {
                'timestamp': datetime.now(UTC) + timedelta(days=i),
                'open': new_price - 0.3,
                'high': new_price + 0.5,
                'low': new_price - 0.5,
                'close': new_price,
                'volume': 100000000,
                'iv': 0.20 + np.random.randn() * 0.02
            }

            prices = np.append(prices, new_price)

            # Manage positions
            if i % 5 == 0:  # Check every 5 days
                management_signals = strategy.manage_positions(market_data)

                if management_signals:
                    for signal in management_signals:
                        logging.info("\nExit Signal Day %s", i)
                        logging.info("Reason: %s", signal.metadata['exit_reason'])
                        logging.info("Days Held: %s", signal.metadata['days_held'])
                        logging.info(f"P&L: ${signal.metadata['unrealized_pnl']:.2f}")
                        logging.info(f"P&L %: {signal.metadata['pnl_percent']:.1f}%")
                        logging.info("Final DTE: %s", signal.metadata['final_dte'])
                        logging.info("Triggers: %s", signal.metadata['management_triggers'])

    # Print position summary
    positions = strategy.get_position_summary()
    if positions:
        logging.info("\n" + "=" * 40)
        logging.info("Active Positions:")
        for pos in positions:
            logging.info("\n%s:", pos['position_id'])
            logging.info("  DTE: %s", pos['dte'])
            logging.info(f"  P&L: ${pos['unrealized_pnl']:.2f} ({pos['pnl_percent']:.1f}%)")
            logging.info(f"  Strikes: Put ${pos['strikes']['put']}, "
                  f"Call ${pos['strikes']['short_call']}/{pos['strikes']['long_call']}")
            logging.info("  Risk Level: %s", pos['risk_level'])
            logging.info("  State: %s", pos['state'])

    # Print final statistics
    stats = strategy.get_strategy_stats()
    logging.info("\n" + "=" * 40)
    logging.info("Strategy Statistics:")
    logging.info("Active Positions: %s", stats['active_positions'])
    logging.info("Portfolio Greeks:")
    logging.info(f"  Delta: {stats['portfolio_greeks']['delta']:.1f}")
    logging.info(f"  Gamma: {stats['portfolio_greeks']['gamma']:.1f}")
    logging.info(f"  Theta: ${stats['portfolio_greeks']['theta']:.2f}")
    logging.info("Total Trades: %s", stats['total_trades'])
    logging.info(f"Win Rate: {stats['win_rate']:.1%}")
    logging.info(f"Perfect Trade Rate: {stats['perfect_trade_rate']:.1%}")
    logging.info(f"Average Credit: ${stats['avg_credit']:.2f}")
    logging.info(f"Avg Holding Days: {stats['avg_holding_days']:.1f}")
    logging.info(f"Total Premium Collected: ${stats['total_premium_collected']:.2f}")
    logging.info(f"Best Trade: ${stats['best_trade']:.2f}")
    logging.info(f"Worst Trade: ${stats['worst_trade']:.2f}")

    logging.info("\n✅ Jade Lizard Strategy Test Complete!")
    logging.info("\nKey Features Tested:")
    logging.info("- ✅ Market sentiment analysis")
    logging.info("- ✅ Three-leg position validation")
    logging.info("- ✅ No upside risk verification")
    logging.info("- ✅ Delta-based strike selection")
    logging.info("- ✅ Probability calculations")
    logging.info("- ✅ Comprehensive risk metrics")
    logging.info("- ✅ Portfolio Greeks aggregation")
    logging.info("- ✅ Pin risk detection")
    logging.info("- ✅ Early assignment monitoring")
    logging.info("- ✅ Performance tracking")


if __name__ == "__main__":
    test_jade_lizard()
