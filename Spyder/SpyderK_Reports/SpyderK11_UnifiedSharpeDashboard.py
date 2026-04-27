#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderK_Reports
Module: SpyderK11_UnifiedSharpeDashboard.py
Purpose: Unified Sharpe Ratio Monitoring and Reporting Dashboard

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-01-16

Module Description:
    Provides a unified dashboard for all Sharpe Ratio calculations including:
    - Standard Sharpe Ratio from multiple modules
    - Probabilistic Sharpe Ratio
    - Options-Adjusted Sharpe Ratio
    - Confidence intervals and statistical significance
    - Real-time Sharpe degradation alerts
    - Multi-timeframe Sharpe analysis
    - Comparative analysis across strategies

Change Log:
    2026-01-16:
        - Initial implementation
        - Integrated all Sharpe calculation modules
        - Added unified reporting interface
        - Added alerting system for Sharpe degradation
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from enum import Enum
import threading
import json
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderE_Risk.SpyderE06_RiskMetrics import (
        RiskMetricsCalculator,
        calculate_sharpe_ratio,
        DEFAULT_RISK_FREE_RATE
    )
    from SpyderE_Risk.SpyderE07_ProbabilisticSharpe import (
        ProbabilisticSharpeCalculator,
        ProbabilisticSharpeResult,
        OptionsAdjustedSharpe
    )
    from SpyderH_Storage.SpyderH07_PerformanceAnalytics import (
        PerformanceAnalytics,
        TimeFrame  # noqa: F401
    )
    LOCAL_IMPORTS = True
except ImportError:
    import logging
    SpyderLogger = type('SpyderLogger', (), {
        'get_logger': staticmethod(lambda name: logging.getLogger(name))
    })()
    DEFAULT_RISK_FREE_RATE = 0.045
    LOCAL_IMPORTS = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
SHARPE_DEGRADATION_THRESHOLD = 0.20  # Alert if Sharpe drops >20%
SHARPE_EXCELLENT_THRESHOLD = 2.0
SHARPE_GOOD_THRESHOLD = 1.0
SHARPE_POOR_THRESHOLD = 0.5

PSR_HIGH_CONFIDENCE = 0.95  # 95% probability
PSR_MODERATE_CONFIDENCE = 0.80  # 80% probability

# Update frequencies (seconds)
UPDATE_INTERVAL_REALTIME = 60  # 1 minute
UPDATE_INTERVAL_DAILY = 86400  # 24 hours

# ==============================================================================
# ENUMS
# ==============================================================================
class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class SharpeStatus(Enum):
    """Sharpe ratio status categories."""
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"
    INSUFFICIENT_DATA = "insufficient_data"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class UnifiedSharpeMetrics:
    """Unified Sharpe metrics from all sources."""
    timestamp: datetime
    strategy_id: str
    strategy_name: str

    # Standard Sharpe from different modules
    sharpe_u15: float  # From SpyderU15
    sharpe_e06: float  # From SpyderE06
    sharpe_h07: float  # From SpyderH07

    # Advanced metrics
    probabilistic_sharpe: ProbabilisticSharpeResult
    options_adjusted_sharpe: OptionsAdjustedSharpe

    # Consensus Sharpe (average of all)
    consensus_sharpe: float

    # Status
    status: SharpeStatus
    is_significant: bool

    # Historical context
    sharpe_30d_avg: float
    sharpe_90d_avg: float
    sharpe_1y_avg: float

    # Change metrics
    sharpe_change_1d: float
    sharpe_change_7d: float
    sharpe_change_30d: float

    # Metadata
    num_observations: int
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class SharpeAlert:
    """Sharpe ratio alert."""
    timestamp: datetime
    strategy_id: str
    alert_level: AlertLevel
    alert_type: str
    current_sharpe: float
    previous_sharpe: float
    change_pct: float
    message: str
    recommended_action: str

@dataclass
class SharpeDashboardReport:
    """Complete Sharpe dashboard report."""
    report_timestamp: datetime
    overall_metrics: UnifiedSharpeMetrics
    strategy_metrics: dict[str, UnifiedSharpeMetrics]
    active_alerts: list[SharpeAlert]
    historical_sharpe: list[tuple[datetime, float]]

    # Summary statistics
    num_strategies: int
    avg_sharpe_all_strategies: float
    best_performing_strategy: str | None
    worst_performing_strategy: str | None

    # Recommendations
    recommendations: list[str]

