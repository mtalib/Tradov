#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderF_Analysis
Module: SpyderF02_PriceAction.py
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
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import signal
from scipy.stats import linregress

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderI_Integration.SpyderI03_ConfigManager import ConfigManager
from Spyder.SpyderM_Monitoring.SpyderM01_SystemMonitor import SystemMonitor
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU11_FeatureFlags import FeatureFlags

class PatternType(Enum):
    """Types of price patterns."""

    # Candlestick patterns
    DOJI = "doji"
    HAMMER = "hammer"
    SHOOTING_STAR = "shooting_star"
    ENGULFING_BULL = "engulfing_bull"
    ENGULFING_BEAR = "engulfing_bear"
    HARAMI_BULL = "harami_bull"
    HARAMI_BEAR = "harami_bear"
    MORNING_STAR = "morning_star"
    EVENING_STAR = "evening_star"

    # Chart patterns
    DOUBLE_TOP = "double_top"
    DOUBLE_BOTTOM = "double_bottom"
    HEAD_SHOULDERS = "head_shoulders"
    TRIANGLE_ASC = "triangle_ascending"
    TRIANGLE_DESC = "triangle_descending"
    FLAG_BULL = "flag_bull"
    FLAG_BEAR = "flag_bear"

    # Micro patterns
    ABSORPTION = "absorption"
    REJECTION = "rejection"
    BREAKOUT = "breakout"
    FAKEOUT = "fakeout"


class PatternDirection(Enum):
    """Pattern direction bias."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class TrendDirection(Enum):
    """Trend direction."""

    UP = "up"
    DOWN = "down"
    SIDEWAYS = "sideways"


# ==============================================================================
# DATA CLASSES
# ==============================================================================


@dataclass
class Candle:
    """Single candlestick data."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def body(self) -> float:
        """Candle body size."""
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        """Full candle range."""
        return self.high - self.low

    @property
    def upper_wick(self) -> float:
        """Upper wick size."""
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        """Lower wick size."""
        return min(self.open, self.close) - self.low

    @property
    def body_position(self) -> float:
        """Body position in range (0=bottom, 1=top)."""
        if self.range == 0:
            return 0.5
        return (min(self.open, self.close) - self.low) / self.range

    @property
    def is_bullish(self) -> bool:
        """Is bullish candle."""
        return self.close > self.open

    @property
    def is_doji(self) -> bool:
        """Is doji candle."""
        return self.body < self.range * 0.1


@dataclass
class Pattern:
    """Detected pattern."""

    pattern_type: PatternType
    direction: PatternDirection
    start_time: datetime
    end_time: datetime
    confidence: float
    candles: list[Candle]
    support_level: float | None = None
    resistance_level: float | None = None
    target_price: float | None = None
    stop_loss: float | None = None


