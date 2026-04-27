#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderF_Analysis
Module: SpyderF03_SupportResistance.py
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
from enum import Enum
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from collections import defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import signal
from sklearn.cluster import DBSCAN


# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderI_Integration.SpyderI03_ConfigManager import ConfigManager
from Spyder.SpyderU_Utilities.SpyderU11_FeatureFlags import FeatureFlags
from Spyder.SpyderM_Monitoring.SpyderM01_SystemMonitor import SystemMonitor
from Spyder.SpyderF_Analysis.SpyderF04_VolatilityAnalysis import VolatilityAnalyzer

# ==============================================================================
# ENUMS
# ==============================================================================
class LevelType(Enum):
    """Type of price level."""
    SUPPORT = "support"
    RESISTANCE = "resistance"
    PIVOT = "pivot"
    VOLUME_NODE = "volume_node"
    PSYCHOLOGICAL = "psychological"

class LevelStrength(Enum):
    """Strength of support/resistance level."""
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4

class PivotType(Enum):
    """Types of pivot calculations."""
    TRADITIONAL = "traditional"
    FIBONACCI = "fibonacci"
    WOODIE = "woodie"
    CAMARILLA = "camarilla"
    DEMARK = "demark"

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class PriceLevel:
    """Single price level with metadata."""
    price: float
    level_type: LevelType
    strength: LevelStrength
    touches: int
    first_touch: datetime
    last_touch: datetime
    volume_at_level: float = 0.0
    breach_count: int = 0

    @property
    def age(self) -> timedelta:
        """Age of the level."""
        now = datetime.now() if self.first_touch.tzinfo is None else datetime.now(timezone.utc)
        return now - self.first_touch

    @property
    def strength_score(self) -> float:
        """Numerical strength score."""
        base_score = self.strength.value
        touch_bonus = min(self.touches / 3, 2.0)  # Max 2x bonus
        age_factor = min(self.age.days / 30, 1.5)  # Max 1.5x for old levels
        return base_score * (1 + touch_bonus) * (1 + age_factor)

    @property
    def strength_category(self) -> str:
        """Human-readable strength category."""
        score = self.strength_score
        if score < 2:
            return "Weak"
        elif score < 4:
            return "Moderate"
        elif score < 6:
            return "Strong"
        else:
            return "Very Strong"

@dataclass
class LevelCluster:
    """Cluster of nearby levels."""
    center_price: float
    levels: list[PriceLevel]
    total_touches: int
    average_strength: float

    @property
    def importance(self) -> float:
        """Overall importance score."""
        return self.average_strength * np.log1p(self.total_touches)

