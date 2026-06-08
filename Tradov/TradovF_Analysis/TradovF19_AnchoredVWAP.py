#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovF_Analysis
Module: TradovF19_AnchoredVWAP.py
Purpose: Enhanced VWAP with anchoring capabilities and trading signals

Author: Claude (Maestro)
Year Created: 2025
Last Updated: 2025-12-27

Module Description:
    This module provides advanced VWAP analysis with anchoring:
    - Anchored VWAP from significant events (earnings, FOMC, breakouts)
    - Multi-timeframe VWAP analysis
    - VWAP bands and deviation channels
    - VWAP-based trading signals
    - VWAP cross detection
    - Support/resistance identification from VWAP levels

    Developed by Brian Shannon, Anchored VWAP reveals the average price
    weighted by volume starting from a specific significant event.

References:
    - Brian Shannon's "Maximum Trading Gains With Anchored VWAP"
    - VWAP trading strategies for intraday momentum
    - TradingSim Anchored VWAP Strategies
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Any
from enum import Enum
from datetime import datetime, date, timedelta, UTC
from dataclasses import dataclass

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger

# ==============================================================================
# CONSTANTS
# ==============================================================================
STANDARD_DEVIATIONS = [1, 2, 3]  # For VWAP bands
DEFAULT_ANCHOR_LOOKBACK = 20    # Days to look back for anchor points

# ==============================================================================
# MODULE LOGGER
# ==============================================================================
logger = TradovLogger.get_logger(__name__)


# ==============================================================================
# ENUMS
# ==============================================================================
class AnchorType(Enum):
    """Types of anchor points for VWAP."""
    SESSION_START = "session_start"      # Traditional VWAP
    EARNINGS = "earnings"                 # Anchored to earnings date
    FOMC = "fomc"                        # Anchored to Fed announcement
    HIGH = "high"                        # Anchored to swing high
    LOW = "low"                          # Anchored to swing low
    BREAKOUT = "breakout"                # Anchored to breakout point
    GAP = "gap"                          # Anchored to gap open
    CUSTOM = "custom"                    # User-defined anchor
    WEEK_START = "week_start"            # Weekly VWAP
    MONTH_START = "month_start"          # Monthly VWAP


