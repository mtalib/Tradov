#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderK_Reports
Module: SpyderK04_ExecutionAnalytics.py
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
from datetime import datetime, timedelta, date, timezone
from typing import Any
from dataclasses import dataclass, asdict
from enum import Enum
import json
from collections import defaultdict, Counter

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderH_Storage.SpyderH01_DataAccessLayer import get_data_access_layer

INTRADAY_BINS = {
    'pre_market': ('04:00', '09:30'),
    'open': ('09:30', '10:00'),
    'morning': ('10:00', '12:00'),
    'lunch': ('12:00', '13:00'),
    'afternoon': ('13:00', '15:30'),
    'close': ('15:30', '16:00'),
    'after_hours': ('16:00', '20:00')
}

# Slippage thresholds (in basis points)
SLIPPAGE_THRESHOLDS = {
    'excellent': 5,    # < 5 bps
    'good': 10,        # 5-10 bps
    'acceptable': 20,  # 10-20 bps
    'poor': 50,        # 20-50 bps
    'unacceptable': float('inf')  # > 50 bps
}

# Market impact thresholds
MARKET_IMPACT_THRESHOLDS = {
    'minimal': 0.001,     # < 0.1%
    'low': 0.005,         # 0.1-0.5%
    'moderate': 0.01,     # 0.5-1%
    'high': 0.02,         # 1-2%
    'severe': float('inf') # > 2%
}

# ==============================================================================
# ENUMS
# ==============================================================================
class ExecutionQuality(Enum):
    """Execution quality ratings"""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    UNACCEPTABLE = "unacceptable"