# ==============================================================================
# UNIFIED SHARPE DASHBOARD
# ==============================================================================
class UnifiedSharpeDashboard:
    """
    Unified dashboard for Sharpe Ratio monitoring and analysis.

    Integrates Sharpe calculations from:
    - SpyderU15_PerformanceMetrics
    - SpyderE06_RiskMetrics
    - SpyderH07_PerformanceAnalytics
    - SpyderE07_ProbabilisticSharpe

    Features:
    - Real-time Sharpe monitoring
    - Multi-timeframe analysis
    - Probabilistic Sharpe Ratio
    - Options-adjusted Sharpe
    - Degradation alerts
    - Comparative analysis across strategies

    Attributes:
        risk_free_rate: Risk-free rate for calculations
        metrics_cache: Cache of calculated metrics
        alert_history: History of alerts
    """

    def __init__(
        self,
        risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
        enable_alerts: bool = True
    ):
        """
        Initialize Unified Sharpe Dashboard.

        Args:
            risk_free_rate: Risk-free rate for calculations
            enable_alerts: Enable automatic alerting
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.risk_free_rate = risk_free_rate
        self.enable_alerts = enable_alerts

        # Initialize calculators
        if LOCAL_IMPORTS:
            self.risk_metrics_calc = RiskMetricsCalculator(risk_free_rate)
            self.prob_sharpe_calc = ProbabilisticSharpeCalculator(risk_free_rate)
            self.perf_analytics = PerformanceAnalytics(risk_free_rate=risk_free_rate)

        # Thread safety
        self._lock = threading.RLock()

        # Cache
        self.metrics_cache: dict[str, UnifiedSharpeMetrics] = {}
        self.sharpe_history: dict[str, list[tuple[datetime, float]]] = {}
        self.alert_history: list[SharpeAlert] = []

        # Alert thresholds
        self.degradation_threshold = SHARPE_DEGRADATION_THRESHOLD

        self.logger.info("UnifiedSharpeDashboard initialized")

    # ==========================================================================
    # PUBLIC METHODS - METRIC CALCULATION
    # ==========================================================================
    def calculate_unified_metrics(
        self,
        strategy_id: str,
        strategy_name: str,
        returns: list[float],
        equity_curve: list[float],
        benchmark_returns: list[float] | None = None
    ) -> UnifiedSharpeMetrics:
        """
        Calculate unified Sharpe metrics for a strategy.

        Args:
            strategy_id: Strategy identifier
            strategy_name: Strategy name
            returns: List of returns
            equity_curve: Equity curve
            benchmark_returns: Optional benchmark returns

        Returns:
            UnifiedSharpeMetrics object
        """
        if not LOCAL_IMPORTS:
            self.logger.warning("Local imports not available, returning empty metrics")
            return self._create_empty_metrics(strategy_id, strategy_name)

        with self._lock:
            # Calculate Sharpe from different modules
            sharpe_e06 = calculate_sharpe_ratio(returns, self.risk_free_rate)

            # Calculate comprehensive metrics
            risk_metrics = self.risk_metrics_calc.calculate_metrics(
                returns, equity_curve, benchmark_returns
            )

            # Calculate probabilistic Sharpe
            prob_sharpe = self.prob_sharpe_calc.calculate_probabilistic_sharpe(returns)

            # Calculate options-adjusted Sharpe
            options_sharpe = self.prob_sharpe_calc.calculate_options_adjusted_sharpe(returns)

            # Consensus Sharpe (average)
            all_sharpes = [sharpe_e06, risk_metrics.sharpe_ratio, prob_sharpe.sharpe_ratio]
            consensus_sharpe = np.mean([s for s in all_sharpes if s != 0])

            # Determine status
            status = self._determine_sharpe_status(
                consensus_sharpe,
                prob_sharpe.probabilistic_sharpe_ratio
            )

            # Historical averages
            sharpe_30d, sharpe_90d, sharpe_1y = self._calculate_historical_averages(
                strategy_id,
                consensus_sharpe
            )

            # Calculate changes
            change_1d, change_7d, change_30d = self._calculate_sharpe_changes(
                strategy_id,
                consensus_sharpe
            )

            # Create metrics object
            metrics = UnifiedSharpeMetrics(
                timestamp=datetime.now(timezone.utc),
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                sharpe_u15=prob_sharpe.sharpe_ratio,  # Using prob calc as U15 equivalent
                sharpe_e06=sharpe_e06,
                sharpe_h07=risk_metrics.sharpe_ratio,
                probabilistic_sharpe=prob_sharpe,
                options_adjusted_sharpe=options_sharpe,
                consensus_sharpe=consensus_sharpe,
                status=status,
                is_significant=prob_sharpe.confidence_interval.is_significant,
                sharpe_30d_avg=sharpe_30d,
                sharpe_90d_avg=sharpe_90d,
                sharpe_1y_avg=sharpe_1y,
                sharpe_change_1d=change_1d,
                sharpe_change_7d=change_7d,
                sharpe_change_30d=change_30d,
                num_observations=len(returns)
            )

            # Update cache and history
            self.metrics_cache[strategy_id] = metrics
            self._update_sharpe_history(strategy_id, consensus_sharpe)

            # Check for alerts
            if self.enable_alerts:
                self._check_and_generate_alerts(strategy_id, metrics)

            return metrics

    def generate_dashboard_report(
        self,
        strategy_metrics: dict[str, UnifiedSharpeMetrics] | None = None
    ) -> SharpeDashboardReport:
        """
        Generate comprehensive dashboard report.

        Args:
            strategy_metrics: Optional dict of strategy metrics (uses cache if None)

        Returns:
            SharpeDashboardReport
        """
        with self._lock:
            if strategy_metrics is None:
                strategy_metrics = self.metrics_cache.copy()

            # Calculate overall metrics (portfolio-level)
            if strategy_metrics:
                # Overall consensus Sharpe (weighted average)
                total_obs = sum(m.num_observations for m in strategy_metrics.values())
                if total_obs > 0:
                    overall_sharpe = sum(
                        m.consensus_sharpe * m.num_observations
                        for m in strategy_metrics.values()
                    ) / total_obs
                else:
                    overall_sharpe = 0.0

                # Find best/worst strategies
                sorted_strategies = sorted(
                    strategy_metrics.items(),
                    key=lambda x: x[1].consensus_sharpe,
                    reverse=True
                )

                best_strategy = sorted_strategies[0][0] if sorted_strategies else None
                worst_strategy = sorted_strategies[-1][0] if sorted_strategies else None

                # Calculate overall probabilistic Sharpe (average)
                avg_psr = np.mean([
                    m.probabilistic_sharpe.probabilistic_sharpe_ratio
                    for m in strategy_metrics.values()
                ])

                # Create synthetic overall metrics
                overall_metrics = self._create_overall_metrics(
                    strategy_metrics,
                    overall_sharpe,
                    avg_psr
                )
            else:
                overall_metrics = self._create_empty_metrics("overall", "Overall Portfolio")
                best_strategy = None
                worst_strategy = None

            # Get active alerts
            active_alerts = self._get_active_alerts()

            # Generate recommendations
            recommendations = self._generate_recommendations(
                overall_metrics,
                strategy_metrics,
                active_alerts
            )

            # Build report
            report = SharpeDashboardReport(
                report_timestamp=datetime.now(timezone.utc),
                overall_metrics=overall_metrics,
                strategy_metrics=strategy_metrics,
                active_alerts=active_alerts,
                historical_sharpe=self.sharpe_history.get("overall", []),
                num_strategies=len(strategy_metrics),
                avg_sharpe_all_strategies=overall_metrics.consensus_sharpe,
                best_performing_strategy=best_strategy,
                worst_performing_strategy=worst_strategy,
                recommendations=recommendations
            )

            return report

    # ==========================================================================
    # ALERT MANAGEMENT
    # ==========================================================================
    def _check_and_generate_alerts(
        self,
        strategy_id: str,
        current_metrics: UnifiedSharpeMetrics
    ) -> None:
        """Check for Sharpe degradation and generate alerts."""
        # Get previous metrics
        history = self.sharpe_history.get(strategy_id, [])
        if len(history) < 2:
            return  # Need at least 2 data points

        current_sharpe = current_metrics.consensus_sharpe
        previous_sharpe = history[-2][1] if len(history) >= 2 else current_sharpe

        if previous_sharpe == 0:
            return

        change_pct = (current_sharpe - previous_sharpe) / abs(previous_sharpe)

        # Check for significant degradation
        if change_pct < -self.degradation_threshold:
            alert = SharpeAlert(
                timestamp=datetime.now(timezone.utc),
                strategy_id=strategy_id,
                alert_level=AlertLevel.CRITICAL,
                alert_type="sharpe_degradation",
                current_sharpe=current_sharpe,
                previous_sharpe=previous_sharpe,
                change_pct=change_pct,
                message=f"Sharpe Ratio dropped {abs(change_pct):.1%} from {previous_sharpe:.2f} to {current_sharpe:.2f}",  # noqa: E501
                recommended_action="Review strategy performance, consider reducing position sizes"
            )

            self.alert_history.append(alert)
            self.logger.warning("Sharpe degradation alert: %s", alert.message)

        # Check for low probabilistic Sharpe
        if current_metrics.probabilistic_sharpe.probabilistic_sharpe_ratio < 0.70:
            alert = SharpeAlert(
                timestamp=datetime.now(timezone.utc),
                strategy_id=strategy_id,
                alert_level=AlertLevel.WARNING,
                alert_type="low_psr",
                current_sharpe=current_sharpe,
                previous_sharpe=previous_sharpe,
                change_pct=0.0,
                message=f"Low probability ({current_metrics.probabilistic_sharpe.probabilistic_sharpe_ratio:.0%}) that true Sharpe > 0",  # noqa: E501
                recommended_action="Increase sample size or review strategy edge"
            )

            self.alert_history.append(alert)
            self.logger.warning("Low PSR alert: %s", alert.message)

        # Check if Sharpe suggests >5% (estimation error indicator)
        if current_sharpe > 5.0:
            alert = SharpeAlert(
                timestamp=datetime.now(timezone.utc),
                strategy_id=strategy_id,
                alert_level=AlertLevel.WARNING,
                alert_type="unrealistic_sharpe",
                current_sharpe=current_sharpe,
                previous_sharpe=previous_sharpe,
                change_pct=0.0,
                message=f"Unrealistically high Sharpe ({current_sharpe:.2f}) suggests estimation error",  # noqa: E501
                recommended_action="Verify calculations and check for data quality issues"
            )

            self.alert_history.append(alert)
            self.logger.warning("Unrealistic Sharpe alert: %s", alert.message)

    def _get_active_alerts(self, hours: int = 24) -> list[SharpeAlert]:
        """Get active alerts from last N hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [
            alert for alert in self.alert_history
            if alert.timestamp >= cutoff
        ]

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _determine_sharpe_status(
        self,
        sharpe: float,
        psr: float
    ) -> SharpeStatus:
        """Determine Sharpe status based on value and confidence."""
        if psr < 0.70:
            return SharpeStatus.INSUFFICIENT_DATA
        elif sharpe >= SHARPE_EXCELLENT_THRESHOLD:
            return SharpeStatus.EXCELLENT
        elif sharpe >= SHARPE_GOOD_THRESHOLD:
            return SharpeStatus.GOOD
        elif sharpe >= SHARPE_POOR_THRESHOLD:
            return SharpeStatus.AVERAGE
        else:
            return SharpeStatus.POOR

    def _update_sharpe_history(
        self,
        strategy_id: str,
        sharpe: float
    ) -> None:
        """Update Sharpe history for a strategy."""
        if strategy_id not in self.sharpe_history:
            self.sharpe_history[strategy_id] = []

        self.sharpe_history[strategy_id].append((datetime.now(timezone.utc), sharpe))

        # Keep last 365 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=365)
        self.sharpe_history[strategy_id] = [
            (ts, s) for ts, s in self.sharpe_history[strategy_id]
            if ts >= cutoff
        ]

    def _calculate_historical_averages(
        self,
        strategy_id: str,
        current_sharpe: float
    ) -> tuple[float, float, float]:
        """Calculate 30d, 90d, 1y average Sharpe."""
        history = self.sharpe_history.get(strategy_id, [])

        if not history:
            return current_sharpe, current_sharpe, current_sharpe

        now = datetime.now(timezone.utc)

        # 30-day average
        sharpe_30d = [
            s for ts, s in history
            if ts >= now - timedelta(days=30)
        ]
        avg_30d = np.mean(sharpe_30d) if sharpe_30d else current_sharpe

        # 90-day average
        sharpe_90d = [
            s for ts, s in history
            if ts >= now - timedelta(days=90)
        ]
        avg_90d = np.mean(sharpe_90d) if sharpe_90d else current_sharpe

        # 1-year average
        sharpe_1y = [s for _, s in history]
        avg_1y = np.mean(sharpe_1y) if sharpe_1y else current_sharpe

        return avg_30d, avg_90d, avg_1y

    def _calculate_sharpe_changes(
        self,
        strategy_id: str,
        current_sharpe: float
    ) -> tuple[float, float, float]:
        """Calculate 1d, 7d, 30d Sharpe changes."""
        history = self.sharpe_history.get(strategy_id, [])

        if not history:
            return 0.0, 0.0, 0.0

        now = datetime.now(timezone.utc)

        # Find historical values
        def find_sharpe_at_date(days_ago: int) -> float | None:
            target_date = now - timedelta(days=days_ago)
            # Find closest historical point
            closest = min(
                history,
                key=lambda x: abs((x[0] - target_date).total_seconds()),
                default=None
            )
            return closest[1] if closest else None

        sharpe_1d_ago = find_sharpe_at_date(1)
        sharpe_7d_ago = find_sharpe_at_date(7)
        sharpe_30d_ago = find_sharpe_at_date(30)

        change_1d = (current_sharpe - sharpe_1d_ago) if sharpe_1d_ago else 0.0
        change_7d = (current_sharpe - sharpe_7d_ago) if sharpe_7d_ago else 0.0
        change_30d = (current_sharpe - sharpe_30d_ago) if sharpe_30d_ago else 0.0

        return change_1d, change_7d, change_30d

    def _generate_recommendations(
        self,
        overall_metrics: UnifiedSharpeMetrics,
        strategy_metrics: dict[str, UnifiedSharpeMetrics],
        active_alerts: list[SharpeAlert]
    ) -> list[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # Overall Sharpe assessment
        if overall_metrics.status == SharpeStatus.POOR:
            recommendations.append(
                "Overall Sharpe Ratio is poor. Consider reducing position sizes or pausing live trading."  # noqa: E501
            )
        elif overall_metrics.status == SharpeStatus.EXCELLENT:
            recommendations.append(
                "Excellent risk-adjusted performance. Consider gradual position size increases."
            )

        # Probabilistic Sharpe assessment
        psr = overall_metrics.probabilistic_sharpe.probabilistic_sharpe_ratio
        if psr < 0.80:
            recommendations.append(
                f"Low confidence ({psr:.0%}) in positive Sharpe. Need {overall_metrics.probabilistic_sharpe.min_track_record_length - overall_metrics.num_observations} more observations for significance."  # noqa: E501
            )

        # Options adjustment
        if overall_metrics.options_adjusted_sharpe.adjusted_sharpe < overall_metrics.consensus_sharpe:  # noqa: E501
            recommendations.append(
                f"Negative skew ({overall_metrics.options_adjusted_sharpe.skewness:.2f}) indicates tail risk. Consider tighter stop losses."  # noqa: E501
            )

        # Strategy-specific
        if strategy_metrics:
            poor_strategies = [
                name for name, m in strategy_metrics.items()
                if m.status == SharpeStatus.POOR
            ]

            if poor_strategies:
                recommendations.append(
                    f"Strategies with poor Sharpe: {', '.join(poor_strategies)}. Review or disable these strategies."  # noqa: E501
                )

        # Alert-based
        critical_alerts = [a for a in active_alerts if a.alert_level == AlertLevel.CRITICAL]
        if critical_alerts:
            recommendations.append(
                f"{len(critical_alerts)} critical Sharpe alerts active. Immediate review required."
            )

        return recommendations

    def _create_empty_metrics(
        self,
        strategy_id: str,
        strategy_name: str
    ) -> UnifiedSharpeMetrics:
        """Create empty metrics object."""
        from SpyderE_Risk.SpyderE07_ProbabilisticSharpe import (
            ProbabilisticSharpeResult,
            OptionsAdjustedSharpe,
            SharpeConfidenceInterval
        )

        empty_ci = SharpeConfidenceInterval(
            sharpe_ratio=0.0,
            lower_bound=0.0,
            upper_bound=0.0,
            confidence_level=0.95,
            standard_error=0.0,
            num_observations=0,
            is_significant=False
        )

        empty_psr = ProbabilisticSharpeResult(
            sharpe_ratio=0.0,
            probabilistic_sharpe_ratio=0.0,
            benchmark_sharpe=0.0,
            confidence_interval=empty_ci,
            min_track_record_length=999999,
            num_observations=0,
            skewness=0.0,
            kurtosis=3.0
        )

        empty_options = OptionsAdjustedSharpe(
            standard_sharpe=0.0,
            adjusted_sharpe=0.0,
            skewness=0.0,
            excess_kurtosis=0.0,
            adjustment_factor=1.0,
            num_observations=0
        )

        return UnifiedSharpeMetrics(
            timestamp=datetime.now(timezone.utc),
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            sharpe_u15=0.0,
            sharpe_e06=0.0,
            sharpe_h07=0.0,
            probabilistic_sharpe=empty_psr,
            options_adjusted_sharpe=empty_options,
            consensus_sharpe=0.0,
            status=SharpeStatus.INSUFFICIENT_DATA,
            is_significant=False,
            sharpe_30d_avg=0.0,
            sharpe_90d_avg=0.0,
            sharpe_1y_avg=0.0,
            sharpe_change_1d=0.0,
            sharpe_change_7d=0.0,
            sharpe_change_30d=0.0,
            num_observations=0
        )

    def _create_overall_metrics(
        self,
        strategy_metrics: dict[str, UnifiedSharpeMetrics],
        overall_sharpe: float,
        avg_psr: float
    ) -> UnifiedSharpeMetrics:
        """Create overall portfolio metrics."""
        # This would be more sophisticated in production
        # For now, return a representative metric
        if strategy_metrics:
            next(iter(strategy_metrics.values()))
            overall = self._create_empty_metrics("overall", "Overall Portfolio")
            overall.consensus_sharpe = overall_sharpe
            overall.probabilistic_sharpe.probabilistic_sharpe_ratio = avg_psr
            overall.num_observations = sum(m.num_observations for m in strategy_metrics.values())
            overall.status = self._determine_sharpe_status(overall_sharpe, avg_psr)
            return overall

        return self._create_empty_metrics("overall", "Overall Portfolio")

    # ==========================================================================
    # EXPORT METHODS
    # ==========================================================================
    def export_report(
        self,
        report: SharpeDashboardReport,
        format: str = "text",
        output_path: Path | None = None
    ) -> str:
        """
        Export dashboard report.

        Args:
            report: Dashboard report to export
            format: 'text', 'json', or 'html'
            output_path: Optional file path to save

        Returns:
            Formatted report string
        """
        if format == "json":
            content = self._export_json(report)
        elif format == "html":
            content = self._export_html(report)
        else:
            content = self._export_text(report)

        if output_path:
            with open(output_path, 'w') as f:
                f.write(content)
            self.logger.info("Report exported to %s", output_path)

        return content

    def _export_text(self, report: SharpeDashboardReport) -> str:
        """Export as formatted text."""
        lines = [
            "=" * 80,
            "SPYDER UNIFIED SHARPE RATIO DASHBOARD",
            "=" * 80,
            f"Generated: {report.report_timestamp}",
            "",
            "-" * 80,
            "OVERALL METRICS",
            "-" * 80,
            f"  Consensus Sharpe Ratio: {report.overall_metrics.consensus_sharpe:.3f}",
            f"  Status: {report.overall_metrics.status.value.upper()}",
            f"  Probabilistic Sharpe: {report.overall_metrics.probabilistic_sharpe.probabilistic_sharpe_ratio:.1%}",  # noqa: E501
            f"  Options-Adjusted Sharpe: {report.overall_metrics.options_adjusted_sharpe.adjusted_sharpe:.3f}",  # noqa: E501
            f"  Statistical Significance: {'Yes' if report.overall_metrics.is_significant else 'No'}",  # noqa: E501
            "",
            f"  30-day Average: {report.overall_metrics.sharpe_30d_avg:.3f}",
            f"  90-day Average: {report.overall_metrics.sharpe_90d_avg:.3f}",
            f"  1-year Average: {report.overall_metrics.sharpe_1y_avg:.3f}",
            "",
            "-" * 80,
            f"STRATEGY SUMMARY ({report.num_strategies} strategies)",
            "-" * 80,
        ]

        if report.best_performing_strategy:
            lines.append(f"  Best: {report.best_performing_strategy}")
        if report.worst_performing_strategy:
            lines.append(f"  Worst: {report.worst_performing_strategy}")

        if report.active_alerts:
            lines.extend([
                "",
                "-" * 80,
                f"ACTIVE ALERTS ({len(report.active_alerts)})",
                "-" * 80,
            ])
            for alert in report.active_alerts[:5]:  # Top 5
                lines.append(f"  [{alert.alert_level.value.upper()}] {alert.message}")

        if report.recommendations:
            lines.extend([
                "",
                "-" * 80,
                "RECOMMENDATIONS",
                "-" * 80,
            ])
            for i, rec in enumerate(report.recommendations, 1):
                lines.append(f"  {i}. {rec}")

        lines.append("\n" + "=" * 80)

        return "\n".join(lines)

    def _export_json(self, report: SharpeDashboardReport) -> str:
        """Export as JSON."""
        # This would need custom serialization for dataclasses
        # Simplified version
        data = {
            "timestamp": report.report_timestamp.isoformat(),
            "consensus_sharpe": report.overall_metrics.consensus_sharpe,
            "num_strategies": report.num_strategies,
            "active_alerts": len(report.active_alerts),
            "recommendations": report.recommendations
        }
        return json.dumps(data, indent=2)

    def _export_html(self, report: SharpeDashboardReport) -> str:
        """Export as HTML."""
        return f"""
<!DOCTYPE html>
<html>
<head><title>Sharpe Dashboard</title></head>
<body>
<h1>Unified Sharpe Dashboard</h1>
<p>Generated: {report.report_timestamp}</p>
<h2>Overall Sharpe: {report.overall_metrics.consensus_sharpe:.3f}</h2>
<p>Status: {report.overall_metrics.status.value}</p>
</body>
</html>
"""

    # --------------------------------------------------------------------------
    # EMPYRICAL VALIDATED SHARPE
    # --------------------------------------------------------------------------

    def compute_validated_sharpe(self, returns: pd.Series,
                                 rolling_window: int = 63,
                                 risk_free_rate: float = 0.05,
                                 ) -> dict[str, Any]:
        """
        Compute validated Sharpe ratio using empyrical library.

        Replaces hand-rolled Sharpe calculation with the institutional-grade
        empyrical implementation for accuracy and consistency.

        Args:
            returns: Strategy daily return series.
            rolling_window: Rolling Sharpe window in trading days.
            risk_free_rate: Annual risk-free rate.

        Returns:
            Dictionary with overall and rolling Sharpe metrics.
        """
        try:
            import empyrical
        except ImportError:
            self.logger.warning("empyrical not installed — using manual Sharpe")
            sharpe = float(returns.mean() / (returns.std() + 1e-8) * np.sqrt(252))
            return {'sharpe_ratio': sharpe, '_backend': 'fallback'}

        rf_daily = risk_free_rate / 252

        overall_sharpe = float(empyrical.sharpe_ratio(returns, risk_free=rf_daily))

        # Rolling Sharpe via empyrical
        try:
            rolling_sharpe = empyrical.roll_sharpe_ratio(
                returns, rolling_window=rolling_window, risk_free=rf_daily)
            rolling_dict = {str(k): float(v) for k, v in rolling_sharpe.dropna().items()}
        except Exception:
            rolling_dict = {}

        result = {
            'sharpe_ratio': overall_sharpe,
            'sortino_ratio': float(empyrical.sortino_ratio(returns)),
            'rolling_sharpe': rolling_dict,
            'rolling_window': rolling_window,
            'max_rolling_sharpe': float(max(rolling_dict.values())) if rolling_dict else 0,
            'min_rolling_sharpe': float(min(rolling_dict.values())) if rolling_dict else 0,
            '_backend': 'empyrical',
        }

        self.logger.info(f"Validated Sharpe: {overall_sharpe:.4f} (empyrical)")
        return result

# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    'UnifiedSharpeDashboard',
    'UnifiedSharpeMetrics',
    'SharpeAlert',
    'SharpeDashboardReport',
    'SharpeStatus',
    'AlertLevel',
]

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":

    if not LOCAL_IMPORTS:
        pass
    else:
        # Create dashboard
        dashboard = UnifiedSharpeDashboard()

        # Generate sample returns
        np.random.seed(42)
        returns_strategy1 = np.random.normal(0.001, 0.02, 250).tolist()
        equity_curve1 = [100000]
        for r in returns_strategy1:
            equity_curve1.append(equity_curve1[-1] * (1 + r))

        # Calculate metrics
        metrics = dashboard.calculate_unified_metrics(
            strategy_id="strategy_1",
            strategy_name="Test Strategy 1",
            returns=returns_strategy1,
            equity_curve=equity_curve1
        )


        # Generate report
        report = dashboard.generate_dashboard_report()

        # Export as text
        text_report = dashboard.export_report(report, format="text")

