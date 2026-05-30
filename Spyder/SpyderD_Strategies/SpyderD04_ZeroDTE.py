#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD04_ZeroDTE.py
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
from datetime import datetime, time, timedelta, date, UTC
from typing import Any
from dataclasses import dataclass, field
from enum import Enum, auto
import uuid
from collections import defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
import pytz

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (

    BaseStrategy, TradingSignal, SignalType, SignalStrength,
    StrategyPosition, EventManager, RiskProfile, Event, EventType
)
from Spyder.SpyderU_Utilities.SpyderU07_Constants import (
    ZERO_DTE_MAX_TRADES,
    MAX_OVERNIGHT_GAP,
    SPY_CONTRACT_MULTIPLIER
)

# ==============================================================================
# ENHANCED CONSTANTS (LEAN-based)
# ==============================================================================
# Entry timing (LEAN pattern: 1 minute after open)
ENTRY_DELAY_MINUTES = 1
MARKET_OPEN_TIME = time(9, 30)
MARKET_CLOSE_TIME = time(16, 0)
ENTRY_TIME = time(9, 31)  # 1 minute after open
EXIT_TIME = time(15, 50)  # 10 minutes before close

# Strike selection
OTM_STRIKE_OFFSET = 2  # $2 OTM for 0DTE
DELTA_TARGET_PUT = -0.20  # Target delta for short puts
DELTA_TARGET_CALL = 0.20  # Target delta for short calls

# Position management
MAX_CONCURRENT_POSITIONS = 2  # Max 0DTE positions
MIN_PREMIUM = 0.50  # Minimum premium to collect
PROFIT_TARGET_PERCENT = 0.25  # Close at 25% profit
STOP_LOSS_PERCENT = 2.00  # Stop at 200% loss
TIME_STOP_HOUR = 15  # Close all by 3 PM

# Market filters
MIN_VOLUME = 50000000  # Minimum SPY volume
MAX_VIX = 30  # Maximum VIX level
MIN_IVR = 30  # Minimum IV rank
OPTION_CHAIN_CACHE_TTL_SECONDS = 30.0
IV_HISTORY_LOOKBACK_DAYS = 365

# Runtime profiles
DEFAULT_0DTE_PROFILE = 'classic'
MARK_SPY_PAPER_PROFILE = 'mark_spy_paper'

_CLASSIC_0DTE_RUNTIME_CONFIG = {
    'symbol': 'SPY',
    'profile': DEFAULT_0DTE_PROFILE,
    'entry_delay_minutes': ENTRY_DELAY_MINUTES,
    'entry_window_end': time(12, 0),
    'time_stop': time(TIME_STOP_HOUR, 0),
    'max_daily_trades': ZERO_DTE_MAX_TRADES,
    'max_positions': MAX_CONCURRENT_POSITIONS,
    'spread_width_points': 5.0,
    'short_delta_min': DELTA_TARGET_CALL,
    'short_delta_max': DELTA_TARGET_CALL,
    'short_delta_target': DELTA_TARGET_CALL,
    'min_premium': MIN_PREMIUM,
    'single_spread_credit_ratio': 0.20,
    'condor_credit_ratio': 0.15,
    'profit_target': PROFIT_TARGET_PERCENT,
    'stop_loss': STOP_LOSS_PERCENT,
    'threat_buffer': 1.0,
    'min_probability_profit': 0.60,
    'min_setup_score': 40,
    'min_iv_rank': MIN_IVR,
    'max_vix': MAX_VIX,
    'prefer_delta_selection': False,
}

_PROFILE_OVERRIDES = {
    MARK_SPY_PAPER_PROFILE: {
        'profile': MARK_SPY_PAPER_PROFILE,
        'symbol': 'SPY',
        'entry_delay_minutes': 2,
        'entry_window_end': time(14, 30),
        'time_stop': time(15, 15),
        'max_daily_trades': 8,
        'max_positions': 4,
        'spread_width_points': 1.0,
        'short_delta_min': 0.07,
        'short_delta_max': 0.20,
        'short_delta_target': 0.12,
        'min_premium': 0.20,
        'single_spread_credit_ratio': 0.35,
        'condor_credit_ratio': 0.20,
        'profit_target': 0.30,
        'stop_loss': 1.25,
        'threat_buffer': 0.35,
        'min_probability_profit': 0.60,
        'min_setup_score': 40,
        'min_iv_rank': MIN_IVR,
        'max_vix': MAX_VIX,
        'prefer_delta_selection': True,
    },
}


def _coerce_intraday_time(value: Any, fallback: time) -> time:
    """Normalize config values to an intraday time object."""
    if isinstance(value, time):
        return value

    text = str(value or '').strip()
    if not text:
        return fallback

    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue

    return fallback