class VWAPSignal(Enum):
    """VWAP-based trading signals."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class PriceRelation(Enum):
    """Price position relative to VWAP."""
    FAR_ABOVE = "far_above"      # > 2 std dev above
    ABOVE = "above"              # > 1 std dev above
    AT_VWAP = "at_vwap"          # Within 0.5 std dev
    BELOW = "below"              # > 1 std dev below
    FAR_BELOW = "far_below"      # > 2 std dev below


class TrendState(Enum):
    """Trend state based on VWAP analysis."""
    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    RANGING = "ranging"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"


# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class AnchorPoint:
    """Definition of an anchor point."""
    anchor_type: AnchorType
    timestamp: datetime
    price: float
    description: str = ""
    significance: float = 1.0  # 0-1, higher = more significant

    def to_dict(self) -> dict[str, Any]:
        return {
            "anchor_type": self.anchor_type.value,
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "description": self.description,
            "significance": self.significance,
        }


@dataclass
class VWAPLevel:
    """Single VWAP calculation result."""
    anchor: AnchorPoint
    timestamp: datetime
    vwap: float
    upper_band_1: float  # +1 std dev
    upper_band_2: float  # +2 std dev
    lower_band_1: float  # -1 std dev
    lower_band_2: float  # -2 std dev
    std_dev: float
    cumulative_volume: float
    bars_since_anchor: int

    @property
    def bands(self) -> dict[str, float]:
        return {
            "vwap": self.vwap,
            "+1_std": self.upper_band_1,
            "+2_std": self.upper_band_2,
            "-1_std": self.lower_band_1,
            "-2_std": self.lower_band_2,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "anchor": self.anchor.to_dict(),
            "timestamp": self.timestamp.isoformat(),
            "vwap": self.vwap,
            "bands": self.bands,
            "std_dev": self.std_dev,
            "cumulative_volume": self.cumulative_volume,
        }


@dataclass
class VWAPAnalysis:
    """Complete VWAP analysis for a symbol."""
    symbol: str
    timestamp: datetime
    current_price: float
    primary_vwap: VWAPLevel  # Main VWAP (session or most significant anchor)
    anchored_vwaps: list[VWAPLevel]  # Multiple anchor points
    price_relation: PriceRelation
    signal: VWAPSignal
    trend_state: TrendState
    support_levels: list[float]
    resistance_levels: list[float]
    distance_from_vwap_percent: float
    momentum_strength: float  # -1 to 1

    @property
    def is_bullish(self) -> bool:
        return self.signal in [VWAPSignal.BUY, VWAPSignal.STRONG_BUY]

    @property
    def is_bearish(self) -> bool:
        return self.signal in [VWAPSignal.SELL, VWAPSignal.STRONG_SELL]

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "current_price": self.current_price,
            "primary_vwap": self.primary_vwap.to_dict(),
            "price_relation": self.price_relation.value,
            "signal": self.signal.value,
            "trend_state": self.trend_state.value,
            "support_levels": self.support_levels,
            "resistance_levels": self.resistance_levels,
            "distance_percent": self.distance_from_vwap_percent,
            "momentum": self.momentum_strength,
            "is_bullish": self.is_bullish,
            "is_bearish": self.is_bearish,
        }


@dataclass
class VWAPCrossEvent:
    """VWAP cross/breakout event."""
    symbol: str
    timestamp: datetime
    cross_type: str  # "above", "below"
    anchor_type: AnchorType
    cross_price: float
    vwap_price: float
    volume_confirmation: bool
    strength: float  # 0-1

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "cross_type": self.cross_type,
            "anchor_type": self.anchor_type.value,
            "cross_price": self.cross_price,
            "vwap_price": self.vwap_price,
            "volume_confirmation": self.volume_confirmation,
            "strength": self.strength,
        }


@dataclass
class VWAPTradingSetup:
    """VWAP-based trading setup."""
    symbol: str
    timestamp: datetime
    setup_type: str  # "pullback_to_vwap", "breakout", "rejection"
    direction: str   # "long", "short"
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    vwap_reference: float
    confidence: float
    rationale: str

    @property
    def risk_reward_ratio(self) -> float:
        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.target_1 - self.entry_price)
        return reward / risk if risk > 0 else 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "setup_type": self.setup_type,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "target_1": self.target_1,
            "target_2": self.target_2,
            "risk_reward": self.risk_reward_ratio,
            "confidence": self.confidence,
            "rationale": self.rationale,
        }


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class AnchoredVWAPCalculator:
    """
    Advanced VWAP calculator with anchoring capabilities.

    Features:
    - Session VWAP (traditional)
    - Anchored VWAP from any significant event
    - VWAP bands (standard deviation channels)
    - Multi-timeframe VWAP
    - VWAP cross detection
    - Trading signal generation

    Example:
        >>> calc = AnchoredVWAPCalculator()
        >>> analysis = calc.analyze(data, symbol="TRAD")
        >>> print(f"VWAP: ${analysis.primary_vwap.vwap:.2f}")
        >>> print(f"Signal: {analysis.signal.value}")
        >>>
        >>> # Anchored to earnings
        >>> earnings_anchor = AnchorPoint(
        ...     anchor_type=AnchorType.EARNINGS,
        ...     timestamp=datetime(2025, 1, 28, 16, 0),
        ...     price=450.0,
        ...     description="Q4 2024 Earnings"
        ... )
        >>> avwap = calc.calculate_anchored_vwap(data, earnings_anchor)
    """

    def __init__(
        self,
        standard_deviations: list[float] = None,
        anchor_lookback_days: int = DEFAULT_ANCHOR_LOOKBACK
    ):
        """
        Initialize VWAP Calculator.

        Args:
            standard_deviations: Std devs for bands (default: [1, 2])
            anchor_lookback_days: Days to look back for auto anchor detection
        """
        self.std_devs = standard_deviations or [1, 2]
        self.anchor_lookback = anchor_lookback_days

        # Cross event history
        self._cross_history: dict[str, list[VWAPCrossEvent]] = {}

        logger.info("AnchoredVWAPCalculator initialized")

    # ==========================================================================
    # CORE VWAP CALCULATIONS
    # ==========================================================================

    def calculate_session_vwap(
        self,
        data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate traditional session VWAP.

        Args:
            data: DataFrame with 'high', 'low', 'close', 'volume' columns

        Returns:
            DataFrame with VWAP and bands added
        """
        df = data.copy()

        # Calculate typical price
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3

        # Calculate VWAP
        df['pv'] = df['typical_price'] * df['volume']
        df['cumulative_pv'] = df['pv'].cumsum()
        df['cumulative_volume'] = df['volume'].cumsum()
        df['vwap'] = df['cumulative_pv'] / df['cumulative_volume']

        # Calculate standard deviation bands
        df['vwap_variance'] = (
            ((df['typical_price'] - df['vwap']) ** 2 * df['volume']).cumsum() /
            df['cumulative_volume']
        )
        df['vwap_std'] = np.sqrt(df['vwap_variance'])

        # Add bands
        for std in self.std_devs:
            df[f'vwap_upper_{std}'] = df['vwap'] + (std * df['vwap_std'])
            df[f'vwap_lower_{std}'] = df['vwap'] - (std * df['vwap_std'])

        return df

    def calculate_anchored_vwap(
        self,
        data: pd.DataFrame,
        anchor: AnchorPoint
    ) -> VWAPLevel:
        """
        Calculate Anchored VWAP from a specific point.

        Args:
            data: DataFrame with OHLCV data
            anchor: Anchor point to start VWAP calculation

        Returns:
            VWAPLevel with calculation results

        Example:
            >>> anchor = AnchorPoint(
            ...     anchor_type=AnchorType.EARNINGS,
            ...     timestamp=datetime(2025, 1, 28),
            ...     price=450.0
            ... )
            >>> vwap = calc.calculate_anchored_vwap(data, anchor)
            >>> print(f"Anchored VWAP: ${vwap.vwap:.2f}")
        """
        df = data.copy()

        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'datetime' in df.columns:
                df = df.set_index('datetime')
            elif 'date' in df.columns:
                df = df.set_index('date')

        # Filter data from anchor point
        anchor_time = anchor.timestamp
        if isinstance(anchor_time, datetime):
            df = df[df.index >= anchor_time]
        else:
            df = df[df.index >= pd.Timestamp(anchor_time)]

        if df.empty:
            return self._empty_vwap_level(anchor)

        # Calculate typical price
        typical_price = (df['high'] + df['low'] + df['close']) / 3

        # Calculate VWAP from anchor
        pv = typical_price * df['volume']
        cumulative_pv = pv.cumsum()
        cumulative_volume = df['volume'].cumsum()
        vwap = cumulative_pv / cumulative_volume

        # Calculate standard deviation
        variance = ((typical_price - vwap) ** 2 * df['volume']).cumsum() / cumulative_volume
        std_dev = np.sqrt(variance)

        # Get latest values
        latest_vwap = vwap.iloc[-1]
        latest_std = std_dev.iloc[-1] if not np.isnan(std_dev.iloc[-1]) else 0

        return VWAPLevel(
            anchor=anchor,
            timestamp=datetime.now(UTC),
            vwap=latest_vwap,
            upper_band_1=latest_vwap + latest_std,
            upper_band_2=latest_vwap + 2 * latest_std,
            lower_band_1=latest_vwap - latest_std,
            lower_band_2=latest_vwap - 2 * latest_std,
            std_dev=latest_std,
            cumulative_volume=cumulative_volume.iloc[-1],
            bars_since_anchor=len(df)
        )

    def calculate_multi_anchor_vwap(
        self,
        data: pd.DataFrame,
        anchors: list[AnchorPoint]
    ) -> list[VWAPLevel]:
        """
        Calculate VWAP from multiple anchor points.

        Useful for seeing how price relates to multiple significant levels.

        Args:
            data: DataFrame with OHLCV data
            anchors: List of anchor points

        Returns:
            List of VWAPLevel for each anchor
        """
        return [self.calculate_anchored_vwap(data, anchor) for anchor in anchors]

    def _empty_vwap_level(self, anchor: AnchorPoint) -> VWAPLevel:
        """Return empty VWAP level."""
        return VWAPLevel(
            anchor=anchor,
            timestamp=datetime.now(UTC),
            vwap=0,
            upper_band_1=0,
            upper_band_2=0,
            lower_band_1=0,
            lower_band_2=0,
            std_dev=0,
            cumulative_volume=0,
            bars_since_anchor=0
        )

    # ==========================================================================
    # ANCHOR POINT DETECTION
    # ==========================================================================

    def auto_detect_anchors(
        self,
        data: pd.DataFrame,
        include_swings: bool = True,
        include_volume_spikes: bool = True,
        include_gaps: bool = True
    ) -> list[AnchorPoint]:
        """
        Automatically detect significant anchor points.

        Args:
            data: DataFrame with OHLCV data
            include_swings: Include swing highs/lows
            include_volume_spikes: Include volume spike points
            include_gaps: Include gap opens

        Returns:
            List of detected AnchorPoint
        """
        anchors = []
        df = data.copy()

        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'datetime' in df.columns:
                df = df.set_index('datetime')

        # Detect swing highs/lows
        if include_swings:
            swing_high, swing_low = self._detect_swing_points(df)
            if swing_high is not None:
                anchors.append(AnchorPoint(
                    anchor_type=AnchorType.HIGH,
                    timestamp=swing_high['timestamp'],
                    price=swing_high['price'],
                    description=f"Swing High: ${swing_high['price']:.2f}",
                    significance=0.8
                ))
            if swing_low is not None:
                anchors.append(AnchorPoint(
                    anchor_type=AnchorType.LOW,
                    timestamp=swing_low['timestamp'],
                    price=swing_low['price'],
                    description=f"Swing Low: ${swing_low['price']:.2f}",
                    significance=0.8
                ))

        # Detect volume spikes
        if include_volume_spikes:
            volume_anchor = self._detect_volume_spike(df)
            if volume_anchor:
                anchors.append(volume_anchor)

        # Detect gaps
        if include_gaps:
            gap_anchor = self._detect_gap(df)
            if gap_anchor:
                anchors.append(gap_anchor)

        # Add week/month starts
        week_start = self._get_period_start(df, 'week')
        if week_start:
            anchors.append(AnchorPoint(
                anchor_type=AnchorType.WEEK_START,
                timestamp=week_start['timestamp'],
                price=week_start['price'],
                description="Week Start",
                significance=0.6
            ))

        return sorted(anchors, key=lambda x: x.significance, reverse=True)

    def _detect_swing_points(
        self,
        df: pd.DataFrame,
        lookback: int = 5
    ) -> tuple[dict | None, dict | None]:
        """Detect recent swing high and low."""
        if len(df) < lookback * 2:
            return None, None

        # Simple swing detection
        df['high'].rolling(lookback).max()
        df['low'].rolling(lookback).min()

        # Find most recent swing high
        swing_high_idx = df['high'].iloc[-lookback * 2:-lookback].idxmax()
        swing_high = {
            'timestamp': swing_high_idx if isinstance(swing_high_idx, datetime) else datetime.now(UTC),
            'price': df.loc[swing_high_idx, 'high']
        }

        # Find most recent swing low
        swing_low_idx = df['low'].iloc[-lookback * 2:-lookback].idxmin()
        swing_low = {
            'timestamp': swing_low_idx if isinstance(swing_low_idx, datetime) else datetime.now(UTC),
            'price': df.loc[swing_low_idx, 'low']
        }

        return swing_high, swing_low

    def _detect_volume_spike(
        self,
        df: pd.DataFrame,
        threshold: float = 2.0
    ) -> AnchorPoint | None:
        """Detect significant volume spike."""
        if len(df) < 20:
            return None

        avg_volume = df['volume'].rolling(20).mean()
        volume_ratio = df['volume'] / avg_volume

        # Find most recent spike above threshold
        spikes = df[volume_ratio > threshold]

        if spikes.empty:
            return None

        latest_spike = spikes.iloc[-1]
        spike_idx = spikes.index[-1]

        return AnchorPoint(
            anchor_type=AnchorType.BREAKOUT,
            timestamp=spike_idx if isinstance(spike_idx, datetime) else datetime.now(UTC),
            price=latest_spike['close'],
            description=f"Volume Spike ({volume_ratio.loc[spike_idx]:.1f}x)",
            significance=min(1.0, volume_ratio.loc[spike_idx] / 3)
        )

    def _detect_gap(
        self,
        df: pd.DataFrame,
        min_gap_percent: float = 0.5
    ) -> AnchorPoint | None:
        """Detect gap open."""
        if len(df) < 2:
            return None

        # Calculate gap
        prev_close = df['close'].shift(1)
        gap = (df['open'] - prev_close) / prev_close * 100

        # Find significant gaps
        significant_gaps = df[abs(gap) > min_gap_percent]

        if significant_gaps.empty:
            return None

        # Get most recent gap
        latest_gap = significant_gaps.iloc[-1]
        gap_idx = significant_gaps.index[-1]
        gap_size = gap.loc[gap_idx]

        return AnchorPoint(
            anchor_type=AnchorType.GAP,
            timestamp=gap_idx if isinstance(gap_idx, datetime) else datetime.now(UTC),
            price=latest_gap['open'],
            description=f"Gap {'Up' if gap_size > 0 else 'Down'} {abs(gap_size):.1f}%",
            significance=min(1.0, abs(gap_size) / 2)
        )

    def _get_period_start(
        self,
        df: pd.DataFrame,
        period: str
    ) -> dict | None:
        """Get start of period (week, month)."""
        if df.empty:
            return None

        if period == 'week':
            # Find Monday of current week
            today = date.today()
            monday = today - timedelta(days=today.weekday())

            # Find first bar on or after Monday
            mask = df.index >= pd.Timestamp(monday)
            if mask.any():
                first_bar = df[mask].iloc[0]
                idx = df[mask].index[0]
                return {
                    'timestamp': idx if isinstance(idx, datetime) else datetime.now(UTC),
                    'price': first_bar['open']
                }

        elif period == 'month':
            today = date.today()
            month_start = date(today.year, today.month, 1)

            mask = df.index >= pd.Timestamp(month_start)
            if mask.any():
                first_bar = df[mask].iloc[0]
                idx = df[mask].index[0]
                return {
                    'timestamp': idx if isinstance(idx, datetime) else datetime.now(UTC),
                    'price': first_bar['open']
                }

        return None

    # ==========================================================================
    # ANALYSIS & SIGNALS
    # ==========================================================================

    def analyze(
        self,
        data: pd.DataFrame,
        symbol: str,
        custom_anchors: list[AnchorPoint] | None = None
    ) -> VWAPAnalysis:
        """
        Perform complete VWAP analysis.

        Args:
            data: DataFrame with OHLCV data
            symbol: Stock symbol
            custom_anchors: Optional custom anchor points

        Returns:
            VWAPAnalysis with comprehensive analysis

        Example:
            >>> analysis = calc.analyze(data, "TRAD")
            >>> print(f"Signal: {analysis.signal.value}")
            >>> print(f"Trend: {analysis.trend_state.value}")
        """
        df = data.copy()

        # Get current price
        current_price = df['close'].iloc[-1]

        # Calculate session VWAP
        session_vwap_df = self.calculate_session_vwap(df)
        primary_vwap = self._create_vwap_level_from_df(
            session_vwap_df,
            AnchorPoint(
                anchor_type=AnchorType.SESSION_START,
                timestamp=df.index[0] if isinstance(df.index[0], datetime) else datetime.now(UTC),
                price=df['open'].iloc[0]
            )
        )

        # Auto-detect anchors if not provided
        if custom_anchors:
            anchors = custom_anchors
        else:
            anchors = self.auto_detect_anchors(df)

        # Calculate anchored VWAPs
        anchored_vwaps = [
            self.calculate_anchored_vwap(df, anchor)
            for anchor in anchors
        ]

        # Determine price relation
        price_relation = self._get_price_relation(
            current_price, primary_vwap
        )

        # Generate signal
        signal = self._generate_signal(
            current_price, primary_vwap, df
        )

        # Determine trend state
        trend_state = self._determine_trend(
            current_price, primary_vwap, anchored_vwaps
        )

        # Get support/resistance
        support, resistance = self._get_sr_levels(
            current_price, primary_vwap, anchored_vwaps
        )

        # Calculate distance
        distance = (
            (current_price - primary_vwap.vwap) / primary_vwap.vwap * 100
            if primary_vwap.vwap > 0 else 0
        )

        # Calculate momentum
        momentum = self._calculate_momentum(df, primary_vwap)

        return VWAPAnalysis(
            symbol=symbol,
            timestamp=datetime.now(UTC),
            current_price=current_price,
            primary_vwap=primary_vwap,
            anchored_vwaps=anchored_vwaps,
            price_relation=price_relation,
            signal=signal,
            trend_state=trend_state,
            support_levels=support,
            resistance_levels=resistance,
            distance_from_vwap_percent=distance,
            momentum_strength=momentum
        )

    def _create_vwap_level_from_df(
        self,
        df: pd.DataFrame,
        anchor: AnchorPoint
    ) -> VWAPLevel:
        """Create VWAPLevel from calculated DataFrame."""
        return VWAPLevel(
            anchor=anchor,
            timestamp=datetime.now(UTC),
            vwap=df['vwap'].iloc[-1],
            upper_band_1=df['vwap_upper_1'].iloc[-1] if 'vwap_upper_1' in df else 0,
            upper_band_2=df['vwap_upper_2'].iloc[-1] if 'vwap_upper_2' in df else 0,
            lower_band_1=df['vwap_lower_1'].iloc[-1] if 'vwap_lower_1' in df else 0,
            lower_band_2=df['vwap_lower_2'].iloc[-1] if 'vwap_lower_2' in df else 0,
            std_dev=df['vwap_std'].iloc[-1] if 'vwap_std' in df else 0,
            cumulative_volume=df['cumulative_volume'].iloc[-1] if 'cumulative_volume' in df else 0,
            bars_since_anchor=len(df)
        )

    def _get_price_relation(
        self,
        price: float,
        vwap: VWAPLevel
    ) -> PriceRelation:
        """Determine price position relative to VWAP."""
        if vwap.std_dev == 0:
            if price > vwap.vwap:
                return PriceRelation.ABOVE
            elif price < vwap.vwap:
                return PriceRelation.BELOW
            return PriceRelation.AT_VWAP

        z_score = (price - vwap.vwap) / vwap.std_dev

        if z_score > 2:
            return PriceRelation.FAR_ABOVE
        elif z_score > 1:
            return PriceRelation.ABOVE
        elif z_score < -2:
            return PriceRelation.FAR_BELOW
        elif z_score < -1:
            return PriceRelation.BELOW
        else:
            return PriceRelation.AT_VWAP

    def _generate_signal(
        self,
        price: float,
        vwap: VWAPLevel,
        df: pd.DataFrame
    ) -> VWAPSignal:
        """Generate trading signal based on VWAP analysis."""
        relation = self._get_price_relation(price, vwap)

        # Check for VWAP crosses
        if len(df) >= 2:
            prev_close = df['close'].iloc[-2]
            vwap_val = vwap.vwap

            # Bullish cross (price crosses above VWAP)
            if prev_close < vwap_val and price > vwap_val:
                return VWAPSignal.BUY

            # Bearish cross (price crosses below VWAP)
            if prev_close > vwap_val and price < vwap_val:
                return VWAPSignal.SELL

        # Position-based signals
        if relation == PriceRelation.FAR_ABOVE:
            return VWAPSignal.STRONG_SELL  # Extended, expect pullback
        elif relation == PriceRelation.FAR_BELOW:
            return VWAPSignal.STRONG_BUY   # Oversold, expect bounce
        elif relation == PriceRelation.ABOVE:
            return VWAPSignal.BUY          # Bullish, above VWAP
        elif relation == PriceRelation.BELOW:
            return VWAPSignal.SELL         # Bearish, below VWAP
        else:
            return VWAPSignal.NEUTRAL

    def _determine_trend(
        self,
        price: float,
        primary: VWAPLevel,
        anchored: list[VWAPLevel]
    ) -> TrendState:
        """Determine overall trend state."""
        # Count how many VWAPs price is above/below
        above_count = 0
        below_count = 0

        all_vwaps = [primary] + anchored

        for v in all_vwaps:
            if v.vwap > 0:
                if price > v.vwap:
                    above_count += 1
                else:
                    below_count += 1

        total = above_count + below_count
        if total == 0:
            return TrendState.RANGING

        above_ratio = above_count / total

        if above_ratio >= 0.8:
            return TrendState.STRONG_UPTREND
        elif above_ratio >= 0.6:
            return TrendState.UPTREND
        elif above_ratio <= 0.2:
            return TrendState.STRONG_DOWNTREND
        elif above_ratio <= 0.4:
            return TrendState.DOWNTREND
        else:
            return TrendState.RANGING

    def _get_sr_levels(
        self,
        price: float,
        primary: VWAPLevel,
        anchored: list[VWAPLevel]
    ) -> tuple[list[float], list[float]]:
        """Get support and resistance levels from VWAPs."""
        all_levels = []

        # Add primary VWAP levels
        all_levels.extend([
            primary.vwap,
            primary.upper_band_1,
            primary.upper_band_2,
            primary.lower_band_1,
            primary.lower_band_2
        ])

        # Add anchored VWAP levels
        for v in anchored:
            all_levels.append(v.vwap)

        # Filter valid levels
        valid_levels = [lvl for lvl in all_levels if lvl > 0]

        support = sorted([lvl for lvl in valid_levels if lvl < price], reverse=True)[:3]
        resistance = sorted([lvl for lvl in valid_levels if lvl > price])[:3]

        return support, resistance

    def _calculate_momentum(
        self,
        df: pd.DataFrame,
        vwap: VWAPLevel
    ) -> float:
        """Calculate momentum relative to VWAP."""
        if len(df) < 10:
            return 0

        # Calculate how price relates to VWAP over recent bars
        recent_closes = df['close'].tail(10)
        vwap_val = vwap.vwap

        above_count = (recent_closes > vwap_val).sum()
        momentum = (above_count / 10) * 2 - 1  # -1 to 1

        return momentum

    # ==========================================================================
    # CROSS DETECTION
    # ==========================================================================

    def detect_vwap_cross(
        self,
        data: pd.DataFrame,
        symbol: str,
        anchor: AnchorPoint | None = None
    ) -> VWAPCrossEvent | None:
        """
        Detect VWAP cross events.

        Args:
            data: DataFrame with OHLCV data
            symbol: Stock symbol
            anchor: Specific anchor (or use session VWAP)

        Returns:
            VWAPCrossEvent if cross detected, None otherwise
        """
        if len(data) < 2:
            return None

        # Calculate VWAP
        df = self.calculate_session_vwap(data)

        prev_close = df['close'].iloc[-2]
        curr_close = df['close'].iloc[-1]
        vwap_val = df['vwap'].iloc[-1]
        prev_vwap = df['vwap'].iloc[-2]

        # Check for cross
        cross_type = None
        if prev_close < prev_vwap and curr_close > vwap_val:
            cross_type = "above"
        elif prev_close > prev_vwap and curr_close < vwap_val:
            cross_type = "below"

        if cross_type is None:
            return None

        # Check volume confirmation
        avg_volume = df['volume'].rolling(20).mean().iloc[-1]
        volume_conf = df['volume'].iloc[-1] > avg_volume

        # Calculate strength
        distance = abs(curr_close - vwap_val)
        strength = min(1.0, distance / (vwap_val * 0.01))

        event = VWAPCrossEvent(
            symbol=symbol,
            timestamp=datetime.now(UTC),
            cross_type=cross_type,
            anchor_type=anchor.anchor_type if anchor else AnchorType.SESSION_START,
            cross_price=curr_close,
            vwap_price=vwap_val,
            volume_confirmation=volume_conf,
            strength=strength
        )

        # Store in history
        if symbol not in self._cross_history:
            self._cross_history[symbol] = []
        self._cross_history[symbol].append(event)

        return event

    # ==========================================================================
    # TRADING SETUPS
    # ==========================================================================

    def get_trading_setup(
        self,
        data: pd.DataFrame,
        symbol: str
    ) -> VWAPTradingSetup | None:
        """
        Generate VWAP-based trading setup.

        Args:
            data: DataFrame with OHLCV data
            symbol: Stock symbol

        Returns:
            VWAPTradingSetup if valid setup found

        Example:
            >>> setup = calc.get_trading_setup(data, "TRAD")
            >>> if setup:
            ...     print(f"Setup: {setup.setup_type}")
            ...     print(f"Entry: ${setup.entry_price:.2f}")
            ...     print(f"Stop: ${setup.stop_loss:.2f}")
        """
        analysis = self.analyze(data, symbol)

        if analysis.signal == VWAPSignal.NEUTRAL:
            return None

        current_price = analysis.current_price
        vwap = analysis.primary_vwap.vwap
        std = analysis.primary_vwap.std_dev

        # Determine setup type and direction
        if analysis.price_relation == PriceRelation.AT_VWAP:
            # Pullback to VWAP - potential entry
            if analysis.trend_state in [TrendState.UPTREND, TrendState.STRONG_UPTREND]:
                setup_type = "pullback_to_vwap"
                direction = "long"
                entry = current_price
                stop = vwap - std
                target1 = vwap + std
                target2 = vwap + 2 * std
            elif analysis.trend_state in [TrendState.DOWNTREND, TrendState.STRONG_DOWNTREND]:
                setup_type = "pullback_to_vwap"
                direction = "short"
                entry = current_price
                stop = vwap + std
                target1 = vwap - std
                target2 = vwap - 2 * std
            else:
                return None

        elif analysis.price_relation in [PriceRelation.FAR_ABOVE, PriceRelation.FAR_BELOW]:
            # Mean reversion setup
            if analysis.price_relation == PriceRelation.FAR_ABOVE:
                setup_type = "rejection"
                direction = "short"
                entry = current_price
                stop = current_price + std
                target1 = vwap + std
                target2 = vwap
            else:
                setup_type = "rejection"
                direction = "long"
                entry = current_price
                stop = current_price - std
                target1 = vwap - std
                target2 = vwap

        else:
            # Trend continuation
            cross = self.detect_vwap_cross(data, symbol)
            if cross and cross.volume_confirmation:
                if cross.cross_type == "above":
                    setup_type = "breakout"
                    direction = "long"
                    entry = current_price
                    stop = vwap - 0.5 * std
                    target1 = vwap + 1.5 * std
                    target2 = vwap + 2.5 * std
                else:
                    setup_type = "breakout"
                    direction = "short"
                    entry = current_price
                    stop = vwap + 0.5 * std
                    target1 = vwap - 1.5 * std
                    target2 = vwap - 2.5 * std
            else:
                return None

        # Calculate confidence
        confidence = 0.6
        if analysis.momentum_strength > 0.5 and direction == "long" or analysis.momentum_strength < -0.5 and direction == "short":  # noqa: E501
            confidence += 0.2

        rationale = (
            f"{setup_type.replace('_', ' ').title()} setup. "
            f"Price {analysis.price_relation.value} VWAP. "
            f"Trend: {analysis.trend_state.value}. "
            f"Momentum: {analysis.momentum_strength:.2f}"
        )

        return VWAPTradingSetup(
            symbol=symbol,
            timestamp=datetime.now(UTC),
            setup_type=setup_type,
            direction=direction,
            entry_price=entry,
            stop_loss=stop,
            target_1=target1,
            target_2=target2,
            vwap_reference=vwap,
            confidence=confidence,
            rationale=rationale
        )


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_anchored_vwap_calculator() -> AnchoredVWAPCalculator:
    """Create AnchoredVWAPCalculator with default settings."""
    return AnchoredVWAPCalculator()


# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":

    # Create sample intraday data
    np.random.seed(42)
    dates = pd.date_range("2025-01-27 09:30", periods=200, freq="5min")
    price_base = 450

    # Generate realistic price movement
    returns = np.random.randn(200) * 0.001
    prices = price_base * np.exp(returns.cumsum())

    data = pd.DataFrame({
        "open": prices + np.random.randn(200) * 0.1,
        "high": prices + np.abs(np.random.randn(200)) * 0.5,
        "low": prices - np.abs(np.random.randn(200)) * 0.5,
        "close": prices,
        "volume": np.random.randint(100000, 1000000, 200),
    }, index=dates)

    # Ensure high > low
    data["high"] = data[["open", "high", "close"]].max(axis=1)
    data["low"] = data[["open", "low", "close"]].min(axis=1)

    # Initialize calculator
    calc = AnchoredVWAPCalculator()

    # Test session VWAP
    vwap_df = calc.calculate_session_vwap(data)

    # Test anchored VWAP
    anchor = AnchorPoint(
        anchor_type=AnchorType.BREAKOUT,
        timestamp=dates[50],
        price=data['close'].iloc[50],
        description="Volume Breakout"
    )
    avwap = calc.calculate_anchored_vwap(data, anchor)

    # Test auto anchor detection
    anchors = calc.auto_detect_anchors(data)
    for _a in anchors[:5]:
        pass

    # Test full analysis
    analysis = calc.analyze(data, "TRAD")

    # Test trading setup
    setup = calc.get_trading_setup(data, "TRAD")
    if setup:
        pass
    else:
        pass
