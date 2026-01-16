#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderK_Reports
Module: SpyderK05_RiskReport.py
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
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
import threading

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    LOCAL_IMPORTS = True
except ImportError:
    import logging
    SpyderLogger = type('SpyderLogger', (), {
        'get_logger': staticmethod(lambda name: logging.getLogger(name))
    })()
    LOCAL_IMPORTS = False

try:
    from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    SpyderErrorHandler = type('SpyderErrorHandler', (), {
        'handle_error': lambda self, e, context: print(f"Error in {context}: {e}")
    })

# ==============================================================================
# CONSTANTS
# ==============================================================================
REPORT_OUTPUT_DIR = Path("reports/risk")
CONFIDENCE_LEVELS = [0.90, 0.95, 0.99]
TRADING_DAYS_PER_YEAR = 252
MAX_ACCEPTABLE_VAR_PERCENT = 5.0  # 5% of portfolio value
MAX_ACCEPTABLE_DRAWDOWN = 10.0    # 10% maximum drawdown threshold

# Risk thresholds
RISK_THRESHOLDS = {
    "delta_limit": 100.0,
    "gamma_limit": 50.0,
    "theta_limit": -500.0,
    "vega_limit": 1000.0,
    "var_limit_percent": 5.0,
    "max_drawdown_percent": 10.0,
    "concentration_limit": 25.0,  # Max 25% in single position
}


