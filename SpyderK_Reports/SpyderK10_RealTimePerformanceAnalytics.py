"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderK10_RealTimePerformanceAnalytics.py
Group: K (Reports)
Purpose: Real-time performance analytics and reporting dashboard
Author: Mohamed Talib
Date Created: 2025-01-08
Last Updated: 2025-01-08 Time: 12:30:00

Description:
    Advanced real-time performance analytics module that integrates with the
    risk management suite to provide comprehensive trading metrics, strategy
    performance analysis, risk-adjusted returns, and automated reporting.
    Designed to work seamlessly with E11, E12, E13, P05, and P06 modules.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import logging
from collections import defaultdict, deque
import asyncio
import statistics
import warnings
warnings.filterwarnings('ignore')

# ==================================================================================
# LOGGING CONFIGURATION
# ==================================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================================================================================
# ENUMS AND CONSTANTS
# ==================================================================================

class MetricType(Enum):
    """Types of performance metrics"""
    RETURNS = "returns"
    RISK_ADJUSTED = "risk_adjusted"
    DRAWDOWN = "drawdown"
    WIN_RATE = "win_rate"
    GREEKS = "greeks"
    EXECUTION = "execution"
    ALLOCATION = "allocation"
    
class TimeFrame(Enum):
    """Time frames for analysis"""
    INTRADAY = "intraday"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    
class ReportFormat(Enum):
    """Report output formats"""
    JSON = "json"
    HTML = "html"
    PDF = "pdf"
    EXCEL = "excel"
    DASHBOARD = "dashboard"

# ==================================================================================
# DATA CLASSES
# ==================================================================================

@dataclass
class PerformanceMetrics:
    """Core performance metrics"""
    timestamp: datetime
    total_return: float
    daily_return: float
    cumulative_return: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    current_drawdown: float
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    best_trade: float
    worst_trade: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    
@dataclass
class StrategyPerformance:
    """Individual strategy performance"""
    strategy_id: str
    strategy_name: str
    active_since: datetime
    total_pnl: float
    daily_pnl: float
    roi: float
    sharpe: float
    win_rate: float
    avg_trade_duration: timedelta
    current_positions: int
    capital_allocated: float
    var_contribution: float
    
@dataclass
class RiskMetrics:
    """Risk-specific metrics"""
    timestamp: datetime
    portfolio_var_95: float
    portfolio_var_99: float
    portfolio_cvar_99: float
    component_var: Dict[str, float]
    tail_risk_score: float
    correlation_risk: float
    concentration_risk: float
    regime_risk: str
    max_loss_limit: float
    current_exposure: float
    
@dataclass
class ExecutionMetrics:
    """Trade execution metrics"""
    timestamp: datetime
    total_orders: int
    filled_orders: int
    partial_fills: int
    rejected_orders: int
    avg_fill_time: float  # seconds
    avg_slippage: float  # bps
    total_commissions: float
    market_impact: float
    execution_shortfall: float

# ==================================================================================
# PERFORMANCE ANALYTICS ENGINE
# ==================================================================================

