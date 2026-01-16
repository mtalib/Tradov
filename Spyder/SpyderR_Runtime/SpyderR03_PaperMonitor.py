#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderR_Runtime
Module: SpyderR03_PaperMonitor.py
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
import datetime
import json
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import statistics
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType

UPDATE_INTERVAL = 5  # seconds
METRICS_WINDOW = 300  # 5 minutes of detailed metrics

# Performance thresholds
MIN_ACCEPTABLE_WIN_RATE = 0.40
MAX_ACCEPTABLE_DRAWDOWN = 0.15
MIN_PROFIT_FACTOR = 1.2
MAX_ACCEPTABLE_SLIPPAGE = 0.05  # $0.05 average

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class StrategyPerformance:
    """Performance metrics for a specific strategy"""
    strategy_name: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    
    # Detailed metrics
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    
    # Risk metrics
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    
    # Execution metrics
    avg_slippage: float = 0.0
    avg_fill_time_ms: float = 0.0
    rejected_orders: int = 0
    
    # Time-based performance
    daily_pnl: Dict[str, float] = field(default_factory=dict)
    hourly_performance: Dict[int, float] = field(default_factory=dict)
    
    def get_win_rate(self) -> float:
        """Calculate win rate"""
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades
    
    def update_metrics(self, trades: List[Dict[str, Any]]) -> None:
        """Update performance metrics from trades"""
        if not trades:
            return
        
        # Filter trades for this strategy
        strategy_trades = [t for t in trades if t.get('strategy') == self.strategy_name]
        
        if not strategy_trades:
            return
        
        # Update counts
        self.total_trades = len(strategy_trades)
        self.winning_trades = sum(1 for t in strategy_trades if t['pnl'] > 0)
        self.losing_trades = sum(1 for t in strategy_trades if t['pnl'] < 0)
        
        # Update P&L
        self.total_pnl = sum(t['pnl'] for t in strategy_trades)
        
        # Calculate averages
        winners = [t for t in strategy_trades if t['pnl'] > 0]
        losers = [t for t in strategy_trades if t['pnl'] < 0]
        
        if winners:
            self.avg_win = np.mean([t['pnl'] for t in winners])
            self.largest_win = max(t['pnl'] for t in winners)
        
        if losers:
            self.avg_loss = abs(np.mean([t['pnl'] for t in losers]))
            self.largest_loss = min(t['pnl'] for t in losers)
        
        # Profit factor
        if losers and self.avg_loss > 0:
            total_wins = sum(t['pnl'] for t in winners) if winners else 0
            total_losses = abs(sum(t['pnl'] for t in losers))
            self.profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # Execution metrics
        self.avg_slippage = np.mean([t.get('slippage', 0) for t in strategy_trades])
        fill_times = [t.get('fill_time_ms', 0) for t in strategy_trades if t.get('fill_time_ms')]
        if fill_times:
            self.avg_fill_time_ms = np.mean(fill_times)

class MarketRegimeAnalysis:
    """Analysis of performance by market regime"""
    regime: str  # trending, ranging, volatile
    trade_count: int = 0
    win_rate: float = 0.0
    avg_pnl: float = 0.0
    
    # Regime-specific metrics
    avg_spread: float = 0.0
    avg_volatility: float = 0.0
    success_factors: List[str] = field(default_factory=list)
    failure_factors: List[str] = field(default_factory=list)

class ExecutionQualityMetrics:
    """Detailed execution quality analysis"""
    # Fill quality
    market_orders_filled: int = 0
    limit_orders_filled: int = 0
    limit_orders_missed: int = 0
    
    # Slippage analysis
    positive_slippage_count: int = 0
    negative_slippage_count: int = 0
    avg_positive_slippage: float = 0.0
    avg_negative_slippage: float = 0.0
    
    # Spread impact
    avg_entry_spread: float = 0.0
    avg_exit_spread: float = 0.0
    spread_cost_total: float = 0.0
    
    # Timing analysis
    best_fill_hour: int = 0
    worst_fill_hour: int = 0
    avg_fill_by_hour: Dict[int, float] = field(default_factory=dict)