class OrderType(Enum):
    """Order types for analysis"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ExecutionMetrics:
    """Metrics for a single execution"""
    order_id: str
    symbol: str
    order_type: OrderType
    side: str  # 'buy' or 'sell'
    quantity: int
    expected_price: float
    executed_price: float
    order_time: datetime
    execution_time: datetime
    slippage_bps: float
    slippage_dollars: float
    market_impact: float
    execution_quality: ExecutionQuality
    time_to_fill_seconds: float
    partial_fills: int
    venue: str | None = None

@dataclass
class ExecutionSummary:
    """Summary statistics for execution analysis"""
    total_trades: int
    avg_slippage_bps: float
    median_slippage_bps: float
    std_slippage_bps: float
    total_slippage_cost: float
    avg_time_to_fill: float
    quality_distribution: dict[ExecutionQuality, int]
    best_execution_time: str
    worst_execution_time: str
    market_impact_avg: float
    partial_fill_rate: float

@dataclass
class TimeWindowAnalysis:
    """Analysis for specific time windows"""
    window_name: str
    trade_count: int
    avg_slippage: float
    avg_market_impact: float
    avg_fill_time: float
    quality_score: float
    recommendation: str

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class ExecutionAnalytics:
    """
    Trade execution quality analysis and reporting engine.

    This class analyzes trade execution quality by measuring slippage, market impact,
    fill times, and other execution metrics. It identifies patterns in execution
    quality across different time periods and provides actionable recommendations.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        dal: Data access layer for retrieving execution data
        metrics_cache: Cache for computed metrics

    Example:
        >>> analytics = ExecutionAnalytics()
        >>> report = analytics.generate_execution_report(date(2025, 1, 7))
        >>> analytics.export_report(report, 'execution_report.pdf')
    """

    def __init__(self):
        """Initialize the execution analytics module."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.dal = get_data_access_layer()
        self.metrics_cache: dict[str, ExecutionMetrics] = {}
        self.time_window_cache: dict[str, TimeWindowAnalysis] = {}

        self.logger.info("ExecutionAnalytics initialized")

    # ==========================================================================
    # CORE ANALYSIS METHODS
    # ==========================================================================
    def analyze_execution(self, order_data: dict[str, Any]) -> ExecutionMetrics:
        """
        Analyze a single order execution.

        Args:
            order_data: Dictionary containing order and execution details

        Returns:
            ExecutionMetrics object with analysis results
        """
        try:
            # Extract order details
            order_id = order_data['order_id']
            symbol = order_data['symbol']
            order_type = OrderType(order_data['order_type'])
            side = order_data['side']
            quantity = order_data['quantity']

            # Price analysis
            expected_price = order_data['expected_price']
            executed_price = order_data['executed_price']

            # Calculate slippage
            if side == 'buy':
                slippage_dollars = (executed_price - expected_price) * quantity
                slippage_pct = (executed_price - expected_price) / expected_price
            else:  # sell
                slippage_dollars = (expected_price - executed_price) * quantity
                slippage_pct = (expected_price - executed_price) / expected_price

            slippage_bps = slippage_pct * 10000  # Convert to basis points

            # Time analysis
            order_time = pd.to_datetime(order_data['order_time'])
            execution_time = pd.to_datetime(order_data['execution_time'])
            time_to_fill = (execution_time - order_time).total_seconds()

            # Market impact calculation
            market_impact = self._calculate_market_impact(order_data)

            # Quality assessment
            quality = self._assess_execution_quality(slippage_bps, time_to_fill, market_impact)

            # Create metrics object
            metrics = ExecutionMetrics(
                order_id=order_id,
                symbol=symbol,
                order_type=order_type,
                side=side,
                quantity=quantity,
                expected_price=expected_price,
                executed_price=executed_price,
                order_time=order_time,
                execution_time=execution_time,
                slippage_bps=slippage_bps,
                slippage_dollars=slippage_dollars,
                market_impact=market_impact,
                execution_quality=quality,
                time_to_fill_seconds=time_to_fill,
                partial_fills=order_data.get('partial_fills', 0),
                venue=order_data.get('venue')
            )

            # Cache the metrics
            self.metrics_cache[order_id] = metrics

            return metrics

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'analyze_execution',
                'order_id': order_data.get('order_id', 'unknown')
            })
            raise

    def analyze_slippage_patterns(self, start_date: date, end_date: date) -> pd.DataFrame:
        """
        Analyze slippage patterns over a date range.

        Args:
            start_date: Analysis start date
            end_date: Analysis end date

        Returns:
            DataFrame with slippage analysis
        """
        try:
            # Retrieve execution data
            executions = self.dal.get_executions(start_date, end_date)

            # Analyze each execution
            metrics_list = []
            for exec_data in executions:
                metrics = self.analyze_execution(exec_data)
                metrics_list.append(asdict(metrics))

            # Create DataFrame for analysis
            df = pd.DataFrame(metrics_list)

            if df.empty:
                self.logger.warning("No execution data found for analysis")
                return pd.DataFrame()

            # Add time-based features
            df['hour'] = df['execution_time'].dt.hour
            df['minute'] = df['execution_time'].dt.minute
            df['day_of_week'] = df['execution_time'].dt.dayofweek
            df['time_window'] = df.apply(self._get_time_window, axis=1)

            # Calculate patterns
            patterns = df.groupby(['time_window', 'order_type', 'side']).agg({
                'slippage_bps': ['mean', 'median', 'std', 'count'],
                'slippage_dollars': 'sum',
                'time_to_fill_seconds': 'mean',
                'market_impact': 'mean'
            }).round(2)

            return patterns

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'analyze_slippage_patterns',
                'date_range': f"{start_date} to {end_date}"
            })
            return pd.DataFrame()

    def identify_best_worst_execution_times(self, lookback_days: int = 30) -> dict[str, Any]:
        """
        Identify best and worst times for execution.

        Args:
            lookback_days: Number of days to analyze

        Returns:
            Dictionary with best/worst execution times and recommendations
        """
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=lookback_days)

            # Get slippage patterns
            patterns = self.analyze_slippage_patterns(start_date, end_date)

            if patterns.empty:
                return {
                    'best_times': [],
                    'worst_times': [],
                    'recommendations': ["Insufficient data for analysis"]
                }

            # Analyze by time window
            time_analysis = {}
            for window in INTRADAY_BINS:
                window_data = patterns.xs(window, level='time_window', drop_level=False)
                if not window_data.empty:
                    avg_slippage = window_data[('slippage_bps', 'mean')].mean()
                    avg_impact = window_data[('market_impact', 'mean')].mean()
                    avg_fill_time = window_data[('time_to_fill_seconds', 'mean')].mean()
                    trade_count = window_data[('slippage_bps', 'count')].sum()

                    # Calculate quality score (lower is better)
                    quality_score = (
                        avg_slippage * 0.5 +
                        avg_impact * 1000 * 0.3 +
                        avg_fill_time * 0.2
                    )

                    time_analysis[window] = TimeWindowAnalysis(
                        window_name=window,
                        trade_count=int(trade_count),
                        avg_slippage=avg_slippage,
                        avg_market_impact=avg_impact,
                        avg_fill_time=avg_fill_time,
                        quality_score=quality_score,
                        recommendation=self._generate_time_recommendation(
                            window, avg_slippage, avg_impact, trade_count
                        )
                    )

            # Sort by quality score
            sorted_windows = sorted(
                time_analysis.items(),
                key=lambda x: x[1].quality_score
            )

            # Identify best and worst times
            best_times = sorted_windows[:3]
            worst_times = sorted_windows[-3:]

            # Generate overall recommendations
            recommendations = self._generate_execution_recommendations(time_analysis)

            return {
                'best_times': [(k, asdict(v)) for k, v in best_times],
                'worst_times': [(k, asdict(v)) for k, v in worst_times],
                'time_analysis': {k: asdict(v) for k, v in time_analysis.items()},
                'recommendations': recommendations
            }

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'identify_best_worst_execution_times',
                'lookback_days': lookback_days
            })
            return {}

    def calculate_market_impact(self, executions: list[dict[str, Any]]) -> pd.DataFrame:
        """
        Calculate market impact for a list of executions.

        Args:
            executions: List of execution data dictionaries

        Returns:
            DataFrame with market impact analysis
        """
        try:
            impact_data = []

            for exec_data in executions:
                impact = self._calculate_market_impact(exec_data)

                impact_data.append({
                    'order_id': exec_data['order_id'],
                    'symbol': exec_data['symbol'],
                    'quantity': exec_data['quantity'],
                    'notional_value': exec_data['quantity'] * exec_data['executed_price'],
                    'market_impact_pct': impact * 100,
                    'impact_category': self._categorize_market_impact(impact),
                    'execution_time': exec_data['execution_time']
                })

            df = pd.DataFrame(impact_data)

            # Add summary statistics
            if not df.empty:
                df['cumulative_impact'] = df['market_impact_pct'].cumsum()
                df['rolling_avg_impact'] = df['market_impact_pct'].rolling(window=20).mean()

            return df

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'calculate_market_impact',
                'execution_count': len(executions)
            })
            return pd.DataFrame()

    # ==========================================================================
    # REPORTING METHODS
    # ==========================================================================
    def generate_execution_report(self, report_date: date,
                                lookback_days: int = 30) -> dict[str, Any]:
        """
        Generate comprehensive execution quality report.

        Args:
            report_date: Date for the report
            lookback_days: Number of days to analyze

        Returns:
            Dictionary containing complete execution analysis report
        """
        try:
            start_date = report_date - timedelta(days=lookback_days)

            # Get execution data
            executions = self.dal.get_executions(start_date, report_date)

            if not executions:
                return self._generate_empty_report(report_date)

            # Analyze all executions
            metrics_list = []
            for exec_data in executions:
                metrics = self.analyze_execution(exec_data)
                metrics_list.append(metrics)

            # Generate summary statistics
            summary = self._generate_execution_summary(metrics_list)

            # Time-based analysis
            time_analysis = self.identify_best_worst_execution_times(lookback_days)

            # Slippage patterns
            slippage_patterns = self.analyze_slippage_patterns(start_date, report_date)

            # Market impact analysis
            impact_analysis = self.calculate_market_impact(executions)

            # Generate visualizations
            charts = self._generate_execution_charts(metrics_list, impact_analysis)

            # Compile report
            report = {
                'report_date': report_date.isoformat(),
                'period': f"{start_date.isoformat()} to {report_date.isoformat()}",
                'summary': asdict(summary),
                'time_analysis': time_analysis,
                'slippage_patterns': slippage_patterns.to_dict() if not slippage_patterns.empty else {},
                'market_impact': {
                    'average': impact_analysis['market_impact_pct'].mean() if not impact_analysis.empty else 0,
                    'total': impact_analysis['market_impact_pct'].sum() if not impact_analysis.empty else 0,
                    'by_category': impact_analysis['impact_category'].value_counts().to_dict() if not impact_analysis.empty else {}
                },
                'charts': charts,
                'recommendations': self._generate_comprehensive_recommendations(
                    summary, time_analysis, impact_analysis
                ),
                'generated_at': datetime.now(timezone.utc).isoformat()
            }

            self.logger.info("Generated execution report for %s", report_date)
            return report

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'generate_execution_report',
                'report_date': report_date
            })
            return self._generate_empty_report(report_date)

    def export_report(self, report: dict[str, Any], output_path: str,
                     format: str = 'html') -> bool:
        """
        Export execution report to file.

        Args:
            report: Report data dictionary
            output_path: Path for output file
            format: Output format ('html', 'pdf', 'json')

        Returns:
            True if successful, False otherwise
        """
        try:
            if format == 'html':
                return self._export_html_report(report, output_path)
            elif format == 'pdf':
                return self._export_pdf_report(report, output_path)
            elif format == 'json':
                return self._export_json_report(report, output_path)
            else:
                self.logger.error("Unsupported export format: %s", format)
                return False

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'export_report',
                'format': format,
                'output_path': output_path
            })
            return False

    # ==========================================================================
    # PRIVATE HELPER METHODS
    # ==========================================================================
    def _calculate_market_impact(self, order_data: dict[str, Any]) -> float:
        """Calculate market impact of an order."""
        try:
            # Get pre and post trade prices
            pre_price = order_data.get('pre_trade_mid', order_data['expected_price'])
            post_price = order_data.get('post_trade_mid', order_data['executed_price'])

            # Calculate temporary and permanent impact
            if order_data['side'] == 'buy':
                temp_impact = (order_data['executed_price'] - pre_price) / pre_price
                perm_impact = (post_price - pre_price) / pre_price
            else:  # sell
                temp_impact = (pre_price - order_data['executed_price']) / pre_price
                perm_impact = (pre_price - post_price) / pre_price

            # Total impact (weighted average)
            total_impact = temp_impact * 0.7 + perm_impact * 0.3

            return max(0, total_impact)  # Ensure non-negative

        except Exception:
            return 0.0

    def _assess_execution_quality(self, slippage_bps: float,
                                fill_time: float, market_impact: float) -> ExecutionQuality:
        """Assess overall execution quality."""
        # Score based on multiple factors
        score = 0

        # Slippage scoring
        for quality, threshold in SLIPPAGE_THRESHOLDS.items():
            if abs(slippage_bps) < threshold:
                if quality == 'excellent':
                    score += 40
                elif quality == 'good':
                    score += 30
                elif quality == 'acceptable':
                    score += 20
                elif quality == 'poor':
                    score += 10
                break

        # Fill time scoring (assumes seconds)
        if fill_time < 1:
            score += 30
        elif fill_time < 5:
            score += 25
        elif fill_time < 30:
            score += 20
        elif fill_time < 60:
            score += 10
        else:
            score += 5

        # Market impact scoring
        for category, threshold in MARKET_IMPACT_THRESHOLDS.items():
            if market_impact < threshold:
                if category == 'minimal':
                    score += 30
                elif category == 'low':
                    score += 25
                elif category == 'moderate':
                    score += 15
                elif category == 'high':
                    score += 5
                break

        # Map score to quality
        if score >= 90:
            return ExecutionQuality.EXCELLENT
        elif score >= 75:
            return ExecutionQuality.GOOD
        elif score >= 50:
            return ExecutionQuality.ACCEPTABLE
        elif score >= 25:
            return ExecutionQuality.POOR
        else:
            return ExecutionQuality.UNACCEPTABLE

    def _get_time_window(self, row: pd.Series) -> str:
        """Get time window for a given execution."""
        exec_time = row['execution_time'].strftime('%H:%M')

        for window, (start, end) in INTRADAY_BINS.items():
            if start <= exec_time < end:
                return window

        return 'other'

    def _categorize_market_impact(self, impact: float) -> str:
        """Categorize market impact level."""
        for category, threshold in MARKET_IMPACT_THRESHOLDS.items():
            if impact < threshold:
                return category
        return 'severe'

    def _generate_execution_summary(self, metrics_list: list[ExecutionMetrics]) -> ExecutionSummary:
        """Generate summary statistics from execution metrics."""
        if not metrics_list:
            return ExecutionSummary(
                total_trades=0,
                avg_slippage_bps=0,
                median_slippage_bps=0,
                std_slippage_bps=0,
                total_slippage_cost=0,
                avg_time_to_fill=0,
                quality_distribution={},
                best_execution_time='',
                worst_execution_time='',
                market_impact_avg=0,
                partial_fill_rate=0
            )

        slippages = [m.slippage_bps for m in metrics_list]
        fill_times = [m.time_to_fill_seconds for m in metrics_list]

        # Quality distribution
        quality_dist = Counter(m.execution_quality for m in metrics_list)

        # Find best/worst times
        time_groups = defaultdict(list)
        for m in metrics_list:
            window = self._get_time_window(pd.Series({'execution_time': m.execution_time}))
            time_groups[window].append(m.slippage_bps)

        avg_by_time = {k: np.mean(v) for k, v in time_groups.items()}
        best_time = min(avg_by_time, key=avg_by_time.get) if avg_by_time else ''
        worst_time = max(avg_by_time, key=avg_by_time.get) if avg_by_time else ''

        return ExecutionSummary(
            total_trades=len(metrics_list),
            avg_slippage_bps=np.mean(slippages),
            median_slippage_bps=np.median(slippages),
            std_slippage_bps=np.std(slippages),
            total_slippage_cost=sum(m.slippage_dollars for m in metrics_list),
            avg_time_to_fill=np.mean(fill_times),
            quality_distribution={q.value: count for q, count in quality_dist.items()},
            best_execution_time=best_time,
            worst_execution_time=worst_time,
            market_impact_avg=np.mean([m.market_impact for m in metrics_list]),
            partial_fill_rate=sum(1 for m in metrics_list if m.partial_fills > 0) / len(metrics_list)
        )

    def _generate_time_recommendation(self, window: str, avg_slippage: float,
                                    avg_impact: float, trade_count: int) -> str:
        """Generate recommendation for a time window."""
        if trade_count < 10:
            return f"Limited data ({trade_count} trades) - monitor further"

        if avg_slippage < SLIPPAGE_THRESHOLDS['good']:
            if avg_impact < MARKET_IMPACT_THRESHOLDS['low']:
                return "Excellent execution window - prioritize trading"
            else:
                return "Good slippage but watch market impact"
        elif avg_slippage < SLIPPAGE_THRESHOLDS['acceptable']:
            return "Acceptable execution - consider for non-urgent trades"
        else:
            return "Poor execution quality - avoid if possible"

    def _generate_execution_recommendations(self,
                                          time_analysis: dict[str, TimeWindowAnalysis]) -> list[str]:
        """Generate overall execution recommendations."""
        recommendations = []

        # Find best overall window
        if time_analysis:
            best_window = min(time_analysis.values(), key=lambda x: x.quality_score)
            worst_window = max(time_analysis.values(), key=lambda x: x.quality_score)

            recommendations.append(
                f"Prioritize executions during {best_window.window_name} "
                f"(avg slippage: {best_window.avg_slippage:.1f} bps)"
            )

            if worst_window.avg_slippage > SLIPPAGE_THRESHOLDS['acceptable']:
                recommendations.append(
                    f"Avoid executions during {worst_window.window_name} "
                    f"(avg slippage: {worst_window.avg_slippage:.1f} bps)"
                )

        # Check for high market impact periods
        high_impact_windows = [
            (k, v) for k, v in time_analysis.items()
            if v.avg_market_impact > MARKET_IMPACT_THRESHOLDS['moderate']
        ]

        if high_impact_windows:
            windows = ', '.join([w[0] for w in high_impact_windows])
            recommendations.append(
                f"Consider splitting large orders during: {windows} (high market impact)"
            )

        # Fill time recommendations
        slow_fill_windows = [
            (k, v) for k, v in time_analysis.items()
            if v.avg_fill_time > 30  # seconds
        ]

        if slow_fill_windows:
            recommendations.append(
                "Consider using more aggressive pricing during slow fill periods"
            )

        return recommendations

    def _generate_comprehensive_recommendations(self, summary: ExecutionSummary,
                                              time_analysis: dict[str, Any],
                                              impact_df: pd.DataFrame) -> list[str]:
        """Generate comprehensive recommendations based on all analyses."""
        recommendations = []

        # Overall execution quality
        if summary.avg_slippage_bps > SLIPPAGE_THRESHOLDS['acceptable']:
            recommendations.append(
                f"High average slippage ({summary.avg_slippage_bps:.1f} bps) - "
                "review order types and timing strategies"
            )

        # Partial fills
        if summary.partial_fill_rate > 0.2:
            recommendations.append(
                f"High partial fill rate ({summary.partial_fill_rate:.1%}) - "
                "consider adjusting order sizes or using iceberg orders"
            )

        # Time-based recommendations
        if 'recommendations' in time_analysis:
            recommendations.extend(time_analysis['recommendations'][:3])

        # Market impact
        if not impact_df.empty and impact_df['market_impact_pct'].mean() > 0.5:
            recommendations.append(
                "Consider implementing pre-trade analytics to estimate market impact"
            )

        # Quality distribution
        poor_quality = (
            summary.quality_distribution.get('poor', 0) +
            summary.quality_distribution.get('unacceptable', 0)
        )

        if summary.total_trades > 0 and poor_quality / summary.total_trades > 0.2:
            recommendations.append(
                "Over 20% of executions rated as poor quality - urgent review needed"
            )

        return recommendations

    def _generate_execution_charts(self, metrics_list: list[ExecutionMetrics],
                                 impact_df: pd.DataFrame) -> dict[str, Any]:
        """Generate charts for execution analysis."""
        charts = {}

        try:
            # Slippage distribution chart
            slippages = [m.slippage_bps for m in metrics_list]

            fig_slippage = go.Figure()
            fig_slippage.add_trace(go.Histogram(
                x=slippages,
                nbinsx=50,
                name='Slippage Distribution',
                marker_color='blue'
            ))

            fig_slippage.update_layout(
                title='Slippage Distribution (Basis Points)',
                xaxis_title='Slippage (bps)',
                yaxis_title='Count',
                showlegend=False
            )

            charts['slippage_distribution'] = fig_slippage.to_json()

            # Time window analysis chart
            time_data = defaultdict(list)
            for m in metrics_list:
                window = self._get_time_window(pd.Series({'execution_time': m.execution_time}))
                time_data[window].append(m.slippage_bps)

            windows = list(INTRADAY_BINS.keys())
            avg_slippages = [np.mean(time_data.get(w, [0])) for w in windows]
            counts = [len(time_data.get(w, [])) for w in windows]

            fig_time = make_subplots(
                rows=1, cols=2,
                subplot_titles=('Average Slippage by Time', 'Trade Count by Time')
            )

            fig_time.add_trace(
                go.Bar(x=windows, y=avg_slippages, name='Avg Slippage'),
                row=1, col=1
            )

            fig_time.add_trace(
                go.Bar(x=windows, y=counts, name='Trade Count'),
                row=1, col=2
            )

            fig_time.update_layout(
                title='Execution Analysis by Time Window',
                showlegend=False
            )

            charts['time_analysis'] = fig_time.to_json()

            # Market impact over time
            if not impact_df.empty:
                fig_impact = go.Figure()
                fig_impact.add_trace(go.Scatter(
                    x=impact_df.index,
                    y=impact_df['market_impact_pct'],
                    mode='lines+markers',
                    name='Market Impact',
                    line=dict(color='red', width=2)
                ))

                fig_impact.add_trace(go.Scatter(
                    x=impact_df.index,
                    y=impact_df['rolling_avg_impact'],
                    mode='lines',
                    name='Rolling Average',
                    line=dict(color='orange', dash='dash')
                ))

                fig_impact.update_layout(
                    title='Market Impact Over Time',
                    xaxis_title='Trade Number',
                    yaxis_title='Market Impact (%)',
                    hovermode='x unified'
                )

                charts['market_impact'] = fig_impact.to_json()

            # Quality distribution pie chart
            quality_counts = Counter(m.execution_quality.value for m in metrics_list)

            fig_quality = go.Figure(data=[go.Pie(
                labels=list(quality_counts.keys()),
                values=list(quality_counts.values()),
                hole=0.3,
                marker_colors=['green', 'lightgreen', 'yellow', 'orange', 'red']
            )])

            fig_quality.update_layout(
                title='Execution Quality Distribution'
            )

            charts['quality_distribution'] = fig_quality.to_json()

        except Exception as e:
            self.logger.error("Error generating charts: %s", e)

        return charts

    def _generate_empty_report(self, report_date: date) -> dict[str, Any]:
        """Generate empty report structure."""
        return {
            'report_date': report_date.isoformat(),
            'summary': asdict(ExecutionSummary(
                total_trades=0,
                avg_slippage_bps=0,
                median_slippage_bps=0,
                std_slippage_bps=0,
                total_slippage_cost=0,
                avg_time_to_fill=0,
                quality_distribution={},
                best_execution_time='',
                worst_execution_time='',
                market_impact_avg=0,
                partial_fill_rate=0
            )),
            'time_analysis': {},
            'slippage_patterns': {},
            'market_impact': {},
            'charts': {},
            'recommendations': ["No execution data available for analysis"],
            'generated_at': datetime.now(timezone.utc).isoformat()
        }

    def _export_html_report(self, report: dict[str, Any], output_path: str) -> bool:
        """Export report as HTML."""
        try:
            # HTML template
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Execution Quality Report - {report_date}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    h1, h2, h3 {{ color: #333; }}
                    .summary {{ background: #f0f0f0; padding: 15px; border-radius: 5px; }}
                    .metric {{ margin: 10px 0; }}
                    .recommendation {{ background: #e8f4f8; padding: 10px; margin: 5px 0; border-left: 3px solid #0066cc; }}
                    table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    .chart {{ margin: 20px 0; }}
                </style>
            </head>
            <body>
                <h1>Execution Quality Report</h1>
                <p>Report Date: {report_date}</p>
                <p>Analysis Period: {period}</p>

                <div class="summary">
                    <h2>Executive Summary</h2>
                    <div class="metric">Total Trades: {total_trades}</div>
                    <div class="metric">Average Slippage: {avg_slippage:.2f} bps</div>
                    <div class="metric">Total Slippage Cost: ${slippage_cost:,.2f}</div>
                    <div class="metric">Average Fill Time: {avg_fill_time:.1f} seconds</div>
                </div>

                <h2>Recommendations</h2>
                {recommendations_html}

                <h2>Best Execution Times</h2>
                {best_times_html}

                <h2>Worst Execution Times</h2>
                {worst_times_html}

                <div class="chart">
                    <h3>Charts</h3>
                    <p>Interactive charts available in the full dashboard</p>
                </div>
            </body>
            </html>
            """

            # Format recommendations
            recommendations_html = '\n'.join([
                f'<div class="recommendation">{rec}</div>'
                for rec in report.get('recommendations', [])
            ])

            # Format best times
            best_times = report.get('time_analysis', {}).get('best_times', [])
            best_times_html = self._format_time_table(best_times)

            # Format worst times
            worst_times = report.get('time_analysis', {}).get('worst_times', [])
            worst_times_html = self._format_time_table(worst_times)

            # Fill template
            html_content = html_template.format(
                report_date=report['report_date'],
                period=report.get('period', 'N/A'),
                total_trades=report['summary']['total_trades'],
                avg_slippage=report['summary']['avg_slippage_bps'],
                slippage_cost=report['summary']['total_slippage_cost'],
                avg_fill_time=report['summary']['avg_time_to_fill'],
                recommendations_html=recommendations_html,
                best_times_html=best_times_html,
                worst_times_html=worst_times_html
            )

            # Write to file
            with open(output_path, 'w') as f:
                f.write(html_content)

            self.logger.info("HTML report exported to %s", output_path)
            return True

        except Exception as e:
            self.logger.error("Error exporting HTML report: %s", e)
            return False

    def _export_pdf_report(self, report: dict[str, Any], output_path: str) -> bool:
        """Export report as PDF (requires additional implementation)."""
        self.logger.warning("PDF export not yet implemented")
        return False

    def _export_json_report(self, report: dict[str, Any], output_path: str) -> bool:
        """Export report as JSON."""
        try:
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)

            self.logger.info("JSON report exported to %s", output_path)
            return True

        except Exception as e:
            self.logger.error("Error exporting JSON report: %s", e)
            return False

    def _format_time_table(self, time_data: list[tuple[str, dict]]) -> str:
        """Format time analysis data as HTML table."""
        if not time_data:
            return "<p>No data available</p>"

        html = """
        <table>
            <tr>
                <th>Time Window</th>
                <th>Trade Count</th>
                <th>Avg Slippage (bps)</th>
                <th>Avg Market Impact</th>
                <th>Quality Score</th>
                <th>Recommendation</th>
            </tr>
        """

        for window, data in time_data:
            html += f"""
            <tr>
                <td>{window}</td>
                <td>{data.get('trade_count', 0)}</td>
                <td>{data.get('avg_slippage', 0):.2f}</td>
                <td>{data.get('avg_market_impact', 0):.3f}</td>
                <td>{data.get('quality_score', 0):.2f}</td>
                <td>{data.get('recommendation', '')}</td>
            </tr>
            """

        html += "</table>"
        return html

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def get_execution_analytics() -> ExecutionAnalytics:
    """
    Get singleton instance of ExecutionAnalytics.

    Returns:
        ExecutionAnalytics instance
    """
    global _analytics_instance
    if _analytics_instance is None:
        _analytics_instance = ExecutionAnalytics()
    return _analytics_instance

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_analytics_instance: ExecutionAnalytics | None = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Example usage
    analytics = get_execution_analytics()

    # Generate report for today
    report = analytics.generate_execution_report(date.today())

    # Export as HTML
    analytics.export_report(report, "execution_report.html", format='html')

    # Print summary
