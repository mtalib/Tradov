#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC13_IndexComponents.py
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
import time
import threading
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum, auto
import concurrent.futures

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager

SP500_UPDATE_INTERVAL = 3600  # Update component list hourly
PRICE_UPDATE_INTERVAL = 60    # Update prices every minute
BREADTH_CALC_INTERVAL = 5     # Calculate breadth every 5 seconds

# Breadth Thresholds
EXTREME_BREADTH_HIGH = 0.80   # 80% advancing
EXTREME_BREADTH_LOW = 0.20    # 20% advancing
STRONG_BREADTH = 0.65
WEAK_BREADTH = 0.35

# Sector Analysis
SECTOR_ROTATION_THRESHOLD = 0.15  # 15% outperformance for rotation signal
SECTOR_COUNT = 11  # Number of S&P sectors

# Performance Analysis
MOMENTUM_PERIODS = [1, 5, 20, 60, 252]  # 1D, 1W, 1M, 3M, 1Y
TOP_MOVERS_COUNT = 20

# ==============================================================================
# ENUMS
# ==============================================================================
class BreadthSignal(Enum):
    """Market breadth signals"""
    EXTREMELY_BULLISH = auto()
    BULLISH = auto()
    NEUTRAL = auto()
    BEARISH = auto()
    EXTREMELY_BEARISH = auto()

class SectorRotation(Enum):
    """Sector rotation phases"""
    RISK_ON = "RISK_ON"          # Tech, Consumer Disc leading
    DEFENSIVE = "DEFENSIVE"       # Utilities, Staples leading
    CYCLICAL = "CYCLICAL"        # Financials, Industrials leading
    COMMODITY = "COMMODITY"       # Energy, Materials leading
    MIXED = "MIXED"

class MarketRegime(Enum):
    """Market regime based on internals"""
    STRONG_UPTREND = auto()
    UPTREND = auto()
    CHOPPY = auto()
    DOWNTREND = auto()
    STRONG_DOWNTREND = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ComponentStock:
    """S&P 500 component stock data"""
    symbol: str
    name: str
    sector: str
    market_cap: float
    weight: float  # Index weight
    price: float
    change_pct: float
    volume: int
    avg_volume: int
    relative_strength: float
    momentum_scores: dict[int, float] = field(default_factory=dict)

@dataclass
class BreadthMetrics:
    """Market breadth metrics"""
    timestamp: datetime
    advancing: int
    declining: int
    unchanged: int
    advance_decline_ratio: float
    advance_decline_line: float
    percent_above_ma50: float
    percent_above_ma200: float
    new_highs: int
    new_lows: int
    high_low_ratio: float
    mcclellan_oscillator: float
    breadth_thrust: float
    signal: BreadthSignal

@dataclass
class SectorMetrics:
    """Sector performance metrics"""
    sector: str
    performance_1d: float
    performance_5d: float
    performance_1m: float
    relative_strength: float
    advancing_pct: float
    volume_ratio: float  # Current vs average
    leading_stocks: list[str]
    lagging_stocks: list[str]