def build_zero_dte_runtime_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolve the runtime configuration for the 0DTE strategy."""
    raw = dict(config or {})
    requested_profile = str(raw.get('profile') or DEFAULT_0DTE_PROFILE).strip().lower()

    resolved = dict(_CLASSIC_0DTE_RUNTIME_CONFIG)
    resolved.update(_PROFILE_OVERRIDES.get(requested_profile, {}))

    override_keys = (
        'symbol',
        'entry_delay_minutes',
        'max_daily_trades',
        'max_positions',
        'spread_width_points',
        'short_delta_min',
        'short_delta_max',
        'short_delta_target',
        'min_premium',
        'single_spread_credit_ratio',
        'condor_credit_ratio',
        'profit_target',
        'stop_loss',
        'threat_buffer',
        'min_probability_profit',
        'min_setup_score',
        'min_iv_rank',
        'max_vix',
        'prefer_delta_selection',
    )
    for key in override_keys:
        if key in raw and raw[key] is not None:
            resolved[key] = raw[key]

    resolved['profile'] = resolved.get('profile') or DEFAULT_0DTE_PROFILE
    resolved['symbol'] = str(resolved.get('symbol') or 'SPY').upper()
    resolved['entry_delay_minutes'] = int(resolved.get('entry_delay_minutes', ENTRY_DELAY_MINUTES))
    resolved['max_daily_trades'] = int(resolved.get('max_daily_trades', ZERO_DTE_MAX_TRADES))
    resolved['max_positions'] = int(resolved.get('max_positions', MAX_CONCURRENT_POSITIONS))
    resolved['spread_width_points'] = float(resolved.get('spread_width_points', 5.0))
    resolved['short_delta_min'] = float(resolved.get('short_delta_min', DELTA_TARGET_CALL))
    resolved['short_delta_max'] = float(resolved.get('short_delta_max', DELTA_TARGET_CALL))
    resolved['short_delta_target'] = float(resolved.get('short_delta_target', DELTA_TARGET_CALL))
    resolved['min_premium'] = float(resolved.get('min_premium', MIN_PREMIUM))
    resolved['single_spread_credit_ratio'] = float(resolved.get('single_spread_credit_ratio', 0.20))
    resolved['condor_credit_ratio'] = float(resolved.get('condor_credit_ratio', 0.15))
    resolved['profit_target'] = float(resolved.get('profit_target', PROFIT_TARGET_PERCENT))
    resolved['stop_loss'] = float(resolved.get('stop_loss', STOP_LOSS_PERCENT))
    resolved['threat_buffer'] = float(resolved.get('threat_buffer', 1.0))
    resolved['min_probability_profit'] = float(resolved.get('min_probability_profit', 0.60))
    resolved['min_setup_score'] = int(resolved.get('min_setup_score', 40))
    resolved['min_iv_rank'] = float(resolved.get('min_iv_rank', MIN_IVR))
    resolved['max_vix'] = float(resolved.get('max_vix', MAX_VIX))
    resolved['prefer_delta_selection'] = bool(resolved.get('prefer_delta_selection', False))
    resolved['entry_window_end'] = _coerce_intraday_time(
        raw.get('entry_window_end', resolved.get('entry_window_end')),
        resolved.get('entry_window_end', time(12, 0)),
    )
    resolved['time_stop'] = _coerce_intraday_time(
        raw.get('time_stop', resolved.get('time_stop')),
        resolved.get('time_stop', time(TIME_STOP_HOUR, 0)),
    )
    return resolved

# ==============================================================================
# ENUMS
# ==============================================================================
class ZeroDTEStrategy(Enum):
    """0DTE strategy types"""
    SHORT_PUT = auto()
    SHORT_CALL = auto()
    IRON_CONDOR = auto()
    IRON_BUTTERFLY = auto()
    CREDIT_SPREAD = auto()


ZeroDTEStrategyType = ZeroDTEStrategy

class ZeroDTEState(Enum):
    """0DTE position states"""
    PENDING = auto()
    ACTIVE = auto()
    PROFIT_TARGET = auto()
    STOP_LOSS = auto()
    TIME_STOP = auto()
    EXPIRED = auto()
    CLOSED = auto()

class MarketPhase(Enum):
    """Intraday market phases"""
    PRE_OPEN = auto()
    OPENING = auto()
    MORNING = auto()
    MIDDAY = auto()
    AFTERNOON = auto()
    CLOSING = auto()
    AFTER_HOURS = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ZeroDTEPosition:
    """0DTE position tracking"""
    position_id: str
    strategy_type: ZeroDTEStrategyType | None
    entry_time: datetime
    expiry_date: date
    strikes: dict[str, float]  # e.g., {'short_put': 445, 'long_put': 440}
    contracts: int
    entry_premium: float
    current_value: float = 0.0
    state: ZeroDTEState = ZeroDTEState.PENDING

    # P&L tracking
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0

    # Risk metrics
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0

    # Exit tracking
    exit_time: datetime | None = None
    exit_reason: str | None = None

    # Metadata
    entry_conditions: dict[str, Any] = field(default_factory=dict)

    @property
    def time_to_expiry(self) -> float:
        """Hours to expiry"""
        if self.expiry_date == date.today():
            close_time = datetime.combine(date.today(), MARKET_CLOSE_TIME)
            return max(0, (close_time - datetime.now(UTC)).total_seconds() / 3600)
        return 0

    @property
    def profit_percentage(self) -> float:
        """Current profit as percentage of max profit"""
        return self.unrealized_pnl / self.max_profit if self.max_profit > 0 else 0

@dataclass
class MarketConditions:
    """Intraday market conditions for 0DTE"""
    timestamp: datetime
    spot_price: float
    opening_price: float
    high_of_day: float
    low_of_day: float
    volume: int
    vix: float
    iv_rank: float
    market_phase: MarketPhase
    trend_direction: str  # 'up', 'down', 'sideways'
    momentum: float
    overnight_gap: float

    @property
    def gap_percentage(self) -> float:
        """Overnight gap as percentage"""
        return self.overnight_gap / self.opening_price if self.opening_price > 0 else 0

    @property
    def intraday_range(self) -> float:
        """Intraday price range"""
        return self.high_of_day - self.low_of_day

@dataclass
class ZeroDTESetup:
    """0DTE trade setup configuration"""
    strategy_type: ZeroDTEStrategyType
    strikes: dict[str, float]
    expiry: datetime
    contracts: int
    estimated_credit: float
    max_profit: float
    max_loss: float
    probability_profit: float
    entry_conditions: MarketConditions
    score: float  # Setup quality score

# ==============================================================================
# ZERO DTE STRATEGY CLASS
# ==============================================================================
class ZeroDTEStrategy(BaseStrategy):
    """
    Enhanced 0DTE strategy with LEAN patterns.

    Implements professional 0DTE trading with precise timing, risk management,
    and position lifecycle handling based on LEAN algorithm patterns.
    """

    def __init__(self, event_manager: EventManager, risk_profile: RiskProfile,
                 config: dict[str, Any]):
        """Initialize 0DTE strategy"""
        super().__init__("ZeroDTE", event_manager, risk_profile, config)

        # Configuration
        self.runtime_config = build_zero_dte_runtime_config(config)
        self.profile_name = str(self.runtime_config['profile'])
        self.symbol = str(self.runtime_config['symbol'])
        self.max_positions = int(self.runtime_config['max_positions'])
        self.max_daily_trades = int(self.runtime_config['max_daily_trades'])
        self.profit_target = float(self.runtime_config['profit_target'])
        self.stop_loss = float(self.runtime_config['stop_loss'])
        self.entry_delay_minutes = int(self.runtime_config['entry_delay_minutes'])
        self.entry_window_end = self.runtime_config['entry_window_end']
        self.time_stop = self.runtime_config['time_stop']
        self.spread_width_points = float(self.runtime_config['spread_width_points'])
        self.short_delta_min = float(self.runtime_config['short_delta_min'])
        self.short_delta_max = float(self.runtime_config['short_delta_max'])
        self.short_delta_target = float(self.runtime_config['short_delta_target'])
        self.min_premium = float(self.runtime_config['min_premium'])
        self.single_spread_credit_ratio = float(self.runtime_config['single_spread_credit_ratio'])
        self.condor_credit_ratio = float(self.runtime_config['condor_credit_ratio'])
        self.threat_buffer = float(self.runtime_config['threat_buffer'])
        self.min_probability_profit = float(self.runtime_config['min_probability_profit'])
        self.min_setup_score = int(self.runtime_config['min_setup_score'])
        self.min_iv_rank = float(self.runtime_config['min_iv_rank'])
        self.max_vix = float(self.runtime_config['max_vix'])
        self.prefer_delta_selection = bool(self.runtime_config['prefer_delta_selection'])

        # Timezone handling
        self.eastern_tz = pytz.timezone('US/Eastern')

        # Position tracking
        self.active_positions: dict[str, ZeroDTEPosition] = {}
        self.today_trades = 0
        self.last_trade_date: date | None = None

        # Market monitoring
        self.current_conditions: MarketConditions | None = None
        self.option_chain_cache: dict[str, pd.DataFrame] = {}
        self.option_chain_cache_time: dict[str, datetime] = {}
        self._tradier_client = None
        self._intraday_iv_history: list[tuple[datetime, float]] = []

        # Performance tracking
        self.daily_stats = {
            'trades_executed': 0,
            'trades_won': 0,
            'trades_lost': 0,
            'total_pnl': 0.0,
            'time_stops': 0,
            'profit_targets': 0,
            'stop_losses': 0,
            'expired_otm': 0
        }

        # Schedule entry check
        self._schedule_entry_check()

        self.logger.info(
            "ZeroDTEStrategy initialized with profile=%s symbol=%s",
            self.profile_name,
            self.symbol,
        )

    # ==========================================================================
    # REQUIRED ABSTRACT METHOD IMPLEMENTATIONS
    # ==========================================================================

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Generate 0DTE trading signals"""
        signals = []

        try:
            # Update market conditions
            self._update_market_conditions(market_data)

            # Check if we can trade 0DTE today
            if not self._can_trade_0dte():
                return signals

            # Check entry time window
            if not self._is_entry_time():
                return signals

            # Get 0DTE option chain
            option_chain = self._get_0dte_options(market_data)
            if option_chain.empty:
                return signals

            # Find best 0DTE setup
            setup = self._find_optimal_0dte_setup(option_chain)
            if setup and self._validate_setup(setup):
                signal = self._create_signal_from_setup(setup)
                if signal:
                    signals.append(signal)
                    self.logger.info("Generated 0DTE signal: %s", signal.signal_id)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'generate_signals',
                'market_data_shape': market_data.shape
            })

        return signals

    def validate_signal(self, signal: TradingSignal) -> bool:
        """Validate 0DTE signal"""
        try:
            # Check signal validity
            if not signal.is_valid():
                return False

            # Check 0DTE specific metadata
            setup_data = signal.metadata.get('setup_data')
            if not setup_data:
                return False

            # Validate expiry is today
            expiry = datetime.fromisoformat(setup_data['expiry'])
            if expiry.date() != date.today():
                return False

            # Validate premium
            if setup_data['estimated_credit'] < self.min_premium:
                return False

            # Validate probability
            if setup_data['probability_profit'] < self.min_probability_profit:
                return False

            # Check market conditions haven't changed significantly
            if self.current_conditions:
                if abs(self.current_conditions.spot_price - signal.entry_price) > 2:
                    return False

            return True

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'validate_signal',
                'signal_id': signal.signal_id
            })
            return False

    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Calculate position size for 0DTE"""
        try:
            # Get setup data
            setup_data = signal.metadata.get('setup_data', {})
            max_loss = setup_data.get('max_loss', 1000)

            # Risk-based sizing
            account_value = self.risk_profile.account_size
            max_risk = account_value * 0.005  # 0.5% risk for 0DTE

            contracts = int(max_risk / (max_loss * SPY_CONTRACT_MULTIPLIER))

            # Apply limits
            contracts = max(1, min(contracts, 5))  # 1-5 contracts for 0DTE

            # Reduce size based on market conditions
            if self.current_conditions:
                if self.current_conditions.vix > 25:
                    contracts = max(1, contracts // 2)
                if abs(self.current_conditions.gap_percentage) > 0.01:
                    contracts = max(1, contracts - 1)

            return contracts

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'calculate_position_size',
                'signal_id': signal.signal_id
            })
            return 1

    def should_exit_position(self, position: StrategyPosition,
                           market_data: pd.DataFrame) -> tuple[bool, str]:
        """Determine if 0DTE position should be exited"""
        try:
            # Get 0DTE position
            dte_position = self.active_positions.get(position.position_id)
            if not dte_position:
                return False, ""

            # Update position value
            self._update_position_value(dte_position, market_data)

            # Check profit target
            if dte_position.profit_percentage >= self.profit_target:
                return True, f"Profit target reached: {dte_position.profit_percentage:.1%}"

            # Check stop loss
            loss_pct = abs(dte_position.unrealized_pnl) / dte_position.max_loss
            if loss_pct >= self.stop_loss:
                return True, f"Stop loss triggered: {loss_pct:.1%}"

            # Check time stop
            current_time = datetime.now(self.eastern_tz).time()
            if current_time >= self.time_stop:
                return True, f"Time stop at {self.time_stop.strftime('%H:%M')}"

            # Check if position is threatened
            spot_price = market_data['close'].iloc[-1]
            if self._is_position_threatened(dte_position, spot_price):
                return True, "Position threatened by price movement"

            return False, ""

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'should_exit_position',
                'position_id': position.position_id
            })
            return False, ""

    # ==========================================================================
    # 0DTE SPECIFIC METHODS
    # ==========================================================================

    def _can_trade_0dte(self) -> bool:
        """Check if we can trade 0DTE today"""
        today = date.today()

        # Reset daily counter
        if self.last_trade_date != today:
            self.today_trades = 0
            self.last_trade_date = today
            self._reset_daily_stats()

        # Check daily trade limit
        if self.today_trades >= self.max_daily_trades:
            return False

        # Check active positions
        if len(self.active_positions) >= self.max_positions:
            return False

        # Check market conditions
        if not self.current_conditions:
            return False

        # Validate market filters
        if self.current_conditions.vix > self.max_vix:
            self.logger.debug("VIX too high: %s", self.current_conditions.vix)
            return False

        if self.current_conditions.iv_rank < self.min_iv_rank:
            self.logger.debug("IV rank too low: %s", self.current_conditions.iv_rank)
            return False

        if abs(self.current_conditions.gap_percentage) > MAX_OVERNIGHT_GAP:
            self.logger.debug(f"Overnight gap too large: {self.current_conditions.gap_percentage:.2%}")  # noqa: E501
            return False

        return True

    def _is_entry_time(self) -> bool:
        """Check if current time is valid for 0DTE entry"""
        current_time = datetime.now(self.eastern_tz).time()

        # Must be after entry delay
        entry_time = (
            datetime.combine(date.today(), MARKET_OPEN_TIME)
            + timedelta(minutes=self.entry_delay_minutes)
        ).time()

        return entry_time <= current_time <= self.entry_window_end

    def _get_tradier_client(self):
        """Create the Tradier client lazily so paper-safe startup stays cheap."""
        if self._tradier_client is not None:
            return self._tradier_client

        try:
            from Spyder.SpyderB_Broker.SpyderB40_TradierClient import create_tradier_client_from_env
        except Exception:
            self.logger.debug("Tradier client import unavailable for D04", exc_info=True)
            return None

        try:
            self._tradier_client = create_tradier_client_from_env()
        except Exception as exc:
            self.logger.warning("D04 could not create Tradier client: %s", exc)
            self._tradier_client = None

        return self._tradier_client

    @staticmethod
    def _extract_latest_scalar(
        market_data: pd.DataFrame,
        candidates: tuple[str, ...],
    ) -> float | None:
        """Return the latest numeric value for any matching column."""
        for candidate in candidates:
            if candidate not in market_data:
                continue

            series = market_data[candidate]
            if isinstance(series, pd.Series):
                series = series.dropna()
                if series.empty:
                    continue
                try:
                    return float(series.iloc[-1])
                except (TypeError, ValueError):
                    continue

            try:
                return float(series)
            except (TypeError, ValueError):
                continue

        return None

    def _fetch_live_quote_value(self, symbol: str) -> float | None:
        """Fetch a live quote scalar for a symbol when market data did not provide it."""
        client = self._get_tradier_client()
        if client is None:
            return None

        try:
            response = client.get_quotes([symbol])
        except Exception as exc:
            self.logger.warning("D04 quote fetch failed for %s: %s", symbol, exc)
            return None

        quote = response.get('quotes', {}).get('quote')
        if isinstance(quote, list):
            quote = quote[0] if quote else None
        if not isinstance(quote, dict):
            return None

        for quote_field in ('last', 'close', 'bid', 'ask', 'prevclose'):
            value = quote.get(quote_field)
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if numeric > 0:
                return numeric
        return None

    @staticmethod
    def _calculate_atm_iv(option_chain: pd.DataFrame, spot_price: float) -> float | None:
        """Approximate ATM IV from the nearest-strike 0DTE chain rows."""
        if option_chain.empty or 'strike' not in option_chain.columns or 'iv' not in option_chain.columns:
            return None

        iv_rows = option_chain.dropna(subset=['strike', 'iv']).copy()
        if iv_rows.empty:
            return None

        iv_rows['distance'] = (iv_rows['strike'].astype(float) - float(spot_price)).abs()
        nearest_distance = iv_rows['distance'].min()
        nearest_rows = iv_rows[iv_rows['distance'] == nearest_distance]
        if nearest_rows.empty:
            return None

        try:
            return float(nearest_rows['iv'].astype(float).median())
        except (TypeError, ValueError):
            return None

    def _calculate_iv_rank(self, current_iv: float | None) -> float:
        """Estimate IV rank from the rolling ATM-IV history when no direct IVR is supplied."""
        if current_iv is None:
            return 50.0

        now = datetime.now(UTC)
        cutoff = now - timedelta(days=IV_HISTORY_LOOKBACK_DAYS)

        def _as_utc(timestamp: datetime) -> datetime:
            if timestamp.tzinfo is None:
                return timestamp.replace(tzinfo=UTC)
            return timestamp.astimezone(UTC)

        history = [
            (_as_utc(timestamp), value)
            for timestamp, value in self._intraday_iv_history
            if _as_utc(timestamp) >= cutoff
        ]
        history.append((now, float(current_iv)))
        self._intraday_iv_history = history[-512:]

        iv_values = [value for _, value in self._intraday_iv_history]
        if len(iv_values) < 2:
            return 50.0

        iv_low = min(iv_values)
        iv_high = max(iv_values)
        if iv_high <= iv_low:
            return 50.0

        iv_rank = ((float(current_iv) - iv_low) / (iv_high - iv_low)) * 100.0
        return max(0.0, min(100.0, iv_rank))

    def _resolve_vix_value(self, market_data: pd.DataFrame) -> float:
        """Resolve current VIX from the market frame first, then live quotes."""
        direct_vix = self._extract_latest_scalar(market_data, ('vix', 'VIX', '^VIX'))
        if direct_vix is not None:
            return direct_vix

        live_vix = self._fetch_live_quote_value('VIX')
        if live_vix is not None:
            return live_vix

        if self.current_conditions is not None:
            return float(self.current_conditions.vix)

        return 20.0

    def _resolve_iv_rank(self, market_data: pd.DataFrame, current_iv: float | None) -> float:
        """Resolve IV rank from supplied data, otherwise derive it from ATM-IV history."""
        direct_iv_rank = self._extract_latest_scalar(market_data, ('iv_rank', 'IVR', 'ivr'))
        if direct_iv_rank is not None:
            if 0.0 <= direct_iv_rank <= 1.0:
                return direct_iv_rank * 100.0
            return direct_iv_rank

        return self._calculate_iv_rank(current_iv)

    def _update_market_conditions(self, market_data: pd.DataFrame) -> None:
        """Update intraday market conditions"""
        try:
            current_time = datetime.now(self.eastern_tz)
            current_price = market_data['close'].iloc[-1]

            # Get opening price (first bar of the day)
            today_data = market_data[market_data.index.date == date.today()]
            if today_data.empty:
                return

            opening_price = today_data['open'].iloc[0]
            high_of_day = today_data['high'].max()
            low_of_day = today_data['low'].min()
            total_volume = today_data['volume'].sum()

            # Calculate overnight gap
            yesterday_close = market_data[market_data.index.date < date.today()]['close'].iloc[-1]
            overnight_gap = opening_price - yesterday_close

            # Determine market phase
            market_phase = self._get_market_phase(current_time.time())

            # Simple trend detection
            sma_5 = market_data['close'].rolling(5).mean().iloc[-1]
            sma_20 = market_data['close'].rolling(20).mean().iloc[-1]

            if current_price > sma_5 > sma_20:
                trend_direction = 'up'
                momentum = (current_price - sma_20) / sma_20
            elif current_price < sma_5 < sma_20:
                trend_direction = 'down'
                momentum = (sma_20 - current_price) / sma_20
            else:
                trend_direction = 'sideways'
                momentum = 0.0

            option_chain = self._get_0dte_options(market_data)
            current_atm_iv = self._calculate_atm_iv(option_chain, current_price)

            # Create conditions object
            self.current_conditions = MarketConditions(
                timestamp=current_time,
                spot_price=current_price,
                opening_price=opening_price,
                high_of_day=high_of_day,
                low_of_day=low_of_day,
                volume=total_volume,
                vix=self._resolve_vix_value(market_data),
                iv_rank=self._resolve_iv_rank(market_data, current_atm_iv),
                market_phase=market_phase,
                trend_direction=trend_direction,
                momentum=momentum,
                overnight_gap=overnight_gap
            )

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_update_market_conditions'})

    def _get_market_phase(self, current_time: time) -> MarketPhase:
        """Determine current market phase"""
        if current_time < MARKET_OPEN_TIME:
            return MarketPhase.PRE_OPEN
        elif current_time < time(10, 0):
            return MarketPhase.OPENING
        elif current_time < time(12, 0):
            return MarketPhase.MORNING
        elif current_time < time(14, 0):
            return MarketPhase.MIDDAY
        elif current_time < time(15, 30):
            return MarketPhase.AFTERNOON
        elif current_time < MARKET_CLOSE_TIME:
            return MarketPhase.CLOSING
        else:
            return MarketPhase.AFTER_HOURS

    def _get_0dte_options(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """Get options expiring today"""
        expiration = date.today().isoformat()
        cache_key = f"{self.symbol}:{expiration}"
        cached = self.option_chain_cache.get(cache_key)
        cached_at = self.option_chain_cache_time.get(cache_key)
        now = datetime.now(UTC)

        if (
            cached is not None
            and cached_at is not None
            and (now - cached_at).total_seconds() <= OPTION_CHAIN_CACHE_TTL_SECONDS
        ):
            return cached.copy()

        client = self._get_tradier_client()
        if client is None:
            return cached.copy() if cached is not None else pd.DataFrame()

        try:
            chain = client.get_option_chain_with_greeks(self.symbol, expiration)
        except Exception as exc:
            self.logger.warning("D04 0DTE chain fetch failed for %s %s: %s", self.symbol, expiration, exc)
            return cached.copy() if cached is not None else pd.DataFrame()

        rows = []
        for contract in chain or []:
            rows.append(
                {
                    'symbol': str(getattr(contract, 'symbol', '')),
                    'underlying': str(getattr(contract, 'underlying', self.symbol)),
                    'strike': float(getattr(contract, 'strike', 0.0) or 0.0),
                    'expiration': str(getattr(contract, 'expiration', expiration)),
                    'option_type': self._normalize_option_type(getattr(contract, 'option_type', '')),
                    'bid': float(getattr(contract, 'bid', 0.0) or 0.0),
                    'ask': float(getattr(contract, 'ask', 0.0) or 0.0),
                    'last': float(getattr(contract, 'last', 0.0) or 0.0),
                    'mid': float(getattr(contract, 'mid', 0.0) or 0.0),
                    'volume': int(getattr(contract, 'volume', 0) or 0),
                    'open_interest': int(getattr(contract, 'open_interest', 0) or 0),
                    'delta': float(getattr(contract, 'delta', 0.0) or 0.0),
                    'gamma': float(getattr(contract, 'gamma', 0.0) or 0.0),
                    'theta': float(getattr(contract, 'theta', 0.0) or 0.0),
                    'vega': float(getattr(contract, 'vega', 0.0) or 0.0),
                    'iv': float(getattr(contract, 'iv', 0.0) or 0.0),
                }
            )

        option_chain = pd.DataFrame(rows)
        if not option_chain.empty and 'expiration' in option_chain.columns:
            option_chain = option_chain[option_chain['expiration'].astype(str) == expiration].reset_index(drop=True)

        self.option_chain_cache[cache_key] = option_chain
        self.option_chain_cache_time[cache_key] = now
        return option_chain.copy()

    def _find_optimal_0dte_setup(self, option_chain: pd.DataFrame) -> ZeroDTESetup | None:
        """Find optimal 0DTE setup based on market conditions"""
        try:
            if option_chain.empty or not self.current_conditions:
                return None

            spot_price = self.current_conditions.spot_price

            # Determine strategy based on market conditions
            if self.current_conditions.trend_direction == 'up':
                # Bullish: Short put spread or short put
                strategy_type = ZeroDTEStrategyType.SHORT_PUT
                strikes = self._find_put_spread_strikes(option_chain, spot_price)
            elif self.current_conditions.trend_direction == 'down':
                # Bearish: Short call spread or short call
                strategy_type = ZeroDTEStrategyType.SHORT_CALL
                strikes = self._find_call_spread_strikes(option_chain, spot_price)
            else:
                # Neutral: Iron condor or iron butterfly
                strategy_type = ZeroDTEStrategyType.IRON_CONDOR
                strikes = self._find_iron_condor_strikes(option_chain, spot_price)

            if not strikes:
                return None

            # Calculate setup metrics
            setup_metrics = self._calculate_setup_metrics(
                strategy_type, strikes, option_chain
            )

            if not setup_metrics:
                return None

            # Create setup
            setup = ZeroDTESetup(
                strategy_type=strategy_type,
                strikes=strikes,
                expiry=datetime.combine(date.today(), MARKET_CLOSE_TIME),
                contracts=1,  # Will be sized later
                estimated_credit=setup_metrics['credit'],
                max_profit=setup_metrics['max_profit'],
                max_loss=setup_metrics['max_loss'],
                probability_profit=setup_metrics['probability'],
                entry_conditions=self.current_conditions,
                score=self._score_setup(setup_metrics)
            )

            return setup

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_find_optimal_0dte_setup'})
            return None

    @staticmethod
    def _normalize_option_type(value: Any) -> str:
        """Normalize option-type strings from chain payloads."""
        text = str(value or '').strip().lower()
        if text.startswith('p'):
            return 'put'
        if text.startswith('c'):
            return 'call'
        return text

    def _select_short_strike_from_chain(
        self,
        option_chain: pd.DataFrame,
        option_type: str,
    ) -> float | None:
        """Select a short strike using the configured delta band when available."""
        if option_chain.empty or 'strike' not in option_chain.columns or 'delta' not in option_chain.columns:
            return None

        option_col = 'option_type' if 'option_type' in option_chain.columns else 'type' if 'type' in option_chain.columns else None
        if not option_col:
            return None

        candidates = option_chain.copy()
        candidates = candidates[candidates[option_col].map(self._normalize_option_type) == option_type]
        if candidates.empty:
            return None

        candidates = candidates.dropna(subset=['strike', 'delta']).copy()
        if candidates.empty:
            return None

        candidates['abs_delta'] = candidates['delta'].astype(float).abs()
        band = candidates[
            (candidates['abs_delta'] >= self.short_delta_min)
            & (candidates['abs_delta'] <= self.short_delta_max)
        ].copy()
        if band.empty:
            if not self.prefer_delta_selection:
                return None
            band = candidates.copy()

        band['delta_distance'] = (band['abs_delta'] - self.short_delta_target).abs()
        band = band.sort_values(
            by=['delta_distance', 'strike'],
            ascending=[True, option_type == 'put'],
        )
        return float(band.iloc[0]['strike'])

    def _resolve_protective_strike(
        self,
        option_chain: pd.DataFrame,
        short_strike: float,
        option_type: str,
    ) -> float:
        """Resolve the long protective strike from the chain or a fallback width."""
        width = max(1.0, float(self.spread_width_points))
        fallback = short_strike - width if option_type == 'put' else short_strike + width
        if option_chain.empty or 'strike' not in option_chain.columns:
            return fallback

        option_col = 'option_type' if 'option_type' in option_chain.columns else 'type' if 'type' in option_chain.columns else None
        if not option_col:
            return fallback

        strikes = option_chain.copy()
        strikes = strikes[strikes[option_col].map(self._normalize_option_type) == option_type]
        if strikes.empty:
            return fallback

        available_strikes = sorted({float(strike) for strike in strikes['strike'].dropna().tolist()})
        if not available_strikes:
            return fallback

        target = short_strike - width if option_type == 'put' else short_strike + width
        if option_type == 'put':
            candidates = [strike for strike in available_strikes if strike < short_strike]
            if not candidates:
                return fallback
            below_target = [strike for strike in candidates if strike <= target]
            return max(below_target) if below_target else max(candidates)

        candidates = [strike for strike in available_strikes if strike > short_strike]
        if not candidates:
            return fallback
        above_target = [strike for strike in candidates if strike >= target]
        return min(above_target) if above_target else min(candidates)

    def _find_put_spread_strikes(self, option_chain: pd.DataFrame,
                                spot_price: float) -> dict[str, float] | None:
        """Find strikes for put spread"""
        short_put = self._select_short_strike_from_chain(option_chain, 'put')
        if short_put is not None:
            long_put = self._resolve_protective_strike(option_chain, short_put, 'put')
        else:
            short_put = round(spot_price - OTM_STRIKE_OFFSET)
            long_put = short_put - max(1.0, float(self.spread_width_points))

        return {
            'short_put': float(short_put),
            'long_put': float(long_put)
        }

    def _find_call_spread_strikes(self, option_chain: pd.DataFrame,
                                 spot_price: float) -> dict[str, float] | None:
        """Find strikes for call spread"""
        short_call = self._select_short_strike_from_chain(option_chain, 'call')
        if short_call is not None:
            long_call = self._resolve_protective_strike(option_chain, short_call, 'call')
        else:
            short_call = round(spot_price + OTM_STRIKE_OFFSET)
            long_call = short_call + max(1.0, float(self.spread_width_points))

        return {
            'short_call': float(short_call),
            'long_call': float(long_call)
        }

    def _find_iron_condor_strikes(self, option_chain: pd.DataFrame,
                                 spot_price: float) -> dict[str, float] | None:
        """Find strikes for iron condor"""
        short_put = self._select_short_strike_from_chain(option_chain, 'put')
        short_call = self._select_short_strike_from_chain(option_chain, 'call')
        if short_put is not None and short_call is not None:
            return {
                'long_put': float(self._resolve_protective_strike(option_chain, short_put, 'put')),
                'short_put': float(short_put),
                'short_call': float(short_call),
                'long_call': float(self._resolve_protective_strike(option_chain, short_call, 'call')),
            }

        return {
            'long_put': float(round(spot_price - 7)),
            'short_put': float(round(spot_price - 2)),
            'short_call': float(round(spot_price + 2)),
            'long_call': float(round(spot_price + 7))
        }

    def _calculate_setup_metrics(self, strategy_type: ZeroDTEStrategyType,
                               strikes: dict[str, float],
                               option_chain: pd.DataFrame) -> dict[str, Any] | None:
        """Calculate metrics for 0DTE setup"""
        # Simplified calculation - would use actual option prices

        if strategy_type == ZeroDTEStrategyType.SHORT_PUT:
            spread_width = strikes['short_put'] - strikes['long_put']
            credit = spread_width * self.single_spread_credit_ratio
            max_profit = credit
            max_loss = spread_width - credit
            probability = 0.75  # Simplified

        elif strategy_type == ZeroDTEStrategyType.SHORT_CALL:
            spread_width = strikes['long_call'] - strikes['short_call']
            credit = spread_width * self.single_spread_credit_ratio
            max_profit = credit
            max_loss = spread_width - credit
            probability = 0.75  # Simplified

        elif strategy_type == ZeroDTEStrategyType.IRON_CONDOR:
            put_width = strikes['short_put'] - strikes['long_put']
            call_width = strikes['long_call'] - strikes['short_call']
            credit = (put_width + call_width) * self.condor_credit_ratio
            max_profit = credit
            max_loss = max(put_width, call_width) - credit
            probability = 0.70  # Simplified

        else:
            return None

        return {
            'credit': credit,
            'max_profit': max_profit,
            'max_loss': max_loss,
            'probability': probability,
            'risk_reward': max_profit / max_loss if max_loss > 0 else 0
        }

    def _score_setup(self, metrics: dict[str, Any]) -> float:
        """Score 0DTE setup quality"""
        score = 0.0

        premium_floor = max(0.01, float(self.min_premium))

        # Credit quality
        if metrics['credit'] >= premium_floor * 2.0:
            score += 30
        elif metrics['credit'] >= premium_floor * 1.5:
            score += 20
        elif metrics['credit'] >= premium_floor:
            score += 10

        # Risk/reward ratio
        if metrics['risk_reward'] >= 0.33:
            score += 30
        elif metrics['risk_reward'] >= 0.25:
            score += 20
        elif metrics['risk_reward'] >= 0.20:
            score += 10

        # Probability of profit
        if metrics['probability'] >= 0.80:
            score += 30
        elif metrics['probability'] >= 0.70:
            score += 20
        elif metrics['probability'] >= 0.60:
            score += 10

        # Market conditions bonus
        if self.current_conditions:
            if self.current_conditions.market_phase == MarketPhase.MORNING:
                score += 10  # Prefer morning entries
            if abs(self.current_conditions.momentum) < 0.5:
                score += 5  # Prefer less volatile conditions

        return score

    def _validate_setup(self, setup: ZeroDTESetup) -> bool:
        """Validate 0DTE setup meets criteria"""
        # Minimum credit
        if setup.estimated_credit < self.min_premium:
            return False

        # Minimum probability
        if setup.probability_profit < self.min_probability_profit:
            return False

        # Minimum score
        if setup.score < self.min_setup_score:
            return False

        # Risk/reward check
        return not setup.max_profit / setup.max_loss < 0.2

    def _create_signal_from_setup(self, setup: ZeroDTESetup) -> TradingSignal | None:
        """Create trading signal from 0DTE setup"""
        try:
            # Calculate signal strength
            if setup.score >= 80:
                strength = SignalStrength.VERY_STRONG
            elif setup.score >= 60:
                strength = SignalStrength.STRONG
            elif setup.score >= 40:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK

            # Create signal
            signal = TradingSignal(
                signal_id=str(uuid.uuid4()),
                signal_type=SignalType.BUY,
                symbol=self.symbol,
                strength=strength,
                confidence=setup.probability_profit,
                entry_price=self.current_conditions.spot_price,
                stop_loss=0,  # Managed differently
                take_profit=0,  # Managed differently
                position_size=1,  # Will be calculated
                timestamp=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
                metadata={
                    'strategy': '0dte',
                    'profile': self.profile_name,
                    'setup_data': {
                        'strategy_type': setup.strategy_type.name,
                        'strikes': setup.strikes,
                        'expiry': setup.expiry.isoformat(),
                        'estimated_credit': setup.estimated_credit,
                        'max_profit': setup.max_profit,
                        'max_loss': setup.max_loss,
                        'probability_profit': setup.probability_profit,
                        'score': setup.score
                    }
                }
            )

            return signal

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_create_signal_from_setup'})
            return None

    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================

    def open_0dte_position(self, signal: TradingSignal) -> ZeroDTEPosition | None:
        """Open a new 0DTE position"""
        try:
            setup_data = signal.metadata['setup_data']

            # Create position
            position = ZeroDTEPosition(
                position_id=str(uuid.uuid4()),
                strategy_type=ZeroDTEStrategyType[setup_data['strategy_type']],
                entry_time=datetime.now(UTC),
                expiry_date=date.today(),
                strikes=setup_data['strikes'],
                contracts=signal.position_size,
                entry_premium=setup_data['estimated_credit'],
                max_profit=setup_data['max_profit'] * signal.position_size * SPY_CONTRACT_MULTIPLIER,  # noqa: E501
                max_loss=setup_data['max_loss'] * signal.position_size * SPY_CONTRACT_MULTIPLIER,
                state=ZeroDTEState.ACTIVE,
                entry_conditions={
                    'spot_price': signal.entry_price,
                    'vix': self.current_conditions.vix if self.current_conditions else 0,
                    'iv_rank': self.current_conditions.iv_rank if self.current_conditions else 0,
                    'gap': self.current_conditions.gap_percentage if self.current_conditions else 0
                }
            )

            # Add to tracking
            self.active_positions[position.position_id] = position
            self.today_trades += 1
            self.daily_stats['trades_executed'] += 1

            # Publish event
            self.event_manager.publish(Event.create(
                EventType.POSITION_OPENED,
                self.name,
                {
                    'position_id': position.position_id,
                    'strategy': '0dte',
                    'type': position.strategy_type.name,
                    'premium': position.entry_premium,
                    'max_profit': position.max_profit
                }
            ))

            self.logger.info("Opened 0DTE position: %s", position.position_id)
            return position

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'open_0dte_position',
                'signal_id': signal.signal_id
            })
            return None

    def _update_position_value(self, position: ZeroDTEPosition,
                             market_data: pd.DataFrame) -> None:
        """Update 0DTE position value"""
        try:
            current_price = market_data['close'].iloc[-1]

            # Simplified P&L calculation
            # In production, would use actual option prices

            if position.strategy_type == ZeroDTEStrategyType.SHORT_PUT:
                short_strike = position.strikes.get('short_put', 0)
                if current_price < short_strike:
                    # ITM - losing money
                    intrinsic = short_strike - current_price
                    position.unrealized_pnl = -intrinsic * position.contracts * SPY_CONTRACT_MULTIPLIER  # noqa: E501
                else:
                    # OTM - keeping premium
                    time_decay = position.time_to_expiry / 6.5  # Trading hours
                    position.unrealized_pnl = position.entry_premium * (1 - time_decay) * position.contracts * SPY_CONTRACT_MULTIPLIER  # noqa: E501

            elif position.strategy_type == ZeroDTEStrategyType.SHORT_CALL:
                short_strike = position.strikes.get('short_call', 0)
                if current_price > short_strike:
                    # ITM - losing money
                    intrinsic = current_price - short_strike
                    position.unrealized_pnl = -intrinsic * position.contracts * SPY_CONTRACT_MULTIPLIER  # noqa: E501
                else:
                    # OTM - keeping premium
                    time_decay = position.time_to_expiry / 6.5  # Trading hours
                    position.unrealized_pnl = position.entry_premium * (1 - time_decay) * position.contracts * SPY_CONTRACT_MULTIPLIER  # noqa: E501

            # Cap P&L at max profit/loss
            position.unrealized_pnl = max(-position.max_loss,
                                        min(position.max_profit, position.unrealized_pnl))

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_position_value',
                'position_id': position.position_id
            })

    def _is_position_threatened(self, position: ZeroDTEPosition, spot_price: float) -> bool:
        """Check if position is threatened by price movement"""
        threat_buffer = self.threat_buffer

        if position.strategy_type == ZeroDTEStrategyType.SHORT_PUT:
            short_strike = position.strikes.get('short_put', 0)
            return spot_price <= short_strike + threat_buffer

        elif position.strategy_type == ZeroDTEStrategyType.SHORT_CALL:
            short_strike = position.strikes.get('short_call', 0)
            return spot_price >= short_strike - threat_buffer

        elif position.strategy_type == ZeroDTEStrategyType.IRON_CONDOR:
            short_put = position.strikes.get('short_put', 0)
            short_call = position.strikes.get('short_call', 0)
            return (spot_price <= short_put + threat_buffer or
                   spot_price >= short_call - threat_buffer)

        return False

    def close_0dte_position(self, position_id: str, reason: str) -> bool:
        """Close 0DTE position"""
        try:
            position = self.active_positions.get(position_id)
            if not position:
                return False

            # Update final P&L
            position.realized_pnl = position.unrealized_pnl
            position.exit_time = datetime.now(UTC)
            position.exit_reason = reason

            # Update state based on reason
            if "profit target" in reason.lower():
                position.state = ZeroDTEState.PROFIT_TARGET
                self.daily_stats['profit_targets'] += 1
            elif "stop loss" in reason.lower():
                position.state = ZeroDTEState.STOP_LOSS
                self.daily_stats['stop_losses'] += 1
            elif "time stop" in reason.lower():
                position.state = ZeroDTEState.TIME_STOP
                self.daily_stats['time_stops'] += 1
            else:
                position.state = ZeroDTEState.CLOSED

            # Update daily stats
            if position.realized_pnl > 0:
                self.daily_stats['trades_won'] += 1
            else:
                self.daily_stats['trades_lost'] += 1

            self.daily_stats['total_pnl'] += position.realized_pnl

            # Remove from active
            del self.active_positions[position_id]

            # Publish event
            self.event_manager.publish(Event.create(
                EventType.POSITION_CLOSED,
                self.name,
                {
                    'position_id': position_id,
                    'realized_pnl': position.realized_pnl,
                    'exit_reason': reason
                }
            ))

            self.logger.info(f"Closed 0DTE position {position_id}: PnL ${position.realized_pnl:.2f}")  # noqa: E501
            return True

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'close_0dte_position',
                'position_id': position_id
            })
            return False

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def _schedule_entry_check(self) -> None:
        """Schedule daily entry check at specified time"""
        # In production, would use proper scheduler
        # This is a placeholder
        entry_time = (
            datetime.combine(date.today(), MARKET_OPEN_TIME)
            + timedelta(minutes=self.entry_delay_minutes)
        ).time()
        self.logger.info("Scheduled 0DTE entry check at %s", entry_time)

    def _reset_daily_stats(self) -> None:
        """Reset daily statistics"""
        self.daily_stats = {
            'trades_executed': 0,
            'trades_won': 0,
            'trades_lost': 0,
            'total_pnl': 0.0,
            'time_stops': 0,
            'profit_targets': 0,
            'stop_losses': 0,
            'expired_otm': 0
        }

    def expire_positions(self) -> None:
        """Handle end-of-day expiration"""
        positions_to_expire = list(self.active_positions.keys())

        for position_id in positions_to_expire:
            position = self.active_positions[position_id]

            # Check if expired OTM
            if position.unrealized_pnl > 0:
                position.state = ZeroDTEState.EXPIRED
                self.daily_stats['expired_otm'] += 1
                reason = "Expired OTM"
            else:
                reason = "Expired ITM"

            self.close_0dte_position(position_id, reason)

    def get_strategy_summary(self) -> dict[str, Any]:
        """Get comprehensive strategy summary"""
        active_by_type = defaultdict(int)
        total_exposure = 0.0

        for position in self.active_positions.values():
            active_by_type[position.strategy_type.name] += 1
            total_exposure += position.max_loss

        win_rate = (self.daily_stats['trades_won'] /
                   self.daily_stats['trades_executed']
                   if self.daily_stats['trades_executed'] > 0 else 0)

        return {
            'strategy': 'ZeroDTE',
            'profile': self.profile_name,
            'state': self.state,
            'active_positions': len(self.active_positions),
            'today_trades': self.today_trades,
            'positions_by_type': dict(active_by_type),
            'total_exposure': total_exposure,
            'daily_stats': self.daily_stats.copy(),
            'win_rate': win_rate,
            'market_conditions': {
                'spot_price': self.current_conditions.spot_price if self.current_conditions else 0,
                'vix': self.current_conditions.vix if self.current_conditions else 0,
                'market_phase': self.current_conditions.market_phase.name if self.current_conditions else 'UNKNOWN'  # noqa: E501
            }
        }

# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":

    # Create components
    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000,
        max_position_size=0.01,
        max_portfolio_risk=0.05,
        max_loss_per_trade=0.005
    )

    config = {
        'max_positions': 2,
        'profit_target': 0.25,
        'stop_loss': 2.0,
        'entry_delay_minutes': 1
    }

    # Create strategy
    strategy = ZeroDTEStrategy(event_manager, risk_profile, config)

    # Start strategy
    strategy.start()

    # Create intraday market data
    current_time = datetime.now(UTC)
    market_open = current_time.replace(hour=9, minute=30, second=0)

    # Generate 5-minute bars from market open
    time_index = pd.date_range(
        start=market_open,
        end=current_time,
        freq='5min'
    )

    # Simulate intraday price movement
    base_price = 450
    prices = base_price + np.cumsum(np.random.randn(len(time_index)) * 0.2)

    market_data = pd.DataFrame({
        'open': prices + np.random.randn(len(time_index)) * 0.1,
        'high': prices + abs(np.random.randn(len(time_index)) * 0.2),
        'low': prices - abs(np.random.randn(len(time_index)) * 0.2),
        'close': prices,
        'volume': np.random.randint(1000000, 3000000, len(time_index))
    }, index=time_index)

    # Process market data
    signals = strategy.generate_signals(market_data)

    # Display results

    if signals:
        signal = signals[0]
        setup = signal.metadata.get('setup_data', {})

    # Get strategy summary
    summary = strategy.get_strategy_summary()

    # Stop strategy
    strategy.stop()

