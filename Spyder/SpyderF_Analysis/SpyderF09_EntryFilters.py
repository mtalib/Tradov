#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderF_Analysis
Module: SpyderF09_EntryFilters.py
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
from typing import Any
from enum import Enum
from datetime import datetime, time
from dataclasses import dataclass, field
from collections import defaultdict, deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderI_Integration.SpyderI03_ConfigManager import ConfigManager
from Spyder.SpyderM_Monitoring.SpyderM01_SystemMonitor import SystemMonitor
from Spyder.SpyderU_Utilities.SpyderU11_FeatureFlags import FeatureFlags

class FilterResult(Enum):
    """Filter result status."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIP = "skip"

class EntryQuality(Enum):
    """Overall entry quality rating."""
    EXCELLENT = 5
    GOOD = 4
    FAIR = 3
    POOR = 2
    AVOID = 1

class FilterType(Enum):
    """Types of entry filters."""
    # Market condition filters
    VOLATILITY = "volatility"
    TREND = "trend"
    MOMENTUM = "momentum"
    VOLUME = "volume"

    # Technical filters
    SUPPORT_RESISTANCE = "support_resistance"
    OVERBOUGHT_OVERSOLD = "overbought_oversold"
    PATTERN = "pattern"

    # Risk filters
    PORTFOLIO_EXPOSURE = "portfolio_exposure"
    CORRELATION = "correlation"
    MAX_LOSS = "max_loss"

    # Time filters
    TIME_OF_DAY = "time_of_day"
    DAY_OF_WEEK = "day_of_week"
    EARNINGS = "earnings"
    ECONOMIC_EVENTS = "economic_events"

    # Greeks filters
    IMPLIED_VOLATILITY = "implied_volatility"
    SKEW = "skew"
    TERM_STRUCTURE = "term_structure"

    # Execution quality filters
    SPREAD_WIDTH = "spread_width"  # Bid-ask spread too wide for safe execution

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class FilterThreshold:
    """Adaptive filter threshold."""
    base_value: float
    current_value: float
    min_value: float
    max_value: float
    adaptation_rate: float = 0.1
    last_update: datetime = field(default_factory=datetime.now)
    performance_history: list[float] = field(default_factory=list)

    def adapt(self, performance_score: float):
        """Adapt threshold based on performance."""
        # Calculate adjustment
        if performance_score > 0.7:
            # Good performance - can be slightly more aggressive
            adjustment = self.adaptation_rate * (performance_score - 0.7)
            self.current_value *= (1 + adjustment)
        elif performance_score < 0.5:
            # Poor performance - be more conservative
            adjustment = self.adaptation_rate * (0.5 - performance_score)
            self.current_value *= (1 - adjustment)

        # Enforce bounds
        self.current_value = max(self.min_value, min(self.max_value, self.current_value))

        # Update history
        self.performance_history.append(performance_score)
        if len(self.performance_history) > 100:
            self.performance_history.pop(0)

        self.last_update = datetime.now()

@dataclass
class FilterCheck:
    """Individual filter check result."""
    filter_type: FilterType
    result: FilterResult
    value: float
    threshold: float
    message: str
    weight: float = 1.0

    @property
    def passed(self) -> bool:
        return self.result in [FilterResult.PASS, FilterResult.WARNING]

@dataclass
class EntryFilterResult:
    """Complete entry filter analysis."""
    overall_result: FilterResult
    quality_rating: EntryQuality
    total_score: float
    checks: list[FilterCheck]
    warnings: list[str]
    recommendations: list[str]
    timestamp: datetime = field(default_factory=datetime.now)

    def get_failed_filters(self) -> list[FilterCheck]:
        """Get all failed filter checks."""
        return [c for c in self.checks if c.result == FilterResult.FAIL]

    def get_warning_filters(self) -> list[FilterCheck]:
        """Get all warning filter checks."""
        return [c for c in self.checks if c.result == FilterResult.WARNING]

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            'overall_result': self.overall_result.value,
            'quality_rating': self.quality_rating.value,
            'total_score': self.total_score,
            'passed_filters': len([c for c in self.checks if c.passed]),
            'failed_filters': len(self.get_failed_filters()),
            'warnings': len(self.warnings),
            'timestamp': self.timestamp.isoformat()
        }

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class EntryFilters:
    """
    Entry filter system with adaptive thresholds.

    Features:
    - Multiple filter categories
    - Adaptive thresholds based on paper trading
    - Weighted scoring system
    - Real-time filter updates
    - Performance tracking
    """

    def __init__(self,
                 config_manager: ConfigManager,
                 paper_trade_learner: Any | None = None):
        """Initialize with adaptive learning."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config_manager = config_manager
        self.paper_trade_learner = paper_trade_learner
        self.feature_flags = FeatureFlags()
        self.monitor = SystemMonitor()

        # Load configuration
        self._load_config()

        # Initialize thresholds
        self.thresholds = self._initialize_thresholds()
        self.base_thresholds = self._initialize_thresholds()  # Keep original values

        # Performance tracking
        self.filter_performance = defaultdict(lambda: deque(maxlen=100))
        self.last_adaptation_time = None

        # Filter weights
        self.filter_weights = self._load_filter_weights()

        self.logger.info("EntryFilters initialized with adaptive thresholds")

    def _load_config(self):
        """Load configuration."""
        config = self.config_manager.get_config('entry_filters', {})

        # Adaptive settings
        self.use_adaptive_thresholds = self.config_manager.is_feature_enabled('adaptive_entry_filters')
        self.adaptation_interval_hours = config.get('adaptation_interval_hours', 24)
        self.min_trades_for_adaptation = config.get('min_trades_for_adaptation', 20)
        self.adaptation_blend_factor = config.get('adaptation_blend_factor', 0.2)  # 80% base, 20% adapted

        # Filter settings
        self.enable_all_filters = config.get('enable_all_filters', True)
        self.min_quality_rating = EntryQuality(config.get('min_quality_rating', 3))
        self.strict_mode = config.get('strict_mode', False)

        # Time filters
        self.restricted_hours = config.get('restricted_hours', {
            'start': time(9, 30),
            'end': time(15, 30)  # No entries in last 30 min
        })
        self.restricted_days = config.get('restricted_days', [5, 6])  # Saturday, Sunday
        # End-of-day force close time — positions should be closed before this
        self.EOD_FORCE_CLOSE_TIME = time(15, 55)  # 3:55 PM ET

    def _initialize_thresholds(self) -> dict[str, FilterThreshold]:
        """Initialize filter thresholds."""
        config = self.config_manager.get_config('entry_filter_thresholds', {})

        thresholds = {
            # Volatility filters
            'min_volatility': FilterThreshold(
                base_value=config.get('min_volatility', 0.10),
                current_value=config.get('min_volatility', 0.10),
                min_value=0.05,
                max_value=0.20
            ),
            'max_volatility': FilterThreshold(
                base_value=config.get('max_volatility', 0.40),
                current_value=config.get('max_volatility', 0.40),
                min_value=0.30,
                max_value=0.60
            ),

            # Trend filters
            'min_trend_strength': FilterThreshold(
                base_value=config.get('min_trend_strength', 0.3),
                current_value=config.get('min_trend_strength', 0.3),
                min_value=0.1,
                max_value=0.5
            ),

            # Volume filters
            'min_volume_ratio': FilterThreshold(
                base_value=config.get('min_volume_ratio', 0.8),
                current_value=config.get('min_volume_ratio', 0.8),
                min_value=0.5,
                max_value=1.5
            ),

            # Technical filters
            'rsi_oversold': FilterThreshold(
                base_value=config.get('rsi_oversold', 30),
                current_value=config.get('rsi_oversold', 30),
                min_value=20,
                max_value=40
            ),
            'rsi_overbought': FilterThreshold(
                base_value=config.get('rsi_overbought', 70),
                current_value=config.get('rsi_overbought', 70),
                min_value=60,
                max_value=80
            ),

            # Risk filters
            'max_portfolio_delta': FilterThreshold(
                base_value=config.get('max_portfolio_delta', 100),
                current_value=config.get('max_portfolio_delta', 100),
                min_value=50,
                max_value=200
            ),
            'max_position_size': FilterThreshold(
                base_value=config.get('max_position_size', 0.1),
                current_value=config.get('max_position_size', 0.1),
                min_value=0.05,
                max_value=0.20
            ),

            # Greeks filters
            'min_iv_percentile': FilterThreshold(
                base_value=config.get('min_iv_percentile', 20),
                current_value=config.get('min_iv_percentile', 20),
                min_value=10,
                max_value=40
            ),
            'max_iv_skew': FilterThreshold(
                base_value=config.get('max_iv_skew', 0.15),
                current_value=config.get('max_iv_skew', 0.15),
                min_value=0.10,
                max_value=0.25
            ),

            # Execution quality — bid-ask spread as fraction of mid-price.
            # Above 5% the fill cost erodes edge; above 10% the trade is
            # almost always unprofitable at market-maker prices.
            'max_spread_pct': FilterThreshold(
                base_value=config.get('max_spread_pct', 0.05),   # 5% of mid — FAIL
                current_value=config.get('max_spread_pct', 0.05),
                min_value=0.01,
                max_value=0.15
            ),
            'warn_spread_pct': FilterThreshold(
                base_value=config.get('warn_spread_pct', 0.025),  # 2.5% — WARNING
                current_value=config.get('warn_spread_pct', 0.025),
                min_value=0.005,
                max_value=0.10
            ),
        }

        return thresholds

    def _load_filter_weights(self) -> dict[FilterType, float]:
        """Load filter importance weights."""
        config = self.config_manager.get_config('filter_weights', {})

        default_weights = {
            FilterType.VOLATILITY: 1.5,
            FilterType.TREND: 1.2,
            FilterType.MOMENTUM: 1.0,
            FilterType.VOLUME: 0.8,
            FilterType.SUPPORT_RESISTANCE: 1.1,
            FilterType.OVERBOUGHT_OVERSOLD: 0.9,
            FilterType.PATTERN: 0.7,
            FilterType.PORTFOLIO_EXPOSURE: 1.3,
            FilterType.CORRELATION: 1.0,
            FilterType.MAX_LOSS: 1.5,
            FilterType.TIME_OF_DAY: 0.6,
            FilterType.DAY_OF_WEEK: 0.5,
            FilterType.EARNINGS: 1.2,
            FilterType.ECONOMIC_EVENTS: 1.1,
            FilterType.IMPLIED_VOLATILITY: 1.4,
            FilterType.SKEW: 1.0,
            FilterType.TERM_STRUCTURE: 0.9,
            FilterType.SPREAD_WIDTH: 1.6,   # High weight — wide spreads destroy edge
        }

        # Override with config values
        for filter_type in FilterType:
            if filter_type.value in config:
                default_weights[filter_type] = config[filter_type.value]

        return default_weights

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================

    def assess_entry(self, entry_params: dict[str, Any]) -> EntryFilterResult:
        """
        Assess entry with adaptive thresholds.

        Args:
            entry_params: Dictionary with entry parameters

        Returns:
            Complete filter assessment
        """
        start_time = datetime.now()

        # Validate critical numeric inputs
        critical_fields = ['current_price', 'volume', 'rsi', 'implied_volatility']
        for field_name in critical_fields:
            val = entry_params.get(field_name)
            if val is not None:
                import math
                if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                    self.logger.error(
                        f"Invalid entry_params['{field_name}'] = {val}. "
                        "Cannot evaluate filters with NaN/Inf values."
                    )
                    return self._create_error_result()
                if field_name == 'current_price' and val <= 0:
                    self.logger.error(
                        f"Invalid current_price={val} (must be > 0)"
                    )
                    return self._create_error_result()
                if field_name == 'rsi' and not (0 <= val <= 100):
                    self.logger.warning(
                        f"RSI={val} out of range [0,100] — clamping"
                    )
                    entry_params = dict(entry_params)
                    entry_params['rsi'] = max(0.0, min(100.0, val))

        try:
            # Update thresholds if needed
            if self.use_adaptive_thresholds:
                self._update_adaptive_thresholds()

            # Run all filters
            checks = self._run_all_filters(entry_params)

            # Calculate overall result
            overall_result, quality_rating, total_score = self._calculate_overall_result(checks)

            # Generate warnings and recommendations
            warnings = self._generate_warnings(checks, entry_params)
            recommendations = self._generate_recommendations(checks, entry_params)

            # Create result
            result = EntryFilterResult(
                overall_result=overall_result,
                quality_rating=quality_rating,
                total_score=total_score,
                checks=checks,
                warnings=warnings,
                recommendations=recommendations
            )

            # Record metrics
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.monitor.record_metric('entry_filters.execution_ms', elapsed_ms)
            self.monitor.record_metric('entry_filters.quality_score', quality_rating.value)

            # Track filter performance
            self._track_filter_performance(result)

            return result

        except Exception as e:
            self.error_handler.handle_error(e, "Entry filter assessment failed")
            return self._create_error_result()

    def get_filter_statistics(self) -> dict[str, Any]:
        """Get filter performance statistics."""
        stats = {
            'total_assessments': sum(len(perf) for perf in self.filter_performance.values()),
            'filter_pass_rates': {},
            'average_quality_scores': {},
            'threshold_adaptations': {}
        }

        # Calculate pass rates by filter
        for filter_type in FilterType:
            perfs = self.filter_performance.get(filter_type, [])
            if perfs:
                stats['filter_pass_rates'][filter_type.value] = np.mean(perfs)

        # Threshold adaptations
        for name, threshold in self.thresholds.items():
            stats['threshold_adaptations'][name] = {
                'base': threshold.base_value,
                'current': threshold.current_value,
                'change_pct': (threshold.current_value - threshold.base_value) / threshold.base_value * 100
            }

        return stats

    def reset_adaptations(self):
        """Reset all thresholds to base values."""
        for _name, threshold in self.thresholds.items():
            threshold.current_value = threshold.base_value
            threshold.performance_history.clear()

        self.filter_performance.clear()
        self.last_adaptation_time = None

        self.logger.info("Filter adaptations reset to base values")

    # ==========================================================================
    # ADAPTIVE THRESHOLD MANAGEMENT
    # ==========================================================================

    def _update_adaptive_thresholds(self):
        """Update thresholds based on paper trading results."""
        if not self.paper_trade_learner:
            return

        # Check if it's time to adapt
        if self.last_adaptation_time:
            hours_since = (datetime.now() - self.last_adaptation_time).total_seconds() / 3600
            if hours_since < self.adaptation_interval_hours:
                return

        try:
            # Get optimized thresholds from paper trading
            optimized = self.paper_trade_learner.get_optimized_thresholds('entry_filters')

            if not optimized:
                return

            # Check if we have enough data
            trade_count = optimized.get('trade_count', 0)
            if trade_count < self.min_trades_for_adaptation:
                self.logger.info(f"Not enough trades for adaptation: {trade_count} < {self.min_trades_for_adaptation}")
                return

            # Scale blend factor by trade count to avoid overfitting on small samples
            # Minimum 50 trades for meaningful adaptation; grows toward 0.20 at 200+ trades
            trade_count = getattr(self, '_paper_trade_count', 0)
            min_trades_for_full_blend = 200
            adaptation_blend_factor = min(
                0.20,
                max(0.0, trade_count / min_trades_for_full_blend) * 0.20
            )
            if trade_count < 50:
                self.logger.debug(
                    f"Adaptive blending at {adaptation_blend_factor:.3f} "
                    f"(trade_count={trade_count} < 50 minimum for full adaptation)"
                )

            # Update each threshold
            for param, opt_value in optimized.items():
                if param in self.thresholds and param != 'trade_count':
                    threshold = self.thresholds[param]
                    base_value = self.base_thresholds[param].current_value

                    # Blend base and optimized values
                    new_value = (
                        (1 - adaptation_blend_factor) * base_value
                        + adaptation_blend_factor * opt_value
                    )

                    # Apply bounds
                    new_value = max(threshold.min_value, min(threshold.max_value, new_value))

                    # Update threshold
                    old_value = threshold.current_value
                    threshold.current_value = new_value

                    if abs(new_value - old_value) > 0.01:
                        self.logger.info(
                            f"Adapted {param}: {old_value:.3f} -> {new_value:.3f} "
                            f"(optimized: {opt_value:.3f})"
                        )

            self.last_adaptation_time = datetime.now()
            self.logger.info("Entry filter thresholds adapted from paper trading")

        except Exception as e:
            self.logger.warning(f"Threshold adaptation failed: {e}", exc_info=True)

    # ==========================================================================
    # FILTER IMPLEMENTATIONS
    # ==========================================================================

    def _run_all_filters(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Run all enabled filters."""
        checks = []

        # Market condition filters
        checks.extend(self._check_volatility_filters(params))
        checks.extend(self._check_trend_filters(params))
        checks.extend(self._check_volume_filters(params))

        # Technical filters
        checks.extend(self._check_technical_filters(params))
        checks.extend(self._check_support_resistance_filters(params))

        # Risk filters
        checks.extend(self._check_risk_filters(params))

        # Time filters
        checks.extend(self._check_time_filters(params))

        # Greeks filters
        checks.extend(self._check_greeks_filters(params))

        # Execution quality filters
        checks.extend(self._check_spread_width_filter(params))

        # Correlation risk filters
        checks.extend(self._check_correlation_filters(params, checks))

        return checks

    def _check_volatility_filters(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Check volatility-based filters."""
        checks = []

        current_vol = params.get('current_volatility', 0)

        # Min volatility check
        min_vol = self.thresholds['min_volatility'].current_value
        if current_vol < min_vol:
            checks.append(FilterCheck(
                filter_type=FilterType.VOLATILITY,
                result=FilterResult.FAIL,
                value=current_vol,
                threshold=min_vol,
                message=f"Volatility too low: {current_vol:.1%} < {min_vol:.1%}",
                weight=self.filter_weights[FilterType.VOLATILITY]
            ))

        # Max volatility check
        max_vol = self.thresholds['max_volatility'].current_value
        if current_vol > max_vol:
            checks.append(FilterCheck(
                filter_type=FilterType.VOLATILITY,
                result=FilterResult.FAIL,
                value=current_vol,
                threshold=max_vol,
                message=f"Volatility too high: {current_vol:.1%} > {max_vol:.1%}",
                weight=self.filter_weights[FilterType.VOLATILITY]
            ))

        # If passed
        if not checks:
            checks.append(FilterCheck(
                filter_type=FilterType.VOLATILITY,
                result=FilterResult.PASS,
                value=current_vol,
                threshold=(min_vol + max_vol) / 2,
                message=f"Volatility acceptable: {current_vol:.1%}",
                weight=self.filter_weights[FilterType.VOLATILITY]
            ))

        return checks

    def _check_trend_filters(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Check trend-based filters."""
        checks = []

        trend_strength = params.get('trend_strength', 0)
        trend_direction = params.get('trend_direction', 'neutral')
        strategy_type = params.get('strategy_type', '')

        # Check trend alignment with strategy
        if strategy_type in ['bull_put_spread', 'call'] and trend_direction == 'down':
            checks.append(FilterCheck(
                filter_type=FilterType.TREND,
                result=FilterResult.FAIL,
                value=0,
                threshold=1,
                message=f"Trend mismatch: {trend_direction} trend for bullish strategy",
                weight=self.filter_weights[FilterType.TREND]
            ))
        elif strategy_type in ['bear_call_spread', 'put'] and trend_direction == 'up':
            checks.append(FilterCheck(
                filter_type=FilterType.TREND,
                result=FilterResult.FAIL,
                value=0,
                threshold=1,
                message=f"Trend mismatch: {trend_direction} trend for bearish strategy",
                weight=self.filter_weights[FilterType.TREND]
            ))

        # Check trend strength
        min_strength = self.thresholds['min_trend_strength'].current_value
        if abs(trend_strength) < min_strength and strategy_type not in ['iron_condor', 'butterfly']:
            checks.append(FilterCheck(
                filter_type=FilterType.TREND,
                result=FilterResult.WARNING,
                value=abs(trend_strength),
                threshold=min_strength,
                message=f"Weak trend: {abs(trend_strength):.2f} < {min_strength:.2f}",
                weight=self.filter_weights[FilterType.TREND] * 0.5
            ))

        # If all passed
        if not checks:
            checks.append(FilterCheck(
                filter_type=FilterType.TREND,
                result=FilterResult.PASS,
                value=abs(trend_strength),
                threshold=min_strength,
                message=f"Trend alignment good: {trend_direction} ({abs(trend_strength):.2f})",
                weight=self.filter_weights[FilterType.TREND]
            ))

        return checks

    def _check_volume_filters(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Check volume-based filters."""
        checks = []

        volume_ratio = params.get('volume_ratio', 1.0)  # Current vs average
        min_ratio = self.thresholds['min_volume_ratio'].current_value

        if volume_ratio < min_ratio:
            checks.append(FilterCheck(
                filter_type=FilterType.VOLUME,
                result=FilterResult.WARNING,
                value=volume_ratio,
                threshold=min_ratio,
                message=f"Low volume: {volume_ratio:.1f}x average",
                weight=self.filter_weights[FilterType.VOLUME]
            ))
        else:
            checks.append(FilterCheck(
                filter_type=FilterType.VOLUME,
                result=FilterResult.PASS,
                value=volume_ratio,
                threshold=min_ratio,
                message=f"Volume adequate: {volume_ratio:.1f}x average",
                weight=self.filter_weights[FilterType.VOLUME]
            ))

        return checks

    def _check_technical_filters(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Check technical indicator filters."""
        checks = []

        rsi = params.get('rsi', 50)

        # Overbought/oversold check
        if rsi < self.thresholds['rsi_oversold'].current_value:
            checks.append(FilterCheck(
                filter_type=FilterType.OVERBOUGHT_OVERSOLD,
                result=FilterResult.WARNING,
                value=rsi,
                threshold=self.thresholds['rsi_oversold'].current_value,
                message=f"RSI oversold: {rsi:.0f}",
                weight=self.filter_weights[FilterType.OVERBOUGHT_OVERSOLD]
            ))
        elif rsi > self.thresholds['rsi_overbought'].current_value:
            checks.append(FilterCheck(
                filter_type=FilterType.OVERBOUGHT_OVERSOLD,
                result=FilterResult.WARNING,
                value=rsi,
                threshold=self.thresholds['rsi_overbought'].current_value,
                message=f"RSI overbought: {rsi:.0f}",
                weight=self.filter_weights[FilterType.OVERBOUGHT_OVERSOLD]
            ))
        else:
            checks.append(FilterCheck(
                filter_type=FilterType.OVERBOUGHT_OVERSOLD,
                result=FilterResult.PASS,
                value=rsi,
                threshold=50,
                message=f"RSI neutral: {rsi:.0f}",
                weight=self.filter_weights[FilterType.OVERBOUGHT_OVERSOLD]
            ))

        return checks

    def _check_support_resistance_filters(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Check support/resistance filters."""
        checks = []

        current_price = params.get('current_price', 0)
        nearest_resistance = params.get('nearest_resistance', float('inf'))
        nearest_support = params.get('nearest_support', 0)

        # Check distance to levels
        resistance_distance = (nearest_resistance - current_price) / current_price
        support_distance = (current_price - nearest_support) / current_price

        # Too close to resistance for long positions
        if params.get('position_type') == 'long' and resistance_distance < 0.005:
            checks.append(FilterCheck(
                filter_type=FilterType.SUPPORT_RESISTANCE,
                result=FilterResult.WARNING,
                value=resistance_distance,
                threshold=0.005,
                message=f"Close to resistance: {resistance_distance:.1%} away",
                weight=self.filter_weights[FilterType.SUPPORT_RESISTANCE]
            ))

        # Too close to support for short positions
        elif params.get('position_type') == 'short' and support_distance < 0.005:
            checks.append(FilterCheck(
                filter_type=FilterType.SUPPORT_RESISTANCE,
                result=FilterResult.WARNING,
                value=support_distance,
                threshold=0.005,
                message=f"Close to support: {support_distance:.1%} away",
                weight=self.filter_weights[FilterType.SUPPORT_RESISTANCE]
            ))
        else:
            checks.append(FilterCheck(
                filter_type=FilterType.SUPPORT_RESISTANCE,
                result=FilterResult.PASS,
                value=min(resistance_distance, support_distance),
                threshold=0.005,
                message="Good distance from S/R levels",
                weight=self.filter_weights[FilterType.SUPPORT_RESISTANCE]
            ))

        return checks

    def _check_risk_filters(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Check risk management filters."""
        checks = []

        # Portfolio exposure check
        portfolio_delta = params.get('portfolio_delta', 0)
        max_delta = self.thresholds['max_portfolio_delta'].current_value

        if abs(portfolio_delta) > max_delta:
            checks.append(FilterCheck(
                filter_type=FilterType.PORTFOLIO_EXPOSURE,
                result=FilterResult.FAIL,
                value=abs(portfolio_delta),
                threshold=max_delta,
                message=f"Portfolio delta too high: {abs(portfolio_delta):.0f} > {max_delta:.0f}",
                weight=self.filter_weights[FilterType.PORTFOLIO_EXPOSURE]
            ))

        # Position size check
        position_size_pct = params.get('position_size_pct', 0)
        max_size = self.thresholds['max_position_size'].current_value

        if position_size_pct > max_size:
            checks.append(FilterCheck(
                filter_type=FilterType.MAX_LOSS,
                result=FilterResult.FAIL,
                value=position_size_pct,
                threshold=max_size,
                message=f"Position too large: {position_size_pct:.1%} of portfolio",
                weight=self.filter_weights[FilterType.MAX_LOSS]
            ))

        # If all passed
        if not checks:
            checks.append(FilterCheck(
                filter_type=FilterType.PORTFOLIO_EXPOSURE,
                result=FilterResult.PASS,
                value=abs(portfolio_delta),
                threshold=max_delta,
                message="Risk parameters acceptable",
                weight=self.filter_weights[FilterType.PORTFOLIO_EXPOSURE]
            ))

        return checks

    def _check_time_filters(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Check time-based filters."""
        checks = []

        current_time = params.get('current_time', datetime.now())

        # EOD force-close warning
        if current_time.time() >= self.EOD_FORCE_CLOSE_TIME:
            self.logger.warning(
                f"Current time {current_time.time()} is past EOD force-close threshold "
                f"{self.EOD_FORCE_CLOSE_TIME}. New entries blocked; "
                "open positions should be closed."
            )

        # Time of day check
        if (current_time.time() < self.restricted_hours['start'] or
                current_time.time() > self.restricted_hours['end']):
            checks.append(FilterCheck(
                filter_type=FilterType.TIME_OF_DAY,
                result=FilterResult.WARNING,
                value=current_time.hour + current_time.minute/60,
                threshold=15.5,  # 3:30 PM
                message="Outside preferred trading hours",
                weight=self.filter_weights[FilterType.TIME_OF_DAY]
            ))

        # Day of week check
        if current_time.weekday() in self.restricted_days:
            checks.append(FilterCheck(
                filter_type=FilterType.DAY_OF_WEEK,
                result=FilterResult.FAIL,
                value=current_time.weekday(),
                threshold=4,  # Friday
                message="Weekend - markets closed",
                weight=self.filter_weights[FilterType.DAY_OF_WEEK]
            ))

        # Earnings check
        days_to_earnings = params.get('days_to_earnings', float('inf'))
        if days_to_earnings < 2:
            checks.append(FilterCheck(
                filter_type=FilterType.EARNINGS,
                result=FilterResult.WARNING,
                value=days_to_earnings,
                threshold=2,
                message=f"Earnings in {days_to_earnings} days",
                weight=self.filter_weights[FilterType.EARNINGS]
            ))

        # If all passed
        if not checks:
            checks.append(FilterCheck(
                filter_type=FilterType.TIME_OF_DAY,
                result=FilterResult.PASS,
                value=current_time.hour + current_time.minute/60,
                threshold=12,  # Noon
                message="Good trading time",
                weight=self.filter_weights[FilterType.TIME_OF_DAY]
            ))

        return checks

    def _check_correlation_filters(
        self,
        entry_params: dict[str, Any],
        filter_results: list[FilterCheck]
    ) -> list[FilterCheck]:
        """
        Check correlation risk against existing portfolio positions.

        Prevents accumulating highly correlated short-delta positions.

        NOTE: Currently checks symbol-level correlation only.
        TODO: Integrate portfolio-level Greek correlation when position data available.
        """
        results = []
        try:
            existing_symbols = entry_params.get('existing_position_symbols', [])
            entry_symbol = entry_params.get('symbol', '')
            max_correlated_positions = entry_params.get('max_correlated_positions', 3)

            # Count how many existing positions share the same underlying
            same_underlying = sum(
                1 for s in existing_symbols
                if s and entry_symbol and (s[:3] == entry_symbol[:3])
            )

            passed = same_underlying < max_correlated_positions
            results.append(FilterCheck(
                filter_type=FilterType.CORRELATION,
                result=FilterResult.PASS if passed else FilterResult.FAIL,
                value=float(same_underlying),
                threshold=float(max_correlated_positions),
                message=(
                    f"Correlation check: {same_underlying} similar positions "
                    f"({'OK' if passed else 'LIMIT REACHED'})"
                ),
                weight=self.filter_weights[FilterType.CORRELATION]
            ))
        except Exception as e:
            self.logger.warning(f"Correlation filter check failed: {e}", exc_info=True)
            # On failure, pass filter (don't block entry for filter error)
            results.append(FilterCheck(
                filter_type=FilterType.CORRELATION,
                result=FilterResult.PASS,
                value=0.5,
                threshold=1.0,
                message=f"Correlation filter unavailable: {e}",
                weight=self.filter_weights[FilterType.CORRELATION]
            ))
        return results

    def _check_spread_width_filter(self, params: dict[str, Any]) -> list[FilterCheck]:
        """
        Reject entries when the bid-ask spread is too wide relative to mid.

        Wide spreads (> 5% of mid) mean the fill cost alone can eliminate
        the strategy's edge before the trade ever moves in our favour.

        Expected params keys:
            bid (float): Best bid price of the option (or net debit/credit bid).
            ask (float): Best ask price.
        """
        bid = params.get('bid')
        ask = params.get('ask')

        # If spread data is not provided, skip gracefully (no penalty).
        if bid is None or ask is None or bid <= 0 or ask <= 0:
            return [FilterCheck(
                filter_type=FilterType.SPREAD_WIDTH,
                result=FilterResult.SKIP,
                value=0.0,
                threshold=self.thresholds['max_spread_pct'].current_value,
                message="Spread data unavailable — filter skipped",
                weight=0.0,
            )]

        mid = (bid + ask) / 2.0
        if mid <= 0:
            return []

        spread_pct = (ask - bid) / mid
        max_spread = self.thresholds['max_spread_pct'].current_value
        warn_spread = self.thresholds['warn_spread_pct'].current_value

        if spread_pct > max_spread:
            return [FilterCheck(
                filter_type=FilterType.SPREAD_WIDTH,
                result=FilterResult.FAIL,
                value=spread_pct,
                threshold=max_spread,
                message=(
                    f"Bid-ask spread too wide: {spread_pct:.1%} of mid "
                    f"(limit {max_spread:.1%}) — fill cost destroys edge"
                ),
                weight=self.filter_weights[FilterType.SPREAD_WIDTH],
            )]

        if spread_pct > warn_spread:
            # Emit logger warning so spread elevation is visible in system logs
            self.logger.warning(
                f"Spread width {spread_pct:.2%} exceeds warn threshold "
                f"{warn_spread:.2%} (max: {max_spread:.2%})"
            )
            return [FilterCheck(
                filter_type=FilterType.SPREAD_WIDTH,
                result=FilterResult.WARNING,
                value=spread_pct,
                threshold=warn_spread,
                message=(
                    f"Spread elevated: {spread_pct:.1%} of mid "
                    f"(warn level {warn_spread:.1%}) — use limit order at mid-price"
                ),
                weight=self.filter_weights[FilterType.SPREAD_WIDTH],
            )]

        return [FilterCheck(
            filter_type=FilterType.SPREAD_WIDTH,
            result=FilterResult.PASS,
            value=spread_pct,
            threshold=max_spread,
            message=f"Spread acceptable: {spread_pct:.1%} of mid",
            weight=self.filter_weights[FilterType.SPREAD_WIDTH],
        )]

    def _check_greeks_filters(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Check Greeks-based filters."""
        checks = []

        # IV percentile check
        iv_percentile = params.get('iv_percentile', 50)
        min_iv_pct = self.thresholds['min_iv_percentile'].current_value

        if params.get('strategy_type') in ['iron_condor', 'credit_spread']:
            if iv_percentile < min_iv_pct:
                checks.append(FilterCheck(
                    filter_type=FilterType.IMPLIED_VOLATILITY,
                    result=FilterResult.WARNING,
                    value=iv_percentile,
                    threshold=min_iv_pct,
                    message=f"Low IV percentile for credit strategy: {iv_percentile:.0f}%",
                    weight=self.filter_weights[FilterType.IMPLIED_VOLATILITY]
                ))

        # IV skew check
        iv_skew = params.get('iv_skew', 0)
        max_skew = self.thresholds['max_iv_skew'].current_value

        if abs(iv_skew) > max_skew:
            checks.append(FilterCheck(
                filter_type=FilterType.SKEW,
                result=FilterResult.WARNING,
                value=abs(iv_skew),
                threshold=max_skew,
                message=f"High IV skew: {abs(iv_skew):.1%}",
                weight=self.filter_weights[FilterType.SKEW]
            ))

        # If all passed
        if not checks:
            checks.append(FilterCheck(
                filter_type=FilterType.IMPLIED_VOLATILITY,
                result=FilterResult.PASS,
                value=iv_percentile,
                threshold=50,
                message="Greeks parameters acceptable",
                weight=self.filter_weights[FilterType.IMPLIED_VOLATILITY]
            ))

        return checks

    # ==========================================================================
    # RESULT CALCULATION
    # ==========================================================================

    def _calculate_overall_result(self,
                                checks: list[FilterCheck]) -> tuple[FilterResult, EntryQuality, float]:
        """Calculate overall filter result and quality rating."""
        if not checks:
            return FilterResult.SKIP, EntryQuality.POOR, 0.0

        # Count results by type
        failed = sum(1 for c in checks if c.result == FilterResult.FAIL)
        warnings = sum(1 for c in checks if c.result == FilterResult.WARNING)
        sum(1 for c in checks if c.result == FilterResult.PASS)

        # Calculate weighted score
        total_weight = sum(c.weight for c in checks)
        if total_weight == 0:
            total_weight = 1

        score = 0
        for check in checks:
            if check.result == FilterResult.PASS:
                score += check.weight
            elif check.result == FilterResult.WARNING:
                score += check.weight * 0.5
            # FAIL adds 0

        normalized_score = score / total_weight

        # Determine overall result
        if failed > 0:
            if self.strict_mode or failed >= 2:
                overall = FilterResult.FAIL
            else:
                overall = FilterResult.WARNING
        elif warnings >= 3:
            overall = FilterResult.WARNING
        else:
            overall = FilterResult.PASS

        # Determine quality rating
        if normalized_score >= 0.9 and failed == 0:
            quality = EntryQuality.EXCELLENT
        elif normalized_score >= 0.75 and failed == 0:
            quality = EntryQuality.GOOD
        elif normalized_score >= 0.6:
            quality = EntryQuality.FAIR
        elif normalized_score >= 0.4:
            quality = EntryQuality.POOR
        else:
            quality = EntryQuality.AVOID

        return overall, quality, normalized_score

    def _generate_warnings(self, checks: list[FilterCheck],
                         params: dict[str, Any]) -> list[str]:
        """Generate warning messages."""
        warnings = []

        # Add warnings from failed/warning checks
        for check in checks:
            if check.result in [FilterResult.FAIL, FilterResult.WARNING]:
                warnings.append(check.message)

        # Add context-specific warnings
        if params.get('volatility_regime') == 'extreme':
            warnings.append("Extreme volatility regime - use extra caution")

        if params.get('near_expiration', False):
            warnings.append("Near expiration - gamma risk elevated")

        return warnings[:5]  # Limit to top 5 warnings

    def _generate_recommendations(self, checks: list[FilterCheck],
                                params: dict[str, Any]) -> list[str]:
        """Generate recommendations based on filter results."""
        recommendations = []

        # Check for specific issues
        vol_checks = [c for c in checks if c.filter_type == FilterType.VOLATILITY]
        if any(c.result == FilterResult.FAIL for c in vol_checks):
            recommendations.append("Wait for volatility to normalize")

        trend_checks = [c for c in checks if c.filter_type == FilterType.TREND]
        if any(c.result == FilterResult.FAIL for c in trend_checks):
            recommendations.append("Consider different strategy aligned with trend")

        risk_checks = [c for c in checks if c.filter_type in [FilterType.PORTFOLIO_EXPOSURE, FilterType.MAX_LOSS]]
        if any(c.result == FilterResult.FAIL for c in risk_checks):
            recommendations.append("Reduce position size or hedge existing positions first")

        # General recommendations
        quality = self._calculate_overall_result(checks)[1]
        if quality == EntryQuality.FAIR:
            recommendations.append("Consider waiting for better setup")
        elif quality in [EntryQuality.POOR, EntryQuality.AVOID]:
            recommendations.append("Skip this trade - look for better opportunities")

        return recommendations[:3]  # Limit to top 3 recommendations

    # ==========================================================================
    # PERFORMANCE TRACKING
    # ==========================================================================

    def _track_filter_performance(self, result: EntryFilterResult):
        """Track performance of individual filters."""
        for check in result.checks:
            # Track pass/fail rate
            self.filter_performance[check.filter_type].append(
                1.0 if check.passed else 0.0
            )

    def _create_error_result(self) -> EntryFilterResult:
        """Create error result when assessment fails."""
        return EntryFilterResult(
            overall_result=FilterResult.FAIL,
            quality_rating=EntryQuality.AVOID,
            total_score=0.0,
            checks=[],
            warnings=["Filter assessment error - skipping trade"],
            recommendations=["System error - please check logs"]
        )


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================
if __name__ == "__main__":
    # Mock paper trade learner
    class MockPaperTradeLearner:
        def get_optimized_thresholds(self, filter_name):
            # Simulate optimized thresholds from paper trading
            return {
                'min_volatility': 0.12,  # Slightly higher than base
                'max_volatility': 0.38,  # Slightly lower than base
                'min_trend_strength': 0.25,  # Lower - more trades
                'rsi_oversold': 25,  # More extreme
                'rsi_overbought': 75,
                'trade_count': 50  # Enough for adaptation
            }

    # Initialize
    config_manager = ConfigManager()
    paper_learner = MockPaperTradeLearner()
    filters = EntryFilters(config_manager, paper_learner)

    # Test entry parameters
    entry_params = {
        'current_volatility': 0.15,
        'trend_strength': 0.4,
        'trend_direction': 'up',
        'strategy_type': 'bull_put_spread',
        'volume_ratio': 1.2,
        'rsi': 45,
        'current_price': 585.0,
        'nearest_resistance': 590.0,
        'nearest_support': 580.0,
        'position_type': 'long',
        'portfolio_delta': 75,
        'position_size_pct': 0.08,
        'current_time': datetime.now(),
        'days_to_earnings': 10,
        'iv_percentile': 65,
        'iv_skew': 0.08,
        'volatility_regime': 'normal'
    }

    # Run assessment
    result = filters.assess_entry(entry_params)


    # Show individual checks
    for check in result.checks:
        status = "✓" if check.passed else "✗"

    # Show warnings and recommendations
    if result.warnings:
        for _warning in result.warnings:
            pass

    if result.recommendations:
        for _rec in result.recommendations:
            pass

    # Test adaptive thresholds

    # Force adaptation
    filters.use_adaptive_thresholds = True
    filters._update_adaptive_thresholds()


    # Run assessment again with adapted thresholds
    result2 = filters.assess_entry(entry_params)

    # Get statistics
    stats = filters.get_filter_statistics()

    for _name, adapt in stats['threshold_adaptations'].items():
        if adapt['change_pct'] != 0:
            pass

    # Test different scenarios

    # High volatility scenario
    high_vol_params = entry_params.copy()
    high_vol_params['current_volatility'] = 0.45
    high_vol_params['volatility_regime'] = 'extreme'

    result_high_vol = filters.assess_entry(high_vol_params)

    # Poor risk scenario
    high_risk_params = entry_params.copy()
    high_risk_params['portfolio_delta'] = 150
    high_risk_params['position_size_pct'] = 0.15

    result_high_risk = filters.assess_entry(high_risk_params)
