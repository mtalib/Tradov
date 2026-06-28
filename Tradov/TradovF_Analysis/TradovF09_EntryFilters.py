#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovF_Analysis
Module: TradovF09_EntryFilters.py
Purpose: TRADOV - Automated TRAD Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    TRADOV - Automated TRAD Options Trading System

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
from datetime import datetime, time, UTC
from dataclasses import dataclass, field
from collections import defaultdict, deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler
from Tradov.TradovI_Integration.TradovI03_ConfigManager import ConfigManager
from Tradov.TradovM_Monitoring.TradovM01_SystemMonitor import SystemMonitor
from Tradov.TradovU_Utilities.TradovU11_FeatureFlags import FeatureFlags

class FilterResult(Enum):
    """Filter result status."""
    PASS = "pass"  # noqa: S105
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
    LIQUIDITY_QUALITY = "liquidity_quality"  # Full contract-level liquidity gate

    # Market internals / macro filters
    MARKET_INTERNALS = "market_internals"  # TICK/TRIN/breadth from C04
    VIX_TERM_STRUCTURE = "vix_term_structure"  # VIX contango/backwardation from C10
    CBOE_SKEW = "cboe_skew"  # CBOE SKEW tail-risk index from S06
    VOL_SURFACE = "vol_surface"  # N06 term structure / smile confidence gate
    DEALER_FLOW = "dealer_flow"  # N09/N11 dealer positioning structure gate
    DATA_QUALITY = "data_quality"  # S07 data-quality SLO hard trust gate
    SHORT_TERM_VOL_STRESS = "short_term_vol_stress"  # VIX9D/VIX front-end stress gate
    VOL_OF_VOL_STRESS = "vol_of_vol_stress"  # VVIX volatility-of-volatility gate
    PUT_CALL_SENTIMENT = "put_call_sentiment"  # CPC sentiment/crowding gate
    PARTICIPATION = "participation"  # RVOL participation/conviction gate
    QQQ_CONFIRMATION = "qqq_confirmation"  # QQQ relative-strength confirmation gate
    IWM_CONFIRMATION = "iwm_confirmation"  # IWM breadth confirmation gate
    XLK_CONFIRMATION = "xlk_confirmation"  # XLK sector leadership confirmation gate
    XLF_CONFIRMATION = "xlf_confirmation"  # XLF financial confirmation gate
    PIVOT_OVERLAY = "pivot_overlay"  # S08 pivot overlay gate (execution qualifier)