# ==============================================================================
# ENUMS
# ==============================================================================
class RiskLevel(Enum):
    """Risk severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReportFormat(Enum):
    """Output formats for risk reports."""
    JSON = "json"
    HTML = "html"
    PDF = "pdf"
    TEXT = "text"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class VaRResult:
    """Value at Risk calculation result."""
    confidence_level: float
    var_absolute: float
    var_percent: float
    expected_shortfall: float  # CVaR
    calculation_method: str
    lookback_days: int
    calculated_at: datetime = field(default_factory=datetime.now)


@dataclass
class GreeksExposure:
    """Portfolio Greeks exposure summary."""
    total_delta: float = 0.0
    total_gamma: float = 0.0
    total_theta: float = 0.0
    total_vega: float = 0.0
    total_rho: float = 0.0
    delta_dollars: float = 0.0
    gamma_dollars: float = 0.0
    theta_daily: float = 0.0
    vega_per_vol: float = 0.0


@dataclass
class DrawdownAnalysis:
    """Drawdown analysis results."""
    current_drawdown: float
    max_drawdown: float
    max_drawdown_date: Optional[date]
    drawdown_duration_days: int
    recovery_needed_percent: float
    avg_drawdown: float
    drawdown_count: int


@dataclass
class RiskLimitStatus:
    """Status of a risk limit check."""
    limit_name: str
    current_value: float
    limit_value: float
    utilization_percent: float
    is_breached: bool
    risk_level: RiskLevel
    message: str


@dataclass
class RiskReportData:
    """Container for comprehensive risk report data."""
    report_date: date
    report_time: datetime
    account_id: str
    portfolio_value: float

    # VaR metrics
    var_results: List[VaRResult] = field(default_factory=list)

    # Greeks exposure
    greeks_exposure: Optional[GreeksExposure] = None

    # Drawdown analysis
    drawdown_analysis: Optional[DrawdownAnalysis] = None

    # Risk limit status
    limit_checks: List[RiskLimitStatus] = field(default_factory=list)

    # Stress test results
    stress_test_results: Dict[str, float] = field(default_factory=dict)

    # Concentration risk
    concentration_by_symbol: Dict[str, float] = field(default_factory=dict)
    concentration_by_strategy: Dict[str, float] = field(default_factory=dict)

    # Overall risk assessment
    overall_risk_level: RiskLevel = RiskLevel.LOW
    risk_score: float = 0.0
    alerts: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


# ==============================================================================
# RISK REPORT GENERATOR
# ==============================================================================
class RiskReportGenerator:
    """
    Comprehensive risk report generator for trading analysis.

    Generates detailed risk reports including VaR calculations, Greeks exposure,
    drawdown analysis, stress testing results, and risk limit compliance checks.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize risk report generator.

        Args:
            config: Optional configuration dictionary
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.config = config or {}

        # Output configuration
        self.output_dir = Path(self.config.get('output_dir', REPORT_OUTPUT_DIR))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Risk thresholds
        self.thresholds = self.config.get('thresholds', RISK_THRESHOLDS.copy())

        # Calculation settings
        self.var_lookback_days = self.config.get('var_lookback_days', 252)
        self.confidence_levels = self.config.get('confidence_levels', CONFIDENCE_LEVELS)

        # Thread safety
        self._lock = threading.Lock()

        self.logger.info("RiskReportGenerator initialized")

    def generate_risk_report(
        self,
        portfolio_data: Dict[str, Any],
        returns_history: Optional[pd.Series] = None,
        positions: Optional[List[Dict[str, Any]]] = None
    ) -> RiskReportData:
        """
        Generate comprehensive risk report.

        Args:
            portfolio_data: Current portfolio state including value and positions
            returns_history: Historical returns series for VaR calculation
            positions: List of current positions with Greeks

        Returns:
            RiskReportData containing all risk analysis
        """
        with self._lock:
            try:
                account_id = portfolio_data.get('account_id', 'unknown')
                portfolio_value = portfolio_data.get('total_value', 0.0)

                report = RiskReportData(
                    report_date=date.today(),
                    report_time=datetime.now(),
                    account_id=account_id,
                    portfolio_value=portfolio_value
                )

                # Calculate VaR if returns history provided
                if returns_history is not None and len(returns_history) > 0:
                    report.var_results = self._calculate_var_metrics(
                        returns_history, portfolio_value
                    )

                # Calculate Greeks exposure if positions provided
                if positions:
                    report.greeks_exposure = self._calculate_greeks_exposure(positions)
                    report.concentration_by_symbol = self._calculate_concentration(
                        positions, portfolio_value, 'symbol'
                    )
                    report.concentration_by_strategy = self._calculate_concentration(
                        positions, portfolio_value, 'strategy'
                    )

                # Calculate drawdown if returns history provided
                if returns_history is not None and len(returns_history) > 0:
                    report.drawdown_analysis = self._calculate_drawdown(returns_history)

                # Run stress tests
                if returns_history is not None:
                    report.stress_test_results = self._run_stress_tests(
                        portfolio_value, returns_history
                    )

                # Check risk limits
                report.limit_checks = self._check_risk_limits(report)

                # Calculate overall risk assessment
                report.overall_risk_level, report.risk_score = self._assess_overall_risk(report)

                # Generate alerts and recommendations
                report.alerts = self._generate_alerts(report)
                report.recommendations = self._generate_recommendations(report)

                self.logger.info(
                    f"Risk report generated - Risk Level: {report.overall_risk_level.value}, "
                    f"Score: {report.risk_score:.2f}"
                )

                return report

            except Exception as e:
                self.logger.error(f"Error generating risk report: {e}")
                raise

    def calculate_var(
        self,
        returns: Union[List[float], np.ndarray, pd.Series],
        confidence: float = 0.95,
        method: str = 'historical'
    ) -> float:
        """
        Calculate Value at Risk.

        Args:
            returns: Historical returns data
            confidence: Confidence level (default 0.95 for 95% VaR)
            method: Calculation method ('historical', 'parametric', 'monte_carlo')

        Returns:
            VaR as a positive number representing potential loss
        """
        returns_array = np.array(returns)

        if len(returns_array) < 30:
            self.logger.warning("Insufficient data for reliable VaR calculation")

        if method == 'historical':
            var = np.percentile(returns_array, (1 - confidence) * 100)
        elif method == 'parametric':
            from scipy import stats
            mean = np.mean(returns_array)
            std = np.std(returns_array)
            var = mean - std * stats.norm.ppf(confidence)
        elif method == 'monte_carlo':
            mean = np.mean(returns_array)
            std = np.std(returns_array)
            simulated = np.random.normal(mean, std, 10000)
            var = np.percentile(simulated, (1 - confidence) * 100)
        else:
            raise ValueError(f"Unknown VaR method: {method}")

        return abs(var)

    def calculate_cvar(
        self,
        returns: Union[List[float], np.ndarray, pd.Series],
        confidence: float = 0.95
    ) -> float:
        """
        Calculate Conditional Value at Risk (Expected Shortfall).

        Args:
            returns: Historical returns data
            confidence: Confidence level

        Returns:
            CVaR as a positive number
        """
        returns_array = np.array(returns)
        var = self.calculate_var(returns_array, confidence, 'historical')
        tail_losses = returns_array[returns_array <= -var]

        if len(tail_losses) > 0:
            cvar = abs(np.mean(tail_losses))
        else:
            cvar = var

        return cvar

    def _calculate_var_metrics(
        self,
        returns: pd.Series,
        portfolio_value: float
    ) -> List[VaRResult]:
        """Calculate VaR at multiple confidence levels."""
        results = []

        for conf in self.confidence_levels:
            var_pct = self.calculate_var(returns, conf, 'historical')
            cvar_pct = self.calculate_cvar(returns, conf)

            results.append(VaRResult(
                confidence_level=conf,
                var_absolute=portfolio_value * var_pct,
                var_percent=var_pct * 100,
                expected_shortfall=portfolio_value * cvar_pct,
                calculation_method='historical',
                lookback_days=len(returns)
            ))

        return results

    def _calculate_greeks_exposure(
        self,
        positions: List[Dict[str, Any]]
    ) -> GreeksExposure:
        """Calculate aggregate Greeks exposure from positions."""
        exposure = GreeksExposure()

        for pos in positions:
            quantity = pos.get('quantity', 0)
            multiplier = pos.get('multiplier', 100)
            price = pos.get('price', 0)

            greeks = pos.get('greeks', {})
            exposure.total_delta += greeks.get('delta', 0) * quantity * multiplier
            exposure.total_gamma += greeks.get('gamma', 0) * quantity * multiplier
            exposure.total_theta += greeks.get('theta', 0) * quantity * multiplier
            exposure.total_vega += greeks.get('vega', 0) * quantity * multiplier
            exposure.total_rho += greeks.get('rho', 0) * quantity * multiplier

        # Calculate dollar exposures (assuming SPY ~$500)
        spy_price = 500.0  # Could be passed in or fetched
        exposure.delta_dollars = exposure.total_delta * spy_price
        exposure.gamma_dollars = exposure.total_gamma * spy_price * spy_price / 100
        exposure.theta_daily = exposure.total_theta
        exposure.vega_per_vol = exposure.total_vega

        return exposure

    def _calculate_concentration(
        self,
        positions: List[Dict[str, Any]],
        portfolio_value: float,
        group_by: str
    ) -> Dict[str, float]:
        """Calculate position concentration by symbol or strategy."""
        concentration = {}

        for pos in positions:
            key = pos.get(group_by, 'unknown')
            value = abs(pos.get('market_value', 0))
            concentration[key] = concentration.get(key, 0) + value

        # Convert to percentages
        if portfolio_value > 0:
            concentration = {
                k: (v / portfolio_value) * 100
                for k, v in concentration.items()
            }

        return concentration

    def _calculate_drawdown(self, returns: pd.Series) -> DrawdownAnalysis:
        """Calculate drawdown metrics from returns series."""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdowns = (cumulative - running_max) / running_max

        current_dd = drawdowns.iloc[-1] if len(drawdowns) > 0 else 0
        max_dd = drawdowns.min()
        max_dd_idx = drawdowns.idxmin() if len(drawdowns) > 0 else None

        # Calculate drawdown duration
        in_drawdown = drawdowns < 0
        dd_periods = 0
        if in_drawdown.iloc[-1]:
            for i in range(len(in_drawdown) - 1, -1, -1):
                if in_drawdown.iloc[i]:
                    dd_periods += 1
                else:
                    break

        # Count number of drawdowns
        dd_count = (in_drawdown.astype(int).diff() == 1).sum()

        # Calculate recovery needed
        recovery_needed = (1 / (1 + current_dd) - 1) * 100 if current_dd < 0 else 0

        return DrawdownAnalysis(
            current_drawdown=current_dd * 100,
            max_drawdown=max_dd * 100,
            max_drawdown_date=max_dd_idx.date() if max_dd_idx is not None else None,
            drawdown_duration_days=dd_periods,
            recovery_needed_percent=recovery_needed,
            avg_drawdown=drawdowns[drawdowns < 0].mean() * 100 if (drawdowns < 0).any() else 0,
            drawdown_count=dd_count
        )

    def _run_stress_tests(
        self,
        portfolio_value: float,
        returns: pd.Series
    ) -> Dict[str, float]:
        """Run stress test scenarios."""
        results = {}

        # Historical scenarios
        results['worst_day'] = returns.min() * portfolio_value
        results['worst_week'] = returns.rolling(5).sum().min() * portfolio_value
        results['worst_month'] = returns.rolling(21).sum().min() * portfolio_value

        # Hypothetical scenarios
        std = returns.std()
        results['2_sigma_loss'] = -2 * std * portfolio_value
        results['3_sigma_loss'] = -3 * std * portfolio_value

        # Market crash scenarios
        results['flash_crash_5pct'] = -0.05 * portfolio_value
        results['correction_10pct'] = -0.10 * portfolio_value
        results['bear_market_20pct'] = -0.20 * portfolio_value

        return results

    def _check_risk_limits(self, report: RiskReportData) -> List[RiskLimitStatus]:
        """Check all risk limits and return status."""
        checks = []

        # Check VaR limit
        if report.var_results:
            var_95 = next(
                (v for v in report.var_results if v.confidence_level == 0.95),
                None
            )
            if var_95:
                limit = self.thresholds['var_limit_percent']
                checks.append(self._create_limit_status(
                    'VaR 95%', var_95.var_percent, limit, 'VaR'
                ))

        # Check Greeks limits
        if report.greeks_exposure:
            ge = report.greeks_exposure
            checks.append(self._create_limit_status(
                'Delta', abs(ge.total_delta), self.thresholds['delta_limit'], 'Greeks'
            ))
            checks.append(self._create_limit_status(
                'Gamma', abs(ge.total_gamma), self.thresholds['gamma_limit'], 'Greeks'
            ))
            checks.append(self._create_limit_status(
                'Vega', abs(ge.total_vega), self.thresholds['vega_limit'], 'Greeks'
            ))

        # Check drawdown limit
        if report.drawdown_analysis:
            dd = abs(report.drawdown_analysis.current_drawdown)
            limit = self.thresholds['max_drawdown_percent']
            checks.append(self._create_limit_status(
                'Drawdown', dd, limit, 'Drawdown'
            ))

        # Check concentration limits
        for symbol, conc in report.concentration_by_symbol.items():
            if conc > self.thresholds['concentration_limit']:
                checks.append(self._create_limit_status(
                    f'Concentration ({symbol})',
                    conc,
                    self.thresholds['concentration_limit'],
                    'Concentration'
                ))

        return checks

    def _create_limit_status(
        self,
        name: str,
        current: float,
        limit: float,
        category: str
    ) -> RiskLimitStatus:
        """Create a risk limit status check."""
        utilization = (current / limit) * 100 if limit > 0 else 0
        is_breached = current > limit

        if utilization <= 50:
            risk_level = RiskLevel.LOW
        elif utilization <= 75:
            risk_level = RiskLevel.MEDIUM
        elif utilization <= 100:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.CRITICAL

        status = "BREACHED" if is_breached else "OK"
        message = f"{category}: {name} at {current:.2f} ({utilization:.1f}% of limit) - {status}"

        return RiskLimitStatus(
            limit_name=name,
            current_value=current,
            limit_value=limit,
            utilization_percent=utilization,
            is_breached=is_breached,
            risk_level=risk_level,
            message=message
        )

    def _assess_overall_risk(
        self,
        report: RiskReportData
    ) -> Tuple[RiskLevel, float]:
        """Calculate overall risk level and score."""
        # Start with base score
        score = 0.0

        # VaR contribution (0-30 points)
        if report.var_results:
            var_95 = next(
                (v for v in report.var_results if v.confidence_level == 0.95),
                None
            )
            if var_95:
                var_score = min(var_95.var_percent / MAX_ACCEPTABLE_VAR_PERCENT * 30, 30)
                score += var_score

        # Drawdown contribution (0-30 points)
        if report.drawdown_analysis:
            dd = abs(report.drawdown_analysis.current_drawdown)
            dd_score = min(dd / MAX_ACCEPTABLE_DRAWDOWN * 30, 30)
            score += dd_score

        # Limit breaches contribution (0-40 points)
        breach_count = sum(1 for c in report.limit_checks if c.is_breached)
        high_util_count = sum(1 for c in report.limit_checks if c.utilization_percent > 75)
        score += breach_count * 10 + high_util_count * 5

        # Determine risk level from score
        if score <= 25:
            level = RiskLevel.LOW
        elif score <= 50:
            level = RiskLevel.MEDIUM
        elif score <= 75:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.CRITICAL

        return level, min(score, 100)

    def _generate_alerts(self, report: RiskReportData) -> List[str]:
        """Generate alert messages based on risk analysis."""
        alerts = []

        # Check for breached limits
        for check in report.limit_checks:
            if check.is_breached:
                alerts.append(f"LIMIT BREACH: {check.message}")
            elif check.utilization_percent > 80:
                alerts.append(f"WARNING: {check.limit_name} approaching limit ({check.utilization_percent:.1f}%)")

        # Check drawdown
        if report.drawdown_analysis:
            if report.drawdown_analysis.current_drawdown < -5:
                alerts.append(
                    f"DRAWDOWN ALERT: Current drawdown {report.drawdown_analysis.current_drawdown:.2f}%"
                )

        # Check VaR
        if report.var_results:
            var_95 = next((v for v in report.var_results if v.confidence_level == 0.95), None)
            if var_95 and var_95.var_percent > MAX_ACCEPTABLE_VAR_PERCENT:
                alerts.append(f"VAR ALERT: 95% VaR at {var_95.var_percent:.2f}% exceeds limit")

        return alerts

    def _generate_recommendations(self, report: RiskReportData) -> List[str]:
        """Generate recommendations based on risk analysis."""
        recommendations = []

        # Greeks-based recommendations
        if report.greeks_exposure:
            ge = report.greeks_exposure
            if abs(ge.total_delta) > self.thresholds['delta_limit'] * 0.8:
                recommendations.append("Consider hedging delta exposure with SPY shares or futures")
            if ge.total_theta < self.thresholds['theta_limit'] * 0.8:
                recommendations.append("High negative theta - consider closing time-decay positions")
            if abs(ge.total_vega) > self.thresholds['vega_limit'] * 0.8:
                recommendations.append("High vega exposure - consider reducing volatility sensitivity")

        # Concentration recommendations
        for symbol, conc in report.concentration_by_symbol.items():
            if conc > self.thresholds['concentration_limit'] * 0.8:
                recommendations.append(f"Reduce concentration in {symbol} (currently {conc:.1f}%)")

        # Drawdown recommendations
        if report.drawdown_analysis:
            if report.drawdown_analysis.current_drawdown < -7:
                recommendations.append("Consider reducing position sizes during drawdown")
            if report.drawdown_analysis.drawdown_duration_days > 10:
                recommendations.append("Extended drawdown period - review strategy performance")

        return recommendations

    def export_report(
        self,
        report: RiskReportData,
        format: ReportFormat = ReportFormat.JSON,
        filename: Optional[str] = None
    ) -> Path:
        """
        Export risk report to file.

        Args:
            report: Risk report data to export
            format: Output format
            filename: Optional custom filename

        Returns:
            Path to the exported file
        """
        if filename is None:
            filename = f"risk_report_{report.report_date.isoformat()}"

        output_path = self.output_dir / f"{filename}.{format.value}"

        if format == ReportFormat.JSON:
            self._export_json(report, output_path)
        elif format == ReportFormat.TEXT:
            self._export_text(report, output_path)
        else:
            # HTML and PDF require additional dependencies
            self.logger.warning(f"Format {format.value} not fully implemented, using JSON")
            output_path = self.output_dir / f"{filename}.json"
            self._export_json(report, output_path)

        self.logger.info(f"Risk report exported to {output_path}")
        return output_path

    def _export_json(self, report: RiskReportData, path: Path) -> None:
        """Export report as JSON."""
        data = asdict(report)
        # Convert non-serializable types
        data['report_date'] = report.report_date.isoformat()
        data['report_time'] = report.report_time.isoformat()
        data['overall_risk_level'] = report.overall_risk_level.value

        if data.get('var_results'):
            for var in data['var_results']:
                var['calculated_at'] = var['calculated_at'].isoformat()

        if data.get('drawdown_analysis') and data['drawdown_analysis'].get('max_drawdown_date'):
            data['drawdown_analysis']['max_drawdown_date'] = \
                data['drawdown_analysis']['max_drawdown_date'].isoformat()

        if data.get('limit_checks'):
            for check in data['limit_checks']:
                check['risk_level'] = check['risk_level'].value

        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def _export_text(self, report: RiskReportData, path: Path) -> None:
        """Export report as formatted text."""
        lines = [
            "=" * 80,
            f"SPYDER RISK REPORT - {report.report_date}",
            "=" * 80,
            f"Generated: {report.report_time}",
            f"Account: {report.account_id}",
            f"Portfolio Value: ${report.portfolio_value:,.2f}",
            f"Overall Risk Level: {report.overall_risk_level.value.upper()}",
            f"Risk Score: {report.risk_score:.1f}/100",
            "",
            "-" * 40,
            "VALUE AT RISK",
            "-" * 40,
        ]

        for var in report.var_results:
            lines.append(
                f"  {var.confidence_level*100:.0f}% VaR: ${var.var_absolute:,.2f} "
                f"({var.var_percent:.2f}%)"
            )

        if report.greeks_exposure:
            ge = report.greeks_exposure
            lines.extend([
                "",
                "-" * 40,
                "GREEKS EXPOSURE",
                "-" * 40,
                f"  Delta: {ge.total_delta:,.2f} (${ge.delta_dollars:,.2f})",
                f"  Gamma: {ge.total_gamma:,.4f}",
                f"  Theta: {ge.total_theta:,.2f}/day",
                f"  Vega: {ge.total_vega:,.2f}",
            ])

        if report.alerts:
            lines.extend([
                "",
                "-" * 40,
                "ALERTS",
                "-" * 40,
            ])
            for alert in report.alerts:
                lines.append(f"  ! {alert}")

        if report.recommendations:
            lines.extend([
                "",
                "-" * 40,
                "RECOMMENDATIONS",
                "-" * 40,
            ])
            for rec in report.recommendations:
                lines.append(f"  * {rec}")

        lines.append("\n" + "=" * 80)

        with open(path, 'w') as f:
            f.write('\n'.join(lines))


# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    "RiskReportGenerator",
    "RiskReportData",
    "VaRResult",
    "GreeksExposure",
    "DrawdownAnalysis",
    "RiskLimitStatus",
    "RiskLevel",
    "ReportFormat",
]