@dataclass
class MarketInternals:
    """Comprehensive market internals"""
    timestamp: datetime
    breadth: BreadthMetrics
    sectors: list[SectorMetrics]
    market_regime: MarketRegime
    rotation_signal: SectorRotation
    strength_score: float  # 0-100
    momentum_leaders: list[ComponentStock]
    momentum_laggards: list[ComponentStock]

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class IndexComponentAnalyzer:
    """
    S&P 500 index component analyzer for market breadth and internals.

    This class provides comprehensive analysis of index components including
    breadth calculations, sector rotation detection, and identification of
    market leaders and laggards.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance

    Example:
        >>> analyzer = IndexComponentAnalyzer()
        >>> internals = analyzer.get_market_internals()
        >>> if internals.breadth.signal == BreadthSignal.EXTREMELY_BULLISH:
        >>>     print("Strong market breadth - favorable for bullish strategies")
    """

    def __init__(self, config: dict | None = None):
        """Initialize index component analyzer."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()

        # Configuration
        self.config = config or {}

        # Component data storage
        self.components: dict[str, ComponentStock] = {}
        self.sector_components: dict[str, list[str]] = defaultdict(list)
        self.historical_breadth: list[BreadthMetrics] = []
        self.price_history: dict[str, pd.DataFrame] = {}

        # Market internals tracking
        self.advance_decline_line: float = 10000.0  # Starting value
        self.mcclellan_sum: float = 0.0
        self.breadth_thrust_values: list[float] = []

        # Threading
        self._lock = threading.Lock()
        self._update_thread: threading.Thread | None = None
        self._running = False
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

        # Initialize components
        self._load_sp500_components()

        self.logger.info(f"{self.__class__.__name__} initialized")

    # ==========================================================================
    # PUBLIC METHODS - MARKET INTERNALS
    # ==========================================================================
    def get_market_internals(self) -> MarketInternals:
        """
        Get comprehensive market internals analysis.

        Returns:
            MarketInternals with current analysis
        """
        # Calculate breadth metrics
        breadth = self.calculate_breadth_metrics()

        # Analyze sectors
        sectors = self.analyze_sectors()

        # Determine market regime
        regime = self._determine_market_regime(breadth, sectors)

        # Detect sector rotation
        rotation = self._detect_sector_rotation(sectors)

        # Calculate market strength
        strength = self._calculate_market_strength(breadth, sectors)

        # Get momentum leaders/laggards
        leaders, laggards = self.get_momentum_leaders_laggards(20)

        return MarketInternals(
            timestamp=datetime.now(),
            breadth=breadth,
            sectors=sectors,
            market_regime=regime,
            rotation_signal=rotation,
            strength_score=strength,
            momentum_leaders=leaders,
            momentum_laggards=laggards
        )

    def calculate_breadth_metrics(self) -> BreadthMetrics:
        """
        Calculate comprehensive breadth metrics.

        Returns:
            Current BreadthMetrics
        """
        with self._lock:
            components = list(self.components.values())

        if not components:
            return self._empty_breadth_metrics()

        # Basic breadth
        advancing = sum(1 for c in components if c.change_pct > 0)
        declining = sum(1 for c in components if c.change_pct < 0)
        unchanged = len(components) - advancing - declining

        # A/D ratio
        ad_ratio = advancing / declining if declining > 0 else float('inf')

        # Update A/D line
        net_advances = advancing - declining
        self.advance_decline_line += net_advances

        # Moving average breadth
        above_ma50 = self._calculate_percent_above_ma(50)
        above_ma200 = self._calculate_percent_above_ma(200)

        # New highs/lows
        new_highs, new_lows = self._calculate_new_highs_lows()
        hl_ratio = new_highs / new_lows if new_lows > 0 else float('inf')

        # McClellan Oscillator
        mcclellan = self._calculate_mcclellan_oscillator(advancing, declining)

        # Breadth thrust
        breadth_thrust = self._calculate_breadth_thrust(advancing, len(components))

        # Determine signal
        signal = self._determine_breadth_signal(
            advancing / len(components),
            ad_ratio,
            above_ma50,
            hl_ratio
        )

        metrics = BreadthMetrics(
            timestamp=datetime.now(),
            advancing=advancing,
            declining=declining,
            unchanged=unchanged,
            advance_decline_ratio=ad_ratio,
            advance_decline_line=self.advance_decline_line,
            percent_above_ma50=above_ma50,
            percent_above_ma200=above_ma200,
            new_highs=new_highs,
            new_lows=new_lows,
            high_low_ratio=hl_ratio,
            mcclellan_oscillator=mcclellan,
            breadth_thrust=breadth_thrust,
            signal=signal
        )

        # Store for historical analysis
        self.historical_breadth.append(metrics)
        if len(self.historical_breadth) > 1000:
            self.historical_breadth.pop(0)

        return metrics

    def analyze_sectors(self) -> list[SectorMetrics]:
        """
        Analyze sector performance and internals.

        Returns:
            List of SectorMetrics for each sector
        """
        sector_metrics = []

        for sector, symbols in self.sector_components.items():
            if not symbols:
                continue

            # Get sector components
            with self._lock:
                sector_stocks = [self.components[s] for s in symbols
                               if s in self.components]

            if not sector_stocks:
                continue

            # Calculate sector metrics
            perf_1d = np.mean([s.change_pct for s in sector_stocks])
            perf_5d = np.mean([s.momentum_scores.get(5, 0) for s in sector_stocks])
            perf_1m = np.mean([s.momentum_scores.get(20, 0) for s in sector_stocks])

            # Relative strength vs SPY
            spy_perf_1m = self._get_spy_performance(20)
            rel_strength = perf_1m - spy_perf_1m if spy_perf_1m is not None else perf_1m

            # Sector breadth
            advancing_pct = sum(1 for s in sector_stocks if s.change_pct > 0) / len(sector_stocks)

            # Volume analysis
            volume_ratio = np.mean([s.volume / s.avg_volume if s.avg_volume > 0 else 1
                                  for s in sector_stocks])

            # Leading/lagging stocks
            sorted_stocks = sorted(sector_stocks, key=lambda x: x.change_pct, reverse=True)
            leaders = [s.symbol for s in sorted_stocks[:3]]
            laggards = [s.symbol for s in sorted_stocks[-3:]]

            sector_metrics.append(SectorMetrics(
                sector=sector,
                performance_1d=perf_1d,
                performance_5d=perf_5d,
                performance_1m=perf_1m,
                relative_strength=rel_strength,
                advancing_pct=advancing_pct,
                volume_ratio=volume_ratio,
                leading_stocks=leaders,
                lagging_stocks=laggards
            ))

        return sorted(sector_metrics, key=lambda x: x.performance_1d, reverse=True)

    def get_momentum_leaders_laggards(self, count: int = 20) -> tuple[list[ComponentStock], list[ComponentStock]]:
        """
        Get momentum leaders and laggards.

        Args:
            count: Number of stocks to return

        Returns:
            Tuple of (leaders, laggards)
        """
        with self._lock:
            # Sort by 20-day momentum
            sorted_stocks = sorted(
                self.components.values(),
                key=lambda x: x.momentum_scores.get(20, 0),
                reverse=True
            )

        leaders = sorted_stocks[:count]
        laggards = sorted_stocks[-count:]

        return leaders, laggards

    def get_sector_rotation_analysis(self) -> dict[str, Any]:
        """
        Get detailed sector rotation analysis.

        Returns:
            Sector rotation analysis including rankings and trends
        """
        sectors = self.analyze_sectors()

        # Rank sectors by different timeframes
        rankings = {
            '1d': sorted(sectors, key=lambda x: x.performance_1d, reverse=True),
            '5d': sorted(sectors, key=lambda x: x.performance_5d, reverse=True),
            '1m': sorted(sectors, key=lambda x: x.performance_1m, reverse=True),
            'relative': sorted(sectors, key=lambda x: x.relative_strength, reverse=True)
        }

        # Detect rotation patterns
        rotation_pattern = self._analyze_rotation_pattern(rankings)

        # Risk on/off assessment
        risk_assessment = self._assess_risk_appetite(sectors)

        return {
            'timestamp': datetime.now(),
            'sector_rankings': {tf: [s.sector for s in ranking]
                              for tf, ranking in rankings.items()},
            'rotation_pattern': rotation_pattern,
            'risk_assessment': risk_assessment,
            'strongest_sectors': [s.sector for s in rankings['relative'][:3]],
            'weakest_sectors': [s.sector for s in rankings['relative'][-3:]],
            'recommendation': self._generate_rotation_recommendation(rotation_pattern, risk_assessment)
        }

    # ==========================================================================
    # PUBLIC METHODS - BREADTH INDICATORS
    # ==========================================================================
    def get_advance_decline_analysis(self) -> dict[str, Any]:
        """
        Get advance/decline line analysis.

        Returns:
            A/D line analysis with trends and signals
        """
        if len(self.historical_breadth) < 20:
            return {'status': 'insufficient_data'}

        # Get recent A/D line values
        ad_line_values = [b.advance_decline_line for b in self.historical_breadth[-20:]]

        # Calculate trend
        x = np.arange(len(ad_line_values))
        slope, intercept = np.polyfit(x, ad_line_values, 1)

        # Moving averages
        ad_line_ma5 = np.mean(ad_line_values[-5:])
        ad_line_ma20 = np.mean(ad_line_values)

        # Divergence check
        spy_trend = self._get_spy_trend(20)
        divergence = self._check_ad_divergence(slope, spy_trend)

        return {
            'current_value': ad_line_values[-1],
            'trend_slope': slope,
            'trend_direction': 'UP' if slope > 0 else 'DOWN',
            'ma5': ad_line_ma5,
            'ma20': ad_line_ma20,
            'above_ma': ad_line_values[-1] > ad_line_ma20,
            'divergence': divergence,
            'signal': self._generate_ad_signal(ad_line_values[-1], ad_line_ma20, slope, divergence)
        }

    def get_mcclellan_analysis(self) -> dict[str, Any]:
        """
        Get McClellan Oscillator and Summation Index analysis.

        Returns:
            McClellan analysis with signals
        """
        if len(self.historical_breadth) < 20:
            return {'status': 'insufficient_data'}

        # Get recent oscillator values
        oscillator_values = [b.mcclellan_oscillator for b in self.historical_breadth[-20:]]

        # Calculate summation index
        self.mcclellan_sum = sum(oscillator_values)

        # Determine overbought/oversold
        current_oscillator = oscillator_values[-1]

        if current_oscillator > 150:
            condition = "EXTREMELY_OVERBOUGHT"
        elif current_oscillator > 50:
            condition = "OVERBOUGHT"
        elif current_oscillator < -150:
            condition = "EXTREMELY_OVERSOLD"
        elif current_oscillator < -50:
            condition = "OVERSOLD"
        else:
            condition = "NEUTRAL"

        return {
            'oscillator': current_oscillator,
            'summation_index': self.mcclellan_sum,
            'condition': condition,
            'trend': 'IMPROVING' if current_oscillator > oscillator_values[-5] else 'WEAKENING',
            'signal': self._generate_mcclellan_signal(current_oscillator, self.mcclellan_sum)
        }

    # ==========================================================================
    # PRIVATE METHODS - CALCULATIONS
    # ==========================================================================
    def _load_sp500_components(self) -> None:
        """Load S&P 500 component list."""
        self.logger.info("Loading S&P 500 components...")

        # In production, this would fetch from a data provider
        # For demonstration, using a subset of major S&P 500 stocks
        sample_components = {
            'AAPL': ('Apple Inc.', 'Technology', 3.0e12),
            'MSFT': ('Microsoft Corp.', 'Technology', 2.8e12),
            'AMZN': ('Amazon.com Inc.', 'Consumer Discretionary', 1.7e12),
            'GOOGL': ('Alphabet Inc.', 'Technology', 1.8e12),
            'META': ('Meta Platforms Inc.', 'Technology', 0.9e12),
            'BRK.B': ('Berkshire Hathaway', 'Financials', 0.8e12),
            'JPM': ('JPMorgan Chase', 'Financials', 0.5e12),
            'JNJ': ('Johnson & Johnson', 'Healthcare', 0.4e12),
            'V': ('Visa Inc.', 'Financials', 0.5e12),
            'PG': ('Procter & Gamble', 'Consumer Staples', 0.4e12),
            'XOM': ('Exxon Mobil', 'Energy', 0.4e12),
            'UNH': ('UnitedHealth Group', 'Healthcare', 0.5e12),
            'HD': ('Home Depot', 'Consumer Discretionary', 0.3e12),
            'MA': ('Mastercard', 'Financials', 0.4e12),
            'BAC': ('Bank of America', 'Financials', 0.3e12),
        }

        # Calculate total market cap for weighting
        total_market_cap = sum(cap for _, _, cap in sample_components.values())

        # Create component objects
        with self._lock:
            for symbol, (name, sector, market_cap) in sample_components.items():
                weight = market_cap / total_market_cap

                self.components[symbol] = ComponentStock(
                    symbol=symbol,
                    name=name,
                    sector=sector,
                    market_cap=market_cap,
                    weight=weight,
                    price=0.0,
                    change_pct=0.0,
                    volume=0,
                    avg_volume=0,
                    relative_strength=0.0
                )

                self.sector_components[sector].append(symbol)

        self.logger.info(f"Loaded {len(self.components)} S&P 500 components")

    def _calculate_percent_above_ma(self, period: int) -> float:
        """Calculate percentage of stocks above moving average."""
        # This would use historical price data
        # For demonstration, returning synthetic value
        base_value = 0.5
        noise = np.random.normal(0, 0.1)
        return max(0, min(1, base_value + noise))

    def _calculate_new_highs_lows(self) -> tuple[int, int]:
        """Calculate 52-week new highs and lows."""
        # This would analyze 52-week price data
        # For demonstration, returning synthetic values
        total = len(self.components)

        new_highs = int(total * 0.1 * (1 + np.random.normal(0, 0.3)))
        new_lows = int(total * 0.05 * (1 + np.random.normal(0, 0.3)))

        return max(0, new_highs), max(0, new_lows)

    def _calculate_mcclellan_oscillator(self, advancing: int, declining: int) -> float:
        """Calculate McClellan Oscillator."""
        # Simplified calculation
        net_advances = advancing - declining
        total = advancing + declining

        if total == 0:
            return 0.0

        # 19-day EMA - 39-day EMA of advances/declines
        ratio = net_advances / total

        # Simplified oscillator calculation
        oscillator = ratio * 1000  # Scale for readability

        return oscillator

    def _calculate_breadth_thrust(self, advancing: int, total: int) -> float:
        """Calculate Zweig Breadth Thrust indicator."""
        if total == 0:
            return 0.5

        thrust = advancing / total
        self.breadth_thrust_values.append(thrust)

        # Keep last 10 values
        if len(self.breadth_thrust_values) > 10:
            self.breadth_thrust_values.pop(0)

        # 10-day moving average
        return np.mean(self.breadth_thrust_values)

    def _determine_breadth_signal(self, adv_pct: float, ad_ratio: float,
                                above_ma50: float, hl_ratio: float) -> BreadthSignal:
        """Determine overall breadth signal."""
        # Score each component
        scores = []

        # Advancing percentage
        if adv_pct > EXTREME_BREADTH_HIGH:
            scores.append(2)
        elif adv_pct > STRONG_BREADTH:
            scores.append(1)
        elif adv_pct < EXTREME_BREADTH_LOW:
            scores.append(-2)
        elif adv_pct < WEAK_BREADTH:
            scores.append(-1)
        else:
            scores.append(0)

        # A/D ratio
        if ad_ratio > 3:
            scores.append(2)
        elif ad_ratio > 1.5:
            scores.append(1)
        elif ad_ratio < 0.33:
            scores.append(-2)
        elif ad_ratio < 0.67:
            scores.append(-1)
        else:
            scores.append(0)

        # Above MA50
        if above_ma50 > 0.8:
            scores.append(1)
        elif above_ma50 < 0.2:
            scores.append(-1)

        # New highs/lows
        if hl_ratio > 3:
            scores.append(1)
        elif hl_ratio < 0.33:
            scores.append(-1)

        # Average score
        avg_score = np.mean(scores)

        if avg_score >= 1.5:
            return BreadthSignal.EXTREMELY_BULLISH
        elif avg_score >= 0.5:
            return BreadthSignal.BULLISH
        elif avg_score <= -1.5:
            return BreadthSignal.EXTREMELY_BEARISH
        elif avg_score <= -0.5:
            return BreadthSignal.BEARISH
        else:
            return BreadthSignal.NEUTRAL

    def _determine_market_regime(self, breadth: BreadthMetrics,
                               sectors: list[SectorMetrics]) -> MarketRegime:
        """Determine overall market regime."""
        # Breadth strength
        breadth_score = 0
        if breadth.signal == BreadthSignal.EXTREMELY_BULLISH:
            breadth_score = 2
        elif breadth.signal == BreadthSignal.BULLISH:
            breadth_score = 1
        elif breadth.signal == BreadthSignal.BEARISH:
            breadth_score = -1
        elif breadth.signal == BreadthSignal.EXTREMELY_BEARISH:
            breadth_score = -2

        # Sector participation
        strong_sectors = sum(1 for s in sectors if s.performance_1m > 5)
        weak_sectors = sum(1 for s in sectors if s.performance_1m < -5)

        sector_score = (strong_sectors - weak_sectors) / len(sectors) if sectors else 0

        # Combined score
        regime_score = breadth_score + sector_score

        if regime_score >= 2:
            return MarketRegime.STRONG_UPTREND
        elif regime_score >= 0.5:
            return MarketRegime.UPTREND
        elif regime_score <= -2:
            return MarketRegime.STRONG_DOWNTREND
        elif regime_score <= -0.5:
            return MarketRegime.DOWNTREND
        else:
            return MarketRegime.CHOPPY

    def _detect_sector_rotation(self, sectors: list[SectorMetrics]) -> SectorRotation:
        """Detect sector rotation pattern."""
        if not sectors:
            return SectorRotation.MIXED

        # Get top performing sectors
        top_sectors = [s.sector for s in sectors[:3]]

        # Check for specific rotation patterns
        if 'Technology' in top_sectors and 'Consumer Discretionary' in top_sectors:
            return SectorRotation.RISK_ON
        elif 'Utilities' in top_sectors and 'Consumer Staples' in top_sectors:
            return SectorRotation.DEFENSIVE
        elif 'Financials' in top_sectors and 'Industrials' in top_sectors:
            return SectorRotation.CYCLICAL
        elif 'Energy' in top_sectors and 'Materials' in top_sectors:
            return SectorRotation.COMMODITY
        else:
            return SectorRotation.MIXED

    def _calculate_market_strength(self, breadth: BreadthMetrics,
                                 sectors: list[SectorMetrics]) -> float:
        """Calculate overall market strength score (0-100)."""
        scores = []

        # Breadth component (40%)
        breadth_score = 50  # Neutral
        if breadth.signal == BreadthSignal.EXTREMELY_BULLISH:
            breadth_score = 100
        elif breadth.signal == BreadthSignal.BULLISH:
            breadth_score = 75
        elif breadth.signal == BreadthSignal.BEARISH:
            breadth_score = 25
        elif breadth.signal == BreadthSignal.EXTREMELY_BEARISH:
            breadth_score = 0

        scores.append(breadth_score * 0.4)

        # A/D line trend (20%)
        if len(self.historical_breadth) >= 5:
            recent_ad = [b.advance_decline_line for b in self.historical_breadth[-5:]]
            ad_trend = (recent_ad[-1] - recent_ad[0]) / recent_ad[0] if recent_ad[0] != 0 else 0
            ad_score = 50 + (ad_trend * 500)  # Scale trend to 0-100
            scores.append(max(0, min(100, ad_score)) * 0.2)

        # Sector strength (20%)
        if sectors:
            positive_sectors = sum(1 for s in sectors if s.performance_1m > 0)
            sector_score = (positive_sectors / len(sectors)) * 100
            scores.append(sector_score * 0.2)

        # New highs/lows (20%)
        if breadth.new_highs + breadth.new_lows > 0:
            hl_score = breadth.new_highs / (breadth.new_highs + breadth.new_lows) * 100
            scores.append(hl_score * 0.2)

        return sum(scores)

    def _get_spy_performance(self, period: int) -> float | None:
        """Get SPY performance for comparison."""
        # In production, this would fetch actual SPY data
        # For demonstration, returning synthetic value
        return np.random.normal(0, 5)

    def _get_spy_trend(self, period: int) -> float:
        """Get SPY price trend."""
        # In production, this would calculate actual trend
        return np.random.normal(0, 1)

    def _check_ad_divergence(self, ad_slope: float, spy_trend: float) -> str | None:
        """Check for A/D line divergence with price."""
        if ad_slope > 0 and spy_trend < 0:
            return "POSITIVE_DIVERGENCE"
        elif ad_slope < 0 and spy_trend > 0:
            return "NEGATIVE_DIVERGENCE"
        return None

    def _generate_ad_signal(self, current: float, ma: float, slope: float,
                          divergence: str | None) -> str:
        """Generate A/D line signal."""
        if divergence == "POSITIVE_DIVERGENCE":
            return "BULLISH - Positive divergence detected"
        elif divergence == "NEGATIVE_DIVERGENCE":
            return "BEARISH - Negative divergence detected"
        elif current > ma and slope > 0:
            return "BULLISH - Uptrend confirmed"
        elif current < ma and slope < 0:
            return "BEARISH - Downtrend confirmed"
        else:
            return "NEUTRAL - No clear signal"

    def _generate_mcclellan_signal(self, oscillator: float, summation: float) -> str:
        """Generate McClellan signal."""
        if oscillator > 100 and summation > 0:
            return "OVERBOUGHT - Consider taking profits"
        elif oscillator < -100 and summation < 0:
            return "OVERSOLD - Potential bounce setup"
        elif oscillator > 50 and summation > 500:
            return "BULLISH - Strong breadth momentum"
        elif oscillator < -50 and summation < -500:
            return "BEARISH - Weak breadth momentum"
        else:
            return "NEUTRAL - Wait for clearer signal"

    def _analyze_rotation_pattern(self, rankings: dict[str, list[SectorMetrics]]) -> str:
        """Analyze sector rotation pattern from rankings."""
        # Compare short-term vs long-term rankings
        short_term_leaders = [s.sector for s in rankings['1d'][:3]]
        long_term_leaders = [s.sector for s in rankings['1m'][:3]]

        # Check for rotation
        new_leaders = [s for s in short_term_leaders if s not in long_term_leaders]

        if len(new_leaders) >= 2:
            return f"ROTATION DETECTED - New leaders: {', '.join(new_leaders)}"
        elif set(short_term_leaders) == set(long_term_leaders):
            return "STABLE LEADERSHIP - No rotation"
        else:
            return "MINOR ROTATION - Leadership shifting"

    def _assess_risk_appetite(self, sectors: list[SectorMetrics]) -> str:
        """Assess market risk appetite from sector performance."""
        # Define risk-on and defensive sectors
        risk_on_sectors = {'Technology', 'Consumer Discretionary', 'Financials'}
        defensive_sectors = {'Utilities', 'Consumer Staples', 'Healthcare'}

        # Calculate average performance
        risk_on_perf = np.mean([s.performance_1m for s in sectors
                               if s.sector in risk_on_sectors])
        defensive_perf = np.mean([s.performance_1m for s in sectors
                                 if s.sector in defensive_sectors])

        if risk_on_perf > defensive_perf + 5:
            return "HIGH RISK APPETITE"
        elif defensive_perf > risk_on_perf + 5:
            return "RISK AVERSE"
        else:
            return "BALANCED"

    def _generate_rotation_recommendation(self, pattern: str, risk: str) -> str:
        """Generate sector rotation recommendation."""
        if "ROTATION DETECTED" in pattern and risk == "HIGH RISK APPETITE":
            return "Follow new sector leaders - momentum favors growth"
        elif risk == "RISK AVERSE":
            return "Rotate to defensive sectors - market showing caution"
        elif "STABLE LEADERSHIP" in pattern:
            return "Maintain current sector exposure - no rotation signal"
        else:
            return "Monitor for clearer rotation signals"

    def _empty_breadth_metrics(self) -> BreadthMetrics:
        """Return empty breadth metrics structure."""
        return BreadthMetrics(
            timestamp=datetime.now(),
            advancing=0,
            declining=0,
            unchanged=0,
            advance_decline_ratio=1.0,
            advance_decline_line=self.advance_decline_line,
            percent_above_ma50=0.5,
            percent_above_ma200=0.5,
            new_highs=0,
            new_lows=0,
            high_low_ratio=1.0,
            mcclellan_oscillator=0.0,
            breadth_thrust=0.5,
            signal=BreadthSignal.NEUTRAL
        )

    # ==========================================================================
    # PUBLIC METHODS - DATA UPDATES
    # ==========================================================================
    def update_component_prices(self, price_data: dict[str, dict[str, Any]]) -> None:
        """
        Update component stock prices and metrics.

        Args:
            price_data: Dictionary of symbol -> price data
        """
        with self._lock:
            for symbol, data in price_data.items():
                if symbol in self.components:
                    component = self.components[symbol]

                    # Update price data
                    old_price = component.price
                    component.price = data.get('price', component.price)
                    component.volume = data.get('volume', component.volume)

                    # Calculate change
                    if old_price > 0:
                        component.change_pct = ((component.price - old_price) / old_price) * 100

                    # Update momentum scores
                    for period in MOMENTUM_PERIODS:
                        if f'return_{period}d' in data:
                            component.momentum_scores[period] = data[f'return_{period}d']

    def start_monitoring(self) -> None:
        """Start component monitoring."""
        if self._running:
            self.logger.warning("Component monitoring already running")
            return

        self._running = True
        self._update_thread = threading.Thread(
            target=self._monitoring_loop,
            name="ComponentMonitor",
            daemon=True
        )
        self._update_thread.start()
        self.logger.info("Component monitoring started")

    def stop_monitoring(self) -> None:
        """Stop component monitoring."""
        self._running = False

        if self._update_thread:
            self._update_thread.join(timeout=5)

        self._executor.shutdown(wait=True)
        self.logger.info("Component monitoring stopped")

    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        last_update = datetime.now()

        while self._running:
            try:
                now = datetime.now()

                # Update prices periodically
                if (now - last_update).total_seconds() > PRICE_UPDATE_INTERVAL:
                    self._update_all_prices()
                    last_update = now

                # Calculate breadth more frequently
                self.calculate_breadth_metrics()

                # Sleep
                time.sleep(BREADTH_CALC_INTERVAL)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")

    def _update_all_prices(self) -> None:
        """Update prices for all components."""
        # In production, this would fetch real prices
        # For demonstration, generating synthetic updates
        with self._lock:
            for component in self.components.values():
                # Simulate price movement
                change = np.random.normal(0, 2)  # 2% volatility
                component.change_pct = change

                if component.price > 0:
                    component.price *= (1 + change / 100)
                else:
                    component.price = 100  # Default price

                # Simulate volume
                component.volume = int(np.random.lognormal(15, 1))  # Log-normal volume
                component.avg_volume = 10_000_000  # Default avg volume

                # Update momentum scores
                for period in MOMENTUM_PERIODS:
                    base_return = period * 0.05  # Approximate daily return
                    component.momentum_scores[period] = np.random.normal(base_return, base_return)

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_monitoring()
        self.logger.info("Index component analyzer cleanup completed")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_index_analyzer(config: dict | None = None) -> IndexComponentAnalyzer:
    """
    Create and return an IndexComponentAnalyzer instance.

    Args:
        config: Optional configuration dictionary

    Returns:
        Configured IndexComponentAnalyzer instance
    """
    return IndexComponentAnalyzer(config)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing
    analyzer = create_index_analyzer()

    try:
        analyzer.start_monitoring()

        # Let it collect some data
        time.sleep(2)  # thread-safe: time.sleep() intentional

        # Get market internals
        internals = analyzer.get_market_internals()

        # Get breadth details
        breadth = internals.breadth

        # Get sector analysis
        for _sector in internals.sectors[:3]:
            pass

        # Get A/D line analysis
        ad_analysis = analyzer.get_advance_decline_analysis()
        if 'current_value' in ad_analysis:
            pass

        # Get rotation analysis
        rotation = analyzer.get_sector_rotation_analysis()

        time.sleep(5)  # thread-safe: time.sleep() intentional

    finally:
        analyzer.cleanup()
