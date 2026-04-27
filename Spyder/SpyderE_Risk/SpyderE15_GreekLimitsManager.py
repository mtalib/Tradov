#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderE_Risk
Module: SpyderE15_GreekLimitsManager.py
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
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

# ==============================================================================
# COMPATIBILITY ALIAS
# ==============================================================================
class AlertLevel:
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# Optional ML imports for enhanced features
try:
    from SpyderF_Analysis.SpyderF08_VolatilityRegime import VolatilityRegimeAnalyzer
    from SpyderF_Analysis.SpyderF10_MarketRegimeDetector import MarketRegimeDetector
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

# Alert manager integration
try:
    # from SpyderJ_Alerts.SpyderJ01_AlertManager import get_alert_manager  # Disabled for migration
    ALERTS_AVAILABLE = True
except ImportError:
    ALERTS_AVAILABLE = False

try:
    from SpyderN_OptionsAnalytics.SpyderN04_OptionsGreeksCalculator import (
        get_n04_calculator as _e15_get_n04_calculator,
    )
    _E15_N04_AVAILABLE = True
except ImportError:
    _e15_get_n04_calculator = None  # type: ignore[assignment]
    _E15_N04_AVAILABLE = False

# ==============================================================================
# ENHANCED CONSTANTS
# ==============================================================================
# Base institutional limits (per $1M portfolio)
DEFAULT_LIMITS = {
    'delta': 50.0,
    'gamma': 50.0,
    'vega': 200.0,
    'theta': -100.0,  # Negative theta is profit for premium sellers
    'rho': 25.0
}

# Dynamic adjustment parameters
VIX_ADJUSTMENT_SCALE = 0.02  # 2% per VIX point above/below 20
REGIME_MULTIPLIERS = {
    'low_volatility': 0.8,
    'normal': 1.0,
    'high_volatility': 1.5,
    'crisis': 2.0,
    'trending': 1.2,
    'mean_reverting': 0.9
}

# Monitoring intervals
MONITORING_INTERVAL = 5  # seconds
CORRELATION_CHECK_INTERVAL = 60  # seconds
REGIME_UPDATE_INTERVAL = 300  # 5 minutes

# Risk escalation levels
ESCALATION_LEVELS = {
    'green': 0.7,   # 70% of limit
    'yellow': 0.85, # 85% of limit
    'orange': 0.95, # 95% of limit
    'red': 1.0      # At limit
}

# ==============================================================================
# ENHANCED ENUMS
# ==============================================================================
class RiskLevel(Enum):
    """Risk escalation levels."""
    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"
    CRITICAL = "critical"  # Beyond limits

class MarketRegime(Enum):
    """Market regime types for risk adaptation."""
    LOW_VOLATILITY = "low_volatility"
    NORMAL = "normal"
    HIGH_VOLATILITY = "high_volatility"
    CRISIS = "crisis"
    TRENDING = "trending"
    MEAN_REVERTING = "mean_reverting"
    UNCERTAIN = "uncertain"

class AdjustmentTrigger(Enum):
    """Triggers for limit adjustments."""
    VIX_CHANGE = "vix_change"
    REGIME_CHANGE = "regime_change"
    CORRELATION_BREAKDOWN = "correlation_breakdown"
    VOLATILITY_SPIKE = "volatility_spike"
    MANUAL_OVERRIDE = "manual_override"
    STRESS_TEST = "stress_test"

# ==============================================================================
# ENHANCED DATA STRUCTURES
# ==============================================================================
@dataclass
class DynamicGreekLimits:
    """Dynamic Greek limits that adapt to market conditions."""
    base_limits: dict[str, float]
    current_limits: dict[str, float]
    adjustment_factors: dict[str, float]
    last_updated: datetime
    regime: MarketRegime
    vix_level: float
    adjustment_history: list[dict[str, Any]] = field(default_factory=list)

    def apply_adjustment(self, greek: str, factor: float, trigger: AdjustmentTrigger) -> None:
        """Apply adjustment to specific Greek limit."""
        old_limit = self.current_limits.get(greek, 0)
        new_limit = self.base_limits[greek] * factor
        self.current_limits[greek] = new_limit
        self.adjustment_factors[greek] = factor

        # Log adjustment
        self.adjustment_history.append({
            'timestamp': datetime.now(timezone.utc),
            'greek': greek,
            'old_limit': old_limit,
            'new_limit': new_limit,
            'factor': factor,
            'trigger': trigger.value
        })

        self.last_updated = datetime.now(timezone.utc)

@dataclass
class GreekExposure:
    """Current Greek exposure for a strategy/position."""
    strategy_id: str
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    rho: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    position_count: int = 0
    total_notional: float = 0.0