# ==============================================================================
# PAPER MONITOR CLASS
# ==============================================================================
class PaperTradingMonitor:
    """
    Monitors paper trading performance and provides insights.
    
    Features:
    - Real-time performance tracking
    - Strategy comparison
    - Execution quality analysis
    - Market regime analysis
    - Alert generation for issues
    """
    
    def __init__(self, event_manager: EventManager):
        """
        Initialize paper trading monitor.
        
        Args:
            event_manager: Event manager for notifications
        """
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Performance tracking
        self.strategy_performance: Dict[str, StrategyPerformance] = {}
        self.execution_metrics = ExecutionQualityMetrics()
        self.market_regimes: Dict[str, MarketRegimeAnalysis] = {}
        
        # Trade history
        self.all_trades: List[Dict[str, Any]] = []
        self.recent_trades: deque = deque(maxlen=100)
        
        # Real-time metrics
        self.equity_curve: List[Tuple[datetime.datetime, float]] = []
        self.current_drawdown: float = 0.0
        self.peak_equity: float = 0.0
        
        # Monitoring state
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        
        # Alert tracking
        self.active_alerts: Dict[str, Dict[str, Any]] = {}
        self.alert_history: deque = deque(maxlen=100)
        
        # Register event handlers
        self._register_event_handlers()
        
        self.logger.info("Paper trading monitor initialized")
    
    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    def _register_event_handlers(self) -> None:
        """Register event handlers"""
        # Paper trade completion
        self.event_manager.subscribe(
            self._handle_trade_complete,
            event_type=EventType.SYSTEM,
            subscriber_id="paper_monitor_trade"
        )
        
        # Session updates
        self.event_manager.subscribe(
            self._handle_session_update,
            event_type=EventType.SYSTEM,
            subscriber_id="paper_monitor_session"
        )
    
    def _handle_trade_complete(self, event: Event) -> None:
        """Handle completed paper trade"""
        if event.data.get('type') != 'paper_trade_complete':
            return
        
        trade_data = event.data.get('learning_data', {})
        if trade_data:
            with self._lock:
                self.all_trades.append(trade_data)
                self.recent_trades.append(trade_data)
                self._update_performance_metrics()
                self._check_performance_alerts()
    
    def _handle_session_update(self, event: Event) -> None:
        """Handle session update events"""
        if event.data.get('type') == 'paper_session_equity_update':
            equity = event.data.get('equity')
            timestamp = event.data.get('timestamp')
            
            with self._lock:
                self.equity_curve.append((timestamp, equity))
                self._update_drawdown(equity)
    
    # ==========================================================================
    # MONITORING
    # ==========================================================================
    def start_monitoring(self) -> None:
        """Start monitoring paper trading"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="PaperMonitor"
        )
        self._monitor_thread.start()
        
        self.logger.info("Paper trading monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop monitoring"""
        self._monitoring = False
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=10.0)
        
        self.logger.info("Paper trading monitoring stopped")
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._monitoring:
            try:
                # Update metrics
                self._update_performance_metrics()
                
                # Analyze execution quality
                self._analyze_execution_quality()
                
                # Check for issues
                self._check_performance_alerts()
                
                # Emit status update
                self._emit_monitor_update()
                
                # Sleep
                threading.Event().wait(UPDATE_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
                self.error_handler.handle_error(e)
    
    # ==========================================================================
    # PERFORMANCE ANALYSIS
    # ==========================================================================
    def _update_performance_metrics(self) -> None:
        """Update performance metrics for all strategies"""
        if not self.all_trades:
            return
        
        # Group trades by strategy
        trades_by_strategy = defaultdict(list)
        for trade in self.all_trades:
            strategy = trade.get('strategy', 'Unknown')
            trades_by_strategy[strategy].append(trade)
        
        # Update each strategy
        for strategy_name, trades in trades_by_strategy.items():
            if strategy_name not in self.strategy_performance:
                self.strategy_performance[strategy_name] = StrategyPerformance(strategy_name)
            
            self.strategy_performance[strategy_name].update_metrics(trades)
        
        # Update market regime analysis
        self._analyze_market_regimes()
    
    def _analyze_execution_quality(self) -> None:
        """Analyze execution quality metrics"""
        if not self.all_trades:
            return
        
        # Reset metrics
        self.execution_metrics = ExecutionQualityMetrics()
        
        # Analyze each trade
        for trade in self.all_trades:
            # Order type analysis
            if trade.get('order_type') == 'MARKET':
                self.execution_metrics.market_orders_filled += 1
            else:
                self.execution_metrics.limit_orders_filled += 1
            
            # Slippage analysis
            slippage = trade.get('slippage', 0)
            if slippage > 0:
                self.execution_metrics.negative_slippage_count += 1
            elif slippage < 0:
                self.execution_metrics.positive_slippage_count += 1
            
            # Spread analysis
            entry_spread = trade.get('entry_spread', 0)
            exit_spread = trade.get('exit_spread', 0)
            
            if entry_spread > 0:
                self.execution_metrics.spread_cost_total += entry_spread / 2
            if exit_spread > 0:
                self.execution_metrics.spread_cost_total += exit_spread / 2
        
        # Calculate averages
        total_trades = len(self.all_trades)
        if total_trades > 0:
            entry_spreads = [t.get('entry_spread', 0) for t in self.all_trades if t.get('entry_spread')]
            exit_spreads = [t.get('exit_spread', 0) for t in self.all_trades if t.get('exit_spread')]
            
            if entry_spreads:
                self.execution_metrics.avg_entry_spread = np.mean(entry_spreads)
            if exit_spreads:
                self.execution_metrics.avg_exit_spread = np.mean(exit_spreads)
        
        # Time-based analysis
        self._analyze_fill_times()
    
    def _analyze_market_regimes(self) -> None:
        """Analyze performance by market regime"""
        # Group trades by market conditions
        regime_trades = defaultdict(list)
        
        for trade in self.all_trades:
            # Determine regime based on VIX and trend
            vix = trade.get('vix', 20)
            trend = trade.get('trend', 'neutral')
            
            if vix > 25:
                regime = 'volatile'
            elif trend in ['bullish', 'bearish']:
                regime = 'trending'
            else:
                regime = 'ranging'
            
            regime_trades[regime].append(trade)
        
        # Analyze each regime
        for regime, trades in regime_trades.items():
            if regime not in self.market_regimes:
                self.market_regimes[regime] = MarketRegimeAnalysis(regime=regime)
            
            analysis = self.market_regimes[regime]
            analysis.trade_count = len(trades)
            
            # Calculate metrics
            winning = sum(1 for t in trades if t['pnl'] > 0)
            analysis.win_rate = winning / len(trades) if trades else 0
            analysis.avg_pnl = np.mean([t['pnl'] for t in trades]) if trades else 0
            
            # Average spread and volatility
            spreads = [t.get('entry_spread', 0) for t in trades if t.get('entry_spread')]
            if spreads:
                analysis.avg_spread = np.mean(spreads)
            
            # Identify success/failure factors
            self._identify_regime_factors(analysis, trades)
    
    def _identify_regime_factors(self, analysis: MarketRegimeAnalysis, trades: List[Dict[str, Any]]) -> None:
        """Identify success and failure factors for a regime"""
        winners = [t for t in trades if t['pnl'] > 0]
        losers = [t for t in trades if t['pnl'] < 0]
        
        # Reset factors
        analysis.success_factors = []
        analysis.failure_factors = []
        
        # Analyze winners
        if winners:
            # Common characteristics of winners
            avg_hold_time = np.mean([t.get('held_minutes', 0) for t in winners])
            if avg_hold_time < 30:
                analysis.success_factors.append("Quick exits (<30 min)")
            
            avg_entry_spread = np.mean([t.get('entry_spread_percent', 0) for t in winners])
            if avg_entry_spread < 0.002:  # 0.2%
                analysis.success_factors.append("Tight entry spreads")
        
        # Analyze losers
        if losers:
            # Common characteristics of losers
            avg_slippage = np.mean([t.get('slippage', 0) for t in losers])
            if avg_slippage > 0.05:
                analysis.failure_factors.append("High slippage (>$0.05)")
            
            avg_exit_spread = np.mean([t.get('exit_spread', 0) for t in losers if t.get('exit_spread')])
            if avg_exit_spread > 0.20:
                analysis.failure_factors.append("Wide exit spreads (>$0.20)")
    
    def _analyze_fill_times(self) -> None:
        """Analyze fill times by hour of day"""
        fill_by_hour = defaultdict(list)
        
        for trade in self.all_trades:
            timestamp = trade.get('timestamp')
            fill_time = trade.get('fill_time_ms', 0)
            
            if timestamp and fill_time:
                # Parse timestamp
                dt = datetime.datetime.fromisoformat(timestamp)
                hour = dt.hour
                fill_by_hour[hour].append(fill_time)
        
        # Calculate averages
        for hour, times in fill_by_hour.items():
            if times:
                self.execution_metrics.avg_fill_by_hour[hour] = np.mean(times)
        
        # Find best/worst hours
        if self.execution_metrics.avg_fill_by_hour:
            self.execution_metrics.best_fill_hour = min(
                self.execution_metrics.avg_fill_by_hour.items(),
                key=lambda x: x[1]
            )[0]
            self.execution_metrics.worst_fill_hour = max(
                self.execution_metrics.avg_fill_by_hour.items(),
                key=lambda x: x[1]
            )[0]
    
    def _update_drawdown(self, current_equity: float) -> None:
        """Update drawdown calculation"""
        # Update peak
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        
        # Calculate drawdown
        if self.peak_equity > 0:
            self.current_drawdown = (self.peak_equity - current_equity) / self.peak_equity
    
    # ==========================================================================
    # ALERTS
    # ==========================================================================
    def _check_performance_alerts(self) -> None:
        """Check for performance issues and generate alerts"""
        alerts = []
        
        # Check overall win rate
        total_trades = sum(s.total_trades for s in self.strategy_performance.values())
        total_wins = sum(s.winning_trades for s in self.strategy_performance.values())
        
        if total_trades >= 10:  # Need minimum trades
            overall_win_rate = total_wins / total_trades
            if overall_win_rate < MIN_ACCEPTABLE_WIN_RATE:
                alerts.append({
                    'type': 'low_win_rate',
                    'severity': 'warning',
                    'message': f'Overall win rate {overall_win_rate:.1%} below minimum {MIN_ACCEPTABLE_WIN_RATE:.0%}',
                    'value': overall_win_rate
                })
        
        # Check drawdown
        if self.current_drawdown > MAX_ACCEPTABLE_DRAWDOWN:
            alerts.append({
                'type': 'high_drawdown',
                'severity': 'critical',
                'message': f'Drawdown {self.current_drawdown:.1%} exceeds maximum {MAX_ACCEPTABLE_DRAWDOWN:.0%}',
                'value': self.current_drawdown
            })
        
        # Check execution quality
        if self.execution_metrics.avg_entry_spread > MAX_ACCEPTABLE_SLIPPAGE * 2:
            alerts.append({
                'type': 'wide_spreads',
                'severity': 'warning',
                'message': f'Average entry spread ${self.execution_metrics.avg_entry_spread:.3f} is too wide',
                'value': self.execution_metrics.avg_entry_spread
            })
        
        # Check individual strategies
        for strategy_name, perf in self.strategy_performance.items():
            if perf.total_trades >= 5:  # Need minimum trades
                # Low profit factor
                if perf.profit_factor < MIN_PROFIT_FACTOR and perf.profit_factor > 0:
                    alerts.append({
                        'type': 'low_profit_factor',
                        'severity': 'warning',
                        'message': f'{strategy_name} profit factor {perf.profit_factor:.2f} below minimum {MIN_PROFIT_FACTOR}',
                        'strategy': strategy_name,
                        'value': perf.profit_factor
                    })
                
                # High slippage
                if perf.avg_slippage > MAX_ACCEPTABLE_SLIPPAGE:
                    alerts.append({
                        'type': 'high_slippage',
                        'severity': 'warning',
                        'message': f'{strategy_name} average slippage ${perf.avg_slippage:.3f} too high',
                        'strategy': strategy_name,
                        'value': perf.avg_slippage
                    })
        
        # Process alerts
        for alert in alerts:
            self._process_alert(alert)
    
    def _process_alert(self, alert: Dict[str, Any]) -> None:
        """Process and emit alert"""
        alert_key = f"{alert['type']}_{alert.get('strategy', 'overall')}"
        
        # Check if already active
        if alert_key not in self.active_alerts:
            # New alert
            alert['timestamp'] = datetime.datetime.now()
            alert['alert_key'] = alert_key
            
            self.active_alerts[alert_key] = alert
            self.alert_history.append(alert)
            
            # Emit alert event
            self.event_manager.emit(Event(
                EventType.ALERT,
                {
                    'source': 'paper_monitor',
                    'alert': alert
                }
            ))
            
            self.logger.warning(f"Paper trading alert: {alert['message']}")
    
    # ==========================================================================
    # STATUS AND REPORTING
    # ==========================================================================
    def _emit_monitor_update(self) -> None:
        """Emit monitoring status update"""
        status = self.get_current_status()
        
        self.event_manager.emit(Event(
            EventType.SYSTEM,
            {
                'type': 'paper_monitor_update',
                'status': status
            }
        ))
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        with self._lock:
            # Overall metrics
            total_trades = sum(s.total_trades for s in self.strategy_performance.values())
            total_pnl = sum(s.total_pnl for s in self.strategy_performance.values())
            
            status = {
                'timestamp': datetime.datetime.now().isoformat(),
                'total_trades': total_trades,
                'total_pnl': total_pnl,
                'current_drawdown': self.current_drawdown,
                'active_alerts': len(self.active_alerts),
                
                # Strategy performance
                'strategies': {
                    name: {
                        'trades': perf.total_trades,
                        'win_rate': perf.get_win_rate(),
                        'pnl': perf.total_pnl,
                        'profit_factor': perf.profit_factor,
                        'avg_slippage': perf.avg_slippage
                    }
                    for name, perf in self.strategy_performance.items()
                },
                
                # Execution quality
                'execution': {
                    'avg_entry_spread': self.execution_metrics.avg_entry_spread,
                    'avg_exit_spread': self.execution_metrics.avg_exit_spread,
                    'spread_cost_total': self.execution_metrics.spread_cost_total,
                    'best_fill_hour': self.execution_metrics.best_fill_hour,
                    'worst_fill_hour': self.execution_metrics.worst_fill_hour
                },
                
                # Market regimes
                'regimes': {
                    regime: {
                        'trades': analysis.trade_count,
                        'win_rate': analysis.win_rate,
                        'avg_pnl': analysis.avg_pnl,
                        'avg_spread': analysis.avg_spread
                    }
                    for regime, analysis in self.market_regimes.items()
                }
            }
            
            return status
    
    def generate_performance_report(self) -> str:
        """Generate detailed performance report"""
        report = []
        report.append("="*80)
        report.append("PAPER TRADING PERFORMANCE REPORT")
        report.append("="*80)
        report.append(f"Generated: {datetime.datetime.now()}")
        report.append("")
        
        # Overall summary
        total_trades = sum(s.total_trades for s in self.strategy_performance.values())
        total_pnl = sum(s.total_pnl for s in self.strategy_performance.values())
        
        report.append("OVERALL SUMMARY:")
        report.append(f"  Total Trades: {total_trades}")
        report.append(f"  Total P&L: ${total_pnl:,.2f}")
        report.append(f"  Current Drawdown: {self.current_drawdown:.1%}")
        report.append(f"  Active Alerts: {len(self.active_alerts)}")
        report.append("")
        
        # Strategy performance
        report.append("STRATEGY PERFORMANCE:")
        for name, perf in sorted(self.strategy_performance.items(), key=lambda x: x[1].total_pnl, reverse=True):
            report.append(f"\n  {name}:")
            report.append(f"    Trades: {perf.total_trades}")
            report.append(f"    Win Rate: {perf.get_win_rate():.1%}")
            report.append(f"    P&L: ${perf.total_pnl:,.2f}")
            report.append(f"    Avg Win: ${perf.avg_win:.2f}")
            report.append(f"    Avg Loss: ${perf.avg_loss:.2f}")
            report.append(f"    Profit Factor: {perf.profit_factor:.2f}")
            report.append(f"    Avg Slippage: ${perf.avg_slippage:.3f}")
            report.append(f"    Avg Fill Time: {perf.avg_fill_time_ms:.0f}ms")
        
        # Execution quality
        report.append("\nEXECUTION QUALITY:")
        report.append(f"  Market Orders: {self.execution_metrics.market_orders_filled}")
        report.append(f"  Limit Orders: {self.execution_metrics.limit_orders_filled}")
        report.append(f"  Avg Entry Spread: ${self.execution_metrics.avg_entry_spread:.3f}")
        report.append(f"  Avg Exit Spread: ${self.execution_metrics.avg_exit_spread:.3f}")
        report.append(f"  Total Spread Cost: ${self.execution_metrics.spread_cost_total:.2f}")
        report.append(f"  Best Fill Hour: {self.execution_metrics.best_fill_hour}:00")
        report.append(f"  Worst Fill Hour: {self.execution_metrics.worst_fill_hour}:00")
        
        # Market regime analysis
        report.append("\nMARKET REGIME ANALYSIS:")
        for regime, analysis in sorted(self.market_regimes.items(), key=lambda x: x[1].trade_count, reverse=True):
            report.append(f"\n  {regime.upper()} Market:")
            report.append(f"    Trades: {analysis.trade_count}")
            report.append(f"    Win Rate: {analysis.win_rate:.1%}")
            report.append(f"    Avg P&L: ${analysis.avg_pnl:.2f}")
            report.append(f"    Avg Spread: ${analysis.avg_spread:.3f}")
            
            if analysis.success_factors:
                report.append(f"    Success Factors: {', '.join(analysis.success_factors)}")
            if analysis.failure_factors:
                report.append(f"    Failure Factors: {', '.join(analysis.failure_factors)}")
        
        # Key insights
        report.append("\nKEY INSIGHTS:")
        insights = self._generate_insights()
        for insight in insights:
            report.append(f"  • {insight}")
        
        # Active alerts
        if self.active_alerts:
            report.append("\nACTIVE ALERTS:")
            for alert in self.active_alerts.values():
                report.append(f"  [{alert['severity'].upper()}] {alert['message']}")
        
        report.append("\n" + "="*80)
        
        return "\n".join(report)
    
    def _generate_insights(self) -> List[str]:
        """Generate actionable insights from data"""
        insights = []
        
        # Best performing strategy
        if self.strategy_performance:
            best_strategy = max(self.strategy_performance.items(), key=lambda x: x[1].total_pnl)
            insights.append(f"Best performing strategy: {best_strategy[0]} (${best_strategy[1].total_pnl:.2f})")
        
        # Execution insights
        if self.execution_metrics.spread_cost_total > 0:
            avg_spread_cost_per_trade = self.execution_metrics.spread_cost_total / len(self.all_trades) if self.all_trades else 0
            insights.append(f"Average spread cost per trade: ${avg_spread_cost_per_trade:.2f}")
        
        # Regime insights
        if self.market_regimes:
            best_regime = max(self.market_regimes.items(), key=lambda x: x[1].win_rate)
            insights.append(f"Best performance in {best_regime[0]} markets ({best_regime[1].win_rate:.1%} win rate)")
        
        # Time-based insights
        if self.execution_metrics.best_fill_hour and self.execution_metrics.worst_fill_hour:
            insights.append(
                f"Best fills at {self.execution_metrics.best_fill_hour}:00, "
                f"avoid trading at {self.execution_metrics.worst_fill_hour}:00"
            )
        
        # Risk insights
        if self.current_drawdown > 0.10:
            insights.append(f"High drawdown ({self.current_drawdown:.1%}) - consider reducing position sizes")
        
        return insights
    
    def get_learning_recommendations(self) -> Dict[str, List[str]]:
        """Get recommendations for strategy improvement"""
        recommendations = defaultdict(list)
        
        for name, perf in self.strategy_performance.items():
            if perf.total_trades < 10:
                recommendations[name].append("Need more trades for reliable analysis (minimum 10)")
                continue
            
            # Win rate recommendations
            if perf.get_win_rate() < 0.45:
                recommendations[name].append("Low win rate - review entry criteria")
            
            # Profit factor recommendations
            if perf.profit_factor < 1.5:
                recommendations[name].append("Low profit factor - improve risk/reward ratio")
            
            # Slippage recommendations
            if perf.avg_slippage > 0.05:
                recommendations[name].append("High slippage - consider limit orders or better timing")
            
            # Loss management
            if abs(perf.largest_loss) > 3 * perf.avg_loss:
                recommendations[name].append("Large outlier losses - improve stop loss management")
        
        # Execution recommendations
        if self.execution_metrics.avg_entry_spread > 0.15:
            recommendations['execution'].append("Wide entry spreads - avoid illiquid strikes")
        
        if self.execution_metrics.market_orders_filled > self.execution_metrics.limit_orders_filled * 2:
            recommendations['execution'].append("Too many market orders - use more limit orders to reduce costs")
        
        return dict(recommendations)
    
    def export_metrics(self, filename: str) -> None:
        """Export detailed metrics to file"""
        metrics_data = {
            'export_time': datetime.datetime.now().isoformat(),
            'summary': {
                'total_trades': sum(s.total_trades for s in self.strategy_performance.values()),
                'total_pnl': sum(s.total_pnl for s in self.strategy_performance.values()),
                'current_drawdown': self.current_drawdown
            },
            'strategies': {
                name: {
                    'total_trades': perf.total_trades,
                    'win_rate': perf.get_win_rate(),
                    'total_pnl': perf.total_pnl,
                    'avg_win': perf.avg_win,
                    'avg_loss': perf.avg_loss,
                    'profit_factor': perf.profit_factor,
                    'avg_slippage': perf.avg_slippage,
                    'avg_fill_time_ms': perf.avg_fill_time_ms
                }
                for name, perf in self.strategy_performance.items()
            },
            'execution_quality': {
                'market_orders': self.execution_metrics.market_orders_filled,
                'limit_orders': self.execution_metrics.limit_orders_filled,
                'avg_entry_spread': self.execution_metrics.avg_entry_spread,
                'avg_exit_spread': self.execution_metrics.avg_exit_spread,
                'spread_cost_total': self.execution_metrics.spread_cost_total,
                'fill_times_by_hour': self.execution_metrics.avg_fill_by_hour
            },
            'market_regimes': {
                regime: {
                    'trade_count': analysis.trade_count,
                    'win_rate': analysis.win_rate,
                    'avg_pnl': analysis.avg_pnl,
                    'avg_spread': analysis.avg_spread,
                    'success_factors': analysis.success_factors,
                    'failure_factors': analysis.failure_factors
                }
                for regime, analysis in self.market_regimes.items()
            },
            'recommendations': self.get_learning_recommendations(),
            'active_alerts': [
                {
                    'type': alert['type'],
                    'severity': alert['severity'],
                    'message': alert['message'],
                    'timestamp': alert['timestamp'].isoformat()
                }
                for alert in self.active_alerts.values()
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(metrics_data, f, indent=2)
        
        self.logger.info(f"Metrics exported to {filename}")

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    print("PaperTradingMonitor module")
    print("This module monitors paper trading performance and execution quality")
    print("It provides insights to improve strategies before live trading")