class LiquidityGateMode(Enum):
    """Execution mode for the contract-level liquidity gate."""
    OBSERVE = "observe"
    WARN = "warn"
    HARD = "hard"

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
    last_update: datetime = field(default_factory=lambda: datetime.now(UTC))
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

        self.last_update = datetime.now(UTC)

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
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

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
                 paper_trade_learner: Any | None = None,
                 vix_analyzer: Any | None = None,
                 skew_calculator: Any | None = None,
                 market_internals: Any | None = None):
        """Initialize with adaptive learning.

        Args:
            config_manager: System config manager.
            paper_trade_learner: Optional L07 paper-trade learner for adaptation.
            vix_analyzer: Optional C10 VIXAnalyzer for term-structure gating.
            skew_calculator: Optional S06 SKEWCalculator for CBOE SKEW gating.
            market_internals: Optional C04 MarketInternals for TICK/TRIN gating.
        """
        self.logger = TradovLogger.get_logger(__name__)
        self.error_handler = TradovErrorHandler()
        self.config_manager = config_manager
        self.paper_trade_learner = paper_trade_learner
        self.feature_flags = FeatureFlags()
        self.monitor = SystemMonitor()

        # Optional live data sources for macro / market-internals filters
        self._vix_analyzer = vix_analyzer
        self._skew_calculator = skew_calculator
        self._market_internals = market_internals

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
        self.use_adaptive_thresholds = self.config_manager.is_feature_enabled('adaptive_entry_filters')  # noqa: E501
        self.adaptation_interval_hours = config.get('adaptation_interval_hours', 24)
        self.min_trades_for_adaptation = config.get('min_trades_for_adaptation', 20)
        self.adaptation_blend_factor = config.get('adaptation_blend_factor', 0.2)  # 80% base, 20% adapted  # noqa: E501

        # Filter settings
        self.enable_all_filters = config.get('enable_all_filters', True)
        self.min_quality_rating = EntryQuality(config.get('min_quality_rating', 3))
        self.strict_mode = config.get('strict_mode', False)
        self.lean_mode = bool(
            self.config_manager.get_config('autonomous_readiness.lean_mode', False)
        )

        # Time filters
        self.restricted_hours = config.get('restricted_hours', {
            'start': time(9, 30),
            'end': time(15, 30)  # No entries in last 30 min
        })
        self.restricted_days = config.get('restricted_days', [5, 6])  # Saturday, Sunday
        # End-of-day force close time — positions should be closed before this
        self.EOD_FORCE_CLOSE_TIME = time(15, 55)  # 3:55 PM ET

        # Event-clock blackout policy (P0-3).
        event_clock_cfg = self.config_manager.get_config('autonomous_readiness.event_clock', {})
        self.event_clock_policy = {
            'enforce_blackout': bool(event_clock_cfg.get('enforce_blackout', True)),
            'allowlist_strategies': [
                str(s).strip() for s in event_clock_cfg.get('allowlist_strategies', [])
                if str(s).strip()
            ],
        }

        market_structure_cfg = self.config_manager.get_config('autonomous_readiness.market_structure', {})  # noqa: E501
        self.market_structure_policy = {
            'min_surface_confidence': float(market_structure_cfg.get('min_surface_confidence', 0.65)),  # noqa: E501
            'max_surface_age_ms': float(market_structure_cfg.get('max_surface_age_ms', 180000)),
            'min_term_slope_0_7': float(market_structure_cfg.get('min_term_slope_0_7', 0.0)),
            'max_abs_rr_25d': float(market_structure_cfg.get('max_abs_rr_25d', 0.03)),
            'max_abs_fly_25d': float(market_structure_cfg.get('max_abs_fly_25d', 0.03)),
            'min_wall_confidence': float(market_structure_cfg.get('min_wall_confidence', 0.55)),
            'max_flow_imbalance': float(market_structure_cfg.get('max_flow_imbalance', 0.75)),
            'zero_gamma_buffer_pct': float(market_structure_cfg.get('zero_gamma_buffer_pct', 0.50)),
        }

        data_quality_cfg = self.config_manager.get_config('autonomous_readiness.data_quality', {})
        required_buckets = data_quality_cfg.get('required_buckets', ['VOL_SURFACE', 'DEALER_FLOW'])  # noqa: E501
        self.data_quality_policy = {
            'enforce_hard_slo': bool(data_quality_cfg.get('enforce_hard_slo', True)),
            'min_bucket_quality': float(data_quality_cfg.get('min_bucket_quality', 0.60)),
            'required_buckets': [
                str(bucket).strip().upper() for bucket in required_buckets if str(bucket).strip()
            ],
        }

        macro_regime_cfg = self.config_manager.get_config('autonomous_readiness.macro_regime', {})
        self.macro_regime_policy = {
            'vix9d_vix_warn_ratio': float(macro_regime_cfg.get('vix9d_vix_warn_ratio', 1.05)),
            'vix9d_vix_fail_ratio': float(macro_regime_cfg.get('vix9d_vix_fail_ratio', 1.12)),
            'vix9d_warn_abs': float(macro_regime_cfg.get('vix9d_warn_abs', 23.0)),
            'vix9d_fail_abs': float(macro_regime_cfg.get('vix9d_fail_abs', 28.0)),
            'vvix_warn': float(macro_regime_cfg.get('vvix_warn', 100.0)),
            'vvix_fail': float(macro_regime_cfg.get('vvix_fail', 115.0)),
            'cpc_warn_high': float(macro_regime_cfg.get('cpc_warn_high', 1.20)),
            'cpc_fail_high': float(macro_regime_cfg.get('cpc_fail_high', 1.35)),
            'cpc_warn_low': float(macro_regime_cfg.get('cpc_warn_low', 0.70)),
            'cpc_fail_low': float(macro_regime_cfg.get('cpc_fail_low', 0.60)),
            'rvol_warn': float(macro_regime_cfg.get('rvol_warn', 0.80)),
            'rvol_fail': float(macro_regime_cfg.get('rvol_fail', 0.55)),
            'qqq_rel_warn_pct': float(macro_regime_cfg.get('qqq_rel_warn_pct', 0.35)),
            'qqq_rel_fail_pct': float(macro_regime_cfg.get('qqq_rel_fail_pct', 0.75)),
            'iwm_rel_warn_pct': float(macro_regime_cfg.get('iwm_rel_warn_pct', 0.40)),
            'iwm_rel_fail_pct': float(macro_regime_cfg.get('iwm_rel_fail_pct', 0.90)),
            'xlk_rel_warn_pct': float(macro_regime_cfg.get('xlk_rel_warn_pct', 0.45)),
            'xlk_rel_fail_pct': float(macro_regime_cfg.get('xlk_rel_fail_pct', 1.00)),
            'xlf_rel_warn_pct': float(macro_regime_cfg.get('xlf_rel_warn_pct', 0.35)),
            'xlf_rel_fail_pct': float(macro_regime_cfg.get('xlf_rel_fail_pct', 0.80)),
        }

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
            FilterType.LIQUIDITY_QUALITY: 1.8,  # Hard gate for options contract tradability
            FilterType.MARKET_INTERNALS: 1.1,   # TICK/TRIN breadth confirmation
            FilterType.VIX_TERM_STRUCTURE: 1.2,  # VIX backwardation = stress regime
            FilterType.CBOE_SKEW: 1.3,           # SKEW > 145 = elevated tail risk
            FilterType.VOL_SURFACE: 1.4,
            FilterType.DEALER_FLOW: 1.4,
            FilterType.DATA_QUALITY: 2.0,
            FilterType.SHORT_TERM_VOL_STRESS: 1.2,
            FilterType.VOL_OF_VOL_STRESS: 1.1,
            FilterType.PUT_CALL_SENTIMENT: 0.9,
            FilterType.PARTICIPATION: 1.0,
            FilterType.QQQ_CONFIRMATION: 1.0,
            FilterType.IWM_CONFIRMATION: 1.0,
            FilterType.XLK_CONFIRMATION: 1.0,
            FilterType.XLF_CONFIRMATION: 1.0,
            FilterType.PIVOT_OVERLAY: 1.3,
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
        start_time = datetime.now(UTC)

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
                        "Invalid current_price=%s (must be > 0)", val
                    )
                    return self._create_error_result()
                if field_name == 'rsi' and not (0 <= val <= 100):
                    self.logger.warning(
                        "RSI=%s out of range [0,100] — clamping", val
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
            elapsed_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
            if hasattr(self.monitor, 'record_metric'):
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
                'change_pct': (threshold.current_value - threshold.base_value) / threshold.base_value * 100  # noqa: E501
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
            hours_since = (datetime.now(UTC) - self.last_adaptation_time).total_seconds() / 3600
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
                self.logger.info("Not enough trades for adaptation: %s < %s", trade_count, self.min_trades_for_adaptation)  # noqa: E501
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

            self.last_adaptation_time = datetime.now(UTC)
            self.logger.info("Entry filter thresholds adapted from paper trading")

        except Exception as e:
            self.logger.warning("Threshold adaptation failed: %s", e, exc_info=True)

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
        checks.extend(self._check_pivot_overlay_filter(params))

        # Risk filters
        checks.extend(self._check_risk_filters(params))
        checks.extend(self._check_time_filters(params))

        # Market-structure / trust-policy filters
        checks.extend(self._check_data_quality_filter(params))
        checks.extend(self._check_vol_surface_structure_filter(params))
        checks.extend(self._check_dealer_flow_filter(params))
        checks.extend(self._check_short_term_vol_stress_filter(params))
        checks.extend(self._check_vix_term_structure_filter())

        # Execution quality filters
        checks.extend(self._check_spread_width_filter(params))
        checks.extend(self._check_liquidity_quality_filter(params))

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

    def _check_pivot_overlay_filter(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Apply TradovS08 pivot signal as execution qualifier for entry timing."""
        checks = []

        signal = params.get('pivot_mr_signal')
        if not isinstance(signal, dict):
            market_conditions = params.get('market_conditions') or {}
            signal = (
                market_conditions.get('pivot_mr_signal')
                or market_conditions.get('s08_pivot_signal')
                or market_conditions.get('pivot_signal')
            )

        if not isinstance(signal, dict):
            return checks

        strategy_type = str(params.get('strategy_type', '')).strip().lower()
        direction = str(signal.get('direction', 'none')).strip().lower()
        fired = bool(signal.get('fired', False))
        score = int(signal.get('score', 0) or 0)
        level_name = str(signal.get('nearest_level_name', '') or '')
        level_price = signal.get('nearest_level_price')
        atr_distance = signal.get('atr_distance')
        penalties = signal.get('penalties') or []
        penalty_text = ' | '.join(str(p) for p in penalties if p)

        if isinstance(level_price, (int, float)):
            level_ctx = f"{level_name}@{level_price:.2f}" if level_name else f"@{level_price:.2f}"
        else:
            level_ctx = level_name or "-"

        if strategy_type == 'bull_put_spread':
            if fired and direction == 'fade_resistance':
                checks.append(FilterCheck(
                    filter_type=FilterType.PIVOT_OVERLAY,
                    result=FilterResult.FAIL,
                    value=float(score),
                    threshold=60.0,
                    message=(
                        f"pivot_block_reason=pivot_direction_conflict; "
                        f"strategy=bull_put_spread; direction={direction}; "
                        f"nearest={level_ctx}; atr_distance={atr_distance}"
                    ),
                    weight=self.filter_weights[FilterType.PIVOT_OVERLAY],
                ))
            elif fired and direction == 'fade_support':
                checks.append(FilterCheck(
                    filter_type=FilterType.PIVOT_OVERLAY,
                    result=FilterResult.PASS,
                    value=float(score),
                    threshold=60.0,
                    message=(
                        f"Pivot overlay aligned for bullish entry; "
                        f"direction={direction}; nearest={level_ctx}; atr_distance={atr_distance}"
                    ),
                    weight=self.filter_weights[FilterType.PIVOT_OVERLAY],
                ))

        elif strategy_type == 'bear_call_spread':
            if fired and direction == 'fade_support':
                checks.append(FilterCheck(
                    filter_type=FilterType.PIVOT_OVERLAY,
                    result=FilterResult.FAIL,
                    value=float(score),
                    threshold=60.0,
                    message=(
                        f"pivot_block_reason=pivot_direction_conflict; "
                        f"strategy=bear_call_spread; direction={direction}; "
                        f"nearest={level_ctx}; atr_distance={atr_distance}"
                    ),
                    weight=self.filter_weights[FilterType.PIVOT_OVERLAY],
                ))
            elif fired and direction == 'fade_resistance':
                checks.append(FilterCheck(
                    filter_type=FilterType.PIVOT_OVERLAY,
                    result=FilterResult.PASS,
                    value=float(score),
                    threshold=60.0,
                    message=(
                        f"Pivot overlay aligned for bearish entry; "
                        f"direction={direction}; nearest={level_ctx}; atr_distance={atr_distance}"
                    ),
                    weight=self.filter_weights[FilterType.PIVOT_OVERLAY],
                ))

        elif strategy_type in {'iron_condor', 'iron_butterfly'}:
            if fired and direction in {'fade_resistance', 'fade_support'}:
                checks.append(FilterCheck(
                    filter_type=FilterType.PIVOT_OVERLAY,
                    result=FilterResult.WARNING,
                    value=float(score),
                    threshold=60.0,
                    message=(
                        f"pivot_block_reason=pivot_directional_pressure; "
                        f"strategy={strategy_type}; direction={direction}; "
                        f"nearest={level_ctx}; atr_distance={atr_distance}"
                    ),
                    weight=self.filter_weights[FilterType.PIVOT_OVERLAY],
                ))

        if not fired and penalty_text:
            checks.append(FilterCheck(
                filter_type=FilterType.PIVOT_OVERLAY,
                result=FilterResult.WARNING,
                value=float(score),
                threshold=60.0,
                message=(
                    f"pivot_block_reason=pivot_signal_not_armed; penalties={penalty_text}; "
                    f"nearest={level_ctx}; atr_distance={atr_distance}"
                ),
                weight=self.filter_weights[FilterType.PIVOT_OVERLAY] * 0.8,
            ))

        if not checks:
            checks.append(FilterCheck(
                filter_type=FilterType.PIVOT_OVERLAY,
                result=FilterResult.PASS,
                value=float(score),
                threshold=60.0,
                message=(
                    f"Pivot overlay neutral; direction={direction}; fired={fired}; "
                    f"nearest={level_ctx}; atr_distance={atr_distance}"
                ),
                weight=self.filter_weights[FilterType.PIVOT_OVERLAY],
            ))

        return checks

    def _check_time_filters(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Check time-based filters."""
        checks = []

        current_time = params.get('current_time', datetime.now(UTC))

        # Economic event blackout gate from scheduler event-clock feed.
        event_clock_state = params.get('event_clock_state') or {}
        event_state = str(event_clock_state.get('state', 'clear')).lower()
        if self.event_clock_policy['enforce_blackout'] and event_state in {'pre', 'live', 'post'}:
            strategy_id = str(
                params.get('strategy_id')
                or params.get('strategy')
                or params.get('strategy_name')
                or ''
            ).strip()
            allowed_strategies = event_clock_state.get('allowed_strategies') or self.event_clock_policy['allowlist_strategies']  # noqa: E501
            allowlist = {str(s).strip() for s in allowed_strategies if str(s).strip()}

            if strategy_id and strategy_id in allowlist:
                checks.append(FilterCheck(
                    filter_type=FilterType.ECONOMIC_EVENTS,
                    result=FilterResult.WARNING,
                    value=1.0,
                    threshold=0.0,
                    message=f"Event-clock blackout ({event_state}) active; allowlisted strategy {strategy_id}",  # noqa: E501
                    weight=self.filter_weights[FilterType.ECONOMIC_EVENTS],
                ))
            else:
                event_type = event_clock_state.get('event_type', 'macro_event')
                checks.append(FilterCheck(
                    filter_type=FilterType.ECONOMIC_EVENTS,
                    result=FilterResult.FAIL,
                    value=1.0,
                    threshold=0.0,
                    message=f"Event-clock blackout ({event_state}) active for {event_type}",
                    weight=self.filter_weights[FilterType.ECONOMIC_EVENTS],
                ))

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

        Performs two checks:
          1. Symbol-level: rejects if too many existing positions share the
             same underlying root (accumulation of directional exposure).
          2. Portfolio-level Greek correlation: when portfolio Greek totals
             are supplied (via `portfolio_greeks`) together with the candidate
             order's expected Greek contribution (via `candidate_greeks`),
             blocks entries that would push net delta/gamma/vega past the
             `max_portfolio_[delta|gamma|vega]` thresholds. This is the gate
             that stops "30 short-delta positions adding up to a -4,500 delta
             book" without the operator ever seeing a single oversized order.
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

            # Portfolio-level Greek aggregation gate
            portfolio_greeks = entry_params.get('portfolio_greeks') or {}
            candidate_greeks = entry_params.get('candidate_greeks') or {}
            if portfolio_greeks and candidate_greeks:
                for greek in ("delta", "gamma", "vega"):
                    limit_key = f"max_portfolio_{greek}"
                    limit = entry_params.get(limit_key)
                    if limit is None:
                        continue
                    projected = float(portfolio_greeks.get(greek, 0.0)) + float(
                        candidate_greeks.get(greek, 0.0)
                    )
                    ok = abs(projected) <= float(limit)
                    results.append(FilterCheck(
                        filter_type=FilterType.CORRELATION,
                        result=FilterResult.PASS if ok else FilterResult.FAIL,
                        value=abs(projected),
                        threshold=float(limit),
                        message=(
                            f"Portfolio {greek} projection: {projected:+.2f} vs "
                            f"limit ±{float(limit):.2f} "
                            f"({'OK' if ok else 'BREACH'})"
                        ),
                        weight=self.filter_weights[FilterType.CORRELATION],
                    ))
        except Exception as e:
            self.logger.warning("Correlation filter check failed: %s", e, exc_info=True)
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

    def _check_liquidity_quality_filter(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Hard gate for contract-level liquidity quality when snapshot is provided."""
        snapshot = params.get('liquidity_snapshot')
        if not isinstance(snapshot, dict) or not snapshot:
            return [FilterCheck(
                filter_type=FilterType.LIQUIDITY_QUALITY,
                result=FilterResult.SKIP,
                value=0.0,
                threshold=1.0,
                message="Liquidity snapshot unavailable — filter skipped",
                weight=0.0,
            )]

        gate_mode = self._get_liquidity_gate_mode()
        allowed, reasons = self.evaluate_liquidity_gate(snapshot, gate_mode=gate_mode)
        if not allowed:
            return [FilterCheck(
                filter_type=FilterType.LIQUIDITY_QUALITY,
                result=FilterResult.FAIL,
                value=0.0,
                threshold=1.0,
                message=f"Liquidity gate blocked entry: {'; '.join(reasons)}",
                weight=self.filter_weights[FilterType.LIQUIDITY_QUALITY],
            )]

        if reasons:
            result = FilterResult.WARNING if gate_mode == LiquidityGateMode.WARN else FilterResult.PASS  # noqa: E501
            message_prefix = "Liquidity gate warning" if gate_mode == LiquidityGateMode.WARN else "Liquidity gate observe"  # noqa: E501
            return [FilterCheck(
                filter_type=FilterType.LIQUIDITY_QUALITY,
                result=result,
                value=1.0,
                threshold=1.0,
                message=f"{message_prefix}: {'; '.join(reasons)}",
                weight=self.filter_weights[FilterType.LIQUIDITY_QUALITY],
            )]

        return [FilterCheck(
            filter_type=FilterType.LIQUIDITY_QUALITY,
            result=FilterResult.PASS,
            value=1.0,
            threshold=1.0,
            message="Liquidity gate passed",
            weight=self.filter_weights[FilterType.LIQUIDITY_QUALITY],
        )]

    def _get_liquidity_gate_mode(self) -> LiquidityGateMode:
        """Return the configured liquidity gate mode."""
        liquidity_cfg = self.config_manager.get_config('autonomous_readiness.liquidity', {})
        raw_mode = str(liquidity_cfg.get('gate_mode', LiquidityGateMode.HARD.value)).strip().lower()
        for mode in LiquidityGateMode:
            if mode.value == raw_mode:
                return mode
        return LiquidityGateMode.HARD

    def evaluate_liquidity_gate(
        self,
        liquidity_snapshot: dict[str, Any],
        thresholds: dict[str, float] | None = None,
        gate_mode: LiquidityGateMode | str | None = None,
    ) -> tuple[bool, list[str]]:
        """Evaluate contract liquidity thresholds for pre-trade gating."""
        if not isinstance(liquidity_snapshot, dict) or not liquidity_snapshot:
            return False, ["liquidity_snapshot unavailable"]

        if gate_mode is None:
            resolved_mode = self._get_liquidity_gate_mode()
        elif isinstance(gate_mode, LiquidityGateMode):
            resolved_mode = gate_mode
        else:
            resolved_mode = LiquidityGateMode(str(gate_mode).strip().lower()) if str(gate_mode).strip().lower() in {m.value for m in LiquidityGateMode} else LiquidityGateMode.HARD  # noqa: E501

        # Load liquidity thresholds from A03 config (P0-1)
        liquidity_cfg = self.config_manager.get_config('autonomous_readiness.liquidity', {})
        t = {
            'max_spread_pct': float(liquidity_cfg.get('max_spread_pct', 0.12)),
            'max_spread_abs': float(liquidity_cfg.get('max_spread_abs', 0.20)),
            'max_quote_age_ms': int(liquidity_cfg.get('max_quote_age_ms', 1500)),
            'min_top_of_book_size': int(liquidity_cfg.get('min_top_of_book_size', 10)),
            'min_open_interest': int(liquidity_cfg.get('min_open_interest', 500)),
            'min_volume': int(liquidity_cfg.get('min_volume', 50)),
            'min_oi_change_pct': float(liquidity_cfg.get('min_oi_change_pct', -0.20)),
        }
  # noqa: W293
        # Allow parameter override (for testing)
        if isinstance(thresholds, dict):
            for key, value in thresholds.items():
                if key in t and isinstance(value, (int, float)):
                    t[key] = float(value) if key in ['max_spread_pct', 'max_spread_abs', 'min_oi_change_pct'] else int(value)  # noqa: E501

        reasons: list[str] = []

        def _check_non_negative(name: str) -> float | None:
            value = liquidity_snapshot.get(name)
            if isinstance(value, (int, float)):
                numeric_value = float(value)
                if numeric_value < 0:
                    reasons.append(f"{name} {numeric_value:.4f} < 0")
                return numeric_value
            return None

        spread_pct = _check_non_negative('spread_pct')
        if spread_pct is not None and spread_pct > t['max_spread_pct']:
            reasons.append(
                f"spread_pct {spread_pct:.4f} > max_spread_pct {t['max_spread_pct']:.4f}"
            )

        spread_abs = _check_non_negative('spread_abs')
        if spread_abs is not None and spread_abs > t['max_spread_abs']:
            reasons.append(
                f"spread_abs {spread_abs:.4f} > max_spread_abs {t['max_spread_abs']:.4f}"
            )

        quote_age_ms = _check_non_negative('quote_age_ms')
        if quote_age_ms is not None and quote_age_ms > t['max_quote_age_ms']:
            reasons.append(
                f"quote_age_ms {quote_age_ms:.0f} > max_quote_age_ms {t['max_quote_age_ms']:.0f}"
            )

        top_of_book_size = _check_non_negative('top_of_book_size')
        if top_of_book_size is not None and top_of_book_size < t['min_top_of_book_size']:
            reasons.append(
                f"top_of_book_size {top_of_book_size:.0f} < min_top_of_book_size {t['min_top_of_book_size']:.0f}"  # noqa: E501
            )

        open_interest = _check_non_negative('open_interest')
        if open_interest is not None and open_interest < t['min_open_interest']:
            reasons.append(
                f"open_interest {open_interest:.0f} < min_open_interest {t['min_open_interest']:.0f}"  # noqa: E501
            )

        volume = _check_non_negative('volume')
        if volume is not None and volume < t['min_volume']:
            reasons.append(f"volume {volume:.0f} < min_volume {t['min_volume']:.0f}")

        oi_change_pct = liquidity_snapshot.get('oi_change_pct')
        if isinstance(oi_change_pct, (int, float)) and float(oi_change_pct) < t['min_oi_change_pct']:  # noqa: E501
            reasons.append(
                f"oi_change_pct {float(oi_change_pct):.4f} < min_oi_change_pct {t['min_oi_change_pct']:.4f}"  # noqa: E501
            )

        if reasons and resolved_mode == LiquidityGateMode.HARD:
            return False, reasons

        return True, reasons

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

    def _get_market_condition_value(self, params: dict[str, Any], key: str, default: Any = None) -> Any:  # noqa: E501
        """Return a value from flat params first, then nested market_conditions."""
        if key in params:
            return params.get(key, default)
        market_conditions = params.get('market_conditions')
        if isinstance(market_conditions, dict):
            return market_conditions.get(key, default)
        return default

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        """Return a finite float or None."""
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric if np.isfinite(numeric) else None

    def _infer_expected_direction(self, params: dict[str, Any]) -> str | None:
        """Infer the expected trade direction for lead-lag confirmation."""
        candidates = [
            params.get('direction'),
            params.get('bias'),
            params.get('position_type'),
            self._get_market_condition_value(params, 'direction'),
        ]
        strategy_type = str(params.get('strategy_type', '')).strip().lower()

        if any(token in strategy_type for token in ('iron_condor', 'straddle', 'strangle', 'butterfly', 'calendar')):  # noqa: E501
            return 'neutral'

        for raw in candidates:
            value = str(raw or '').strip().lower()
            if value in {'up', 'bull', 'bullish', 'long'}:
                return 'up'
            if value in {'down', 'bear', 'bearish', 'short'}:
                return 'down'
            if value in {'neutral', 'flat'}:
                return 'neutral'

        if 'bull' in strategy_type or strategy_type.endswith('_call'):
            return 'up'
        if 'bear' in strategy_type or strategy_type.endswith('_put'):
            return 'down'
        return None

    def _check_data_quality_filter(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Enforce data-quality SLOs as a hard trust policy when the feed is present."""
        feed = self._get_market_condition_value(params, 'data_quality_feed')
        if not isinstance(feed, dict) or not feed:
            if self.data_quality_policy['enforce_hard_slo']:
                return [FilterCheck(
                    filter_type=FilterType.DATA_QUALITY,
                    result=FilterResult.FAIL,
                    value=0.0,
                    threshold=1.0,
                    message='Data-quality feed absent — hard SLO enforced, entry blocked',
                    weight=self.filter_weights[FilterType.DATA_QUALITY],
                )]
            return [FilterCheck(
                filter_type=FilterType.DATA_QUALITY,
                result=FilterResult.SKIP,
                value=0.0,
                threshold=1.0,
                message='Data-quality feed unavailable — filter skipped',
                weight=0.0,
            )]

        data = feed.get('data') if isinstance(feed.get('data'), dict) else feed
        if not isinstance(data, dict):
            return [FilterCheck(
                filter_type=FilterType.DATA_QUALITY,
                result=FilterResult.SKIP,
                value=0.0,
                threshold=1.0,
                message='Data-quality feed malformed — filter skipped',
                weight=0.0,
            )]

        slo_status = data.get('slo_status') if isinstance(data.get('slo_status'), dict) else {}
        quality_buckets = data.get('quality_buckets') if isinstance(data.get('quality_buckets'), dict) else {}  # noqa: E501
        overall_quality = self._coerce_float(data.get('overall_quality'))

        failures: list[str] = []
        if self.data_quality_policy['enforce_hard_slo'] and slo_status:
            for name, ok in slo_status.items():
                if name == 'all_ok':
                    continue
                if ok is False:
                    failures.append(name)

        for bucket_name in self.data_quality_policy['required_buckets']:
            bucket = quality_buckets.get(bucket_name)
            if not isinstance(bucket, dict):
                failures.append(f'{bucket_name.lower()}_missing')
                continue

            bucket_quality = self._coerce_float(bucket.get('quality_score'))
            if bucket.get('stale'):
                failures.append(f'{bucket_name.lower()}_stale')
            if bucket.get('source_available') is False:
                failures.append(f'{bucket_name.lower()}_source_unavailable')
            if bucket_quality is None or bucket_quality < self.data_quality_policy['min_bucket_quality']:  # noqa: E501
                failures.append(f'{bucket_name.lower()}_quality_low')

        if failures:
            return [FilterCheck(
                filter_type=FilterType.DATA_QUALITY,
                result=FilterResult.FAIL,
                value=overall_quality if overall_quality is not None else 0.0,
                threshold=1.0,
                message=f'Data-quality trust policy failed: {", ".join(failures)}',
                weight=self.filter_weights[FilterType.DATA_QUALITY],
            )]

        return [FilterCheck(
            filter_type=FilterType.DATA_QUALITY,
            result=FilterResult.PASS,
            value=overall_quality if overall_quality is not None else 1.0,
            threshold=1.0,
            message='Data-quality trust policy passed',
            weight=self.filter_weights[FilterType.DATA_QUALITY],
        )]

    def _check_vol_surface_structure_filter(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Gate entries on vol-surface freshness, confidence, and front-end structure."""
        surface_confidence = self._coerce_float(self._get_market_condition_value(params, 'surface_confidence'))  # noqa: E501
        surface_age_ms = self._coerce_float(self._get_market_condition_value(params, 'surface_age_ms'))  # noqa: E501
        term_slope_0_7 = self._coerce_float(self._get_market_condition_value(params, 'term_slope_0_7'))  # noqa: E501
        rr_25d = self._coerce_float(self._get_market_condition_value(params, 'rr_25d'))
        fly_25d = self._coerce_float(self._get_market_condition_value(params, 'fly_25d'))

        if all(value is None for value in (surface_confidence, surface_age_ms, term_slope_0_7, rr_25d, fly_25d)):  # noqa: E501
            if self.data_quality_policy['enforce_hard_slo']:
                return [FilterCheck(
                    filter_type=FilterType.VOL_SURFACE,
                    result=FilterResult.FAIL,
                    value=0.0,
                    threshold=1.0,
                    message='Vol-surface snapshot absent — hard SLO enforced, entry blocked',
                    weight=self.filter_weights[FilterType.VOL_SURFACE],
                )]
            return [FilterCheck(
                filter_type=FilterType.VOL_SURFACE,
                result=FilterResult.SKIP,
                value=0.0,
                threshold=1.0,
                message='Vol-surface snapshot unavailable — filter skipped',
                weight=0.0,
            )]

        if surface_confidence is None or surface_confidence < self.market_structure_policy['min_surface_confidence']:  # noqa: E501
            return [FilterCheck(
                filter_type=FilterType.VOL_SURFACE,
                result=FilterResult.FAIL,
                value=surface_confidence or 0.0,
                threshold=self.market_structure_policy['min_surface_confidence'],
                message='Vol-surface confidence too low for entry decision',
                weight=self.filter_weights[FilterType.VOL_SURFACE],
            )]

        if surface_age_ms is None or surface_age_ms > self.market_structure_policy['max_surface_age_ms']:  # noqa: E501
            return [FilterCheck(
                filter_type=FilterType.VOL_SURFACE,
                result=FilterResult.FAIL,
                value=surface_age_ms or 0.0,
                threshold=self.market_structure_policy['max_surface_age_ms'],
                message='Vol-surface snapshot stale for live decisioning',
                weight=self.filter_weights[FilterType.VOL_SURFACE],
            )]

        if term_slope_0_7 is not None and term_slope_0_7 < self.market_structure_policy['min_term_slope_0_7']:  # noqa: E501
            return [FilterCheck(
                filter_type=FilterType.VOL_SURFACE,
                result=FilterResult.FAIL,
                value=term_slope_0_7,
                threshold=self.market_structure_policy['min_term_slope_0_7'],
                message=f'Front-end vol term structure inverted: slope_0_7={term_slope_0_7:.2f}',
                weight=self.filter_weights[FilterType.VOL_SURFACE],
            )]

        extreme_smile = []
        if rr_25d is not None and abs(rr_25d) > self.market_structure_policy['max_abs_rr_25d']:
            extreme_smile.append(f'rr_25d={rr_25d:.3f}')
        if fly_25d is not None and abs(fly_25d) > self.market_structure_policy['max_abs_fly_25d']:
            extreme_smile.append(f'fly_25d={fly_25d:.3f}')
        if extreme_smile:
            return [FilterCheck(
                filter_type=FilterType.VOL_SURFACE,
                result=FilterResult.WARNING,
                value=surface_confidence,
                threshold=self.market_structure_policy['max_abs_rr_25d'],
                message=f'Vol-surface smile extreme: {", ".join(extreme_smile)}',
                weight=self.filter_weights[FilterType.VOL_SURFACE],
            )]

        return [FilterCheck(
            filter_type=FilterType.VOL_SURFACE,
            result=FilterResult.PASS,
            value=surface_confidence,
            threshold=self.market_structure_policy['min_surface_confidence'],
            message='Vol-surface structure acceptable',
            weight=self.filter_weights[FilterType.VOL_SURFACE],
        )]

    def _check_dealer_flow_filter(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Gate entries on dealer-flow confidence and unstable short-gamma structure."""
        dealer_flow = self._get_market_condition_value(params, 'dealer_flow', {})
        if not isinstance(dealer_flow, dict):
            dealer_flow = {}

        wall_confidence = self._coerce_float(self._get_market_condition_value(params, 'wall_confidence'))  # noqa: E501
        if wall_confidence is None:
            wall_confidence = self._coerce_float(dealer_flow.get('wall_confidence'))

        flow_imbalance = self._coerce_float(self._get_market_condition_value(params, 'flow_imbalance'))  # noqa: E501
        if flow_imbalance is None:
            flow_imbalance = self._coerce_float(dealer_flow.get('flow_imbalance_score'))

        spot_to_zero_gamma_pct = self._coerce_float(dealer_flow.get('spot_to_zero_gamma_pct'))
        dealer_position = str(dealer_flow.get('dealer_position') or dealer_flow.get('regime') or '').strip().lower()  # noqa: E501

        if wall_confidence is None and flow_imbalance is None and spot_to_zero_gamma_pct is None and not dealer_position:  # noqa: E501
            if self.data_quality_policy['enforce_hard_slo']:
                return [FilterCheck(
                    filter_type=FilterType.DEALER_FLOW,
                    result=FilterResult.FAIL,
                    value=0.0,
                    threshold=1.0,
                    message='Dealer-flow snapshot absent — hard SLO enforced, entry blocked',
                    weight=self.filter_weights[FilterType.DEALER_FLOW],
                )]
            return [FilterCheck(
                filter_type=FilterType.DEALER_FLOW,
                result=FilterResult.SKIP,
                value=0.0,
                threshold=1.0,
                message='Dealer-flow snapshot unavailable — filter skipped',
                weight=0.0,
            )]

        if wall_confidence is None or wall_confidence < self.market_structure_policy['min_wall_confidence']:  # noqa: E501
            return [FilterCheck(
                filter_type=FilterType.DEALER_FLOW,
                result=FilterResult.FAIL,
                value=wall_confidence or 0.0,
                threshold=self.market_structure_policy['min_wall_confidence'],
                message='Dealer-flow confidence too low for entry decision',
                weight=self.filter_weights[FilterType.DEALER_FLOW],
            )]

        if dealer_position == 'short_gamma' and spot_to_zero_gamma_pct is not None:
            if abs(spot_to_zero_gamma_pct) <= self.market_structure_policy['zero_gamma_buffer_pct']:
                return [FilterCheck(
                    filter_type=FilterType.DEALER_FLOW,
                    result=FilterResult.FAIL,
                    value=abs(spot_to_zero_gamma_pct),
                    threshold=self.market_structure_policy['zero_gamma_buffer_pct'],
                    message='Dealer short-gamma regime too close to zero-gamma flip level',
                    weight=self.filter_weights[FilterType.DEALER_FLOW],
                )]

        if flow_imbalance is not None and abs(flow_imbalance) >= self.market_structure_policy['max_flow_imbalance']:  # noqa: E501
            return [FilterCheck(
                filter_type=FilterType.DEALER_FLOW,
                result=FilterResult.WARNING,
                value=abs(flow_imbalance),
                threshold=self.market_structure_policy['max_flow_imbalance'],
                message=f'Dealer-flow pressure extreme: imbalance={flow_imbalance:.2f}',
                weight=self.filter_weights[FilterType.DEALER_FLOW],
            )]

        return [FilterCheck(
            filter_type=FilterType.DEALER_FLOW,
            result=FilterResult.PASS,
            value=wall_confidence,
            threshold=self.market_structure_policy['min_wall_confidence'],
            message='Dealer-flow structure acceptable',
            weight=self.filter_weights[FilterType.DEALER_FLOW],
        )]

    # --------------------------------------------------------------------------
    # Macro / Market-Internals Filters (Wave 2 — live data sources)
    # --------------------------------------------------------------------------

    def _check_short_term_vol_stress_filter(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Gate entries when short-dated volatility leads spot VIX too aggressively."""
        vix = self._coerce_float(self._get_market_condition_value(params, 'vix'))
        vix9d = self._coerce_float(self._get_market_condition_value(params, 'vix9d'))

        if vix is None or vix <= 0 or vix9d is None:
            return [FilterCheck(
                filter_type=FilterType.SHORT_TERM_VOL_STRESS,
                result=FilterResult.SKIP,
                value=0.0,
                threshold=self.macro_regime_policy['vix9d_vix_warn_ratio'],
                message='VIX/VIX9D snapshot unavailable — filter skipped',
                weight=0.0,
            )]

        ratio = vix9d / vix
        warn_ratio = self.macro_regime_policy['vix9d_vix_warn_ratio']
        fail_ratio = self.macro_regime_policy['vix9d_vix_fail_ratio']
        warn_abs = self.macro_regime_policy['vix9d_warn_abs']
        fail_abs = self.macro_regime_policy['vix9d_fail_abs']

        if ratio >= fail_ratio or vix9d >= fail_abs:
            return [FilterCheck(
                filter_type=FilterType.SHORT_TERM_VOL_STRESS,
                result=FilterResult.FAIL,
                value=ratio,
                threshold=fail_ratio,
                message=(
                    f'Short-term vol stress elevated: VIX9D/VIX={ratio:.3f}, '
                    f'VIX9D={vix9d:.2f}; front-end panic regime'
                ),
                weight=self.filter_weights[FilterType.SHORT_TERM_VOL_STRESS],
            )]

        if ratio >= warn_ratio or vix9d >= warn_abs:
            return [FilterCheck(
                filter_type=FilterType.SHORT_TERM_VOL_STRESS,
                result=FilterResult.WARNING,
                value=ratio,
                threshold=warn_ratio,
                message=(
                    f'Short-term volatility caution: VIX9D/VIX={ratio:.3f}, '
                    f'VIX9D={vix9d:.2f}'
                ),
                weight=self.filter_weights[FilterType.SHORT_TERM_VOL_STRESS],
            )]

        return [FilterCheck(
            filter_type=FilterType.SHORT_TERM_VOL_STRESS,
            result=FilterResult.PASS,
            value=ratio,
            threshold=warn_ratio,
            message=f'Short-term volatility structure acceptable: VIX9D/VIX={ratio:.3f}',
            weight=self.filter_weights[FilterType.SHORT_TERM_VOL_STRESS],
        )]

    def _check_vol_of_vol_stress_filter(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Gate entries when VVIX signals unstable vol-of-vol conditions."""
        vvix = self._coerce_float(self._get_market_condition_value(params, 'vvix'))
        if vvix is None:
            return [FilterCheck(
                filter_type=FilterType.VOL_OF_VOL_STRESS,
                result=FilterResult.SKIP,
                value=0.0,
                threshold=self.macro_regime_policy['vvix_warn'],
                message='VVIX snapshot unavailable — filter skipped',
                weight=0.0,
            )]

        vvix_warn = self.macro_regime_policy['vvix_warn']
        vvix_fail = self.macro_regime_policy['vvix_fail']
        if vvix >= vvix_fail:
            return [FilterCheck(
                filter_type=FilterType.VOL_OF_VOL_STRESS,
                result=FilterResult.FAIL,
                value=vvix,
                threshold=vvix_fail,
                message=f'VVIX={vvix:.1f} indicates severe vol-of-vol stress',
                weight=self.filter_weights[FilterType.VOL_OF_VOL_STRESS],
            )]

        if vvix >= vvix_warn:
            return [FilterCheck(
                filter_type=FilterType.VOL_OF_VOL_STRESS,
                result=FilterResult.WARNING,
                value=vvix,
                threshold=vvix_warn,
                message=f'VVIX={vvix:.1f} elevated; size/risk should be reduced',
                weight=self.filter_weights[FilterType.VOL_OF_VOL_STRESS],
            )]

        return [FilterCheck(
            filter_type=FilterType.VOL_OF_VOL_STRESS,
            result=FilterResult.PASS,
            value=vvix,
            threshold=vvix_warn,
            message=f'VVIX stable: {vvix:.1f}',
            weight=self.filter_weights[FilterType.VOL_OF_VOL_STRESS],
        )]

    def _check_put_call_sentiment_filter(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Flag crowding/extremes in put-call sentiment from CPC."""
        cpc = self._coerce_float(self._get_market_condition_value(params, 'cpc'))
        if cpc is None:
            return [FilterCheck(
                filter_type=FilterType.PUT_CALL_SENTIMENT,
                result=FilterResult.SKIP,
                value=0.0,
                threshold=self.macro_regime_policy['cpc_warn_high'],
                message='CPC snapshot unavailable — filter skipped',
                weight=0.0,
            )]

        cpc_warn_high = self.macro_regime_policy['cpc_warn_high']
        cpc_fail_high = self.macro_regime_policy['cpc_fail_high']
        cpc_warn_low = self.macro_regime_policy['cpc_warn_low']
        cpc_fail_low = self.macro_regime_policy['cpc_fail_low']

        if cpc >= cpc_fail_high:
            return [FilterCheck(
                filter_type=FilterType.PUT_CALL_SENTIMENT,
                result=FilterResult.FAIL,
                value=cpc,
                threshold=cpc_fail_high,
                message=f'CPC={cpc:.2f} at panic extreme; avoid new discretionary risk',
                weight=self.filter_weights[FilterType.PUT_CALL_SENTIMENT],
            )]

        if cpc <= cpc_fail_low:
            return [FilterCheck(
                filter_type=FilterType.PUT_CALL_SENTIMENT,
                result=FilterResult.FAIL,
                value=cpc,
                threshold=cpc_fail_low,
                message=f'CPC={cpc:.2f} at complacency extreme; crowding risk elevated',
                weight=self.filter_weights[FilterType.PUT_CALL_SENTIMENT],
            )]

        if cpc >= cpc_warn_high or cpc <= cpc_warn_low:
            return [FilterCheck(
                filter_type=FilterType.PUT_CALL_SENTIMENT,
                result=FilterResult.WARNING,
                value=cpc,
                threshold=cpc_warn_high,
                message=f'CPC={cpc:.2f} at sentiment extreme; proceed with tighter risk',
                weight=self.filter_weights[FilterType.PUT_CALL_SENTIMENT],
            )]

        return [FilterCheck(
            filter_type=FilterType.PUT_CALL_SENTIMENT,
            result=FilterResult.PASS,
            value=cpc,
            threshold=cpc_warn_high,
            message=f'CPC sentiment neutral: {cpc:.2f}',
            weight=self.filter_weights[FilterType.PUT_CALL_SENTIMENT],
        )]

    def _check_participation_filter(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Require minimum RVOL participation before accepting directional risk."""
        rvol = self._coerce_float(self._get_market_condition_value(params, 'rvol'))
        if rvol is None:
            return [FilterCheck(
                filter_type=FilterType.PARTICIPATION,
                result=FilterResult.SKIP,
                value=0.0,
                threshold=self.macro_regime_policy['rvol_warn'],
                message='RVOL snapshot unavailable — filter skipped',
                weight=0.0,
            )]

        rvol_warn = self.macro_regime_policy['rvol_warn']
        rvol_fail = self.macro_regime_policy['rvol_fail']
        expected_direction = self._infer_expected_direction(params)
        is_directional = expected_direction in {'up', 'down'}

        if is_directional and rvol < rvol_fail:
            return [FilterCheck(
                filter_type=FilterType.PARTICIPATION,
                result=FilterResult.FAIL,
                value=rvol,
                threshold=rvol_fail,
                message=f'RVOL={rvol:.2f} too weak for directional entry',
                weight=self.filter_weights[FilterType.PARTICIPATION],
            )]

        if rvol < rvol_warn:
            return [FilterCheck(
                filter_type=FilterType.PARTICIPATION,
                result=FilterResult.WARNING,
                value=rvol,
                threshold=rvol_warn,
                message=f'RVOL={rvol:.2f} below preferred participation level',
                weight=self.filter_weights[FilterType.PARTICIPATION],
            )]

        return [FilterCheck(
            filter_type=FilterType.PARTICIPATION,
            result=FilterResult.PASS,
            value=rvol,
            threshold=rvol_warn,
            message=f'RVOL participation acceptable: {rvol:.2f}',
            weight=self.filter_weights[FilterType.PARTICIPATION],
        )]

    def _check_relative_confirmation_filter(
        self,
        params: dict[str, Any],
        *,
        symbol_name: str,
        filter_type: FilterType,
        symbol_change_key: str,
        warn_threshold: float,
        fail_threshold: float,
    ) -> list[FilterCheck]:
        """Require cross-index confirmation relative to TRAD for directional entries."""
        expected_direction = self._infer_expected_direction(params)
        if expected_direction not in {'up', 'down'}:
            return [FilterCheck(
                filter_type=filter_type,
                result=FilterResult.SKIP,
                value=0.0,
                threshold=warn_threshold,
                message=f'{symbol_name} confirmation not required for neutral strategy',
                weight=0.0,
            )]

        spy_change_pct = self._coerce_float(self._get_market_condition_value(params, 'spy_change_pct'))
        symbol_change_pct = self._coerce_float(self._get_market_condition_value(params, symbol_change_key))
        if spy_change_pct is None or symbol_change_pct is None:
            return [FilterCheck(
                filter_type=filter_type,
                result=FilterResult.SKIP,
                value=0.0,
                threshold=warn_threshold,
                message=f'{symbol_name}/TRAD relative-performance snapshot unavailable — filter skipped',
                weight=0.0,
            )]

        relative_change = symbol_change_pct - spy_change_pct
        if expected_direction == 'up':
            if relative_change <= -fail_threshold:
                return [FilterCheck(
                    filter_type=filter_type,
                    result=FilterResult.FAIL,
                    value=relative_change,
                    threshold=-fail_threshold,
                    message=(
                        f'{symbol_name} underperforming TRAD by {abs(relative_change):.2f} pts '
                        f'on bullish setup ({symbol_change_pct:+.2f}% vs TRAD {spy_change_pct:+.2f}%)'
                    ),
                    weight=self.filter_weights[filter_type],
                )]

            if relative_change <= -warn_threshold:
                return [FilterCheck(
                    filter_type=filter_type,
                    result=FilterResult.WARNING,
                    value=relative_change,
                    threshold=-warn_threshold,
                    message=(
                        f'{symbol_name} lagging TRAD by {abs(relative_change):.2f} pts '
                        f'on bullish setup ({symbol_change_pct:+.2f}% vs TRAD {spy_change_pct:+.2f}%)'
                    ),
                    weight=self.filter_weights[filter_type],
                )]

            return [FilterCheck(
                filter_type=filter_type,
                result=FilterResult.PASS,
                value=relative_change,
                threshold=-warn_threshold,
                message=(
                    f'{symbol_name} confirming bullish tape '
                    f'({symbol_change_pct:+.2f}% vs TRAD {spy_change_pct:+.2f}%)'
                ),
                weight=self.filter_weights[filter_type],
            )]

        if relative_change >= fail_threshold:
            return [FilterCheck(
                filter_type=filter_type,
                result=FilterResult.FAIL,
                value=relative_change,
                threshold=fail_threshold,
                message=(
                    f'{symbol_name} outperforming TRAD by {relative_change:.2f} pts '
                    f'against bearish setup ({symbol_change_pct:+.2f}% vs TRAD {spy_change_pct:+.2f}%)'
                ),
                weight=self.filter_weights[filter_type],
            )]

        if relative_change >= warn_threshold:
            return [FilterCheck(
                filter_type=filter_type,
                result=FilterResult.WARNING,
                value=relative_change,
                threshold=warn_threshold,
                message=(
                    f'{symbol_name} stronger than TRAD by {relative_change:.2f} pts '
                    f'against bearish setup ({symbol_change_pct:+.2f}% vs TRAD {spy_change_pct:+.2f}%)'
                ),
                weight=self.filter_weights[filter_type],
            )]

        return [FilterCheck(
            filter_type=filter_type,
            result=FilterResult.PASS,
            value=relative_change,
            threshold=warn_threshold,
            message=(
                f'{symbol_name} confirming bearish tape '
                f'({symbol_change_pct:+.2f}% vs TRAD {spy_change_pct:+.2f}%)'
            ),
            weight=self.filter_weights[filter_type],
        )]

    def _check_qqq_confirmation_filter(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Require QQQ relative-strength confirmation for directional TRAD entries."""
        return self._check_relative_confirmation_filter(
            params,
            symbol_name='QQQ',
            filter_type=FilterType.QQQ_CONFIRMATION,
            symbol_change_key='qqq_change_pct',
            warn_threshold=self.macro_regime_policy['qqq_rel_warn_pct'],
            fail_threshold=self.macro_regime_policy['qqq_rel_fail_pct'],
        )

    def _check_iwm_confirmation_filter(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Require IWM breadth confirmation for directional TRAD entries."""
        return self._check_relative_confirmation_filter(
            params,
            symbol_name='IWM',
            filter_type=FilterType.IWM_CONFIRMATION,
            symbol_change_key='iwm_change_pct',
            warn_threshold=self.macro_regime_policy['iwm_rel_warn_pct'],
            fail_threshold=self.macro_regime_policy['iwm_rel_fail_pct'],
        )

    def _check_xlk_confirmation_filter(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Require XLK sector leadership confirmation for directional TRAD entries."""
        return self._check_relative_confirmation_filter(
            params,
            symbol_name='XLK',
            filter_type=FilterType.XLK_CONFIRMATION,
            symbol_change_key='xlk_change_pct',
            warn_threshold=self.macro_regime_policy['xlk_rel_warn_pct'],
            fail_threshold=self.macro_regime_policy['xlk_rel_fail_pct'],
        )

    def _check_xlf_confirmation_filter(self, params: dict[str, Any]) -> list[FilterCheck]:
        """Require XLF financial-sector confirmation for directional TRAD entries."""
        return self._check_relative_confirmation_filter(
            params,
            symbol_name='XLF',
            filter_type=FilterType.XLF_CONFIRMATION,
            symbol_change_key='xlf_change_pct',
            warn_threshold=self.macro_regime_policy['xlf_rel_warn_pct'],
            fail_threshold=self.macro_regime_policy['xlf_rel_fail_pct'],
        )

    def _check_vix_term_structure_filter(self) -> list[FilterCheck]:
        """Block entries when VIX term structure is in steep backwardation.

        Steep backwardation means near-term fear > long-term fear — a stress
        signal.  Entries are blocked when the structure is STEEP_BACKWARDATION
        and warned on plain BACKWARDATION.  Returns an empty list (no filter
        applied) when C10 VIXAnalyzer is not injected or has no data yet.
        """
        if self._vix_analyzer is None:
            return []
        try:
            ts = self._vix_analyzer.get_term_structure()
            if ts is None:
                return []
            state = ts.state.value if hasattr(ts.state, "value") else str(ts.state)
            if state == "steep_backwardation":
                return [FilterCheck(
                    filter_type=FilterType.VIX_TERM_STRUCTURE,
                    result=FilterResult.FAIL,
                    value=ts.vix_vxv_ratio,
                    threshold=1.0,
                    message=f"VIX term structure steep backwardation (VIX/VXV={ts.vix_vxv_ratio:.3f}); stress regime",  # noqa: E501
                    weight=self.filter_weights[FilterType.VIX_TERM_STRUCTURE],
                )]
            if state == "backwardation":
                return [FilterCheck(
                    filter_type=FilterType.VIX_TERM_STRUCTURE,
                    result=FilterResult.WARNING,
                    value=ts.vix_vxv_ratio,
                    threshold=1.0,
                    message=f"VIX term structure backwardation (VIX/VXV={ts.vix_vxv_ratio:.3f}); elevated caution",  # noqa: E501
                    weight=self.filter_weights[FilterType.VIX_TERM_STRUCTURE],
                )]
            return [FilterCheck(
                filter_type=FilterType.VIX_TERM_STRUCTURE,
                result=FilterResult.PASS,
                value=ts.vix_vxv_ratio,
                threshold=1.0,
                message=f"VIX term structure {state} (VIX/VXV={ts.vix_vxv_ratio:.3f})",
                weight=self.filter_weights[FilterType.VIX_TERM_STRUCTURE],
            )]
        except Exception as exc:
            self.logger.debug("VIX term structure filter skipped: %s", exc)
            return []

    def _check_cboe_skew_filter(self) -> list[FilterCheck]:
        """Block entries when the CBOE SKEW index signals extreme tail risk.

        SKEW > 145 → extreme tail-risk premium; block entries.
        SKEW 135–145 → elevated; warn.
        Returns an empty list when S06 SKEWCalculator is not injected or has
        no data yet.
        """
        if self._skew_calculator is None:
            return []
        try:
            skew = self._skew_calculator.get_current_skew()
            if skew is None:
                return []
            skew = float(skew)
            if skew > 145:
                return [FilterCheck(
                    filter_type=FilterType.CBOE_SKEW,
                    result=FilterResult.FAIL,
                    value=skew,
                    threshold=145.0,
                    message=f"CBOE SKEW={skew:.1f} > 145; extreme tail-risk premium; block entry",
                    weight=self.filter_weights[FilterType.CBOE_SKEW],
                )]
            if skew > 135:
                return [FilterCheck(
                    filter_type=FilterType.CBOE_SKEW,
                    result=FilterResult.WARNING,
                    value=skew,
                    threshold=135.0,
                    message=f"CBOE SKEW={skew:.1f} elevated (>135); increased tail risk",
                    weight=self.filter_weights[FilterType.CBOE_SKEW],
                )]
            return [FilterCheck(
                filter_type=FilterType.CBOE_SKEW,
                result=FilterResult.PASS,
                value=skew,
                threshold=145.0,
                message=f"CBOE SKEW={skew:.1f} within normal range",
                weight=self.filter_weights[FilterType.CBOE_SKEW],
            )]
        except Exception as exc:
            self.logger.debug("CBOE SKEW filter skipped: %s", exc)
            return []

    def _check_market_internals_filter(self) -> list[FilterCheck]:
        """Block entries when market internals show extreme deterioration.

        Uses C04 MarketInternals breadth/TICK/TRIN data:
        - BreadthCondition EXTREMELY_WEAK → block
        - BreadthCondition WEAK → warn
        Returns an empty list when C04 is not injected or has no data yet.
        """
        if self._market_internals is None:
            return []
        try:
            condition = self._market_internals.get_breadth_condition()
            cond_value = condition.value if hasattr(condition, "value") else str(condition)
            tick = self._market_internals.get_internal_value("TICK")
            tick_str = f", TICK={tick:.0f}" if tick is not None else ""
            if cond_value == "extremely_weak":
                return [FilterCheck(
                    filter_type=FilterType.MARKET_INTERNALS,
                    result=FilterResult.FAIL,
                    value=-1.0,
                    threshold=-0.8,
                    message=f"Market internals extremely weak{tick_str}; breadth deteriorating",
                    weight=self.filter_weights[FilterType.MARKET_INTERNALS],
                )]
            if cond_value == "weak":
                return [FilterCheck(
                    filter_type=FilterType.MARKET_INTERNALS,
                    result=FilterResult.WARNING,
                    value=-0.5,
                    threshold=-0.8,
                    message=f"Market internals weak{tick_str}; proceed with caution",
                    weight=self.filter_weights[FilterType.MARKET_INTERNALS],
                )]
            return [FilterCheck(
                filter_type=FilterType.MARKET_INTERNALS,
                result=FilterResult.PASS,
                value=0.0,
                threshold=-0.8,
                message=f"Market internals {cond_value}{tick_str}",
                weight=self.filter_weights[FilterType.MARKET_INTERNALS],
            )]
        except Exception as exc:
            self.logger.debug("Market internals filter skipped: %s", exc)
            return []

    # ==========================================================================
    # RESULT CALCULATION
    # ==========================================================================

    def _calculate_overall_result(self,
                                checks: list[FilterCheck]) -> tuple[FilterResult, EntryQuality, float]:  # noqa: E501
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
        hard_fail_filters = {
            FilterType.LIQUIDITY_QUALITY,
            FilterType.DATA_QUALITY,
            FilterType.VOL_SURFACE,
            FilterType.DEALER_FLOW,
            FilterType.PIVOT_OVERLAY,
        }
        hard_fail_present = any(
            check.result == FilterResult.FAIL and check.filter_type in hard_fail_filters
            for check in checks
        )

        if hard_fail_present:
            overall = FilterResult.FAIL
        elif failed > 0:
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

        risk_checks = [c for c in checks if c.filter_type in [FilterType.PORTFOLIO_EXPOSURE, FilterType.MAX_LOSS]]  # noqa: E501
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
        'current_time': datetime.now(UTC),
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
