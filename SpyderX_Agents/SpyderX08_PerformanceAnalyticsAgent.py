#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX08_PerformanceAnalyticsAgent.py
Purpose: AI-Enhanced Performance Analytics and Reporting
Group: X (AI Agents)

Description:
    Replaces traditional reporting modules (SpyderK group) with an intelligent
    AI agent that provides deep performance insights, natural language reports,
    attribution analysis, and actionable recommendations for trading improvement.

    Replaced Modules:
    - SpyderK01_DailyReport
    - SpyderK02_TradeJournal  
    - SpyderK03_PerformanceMetrics
    
    This agent transforms raw trading data into meaningful insights that help
    traders understand their performance and make better decisions.

Author: AI Trading Assistant
Date: 2025-01-17
Version: 1.0.0

Dependencies:
    - ollama (for LLM integration)
    - numpy, pandas
    - plotly (for visualizations)
    - scipy
    - asyncio
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import hashlib
from scipy import stats
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# Import Spyder core components
from SpyderU01_DataStructures import (
    Portfolio, Position, Trade, OptionContract,
    Greeks, PnL
)
from SpyderU02_Configuration import config
from SpyderU03_Logger import SpyderLogger
from SpyderU04_EventManager import Event, EventType
from SpyderU12_AgentIntegration import SpyderBaseAgent, AgentState

# Report Types
class ReportType(Enum):
    """Types of performance reports"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    CUSTOM = "custom"
    REAL_TIME = "real_time"
    TRADE_ANALYSIS = "trade_analysis"
    STRATEGY_REVIEW = "strategy_review"

# Analysis Categories
class AnalysisCategory(Enum):
    """Performance analysis categories"""
    RETURNS = "returns"
    RISK = "risk"
    ATTRIBUTION = "attribution"
    TIMING = "timing"
    STRATEGY = "strategy"
    MARKET_CONDITIONS = "market_conditions"
    BEHAVIORAL = "behavioral"
    COMPARATIVE = "comparative"

# Performance Metrics
class MetricType(Enum):
    """Types of performance metrics"""
    ABSOLUTE_RETURN = "absolute_return"
    RISK_ADJUSTED_RETURN = "risk_adjusted_return"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    RECOVERY_TIME = "recovery_time"
    TRADE_EFFICIENCY = "trade_efficiency"

@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics"""
    period_start: datetime
    period_end: datetime
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_duration: int
    win_rate: float
    profit_factor: float
    average_win: float
    average_loss: float
    largest_win: float
    largest_loss: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_holding_period: timedelta
    best_day: Tuple[date, float]
    worst_day: Tuple[date, float]
    consecutive_wins: int
    consecutive_losses: int
    recovery_factor: float
    expectancy: float
    kelly_criterion: float
    risk_reward_ratio: float

@dataclass
class AttributionAnalysis:
    """Performance attribution breakdown"""
    strategy_attribution: Dict[str, float]
    timing_attribution: float
    selection_attribution: float
    market_attribution: float
    greek_attribution: Dict[str, float]  # Delta, Gamma, Theta, Vega
    factor_attribution: Dict[str, float]
    residual: float

@dataclass
class TradeAnalysis:
    """Detailed trade analysis"""
    trade_id: str
    symbol: str
    strategy: str
    entry_time: datetime
    exit_time: datetime
    holding_period: timedelta
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_percent: float
    max_profit: float
    max_loss: float
    efficiency: float  # Actual PnL / Max possible PnL
    entry_reason: str
    exit_reason: str
    market_condition: str
    mistakes: List[str]
    learnings: List[str]

@dataclass
class PerformanceReport:
    """Complete performance report"""
    report_type: ReportType
    period: Tuple[datetime, datetime]
    metrics: PerformanceMetrics
    attribution: AttributionAnalysis
    top_trades: List[TradeAnalysis]
    worst_trades: List[TradeAnalysis]
    strategy_breakdown: Dict[str, Dict[str, float]]
    risk_analysis: Dict[str, Any]
    market_correlation: Dict[str, float]
    behavioral_analysis: Dict[str, Any]
    ai_insights: List[str]
    recommendations: List[str]
    visualizations: Dict[str, Any]
    narrative: str

@dataclass
class RealTimeMetrics:
    """Real-time performance tracking"""
    timestamp: datetime
    daily_pnl: float
    open_positions: int
    position_pnl: float
    realized_pnl: float
    current_drawdown: float
    risk_utilization: float
    win_rate_today: float
    sharpe_rolling_30d: float
    var_95: float
    exposure: Dict[str, float]

