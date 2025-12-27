#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderK03_PerformanceDashboard.py
Group: K (Reports)
Purpose: Interactive real-time performance dashboard

Description:
    This module provides an interactive web-based performance dashboard using
    Dash/Plotly. It displays real-time P&L curves, strategy comparisons,
    risk-adjusted returns, drawdown analysis, and comprehensive performance
    metrics. The dashboard auto-updates and provides drill-down capabilities
    for detailed analysis.

Author: Mohamed Talib
Date: 2025-01-28
Version: 1.0
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import json
import threading
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import queue

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
import dash
from dash import dcc, html, dash_table, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import dash_daq as daq

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU15_PerformanceMetrics import PerformanceMetrics
from Spyder.SpyderH_Storage.SpyderH01_DataAccessLayer import get_data_access_layer
from Spyder.SpyderE_Risk.SpyderE06_RiskMetrics import RiskMetricsCalculator
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType

# ==============================================================================
# CONSTANTS
# ==============================================================================
DASHBOARD_PORT = 8050
UPDATE_INTERVAL = 5000  # milliseconds
LOOKBACK_PERIODS = {
    '1D': 1,
    '1W': 7,
    '1M': 30,
    '3M': 90,
    '6M': 180,
    '1Y': 365,
    'YTD': 'YTD',
    'ALL': 'ALL'
}

# Color scheme
COLORS = {
    'background': '#1e1e1e',
    'text': '#ffffff',
    'grid': '#333333',
    'profit': '#00ff00',
    'loss': '#ff0000',
    'primary': '#1f77b4',
    'secondary': '#ff7f0e',
    'warning': '#ffbb00',
    'danger': '#ff4444'
}

