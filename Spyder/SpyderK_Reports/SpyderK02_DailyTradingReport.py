#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderK_Reports
Module: SpyderK02_DailyTradingReport.py
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
import os
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import io
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import seaborn as sns
from jinja2 import Template
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from fpdf import FPDF
import xlsxwriter

# quantstats: institutional-grade return analytics
try:
    import quantstats as qs
    HAS_QUANTSTATS = True
except ImportError:
    qs = None  # type: ignore[assignment]
    HAS_QUANTSTATS = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU15_PerformanceMetrics import PerformanceCalculator as PerformanceMetrics
from Spyder.SpyderH_Storage.SpyderH01_DataAccessLayer import get_data_access_layer
from Spyder.SpyderB_Broker.SpyderB03_PositionTracker import PositionTracker
from Spyder.SpyderE_Risk.SpyderE06_RiskMetrics import RiskMetricsCalculator
from Spyder.SpyderJ_Alerts.SpyderJ02_EmailNotifier import EmailNotifier

# Institutional Analytics
try:
    import empyrical
    HAS_EMPYRICAL = True
except ImportError:
    HAS_EMPYRICAL = False

REPORT_TEMPLATES_DIR = Path("templates/reports")
REPORT_OUTPUT_DIR = Path("reports/daily")
REPORT_FORMATS = ["pdf", "html", "excel", "json"]

# Report sections
REPORT_SECTIONS = [
    "executive_summary",
    "pnl_analysis",
    "position_summary",
    "strategy_performance",
    "risk_metrics",
    "execution_quality",
    "market_context",
    "alerts_violations"
]

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class DailyReportData:
    """Container for daily report data"""
    report_date: date
    account_id: str
    
    # P&L Metrics
    daily_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    commission_paid: float
    net_pnl: float
    
    # Position Summary
    total_positions: int
    open_positions: int
    closed_positions: int
    winning_trades: int
    losing_trades: int
    
    # Strategy Performance
    strategy_pnl: Dict[str, float] = field(default_factory=dict)
    strategy_trades: Dict[str, int] = field(default_factory=dict)
    strategy_win_rate: Dict[str, float] = field(default_factory=dict)
    
    # Risk Metrics
    portfolio_delta: float = 0.0
    portfolio_gamma: float = 0.0
    portfolio_theta: float = 0.0
    portfolio_vega: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    var_95: float = 0.0
    
    # Execution Quality
    avg_slippage: float = 0.0
    fill_rate: float = 0.0
    avg_fill_time: float = 0.0
    rejected_orders: int = 0
    
    # Market Context
    spy_return: float = 0.0
    vix_level: float = 0.0
    volume_ratio: float = 0.0
    market_regime: str = "normal"
    
    # Alerts
    risk_violations: List[str] = field(default_factory=list)
    system_alerts: List[str] = field(default_factory=list)
    
    # Institutional Metrics (empyrical-validated)
    institutional_metrics: Dict[str, float] = field(default_factory=dict)

@dataclass
class TradeDetail:
    """Individual trade details"""
    trade_id: str
    strategy: str
    symbol: str
    side: str
    quantity: int
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    commission: float
    trade_duration: timedelta
    max_profit: float
    max_loss: float