class PerformanceAnalyticsEngine:
    """
    Real-time performance analytics engine
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize analytics engine"""
        self.config = config
        self.portfolio_value = config.get('portfolio_value', 1000000)
        self.risk_free_rate = config.get('risk_free_rate', 0.05)
        
        # Performance tracking
        self.metrics_history = deque(maxlen=10000)
        self.strategy_performance = {}
        self.risk_metrics_history = deque(maxlen=1000)
        self.execution_metrics_history = deque(maxlen=1000)
        
        # Real-time data
        self.current_positions = {}
        self.daily_returns = []
        self.cumulative_pnl = 0
        self.high_water_mark = self.portfolio_value
        
        # Analytics cache
        self.cache = {}
        self.last_calculation = datetime.now()
        
        logger.info("Performance Analytics Engine initialized")
        
    # ==================================================================================
    # CORE ANALYTICS
    # ==================================================================================
    
    def calculate_performance_metrics(self, positions: Dict[str, Any], 
                                     market_data: Dict[str, Any]) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics"""
        
        # Calculate returns
        daily_return = self._calculate_daily_return(positions)
        total_return = self.cumulative_pnl / self.portfolio_value
        
        # Risk-adjusted metrics
        sharpe = self._calculate_sharpe_ratio()
        sortino = self._calculate_sortino_ratio()
        calmar = self._calculate_calmar_ratio()
        
        # Drawdown analysis
        max_dd, current_dd = self._calculate_drawdowns()
        
        # Win/loss statistics
        win_stats = self._calculate_win_loss_stats()
        
        metrics = PerformanceMetrics(
            timestamp=datetime.now(),
            total_return=total_return,
            daily_return=daily_return,
            cumulative_return=total_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown=max_dd,
            current_drawdown=current_dd,
            win_rate=win_stats['win_rate'],
            profit_factor=win_stats['profit_factor'],
            avg_win=win_stats['avg_win'],
            avg_loss=win_stats['avg_loss'],
            best_trade=win_stats['best_trade'],
            worst_trade=win_stats['worst_trade'],
            total_trades=win_stats['total_trades'],
            winning_trades=win_stats['winning_trades'],
            losing_trades=win_stats['losing_trades']
        )
        
        self.metrics_history.append(metrics)
        return metrics
        
    def analyze_strategy_performance(self, strategy_id: str, 
                                    trades: List[Dict]) -> StrategyPerformance:
        """Analyze individual strategy performance"""
        
        if not trades:
            return None
            
        # Calculate strategy-specific metrics
        strategy_pnl = sum(t['pnl'] for t in trades)
        daily_pnl = sum(t['pnl'] for t in trades if t['timestamp'].date() == datetime.now().date())
        
        # Calculate win rate
        winning = [t for t in trades if t['pnl'] > 0]
        win_rate = len(winning) / len(trades) if trades else 0
        
        # Calculate ROI
        capital_used = sum(t['capital'] for t in trades) / len(trades)
        roi = strategy_pnl / capital_used if capital_used > 0 else 0
        
        # Calculate Sharpe
        returns = [t['pnl'] / t['capital'] for t in trades if t['capital'] > 0]
        sharpe = self._calculate_sharpe_from_returns(returns)
        
        # Average trade duration
        durations = [(t['exit_time'] - t['entry_time']) for t in trades if 'exit_time' in t]
        avg_duration = sum(durations, timedelta()) / len(durations) if durations else timedelta()
        
        performance = StrategyPerformance(
            strategy_id=strategy_id,
            strategy_name=self._get_strategy_name(strategy_id),
            active_since=trades[0]['timestamp'] if trades else datetime.now(),
            total_pnl=strategy_pnl,
            daily_pnl=daily_pnl,
            roi=roi,
            sharpe=sharpe,
            win_rate=win_rate,
            avg_trade_duration=avg_duration,
            current_positions=len([t for t in trades if t.get('is_open', False)]),
            capital_allocated=capital_used,
            var_contribution=self._calculate_var_contribution(strategy_id)
        )
        
        self.strategy_performance[strategy_id] = performance
        return performance
        
    def calculate_risk_metrics(self, var_data: Dict[str, Any], 
                              tail_data: Dict[str, Any]) -> RiskMetrics:
        """Calculate comprehensive risk metrics"""
        
        metrics = RiskMetrics(
            timestamp=datetime.now(),
            portfolio_var_95=var_data.get('var_95', 0),
            portfolio_var_99=var_data.get('var_99', 0),
            portfolio_cvar_99=var_data.get('cvar_99', 0),
            component_var=var_data.get('component_var', {}),
            tail_risk_score=tail_data.get('warning_score', 0),
            correlation_risk=self._calculate_correlation_risk(),
            concentration_risk=self._calculate_concentration_risk(),
            regime_risk=tail_data.get('current_regime', 'NORMAL'),
            max_loss_limit=self.config.get('max_daily_loss', 50000),
            current_exposure=self._calculate_current_exposure()
        )
        
        self.risk_metrics_history.append(metrics)
        return metrics
        
    def track_execution_metrics(self, orders: List[Dict]) -> ExecutionMetrics:
        """Track execution quality metrics"""
        
        if not orders:
            return None
            
        filled = [o for o in orders if o['status'] == 'FILLED']
        partial = [o for o in orders if o['status'] == 'PARTIAL']
        rejected = [o for o in orders if o['status'] == 'REJECTED']
        
        # Calculate averages
        fill_times = [o['fill_time'] for o in filled if 'fill_time' in o]
        avg_fill_time = statistics.mean(fill_times) if fill_times else 0
        
        slippages = [o['slippage'] for o in filled if 'slippage' in o]
        avg_slippage = statistics.mean(slippages) if slippages else 0
        
        metrics = ExecutionMetrics(
            timestamp=datetime.now(),
            total_orders=len(orders),
            filled_orders=len(filled),
            partial_fills=len(partial),
            rejected_orders=len(rejected),
            avg_fill_time=avg_fill_time,
            avg_slippage=avg_slippage * 10000,  # Convert to bps
            total_commissions=sum(o.get('commission', 0) for o in filled),
            market_impact=self._calculate_market_impact(filled),
            execution_shortfall=self._calculate_execution_shortfall(orders)
        )
        
        self.execution_metrics_history.append(metrics)
        return metrics
        
    # ==================================================================================
    # REPORTING FUNCTIONS
    # ==================================================================================
    
    def generate_performance_report(self, timeframe: TimeFrame = TimeFrame.DAILY,
                                   format: ReportFormat = ReportFormat.JSON) -> Union[Dict, str]:
        """Generate comprehensive performance report"""
        
        report_data = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'timeframe': timeframe.value,
                'portfolio_value': self.portfolio_value,
                'reporting_period': self._get_reporting_period(timeframe)
            },
            'performance': self._compile_performance_data(timeframe),
            'strategies': self._compile_strategy_data(),
            'risk': self._compile_risk_data(),
            'execution': self._compile_execution_data(),
            'attribution': self._perform_attribution_analysis(),
            'recommendations': self._generate_recommendations()
        }
        
        # Format report based on requested format
        if format == ReportFormat.JSON:
            return report_data
        elif format == ReportFormat.HTML:
            return self._format_html_report(report_data)
        elif format == ReportFormat.EXCEL:
            return self._export_to_excel(report_data)
        elif format == ReportFormat.DASHBOARD:
            return self._prepare_dashboard_data(report_data)
        else:
            return report_data
            
    def generate_risk_report(self) -> Dict[str, Any]:
        """Generate detailed risk analysis report"""
        
        latest_risk = self.risk_metrics_history[-1] if self.risk_metrics_history else None
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'current_risk': {
                'var_95': latest_risk.portfolio_var_95 if latest_risk else 0,
                'var_99': latest_risk.portfolio_var_99 if latest_risk else 0,
                'tail_risk_score': latest_risk.tail_risk_score if latest_risk else 0,
                'regime': latest_risk.regime_risk if latest_risk else 'UNKNOWN'
            },
            'risk_decomposition': self._decompose_risk(),
            'stress_test_results': self._run_stress_tests(),
            'risk_limits': {
                'max_var': self.config.get('var_limit', 0.10),
                'max_drawdown': self.config.get('max_drawdown', 0.20),
                'max_concentration': self.config.get('max_concentration', 0.25)
            },
            'violations': self._check_risk_violations()
        }
        
        return report
        
    def generate_strategy_comparison(self) -> pd.DataFrame:
        """Generate strategy comparison matrix"""
        
        if not self.strategy_performance:
            return pd.DataFrame()
            
        # Create comparison dataframe
        data = []
        for strategy_id, perf in self.strategy_performance.items():
            data.append({
                'Strategy': perf.strategy_name,
                'Total PnL': perf.total_pnl,
                'ROI %': perf.roi * 100,
                'Sharpe': perf.sharpe,
                'Win Rate %': perf.win_rate * 100,
                'Capital': perf.capital_allocated,
                'VaR Contribution': perf.var_contribution
            })
            
        df = pd.DataFrame(data)
        df = df.sort_values('Sharpe', ascending=False)
        
        # Add rankings
        df['Rank'] = range(1, len(df) + 1)
        
        return df
        
    # ==================================================================================
    # ANALYTICS CALCULATIONS
    # ==================================================================================
    
    def _calculate_daily_return(self, positions: Dict) -> float:
        """Calculate daily return"""
        daily_pnl = sum(p.get('daily_pnl', 0) for p in positions.values())
        return daily_pnl / self.portfolio_value
        
    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio"""
        if len(self.daily_returns) < 2:
            return 0
            
        returns = np.array(self.daily_returns)
        excess_returns = returns - self.risk_free_rate / 252
        
        if returns.std() == 0:
            return 0
            
        return np.sqrt(252) * excess_returns.mean() / returns.std()
        
    def _calculate_sortino_ratio(self) -> float:
        """Calculate Sortino ratio"""
        if len(self.daily_returns) < 2:
            return 0
            
        returns = np.array(self.daily_returns)
        excess_returns = returns - self.risk_free_rate / 252
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0:
            return float('inf')
            
        downside_std = np.std(downside_returns)
        if downside_std == 0:
            return 0
            
        return np.sqrt(252) * excess_returns.mean() / downside_std
        
    def _calculate_calmar_ratio(self) -> float:
        """Calculate Calmar ratio"""
        max_dd, _ = self._calculate_drawdowns()
        
        if max_dd == 0:
            return 0
            
        annual_return = (1 + self.cumulative_pnl / self.portfolio_value) ** (252 / max(len(self.daily_returns), 1)) - 1
        return annual_return / abs(max_dd)
        
    def _calculate_drawdowns(self) -> Tuple[float, float]:
        """Calculate maximum and current drawdown"""
        if not self.metrics_history:
            return 0, 0
            
        cumulative_returns = [1 + m.total_return for m in self.metrics_history]
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = (cumulative_returns - running_max) / running_max
        
        max_drawdown = min(drawdowns) if len(drawdowns) > 0 else 0
        current_drawdown = drawdowns[-1] if len(drawdowns) > 0 else 0
        
        return max_drawdown, current_drawdown
        
    def _calculate_win_loss_stats(self) -> Dict[str, Any]:
        """Calculate win/loss statistics"""
        if not self.current_positions:
            return {
                'win_rate': 0, 'profit_factor': 0, 'avg_win': 0,
                'avg_loss': 0, 'best_trade': 0, 'worst_trade': 0,
                'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0
            }
            
        trades = [p for p in self.current_positions.values() if p.get('closed', False)]
        
        if not trades:
            return {
                'win_rate': 0, 'profit_factor': 0, 'avg_win': 0,
                'avg_loss': 0, 'best_trade': 0, 'worst_trade': 0,
                'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0
            }
            
        pnls = [t['pnl'] for t in trades]
        winning_trades = [p for p in pnls if p > 0]
        losing_trades = [p for p in pnls if p < 0]
        
        gross_profit = sum(winning_trades)
        gross_loss = abs(sum(losing_trades))
        
        return {
            'win_rate': len(winning_trades) / len(trades) if trades else 0,
            'profit_factor': gross_profit / gross_loss if gross_loss > 0 else float('inf'),
            'avg_win': np.mean(winning_trades) if winning_trades else 0,
            'avg_loss': np.mean(losing_trades) if losing_trades else 0,
            'best_trade': max(pnls) if pnls else 0,
            'worst_trade': min(pnls) if pnls else 0,
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades)
        }
        
    def _calculate_sharpe_from_returns(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio from returns list"""
        if len(returns) < 2:
            return 0
            
        returns_array = np.array(returns)
        excess_returns = returns_array - self.risk_free_rate / 252
        
        if returns_array.std() == 0:
            return 0
            
        return np.sqrt(252) * excess_returns.mean() / returns_array.std()
        
    def _get_strategy_name(self, strategy_id: str) -> str:
        """Get strategy name from ID"""
        strategy_names = {
            'D01': 'Base Strategy',
            'D02': 'Iron Condor',
            'D03': 'Credit Spread',
            'D04': 'Zero DTE',
            'D05': 'Straddle',
            # Add more mappings as needed
        }
        return strategy_names.get(strategy_id, strategy_id)
        
    def _calculate_var_contribution(self, strategy_id: str) -> float:
        """Calculate VaR contribution for strategy"""
        # This would integrate with E12_PortfolioVaR
        return 0.05  # Placeholder
        
    def _calculate_correlation_risk(self) -> float:
        """Calculate correlation risk score"""
        # Measure how correlated strategies are
        return 0.3  # Placeholder
        
    def _calculate_concentration_risk(self) -> float:
        """Calculate concentration risk"""
        if not self.strategy_performance:
            return 0
            
        allocations = [p.capital_allocated for p in self.strategy_performance.values()]
        total = sum(allocations)
        
        if total == 0:
            return 0
            
        # Calculate Herfindahl index
        hhi = sum((a/total)**2 for a in allocations)
        return hhi
        
    def _calculate_current_exposure(self) -> float:
        """Calculate current market exposure"""
        return sum(p.get('value', 0) for p in self.current_positions.values())
        
    def _calculate_market_impact(self, orders: List[Dict]) -> float:
        """Calculate market impact of orders"""
        if not orders:
            return 0
            
        impacts = []
        for order in orders:
            if 'expected_price' in order and 'fill_price' in order:
                impact = abs(order['fill_price'] - order['expected_price']) / order['expected_price']
                impacts.append(impact)
                
        return statistics.mean(impacts) * 10000 if impacts else 0  # in bps
        
    def _calculate_execution_shortfall(self, orders: List[Dict]) -> float:
        """Calculate execution shortfall"""
        if not orders:
            return 0
            
        shortfalls = []
        for order in orders:
            if order['status'] != 'FILLED':
                # Opportunity cost of unfilled orders
                if 'expected_profit' in order:
                    shortfalls.append(order['expected_profit'])
                    
        return sum(shortfalls)
        
    # ==================================================================================
    # REPORT COMPILATION
    # ==================================================================================
    
    def _get_reporting_period(self, timeframe: TimeFrame) -> Dict[str, str]:
        """Get reporting period based on timeframe"""
        end_date = datetime.now()
        
        if timeframe == TimeFrame.DAILY:
            start_date = end_date - timedelta(days=1)
        elif timeframe == TimeFrame.WEEKLY:
            start_date = end_date - timedelta(weeks=1)
        elif timeframe == TimeFrame.MONTHLY:
            start_date = end_date - timedelta(days=30)
        elif timeframe == TimeFrame.QUARTERLY:
            start_date = end_date - timedelta(days=90)
        elif timeframe == TimeFrame.ANNUAL:
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date.replace(hour=0, minute=0, second=0)
            
        return {
            'start': start_date.isoformat(),
            'end': end_date.isoformat()
        }
        
    def _compile_performance_data(self, timeframe: TimeFrame) -> Dict[str, Any]:
        """Compile performance data for reporting period"""
        if not self.metrics_history:
            return {}
            
        latest = self.metrics_history[-1]
        
        return {
            'returns': {
                'total': latest.total_return,
                'daily': latest.daily_return,
                'cumulative': latest.cumulative_return
            },
            'risk_adjusted': {
                'sharpe': latest.sharpe_ratio,
                'sortino': latest.sortino_ratio,
                'calmar': latest.calmar_ratio
            },
            'drawdown': {
                'maximum': latest.max_drawdown,
                'current': latest.current_drawdown
            },
            'win_loss': {
                'win_rate': latest.win_rate,
                'profit_factor': latest.profit_factor,
                'avg_win': latest.avg_win,
                'avg_loss': latest.avg_loss
            }
        }
        
    def _compile_strategy_data(self) -> List[Dict]:
        """Compile strategy performance data"""
        return [asdict(perf) for perf in self.strategy_performance.values()]
        
    def _compile_risk_data(self) -> Dict[str, Any]:
        """Compile risk metrics data"""
        if not self.risk_metrics_history:
            return {}
            
        latest = self.risk_metrics_history[-1]
        
        return {
            'var': {
                '95': latest.portfolio_var_95,
                '99': latest.portfolio_var_99,
                'cvar_99': latest.portfolio_cvar_99
            },
            'tail_risk': latest.tail_risk_score,
            'correlations': latest.correlation_risk,
            'concentration': latest.concentration_risk,
            'regime': latest.regime_risk
        }
        
    def _compile_execution_data(self) -> Dict[str, Any]:
        """Compile execution metrics data"""
        if not self.execution_metrics_history:
            return {}
            
        latest = self.execution_metrics_history[-1]
        
        return {
            'fill_rate': latest.filled_orders / latest.total_orders if latest.total_orders > 0 else 0,
            'avg_fill_time': latest.avg_fill_time,
            'avg_slippage_bps': latest.avg_slippage,
            'total_commissions': latest.total_commissions,
            'market_impact_bps': latest.market_impact
        }
        
    def _perform_attribution_analysis(self) -> Dict[str, Any]:
        """Perform return attribution analysis"""
        attribution = {
            'by_strategy': {},
            'by_factor': {},
            'by_timeframe': {}
        }
        
        # Attribution by strategy
        total_pnl = sum(p.total_pnl for p in self.strategy_performance.values())
        
        for strategy_id, perf in self.strategy_performance.items():
            if total_pnl != 0:
                attribution['by_strategy'][strategy_id] = perf.total_pnl / total_pnl
                
        return attribution
        
    def _generate_recommendations(self) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Check performance metrics
        if self.metrics_history:
            latest = self.metrics_history[-1]
            
            if latest.sharpe_ratio < 0.5:
                recommendations.append("Consider reviewing strategy selection - Sharpe ratio below 0.5")
                
            if latest.max_drawdown < -0.15:
                recommendations.append("High drawdown detected - Consider reducing position sizes")
                
            if latest.win_rate < 0.4:
                recommendations.append("Low win rate - Review entry criteria")
                
        # Check risk metrics
        if self.risk_metrics_history:
            latest_risk = self.risk_metrics_history[-1]
            
            if latest_risk.tail_risk_score > 60:
                recommendations.append("Elevated tail risk - Consider adding hedges")
                
            if latest_risk.concentration_risk > 0.5:
                recommendations.append("High concentration risk - Diversify strategy allocation")
                
        return recommendations
        
    def _decompose_risk(self) -> Dict[str, float]:
        """Decompose portfolio risk by source"""
        # Placeholder implementation
        return {
            'market_risk': 0.60,
            'strategy_risk': 0.25,
            'execution_risk': 0.10,
            'model_risk': 0.05
        }
        
    def _run_stress_tests(self) -> List[Dict]:
        """Run stress test scenarios"""
        # Placeholder implementation
        scenarios = [
            {'scenario': 'Market Crash -20%', 'impact': -0.15},
            {'scenario': 'VIX Spike 3x', 'impact': -0.08},
            {'scenario': 'Correlation to 1', 'impact': -0.12}
        ]
        return scenarios
        
    def _check_risk_violations(self) -> List[str]:
        """Check for risk limit violations"""
        violations = []
        
        if self.risk_metrics_history:
            latest = self.risk_metrics_history[-1]
            
            if latest.portfolio_var_99 > self.config.get('var_limit', 0.10):
                violations.append(f"VaR limit breach: {latest.portfolio_var_99:.2%}")
                
            if latest.current_exposure > latest.max_loss_limit:
                violations.append(f"Exposure limit breach: ${latest.current_exposure:,.0f}")
                
        return violations
        
    def _format_html_report(self, data: Dict) -> str:
        """Format report as HTML"""
        # Simplified HTML generation
        html = f"""
        <html>
        <head><title>Performance Report</title></head>
        <body>
            <h1>Performance Analytics Report</h1>
            <h2>Generated: {data['metadata']['generated_at']}</h2>
            <pre>{json.dumps(data, indent=2)}</pre>
        </body>
        </html>
        """
        return html
        
    def _export_to_excel(self, data: Dict) -> str:
        """Export report to Excel format"""
        # Would use pandas.ExcelWriter in production
        filename = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        # Save logic here
        return filename
        
    def _prepare_dashboard_data(self, data: Dict) -> Dict:
        """Prepare data for dashboard visualization"""
        return {
            'charts': {
                'equity_curve': self._prepare_equity_curve(),
                'drawdown_chart': self._prepare_drawdown_chart(),
                'strategy_performance': self._prepare_strategy_chart(),
                'risk_metrics': self._prepare_risk_chart()
            },
            'tables': {
                'top_strategies': self.generate_strategy_comparison().to_dict('records'),
                'recent_trades': self._get_recent_trades()
            },
            'metrics': data['performance']
        }
        
    def _prepare_equity_curve(self) -> List[Dict]:
        """Prepare equity curve data"""
        if not self.metrics_history:
            return []
            
        return [
            {
                'timestamp': m.timestamp.isoformat(),
                'value': self.portfolio_value * (1 + m.cumulative_return)
            }
            for m in self.metrics_history
        ]
        
    def _prepare_drawdown_chart(self) -> List[Dict]:
        """Prepare drawdown chart data"""
        if not self.metrics_history:
            return []
            
        return [
            {
                'timestamp': m.timestamp.isoformat(),
                'drawdown': m.current_drawdown
            }
            for m in self.metrics_history
        ]
        
    def _prepare_strategy_chart(self) -> Dict:
        """Prepare strategy performance chart"""
        if not self.strategy_performance:
            return {}
            
        return {
            'labels': [p.strategy_name for p in self.strategy_performance.values()],
            'pnl': [p.total_pnl for p in self.strategy_performance.values()],
            'sharpe': [p.sharpe for p in self.strategy_performance.values()]
        }
        
    def _prepare_risk_chart(self) -> Dict:
        """Prepare risk metrics chart"""
        if not self.risk_metrics_history:
            return {}
            
        return {
            'timestamps': [r.timestamp.isoformat() for r in self.risk_metrics_history[-100:]],
            'var_99': [r.portfolio_var_99 for r in self.risk_metrics_history[-100:]],
            'tail_risk': [r.tail_risk_score for r in self.risk_metrics_history[-100:]]
        }
        
    def _get_recent_trades(self, limit: int = 10) -> List[Dict]:
        """Get recent trades for display"""
        # Placeholder - would fetch from trade history
        return []

# ==================================================================================
# FACTORY FUNCTION
# ==================================================================================

def create_performance_analytics(config: Dict[str, Any]) -> PerformanceAnalyticsEngine:
    """Factory function to create performance analytics engine"""
    return PerformanceAnalyticsEngine(config)

# ==================================================================================
# ASYNC REAL-TIME UPDATES
# ==================================================================================

class RealTimePerformanceMonitor:
    """Real-time performance monitoring"""
    
    def __init__(self, analytics_engine: PerformanceAnalyticsEngine):
        self.engine = analytics_engine
        self.update_interval = 1  # seconds
        self.is_running = False
        
    async def start_monitoring(self):
        """Start real-time monitoring"""
        self.is_running = True
        logger.info("Real-time performance monitoring started")
        
        while self.is_running:
            try:
                # Update metrics
                await self._update_metrics()
                
                # Check alerts
                await self._check_performance_alerts()
                
                # Sleep
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")
                
    async def _update_metrics(self):
        """Update performance metrics"""
        # Would fetch real-time data from broker/market data
        pass
        
    async def _check_performance_alerts(self):
        """Check for performance-based alerts"""
        if self.engine.metrics_history:
            latest = self.engine.metrics_history[-1]
            
            # Check for significant changes
            if latest.daily_return < -0.05:
                logger.warning(f"Large daily loss: {latest.daily_return:.2%}")
                
            if latest.current_drawdown < -0.10:
                logger.warning(f"Significant drawdown: {latest.current_drawdown:.2%}")
                
    async def stop_monitoring(self):
        """Stop monitoring"""
        self.is_running = False
        logger.info("Real-time performance monitoring stopped")

# ==================================================================================
# MAIN EXECUTION
# ==================================================================================

if __name__ == "__main__":
    # Example usage
    config = {
        'portfolio_value': 1000000,
        'risk_free_rate': 0.05,
        'var_limit': 0.10,
        'max_drawdown': 0.20,
        'max_concentration': 0.25,
        'max_daily_loss': 50000
    }
    
    # Create analytics engine
    analytics = create_performance_analytics(config)
    
    # Generate sample report
    report = analytics.generate_performance_report(
        timeframe=TimeFrame.DAILY,
        format=ReportFormat.JSON
    )
    
    print(json.dumps(report, indent=2))
    
    # Start real-time monitoring
    monitor = RealTimePerformanceMonitor(analytics)
    
    # Run async monitoring
    # asyncio.run(monitor.start_monitoring())