# ==============================================================================
# PERFORMANCE DASHBOARD CLASS
# ==============================================================================
class PerformanceDashboard:
    """
    Interactive performance dashboard for Spyder trading system.
    
    Features:
    - Real-time P&L tracking
    - Strategy performance comparison
    - Risk-adjusted metrics (Sharpe, Sortino, Calmar)
    - Drawdown visualization
    - Win/loss distribution
    - Performance attribution
    - Custom date range analysis
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize performance dashboard"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or {}
        
        # Data access
        self.dal = get_data_access_layer()
        self.performance_metrics = PerformanceMetrics()
        self.risk_calculator = RiskMetricsCalculator()
        self.event_manager = get_event_manager()
        
        # Dashboard configuration
        self.port = self.config.get('port', DASHBOARD_PORT)
        self.debug = self.config.get('debug', False)
        self.update_interval = self.config.get('update_interval', UPDATE_INTERVAL)
        
        # Data cache
        self.data_cache = {
            'equity_curve': pd.DataFrame(),
            'trades': pd.DataFrame(),
            'positions': pd.DataFrame(),
            'metrics': {},
            'last_update': None
        }
        self._cache_lock = threading.Lock()
        
        # Initialize Dash app
        self.app = self._create_app()
        self._setup_callbacks()
        
        # Background data updater
        self._update_thread = None
        self._stop_event = threading.Event()
        
        self.logger.info("Performance Dashboard initialized")
    
    # ==========================================================================
    # DASHBOARD CREATION
    # ==========================================================================
    
    def _create_app(self) -> dash.Dash:
        """Create Dash application"""
        app = dash.Dash(
            __name__,
            external_stylesheets=[dbc.themes.DARKLY],
            suppress_callback_exceptions=True
        )
        
        app.title = "Spyder Performance Dashboard"
        
        # Define layout
        app.layout = self._create_layout()
        
        return app
    
    def _create_layout(self) -> html.Div:
        """Create dashboard layout"""
        return dbc.Container([
            # Header
            dbc.Row([
                dbc.Col([
                    html.H1("Spyder Performance Dashboard", 
                           className="text-center mb-4",
                           style={'color': COLORS['text']}),
                    html.Hr()
                ])
            ]),
            
            # Key Metrics Cards
            dbc.Row([
                dbc.Col([self._create_metric_card("Total P&L", "total_pnl", "$")], width=3),
                dbc.Col([self._create_metric_card("Today P&L", "today_pnl", "$")], width=3),
                dbc.Col([self._create_metric_card("Win Rate", "win_rate", "%")], width=3),
                dbc.Col([self._create_metric_card("Sharpe Ratio", "sharpe_ratio", "")], width=3),
            ], className="mb-4"),
            
            # Time Period Selector
            dbc.Row([
                dbc.Col([
                    dbc.ButtonGroup([
                        dbc.Button(period, id=f"period-{period}", 
                                  n_clicks=0, color="secondary", size="sm")
                        for period in LOOKBACK_PERIODS.keys()
                    ], id="period-selector"),
                ], width=12)
            ], className="mb-4"),
            
            # Main Charts
            dbc.Row([
                dbc.Col([
                    dcc.Graph(id="equity-curve-chart", style={'height': '400px'})
                ], width=8),
                dbc.Col([
                    dcc.Graph(id="strategy-pie-chart", style={'height': '400px'})
                ], width=4)
            ], className="mb-4"),
            
            # Secondary Charts
            dbc.Row([
                dbc.Col([
                    dcc.Graph(id="drawdown-chart", style={'height': '300px'})
                ], width=6),
                dbc.Col([
                    dcc.Graph(id="returns-distribution", style={'height': '300px'})
                ], width=6)
            ], className="mb-4"),
            
            # Performance Metrics Table
            dbc.Row([
                dbc.Col([
                    html.H4("Performance Metrics", style={'color': COLORS['text']}),
                    html.Div(id="metrics-table")
                ], width=6),
                dbc.Col([
                    html.H4("Top Trades", style={'color': COLORS['text']}),
                    html.Div(id="trades-table")
                ], width=6)
            ], className="mb-4"),
            
            # Risk Metrics
            dbc.Row([
                dbc.Col([
                    dcc.Graph(id="risk-gauge-chart", style={'height': '300px'})
                ], width=12)
            ], className="mb-4"),
            
            # Auto-refresh interval
            dcc.Interval(
                id='interval-component',
                interval=self.update_interval,
                n_intervals=0
            ),
            
            # Hidden div to store current period
            html.Div(id='current-period', style={'display': 'none'}, children='1M')
            
        ], fluid=True, style={'backgroundColor': COLORS['background']})
    
    def _create_metric_card(self, title: str, metric_id: str, prefix: str = "") -> dbc.Card:
        """Create a metric display card"""
        return dbc.Card([
            dbc.CardBody([
                html.H6(title, className="card-title", 
                       style={'color': COLORS['text'], 'fontSize': '14px'}),
                html.H3(id=f"metric-{metric_id}", children="--",
                       style={'color': COLORS['text'], 'fontSize': '24px'}),
                html.P(id=f"metric-{metric_id}-change", children="",
                      style={'fontSize': '12px', 'marginBottom': '0'})
            ])
        ], style={'backgroundColor': '#2a2a2a', 'border': 'none'})
    
    # ==========================================================================
    # CALLBACKS
    # ==========================================================================
    
    def _setup_callbacks(self):
        """Setup all dashboard callbacks"""
        
        # Period selector callback
        @self.app.callback(
            Output('current-period', 'children'),
            [Input(f'period-{period}', 'n_clicks') for period in LOOKBACK_PERIODS.keys()]
        )
        def update_period(*args):
            ctx = callback_context
            if not ctx.triggered:
                return '1M'
            
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            period = button_id.split('-')[1]
            return period
        
        # Main update callback
        @self.app.callback(
            [
                # Metric cards
                Output('metric-total_pnl', 'children'),
                Output('metric-total_pnl-change', 'children'),
                Output('metric-total_pnl-change', 'style'),
                Output('metric-today_pnl', 'children'),
                Output('metric-today_pnl-change', 'children'),
                Output('metric-today_pnl-change', 'style'),
                Output('metric-win_rate', 'children'),
                Output('metric-sharpe_ratio', 'children'),
                
                # Charts
                Output('equity-curve-chart', 'figure'),
                Output('strategy-pie-chart', 'figure'),
                Output('drawdown-chart', 'figure'),
                Output('returns-distribution', 'figure'),
                Output('risk-gauge-chart', 'figure'),
                
                # Tables
                Output('metrics-table', 'children'),
                Output('trades-table', 'children')
            ],
            [
                Input('interval-component', 'n_intervals'),
                Input('current-period', 'children')
            ]
        )
        def update_dashboard(n_intervals, period):
            """Update all dashboard components"""
            try:
                # Get fresh data
                self._update_cache()
                
                with self._cache_lock:
                    data = self.data_cache.copy()
                
                # Filter data by period
                filtered_data = self._filter_by_period(data, period)
                
                # Update metrics
                metrics = self._calculate_display_metrics(filtered_data)
                
                # Create outputs
                outputs = []
                
                # Total P&L
                total_pnl = metrics.get('total_pnl', 0)
                pnl_change = metrics.get('total_pnl_change', 0)
                outputs.extend([
                    f"${total_pnl:,.2f}",
                    f"{pnl_change:+.1f}%",
                    {'color': COLORS['profit'] if pnl_change >= 0 else COLORS['loss']}
                ])
                
                # Today P&L
                today_pnl = metrics.get('today_pnl', 0)
                today_change = metrics.get('today_pnl_change', 0)
                outputs.extend([
                    f"${today_pnl:,.2f}",
                    f"{today_change:+.1f}%",
                    {'color': COLORS['profit'] if today_pnl >= 0 else COLORS['loss']}
                ])
                
                # Win Rate
                win_rate = metrics.get('win_rate', 0)
                outputs.append(f"{win_rate:.1f}%")
                
                # Sharpe Ratio
                sharpe = metrics.get('sharpe_ratio', 0)
                outputs.append(f"{sharpe:.2f}")
                
                # Charts
                outputs.append(self._create_equity_curve(filtered_data))
                outputs.append(self._create_strategy_pie(filtered_data))
                outputs.append(self._create_drawdown_chart(filtered_data))
                outputs.append(self._create_returns_distribution(filtered_data))
                outputs.append(self._create_risk_gauges(metrics))
                
                # Tables
                outputs.append(self._create_metrics_table(metrics))
                outputs.append(self._create_trades_table(filtered_data))
                
                return outputs
                
            except Exception as e:
                self.logger.error(f"Dashboard update failed: {e}")
                # Return empty/default values
                return ["--"] * 8 + [go.Figure()] * 5 + [html.Div()] * 2
    
    # ==========================================================================
    # DATA METHODS
    # ==========================================================================
    
    def _update_cache(self):
        """Update data cache from database"""
        try:
            with self._cache_lock:
                # Get equity curve
                self.data_cache['equity_curve'] = self.dal.get_equity_curve()
                
                # Get recent trades
                self.data_cache['trades'] = self.dal.query_trades(
                    start_date=datetime.now() - timedelta(days=365)
                )
                
                # Get current positions
                self.data_cache['positions'] = self.dal.query_positions(
                    status='OPEN'
                )
                
                # Calculate metrics
                if not self.data_cache['equity_curve'].empty:
                    returns = self.data_cache['equity_curve']['returns']
                    self.data_cache['metrics'] = {
                        'total_return': (self.data_cache['equity_curve']['equity'].iloc[-1] / 
                                       self.data_cache['equity_curve']['equity'].iloc[0] - 1) * 100,
                        'sharpe_ratio': self.performance_metrics.calculate_sharpe_ratio(returns),
                        'sortino_ratio': self.performance_metrics.calculate_sortino_ratio(returns),
                        'max_drawdown': self.risk_calculator.calculate_max_drawdown(
                            self.data_cache['equity_curve']['equity']
                        ),
                        'win_rate': self._calculate_win_rate(self.data_cache['trades'])
                    }
                
                self.data_cache['last_update'] = datetime.now()
                
        except Exception as e:
            self.logger.error(f"Cache update failed: {e}")
    
    def _filter_by_period(self, data: Dict[str, Any], period: str) -> Dict[str, Any]:
        """Filter data by selected time period"""
        filtered = data.copy()
        
        if period == 'ALL':
            return filtered
        
        if period == 'YTD':
            start_date = datetime(datetime.now().year, 1, 1)
        else:
            days = LOOKBACK_PERIODS.get(period, 30)
            start_date = datetime.now() - timedelta(days=days)
        
        # Filter equity curve
        if not filtered['equity_curve'].empty:
            filtered['equity_curve'] = filtered['equity_curve'][
                filtered['equity_curve'].index >= start_date
            ]
        
        # Filter trades
        if not filtered['trades'].empty:
            filtered['trades'] = filtered['trades'][
                pd.to_datetime(filtered['trades']['entry_time']) >= start_date
            ]
        
        return filtered
    
    def _calculate_display_metrics(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate metrics for display"""
        metrics = {}
        
        # P&L metrics
        if not data['equity_curve'].empty:
            equity = data['equity_curve']['equity']
            metrics['total_pnl'] = equity.iloc[-1] - equity.iloc[0]
            metrics['total_pnl_change'] = (equity.iloc[-1] / equity.iloc[0] - 1) * 100
            
            # Today's P&L
            today_start = equity[equity.index.date == date.today()].iloc[0] if any(
                equity.index.date == date.today()
            ) else equity.iloc[-2]
            metrics['today_pnl'] = equity.iloc[-1] - today_start
            metrics['today_pnl_change'] = (equity.iloc[-1] / today_start - 1) * 100
        
        # Win rate
        metrics['win_rate'] = self._calculate_win_rate(data['trades'])
        
        # Risk metrics
        if 'metrics' in data:
            metrics.update(data['metrics'])
        
        return metrics
    
    def _calculate_win_rate(self, trades_df: pd.DataFrame) -> float:
        """Calculate win rate from trades"""
        if trades_df.empty:
            return 0.0
        
        closed_trades = trades_df[trades_df['exit_price'] > 0]
        if closed_trades.empty:
            return 0.0
        
        winners = len(closed_trades[closed_trades['pnl'] > 0])
        total = len(closed_trades)
        
        return (winners / total * 100) if total > 0 else 0.0
    
    # ==========================================================================
    # CHART CREATION
    # ==========================================================================
    
    def _create_equity_curve(self, data: Dict[str, Any]) -> go.Figure:
        """Create equity curve chart"""
        fig = go.Figure()
        
        if data['equity_curve'].empty:
            return fig
        
        equity_df = data['equity_curve']
        
        # Add equity line
        fig.add_trace(go.Scatter(
            x=equity_df.index,
            y=equity_df['equity'],
            mode='lines',
            name='Equity',
            line=dict(color=COLORS['primary'], width=2),
            fill='tozeroy',
            fillcolor='rgba(31, 119, 180, 0.2)'
        ))
        
        # Add benchmark if available
        if 'benchmark' in equity_df.columns:
            fig.add_trace(go.Scatter(
                x=equity_df.index,
                y=equity_df['benchmark'],
                mode='lines',
                name='SPY Benchmark',
                line=dict(color=COLORS['secondary'], width=1, dash='dash')
            ))
        
        # Layout
        fig.update_layout(
            title="Equity Curve",
            xaxis_title="Date",
            yaxis_title="Equity ($)",
            template="plotly_dark",
            showlegend=True,
            hovermode='x unified',
            plot_bgcolor=COLORS['background'],
            paper_bgcolor=COLORS['background'],
            font=dict(color=COLORS['text'])
        )
        
        return fig
    
    def _create_strategy_pie(self, data: Dict[str, Any]) -> go.Figure:
        """Create strategy performance pie chart"""
        fig = go.Figure()
        
        if data['trades'].empty:
            return fig
        
        # Calculate P&L by strategy
        strategy_pnl = data['trades'].groupby('strategy')['pnl'].sum()
        
        # Only show positive contributions
        positive_pnl = strategy_pnl[strategy_pnl > 0]
        
        if positive_pnl.empty:
            return fig
        
        fig.add_trace(go.Pie(
            labels=positive_pnl.index,
            values=positive_pnl.values,
            hole=0.4,
            marker=dict(
                colors=px.colors.qualitative.Set3[:len(positive_pnl)]
            )
        ))
        
        fig.update_layout(
            title="Strategy P&L Contribution",
            template="plotly_dark",
            showlegend=True,
            plot_bgcolor=COLORS['background'],
            paper_bgcolor=COLORS['background'],
            font=dict(color=COLORS['text'])
        )
        
        return fig
    
    def _create_drawdown_chart(self, data: Dict[str, Any]) -> go.Figure:
        """Create drawdown chart"""
        fig = go.Figure()
        
        if data['equity_curve'].empty:
            return fig
        
        equity = data['equity_curve']['equity']
        
        # Calculate drawdown
        rolling_max = equity.expanding().max()
        drawdown = (equity - rolling_max) / rolling_max * 100
        
        # Add drawdown area
        fig.add_trace(go.Scatter(
            x=drawdown.index,
            y=drawdown.values,
            mode='lines',
            name='Drawdown',
            line=dict(color=COLORS['loss'], width=0),
            fill='tozeroy',
            fillcolor=COLORS['loss']
        ))
        
        # Add max drawdown line
        max_dd_idx = drawdown.idxmin()
        max_dd_value = drawdown.min()
        
        fig.add_trace(go.Scatter(
            x=[max_dd_idx],
            y=[max_dd_value],
            mode='markers+text',
            name='Max Drawdown',
            marker=dict(size=10, color=COLORS['danger']),
            text=[f"{max_dd_value:.1f}%"],
            textposition="top center"
        ))
        
        fig.update_layout(
            title="Drawdown Analysis",
            xaxis_title="Date",
            yaxis_title="Drawdown (%)",
            template="plotly_dark",
            showlegend=True,
            hovermode='x unified',
            plot_bgcolor=COLORS['background'],
            paper_bgcolor=COLORS['background'],
            font=dict(color=COLORS['text']),
            yaxis=dict(range=[min(-1, max_dd_value * 1.1), 0])
        )
        
        return fig
    
    def _create_returns_distribution(self, data: Dict[str, Any]) -> go.Figure:
        """Create returns distribution histogram"""
        fig = go.Figure()
        
        if data['equity_curve'].empty or 'returns' not in data['equity_curve']:
            return fig
        
        returns = data['equity_curve']['returns'].dropna() * 100  # Convert to percentage
        
        # Create histogram
        fig.add_trace(go.Histogram(
            x=returns,
            nbinsx=50,
            name='Daily Returns',
            marker_color=COLORS['primary'],
            opacity=0.7
        ))
        
        # Add normal distribution overlay
        mean = returns.mean()
        std = returns.std()
        x_range = np.linspace(returns.min(), returns.max(), 100)
        normal_dist = np.exp(-(x_range - mean)**2 / (2 * std**2)) / (std * np.sqrt(2 * np.pi))
        normal_dist = normal_dist * len(returns) * (returns.max() - returns.min()) / 50
        
        fig.add_trace(go.Scatter(
            x=x_range,
            y=normal_dist,
            mode='lines',
            name='Normal Distribution',
            line=dict(color=COLORS['warning'], width=2)
        ))
        
        fig.update_layout(
            title="Returns Distribution",
            xaxis_title="Daily Return (%)",
            yaxis_title="Frequency",
            template="plotly_dark",
            showlegend=True,
            plot_bgcolor=COLORS['background'],
            paper_bgcolor=COLORS['background'],
            font=dict(color=COLORS['text'])
        )
        
        return fig
    
    def _create_risk_gauges(self, metrics: Dict[str, float]) -> go.Figure:
        """Create risk metric gauges"""
        fig = make_subplots(
            rows=1, cols=4,
            specs=[[{'type': 'indicator'}, {'type': 'indicator'}, 
                   {'type': 'indicator'}, {'type': 'indicator'}]],
            subplot_titles=('Sharpe Ratio', 'Sortino Ratio', 
                          'Max Drawdown', 'Calmar Ratio')
        )
        
        # Sharpe Ratio gauge
        sharpe = metrics.get('sharpe_ratio', 0)
        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=sharpe,
            title={'text': "Sharpe", 'font': {'color': COLORS['text']}},
            gauge={
                'axis': {'range': [-1, 3], 'tickcolor': COLORS['text']},
                'bar': {'color': COLORS['primary']},
                'steps': [
                    {'range': [-1, 0], 'color': COLORS['loss']},
                    {'range': [0, 1], 'color': COLORS['warning']},
                    {'range': [1, 3], 'color': COLORS['profit']}
                ],
                'threshold': {
                    'line': {'color': COLORS['text'], 'width': 2},
                    'thickness': 0.75,
                    'value': 1
                }
            }
        ), row=1, col=1)
        
        # Sortino Ratio gauge
        sortino = metrics.get('sortino_ratio', 0)
        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=sortino,
            title={'text': "Sortino", 'font': {'color': COLORS['text']}},
            gauge={
                'axis': {'range': [-1, 4], 'tickcolor': COLORS['text']},
                'bar': {'color': COLORS['primary']},
                'steps': [
                    {'range': [-1, 0], 'color': COLORS['loss']},
                    {'range': [0, 1.5], 'color': COLORS['warning']},
                    {'range': [1.5, 4], 'color': COLORS['profit']}
                ]
            }
        ), row=1, col=2)
        
        # Max Drawdown gauge
        max_dd = abs(metrics.get('max_drawdown', 0) * 100)
        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=max_dd,
            title={'text': "Max DD %", 'font': {'color': COLORS['text']}},
            gauge={
                'axis': {'range': [0, 30], 'tickcolor': COLORS['text']},
                'bar': {'color': COLORS['danger']},
                'steps': [
                    {'range': [0, 10], 'color': COLORS['profit']},
                    {'range': [10, 20], 'color': COLORS['warning']},
                    {'range': [20, 30], 'color': COLORS['loss']}
                ]
            }
        ), row=1, col=3)
        
        # Calmar Ratio gauge
        calmar = metrics.get('total_return', 0) / max_dd if max_dd > 0 else 0
        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=calmar,
            title={'text': "Calmar", 'font': {'color': COLORS['text']}},
            gauge={
                'axis': {'range': [-1, 3], 'tickcolor': COLORS['text']},
                'bar': {'color': COLORS['primary']},
                'steps': [
                    {'range': [-1, 0], 'color': COLORS['loss']},
                    {'range': [0, 1], 'color': COLORS['warning']},
                    {'range': [1, 3], 'color': COLORS['profit']}
                ]
            }
        ), row=1, col=4)
        
        fig.update_layout(
            template="plotly_dark",
            height=250,
            plot_bgcolor=COLORS['background'],
            paper_bgcolor=COLORS['background'],
            font=dict(color=COLORS['text']),
            showlegend=False
        )
        
        return fig
    
    # ==========================================================================
    # TABLE CREATION
    # ==========================================================================
    
    def _create_metrics_table(self, metrics: Dict[str, float]) -> dbc.Table:
        """Create performance metrics table"""
        rows = []
        
        metric_definitions = [
            ('Total Return', 'total_return', '%', 1),
            ('Sharpe Ratio', 'sharpe_ratio', '', 2),
            ('Sortino Ratio', 'sortino_ratio', '', 2),
            ('Max Drawdown', 'max_drawdown', '%', 1),
            ('Win Rate', 'win_rate', '%', 1),
            ('Profit Factor', 'profit_factor', '', 2),
            ('Recovery Factor', 'recovery_factor', '', 2),
            ('Expectancy', 'expectancy', '$', 2)
        ]
        
        for name, key, suffix, decimals in metric_definitions:
            value = metrics.get(key, 0)
            
            if suffix == '%':
                value_str = f"{value:.{decimals}f}%"
            elif suffix == '$':
                value_str = f"${value:,.{decimals}f}"
            else:
                value_str = f"{value:.{decimals}f}"
            
            color = COLORS['text']
            if key in ['total_return', 'expectancy']:
                color = COLORS['profit'] if value >= 0 else COLORS['loss']
            
            rows.append(
                html.Tr([
                    html.Td(name, style={'color': COLORS['text']}),
                    html.Td(value_str, style={'color': color, 'textAlign': 'right'})
                ])
            )
        
        return dbc.Table(
            children=[
                html.Tbody(rows)
            ],
            bordered=True,
            dark=True,
            hover=True,
            responsive=True,
            striped=True
        )
    
    def _create_trades_table(self, data: Dict[str, Any]) -> dbc.Table:
        """Create top trades table"""
        if data['trades'].empty:
            return html.Div("No trades available", style={'color': COLORS['text']})
        
        # Get top 10 trades by absolute P&L
        trades_df = data['trades'].copy()
        trades_df['abs_pnl'] = trades_df['pnl'].abs()
        top_trades = trades_df.nlargest(10, 'abs_pnl')[
            ['entry_time', 'strategy', 'symbol', 'side', 'quantity', 'pnl']
        ]
        
        rows = []
        for _, trade in top_trades.iterrows():
            pnl_color = COLORS['profit'] if trade['pnl'] >= 0 else COLORS['loss']
            
            rows.append(
                html.Tr([
                    html.Td(trade['entry_time'].strftime('%Y-%m-%d'), 
                           style={'color': COLORS['text']}),
                    html.Td(trade['strategy'], style={'color': COLORS['text']}),
                    html.Td(trade['symbol'], style={'color': COLORS['text']}),
                    html.Td(trade['side'], style={'color': COLORS['text']}),
                    html.Td(f"{trade['quantity']}", style={'color': COLORS['text']}),
                    html.Td(f"${trade['pnl']:,.2f}", 
                           style={'color': pnl_color, 'textAlign': 'right'})
                ])
            )
        
        return dbc.Table(
            children=[
                html.Thead([
                    html.Tr([
                        html.Th("Date", style={'color': COLORS['text']}),
                        html.Th("Strategy", style={'color': COLORS['text']}),
                        html.Th("Symbol", style={'color': COLORS['text']}),
                        html.Th("Side", style={'color': COLORS['text']}),
                        html.Th("Qty", style={'color': COLORS['text']}),
                        html.Th("P&L", style={'color': COLORS['text'], 'textAlign': 'right'})
                    ])
                ]),
                html.Tbody(rows)
            ],
            bordered=True,
            dark=True,
            hover=True,
            responsive=True,
            striped=True,
            size='sm'
        )
    
    # ==========================================================================
    # DASHBOARD MANAGEMENT
    # ==========================================================================
    
    def start(self):
        """Start the dashboard server"""
        try:
            self.logger.info(f"Starting Performance Dashboard on port {self.port}")
            
            # Start background data updater
            self._stop_event.clear()
            self._update_thread = threading.Thread(target=self._background_updater)
            self._update_thread.daemon = True
            self._update_thread.start()
            
            # Run Dash app
            self.app.run_server(
                host='0.0.0.0',
                port=self.port,
                debug=self.debug,
                use_reloader=False
            )
            
        except Exception as e:
            self.logger.error(f"Failed to start dashboard: {e}")
            self.error_handler.handle_error(e, "PerformanceDashboard")
    
    def stop(self):
        """Stop the dashboard server"""
        self.logger.info("Stopping Performance Dashboard")
        self._stop_event.set()
        
        if self._update_thread:
            self._update_thread.join(timeout=5)
    
    def _background_updater(self):
        """Background thread to update data cache"""
        while not self._stop_event.is_set():
            try:
                self._update_cache()
                
                # Subscribe to real-time events
                if self.event_manager:
                    # Process any pending events
                    pass
                
            except Exception as e:
                self.logger.error(f"Background update error: {e}")
            
            # Wait before next update
            self._stop_event.wait(5)  # Update every 5 seconds


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_performance_dashboard(config: Optional[Dict[str, Any]] = None) -> PerformanceDashboard:
    """
    Factory function to create performance dashboard.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        PerformanceDashboard instance
    """
    return PerformanceDashboard(config)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Spyder Performance Dashboard")
    parser.add_argument('--port', type=int, default=8050, help='Dashboard port')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Configuration
    config = {
        'port': args.port,
        'debug': args.debug
    }
    
    # Create and start dashboard
    dashboard = create_performance_dashboard(config)
    
    try:
        dashboard.start()
    except KeyboardInterrupt:
        print("\nShutting down dashboard...")
        dashboard.stop()