# ==============================================================================
# DAILY TRADING REPORT CLASS
# ==============================================================================
class DailyTradingReport:
    """
    Comprehensive daily trading report generator.
    
    This class generates detailed daily reports including:
    - P&L analysis with breakdown by strategy
    - Position summaries and Greeks exposure
    - Risk metrics and compliance checks
    - Execution quality statistics
    - Market context and regime analysis
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize daily trading report generator"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or {}
        
        # Data access
        self.dal = get_data_access_layer()
        self.performance_metrics = PerformanceMetrics()
        self.risk_calculator = RiskMetricsCalculator()
        
        # Report configuration
        self.output_dir = Path(self.config.get('output_dir', REPORT_OUTPUT_DIR))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.template_dir = Path(self.config.get('template_dir', REPORT_TEMPLATES_DIR))
        self.formats = self.config.get('formats', ['html', 'pdf'])
        
        # Email configuration
        self.email_enabled = self.config.get('email_enabled', True)
        self.email_recipients = self.config.get('email_recipients', [])
        self.email_notifier = EmailNotifier() if self.email_enabled else None
        
        # Visualization settings
        self.chart_theme = self.config.get('chart_theme', 'plotly_dark')
        self.color_scheme = {
            'profit': '#00ff00',
            'loss': '#ff0000',
            'neutral': '#808080',
            'primary': '#1f77b4',
            'secondary': '#ff7f0e'
        }
        
        self.logger.info("Daily Trading Report generator initialized")
    
    # ==========================================================================
    # REPORT GENERATION
    # ==========================================================================
    
    def generate_daily_report(self, report_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Generate comprehensive daily trading report.
        
        Args:
            report_date: Date for report (default: today)
            
        Returns:
            Dict containing report data and file paths
        """
        try:
            # Set report date
            report_date = report_date or date.today()
            self.logger.info(f"Generating daily report for {report_date}")
            
            # Collect report data
            report_data = self._collect_report_data(report_date)
            
            # Generate visualizations
            charts = self._create_visualizations(report_data)
            
            # Generate reports in requested formats
            output_files = {}
            
            if 'html' in self.formats:
                output_files['html'] = self._generate_html_report(report_data, charts)
            
            if 'pdf' in self.formats:
                output_files['pdf'] = self._generate_pdf_report(report_data, charts)
            
            if 'excel' in self.formats:
                output_files['excel'] = self._generate_excel_report(report_data)
            
            if 'json' in self.formats:
                output_files['json'] = self._generate_json_report(report_data)
            
            # Send email if enabled
            if self.email_enabled and self.email_recipients:
                self._send_email_report(report_data, output_files)
            
            # Archive report
            self._archive_report(report_date, report_data, output_files)
            
            self.logger.info(f"Daily report generated successfully: {output_files}")
            
            return {
                'status': 'success',
                'report_date': report_date,
                'data': asdict(report_data),
                'files': output_files
            }
            
        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            self.error_handler.handle_error(e, "DailyTradingReport")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _collect_report_data(self, report_date: date) -> DailyReportData:
        """Collect all data needed for daily report"""
        self.logger.info("Collecting report data...")
        
        # Initialize report data
        report_data = DailyReportData(
            report_date=report_date,
            account_id=self.config.get('account_id', 'DEFAULT')
        )
        
        # Get trades for the day
        trades = self._get_daily_trades(report_date)
        
        # Calculate P&L metrics
        pnl_metrics = self._calculate_pnl_metrics(trades)
        report_data.daily_pnl = pnl_metrics['total_pnl']
        report_data.realized_pnl = pnl_metrics['realized_pnl']
        report_data.unrealized_pnl = pnl_metrics['unrealized_pnl']
        report_data.commission_paid = pnl_metrics['commission']
        report_data.net_pnl = pnl_metrics['net_pnl']
        
        # Position summary
        positions = self._get_position_summary(report_date)
        report_data.total_positions = positions['total']
        report_data.open_positions = positions['open']
        report_data.closed_positions = positions['closed']
        report_data.winning_trades = positions['winners']
        report_data.losing_trades = positions['losers']
        
        # Strategy performance
        strategy_perf = self._analyze_strategy_performance(trades)
        report_data.strategy_pnl = strategy_perf['pnl']
        report_data.strategy_trades = strategy_perf['trades']
        report_data.strategy_win_rate = strategy_perf['win_rate']
        
        # Risk metrics
        risk_metrics = self._calculate_risk_metrics(report_date)
        report_data.portfolio_delta = risk_metrics['delta']
        report_data.portfolio_gamma = risk_metrics['gamma']
        report_data.portfolio_theta = risk_metrics['theta']
        report_data.portfolio_vega = risk_metrics['vega']
        report_data.max_drawdown = risk_metrics['max_drawdown']
        report_data.current_drawdown = risk_metrics['current_drawdown']
        report_data.var_95 = risk_metrics['var_95']
        
        # Execution quality
        exec_quality = self._analyze_execution_quality(trades)
        report_data.avg_slippage = exec_quality['avg_slippage']
        report_data.fill_rate = exec_quality['fill_rate']
        report_data.avg_fill_time = exec_quality['avg_fill_time']
        report_data.rejected_orders = exec_quality['rejected_orders']
        
        # Market context
        market_context = self._get_market_context(report_date)
        report_data.spy_return = market_context['spy_return']
        report_data.vix_level = market_context['vix_level']
        report_data.volume_ratio = market_context['volume_ratio']
        report_data.market_regime = market_context['regime']
        
        # Alerts and violations
        alerts = self._check_alerts_violations(report_date)
        report_data.risk_violations = alerts['risk_violations']
        report_data.system_alerts = alerts['system_alerts']
        
        # Institutional metrics (empyrical-validated)
        report_data.institutional_metrics = self._generate_institutional_metrics(report_date)
        
        return report_data
    
    # ==========================================================================
    # DATA COLLECTION METHODS
    # ==========================================================================
    
    def _get_daily_trades(self, report_date: date) -> List[TradeDetail]:
        """Get all trades executed on report date"""
        # Query trades from database
        trades_df = self.dal.query_trades(
            start_date=report_date,
            end_date=report_date
        )
        
        trades = []
        for _, row in trades_df.iterrows():
            trade = TradeDetail(
                trade_id=row['trade_id'],
                strategy=row['strategy'],
                symbol=row['symbol'],
                side=row['side'],
                quantity=row['quantity'],
                entry_price=row['entry_price'],
                exit_price=row.get('exit_price', 0),
                entry_time=row['entry_time'],
                exit_time=row.get('exit_time', row['entry_time']),
                pnl=row.get('pnl', 0),
                commission=row.get('commission', 0),
                trade_duration=timedelta(seconds=0),
                max_profit=row.get('max_profit', 0),
                max_loss=row.get('max_loss', 0)
            )
            trades.append(trade)
        
        return trades
    
    def _calculate_pnl_metrics(self, trades: List[TradeDetail]) -> Dict[str, float]:
        """Calculate P&L metrics from trades"""
        total_pnl = sum(trade.pnl for trade in trades)
        realized_pnl = sum(trade.pnl for trade in trades if trade.exit_price > 0)
        unrealized_pnl = sum(trade.pnl for trade in trades if trade.exit_price == 0)
        commission = sum(trade.commission for trade in trades)

        metrics = {
            'total_pnl': total_pnl,
            'realized_pnl': realized_pnl,
            'unrealized_pnl': unrealized_pnl,
            'commission': commission,
            'net_pnl': total_pnl - commission
        }

        # quantstats trade-level stats when returns series is available
        if HAS_QUANTSTATS and len(trades) >= 10:
            try:
                pnl_series = pd.Series([t.pnl for t in trades])
                # Normalise to fractional returns (avoid div-by-zero)
                avg_notional = pnl_series.abs().mean() or 1.0
                ret_series = pnl_series / avg_notional
                metrics['qs_win_rate'] = float(qs.stats.win_rate(ret_series))
                metrics['qs_avg_win'] = float(qs.stats.avg_win(ret_series))
                metrics['qs_avg_loss'] = float(qs.stats.avg_loss(ret_series))
                metrics['qs_payoff_ratio'] = float(qs.stats.payoff_ratio(ret_series))
                metrics['qs_profit_factor'] = float(qs.stats.profit_factor(ret_series))
            except Exception as _qs_err:
                self.logger.debug(f"quantstats daily metrics skipped: {_qs_err}")

        return metrics

    def _get_position_summary(self, report_date: date) -> Dict[str, int]:
        """Get position summary statistics"""
        # Query positions from database
        positions_df = self.dal.query_positions(date=report_date)
        
        total = len(positions_df)
        open_positions = len(positions_df[positions_df['status'] == 'OPEN'])
        closed_positions = len(positions_df[positions_df['status'] == 'CLOSED'])
        winners = len(positions_df[positions_df['pnl'] > 0])
        losers = len(positions_df[positions_df['pnl'] < 0])
        
        return {
            'total': total,
            'open': open_positions,
            'closed': closed_positions,
            'winners': winners,
            'losers': losers
        }
    
    def _analyze_strategy_performance(self, trades: List[TradeDetail]) -> Dict[str, Any]:
        """Analyze performance by strategy"""
        strategy_stats = defaultdict(lambda: {
            'pnl': 0.0,
            'trades': 0,
            'winners': 0,
            'losers': 0
        })
        
        for trade in trades:
            strategy = trade.strategy
            strategy_stats[strategy]['pnl'] += trade.pnl
            strategy_stats[strategy]['trades'] += 1
            
            if trade.pnl > 0:
                strategy_stats[strategy]['winners'] += 1
            elif trade.pnl < 0:
                strategy_stats[strategy]['losers'] += 1
        
        # Calculate win rates
        strategy_pnl = {}
        strategy_trades = {}
        strategy_win_rate = {}
        
        for strategy, stats in strategy_stats.items():
            strategy_pnl[strategy] = stats['pnl']
            strategy_trades[strategy] = stats['trades']
            
            if stats['trades'] > 0:
                strategy_win_rate[strategy] = stats['winners'] / stats['trades']
            else:
                strategy_win_rate[strategy] = 0.0
        
        return {
            'pnl': strategy_pnl,
            'trades': strategy_trades,
            'win_rate': strategy_win_rate
        }
    
    def _generate_institutional_metrics(self, report_date: date) -> Dict[str, Any]:
        """
        Generate empyrical-validated institutional performance metrics.
        
        Uses empyrical library for industry-standard risk/return calculations
        that match institutional reporting requirements.
        
        Args:
            report_date: Date for metrics computation.
            
        Returns:
            Dict of validated performance metrics.
        """
        metrics = {'source': 'empyrical', 'available': HAS_EMPYRICAL}
        
        if not HAS_EMPYRICAL:
            return metrics
        
        try:
            # Get historical returns from DAL
            returns_data = self.dal.get_returns(
                end_date=report_date, lookback_days=252
            )
            
            if returns_data is None or len(returns_data) < 10:
                metrics['error'] = 'Insufficient return history'
                return metrics
            
            returns = pd.Series(returns_data) if not isinstance(returns_data, pd.Series) else returns_data
            
            # Rolling metrics (last 30 days)
            if len(returns) >= 30:
                recent = returns.iloc[-30:]
                metrics['rolling_30d_sharpe'] = float(empyrical.sharpe_ratio(recent, period='daily'))
                metrics['rolling_30d_sortino'] = float(empyrical.sortino_ratio(recent, period='daily'))
                metrics['rolling_30d_volatility'] = float(empyrical.annual_volatility(recent, period='daily'))
                metrics['rolling_30d_max_dd'] = float(empyrical.max_drawdown(recent))
            
            # Full period metrics
            metrics['annual_return'] = float(empyrical.annual_return(returns, period='daily'))
            metrics['annual_volatility'] = float(empyrical.annual_volatility(returns, period='daily'))
            metrics['sharpe_ratio'] = float(empyrical.sharpe_ratio(returns, period='daily'))
            metrics['sortino_ratio'] = float(empyrical.sortino_ratio(returns, period='daily'))
            metrics['calmar_ratio'] = float(empyrical.calmar_ratio(returns, period='daily'))
            metrics['omega_ratio'] = float(empyrical.omega_ratio(returns))
            metrics['max_drawdown'] = float(empyrical.max_drawdown(returns))
            metrics['stability'] = float(empyrical.stability_of_timeseries(returns))
            metrics['tail_ratio'] = float(empyrical.tail_ratio(returns))
            metrics['var_5'] = float(empyrical.value_at_risk(returns, cutoff=0.05))
            metrics['cvar_5'] = float(empyrical.conditional_value_at_risk(returns, cutoff=0.05))
            metrics['cumulative_return'] = float(empyrical.cum_returns_final(returns))
            
            self.logger.info(f"Institutional metrics generated: Sharpe={metrics['sharpe_ratio']:.3f}")
            
        except Exception as e:
            self.logger.error(f"Error generating institutional metrics: {e}")
            metrics['error'] = str(e)
        
        return metrics
    
    def _calculate_risk_metrics(self, report_date: date) -> Dict[str, float]:
        """Calculate portfolio risk metrics"""
        # Get current positions
        positions = self.dal.query_positions(
            date=report_date,
            status='OPEN'
        )
        
        # Calculate Greeks
        total_delta = positions['delta'].sum() if 'delta' in positions else 0
        total_gamma = positions['gamma'].sum() if 'gamma' in positions else 0
        total_theta = positions['theta'].sum() if 'theta' in positions else 0
        total_vega = positions['vega'].sum() if 'vega' in positions else 0
        
        # Get drawdown metrics
        equity_curve = self.dal.get_equity_curve(end_date=report_date)
        drawdown_analysis = self.risk_calculator.analyze_drawdowns(equity_curve)
        
        # Calculate VaR
        returns = self.dal.get_returns(end_date=report_date, lookback_days=252)
        var_95 = self.risk_calculator.calculate_var(returns, confidence=0.95)
        
        return {
            'delta': total_delta,
            'gamma': total_gamma,
            'theta': total_theta,
            'vega': total_vega,
            'max_drawdown': drawdown_analysis.max_drawdown,
            'current_drawdown': drawdown_analysis.current_drawdown,
            'var_95': var_95
        }
    
    def _analyze_execution_quality(self, trades: List[TradeDetail]) -> Dict[str, float]:
        """Analyze trade execution quality"""
        if not trades:
            return {
                'avg_slippage': 0.0,
                'fill_rate': 1.0,
                'avg_fill_time': 0.0,
                'rejected_orders': 0
            }
        
        # Get order execution data
        orders_df = self.dal.query_orders(date=trades[0].entry_time.date())
        
        # Calculate metrics
        slippages = []
        fill_times = []
        
        for _, order in orders_df.iterrows():
            if order['status'] == 'FILLED':
                # Calculate slippage (simplified)
                expected_price = order['limit_price'] if order['order_type'] == 'LIMIT' else order['submitted_price']
                actual_price = order['fill_price']
                slippage = abs(actual_price - expected_price)
                slippages.append(slippage)
                
                # Calculate fill time
                fill_time = (order['filled_time'] - order['submitted_time']).total_seconds()
                fill_times.append(fill_time)
        
        total_orders = len(orders_df)
        filled_orders = len(orders_df[orders_df['status'] == 'FILLED'])
        rejected_orders = len(orders_df[orders_df['status'] == 'REJECTED'])
        
        return {
            'avg_slippage': np.mean(slippages) if slippages else 0.0,
            'fill_rate': filled_orders / total_orders if total_orders > 0 else 1.0,
            'avg_fill_time': np.mean(fill_times) if fill_times else 0.0,
            'rejected_orders': rejected_orders
        }
    
    def _get_market_context(self, report_date: date) -> Dict[str, Any]:
        """Get market context for report date"""
        # Get market data
        market_data = self.dal.get_market_data(date=report_date, symbol='SPY')
        
        if market_data.empty:
            return {
                'spy_return': 0.0,
                'vix_level': 20.0,
                'volume_ratio': 1.0,
                'regime': 'normal'
            }
        
        # Calculate SPY return
        spy_return = (market_data['close'].iloc[-1] / market_data['open'].iloc[0] - 1) * 100
        
        # Get VIX level
        vix_data = self.dal.get_market_data(date=report_date, symbol='VIX')
        vix_level = vix_data['close'].iloc[-1] if not vix_data.empty else 20.0
        
        # Calculate volume ratio
        avg_volume = market_data['volume'].rolling(20).mean().iloc[-1]
        today_volume = market_data['volume'].iloc[-1]
        volume_ratio = today_volume / avg_volume if avg_volume > 0 else 1.0
        
        # Determine market regime
        if vix_level < 15:
            regime = 'low_volatility'
        elif vix_level > 30:
            regime = 'high_volatility'
        else:
            regime = 'normal'
        
        return {
            'spy_return': spy_return,
            'vix_level': vix_level,
            'volume_ratio': volume_ratio,
            'regime': regime
        }
    
    def _check_alerts_violations(self, report_date: date) -> Dict[str, List[str]]:
        """Check for risk violations and system alerts"""
        risk_violations = []
        system_alerts = []
        
        # Check risk limits
        risk_checks = self.dal.get_risk_violations(date=report_date)
        for _, violation in risk_checks.iterrows():
            risk_violations.append(
                f"{violation['rule']}: {violation['current_value']} exceeds limit {violation['limit']}"
            )
        
        # Check system alerts
        alerts = self.dal.get_system_alerts(date=report_date)
        for _, alert in alerts.iterrows():
            system_alerts.append(
                f"[{alert['severity']}] {alert['message']}"
            )
        
        return {
            'risk_violations': risk_violations,
            'system_alerts': system_alerts
        }
    
    # ==========================================================================
    # VISUALIZATION METHODS
    # ==========================================================================
    
    def _create_visualizations(self, report_data: DailyReportData) -> Dict[str, Any]:
        """Create all visualizations for the report"""
        charts = {}
        
        # P&L waterfall chart
        charts['pnl_waterfall'] = self._create_pnl_waterfall(report_data)
        
        # Strategy performance bar chart
        charts['strategy_performance'] = self._create_strategy_performance_chart(report_data)
        
        # Greeks exposure radar chart
        charts['greeks_radar'] = self._create_greeks_radar(report_data)
        
        # Intraday P&L curve
        charts['intraday_pnl'] = self._create_intraday_pnl_curve(report_data)
        
        # Win/loss distribution
        charts['win_loss_dist'] = self._create_win_loss_distribution(report_data)
        
        # Risk metrics gauge
        charts['risk_gauges'] = self._create_risk_gauges(report_data)
        
        return charts
    
    def _create_pnl_waterfall(self, report_data: DailyReportData) -> go.Figure:
        """Create P&L waterfall chart"""
        fig = go.Figure(go.Waterfall(
            name="P&L",
            orientation="v",
            measure=["relative", "relative", "relative", "relative", "total"],
            x=["Realized P&L", "Unrealized P&L", "Commission", "Other", "Net P&L"],
            textposition="outside",
            text=[f"${report_data.realized_pnl:,.0f}",
                  f"${report_data.unrealized_pnl:,.0f}",
                  f"-${report_data.commission_paid:,.0f}",
                  "$0",
                  f"${report_data.net_pnl:,.0f}"],
            y=[report_data.realized_pnl,
               report_data.unrealized_pnl,
               -report_data.commission_paid,
               0,
               report_data.net_pnl],
            connector={"line": {"color": "rgb(63, 63, 63)"}},
            increasing={"marker": {"color": self.color_scheme['profit']}},
            decreasing={"marker": {"color": self.color_scheme['loss']}}
        ))
        
        fig.update_layout(
            title="Daily P&L Breakdown",
            template=self.chart_theme,
            showlegend=False,
            height=400
        )
        
        return fig
    
    def _create_strategy_performance_chart(self, report_data: DailyReportData) -> go.Figure:
        """Create strategy performance comparison chart"""
        strategies = list(report_data.strategy_pnl.keys())
        pnl_values = list(report_data.strategy_pnl.values())
        trade_counts = [report_data.strategy_trades[s] for s in strategies]
        win_rates = [report_data.strategy_win_rate[s] * 100 for s in strategies]
        
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Strategy P&L', 'Win Rate %'),
            specs=[[{"secondary_y": True}, {"secondary_y": False}]]
        )
        
        # P&L bars
        colors = [self.color_scheme['profit'] if pnl > 0 else self.color_scheme['loss'] 
                  for pnl in pnl_values]
        
        fig.add_trace(
            go.Bar(x=strategies, y=pnl_values, name="P&L", marker_color=colors),
            row=1, col=1
        )
        
        # Trade count line
        fig.add_trace(
            go.Scatter(x=strategies, y=trade_counts, name="Trades", mode='lines+markers'),
            row=1, col=1, secondary_y=True
        )
        
        # Win rate bars
        fig.add_trace(
            go.Bar(x=strategies, y=win_rates, name="Win Rate %",
                   marker_color=self.color_scheme['primary']),
            row=1, col=2
        )
        
        fig.update_layout(
            title="Strategy Performance Analysis",
            template=self.chart_theme,
            showlegend=True,
            height=400
        )
        
        return fig
    
    def _create_greeks_radar(self, report_data: DailyReportData) -> go.Figure:
        """Create Greeks exposure radar chart"""
        categories = ['Delta', 'Gamma', 'Theta', 'Vega']
        values = [
            report_data.portfolio_delta,
            report_data.portfolio_gamma,
            report_data.portfolio_theta,
            report_data.portfolio_vega
        ]
        
        # Normalize values for better visualization
        max_val = max(abs(v) for v in values) if values else 1
        normalized_values = [v / max_val * 100 for v in values]
        
        fig = go.Figure(data=go.Scatterpolar(
            r=normalized_values,
            theta=categories,
            fill='toself',
            name='Greeks Exposure'
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[-100, 100]
                )),
            title="Portfolio Greeks Exposure (Normalized)",
            template=self.chart_theme,
            showlegend=False,
            height=400
        )
        
        return fig
    
    def _create_intraday_pnl_curve(self, report_data: DailyReportData) -> go.Figure:
        """Create intraday P&L curve"""
        # Get intraday P&L data
        intraday_data = self.dal.get_intraday_pnl(date=report_data.report_date)
        
        if intraday_data.empty:
            # Create dummy data if no real data
            times = pd.date_range(
                start=f"{report_data.report_date} 09:30:00",
                end=f"{report_data.report_date} 16:00:00",
                freq='5min'
            )
            pnl_values = [0] * len(times)
        else:
            times = intraday_data.index
            pnl_values = intraday_data['cumulative_pnl']
        
        fig = go.Figure()
        
        # Add P&L line
        fig.add_trace(go.Scatter(
            x=times,
            y=pnl_values,
            mode='lines',
            name='Cumulative P&L',
            line=dict(
                color=self.color_scheme['profit'] if pnl_values[-1] >= 0 
                      else self.color_scheme['loss'],
                width=2
            )
        ))
        
        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        
        # Add annotations for key events
        # (Would add actual trade markers here)
        
        fig.update_layout(
            title="Intraday P&L Curve",
            xaxis_title="Time",
            yaxis_title="Cumulative P&L ($)",
            template=self.chart_theme,
            showlegend=True,
            height=400
        )
        
        return fig
    
    def _create_win_loss_distribution(self, report_data: DailyReportData) -> go.Figure:
        """Create win/loss distribution histogram"""
        # Get individual trade P&Ls
        trades = self._get_daily_trades(report_data.report_date)
        trade_pnls = [trade.pnl for trade in trades if trade.pnl != 0]
        
        if not trade_pnls:
            trade_pnls = [0]  # Dummy data
        
        fig = go.Figure()
        
        # Create histogram
        fig.add_trace(go.Histogram(
            x=trade_pnls,
            nbinsx=20,
            name='Trade P&L Distribution',
            marker_color=self.color_scheme['primary']
        ))
        
        # Add mean line
        mean_pnl = np.mean(trade_pnls)
        fig.add_vline(x=mean_pnl, line_dash="dash", line_color="yellow",
                      annotation_text=f"Mean: ${mean_pnl:.0f}")
        
        # Add zero line
        fig.add_vline(x=0, line_dash="solid", line_color="gray")
        
        fig.update_layout(
            title="Trade P&L Distribution",
            xaxis_title="P&L ($)",
            yaxis_title="Frequency",
            template=self.chart_theme,
            showlegend=False,
            height=400
        )
        
        return fig
    
    def _create_risk_gauges(self, report_data: DailyReportData) -> go.Figure:
        """Create risk metrics gauge charts"""
        fig = make_subplots(
            rows=1, cols=3,
            specs=[[{'type': 'indicator'}, {'type': 'indicator'}, {'type': 'indicator'}]],
            subplot_titles=('Drawdown', 'VaR Utilization', 'Win Rate')
        )
        
        # Drawdown gauge
        fig.add_trace(go.Indicator(
            mode="gauge+number+delta",
            value=abs(report_data.current_drawdown) * 100,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Drawdown %"},
            delta={'reference': abs(report_data.max_drawdown) * 100},
            gauge={
                'axis': {'range': [None, 20]},
                'bar': {'color': "darkred"},
                'steps': [
                    {'range': [0, 5], 'color': "lightgreen"},
                    {'range': [5, 10], 'color': "yellow"},
                    {'range': [10, 20], 'color': "red"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 15
                }
            }
        ), row=1, col=1)
        
        # VaR utilization gauge
        var_utilization = (abs(report_data.daily_pnl) / report_data.var_95 * 100) if report_data.var_95 > 0 else 0
        
        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=var_utilization,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "VaR Utilization %"},
            gauge={
                'axis': {'range': [None, 150]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 50], 'color': "lightgreen"},
                    {'range': [50, 100], 'color': "yellow"},
                    {'range': [100, 150], 'color': "red"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 100
                }
            }
        ), row=1, col=2)
        
        # Win rate gauge
        total_trades = report_data.winning_trades + report_data.losing_trades
        win_rate = (report_data.winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=win_rate,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Win Rate %"},
            gauge={
                'axis': {'range': [None, 100]},
                'bar': {'color': "darkgreen"},
                'steps': [
                    {'range': [0, 40], 'color': "red"},
                    {'range': [40, 60], 'color': "yellow"},
                    {'range': [60, 100], 'color': "lightgreen"}
                ],
                'threshold': {
                    'line': {'color': "green", 'width': 4},
                    'thickness': 0.75,
                    'value': 55
                }
            }
        ), row=1, col=3)
        
        fig.update_layout(
            title="Risk Metrics Dashboard",
            template=self.chart_theme,
            height=300
        )
        
        return fig
    
    # ==========================================================================
    # REPORT GENERATION METHODS
    # ==========================================================================
    
    def _generate_html_report(self, report_data: DailyReportData, 
                             charts: Dict[str, Any]) -> str:
        """Generate HTML version of the report"""
        # Load HTML template
        template_path = self.template_dir / "daily_report_template.html"
        
        if not template_path.exists():
            # Create default template
            template_content = self._create_default_html_template()
        else:
            with open(template_path, 'r') as f:
                template_content = f.read()
        
        # Convert charts to HTML
        chart_html = {}
        for name, fig in charts.items():
            chart_html[name] = fig.to_html(
                include_plotlyjs='cdn',
                div_id=f"chart_{name}"
            )
        
        # Prepare template data
        template_data = {
            'report_date': report_data.report_date.strftime('%Y-%m-%d'),
            'account_id': report_data.account_id,
            'daily_pnl': f"${report_data.daily_pnl:,.2f}",
            'net_pnl': f"${report_data.net_pnl:,.2f}",
            'total_positions': report_data.total_positions,
            'winning_trades': report_data.winning_trades,
            'losing_trades': report_data.losing_trades,
            'charts': chart_html,
            'strategy_table': self._create_strategy_table_html(report_data),
            'risk_table': self._create_risk_table_html(report_data),
            'alerts': report_data.risk_violations + report_data.system_alerts
        }
        
        # Render template
        template = Template(template_content)
        html_content = template.render(**template_data)
        
        # Save to file
        output_path = self.output_dir / f"daily_report_{report_data.report_date}.html"
        with open(output_path, 'w') as f:
            f.write(html_content)
        
        return str(output_path)
    
    def _generate_pdf_report(self, report_data: DailyReportData, 
                            charts: Dict[str, Any]) -> str:
        """Generate PDF version of the report"""
        # Create PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        
        # Title
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt=f"Daily Trading Report - {report_data.report_date}", 
                 ln=True, align='C')
        
        # Executive Summary
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, txt="Executive Summary", ln=True)
        
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"Net P&L: ${report_data.net_pnl:,.2f}", ln=True)
        pdf.cell(200, 10, txt=f"Total Trades: {report_data.total_positions}", ln=True)
        pdf.cell(200, 10, txt=f"Win Rate: {(report_data.winning_trades / max(1, report_data.total_positions)) * 100:.1f}%", ln=True)
        
        # Save charts as images and add to PDF
        for name, fig in charts.items():
            img_path = self.output_dir / f"temp_{name}.png"
            fig.write_image(str(img_path))
            
            pdf.add_page()
            pdf.image(str(img_path), x=10, y=30, w=190)
            
            # Clean up temp image
            img_path.unlink()
        
        # Save PDF
        output_path = self.output_dir / f"daily_report_{report_data.report_date}.pdf"
        pdf.output(str(output_path))
        
        return str(output_path)
    
    def _generate_excel_report(self, report_data: DailyReportData) -> str:
        """Generate Excel version of the report"""
        output_path = self.output_dir / f"daily_report_{report_data.report_date}.xlsx"
        
        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            # Summary sheet
            summary_df = pd.DataFrame({
                'Metric': ['Date', 'Account', 'Daily P&L', 'Net P&L', 'Commission',
                          'Total Positions', 'Winners', 'Losers', 'Win Rate'],
                'Value': [
                    report_data.report_date,
                    report_data.account_id,
                    report_data.daily_pnl,
                    report_data.net_pnl,
                    report_data.commission_paid,
                    report_data.total_positions,
                    report_data.winning_trades,
                    report_data.losing_trades,
                    f"{(report_data.winning_trades / max(1, report_data.total_positions)) * 100:.1f}%"
                ]
            })
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Strategy performance sheet
            strategy_df = pd.DataFrame({
                'Strategy': list(report_data.strategy_pnl.keys()),
                'P&L': list(report_data.strategy_pnl.values()),
                'Trades': [report_data.strategy_trades[s] for s in report_data.strategy_pnl.keys()],
                'Win Rate': [f"{report_data.strategy_win_rate[s] * 100:.1f}%" 
                            for s in report_data.strategy_pnl.keys()]
            })
            strategy_df.to_excel(writer, sheet_name='Strategy Performance', index=False)
            
            # Risk metrics sheet
            risk_df = pd.DataFrame({
                'Metric': ['Delta', 'Gamma', 'Theta', 'Vega', 'Max Drawdown', 
                          'Current Drawdown', 'VaR (95%)'],
                'Value': [
                    report_data.portfolio_delta,
                    report_data.portfolio_gamma,
                    report_data.portfolio_theta,
                    report_data.portfolio_vega,
                    f"{report_data.max_drawdown * 100:.2f}%",
                    f"{report_data.current_drawdown * 100:.2f}%",
                    report_data.var_95
                ]
            })
            risk_df.to_excel(writer, sheet_name='Risk Metrics', index=False)
            
            # Trades detail sheet
            trades = self._get_daily_trades(report_data.report_date)
            if trades:
                trades_df = pd.DataFrame([asdict(t) for t in trades])
                trades_df.to_excel(writer, sheet_name='Trade Details', index=False)
            
            # Format worksheets
            workbook = writer.book
            currency_format = workbook.add_format({'num_format': '$#,##0.00'})
            percent_format = workbook.add_format({'num_format': '0.00%'})
            
            # Apply formatting
            worksheet = writer.sheets['Summary']
            worksheet.set_column('B:B', 15, currency_format)
        
        return str(output_path)
    
    def _generate_json_report(self, report_data: DailyReportData) -> str:
        """Generate JSON version of the report"""
        output_path = self.output_dir / f"daily_report_{report_data.report_date}.json"
        
        # Convert dataclass to dict
        report_dict = asdict(report_data)
        
        # Add metadata
        report_dict['metadata'] = {
            'generated_at': datetime.now().isoformat(),
            'version': '1.0',
            'generator': 'SpyderK02_DailyTradingReport'
        }
        
        # Save to file
        with open(output_path, 'w') as f:
            json.dump(report_dict, f, indent=2, default=str)
        
        return str(output_path)
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    
    def _create_default_html_template(self) -> str:
        """Create default HTML template"""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>Spyder Daily Trading Report - {{ report_date }}</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .header {
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 10px;
        }
        .section {
            background-color: white;
            margin: 20px 0;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .metric {
            display: inline-block;
            margin: 10px 20px;
        }
        .metric-value {
            font-size: 24px;
            font-weight: bold;
            color: #2c3e50;
        }
        .metric-label {
            font-size: 14px;
            color: #7f8c8d;
        }
        .positive {
            color: #27ae60;
        }
        .negative {
            color: #e74c3c;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #34495e;
            color: white;
        }
        .alert {
            background-color: #e74c3c;
            color: white;
            padding: 10px;
            border-radius: 5px;
            margin: 5px 0;
        }
    </style>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
    <div class="header">
        <h1>Daily Trading Report</h1>
        <h2>{{ report_date }} - Account: {{ account_id }}</h2>
    </div>
    
    <div class="section">
        <h2>Executive Summary</h2>
        <div class="metric">
            <div class="metric-label">Net P&L</div>
            <div class="metric-value {{ 'positive' if net_pnl >= 0 else 'negative' }}">
                {{ net_pnl }}
            </div>
        </div>
        <div class="metric">
            <div class="metric-label">Daily P&L</div>
            <div class="metric-value {{ 'positive' if daily_pnl >= 0 else 'negative' }}">
                {{ daily_pnl }}
            </div>
        </div>
        <div class="metric">
            <div class="metric-label">Total Positions</div>
            <div class="metric-value">{{ total_positions }}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Win/Loss</div>
            <div class="metric-value">{{ winning_trades }}/{{ losing_trades }}</div>
        </div>
    </div>
    
    <div class="section">
        <h2>P&L Analysis</h2>
        {{ charts.pnl_waterfall|safe }}
    </div>
    
    <div class="section">
        <h2>Strategy Performance</h2>
        {{ charts.strategy_performance|safe }}
        {{ strategy_table|safe }}
    </div>
    
    <div class="section">
        <h2>Risk Metrics</h2>
        {{ charts.risk_gauges|safe }}
        {{ risk_table|safe }}
    </div>
    
    <div class="section">
        <h2>Intraday Performance</h2>
        {{ charts.intraday_pnl|safe }}
    </div>
    
    <div class="section">
        <h2>Trade Distribution</h2>
        {{ charts.win_loss_dist|safe }}
    </div>
    
    <div class="section">
        <h2>Greeks Exposure</h2>
        {{ charts.greeks_radar|safe }}
    </div>
    
    {% if alerts %}
    <div class="section">
        <h2>Alerts & Violations</h2>
        {% for alert in alerts %}
        <div class="alert">{{ alert }}</div>
        {% endfor %}
    </div>
    {% endif %}
    
    <div class="section" style="text-align: center; color: #7f8c8d;">
        <p>Report generated by Spyder Trading System</p>
        <p>© 2025 Spyder Trading. All rights reserved.</p>
    </div>
</body>
</html>
        """
    
    def _create_strategy_table_html(self, report_data: DailyReportData) -> str:
        """Create HTML table for strategy performance"""
        html = """
        <table>
            <tr>
                <th>Strategy</th>
                <th>P&L</th>
                <th>Trades</th>
                <th>Win Rate</th>
            </tr>
        """
        
        for strategy in report_data.strategy_pnl:
            pnl = report_data.strategy_pnl[strategy]
            trades = report_data.strategy_trades[strategy]
            win_rate = report_data.strategy_win_rate[strategy]
            
            pnl_class = 'positive' if pnl >= 0 else 'negative'
            
            html += f"""
            <tr>
                <td>{strategy}</td>
                <td class="{pnl_class}">${pnl:,.2f}</td>
                <td>{trades}</td>
                <td>{win_rate * 100:.1f}%</td>
            </tr>
            """
        
        html += "</table>"
        return html
    
    def _create_risk_table_html(self, report_data: DailyReportData) -> str:
        """Create HTML table for risk metrics"""
        return f"""
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Portfolio Delta</td>
                <td>{report_data.portfolio_delta:,.2f}</td>
            </tr>
            <tr>
                <td>Portfolio Gamma</td>
                <td>{report_data.portfolio_gamma:,.2f}</td>
            </tr>
            <tr>
                <td>Portfolio Theta</td>
                <td>{report_data.portfolio_theta:,.2f}</td>
            </tr>
            <tr>
                <td>Portfolio Vega</td>
                <td>{report_data.portfolio_vega:,.2f}</td>
            </tr>
            <tr>
                <td>Current Drawdown</td>
                <td class="{'negative' if report_data.current_drawdown < 0 else ''}">
                    {report_data.current_drawdown * 100:.2f}%
                </td>
            </tr>
            <tr>
                <td>VaR (95%)</td>
                <td>${report_data.var_95:,.2f}</td>
            </tr>
        </table>
        """
    
    def _send_email_report(self, report_data: DailyReportData, 
                          output_files: Dict[str, str]) -> None:
        """Send report via email"""
        try:
            subject = f"Spyder Daily Report - {report_data.report_date} - Net P&L: ${report_data.net_pnl:,.2f}"
            
            # Create email body
            body = f"""
Daily Trading Report Summary
Date: {report_data.report_date}
Account: {report_data.account_id}

PERFORMANCE SUMMARY:
- Net P&L: ${report_data.net_pnl:,.2f}
- Daily P&L: ${report_data.daily_pnl:,.2f}
- Commission: ${report_data.commission_paid:,.2f}

TRADING ACTIVITY:
- Total Positions: {report_data.total_positions}
- Winners: {report_data.winning_trades}
- Losers: {report_data.losing_trades}
- Win Rate: {(report_data.winning_trades / max(1, report_data.total_positions)) * 100:.1f}%

RISK METRICS:
- Current Drawdown: {report_data.current_drawdown * 100:.2f}%
- Portfolio Delta: {report_data.portfolio_delta:,.2f}
- VaR (95%): ${report_data.var_95:,.2f}

Please find detailed reports attached.
            """
            
            # Send email with attachments
            self.email_notifier.send_email(
                subject=subject,
                body=body,
                recipients=self.email_recipients,
                attachments=list(output_files.values())
            )
            
            self.logger.info(f"Report emailed to {len(self.email_recipients)} recipients")
            
        except Exception as e:
            self.logger.error(f"Failed to send email report: {e}")
    
    def _archive_report(self, report_date: date, report_data: DailyReportData,
                       output_files: Dict[str, str]) -> None:
        """Archive report data and files"""
        try:
            # Create archive directory
            archive_dir = self.output_dir / "archive" / str(report_date.year) / f"{report_date.month:02d}"
            archive_dir.mkdir(parents=True, exist_ok=True)
            
            # Save report data
            # NOTE: pickle retained here because report_data contains complex
            # nested objects (DataFrames, custom types) that may not round-trip
            # cleanly through JSON.  This file is write-once archive data (never
            # loaded from untrusted sources), so pickle is low-risk here.
            # TODO: migrate to JSON+pandas parquet if structured access is needed.
            data_file = archive_dir / f"report_data_{report_date}.pkl"
            with open(data_file, 'wb') as f:
                pickle.dump(report_data, f)
            
            # Copy output files to archive
            for format_type, filepath in output_files.items():
                src = Path(filepath)
                dst = archive_dir / src.name
                dst.write_bytes(src.read_bytes())
            
            self.logger.info(f"Report archived to {archive_dir}")
            
        except Exception as e:
            self.logger.error(f"Failed to archive report: {e}")
    
    # ==========================================================================
    # SCHEDULED REPORT GENERATION
    # ==========================================================================
    
    def schedule_daily_reports(self, generation_time: str = "17:00") -> None:
        """
        Schedule automatic daily report generation.
        
        Args:
            generation_time: Time to generate report (HH:MM format)
        """
        import schedule
        
        def generate_report_job():
            """Job to generate daily report"""
            self.logger.info("Running scheduled daily report generation")
            self.generate_daily_report()
        
        # Schedule the job
        schedule.every().day.at(generation_time).do(generate_report_job)
        
        self.logger.info(f"Daily report generation scheduled for {generation_time}")
    
    def generate_intraday_snapshot(self) -> Dict[str, Any]:
        """Generate quick intraday performance snapshot"""
        try:
            # Get current date
            snapshot_time = datetime.now()
            report_date = snapshot_time.date()
            
            # Collect basic metrics
            trades = self._get_daily_trades(report_date)
            pnl_metrics = self._calculate_pnl_metrics(trades)
            
            # Create snapshot
            snapshot = {
                'timestamp': snapshot_time,
                'net_pnl': pnl_metrics['net_pnl'],
                'realized_pnl': pnl_metrics['realized_pnl'],
                'unrealized_pnl': pnl_metrics['unrealized_pnl'],
                'trade_count': len(trades),
                'winning_trades': len([t for t in trades if t.pnl > 0]),
                'losing_trades': len([t for t in trades if t.pnl < 0])
            }
            
            # Log snapshot
            self.logger.info(f"Intraday snapshot: Net P&L ${snapshot['net_pnl']:,.2f}")
            
            return snapshot
            
        except Exception as e:
            self.logger.error(f"Failed to generate intraday snapshot: {e}")
            return {}


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_daily_report_generator(config: Optional[Dict[str, Any]] = None) -> DailyTradingReport:
    """
    Factory function to create daily report generator.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        DailyTradingReport instance
    """
    return DailyTradingReport(config)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Example usage
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate Spyder daily trading report")
    parser.add_argument('--date', type=str, help='Report date (YYYY-MM-DD)')
    parser.add_argument('--email', action='store_true', help='Send email report')
    parser.add_argument('--formats', nargs='+', default=['html', 'pdf'],
                       help='Report formats to generate')
    
    args = parser.parse_args()
    
    # Configuration
    config = {
        'formats': args.formats,
        'email_enabled': args.email,
        'email_recipients': ['trader@example.com'] if args.email else []
    }
    
    # Create report generator
    report_gen = create_daily_report_generator(config)
    
    # Generate report
    if args.date:
        report_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    else:
        report_date = date.today()
    
    result = report_gen.generate_daily_report(report_date)
    
    if result['status'] == 'success':
        print(f"Report generated successfully!")
        print(f"Files created: {result['files']}")
    else:
        print(f"Report generation failed: {result.get('error')}")