class PerformanceAnalyticsAgent(SpyderBaseAgent):
    """
    AI-Enhanced Performance Analytics Agent
    
    Provides intelligent performance analysis, natural language reporting,
    and actionable insights for trading improvement.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Performance Analytics Agent"""
        super().__init__(config)
        
        # Agent configuration
        self.llm_model = config.get('analytics_llm_model', 'llama3.2:3b-instruct-q4_K_M')
        self.report_frequency = config.get('report_frequency', 'daily')
        self.metrics_window = config.get('metrics_window', 252)  # Trading days
        
        # Data storage
        self.trades_history: List[Trade] = []
        self.daily_pnl: pd.Series = pd.Series()
        self.positions_history: List[Dict[str, Any]] = []
        self.market_data_cache: Dict[str, pd.DataFrame] = {}
        
        # Performance tracking
        self.metrics_cache: Dict[str, PerformanceMetrics] = {}
        self.attribution_history: List[AttributionAnalysis] = []
        self.real_time_metrics: deque = deque(maxlen=1000)
        
        # Analysis state
        self.current_report: Optional[PerformanceReport] = None
        self.report_history: List[PerformanceReport] = []
        self.insights_cache: Dict[str, List[str]] = {}
        
        # Behavioral tracking
        self.trading_patterns: Dict[str, Any] = {}
        self.mistake_patterns: defaultdict = defaultdict(int)
        self.improvement_tracking: List[Dict[str, Any]] = []
        
        # Benchmarks
        self.benchmarks = {
            'SPY': None,  # SPY ETF performance
            'risk_free': 0.05,  # 5% annual risk-free rate
            'target_sharpe': 1.5,
            'target_win_rate': 0.6
        }
        
        # Report templates
        self.report_templates = self._load_report_templates()
        
        self.logger.info("Performance Analytics Agent initialized")

    async def initialize(self, event_manager=None, portfolio_manager=None):
        """Initialize agent with dependencies"""
        await super().initialize(event_manager)
        
        self.portfolio_manager = portfolio_manager
        
        # Subscribe to events
        if self.event_manager:
            self.event_manager.subscribe(EventType.TRADE_EXECUTED, self._handle_trade_executed)
            self.event_manager.subscribe(EventType.POSITION_UPDATED, self._handle_position_update)
            self.event_manager.subscribe(EventType.MARKET_CLOSE, self._handle_market_close)
            self.event_manager.subscribe(EventType.PORTFOLIO_UPDATE, self._handle_portfolio_update)
        
        # Start monitoring tasks
        asyncio.create_task(self._monitor_real_time_metrics())
        asyncio.create_task(self._generate_scheduled_reports())
        
        # Load historical data
        await self._load_historical_data()
        
        self.state = AgentState.RUNNING
        self.logger.info("Performance Analytics Agent initialized and running")

    async def generate_report(
        self,
        report_type: ReportType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        custom_params: Optional[Dict[str, Any]] = None
    ) -> PerformanceReport:
        """
        Generate comprehensive performance report
        
        Args:
            report_type: Type of report to generate
            start_date: Report start date
            end_date: Report end date
            custom_params: Custom report parameters
            
        Returns:
            Complete performance report with insights
        """
        try:
            # Determine period
            period = self._determine_report_period(report_type, start_date, end_date)
            
            # Calculate performance metrics
            metrics = await self._calculate_performance_metrics(period)
            
            # Perform attribution analysis
            attribution = await self._perform_attribution_analysis(period, metrics)
            
            # Analyze trades
            trade_analyses = await self._analyze_trades(period)
            top_trades = sorted(trade_analyses, key=lambda x: x.pnl, reverse=True)[:10]
            worst_trades = sorted(trade_analyses, key=lambda x: x.pnl)[:10]
            
            # Strategy breakdown
            strategy_breakdown = await self._analyze_strategy_performance(period)
            
            # Risk analysis
            risk_analysis = await self._perform_risk_analysis(period, metrics)
            
            # Market correlation
            market_correlation = await self._analyze_market_correlation(period)
            
            # Behavioral analysis
            behavioral_analysis = await self._perform_behavioral_analysis(period, trade_analyses)
            
            # Generate AI insights
            ai_insights = await self._generate_ai_insights(
                metrics, attribution, trade_analyses, behavioral_analysis
            )
            
            # Generate recommendations
            recommendations = await self._generate_recommendations(
                metrics, attribution, behavioral_analysis, risk_analysis
            )
            
            # Create visualizations
            visualizations = await self._create_visualizations(
                period, metrics, attribution, trade_analyses
            )
            
            # Generate narrative report
            narrative = await self._generate_narrative_report(
                report_type, period, metrics, attribution, ai_insights
            )
            
            # Create report object
            report = PerformanceReport(
                report_type=report_type,
                period=period,
                metrics=metrics,
                attribution=attribution,
                top_trades=top_trades,
                worst_trades=worst_trades,
                strategy_breakdown=strategy_breakdown,
                risk_analysis=risk_analysis,
                market_correlation=market_correlation,
                behavioral_analysis=behavioral_analysis,
                ai_insights=ai_insights,
                recommendations=recommendations,
                visualizations=visualizations,
                narrative=narrative
            )
            
            # Cache report
            self.current_report = report
            self.report_history.append(report)
            
            # Publish report event
            if self.event_manager:
                self.event_manager.publish(Event(
                    EventType.REPORT_GENERATED,
                    {'report': report}
                ))
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating report: {str(e)}")
            raise

    async def get_real_time_metrics(self) -> RealTimeMetrics:
        """Get current real-time performance metrics"""
        try:
            # Get current portfolio state
            if self.portfolio_manager:
                portfolio = self.portfolio_manager.get_portfolio()
            else:
                # Mock portfolio
                portfolio = Portfolio(cash=100000)
            
            # Calculate metrics
            daily_pnl = self._calculate_daily_pnl()
            position_pnl = sum(pos.unrealized_pnl for pos in portfolio.positions.values())
            realized_pnl = sum(trade.pnl for trade in self._get_todays_trades())
            
            # Current drawdown
            equity_curve = self._get_equity_curve()
            current_drawdown = self._calculate_current_drawdown(equity_curve)
            
            # Risk utilization
            risk_utilization = self._calculate_risk_utilization(portfolio)
            
            # Today's win rate
            todays_trades = self._get_todays_trades()
            win_rate_today = self._calculate_win_rate(todays_trades)
            
            # Rolling Sharpe
            sharpe_30d = self._calculate_rolling_sharpe(30)
            
            # VaR
            var_95 = self._calculate_var(equity_curve, 0.95)
            
            # Exposure by strategy
            exposure = self._calculate_exposure_breakdown(portfolio)
            
            metrics = RealTimeMetrics(
                timestamp=datetime.now(),
                daily_pnl=daily_pnl,
                open_positions=len(portfolio.positions),
                position_pnl=position_pnl,
                realized_pnl=realized_pnl,
                current_drawdown=current_drawdown,
                risk_utilization=risk_utilization,
                win_rate_today=win_rate_today,
                sharpe_rolling_30d=sharpe_30d,
                var_95=var_95,
                exposure=exposure
            )
            
            # Store in history
            self.real_time_metrics.append(metrics)
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating real-time metrics: {str(e)}")
            # Return default metrics
            return RealTimeMetrics(
                timestamp=datetime.now(),
                daily_pnl=0,
                open_positions=0,
                position_pnl=0,
                realized_pnl=0,
                current_drawdown=0,
                risk_utilization=0,
                win_rate_today=0,
                sharpe_rolling_30d=0,
                var_95=0,
                exposure={}
            )

    async def analyze_trade(self, trade: Trade) -> TradeAnalysis:
        """
        Perform detailed analysis of a single trade
        
        Args:
            trade: Trade to analyze
            
        Returns:
            Detailed trade analysis with AI insights
        """
        try:
            # Calculate basic metrics
            holding_period = trade.exit_time - trade.entry_time
            pnl_percent = (trade.pnl / (trade.entry_price * trade.quantity)) * 100
            
            # Get price path during trade
            price_path = await self._get_price_path(
                trade.symbol, trade.entry_time, trade.exit_time
            )
            
            # Calculate efficiency
            if price_path is not None and len(price_path) > 0:
                if trade.side == 'LONG':
                    max_price = price_path.max()
                    max_profit = (max_price - trade.entry_price) * trade.quantity
                    min_price = price_path.min()
                    max_loss = (min_price - trade.entry_price) * trade.quantity
                else:
                    min_price = price_path.min()
                    max_profit = (trade.entry_price - min_price) * trade.quantity
                    max_price = price_path.max()
                    max_loss = (trade.entry_price - max_price) * trade.quantity
                
                efficiency = trade.pnl / max_profit if max_profit > 0 else 0
            else:
                max_profit = trade.pnl if trade.pnl > 0 else 0
                max_loss = trade.pnl if trade.pnl < 0 else 0
                efficiency = 1.0 if trade.pnl > 0 else 0
            
            # Get market condition during trade
            market_condition = await self._get_market_condition(trade.entry_time)
            
            # Analyze entry and exit
            entry_analysis = await self._analyze_trade_entry(trade)
            exit_analysis = await self._analyze_trade_exit(trade)
            
            # Identify mistakes and learnings
            mistakes = await self._identify_trade_mistakes(
                trade, efficiency, entry_analysis, exit_analysis
            )
            learnings = await self._extract_trade_learnings(
                trade, mistakes, market_condition
            )
            
            analysis = TradeAnalysis(
                trade_id=trade.trade_id,
                symbol=trade.symbol,
                strategy=trade.strategy,
                entry_time=trade.entry_time,
                exit_time=trade.exit_time,
                holding_period=holding_period,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                quantity=trade.quantity,
                pnl=trade.pnl,
                pnl_percent=pnl_percent,
                max_profit=max_profit,
                max_loss=max_loss,
                efficiency=efficiency,
                entry_reason=entry_analysis.get('reason', 'Unknown'),
                exit_reason=exit_analysis.get('reason', 'Unknown'),
                market_condition=market_condition,
                mistakes=mistakes,
                learnings=learnings
            )
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing trade {trade.trade_id}: {str(e)}")
            # Return basic analysis
            return TradeAnalysis(
                trade_id=trade.trade_id,
                symbol=trade.symbol,
                strategy=trade.strategy,
                entry_time=trade.entry_time,
                exit_time=trade.exit_time,
                holding_period=trade.exit_time - trade.entry_time,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                quantity=trade.quantity,
                pnl=trade.pnl,
                pnl_percent=0,
                max_profit=0,
                max_loss=0,
                efficiency=0,
                entry_reason="Error",
                exit_reason="Error",
                market_condition="Unknown",
                mistakes=[],
                learnings=[]
            )

    async def _calculate_performance_metrics(
        self,
        period: Tuple[datetime, datetime]
    ) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics"""
        start_date, end_date = period
        
        # Get trades and PnL for period
        period_trades = [t for t in self.trades_history 
                        if start_date <= t.exit_time <= end_date]
        
        # Get equity curve
        equity_curve = self._get_equity_curve_for_period(start_date, end_date)
        returns = equity_curve.pct_change().dropna()
        
        # Basic return metrics
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1 if len(equity_curve) > 0 else 0
        days = (end_date - start_date).days
        annualized_return = ((1 + total_return) ** (252 / days) - 1) if days > 0 else 0
        
        # Volatility
        volatility = returns.std() * np.sqrt(252) if len(returns) > 0 else 0
        
        # Risk-adjusted returns
        excess_returns = returns - self.benchmarks['risk_free'] / 252
        sharpe_ratio = (excess_returns.mean() * 252) / (returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
        
        # Sortino ratio (downside deviation)
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0.01
        sortino_ratio = (annualized_return - self.benchmarks['risk_free']) / downside_std
        
        # Drawdown analysis
        drawdown_data = self._calculate_drawdown_series(equity_curve)
        max_drawdown = drawdown_data['max_drawdown']
        max_dd_duration = drawdown_data['max_duration']
        
        # Calmar ratio
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # Trade statistics
        winning_trades = [t for t in period_trades if t.pnl > 0]
        losing_trades = [t for t in period_trades if t.pnl <= 0]
        
        total_trades = len(period_trades)
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        # Profit factor
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Average metrics
        avg_win = gross_profit / len(winning_trades) if winning_trades else 0
        avg_loss = gross_loss / len(losing_trades) if losing_trades else 0
        
        # Extremes
        largest_win = max((t.pnl for t in period_trades), default=0)
        largest_loss = min((t.pnl for t in period_trades), default=0)
        
        # Consecutive wins/losses
        consecutive_wins = self._max_consecutive(period_trades, lambda t: t.pnl > 0)
        consecutive_losses = self._max_consecutive(period_trades, lambda t: t.pnl <= 0)
        
        # Average holding period
        if period_trades:
            holding_periods = [(t.exit_time - t.entry_time) for t in period_trades]
            avg_holding = sum(holding_periods, timedelta()) / len(holding_periods)
        else:
            avg_holding = timedelta()
        
        # Best/worst days
        daily_returns = equity_curve.resample('D').last().pct_change().dropna()
        if len(daily_returns) > 0:
            best_day = (daily_returns.idxmax().date(), daily_returns.max())
            worst_day = (daily_returns.idxmin().date(), daily_returns.min())
        else:
            best_day = (date.today(), 0)
            worst_day = (date.today(), 0)
        
        # Recovery factor
        recovery_factor = total_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # Expectancy
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        
        # Kelly Criterion
        if avg_loss > 0:
            win_loss_ratio = avg_win / avg_loss
            kelly = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        else:
            kelly = 0
        
        # Risk-reward ratio
        risk_reward = avg_win / avg_loss if avg_loss > 0 else float('inf')
        
        return PerformanceMetrics(
            period_start=start_date,
            period_end=end_date,
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_duration=max_dd_duration,
            win_rate=win_rate,
            profit_factor=profit_factor,
            average_win=avg_win,
            average_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            avg_holding_period=avg_holding,
            best_day=best_day,
            worst_day=worst_day,
            consecutive_wins=consecutive_wins,
            consecutive_losses=consecutive_losses,
            recovery_factor=recovery_factor,
            expectancy=expectancy,
            kelly_criterion=kelly,
            risk_reward_ratio=risk_reward
        )

    async def _perform_attribution_analysis(
        self,
        period: Tuple[datetime, datetime],
        metrics: PerformanceMetrics
    ) -> AttributionAnalysis:
        """Perform performance attribution analysis"""
        start_date, end_date = period
        
        # Get period data
        period_trades = [t for t in self.trades_history 
                        if start_date <= t.exit_time <= end_date]
        
        # Strategy attribution
        strategy_pnl = defaultdict(float)
        strategy_trades = defaultdict(int)
        
        for trade in period_trades:
            strategy_pnl[trade.strategy] += trade.pnl
            strategy_trades[trade.strategy] += 1
        
        total_pnl = sum(strategy_pnl.values())
        strategy_attribution = {
            strategy: pnl / total_pnl if total_pnl != 0 else 0
            for strategy, pnl in strategy_pnl.items()
        }
        
        # Timing vs selection attribution (simplified)
        # Would need entry/exit timing analysis vs optimal
        timing_attribution = 0.3  # Placeholder
        selection_attribution = 0.5  # Placeholder
        
        # Market attribution (beta component)
        market_attribution = await self._calculate_market_attribution(period, period_trades)
        
        # Greeks attribution for options
        greek_attribution = await self._calculate_greek_attribution(period_trades)
        
        # Factor attribution
        factor_attribution = {
            'volatility': 0.2,  # Placeholder
            'momentum': 0.15,   # Placeholder
            'mean_reversion': 0.1  # Placeholder
        }
        
        # Residual (unexplained)
        residual = 1.0 - (sum(strategy_attribution.values()) + 
                         timing_attribution + selection_attribution + 
                         market_attribution)
        
        return AttributionAnalysis(
            strategy_attribution=strategy_attribution,
            timing_attribution=timing_attribution,
            selection_attribution=selection_attribution,
            market_attribution=market_attribution,
            greek_attribution=greek_attribution,
            factor_attribution=factor_attribution,
            residual=residual
        )

    async def _analyze_trades(
        self,
        period: Tuple[datetime, datetime]
    ) -> List[TradeAnalysis]:
        """Analyze all trades in period"""
        start_date, end_date = period
        
        period_trades = [t for t in self.trades_history 
                        if start_date <= t.exit_time <= end_date]
        
        analyses = []
        for trade in period_trades:
            analysis = await self.analyze_trade(trade)
            analyses.append(analysis)
        
        return analyses

    async def _analyze_strategy_performance(
        self,
        period: Tuple[datetime, datetime]
    ) -> Dict[str, Dict[str, float]]:
        """Analyze performance by strategy"""
        start_date, end_date = period
        
        period_trades = [t for t in self.trades_history 
                        if start_date <= t.exit_time <= end_date]
        
        strategy_metrics = defaultdict(lambda: {
            'total_pnl': 0,
            'trades': 0,
            'wins': 0,
            'win_rate': 0,
            'avg_pnl': 0,
            'sharpe': 0,
            'max_drawdown': 0
        })
        
        # Group trades by strategy
        for trade in period_trades:
            strategy = trade.strategy
            strategy_metrics[strategy]['total_pnl'] += trade.pnl
            strategy_metrics[strategy]['trades'] += 1
            if trade.pnl > 0:
                strategy_metrics[strategy]['wins'] += 1
        
        # Calculate derived metrics
        for strategy, metrics in strategy_metrics.items():
            if metrics['trades'] > 0:
                metrics['win_rate'] = metrics['wins'] / metrics['trades']
                metrics['avg_pnl'] = metrics['total_pnl'] / metrics['trades']
                
                # Get strategy-specific returns
                strategy_trades = [t for t in period_trades if t.strategy == strategy]
                if strategy_trades:
                    strategy_returns = pd.Series([t.pnl for t in strategy_trades])
                    if strategy_returns.std() > 0:
                        metrics['sharpe'] = (strategy_returns.mean() * 252) / (strategy_returns.std() * np.sqrt(252))
        
        return dict(strategy_metrics)

    async def _perform_risk_analysis(
        self,
        period: Tuple[datetime, datetime],
        metrics: PerformanceMetrics
    ) -> Dict[str, Any]:
        """Perform comprehensive risk analysis"""
        # Get equity curve
        equity_curve = self._get_equity_curve_for_period(period[0], period[1])
        returns = equity_curve.pct_change().dropna()
        
        risk_analysis = {
            'var_95': np.percentile(returns, 5) if len(returns) > 0 else 0,
            'var_99': np.percentile(returns, 1) if len(returns) > 0 else 0,
            'cvar_95': returns[returns <= np.percentile(returns, 5)].mean() if len(returns) > 0 else 0,
            'downside_deviation': returns[returns < 0].std() * np.sqrt(252) if len(returns[returns < 0]) > 0 else 0,
            'upside_deviation': returns[returns > 0].std() * np.sqrt(252) if len(returns[returns > 0]) > 0 else 0,
            'skewness': stats.skew(returns) if len(returns) > 3 else 0,
            'kurtosis': stats.kurtosis(returns) if len(returns) > 3 else 0,
            'max_consecutive_losses': metrics.consecutive_losses,
            'recovery_time_days': self._calculate_recovery_time(equity_curve),
            'ulcer_index': self._calculate_ulcer_index(equity_curve),
            'tail_ratio': self._calculate_tail_ratio(returns),
            'capture_ratio': await self._calculate_capture_ratio(returns, period)
        }
        
        return risk_analysis

    async def _analyze_market_correlation(
        self,
        period: Tuple[datetime, datetime]
    ) -> Dict[str, float]:
        """Analyze correlation with market benchmarks"""
        # Get strategy returns
        equity_curve = self._get_equity_curve_for_period(period[0], period[1])
        strategy_returns = equity_curve.pct_change().dropna()
        
        # Get benchmark returns (would fetch real data)
        spy_returns = await self._get_benchmark_returns('SPY', period)
        vix_levels = await self._get_benchmark_returns('VIX', period)
        
        correlations = {}
        
        if len(strategy_returns) > 30 and spy_returns is not None:
            correlations['SPY'] = strategy_returns.corr(spy_returns)
            
            # Rolling correlation
            correlations['SPY_rolling_30d'] = strategy_returns.rolling(30).corr(spy_returns).iloc[-1]
        
        if vix_levels is not None:
            correlations['VIX'] = strategy_returns.corr(vix_levels)
        
        # Beta calculation
        if spy_returns is not None and len(strategy_returns) > 30:
            covariance = strategy_returns.cov(spy_returns)
            spy_variance = spy_returns.var()
            correlations['beta'] = covariance / spy_variance if spy_variance > 0 else 0
        
        return correlations

    async def _perform_behavioral_analysis(
        self,
        period: Tuple[datetime, datetime],
        trade_analyses: List[TradeAnalysis]
    ) -> Dict[str, Any]:
        """Analyze trading behavior and psychology"""
        
        behavioral_metrics = {
            'overtrading_score': 0,
            'revenge_trading_score': 0,
            'discipline_score': 0,
            'patience_score': 0,
            'consistency_score': 0,
            'emotional_stability': 0,
            'common_mistakes': {},
            'time_of_day_performance': {},
            'day_of_week_performance': {},
            'winning_streak_behavior': {},
            'losing_streak_behavior': {}
        }
        
        # Overtrading analysis
        daily_trades = defaultdict(int)
        for trade in trade_analyses:
            daily_trades[trade.entry_time.date()] += 1
        
        avg_daily_trades = np.mean(list(daily_trades.values())) if daily_trades else 0
        std_daily_trades = np.std(list(daily_trades.values())) if len(daily_trades) > 1 else 0
        
        # Days with excessive trading
        if std_daily_trades > 0:
            excessive_days = sum(1 for count in daily_trades.values() 
                               if count > avg_daily_trades + 2 * std_daily_trades)
            behavioral_metrics['overtrading_score'] = excessive_days / len(daily_trades) if daily_trades else 0
        
        # Revenge trading (quick re-entry after loss)
        revenge_trades = 0
        for i in range(1, len(trade_analyses)):
            if (trade_analyses[i-1].pnl < 0 and 
                (trade_analyses[i].entry_time - trade_analyses[i-1].exit_time).seconds < 300):
                revenge_trades += 1
        
        behavioral_metrics['revenge_trading_score'] = revenge_trades / len(trade_analyses) if trade_analyses else 0
        
        # Discipline score (following exit rules)
        disciplined_exits = sum(1 for trade in trade_analyses 
                               if 'stop_loss' in trade.exit_reason or 'target' in trade.exit_reason)
        behavioral_metrics['discipline_score'] = disciplined_exits / len(trade_analyses) if trade_analyses else 0
        
        # Time of day analysis
        for trade in trade_analyses:
            hour = trade.entry_time.hour
            if hour not in behavioral_metrics['time_of_day_performance']:
                behavioral_metrics['time_of_day_performance'][hour] = []
            behavioral_metrics['time_of_day_performance'][hour].append(trade.pnl)
        
        # Average by hour
        for hour, pnls in behavioral_metrics['time_of_day_performance'].items():
            behavioral_metrics['time_of_day_performance'][hour] = np.mean(pnls)
        
        # Common mistakes
        mistake_counts = defaultdict(int)
        for trade in trade_analyses:
            for mistake in trade.mistakes:
                mistake_counts[mistake] += 1
        
        behavioral_metrics['common_mistakes'] = dict(mistake_counts)
        
        # Streak behavior
        current_streak = 0
        streak_after_trades = {'3_wins': [], '3_losses': []}
        
        for i, trade in enumerate(trade_analyses):
            if trade.pnl > 0:
                current_streak = current_streak + 1 if current_streak > 0 else 1
            else:
                current_streak = current_streak - 1 if current_streak < 0 else -1
            
            # Check behavior after streaks
            if current_streak >= 3 and i < len(trade_analyses) - 1:
                streak_after_trades['3_wins'].append(trade_analyses[i+1].pnl)
            elif current_streak <= -3 and i < len(trade_analyses) - 1:
                streak_after_trades['3_losses'].append(trade_analyses[i+1].pnl)
        
        # Analyze post-streak performance
        if streak_after_trades['3_wins']:
            behavioral_metrics['winning_streak_behavior'] = {
                'avg_next_trade': np.mean(streak_after_trades['3_wins']),
                'continues_winning': sum(1 for p in streak_after_trades['3_wins'] if p > 0) / len(streak_after_trades['3_wins'])
            }
        
        if streak_after_trades['3_losses']:
            behavioral_metrics['losing_streak_behavior'] = {
                'avg_next_trade': np.mean(streak_after_trades['3_losses']),
                'recovers': sum(1 for p in streak_after_trades['3_losses'] if p > 0) / len(streak_after_trades['3_losses'])
            }
        
        return behavioral_metrics

    async def _generate_ai_insights(
        self,
        metrics: PerformanceMetrics,
        attribution: AttributionAnalysis,
        trade_analyses: List[TradeAnalysis],
        behavioral_analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate AI-powered insights"""
        
        # Prepare context for LLM
        context = {
            'sharpe_ratio': metrics.sharpe_ratio,
            'win_rate': metrics.win_rate,
            'profit_factor': metrics.profit_factor,
            'max_drawdown': metrics.max_drawdown,
            'best_strategy': max(attribution.strategy_attribution.items(), key=lambda x: x[1])[0] if attribution.strategy_attribution else 'None',
            'worst_strategy': min(attribution.strategy_attribution.items(), key=lambda x: x[1])[0] if attribution.strategy_attribution else 'None',
            'common_mistakes': behavioral_analysis.get('common_mistakes', {}),
            'overtrading_score': behavioral_analysis.get('overtrading_score', 0),
            'discipline_score': behavioral_analysis.get('discipline_score', 0)
        }
        
        prompt = f"""
        Analyze this trading performance and provide key insights:
        
        Performance Metrics:
        - Sharpe Ratio: {context['sharpe_ratio']:.2f}
        - Win Rate: {context['win_rate']:.2%}
        - Profit Factor: {context['profit_factor']:.2f}
        - Max Drawdown: {context['max_drawdown']:.2%}
        
        Strategy Performance:
        - Best: {context['best_strategy']}
        - Worst: {context['worst_strategy']}
        
        Behavioral Patterns:
        - Overtrading Score: {context['overtrading_score']:.2f}
        - Discipline Score: {context['discipline_score']:.2f}
        - Common Mistakes: {list(context['common_mistakes'].keys())[:3]}
        
        Provide 5-7 specific, actionable insights about:
        1. What's working well
        2. Areas for improvement
        3. Risk management observations
        4. Behavioral patterns to address
        5. Strategic recommendations
        
        Format as a JSON array of insight strings.
        """
        
        try:
            response = await asyncio.wait_for(self._query_llm(prompt), timeout=5.0)
            insights = json.loads(response)
            return insights[:7]  # Limit to 7 insights
        except:
            # Fallback insights based on metrics
            insights = []
            
            if metrics.sharpe_ratio > 1.5:
                insights.append("Excellent risk-adjusted returns with Sharpe ratio above 1.5")
            elif metrics.sharpe_ratio < 0.5:
                insights.append("Risk-adjusted returns need improvement - consider reducing position sizes")
            
            if metrics.win_rate > 0.6:
                insights.append(f"Strong win rate of {metrics.win_rate:.1%} indicates good trade selection")
            elif metrics.win_rate < 0.4:
                insights.append("Low win rate suggests need for better entry criteria")
            
            if metrics.max_drawdown > 0.2:
                insights.append(f"Maximum drawdown of {metrics.max_drawdown:.1%} is concerning - implement stricter risk controls")
            
            if behavioral_analysis.get('overtrading_score', 0) > 0.2:
                insights.append("Signs of overtrading detected - consider daily trade limits")
            
            if metrics.profit_factor < 1.5:
                insights.append("Profit factor below 1.5 - focus on improving risk/reward ratios")
            
            return insights

    async def _generate_recommendations(
        self,
        metrics: PerformanceMetrics,
        attribution: AttributionAnalysis,
        behavioral_analysis: Dict[str, Any],
        risk_analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable recommendations"""
        
        recommendations = []
        
        # Risk management recommendations
        if metrics.max_drawdown > 0.15:
            recommendations.append(
                f"Implement maximum daily loss limit of {metrics.max_drawdown * 0.3:.1%} "
                f"to prevent drawdowns exceeding {metrics.max_drawdown:.1%}"
            )
        
        # Win rate improvements
        if metrics.win_rate < 0.5:
            recommendations.append(
                "Improve trade selection criteria - consider adding confirmation signals "
                "to increase win rate above 50%"
            )
        
        # Position sizing
        if metrics.kelly_criterion > 0 and metrics.kelly_criterion < 0.25:
            recommendations.append(
                f"Optimal position sizing suggests {metrics.kelly_criterion:.1%} of capital per trade "
                f"based on current win rate and risk/reward"
            )
        
        # Strategy recommendations
        if attribution.strategy_attribution:
            best_strategy = max(attribution.strategy_attribution.items(), key=lambda x: x[1])[0]
            worst_strategy = min(attribution.strategy_attribution.items(), key=lambda x: x[1])[0]
            
            recommendations.append(
                f"Increase allocation to {best_strategy} strategy and reduce {worst_strategy} exposure"
            )
        
        # Behavioral recommendations  
        if behavioral_analysis.get('revenge_trading_score', 0) > 0.1:
            recommendations.append(
                "Implement mandatory 15-minute cooldown period after losing trades "
                "to prevent emotional revenge trading"
            )
        
        # Time-based recommendations
        if 'time_of_day_performance' in behavioral_analysis:
            best_hours = sorted(
                behavioral_analysis['time_of_day_performance'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            if best_hours:
                best_hours_str = ', '.join([f"{h}:00" for h, _ in best_hours])
                recommendations.append(
                    f"Focus trading during your most profitable hours: {best_hours_str}"
                )
        
        # Risk recommendations
        if risk_analysis.get('tail_ratio', 0) < 1:
            recommendations.append(
                "Tail risk is concerning - consider implementing tail risk hedging strategies"
            )
        
        return recommendations[:7]  # Limit to 7 recommendations

    async def _create_visualizations(
        self,
        period: Tuple[datetime, datetime],
        metrics: PerformanceMetrics,
        attribution: AttributionAnalysis,
        trade_analyses: List[TradeAnalysis]
    ) -> Dict[str, Any]:
        """Create performance visualizations"""
        
        visualizations = {}
        
        # Equity curve
        equity_curve = self._get_equity_curve_for_period(period[0], period[1])
        
        # 1. Equity Curve with Drawdown
        fig_equity = make_subplots(
            rows=2, cols=1,
            row_heights=[0.7, 0.3],
            shared_xaxes=True,
            vertical_spacing=0.05
        )
        
        # Equity curve
        fig_equity.add_trace(
            go.Scatter(
                x=equity_curve.index,
                y=equity_curve.values,
                name='Portfolio Value',
                line=dict(color='blue', width=2)
            ),
            row=1, col=1
        )
        
        # Drawdown
        drawdown = self._calculate_drawdown_series(equity_curve)['drawdown_series']
        fig_equity.add_trace(
            go.Scatter(
                x=drawdown.index,
                y=drawdown.values * 100,
                name='Drawdown %',
                fill='tozeroy',
                line=dict(color='red', width=1)
            ),
            row=2, col=1
        )
        
        fig_equity.update_layout(
            title='Portfolio Equity Curve and Drawdown',
            height=600,
            showlegend=True
        )
        
        visualizations['equity_curve'] = fig_equity.to_json()
        
        # 2. Returns Distribution
        returns = equity_curve.pct_change().dropna()
        fig_returns = go.Figure()
        
        fig_returns.add_trace(go.Histogram(
            x=returns * 100,
            nbinsx=50,
            name='Daily Returns',
            marker_color='lightblue'
        ))
        
        # Add normal distribution overlay
        x_range = np.linspace(returns.min() * 100, returns.max() * 100, 100)
        normal_dist = stats.norm.pdf(x_range, returns.mean() * 100, returns.std() * 100)
        fig_returns.add_trace(go.Scatter(
            x=x_range,
            y=normal_dist * len(returns) * (x_range[1] - x_range[0]),
            name='Normal Distribution',
            line=dict(color='red', width=2)
        ))
        
        fig_returns.update_layout(
            title='Returns Distribution',
            xaxis_title='Daily Return %',
            yaxis_title='Frequency'
        )
        
        visualizations['returns_distribution'] = fig_returns.to_json()
        
        # 3. Strategy Performance
        if attribution.strategy_attribution:
            strategies = list(attribution.strategy_attribution.keys())
            values = list(attribution.strategy_attribution.values())
            
            fig_strategy = go.Figure(data=[
                go.Bar(x=strategies, y=values, marker_color='green')
            ])
            
            fig_strategy.update_layout(
                title='Performance Attribution by Strategy',
                xaxis_title='Strategy',
                yaxis_title='Attribution %'
            )
            
            visualizations['strategy_attribution'] = fig_strategy.to_json()
        
        # 4. Monthly Returns Heatmap
        monthly_returns = equity_curve.resample('M').last().pct_change() * 100
        if len(monthly_returns) > 3:
            # Reshape for heatmap
            years = monthly_returns.index.year.unique()
            months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            
            heatmap_data = []
            for year in years:
                year_data = []
                for month in range(1, 13):
                    try:
                        value = monthly_returns[
                            (monthly_returns.index.year == year) & 
                            (monthly_returns.index.month == month)
                        ].iloc[0]
                    except:
                        value = 0
                    year_data.append(value)
                heatmap_data.append(year_data)
            
            fig_heatmap = go.Figure(data=go.Heatmap(
                z=heatmap_data,
                x=months,
                y=years,
                colorscale='RdYlGn',
                zmid=0
            ))
            
            fig_heatmap.update_layout(
                title='Monthly Returns Heatmap (%)',
                xaxis_title='Month',
                yaxis_title='Year'
            )
            
            visualizations['monthly_heatmap'] = fig_heatmap.to_json()
        
        # 5. Win/Loss Analysis
        if trade_analyses:
            wins = [t.pnl for t in trade_analyses if t.pnl > 0]
            losses = [abs(t.pnl) for t in trade_analyses if t.pnl < 0]
            
            fig_winloss = go.Figure()
            
            if wins:
                fig_winloss.add_trace(go.Box(
                    y=wins,
                    name='Wins',
                    marker_color='green'
                ))
            
            if losses:
                fig_winloss.add_trace(go.Box(
                    y=losses,
                    name='Losses',
                    marker_color='red'
                ))
            
            fig_winloss.update_layout(
                title='Win/Loss Distribution',
                yaxis_title='P&L ($)'
            )
            
            visualizations['win_loss_distribution'] = fig_winloss.to_json()
        
        return visualizations

    async def _generate_narrative_report(
        self,
        report_type: ReportType,
        period: Tuple[datetime, datetime],
        metrics: PerformanceMetrics,
        attribution: AttributionAnalysis,
        insights: List[str]
    ) -> str:
        """Generate natural language narrative report"""
        
        # Prepare context
        period_str = f"{period[0].strftime('%B %d, %Y')} to {period[1].strftime('%B %d, %Y')}"
        
        prompt = f"""
        Write a professional investment performance report narrative for the period {period_str}.
        
        Key Metrics:
        - Total Return: {metrics.total_return:.2%}
        - Sharpe Ratio: {metrics.sharpe_ratio:.2f}
        - Win Rate: {metrics.win_rate:.2%}
        - Max Drawdown: {metrics.max_drawdown:.2%}
        - Total Trades: {metrics.total_trades}
        
        Key Insights:
        {chr(10).join([f"- {insight}" for insight in insights[:3]])}
        
        Write a 3-4 paragraph executive summary that:
        1. Opens with overall performance summary
        2. Discusses key drivers of performance
        3. Addresses risk management and drawdowns
        4. Concludes with forward-looking perspective
        
        Use professional financial language appropriate for investors.
        """
        
        try:
            narrative = await asyncio.wait_for(self._query_llm(prompt), timeout=10.0)
            return narrative
        except:
            # Fallback narrative
            narrative = f"""
            Performance Summary for {period_str}
            
            The portfolio generated a total return of {metrics.total_return:.2%} during the reporting period, 
            with a Sharpe ratio of {metrics.sharpe_ratio:.2f}. The strategy executed {metrics.total_trades} trades 
            with a win rate of {metrics.win_rate:.1%} and a profit factor of {metrics.profit_factor:.2f}.
            
            Risk management remained a key focus, with maximum drawdown limited to {metrics.max_drawdown:.1%}. 
            The portfolio maintained disciplined position sizing and exit strategies, resulting in an average 
            win of ${metrics.average_win:.2f} versus an average loss of ${metrics.average_loss:.2f}.
            
            Looking forward, the strategy continues to adapt to market conditions while maintaining strict 
            risk controls. Key areas of focus include improving trade selection criteria and optimizing 
            position sizing based on market volatility.
            """
            
            return narrative

    def _determine_report_period(
        self,
        report_type: ReportType,
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> Tuple[datetime, datetime]:
        """Determine report period based on type"""
        
        if start_date and end_date:
            return (start_date, end_date)
        
        end = end_date or datetime.now()
        
        if report_type == ReportType.DAILY:
            start = end.replace(hour=0, minute=0, second=0, microsecond=0)
        elif report_type == ReportType.WEEKLY:
            start = end - timedelta(days=7)
        elif report_type == ReportType.MONTHLY:
            start = end - timedelta(days=30)
        elif report_type == ReportType.QUARTERLY:
            start = end - timedelta(days=90)
        elif report_type == ReportType.ANNUAL:
            start = end - timedelta(days=365)
        else:
            start = end - timedelta(days=30)  # Default to monthly
        
        return (start, end)

    def _get_equity_curve(self) -> pd.Series:
        """Get complete equity curve"""
        if not self.daily_pnl.empty:
            return self.daily_pnl.cumsum() + 100000  # Assuming 100k starting capital
        else:
            # Generate from trades
            return self._build_equity_curve_from_trades()

    def _get_equity_curve_for_period(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> pd.Series:
        """Get equity curve for specific period"""
        full_curve = self._get_equity_curve()
        return full_curve[(full_curve.index >= start_date) & (full_curve.index <= end_date)]

    def _build_equity_curve_from_trades(self) -> pd.Series:
        """Build equity curve from trade history"""
        if not self.trades_history:
            return pd.Series([100000], index=[datetime.now()])
        
        # Sort trades by exit time
        sorted_trades = sorted(self.trades_history, key=lambda x: x.exit_time)
        
        # Build cumulative P&L
        dates = []
        cumulative_pnl = []
        running_pnl = 0
        
        for trade in sorted_trades:
            running_pnl += trade.pnl
            dates.append(trade.exit_time)
            cumulative_pnl.append(100000 + running_pnl)  # Starting capital + P&L
        
        return pd.Series(cumulative_pnl, index=dates)

    def _calculate_drawdown_series(self, equity_curve: pd.Series) -> Dict[str, Any]:
        """Calculate drawdown series and statistics"""
        if len(equity_curve) < 2:
            return {
                'drawdown_series': pd.Series([0]),
                'max_drawdown': 0,
                'max_duration': 0
            }
        
        # Calculate running maximum
        running_max = equity_curve.expanding().max()
        
        # Calculate drawdown
        drawdown = (equity_curve - running_max) / running_max
        
        # Find maximum drawdown
        max_drawdown = drawdown.min()
        
        # Calculate drawdown duration
        drawdown_start = None
        max_duration = 0
        current_duration = 0
        
        for i in range(len(drawdown)):
            if drawdown.iloc[i] < 0:
                if drawdown_start is None:
                    drawdown_start = i
                current_duration = i - drawdown_start
            else:
                if drawdown_start is not None:
                    max_duration = max(max_duration, current_duration)
                    drawdown_start = None
                    current_duration = 0
        
        return {
            'drawdown_series': drawdown,
            'max_drawdown': abs(max_drawdown),
            'max_duration': max_duration
        }

    def _max_consecutive(self, trades: List[Trade], condition) -> int:
        """Calculate maximum consecutive trades meeting condition"""
        if not trades:
            return 0
        
        max_streak = 0
        current_streak = 0
        
        for trade in trades:
            if condition(trade):
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return max_streak

    def _calculate_daily_pnl(self) -> float:
        """Calculate today's P&L"""
        today = datetime.now().date()
        todays_trades = [t for t in self.trades_history if t.exit_time.date() == today]
        return sum(t.pnl for t in todays_trades)

    def _get_todays_trades(self) -> List[Trade]:
        """Get today's trades"""
        today = datetime.now().date()
        return [t for t in self.trades_history if t.exit_time.date() == today]

    def _calculate_current_drawdown(self, equity_curve: pd.Series) -> float:
        """Calculate current drawdown"""
        if len(equity_curve) < 2:
            return 0
        
        current_value = equity_curve.iloc[-1]
        running_max = equity_curve.max()
        
        return (current_value - running_max) / running_max if running_max > 0 else 0

    def _calculate_risk_utilization(self, portfolio: Portfolio) -> float:
        """Calculate current risk utilization"""
        # Simplified - would calculate based on position sizes and risk limits
        position_value = sum(abs(pos.quantity * pos.current_price) 
                           for pos in portfolio.positions.values())
        total_capital = portfolio.cash + position_value
        
        return position_value / total_capital if total_capital > 0 else 0

    def _calculate_win_rate(self, trades: List[Trade]) -> float:
        """Calculate win rate for trades"""
        if not trades:
            return 0
        
        wins = sum(1 for t in trades if t.pnl > 0)
        return wins / len(trades)

    def _calculate_rolling_sharpe(self, days: int) -> float:
        """Calculate rolling Sharpe ratio"""
        equity_curve = self._get_equity_curve()
        
        if len(equity_curve) < days:
            return 0
        
        recent_returns = equity_curve.pct_change().dropna().tail(days)
        
        if len(recent_returns) < 2 or recent_returns.std() == 0:
            return 0
        
        return (recent_returns.mean() * 252) / (recent_returns.std() * np.sqrt(252))

    def _calculate_var(self, returns: pd.Series, confidence: float) -> float:
        """Calculate Value at Risk"""
        if len(returns) < 10:
            return 0
        
        return np.percentile(returns.pct_change().dropna(), (1 - confidence) * 100)

    def _calculate_exposure_breakdown(self, portfolio: Portfolio) -> Dict[str, float]:
        """Calculate exposure by strategy"""
        exposure = defaultdict(float)
        
        for position in portfolio.positions.values():
            strategy = getattr(position, 'strategy', 'Unknown')
            exposure[strategy] += abs(position.quantity * position.current_price)
        
        return dict(exposure)

    async def _get_price_path(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[pd.Series]:
        """Get price path for period"""
        # Would fetch from market data
        # Mock implementation
        return None

    async def _get_market_condition(self, timestamp: datetime) -> str:
        """Get market condition at timestamp"""
        # Would analyze market state
        return "Normal"

    async def _analyze_trade_entry(self, trade: Trade) -> Dict[str, Any]:
        """Analyze trade entry"""
        return {'reason': 'Signal triggered'}

    async def _analyze_trade_exit(self, trade: Trade) -> Dict[str, Any]:
        """Analyze trade exit"""
        return {'reason': 'Target reached' if trade.pnl > 0 else 'Stop loss'}

    async def _identify_trade_mistakes(
        self,
        trade: Trade,
        efficiency: float,
        entry_analysis: Dict[str, Any],
        exit_analysis: Dict[str, Any]
    ) -> List[str]:
        """Identify mistakes in trade"""
        mistakes = []
        
        if efficiency < 0.3:
            mistakes.append("Poor timing - captured less than 30% of potential profit")
        
        if trade.pnl < 0 and abs(trade.pnl) > trade.entry_price * trade.quantity * 0.02:
            mistakes.append("Position size too large relative to stop loss")
        
        # Track patterns
        for mistake in mistakes:
            self.mistake_patterns[mistake] += 1
        
        return mistakes

    async def _extract_trade_learnings(
        self,
        trade: Trade,
        mistakes: List[str],
        market_condition: str
    ) -> List[str]:
        """Extract learnings from trade"""
        learnings = []
        
        if trade.pnl > 0 and not mistakes:
            learnings.append(f"Well-executed {trade.strategy} trade in {market_condition} conditions")
        
        if mistakes:
            learnings.append(f"Review {', '.join(mistakes)} for future improvement")
        
        return learnings

    async def _calculate_market_attribution(
        self,
        period: Tuple[datetime, datetime],
        trades: List[Trade]
    ) -> float:
        """Calculate market beta attribution"""
        # Simplified - would calculate actual beta exposure
        return 0.1

    async def _calculate_greek_attribution(
        self,
        trades: List[Trade]
    ) -> Dict[str, float]:
        """Calculate attribution from option Greeks"""
        greek_pnl = {
            'delta': 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0
        }
        
        # Would calculate actual Greek P&L from position Greeks
        # Placeholder distribution
        total_pnl = sum(t.pnl for t in trades)
        if total_pnl != 0:
            greek_pnl['delta'] = 0.4  # 40% from directional
            greek_pnl['theta'] = 0.3  # 30% from time decay
            greek_pnl['vega'] = 0.2   # 20% from volatility
            greek_pnl['gamma'] = 0.1  # 10% from gamma
        
        return greek_pnl

    def _calculate_recovery_time(self, equity_curve: pd.Series) -> int:
        """Calculate average recovery time from drawdowns"""
        if len(equity_curve) < 2:
            return 0
        
        # Find drawdown periods and recovery times
        running_max = equity_curve.expanding().max()
        in_drawdown = equity_curve < running_max
        
        recovery_times = []
        drawdown_start = None
        
        for i in range(len(equity_curve)):
            if in_drawdown.iloc[i] and drawdown_start is None:
                drawdown_start = i
            elif not in_drawdown.iloc[i] and drawdown_start is not None:
                recovery_times.append(i - drawdown_start)
                drawdown_start = None
        
        return int(np.mean(recovery_times)) if recovery_times else 0

    def _calculate_ulcer_index(self, equity_curve: pd.Series) -> float:
        """Calculate Ulcer Index (measures downside volatility)"""
        if len(equity_curve) < 2:
            return 0
        
        # Calculate percentage drawdown
        running_max = equity_curve.expanding().max()
        dd_pct = ((equity_curve - running_max) / running_max * 100) ** 2
        
        # Ulcer Index is square root of mean squared drawdown
        return np.sqrt(dd_pct.mean())

    def _calculate_tail_ratio(self, returns: pd.Series) -> float:
        """Calculate tail ratio (right tail / left tail)"""
        if len(returns) < 20:
            return 1.0
        
        # 95th percentile / 5th percentile
        right_tail = abs(np.percentile(returns, 95))
        left_tail = abs(np.percentile(returns, 5))
        
        return right_tail / left_tail if left_tail > 0 else float('inf')

    async def _calculate_capture_ratio(
        self,
        returns: pd.Series,
        period: Tuple[datetime, datetime]
    ) -> Dict[str, float]:
        """Calculate upside/downside capture ratios"""
        # Get benchmark returns
        benchmark_returns = await self._get_benchmark_returns('SPY', period)
        
        if benchmark_returns is None or len(returns) != len(benchmark_returns):
            return {'upside_capture': 0, 'downside_capture': 0}
        
        # Align indices
        aligned = pd.DataFrame({
            'strategy': returns,
            'benchmark': benchmark_returns
        }).dropna()
        
        # Upside capture
        up_days = aligned[aligned['benchmark'] > 0]
        if len(up_days) > 0:
            upside_capture = (up_days['strategy'].mean() / up_days['benchmark'].mean()) * 100
        else:
            upside_capture = 0
        
        # Downside capture
        down_days = aligned[aligned['benchmark'] < 0]
        if len(down_days) > 0:
            downside_capture = (down_days['strategy'].mean() / down_days['benchmark'].mean()) * 100
        else:
            downside_capture = 0
        
        return {
            'upside_capture': upside_capture,
            'downside_capture': downside_capture
        }

    async def _get_benchmark_returns(
        self,
        symbol: str,
        period: Tuple[datetime, datetime]
    ) -> Optional[pd.Series]:
        """Get benchmark returns for period"""
        # Would fetch actual benchmark data
        # Mock implementation
        dates = pd.date_range(period[0], period[1], freq='D')
        returns = np.random.normal(0.0005, 0.01, len(dates))  # Mock returns
        return pd.Series(returns, index=dates)

    def _load_report_templates(self) -> Dict[str, str]:
        """Load report templates"""
        return {
            'daily': "Daily Performance Report",
            'weekly': "Weekly Performance Summary",
            'monthly': "Monthly Performance Analysis",
            'quarterly': "Quarterly Investment Report",
            'annual': "Annual Performance Review"
        }

    async def _load_historical_data(self):
        """Load historical trading data"""
        # Would load from database
        self.logger.info("Loading historical data")

    async def _monitor_real_time_metrics(self):
        """Monitor and update real-time metrics"""
        while self.state == AgentState.RUNNING:
            try:
                # Update metrics every minute
                metrics = await self.get_real_time_metrics()
                
                # Check for alerts
                if metrics.current_drawdown < -0.05:  # 5% drawdown
                    if self.event_manager:
                        self.event_manager.publish(Event(
                            EventType.RISK_ALERT,
                            {'type': 'drawdown', 'value': metrics.current_drawdown}
                        ))
                
                await asyncio.sleep(60)  # Update every minute
                
            except Exception as e:
                self.logger.error(f"Error monitoring metrics: {str(e)}")

    async def _generate_scheduled_reports(self):
        """Generate reports on schedule"""
        while self.state == AgentState.RUNNING:
            try:
                now = datetime.now()
                
                # Daily report at market close
                if now.hour == 16 and now.minute == 0:
                    report = await self.generate_report(ReportType.DAILY)
                    self.logger.info("Generated daily report")
                
                # Weekly report on Fridays
                if now.weekday() == 4 and now.hour == 17:
                    report = await self.generate_report(ReportType.WEEKLY)
                    self.logger.info("Generated weekly report")
                
                # Monthly report on last day
                tomorrow = now + timedelta(days=1)
                if tomorrow.month != now.month and now.hour == 17:
                    report = await self.generate_report(ReportType.MONTHLY)
                    self.logger.info("Generated monthly report")
                
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                self.logger.error(f"Error generating scheduled report: {str(e)}")

    async def _handle_trade_executed(self, event: Event):
        """Handle trade execution events"""
        if hasattr(event, 'data') and 'trade' in event.data:
            trade = event.data['trade']
            self.trades_history.append(trade)
            
            # Update daily P&L
            today = datetime.now().date()
            if today not in self.daily_pnl.index:
                self.daily_pnl[today] = trade.pnl
            else:
                self.daily_pnl[today] += trade.pnl

    async def _handle_position_update(self, event: Event):
        """Handle position update events"""
        if hasattr(event, 'data'):
            position_snapshot = {
                'timestamp': datetime.now(),
                'positions': event.data.get('positions', {}),
                'total_value': event.data.get('total_value', 0)
            }
            self.positions_history.append(position_snapshot)

    async def _handle_market_close(self, event: Event):
        """Handle market close events"""
        # Generate daily report
        asyncio.create_task(self.generate_report(ReportType.DAILY))

    async def _handle_portfolio_update(self, event: Event):
        """Handle portfolio update events"""
        # Update real-time metrics
        asyncio.create_task(self.get_real_time_metrics())

    async def _query_llm(self, prompt: str) -> str:
        """Query LLM for insights and narratives"""
        # Mock implementation
        if "insights" in prompt:
            return json.dumps([
                "Strong performance driven by disciplined risk management and favorable market conditions",
                "Win rate improvement suggests enhanced trade selection criteria are working effectively",
                "Consider reducing position sizes during high volatility periods to protect capital",
                "Time-of-day analysis shows best performance during first hour of trading",
                "Strategy diversification helping to reduce overall portfolio volatility",
                "Behavioral patterns indicate good emotional control with minimal revenge trading",
                "Focus on maintaining current discipline while exploring additional income strategies"
            ])
        elif "narrative" in prompt:
            return """
            The portfolio delivered strong risk-adjusted returns during the reporting period, demonstrating 
            the effectiveness of our systematic options trading approach. The combination of disciplined 
            risk management and adaptive strategy selection resulted in consistent performance across 
            varying market conditions.
            
            Key performance drivers included improved trade selection criteria, which increased our win 
            rate, and dynamic position sizing that helped limit drawdowns during volatile periods. The 
            strategy successfully captured premium from options time decay while managing directional risk 
            through careful strike selection and timing.
            
            Risk management remained robust throughout the period, with maximum drawdown well within 
            acceptable limits. The portfolio maintained appropriate diversification across different 
            option strategies, reducing concentration risk and smoothing overall returns.
            
            Looking ahead, we remain focused on continuous improvement through systematic analysis of 
            trading outcomes and market conditions. The strategy is well-positioned to adapt to changing 
            market dynamics while maintaining its core focus on consistent, risk-adjusted returns.
            """
        else:
            return "{}"

    async def export_report(
        self,
        report: PerformanceReport,
        format: str = 'html',
        include_charts: bool = True
    ) -> str:
        """Export report in specified format"""
        
        if format == 'html':
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{report.report_type.value.title()} Performance Report</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    h1 {{ color: #333; }}
                    .metric {{ margin: 10px 0; }}
                    .metric-label {{ font-weight: bold; }}
                    .section {{ margin: 30px 0; }}
                    table {{ border-collapse: collapse; width: 100%; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                </style>
            </head>
            <body>
                <h1>{report.report_type.value.title()} Performance Report</h1>
                <p>Period: {report.period[0].strftime('%B %d, %Y')} to {report.period[1].strftime('%B %d, %Y')}</p>
                
                <div class="section">
                    <h2>Executive Summary</h2>
                    <p>{report.narrative}</p>
                </div>
                
                <div class="section">
                    <h2>Key Metrics</h2>
                    <div class="metric">
                        <span class="metric-label">Total Return:</span> {report.metrics.total_return:.2%}
                    </div>
                    <div class="metric">
                        <span class="metric-label">Sharpe Ratio:</span> {report.metrics.sharpe_ratio:.2f}
                    </div>
                    <div class="metric">
                        <span class="metric-label">Win Rate:</span> {report.metrics.win_rate:.1%}
                    </div>
                    <div class="metric">
                        <span class="metric-label">Max Drawdown:</span> {report.metrics.max_drawdown:.1%}
                    </div>
                </div>
                
                <div class="section">
                    <h2>Key Insights</h2>
                    <ul>
                        {"".join([f"<li>{insight}</li>" for insight in report.ai_insights])}
                    </ul>
                </div>
                
                <div class="section">
                    <h2>Recommendations</h2>
                    <ul>
                        {"".join([f"<li>{rec}</li>" for rec in report.recommendations])}
                    </ul>
                </div>
            </body>
            </html>
            """
            return html_content
            
        elif format == 'json':
            return json.dumps({
                'report_type': report.report_type.value,
                'period': {
                    'start': report.period[0].isoformat(),
                    'end': report.period[1].isoformat()
                },
                'metrics': {
                    'total_return': report.metrics.total_return,
                    'sharpe_ratio': report.metrics.sharpe_ratio,
                    'win_rate': report.metrics.win_rate,
                    'max_drawdown': report.metrics.max_drawdown
                },
                'insights': report.ai_insights,
                'recommendations': report.recommendations,
                'narrative': report.narrative
            }, indent=2)
        
        else:
            return str(report)

    async def get_performance_summary(self) -> Dict[str, Any]:
        """Get current performance summary"""
        # Get YTD metrics
        ytd_start = datetime(datetime.now().year, 1, 1)
        ytd_metrics = await self._calculate_performance_metrics((ytd_start, datetime.now()))
        
        # Get recent metrics
        real_time = await self.get_real_time_metrics()
        
        return {
            'ytd_return': ytd_metrics.total_return,
            'ytd_sharpe': ytd_metrics.sharpe_ratio,
            'current_drawdown': real_time.current_drawdown,
            'today_pnl': real_time.daily_pnl,
            'open_positions': real_time.open_positions,
            'win_rate_30d': self._calculate_rolling_win_rate(30),
            'total_trades_ytd': ytd_metrics.total_trades,
            'best_strategy_ytd': self._get_best_strategy_ytd()
        }

    def _calculate_rolling_win_rate(self, days: int) -> float:
        """Calculate rolling win rate"""
        cutoff = datetime.now() - timedelta(days=days)
        recent_trades = [t for t in self.trades_history if t.exit_time > cutoff]
        return self._calculate_win_rate(recent_trades)

    def _get_best_strategy_ytd(self) -> str:
        """Get best performing strategy YTD"""
        ytd_start = datetime(datetime.now().year, 1, 1)
        ytd_trades = [t for t in self.trades_history if t.exit_time > ytd_start]
        
        strategy_pnl = defaultdict(float)
        for trade in ytd_trades:
            strategy_pnl[trade.strategy] += trade.pnl
        
        if strategy_pnl:
            return max(strategy_pnl.items(), key=lambda x: x[1])[0]
        return "None"

    async def shutdown(self):
        """Shutdown agent gracefully"""
        self.state = AgentState.STOPPED
        
        # Generate final report
        try:
            final_report = await self.generate_report(ReportType.DAILY)
            self.logger.info("Generated final daily report before shutdown")
        except:
            pass
        
        self.logger.info("Performance Analytics Agent shutdown complete")

# Factory function
def create_performance_analytics_agent(config: Dict[str, Any]) -> PerformanceAnalyticsAgent:
    """Create and return a Performance Analytics Agent instance"""
    return PerformanceAnalyticsAgent(config)


# Usage Example:
if __name__ == "__main__":
    # Example configuration
    test_config = {
        'analytics_llm_model': 'llama3.2:3b-instruct-q4_K_M',
        'report_frequency': 'daily',
        'metrics_window': 252
    }
    
    # Create agent
    analytics_agent = create_performance_analytics_agent(test_config)
    
    # Example usage
    async def example_usage():
        await analytics_agent.initialize()
        
        # Generate performance report
        report = await analytics_agent.generate_report(
            ReportType.MONTHLY,
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now()
        )
        
        print(f"Report Type: {report.report_type.value}")
        print(f"Total Return: {report.metrics.total_return:.2%}")
        print(f"Sharpe Ratio: {report.metrics.sharpe_ratio:.2f}")
        print(f"Win Rate: {report.metrics.win_rate:.1%}")
        print(f"\nKey Insights:")
        for insight in report.ai_insights[:3]:
            print(f"- {insight}")
        
        # Get real-time metrics
        real_time = await analytics_agent.get_real_time_metrics()
        print(f"\nReal-Time Metrics:")
        print(f"Today's P&L: ${real_time.daily_pnl:.2f}")
        print(f"Current Drawdown: {real_time.current_drawdown:.1%}")
        print(f"Open Positions: {real_time.open_positions}")
        
        # Export report
        html_report = await analytics_agent.export_report(report, format='html')
        # Would save to file
    
    # Run example
    # asyncio.run(example_usage())