@dataclass
class PerformanceMetrics:
    """Performance tracking for pattern detection."""

    total_patterns_scanned: int = 0
    patterns_found: int = 0
    total_execution_time_ms: float = 0.0
    avg_execution_time_ms: float = 0.0
    max_execution_time_ms: float = 0.0
    slow_executions: int = 0
    last_update: datetime = None


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class PriceActionAnalyzer:
    """
    Price action pattern analyzer with performance monitoring.

    Features:
    - Candlestick pattern recognition
    - Chart pattern detection
    - Micro-structure analysis
    - Performance monitoring and optimization
    - Parallel pattern detection
    """

    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        monitor: SystemMonitor | None = None,
    ):
        """Initialize price action analyzer."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config_manager = config_manager or ConfigManager()
        self.monitor = monitor or SystemMonitor()
        self.feature_flags = FeatureFlags()

        # Load configuration
        self._load_config()

        # Performance tracking
        self.performance_metrics = PerformanceMetrics()
        self.execution_times = deque(maxlen=1000)
        self._metrics_lock = threading.Lock()

        # Pattern cache
        self._pattern_cache = {}
        self._cache_lock = threading.Lock()

        self.logger.info("PriceActionAnalyzer initialized with performance monitoring")

    def _load_config(self):
        """Load configuration."""
        config = self.config_manager.get_config("price_action", {})

        # Performance settings
        self.monitoring_enabled = config.get("enable_monitoring", True)
        self.performance_threshold_ms = config.get("performance_threshold_ms", 100)
        self.parallel_detection = config.get("parallel_detection", True)
        self.max_workers = config.get("max_workers", 4)

        # Pattern detection settings
        self.min_pattern_confidence = config.get("min_pattern_confidence", 0.7)
        self.lookback_periods = config.get("lookback_periods", 50)
        self.enable_micro_patterns = config.get("enable_micro_patterns", True)

        # Cache settings
        self.cache_enabled = config.get("cache_enabled", True)
        self.cache_ttl_seconds = config.get("cache_ttl_seconds", 60)

        # Feature flags
        self.use_ml_enhancement = self.feature_flags.is_enabled("ml_pattern_enhancement")
        self.use_volume_analysis = self.feature_flags.is_enabled("volume_pattern_analysis")

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================

    def detect_patterns(
        self, data: pd.DataFrame, pattern_types: list[PatternType] | None = None
    ) -> list[Pattern]:
        """
        Detect patterns with performance monitoring.

        Args:
            data: OHLCV DataFrame
            pattern_types: Specific patterns to look for (None = all)

        Returns:
            List of detected patterns
        """
        start_time = time.time()
        patterns = []

        try:
            # Check cache
            cache_key = self._generate_cache_key(data)
            if self.cache_enabled and cache_key in self._pattern_cache:
                cached_result, cache_time = self._pattern_cache[cache_key]
                if time.time() - cache_time < self.cache_ttl_seconds:
                    self._record_execution(0, len(cached_result))  # 0ms for cache hit
                    return cached_result

            # Convert to candles
            candles = self._df_to_candles(data)

            # Detect patterns
            if self.parallel_detection and len(candles) > 20:
                patterns = self._detect_patterns_parallel(candles, pattern_types)
            else:
                patterns = self._detect_patterns_sequential(candles, pattern_types)

            # Filter by confidence
            patterns = [p for p in patterns if p.confidence >= self.min_pattern_confidence]

            # Cache results
            if self.cache_enabled:
                with self._cache_lock:
                    self._pattern_cache[cache_key] = (patterns, time.time())

            # Record performance
            elapsed_ms = (time.time() - start_time) * 1000
            self._record_execution(elapsed_ms, len(patterns))

            # Log if slow
            if elapsed_ms > self.performance_threshold_ms:
                self.logger.warning(
                    f"Pattern detection slow: {elapsed_ms:.1f}ms for {len(candles)} candles"
                )

        except Exception as e:
            self.error_handler.handle_error(e, "Pattern detection failed")
            elapsed_ms = (time.time() - start_time) * 1000
            self._record_execution(elapsed_ms, 0)

        return patterns

    def analyze_trend(self, data: pd.DataFrame, period: int = 20) -> dict:
        """
        Analyze price trend with performance monitoring.

        Returns:
            Dictionary with trend analysis
        """
        start_time = time.time()

        try:
            result = {
                "direction": TrendDirection.SIDEWAYS,
                "strength": 0.0,
                "angle": 0.0,
                "r_squared": 0.0,
            }

            if len(data) < period:
                return result

            # Use close prices for trend
            prices = data["close"].values[-period:]
            x = np.arange(len(prices))

            # Linear regression
            slope, intercept, r_value, _, _ = linregress(x, prices)

            # Calculate trend metrics
            angle = np.degrees(np.arctan(slope))
            r_squared = r_value**2

            # Determine direction
            if abs(angle) < 5:
                direction = TrendDirection.SIDEWAYS
            elif angle > 0:
                direction = TrendDirection.UP
            else:
                direction = TrendDirection.DOWN

            # Update result
            result.update(
                {
                    "direction": direction,
                    "strength": abs(slope) / np.mean(prices),
                    "angle": angle,
                    "r_squared": r_squared,
                }
            )

            # Record performance
            elapsed_ms = (time.time() - start_time) * 1000
            if self.monitoring_enabled:
                self.monitor.record_metric("price_action.trend_analysis_ms", elapsed_ms)

            return result

        except Exception as e:
            self.error_handler.handle_error(e, "Trend analysis failed")
            return result

    def find_support_resistance(
        self, data: pd.DataFrame, min_touches: int = 3
    ) -> dict[str, list[float]]:
        """
        Find support and resistance levels with performance monitoring.

        Returns:
            Dictionary with support and resistance levels
        """
        start_time = time.time()

        try:
            levels = {"support": [], "resistance": []}

            if len(data) < 20:
                return levels

            # Find peaks and troughs
            highs = data["high"].values
            lows = data["low"].values

            # Find local maxima (resistance)
            peaks, _ = signal.find_peaks(highs, distance=5)
            if len(peaks) >= min_touches:
                # Cluster nearby peaks
                peak_prices = highs[peaks]
                resistance_levels = self._cluster_levels(peak_prices, threshold=0.01)
                levels["resistance"] = resistance_levels

            # Find local minima (support)
            troughs, _ = signal.find_peaks(-lows, distance=5)
            if len(troughs) >= min_touches:
                # Cluster nearby troughs
                trough_prices = lows[troughs]
                support_levels = self._cluster_levels(trough_prices, threshold=0.01)
                levels["support"] = support_levels

            # Record performance
            elapsed_ms = (time.time() - start_time) * 1000
            if self.monitoring_enabled:
                self.monitor.record_metric("price_action.sr_detection_ms", elapsed_ms)

            return levels

        except Exception as e:
            self.error_handler.handle_error(e, "Support/Resistance detection failed")
            return {"support": [], "resistance": []}

    def get_performance_stats(self) -> dict:
        """Get performance statistics."""
        with self._metrics_lock:
            if not self.execution_times:
                return {
                    "avg_execution_ms": 0,
                    "max_execution_ms": 0,
                    "patterns_per_second": 0,
                    "cache_size": len(self._pattern_cache),
                    "slow_execution_rate": 0,
                }

            execution_times = list(self.execution_times)
            total_patterns = self.performance_metrics.patterns_found
            total_scans = self.performance_metrics.total_patterns_scanned

            return {
                "avg_execution_ms": np.mean(execution_times),
                "max_execution_ms": np.max(execution_times),
                "min_execution_ms": np.min(execution_times),
                "patterns_per_second": (
                    total_patterns / (sum(execution_times) / 1000) if execution_times else 0
                ),
                "cache_size": len(self._pattern_cache),
                "cache_hit_rate": self._calculate_cache_hit_rate(),
                "slow_execution_rate": (
                    self.performance_metrics.slow_executions / len(execution_times)
                    if execution_times
                    else 0
                ),
                "total_patterns_found": total_patterns,
                "detection_success_rate": total_patterns / total_scans if total_scans > 0 else 0,
            }

    def clear_cache(self):
        """Clear pattern cache."""
        with self._cache_lock:
            self._pattern_cache.clear()
        self.logger.info("Pattern cache cleared")

    # ==========================================================================
    # PATTERN DETECTION METHODS
    # ==========================================================================

    def _detect_patterns_sequential(
        self, candles: list[Candle], pattern_types: list[PatternType] | None
    ) -> list[Pattern]:
        """Sequential pattern detection."""
        patterns = []

        # Detect candlestick patterns
        patterns.extend(self._detect_candlestick_patterns(candles, pattern_types))

        # Detect chart patterns
        if len(candles) >= 20:
            patterns.extend(self._detect_chart_patterns(candles, pattern_types))

        # Detect micro patterns
        if self.enable_micro_patterns:
            patterns.extend(self._detect_micro_patterns(candles, pattern_types))

        return patterns

    def _detect_patterns_parallel(
        self, candles: list[Candle], pattern_types: list[PatternType] | None
    ) -> list[Pattern]:
        """Parallel pattern detection using thread pool."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        patterns = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []

            # Submit detection tasks
            futures.append(
                executor.submit(self._detect_candlestick_patterns, candles, pattern_types)
            )

            if len(candles) >= 20:
                futures.append(executor.submit(self._detect_chart_patterns, candles, pattern_types))

            if self.enable_micro_patterns:
                futures.append(executor.submit(self._detect_micro_patterns, candles, pattern_types))

            # Collect results
            for future in as_completed(futures):
                try:
                    patterns.extend(future.result())
                except Exception as e:
                    self.logger.error("Pattern detection task failed: %s", e)

        return patterns

    def _detect_candlestick_patterns(
        self, candles: list[Candle], pattern_types: list[PatternType] | None
    ) -> list[Pattern]:
        """Detect candlestick patterns."""
        patterns = []

        if len(candles) < 3:
            return patterns

        # Check each pattern type
        for i in range(2, len(candles)):
            candle = candles[i]
            prev_candle = candles[i - 1]
            candles[i - 2] if i >= 2 else None

            # Doji
            if self._should_check_pattern(PatternType.DOJI, pattern_types):
                if candle.is_doji:
                    patterns.append(
                        Pattern(
                            pattern_type=PatternType.DOJI,
                            direction=PatternDirection.NEUTRAL,
                            start_time=candle.timestamp,
                            end_time=candle.timestamp,
                            confidence=0.8,
                            candles=[candle],
                        )
                    )

            # Hammer/Shooting Star
            if self._should_check_pattern(PatternType.HAMMER, pattern_types):
                if self._is_hammer(candle):
                    patterns.append(
                        Pattern(
                            pattern_type=PatternType.HAMMER,
                            direction=PatternDirection.BULLISH,
                            start_time=candle.timestamp,
                            end_time=candle.timestamp,
                            confidence=0.75,
                            candles=[candle],
                        )
                    )

            if self._should_check_pattern(PatternType.SHOOTING_STAR, pattern_types):
                if self._is_shooting_star(candle):
                    patterns.append(
                        Pattern(
                            pattern_type=PatternType.SHOOTING_STAR,
                            direction=PatternDirection.BEARISH,
                            start_time=candle.timestamp,
                            end_time=candle.timestamp,
                            confidence=0.75,
                            candles=[candle],
                        )
                    )

            # Engulfing patterns
            if self._should_check_pattern(PatternType.ENGULFING_BULL, pattern_types):
                if self._is_bullish_engulfing(prev_candle, candle):
                    patterns.append(
                        Pattern(
                            pattern_type=PatternType.ENGULFING_BULL,
                            direction=PatternDirection.BULLISH,
                            start_time=prev_candle.timestamp,
                            end_time=candle.timestamp,
                            confidence=0.85,
                            candles=[prev_candle, candle],
                        )
                    )

            if self._should_check_pattern(PatternType.ENGULFING_BEAR, pattern_types):
                if self._is_bearish_engulfing(prev_candle, candle):
                    patterns.append(
                        Pattern(
                            pattern_type=PatternType.ENGULFING_BEAR,
                            direction=PatternDirection.BEARISH,
                            start_time=prev_candle.timestamp,
                            end_time=candle.timestamp,
                            confidence=0.85,
                            candles=[prev_candle, candle],
                        )
                    )

        return patterns

    def _detect_chart_patterns(
        self, candles: list[Candle], pattern_types: list[PatternType] | None
    ) -> list[Pattern]:
        """Detect chart patterns (placeholder for complex patterns)."""
        patterns = []

        # This would contain more sophisticated pattern detection
        # For now, just a placeholder

        return patterns

    def _detect_micro_patterns(
        self, candles: list[Candle], pattern_types: list[PatternType] | None
    ) -> list[Pattern]:
        """Detect micro-structure patterns."""
        patterns = []

        if len(candles) < 5:
            return patterns

        # Volume-based absorption
        if self.use_volume_analysis:
            for i in range(4, len(candles)):
                if self._is_absorption(candles[i - 4 : i + 1]):
                    patterns.append(
                        Pattern(
                            pattern_type=PatternType.ABSORPTION,
                            direction=PatternDirection.NEUTRAL,
                            start_time=candles[i - 4].timestamp,
                            end_time=candles[i].timestamp,
                            confidence=0.7,
                            candles=candles[i - 4 : i + 1],
                        )
                    )

        return patterns

    # ==========================================================================
    # PATTERN RECOGNITION HELPERS
    # ==========================================================================

    def _is_hammer(self, candle: Candle) -> bool:
        """Check if candle is a hammer."""
        return (
            candle.lower_wick > candle.body * 2
            and candle.upper_wick < candle.body * 0.3
            and candle.body_position < 0.3
        )

    def _is_shooting_star(self, candle: Candle) -> bool:
        """Check if candle is a shooting star."""
        return (
            candle.upper_wick > candle.body * 2
            and candle.lower_wick < candle.body * 0.3
            and candle.body_position > 0.7
        )

    def _is_bullish_engulfing(self, prev: Candle, curr: Candle) -> bool:
        """Check if current candle engulfs previous bearish candle."""
        return (
            not prev.is_bullish
            and curr.is_bullish
            and curr.open < prev.close
            and curr.close > prev.open
        )

    def _is_bearish_engulfing(self, prev: Candle, curr: Candle) -> bool:
        """Check if current candle engulfs previous bullish candle."""
        return (
            prev.is_bullish
            and not curr.is_bullish
            and curr.open > prev.close
            and curr.close < prev.open
        )

    def _is_absorption(self, candles: list[Candle]) -> bool:
        """Check for volume absorption pattern."""
        if len(candles) < 5:
            return False

        # High volume with small price movement
        avg_volume = np.mean([c.volume for c in candles[:-1]])
        last_volume = candles[-1].volume
        price_change = abs(candles[-1].close - candles[0].close) / candles[0].close

        return last_volume > avg_volume * 1.5 and price_change < 0.002

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def _df_to_candles(self, df: pd.DataFrame) -> list[Candle]:
        """Convert DataFrame to Candle objects."""
        candles = []

        for idx, row in df.iterrows():
            candles.append(
                Candle(
                    timestamp=idx if isinstance(idx, datetime) else datetime.now(timezone.utc),
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"],
                )
            )

        return candles

    def _cluster_levels(self, prices: np.ndarray, threshold: float) -> list[float]:
        """Cluster price levels within threshold."""
        if len(prices) == 0:
            return []

        # Sort prices
        sorted_prices = np.sort(prices)
        clusters = []
        current_cluster = [sorted_prices[0]]

        for price in sorted_prices[1:]:
            if price - current_cluster[-1] <= threshold * price:
                current_cluster.append(price)
            else:
                # New cluster
                clusters.append(np.mean(current_cluster))
                current_cluster = [price]

        # Don't forget last cluster
        clusters.append(np.mean(current_cluster))

        return clusters

    def _should_check_pattern(
        self, pattern_type: PatternType, pattern_types: list[PatternType] | None
    ) -> bool:
        """Check if we should look for this pattern type."""
        if pattern_types is None:
            return True
        return pattern_type in pattern_types

    def _generate_cache_key(self, data: pd.DataFrame) -> str:
        """Generate cache key for DataFrame."""
        # Use last row's data and length as key
        last_row = data.iloc[-1]
        key = f"{len(data)}_{last_row['close']:.2f}_{last_row['volume']}"
        return key

    # ==========================================================================
    # PERFORMANCE TRACKING
    # ==========================================================================

    def _record_execution(self, elapsed_ms: float, patterns_found: int):
        """Record execution metrics."""
        with self._metrics_lock:
            self.execution_times.append(elapsed_ms)
            self.performance_metrics.total_execution_time_ms += elapsed_ms
            self.performance_metrics.patterns_found += patterns_found
            self.performance_metrics.total_patterns_scanned += 1

            if elapsed_ms > self.performance_metrics.max_execution_time_ms:
                self.performance_metrics.max_execution_time_ms = elapsed_ms

            if elapsed_ms > self.performance_threshold_ms:
                self.performance_metrics.slow_executions += 1

            # Update average
            if self.execution_times:
                self.performance_metrics.avg_execution_time_ms = np.mean(self.execution_times)

            self.performance_metrics.last_update = datetime.now(timezone.utc)

        # Report to monitor
        if self.monitoring_enabled:
            self.monitor.record_metric("price_action.pattern_detection_ms", elapsed_ms)
            self.monitor.record_metric("price_action.patterns_found", patterns_found)

    def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate from execution times."""
        if not self.execution_times:
            return 0.0

        # Cache hits have 0ms execution time
        cache_hits = sum(1 for t in self.execution_times if t == 0)
        return cache_hits / len(self.execution_times)


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================
if __name__ == "__main__":
    # Create sample data
    dates = pd.date_range("2024-01-01 09:30", periods=100, freq="5min")
    data = pd.DataFrame(
        {
            "open": np.random.randn(100).cumsum() + 585,
            "high": np.random.randn(100).cumsum() + 586,
            "low": np.random.randn(100).cumsum() + 584,
            "close": np.random.randn(100).cumsum() + 585,
            "volume": np.random.randint(1000, 10000, 100),
        },
        index=dates,
    )

    # Ensure high > low
    data["high"] = data[["open", "high", "close"]].max(axis=1)
    data["low"] = data[["open", "low", "close"]].min(axis=1)

    # Initialize analyzer
    config_manager = ConfigManager()
    monitor = SystemMonitor()
    analyzer = PriceActionAnalyzer(config_manager, monitor)

    # Detect patterns
    patterns = analyzer.detect_patterns(data)
    for _pattern in patterns[:5]:  # Show first 5
        pass

    # Analyze trend
    trend = analyzer.analyze_trend(data)

    # Find support/resistance
    levels = analyzer.find_support_resistance(data)

    # Performance test

    # First run (no cache)
    start = time.time()
    patterns1 = analyzer.detect_patterns(data)
    time1 = (time.time() - start) * 1000

    # Second run (with cache)
    start = time.time()
    patterns2 = analyzer.detect_patterns(data)
    time2 = (time.time() - start) * 1000


    # Get performance stats
    stats = analyzer.get_performance_stats()
    for _key, value in stats.items():
        if isinstance(value, float):
            pass
        else:
            pass

    # Test parallel detection

    # Large dataset
    large_data = pd.DataFrame(
        {
            "open": np.random.randn(500).cumsum() + 585,
            "high": np.random.randn(500).cumsum() + 586,
            "low": np.random.randn(500).cumsum() + 584,
            "close": np.random.randn(500).cumsum() + 585,
            "volume": np.random.randint(1000, 10000, 500),
        },
        index=pd.date_range("2024-01-01", periods=500, freq="5min"),
    )

    large_data["high"] = large_data[["open", "high", "close"]].max(axis=1)
    large_data["low"] = large_data[["open", "low", "close"]].min(axis=1)

    # Clear cache
    analyzer.clear_cache()

    # Sequential
    analyzer.parallel_detection = False
    start = time.time()
    seq_patterns = analyzer.detect_patterns(large_data)
    seq_time = (time.time() - start) * 1000

    # Clear cache again
    analyzer.clear_cache()

    # Parallel
    analyzer.parallel_detection = True
    start = time.time()
    par_patterns = analyzer.detect_patterns(large_data)
    par_time = (time.time() - start) * 1000