@dataclass
class SupportResistanceAnalysis:
    """Complete S/R analysis results."""
    support_levels: list[PriceLevel]
    resistance_levels: list[PriceLevel]
    pivot_levels: dict[str, float]
    volume_nodes: list[tuple[float, float]]  # (price, volume)
    key_levels: list[float]  # Most important levels
    current_price: float
    nearest_support: float | None = None
    nearest_resistance: float | None = None
    analysis_timestamp: datetime = field(default_factory=datetime.now)

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SupportResistanceAnalyzer:
    """
    Support and resistance analyzer with dynamic configuration.

    Features:
    - Multiple detection methods
    - Dynamic thresholds based on volatility
    - Volume profile integration
    - Machine learning enhancement
    - Real-time level updates
    """

    def __init__(self,
                 config_manager: ConfigManager | None = None,
                 volatility_analyzer: VolatilityAnalyzer | None = None):
        """Initialize with dynamic configuration."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config_manager = config_manager or ConfigManager()
        self.feature_flags = FeatureFlags()
        self.monitor = SystemMonitor()
        self.volatility_analyzer = volatility_analyzer

        # Load configuration
        self._load_config()

        # Level storage
        self.price_levels: dict[float, PriceLevel] = {}
        self.level_history: list[PriceLevel] = []

        # Performance tracking
        self.last_analysis_time = None
        self.analysis_count = 0

        self.logger.info("SupportResistanceAnalyzer initialized with dynamic configuration")

    def _load_config(self):
        """Load configuration dynamically."""
        config = self.config_manager.get_config('support_resistance', {})

        # Base parameters (will be adjusted by volatility)
        self.base_cluster_threshold = config.get('base_cluster_threshold', 0.002)
        self.min_touches = config.get('min_touches', 3)
        self.lookback_periods = config.get('lookback_periods', 100)
        self.volume_percentile_threshold = config.get('volume_percentile_threshold', 80)

        # Feature flags
        self.use_volume_profile = self.config_manager.is_feature_enabled('volume_profile_sr')
        self.use_ml_enhancement = self.config_manager.is_feature_enabled('ml_sr_detection')
        self.use_pivot_points = config.get('use_pivot_points', True)
        self.use_psychological_levels = config.get('use_psychological_levels', True)

        # Level decay settings
        self.level_decay_days = config.get('level_decay_days', 30)
        self.max_levels_per_type = config.get('max_levels_per_type', 10)

        # Volatility adjustment factors
        self.volatility_adjustment = config.get('volatility_adjustment', {
            'low': 0.5,      # Tighter clustering in low vol
            'normal': 1.0,   # Normal clustering
            'high': 2.0,     # Wider clustering in high vol
            'extreme': 3.0   # Very wide clustering
        })

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================

    def analyze(self, data: pd.DataFrame, current_volatility: float | None = None) -> SupportResistanceAnalysis:  # noqa: E501
        """
        Perform complete support/resistance analysis.

        Args:
            data: OHLCV DataFrame
            current_volatility: Current market volatility (optional)

        Returns:
            Complete analysis results
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Get dynamic cluster threshold
            cluster_threshold = self.get_cluster_threshold(current_volatility)

            # Detect levels using multiple methods
            all_levels = []

            # 1. Peak/Trough detection
            peak_trough_levels = self._detect_peak_trough_levels(data)
            all_levels.extend(peak_trough_levels)

            # 2. Volume profile (if enabled)
            if self.use_volume_profile and 'volume' in data.columns:
                volume_levels = self._detect_volume_levels(data)
                all_levels.extend(volume_levels)

            # 3. Pivot points
            if self.use_pivot_points:
                pivot_levels = self._calculate_pivot_levels(data)
                all_levels.extend(self._pivot_dict_to_levels(pivot_levels))

            # 4. Psychological levels
            if self.use_psychological_levels:
                psych_levels = self._detect_psychological_levels(data)
                all_levels.extend(psych_levels)

            # Cluster nearby levels
            clustered_levels = self._cluster_levels(all_levels, cluster_threshold)

            # Classify as support or resistance
            current_price = data['close'].iloc[-1]
            support_levels = []
            resistance_levels = []

            for level in clustered_levels:
                if level.price < current_price:
                    level.level_type = LevelType.SUPPORT
                    support_levels.append(level)
                else:
                    level.level_type = LevelType.RESISTANCE
                    resistance_levels.append(level)

            # Sort by distance from current price
            support_levels.sort(key=lambda x: x.price, reverse=True)
            resistance_levels.sort(key=lambda x: x.price)

            # Limit number of levels
            support_levels = support_levels[:self.max_levels_per_type]
            resistance_levels = resistance_levels[:self.max_levels_per_type]

            # Identify key levels
            key_levels = self._identify_key_levels(support_levels + resistance_levels)

            # Create analysis result
            analysis = SupportResistanceAnalysis(
                support_levels=support_levels,
                resistance_levels=resistance_levels,
                pivot_levels=pivot_levels if self.use_pivot_points else {},
                volume_nodes=self._get_volume_nodes(data) if self.use_volume_profile else [],
                key_levels=key_levels,
                current_price=current_price,
                nearest_support=support_levels[0].price if support_levels else None,
                nearest_resistance=resistance_levels[0].price if resistance_levels else None
            )

            # Record performance
            elapsed_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self.monitor.record_metric('sr_analysis.execution_ms', elapsed_ms)
            self.monitor.record_metric('sr_analysis.levels_found', len(support_levels) + len(resistance_levels))  # noqa: E501

            # Update history
            self.last_analysis_time = datetime.now(timezone.utc)
            self.analysis_count += 1

            return analysis

        except Exception as e:
            self.error_handler.handle_error(e, "S/R analysis failed")
            return SupportResistanceAnalysis(
                support_levels=[],
                resistance_levels=[],
                pivot_levels={},
                volume_nodes=[],
                key_levels=[],
                current_price=data['close'].iloc[-1] if len(data) > 0 else 0
            )

    def get_cluster_threshold(self, volatility: float | None = None) -> float:
        """
        Get dynamic cluster threshold based on volatility.

        Args:
            volatility: Current volatility (will fetch if not provided)

        Returns:
            Adjusted cluster threshold
        """
        # Get current volatility if not provided
        if volatility is None and self.volatility_analyzer:
            volatility = self.volatility_analyzer.get_current_volatility()

        if volatility is None:
            return self.base_cluster_threshold

        # Determine volatility regime
        if volatility < 0.10:
            vol_regime = 'low'
        elif volatility < 0.20:
            vol_regime = 'normal'
        elif volatility < 0.30:
            vol_regime = 'high'
        else:
            vol_regime = 'extreme'

        # Apply adjustment
        adjustment_factor = self.volatility_adjustment.get(vol_regime, 1.0)
        adjusted_threshold = self.base_cluster_threshold * adjustment_factor

        self.logger.debug(
            f"Cluster threshold adjusted: {self.base_cluster_threshold:.4f} -> "
            f"{adjusted_threshold:.4f} (volatility: {volatility:.2%}, regime: {vol_regime})"
        )

        return adjusted_threshold

    def update_level_touches(self, price: float, levels: list[PriceLevel],
                           tolerance: float | None = None):
        """
        Update touch counts for levels near current price.

        Args:
            price: Current price
            levels: List of levels to check
            tolerance: Price tolerance (uses cluster threshold if None)
        """
        if tolerance is None:
            tolerance = self.get_cluster_threshold()

        for level in levels:
            if abs(price - level.price) <= price * tolerance:
                level.touches += 1
                level.last_touch = datetime.now(timezone.utc)

                # Update strength based on touches
                if level.touches >= 10:
                    level.strength = LevelStrength.VERY_STRONG
                elif level.touches >= 7:
                    level.strength = LevelStrength.STRONG
                elif level.touches >= 4:
                    level.strength = LevelStrength.MODERATE

    def get_level_statistics(self) -> dict:
        """Get statistics about detected levels."""
        all_levels = list(self.price_levels.values())

        if not all_levels:
            return {
                'total_levels': 0,
                'avg_touches': 0,
                'avg_strength': 0,
                'oldest_level_days': 0,
                'most_touched_level': None
            }

        touches = [level.touches for level in all_levels]
        strengths = [level.strength_score for level in all_levels]
        ages = [(datetime.now(timezone.utc) - level.first_touch).days for level in all_levels]

        most_touched = max(all_levels, key=lambda x: x.touches)

        return {
            'total_levels': len(all_levels),
            'avg_touches': np.mean(touches),
            'avg_strength': np.mean(strengths),
            'oldest_level_days': max(ages),
            'most_touched_level': {
                'price': most_touched.price,
                'touches': most_touched.touches,
                'strength': most_touched.strength_category
            }
        }

    # ==========================================================================
    # DETECTION METHODS
    # ==========================================================================

    def _detect_peak_trough_levels(self, data: pd.DataFrame) -> list[PriceLevel]:
        """Detect levels from price peaks and troughs."""
        levels = []

        # Use high/low for better accuracy
        highs = data['high'].values
        lows = data['low'].values
        timestamps = data.index.to_pydatetime()

        # Find peaks (resistance)
        peaks, peak_props = signal.find_peaks(highs, distance=5, prominence=0.0001)

        for idx in peaks:
            level = PriceLevel(
                price=highs[idx],
                level_type=LevelType.RESISTANCE,
                strength=self._calculate_peak_strength(highs, idx),
                touches=1,
                first_touch=timestamps[idx],
                last_touch=timestamps[idx]
            )
            levels.append(level)

        # Find troughs (support)
        troughs, trough_props = signal.find_peaks(-lows, distance=5, prominence=0.0001)

        for idx in troughs:
            level = PriceLevel(
                price=lows[idx],
                level_type=LevelType.SUPPORT,
                strength=self._calculate_peak_strength(-lows, idx),
                touches=1,
                first_touch=timestamps[idx],
                last_touch=timestamps[idx]
            )
            levels.append(level)

        return levels

    def _detect_volume_levels(self, data: pd.DataFrame) -> list[PriceLevel]:
        """Detect levels from volume profile."""
        levels = []

        if len(data) < 20:
            return levels

        # Create volume profile
        prices = data['close'].values
        volumes = data['volume'].values

        # Discretize price into bins
        price_bins = np.linspace(prices.min(), prices.max(), 50)
        volume_profile = np.zeros(len(price_bins) - 1)

        for i in range(len(prices)):
            bin_idx = np.digitize(prices[i], price_bins) - 1
            if 0 <= bin_idx < len(volume_profile):
                volume_profile[bin_idx] += volumes[i]

        # Find high volume nodes
        threshold = np.percentile(volume_profile, self.volume_percentile_threshold)
        high_volume_indices = np.where(volume_profile > threshold)[0]

        for idx in high_volume_indices:
            price = (price_bins[idx] + price_bins[idx + 1]) / 2
            level = PriceLevel(
                price=price,
                level_type=LevelType.VOLUME_NODE,
                strength=LevelStrength.MODERATE,
                touches=1,
                first_touch=datetime.now(timezone.utc),
                last_touch=datetime.now(timezone.utc),
                volume_at_level=volume_profile[idx]
            )
            levels.append(level)

        return levels

    def _calculate_pivot_levels(self, data: pd.DataFrame) -> dict[str, float]:
        """Calculate various pivot point levels."""
        if len(data) < 2:
            return {}

        # Use previous day's data
        prev_high = data['high'].iloc[-2]
        prev_low = data['low'].iloc[-2]
        prev_close = data['close'].iloc[-2]

        pivots = {}

        # Traditional pivot
        pivot = (prev_high + prev_low + prev_close) / 3
        pivots['pivot'] = pivot

        # Support and resistance levels
        pivots['r1'] = 2 * pivot - prev_low
        pivots['s1'] = 2 * pivot - prev_high
        pivots['r2'] = pivot + (prev_high - prev_low)
        pivots['s2'] = pivot - (prev_high - prev_low)
        pivots['r3'] = prev_high + 2 * (pivot - prev_low)
        pivots['s3'] = prev_low - 2 * (prev_high - pivot)

        # Fibonacci pivots
        if self.config_manager.is_feature_enabled('fibonacci_pivots'):
            range_hl = prev_high - prev_low
            pivots['fib_r1'] = pivot + 0.382 * range_hl
            pivots['fib_r2'] = pivot + 0.618 * range_hl
            pivots['fib_r3'] = pivot + 1.000 * range_hl
            pivots['fib_s1'] = pivot - 0.382 * range_hl
            pivots['fib_s2'] = pivot - 0.618 * range_hl
            pivots['fib_s3'] = pivot - 1.000 * range_hl

        return pivots

    def _detect_psychological_levels(self, data: pd.DataFrame) -> list[PriceLevel]:
        """Detect psychological price levels (round numbers)."""
        levels = []

        data['close'].iloc[-1]
        price_range = data['high'].max() - data['low'].min()

        # Determine step size based on price range
        if price_range < 10:
            step = 1
        elif price_range < 50:
            step = 5
        elif price_range < 100:
            step = 10
        else:
            step = 25

        # Find round numbers within data range
        start = int(data['low'].min() / step) * step
        end = int(data['high'].max() / step + 1) * step

        for price in range(start, end, step):
            if data['low'].min() <= price <= data['high'].max():
                level = PriceLevel(
                    price=float(price),
                    level_type=LevelType.PSYCHOLOGICAL,
                    strength=LevelStrength.WEAK,
                    touches=0,
                    first_touch=datetime.now(timezone.utc),
                    last_touch=datetime.now(timezone.utc)
                )
                levels.append(level)

        return levels

    # ==========================================================================
    # CLUSTERING AND FILTERING
    # ==========================================================================

    def _cluster_levels(self, levels: list[PriceLevel], threshold: float) -> list[PriceLevel]:
        """Cluster nearby levels using DBSCAN."""
        if not levels:
            return []

        # Extract prices for clustering
        prices = np.array([[level.price] for level in levels])

        # Normalize threshold to price scale
        eps = np.mean(prices) * threshold

        # Perform clustering
        clustering = DBSCAN(eps=eps, min_samples=1).fit(prices)

        # Group levels by cluster
        clusters = defaultdict(list)
        for i, label in enumerate(clustering.labels_):
            clusters[label].append(levels[i])

        # Create merged levels for each cluster
        merged_levels = []
        for cluster_levels in clusters.values():
            if len(cluster_levels) == 1:
                merged_levels.append(cluster_levels[0])
            else:
                # Merge cluster into single level
                merged_level = self._merge_levels(cluster_levels)
                merged_levels.append(merged_level)

        return merged_levels

    def _merge_levels(self, levels: list[PriceLevel]) -> PriceLevel:
        """Merge multiple levels into one."""
        # Weighted average price based on touches
        total_touches = sum(level.touches for level in levels)
        if total_touches > 0:
            weighted_price = sum(level.price * level.touches for level in levels) / total_touches
        else:
            weighted_price = np.mean([level.price for level in levels])

        # Combined properties
        total_touches = sum(level.touches for level in levels)
        max_strength = max(level.strength for level in levels)
        first_touch = min(level.first_touch for level in levels)
        last_touch = max(level.last_touch for level in levels)
        total_volume = sum(level.volume_at_level for level in levels)

        # Determine type (most common)
        type_counts = defaultdict(int)
        for level in levels:
            type_counts[level.level_type] += 1
        level_type = max(type_counts, key=type_counts.get)

        return PriceLevel(
            price=weighted_price,
            level_type=level_type,
            strength=max_strength,
            touches=total_touches,
            first_touch=first_touch,
            last_touch=last_touch,
            volume_at_level=total_volume
        )

    def _identify_key_levels(self, levels: list[PriceLevel], max_key_levels: int = 5) -> list[float]:  # noqa: E501
        """Identify the most important levels."""
        if not levels:
            return []

        # Sort by importance (strength score)
        sorted_levels = sorted(levels, key=lambda x: x.strength_score, reverse=True)

        # Take top levels
        key_levels = [level.price for level in sorted_levels[:max_key_levels]]

        return sorted(key_levels)

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def _calculate_peak_strength(self, data: np.ndarray, peak_idx: int) -> LevelStrength:
        """Calculate strength of a peak/trough."""
        # Look at prominence and sharpness
        window = 5
        start = max(0, peak_idx - window)
        end = min(len(data), peak_idx + window + 1)

        local_data = data[start:end]
        if len(local_data) < 3:
            return LevelStrength.WEAK

        # Calculate prominence
        prominence = abs(data[peak_idx] - np.mean(local_data))
        relative_prominence = prominence / np.std(data) if np.std(data) > 0 else 0

        # Determine strength
        if relative_prominence > 2:
            return LevelStrength.VERY_STRONG
        elif relative_prominence > 1:
            return LevelStrength.STRONG
        elif relative_prominence > 0.5:
            return LevelStrength.MODERATE
        else:
            return LevelStrength.WEAK

    def _pivot_dict_to_levels(self, pivots: dict[str, float]) -> list[PriceLevel]:
        """Convert pivot dictionary to PriceLevel objects."""
        levels = []

        for name, price in pivots.items():
            level_type = LevelType.SUPPORT if 's' in name else LevelType.RESISTANCE
            if name == 'pivot':
                level_type = LevelType.PIVOT

            level = PriceLevel(
                price=price,
                level_type=level_type,
                strength=LevelStrength.MODERATE,
                touches=0,
                first_touch=datetime.now(timezone.utc),
                last_touch=datetime.now(timezone.utc)
            )
            levels.append(level)

        return levels

    def _get_volume_nodes(self, data: pd.DataFrame) -> list[tuple[float, float]]:
        """Get volume nodes for visualization."""
        if 'volume' not in data.columns or len(data) < 10:
            return []

        # Simple volume profile
        prices = data['close'].values
        volumes = data['volume'].values

        # Create bins
        bins = 20
        price_bins = np.linspace(prices.min(), prices.max(), bins)
        volume_profile = []

        for i in range(len(price_bins) - 1):
            mask = (prices >= price_bins[i]) & (prices < price_bins[i + 1])
            bin_volume = volumes[mask].sum()
            bin_price = (price_bins[i] + price_bins[i + 1]) / 2
            volume_profile.append((bin_price, bin_volume))

        return volume_profile


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================
if __name__ == "__main__":
    # Create sample data
    dates = pd.date_range('2024-01-01', periods=200, freq='5min')

    # Generate price data with some structure
    np.random.seed(42)
    price = 585.0
    prices = []

    for i in range(200):
        # Add some trends and reversals
        if i < 50:
            price += np.random.normal(0.1, 0.5)
        elif i < 100:
            price -= np.random.normal(0.1, 0.5)
        elif i < 150:
            price += np.random.normal(0.05, 0.3)
        else:
            price -= np.random.normal(0.05, 0.3)

        # Add some support/resistance behavior
        if price > 590:
            price -= np.random.normal(0.5, 0.2)
        elif price < 580:
            price += np.random.normal(0.5, 0.2)

        prices.append(price)

    data = pd.DataFrame({
        'open': prices,
        'high': [p + np.random.uniform(0, 0.5) for p in prices],
        'low': [p - np.random.uniform(0, 0.5) for p in prices],
        'close': [p + np.random.normal(0, 0.2) for p in prices],
        'volume': np.random.randint(1000, 10000, 200)
    }, index=dates)

    # Initialize analyzer
    config_manager = ConfigManager()
    analyzer = SupportResistanceAnalyzer(config_manager)

    # Analyze with different volatility levels

    for volatility in [0.05, 0.15, 0.25, 0.35]:

        # Get dynamic threshold
        threshold = analyzer.get_cluster_threshold(volatility)

        # Perform analysis
        analysis = analyzer.analyze(data, volatility)

        if analysis.support_levels:
            for _level in analysis.support_levels[:3]:
                pass

        if analysis.resistance_levels:
            for _level in analysis.resistance_levels[:3]:
                pass


    # Test level updates
    current_price = analysis.current_price

    # Simulate price touching a level
    if analysis.support_levels:
        test_level = analysis.support_levels[0]

        # Update touches
        for _ in range(5):
            analyzer.update_level_touches(test_level.price + 0.05, [test_level])


    # Get statistics
    stats = analyzer.get_level_statistics()
    for _key, _value in stats.items():
        pass