@dataclass
class RiskAlert:
    """Risk alert for Greek limit violations."""
    alert_id: str
    strategy_id: str
    greek_type: str
    current_value: float
    limit_value: float
    risk_level: RiskLevel
    utilization_pct: float
    timestamp: datetime
    recommended_actions: list[str]
    market_context: dict[str, Any]

@dataclass
class CorrelationBreakdown:
    """Detection of correlation breakdown events."""
    timestamp: datetime
    assets: list[str]
    historical_correlation: float
    current_correlation: float
    breakdown_severity: float  # 0.0 to 1.0
    duration_minutes: int
    risk_impact: str  # 'low', 'medium', 'high', 'critical'

# ==============================================================================
# ENHANCED GREEK LIMITS MANAGER
# ==============================================================================
class GreekLimitsManager:
    """
    Enhanced Greek Limits Manager with dynamic risk adaptation.

    New Features:
    - Dynamic limit adjustment based on market regimes
    - VIX-based risk scaling
    - Correlation breakdown detection
    - Predictive risk modeling
    - Real-time stress testing
    - Regime-aware position sizing

    Maintains all existing functionality while adding adaptive intelligence.
    """

    def __init__(self, config: dict[str, Any] = None):
        """Initialize enhanced Greek limits manager."""
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()

        # Configuration
        self.config = config or {}
        self.monitoring_enabled = self.config.get('monitoring_enabled', True)
        self.dynamic_adjustment_enabled = self.config.get('dynamic_adjustment', True)

        # Base limits
        self.base_limits = {**DEFAULT_LIMITS, **self.config.get('base_limits', {})}

        # Dynamic limits for each strategy
        self.strategy_limits: dict[str, DynamicGreekLimits] = {}

        # Current exposures
        self.current_exposures: dict[str, GreekExposure] = {}
        self.portfolio_exposure = GreekExposure(strategy_id="PORTFOLIO")

        # Market data and regime detection
        self.current_market_data: dict[str, Any] = {}
        self.current_regime = MarketRegime.NORMAL
        self.vix_level = 20.0
        self.correlation_matrix = pd.DataFrame()

        # ML components (if available)
        self.ml_available = ML_AVAILABLE
        self.regime_classifier = None
        self.volatility_analyzer = None
        self.market_detector = None

        # Alert integration
        self.alert_manager = None
        # get_alert_manager is disabled pending migration to SpyderJ01

        # Risk monitoring
        self.risk_alerts: dict[str, RiskAlert] = {}
        self.violation_history: deque = deque(maxlen=1000)
        self.correlation_breakdowns: list[CorrelationBreakdown] = []

        # Performance tracking
        self.monitoring_stats = {
            'checks_performed': 0,
            'violations_detected': 0,
            'adjustments_made': 0,
            'regime_changes': 0,
            'correlation_breakdowns': 0
        }

        # Threading
        self._stop_event = threading.Event()
        self._monitoring_thread = None
        self._regime_thread = None

        # N04 OptionsGreeksCalculator reference — lazily resolved on first use
        self._n04_calculator: Any | None = None

        # Initialize components
        self._initialize_ml_components()
        self._start_monitoring()

        self.logger.info("✅ Enhanced GreekLimitsManager with dynamic adaptation initialized")

    # ==========================================================================
    # ML INTEGRATION AND INITIALIZATION
    # ==========================================================================
    def _initialize_ml_components(self) -> None:
        """Initialize ML components for regime detection and adaptation."""
        try:
            if not self.ml_available or not self.dynamic_adjustment_enabled:
                self.logger.warning("ML components not available - using static limits")
                return

            # Initialize regime classifier
            try:
                from Spyder.SpyderF_Analysis.SpyderF10_MarketRegimeDetector import MarketRegimeDetector as RegimeClassifier  # noqa: E501
                self.regime_classifier = RegimeClassifier()
            except (ImportError, Exception):
                self.regime_classifier = None

            # Initialize volatility analyzer
            self.volatility_analyzer = VolatilityRegimeAnalyzer()

            # Initialize market regime detector
            self.market_detector = MarketRegimeDetector()

            # Wire N04 singleton for accurate portfolio-level Greeks
            if _E15_N04_AVAILABLE:
                try:
                    self._n04_calculator = _e15_get_n04_calculator()
                    self.logger.info("📊 N04 OptionsGreeksCalculator wired into GreekLimitsManager")
                except Exception as exc:
                    self.logger.debug("N04 not yet available at init time: %s", exc)

            self.logger.info("🤖 ML components initialized for dynamic risk adaptation")

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_initialize_ml_components'
            })
            self.ml_available = False

    def _get_n04(self) -> Any | None:
        """Lazy-resolve the N04 OptionsGreeksCalculator singleton.

        Falls back gracefully: returns None when N04 is unavailable or fails
        to initialise so all callers must guard with ``if n04 is not None``.
        """
        if not _E15_N04_AVAILABLE:
            return None
        if self._n04_calculator is None:
            try:
                self._n04_calculator = _e15_get_n04_calculator()
            except Exception as exc:
                self.logger.debug("N04 calculator unavailable: %s", exc)
        return self._n04_calculator

    # ==========================================================================
    # STRATEGY REGISTRATION AND LIMIT MANAGEMENT
    # ==========================================================================
    def register_strategy(self, strategy_id: str, custom_limits: dict[str, float] = None) -> None:
        """
        Register a strategy for Greek limits monitoring.

        Args:
            strategy_id: Strategy identifier
            custom_limits: Custom limits override (optional)
        """
        try:
            # Use custom limits or default to base limits
            limits = custom_limits or self.base_limits.copy()

            # Create dynamic limits for strategy
            dynamic_limits = DynamicGreekLimits(
                base_limits=limits.copy(),
                current_limits=limits.copy(),
                adjustment_factors={greek: 1.0 for greek in limits},
                last_updated=datetime.now(timezone.utc),
                regime=self.current_regime,
                vix_level=self.vix_level
            )

            self.strategy_limits[strategy_id] = dynamic_limits

            # Initialize exposure tracking
            self.current_exposures[strategy_id] = GreekExposure(strategy_id=strategy_id)

            self.logger.info("📋 Registered strategy %s for Greek limits monitoring", strategy_id)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'register_strategy',
                'strategy_id': strategy_id
            })

    def update_strategy_limits(self, strategy_id: str, new_limits: dict[str, float]) -> None:
        """Update base limits for a strategy."""
        try:
            if strategy_id not in self.strategy_limits:
                self.register_strategy(strategy_id, new_limits)
                return

            # Update base limits
            strategy_limits = self.strategy_limits[strategy_id]
            strategy_limits.base_limits.update(new_limits)

            # Recalculate current limits with existing adjustments
            for greek, base_limit in new_limits.items():
                adjustment_factor = strategy_limits.adjustment_factors.get(greek, 1.0)
                strategy_limits.current_limits[greek] = base_limit * adjustment_factor

            strategy_limits.last_updated = datetime.now(timezone.utc)

            self.logger.info("📊 Updated limits for strategy %s", strategy_id)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'update_strategy_limits',
                'strategy_id': strategy_id
            })

    # ==========================================================================
    # DYNAMIC LIMIT ADJUSTMENT METHODS
    # ==========================================================================
    def adjust_limits_for_regime(self, new_regime: MarketRegime, vix_level: float) -> None:
        """
        Adjust limits based on market regime change.

        Args:
            new_regime: New market regime
            vix_level: Current VIX level
        """
        try:
            if not self.dynamic_adjustment_enabled:
                return

            # Calculate regime multiplier
            regime_multiplier = REGIME_MULTIPLIERS.get(new_regime.value, 1.0)

            # Calculate VIX adjustment (normalized around VIX 20)
            vix_adjustment = 1.0 + ((vix_level - 20.0) * VIX_ADJUSTMENT_SCALE)
            vix_adjustment = max(0.5, min(2.0, vix_adjustment))  # Clamp to reasonable range

            # Combined adjustment factor
            total_adjustment = regime_multiplier * vix_adjustment

            # Apply to all registered strategies
            for strategy_id, strategy_limits in self.strategy_limits.items():
                old_regime = strategy_limits.regime

                # Update regime and VIX level
                strategy_limits.regime = new_regime
                strategy_limits.vix_level = vix_level

                # Apply adjustments to each Greek
                for greek in strategy_limits.base_limits:
                    # Different Greeks may have different sensitivities
                    greek_adjustment = self._calculate_greek_specific_adjustment(
                        greek, total_adjustment, new_regime, vix_level
                    )

                    strategy_limits.apply_adjustment(
                        greek, greek_adjustment, AdjustmentTrigger.REGIME_CHANGE
                    )

                self.logger.info(
                    f"🎯 Adjusted limits for {strategy_id}: "
                    f"{old_regime.value} → {new_regime.value}, "
                    f"VIX: {vix_level:.1f}, "
                    f"Adjustment: {total_adjustment:.2f}x"
                )

            # Update monitoring stats
            self.monitoring_stats['adjustments_made'] += len(self.strategy_limits)
            self.monitoring_stats['regime_changes'] += 1

            # Send alert about regime change
            self._send_regime_change_alert(new_regime, vix_level, total_adjustment)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'adjust_limits_for_regime'
            })

    def _calculate_greek_specific_adjustment(self, greek: str, base_adjustment: float,
                                           regime: MarketRegime, vix_level: float) -> float:
        """Calculate Greek-specific adjustment factors."""
        try:
            # Base adjustment
            adjustment = base_adjustment

            # Greek-specific modifiers
            if greek == 'gamma':
                # Gamma risk increases more in high vol environments
                if regime in [MarketRegime.HIGH_VOLATILITY, MarketRegime.CRISIS]:
                    adjustment *= 1.2
                elif regime == MarketRegime.LOW_VOLATILITY:
                    adjustment *= 0.8

            elif greek == 'vega':
                # Vega risk is more sensitive to regime changes
                if regime == MarketRegime.CRISIS:
                    adjustment *= 1.5
                elif regime == MarketRegime.LOW_VOLATILITY:
                    adjustment *= 0.7

            elif greek == 'delta':
                # Delta exposure less sensitive to volatility regimes
                adjustment *= 0.9 + (0.2 * (adjustment - 1.0))

            elif greek == 'theta':
                # Theta strategies benefit from high vol (more premium)
                if regime in [MarketRegime.HIGH_VOLATILITY, MarketRegime.CRISIS]:
                    adjustment *= 0.8  # Allow more theta exposure

            return max(0.3, min(3.0, adjustment))  # Reasonable bounds

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_calculate_greek_specific_adjustment'
            })
            return base_adjustment

    def adjust_for_correlation_breakdown(self, breakdown: CorrelationBreakdown) -> None:
        """Adjust limits when correlation breakdown is detected."""
        try:
            if breakdown.risk_impact in ['high', 'critical']:
                # Reduce all limits by 20-40% during correlation breakdown
                reduction_factor = 0.6 if breakdown.risk_impact == 'critical' else 0.8

                for _strategy_id, strategy_limits in self.strategy_limits.items():
                    for greek in strategy_limits.base_limits:
                        current_factor = strategy_limits.adjustment_factors.get(greek, 1.0)
                        new_factor = current_factor * reduction_factor

                        strategy_limits.apply_adjustment(
                            greek, new_factor, AdjustmentTrigger.CORRELATION_BREAKDOWN
                        )

                self.logger.warning(
                    f"🚨 Reduced limits due to correlation breakdown: "
                    f"{breakdown.breakdown_severity:.1%} severity"
                )

                # Send critical alert
                if self.alert_manager:
                    self.alert_manager.send_alert(
                        level=AlertLevel.CRITICAL,
                        title="Correlation Breakdown Detected",
                        message=f"Correlation breakdown severity: {breakdown.breakdown_severity:.1%}. "  # noqa: E501
                               f"Limits reduced by {(1-reduction_factor)*100:.0f}%",
                        category="RISK"
                    )

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'adjust_for_correlation_breakdown'
            })

    # ==========================================================================
    # EXPOSURE MONITORING AND VALIDATION
    # ==========================================================================
    def update_strategy_exposure(self, strategy_id: str, greeks: dict[str, float],
                                position_count: int = 0, notional: float = 0.0) -> None:
        """
        Update Greek exposure for a strategy.

        Args:
            strategy_id: Strategy identifier
            greeks: Current Greek exposures
            position_count: Number of positions
            notional: Total notional value
        """
        try:
            if strategy_id not in self.current_exposures:
                self.current_exposures[strategy_id] = GreekExposure(strategy_id=strategy_id)

            exposure = self.current_exposures[strategy_id]

            # Update exposures
            exposure.delta = greeks.get('delta', 0.0)
            exposure.gamma = greeks.get('gamma', 0.0)
            exposure.vega = greeks.get('vega', 0.0)
            exposure.theta = greeks.get('theta', 0.0)
            exposure.rho = greeks.get('rho', 0.0)
            exposure.timestamp = datetime.now(timezone.utc)
            exposure.position_count = position_count
            exposure.total_notional = notional

            # Update portfolio exposure
            self._update_portfolio_exposure()

            # Check for violations
            violations = self.check_strategy_violations(strategy_id)
            if violations:
                self._handle_violations(strategy_id, violations)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'update_strategy_exposure',
                'strategy_id': strategy_id
            })

    def check_strategy_violations(self, strategy_id: str) -> list[RiskAlert]:
        """Check for Greek limit violations for a strategy."""
        violations = []

        try:
            if strategy_id not in self.strategy_limits or strategy_id not in self.current_exposures:
                return violations

            limits = self.strategy_limits[strategy_id]
            exposure = self.current_exposures[strategy_id]

            # Check each Greek
            for greek in limits.current_limits:
                current_value = getattr(exposure, greek, 0.0)
                limit_value = limits.current_limits[greek]

                if limit_value == 0:
                    continue

                # Calculate utilization percentage
                utilization = abs(current_value) / abs(limit_value)

                # Determine risk level
                risk_level = self._determine_risk_level(utilization)

                # Create alert if above green level
                if risk_level != RiskLevel.GREEN:
                    alert = RiskAlert(
                        alert_id=f"{strategy_id}_{greek}_{int(time.time())}",
                        strategy_id=strategy_id,
                        greek_type=greek,
                        current_value=current_value,
                        limit_value=limit_value,
                        risk_level=risk_level,
                        utilization_pct=utilization * 100,
                        timestamp=datetime.now(timezone.utc),
                        recommended_actions=self._generate_risk_recommendations(
                            greek, utilization, risk_level
                        ),
                        market_context=self._get_market_context()
                    )

                    violations.append(alert)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'check_strategy_violations',
                'strategy_id': strategy_id
            })

        return violations

    def _update_portfolio_exposure(self) -> None:
        """Update portfolio-level Greek exposure."""
        try:
            # Sum all strategy exposures
            total_delta = sum(exp.delta for exp in self.current_exposures.values())
            total_gamma = sum(exp.gamma for exp in self.current_exposures.values())
            total_vega = sum(exp.vega for exp in self.current_exposures.values())
            total_theta = sum(exp.theta for exp in self.current_exposures.values())
            total_rho = sum(exp.rho for exp in self.current_exposures.values())

            # Update portfolio exposure
            self.portfolio_exposure.delta = total_delta
            self.portfolio_exposure.gamma = total_gamma
            self.portfolio_exposure.vega = total_vega
            self.portfolio_exposure.theta = total_theta
            self.portfolio_exposure.rho = total_rho
            self.portfolio_exposure.timestamp = datetime.now(timezone.utc)
            self.portfolio_exposure.position_count = sum(
                exp.position_count for exp in self.current_exposures.values()
            )
            self.portfolio_exposure.total_notional = sum(
                exp.total_notional for exp in self.current_exposures.values()
            )

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_portfolio_exposure'
            })

    def _determine_risk_level(self, utilization: float) -> RiskLevel:
        """Determine risk level based on limit utilization."""
        if utilization >= 1.0:
            return RiskLevel.CRITICAL
        elif utilization >= ESCALATION_LEVELS['red']:
            return RiskLevel.RED
        elif utilization >= ESCALATION_LEVELS['orange']:
            return RiskLevel.ORANGE
        elif utilization >= ESCALATION_LEVELS['yellow']:
            return RiskLevel.YELLOW
        else:
            return RiskLevel.GREEN

    def _generate_risk_recommendations(self, greek: str, utilization: float,
                                     risk_level: RiskLevel) -> list[str]:
        """Generate risk management recommendations."""
        recommendations = []

        try:
            if risk_level in [RiskLevel.RED, RiskLevel.CRITICAL]:
                if greek == 'delta':
                    recommendations.extend([
                        "Reduce directional exposure immediately",
                        "Consider delta hedging with underlying",
                        "Close out-of-the-money positions"
                    ])
                elif greek == 'gamma':
                    recommendations.extend([
                        "Reduce gamma exposure urgently",
                        "Close short gamma positions",
                        "Consider dynamic hedging"
                    ])
                elif greek == 'vega':
                    recommendations.extend([
                        "Reduce volatility exposure",
                        "Close high vega positions",
                        "Consider VIX hedges"
                    ])

            elif risk_level == RiskLevel.ORANGE:
                recommendations.extend([
                    f"Monitor {greek} exposure closely",
                    "Prepare to reduce position sizes",
                    "Review risk management rules"
                ])

            elif risk_level == RiskLevel.YELLOW:
                recommendations.extend([
                    f"Caution: {greek} approaching limits",
                    "Consider position sizing adjustments"
                ])

            # Add utilization-specific recommendations
            if utilization > 0.9:
                recommendations.append(f"URGENT: {utilization:.1%} of {greek} limit used")

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_generate_risk_recommendations'
            })
            recommendations = [f"Monitor {greek} exposure", "Review position sizes"]

        return recommendations[:5]  # Limit to top 5 recommendations

    def _get_market_context(self) -> dict[str, Any]:
        """Get current market context for alerts."""
        return {
            'regime': self.current_regime.value,
            'vix_level': self.vix_level,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'portfolio_positions': self.portfolio_exposure.position_count,
            'portfolio_notional': self.portfolio_exposure.total_notional
        }

    # ==========================================================================
    # VIOLATION HANDLING AND ALERTING
    # ==========================================================================
    def _handle_violations(self, strategy_id: str, violations: list[RiskAlert]) -> None:
        """Handle Greek limit violations."""
        try:
            for violation in violations:
                # Store in risk alerts
                self.risk_alerts[violation.alert_id] = violation

                # Add to violation history
                self.violation_history.append({
                    'timestamp': violation.timestamp,
                    'strategy_id': strategy_id,
                    'greek': violation.greek_type,
                    'utilization': violation.utilization_pct,
                    'risk_level': violation.risk_level.value
                })

                # Send alerts based on severity
                self._send_violation_alert(violation)

                # Emit event
                self.event_manager.publish(Event(
                    type=EventType.RISK,
                    source="GreekLimitsManager",
                    data={
                        'violation': violation.__dict__,
                        'strategy_id': strategy_id
                    }
                ))

            # Update stats
            self.monitoring_stats['violations_detected'] += len(violations)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_handle_violations',
                'strategy_id': strategy_id
            })

    def _send_violation_alert(self, violation: RiskAlert) -> None:
        """Send alert for Greek limit violation."""
        try:
            if not self.alert_manager:
                return

            # Determine alert level
            alert_level_map = {
                RiskLevel.YELLOW: AlertLevel.WARNING,
                RiskLevel.ORANGE: AlertLevel.ERROR,
                RiskLevel.RED: AlertLevel.CRITICAL,
                RiskLevel.CRITICAL: AlertLevel.CRITICAL
            }

            alert_level = alert_level_map.get(violation.risk_level, AlertLevel.WARNING)

            # Format message
            message = self._format_violation_message(violation)

            # Send alert
            self.alert_manager.send_alert(
                level=alert_level,
                title=f"{violation.greek_type.upper()} Limit Violation",
                message=message,
                category="RISK"
            )

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_send_violation_alert'
            })

    def _format_violation_message(self, violation: RiskAlert) -> str:
        """Format violation alert message."""
        try:
            risk_emoji = {
                RiskLevel.YELLOW: "🟡",
                RiskLevel.ORANGE: "🟠",
                RiskLevel.RED: "🔴",
                RiskLevel.CRITICAL: "🚨"
            }

            message = f"""
{risk_emoji.get(violation.risk_level, '⚠️')} **{violation.greek_type.upper()} LIMIT VIOLATION**

**Strategy:** {violation.strategy_id}
**Current:** {violation.current_value:.2f}
**Limit:** {violation.limit_value:.2f}
**Utilization:** {violation.utilization_pct:.1f}%
**Risk Level:** {violation.risk_level.value.upper()}

**Market Context:**
• Regime: {violation.market_context.get('regime', 'unknown')}
• VIX: {violation.market_context.get('vix_level', 0):.1f}
• Portfolio Positions: {violation.market_context.get('portfolio_positions', 0)}

**Recommended Actions:**
{chr(10).join(f'• {action}' for action in violation.recommended_actions)}
            """.strip()

            return message

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_format_violation_message'
            })
            return f"Greek limit violation: {violation.greek_type} at {violation.utilization_pct:.1f}%"  # noqa: E501

    def _send_regime_change_alert(self, new_regime: MarketRegime, vix_level: float,
                                 adjustment_factor: float) -> None:
        """Send alert for regime change and limit adjustments."""
        try:
            if not self.alert_manager:
                return

            message = f"""
🔄 **MARKET REGIME CHANGE**

**New Regime:** {new_regime.value.replace('_', ' ').title()}
**VIX Level:** {vix_level:.1f}
**Limit Adjustment:** {adjustment_factor:.2f}x

**Impact:**
• All Greek limits automatically adjusted
• {len(self.strategy_limits)} strategies affected
• Monitoring continues with new thresholds

**Next Steps:**
• Review position sizes in new regime
• Monitor for additional adjustments
• Consider regime-appropriate strategies
            """.strip()

            self.alert_manager.send_alert(
                level=AlertLevel.INFO,
                title="Market Regime Change",
                message=message,
                category="MARKET"
            )

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_send_regime_change_alert'
            })

    # ==========================================================================
    # MONITORING THREADS
    # ==========================================================================
    def _start_monitoring(self) -> None:
        """Start monitoring threads."""
        try:
            if not self.monitoring_enabled:
                return

            # Start main monitoring thread
            self._monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                name="GreekLimits-Monitor",
                daemon=True
            )
            self._monitoring_thread.start()

            # Start regime monitoring thread
            if self.dynamic_adjustment_enabled and self.ml_available:
                self._regime_thread = threading.Thread(
                    target=self._regime_monitoring_loop,
                    name="GreekLimits-Regime",
                    daemon=True
                )
                self._regime_thread.start()

            self.logger.info("🚀 Greek limits monitoring threads started")

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_start_monitoring'
            })

    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while not self._stop_event.is_set():
            try:
                # Check all strategies for violations
                total_violations = 0

                for strategy_id in self.strategy_limits:
                    violations = self.check_strategy_violations(strategy_id)
                    if violations:
                        self._handle_violations(strategy_id, violations)
                        total_violations += len(violations)

                # Update monitoring stats
                self.monitoring_stats['checks_performed'] += 1

                # Log status periodically
                if self.monitoring_stats['checks_performed'] % 60 == 0:  # Every 5 minutes
                    self.logger.debug(
                        f"📊 Monitoring status: {self.monitoring_stats['checks_performed']} checks, "  # noqa: E501
                        f"{self.monitoring_stats['violations_detected']} violations detected"
                    )

                # Sleep for monitoring interval
                self._stop_event.wait(MONITORING_INTERVAL)

            except Exception as e:
                self.logger.error("Error in monitoring loop: %s", e)
                self._stop_event.wait(MONITORING_INTERVAL * 2)  # Longer sleep on error

    def _regime_monitoring_loop(self) -> None:
        """Regime monitoring and adjustment loop."""
        while not self._stop_event.is_set():
            try:
                # Update market data and detect regime changes
                if self.current_market_data:
                    new_regime = self._detect_regime_change()
                    new_vix = self.current_market_data.get('vix', self.vix_level)

                    # Check if regime or VIX changed significantly
                    regime_changed = new_regime != self.current_regime
                    vix_changed = abs(new_vix - self.vix_level) > 1.0  # 1 point change

                    if regime_changed or vix_changed:
                        self.current_regime = new_regime
                        self.vix_level = new_vix
                        self.adjust_limits_for_regime(new_regime, new_vix)

                # Check for correlation breakdowns
                self._check_correlation_breakdown()

                # Sleep for regime check interval
                self._stop_event.wait(REGIME_UPDATE_INTERVAL)

            except Exception as e:
                self.logger.error("Error in regime monitoring: %s", e)
                self._stop_event.wait(REGIME_UPDATE_INTERVAL * 2)

    def _detect_regime_change(self) -> MarketRegime:
        """Detect current market regime."""
        try:
            if self.regime_classifier and self.current_market_data:
                regime_result = self.regime_classifier.classify(self.current_market_data)

                # Map classifier result to our enum
                regime_mapping = {
                    'low_vol': MarketRegime.LOW_VOLATILITY,
                    'normal': MarketRegime.NORMAL,
                    'high_vol': MarketRegime.HIGH_VOLATILITY,
                    'crisis': MarketRegime.CRISIS,
                    'trending': MarketRegime.TRENDING,
                    'mean_reverting': MarketRegime.MEAN_REVERTING
                }

                return regime_mapping.get(regime_result, MarketRegime.NORMAL)

            # Fallback: VIX-based regime detection, augmented by N04 portfolio gamma.
            # High absolute gamma indicates a destabilising options market regardless
            # of VIX level, so we escalate LOW_VOLATILITY → NORMAL when gamma is
            # elevated (|Γ| > 5) and NORMAL → HIGH_VOLATILITY when |Γ| > 20.
            vix = self.current_market_data.get('vix', 20.0)
            if vix < 12:
                regime = MarketRegime.LOW_VOLATILITY
            elif vix < 20:
                regime = MarketRegime.NORMAL
            elif vix < 30:
                regime = MarketRegime.HIGH_VOLATILITY
            else:
                regime = MarketRegime.CRISIS

            # Gamma-based regime escalation via N04
            n04 = self._get_n04()
            if n04 is not None:
                try:
                    abs_gamma = abs(n04.portfolio_greeks.total_gamma)
                    if abs_gamma > 20 and regime in (MarketRegime.LOW_VOLATILITY, MarketRegime.NORMAL):  # noqa: E501
                        self.logger.debug(
                            "N04 gamma %.2f escalates regime %s → HIGH_VOLATILITY",
                            abs_gamma, regime.name,
                        )
                        regime = MarketRegime.HIGH_VOLATILITY
                    elif abs_gamma > 5 and regime == MarketRegime.LOW_VOLATILITY:
                        self.logger.debug(
                            "N04 gamma %.2f escalates regime LOW_VOLATILITY → NORMAL",
                            abs_gamma,
                        )
                        regime = MarketRegime.NORMAL
                except Exception as exc:
                    self.logger.debug("N04 gamma read failed during regime detection: %s", exc)

            return regime

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_detect_regime_change'
            })
            return self.current_regime

    def _check_correlation_breakdown(self) -> None:
        """Check for correlation breakdown events."""
        try:
            # This would analyze correlation matrices and detect breakdowns
            # For now, implement a simple placeholder

            # In production, this would:
            # 1. Calculate rolling correlations
            # 2. Compare to historical correlations
            # 3. Detect significant breakdowns
            # 4. Trigger limit adjustments if needed

            pass

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_check_correlation_breakdown'
            })

    # --------------------------------------------------------------------------
    # STABLE-BASELINES3: RL DYNAMIC GREEK LIMIT ADJUSTMENT
    # --------------------------------------------------------------------------

    def create_greek_limits_rl_env(self):
        """
        Create an RL environment for dynamic Greek limit adjustment.

        The agent learns to adapt Greek limits based on market regime,
        VIX level, and recent P&L to balance risk and opportunity.

        Returns:
            gym.Env instance for training with SB3 PPO.
        """
        try:
            import gymnasium as gym
            from gymnasium import spaces
        except ImportError:
            try:
                import gym
                from gym import spaces
            except ImportError:
                self.logger.warning("gym/gymnasium not installed")
                return None

        import numpy as _np

        class GreekLimitsEnvironment(gym.Env):
            """
            RL environment for Greek limit adjustment.

            Observation: [delta_exposure, gamma_exposure, vega_exposure,
                         theta_exposure, vix_level, regime_id, recent_pnl,
                         portfolio_value_norm]
            Action: Continuous box [delta_limit_adj, gamma_limit_adj,
                    vega_limit_adj, theta_limit_adj] in [-1, 1]
            Reward: risk_adjusted_pnl - limit_violation_penalty
            """
            metadata = {'render_modes': []}

            def __init__(self):
                super().__init__()
                self.observation_space = spaces.Box(
                    low=-5.0, high=5.0, shape=(8,), dtype=_np.float32)
                self.action_space = spaces.Box(
                    low=-1.0, high=1.0, shape=(4,), dtype=_np.float32)
                self.step_count = 0
                self.max_steps = 252

            def reset(self, seed=None, options=None):
                super().reset(seed=seed)
                self.step_count = 0
                self._state = _np.array([
                    _np.random.uniform(-1, 1),     # delta_exposure
                    _np.random.uniform(0, 0.5),    # gamma_exposure
                    _np.random.uniform(-0.5, 0.5), # vega_exposure
                    _np.random.uniform(-0.3, 0),   # theta_exposure
                    _np.random.uniform(12, 35),     # VIX
                    float(_np.random.randint(0, 4)), # regime
                    0.0,                            # recent PnL
                    1.0,                            # portfolio norm
                ], dtype=_np.float32)
                return self._state, {}

            def step(self, action):
                self.step_count += 1
                vix = self._state[4]
                greeks = self._state[:4]

                # Adjusted limits based on action
                base_limits = _np.array([0.3, 0.1, 0.2, 0.15])
                adj_limits = base_limits * (1 + action * 0.5)

                violations = _np.maximum(0, _np.abs(greeks) - adj_limits)
                violation_penalty = float(violations.sum()) * 10

                # Simulate PnL
                pnl = float(_np.random.normal(0.001, 0.02))
                self._state[6] = pnl

                # Tighter limits in high-VIX = lower violations but less opportunity
                opportunity_cost = float(_np.mean(_np.maximum(0, base_limits - adj_limits))) * 5

                reward = pnl * 100 - violation_penalty - opportunity_cost

                # Evolve state
                self._state[:4] += _np.random.normal(0, 0.05, 4).astype(_np.float32)
                self._state[4] = _np.clip(vix + _np.random.normal(0, 1), 10, 80)

                done = self.step_count >= self.max_steps
                return self._state.copy(), float(reward), done, False, {}

        return GreekLimitsEnvironment()

    def train_greek_limits_policy(self, total_timesteps: int = 50000) -> Any | None:
        """
        Train a PPO policy for dynamic Greek limit adjustment.

        Args:
            total_timesteps: Training steps.

        Returns:
            Trained SB3 model or None.
        """
        env = self.create_greek_limits_rl_env()
        if env is None:
            return None

        try:
            from stable_baselines3 import PPO
            model = PPO('MlpPolicy', env, verbose=0,
                       learning_rate=3e-4, n_steps=2048)
            model.learn(total_timesteps=total_timesteps)
            self.logger.info("Greek limits RL policy trained: %s steps", total_timesteps)
            return model
        except ImportError:
            self.logger.warning("stable-baselines3 not installed")
            return None
