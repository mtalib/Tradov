"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderR06_EnhancedBacktestEngine.py
Group: R (Runtime)
Purpose: Enhanced backtesting engine with risk suite and ML integration
Author: Mohamed Talib
Date Created: 2025-01-08
Last Updated: 2025-01-08 Time: 14:00:00

Description:
    Advanced backtesting engine that integrates with the risk management suite
    (E11-E13), portfolio management (P05-P06), performance analytics (K10), 
    and ML engine (L18). Features event-driven architecture, realistic 
    execution simulation, walk-forward analysis, and Monte Carlo optimization.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import logging
from collections import defaultdict, deque
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import pickle
import sqlite3
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

class BacktestMode(Enum):
    """Backtesting modes"""
    STANDARD = "standard"
    WALK_FORWARD = "walk_forward"
    MONTE_CARLO = "monte_carlo"
    OPTIMIZATION = "optimization"
    STRESS_TEST = "stress_test"
    
class ExecutionModel(Enum):
    """Execution simulation models"""
    INSTANT = "instant"
    MARKET_IMPACT = "market_impact"
    REALISTIC = "realistic"
    ADVERSE = "adverse"
    
class DataFrequency(Enum):
    """Data frequency for backtesting"""
    TICK = "tick"
    SECOND = "1s"
    MINUTE = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    HOUR = "1h"
    DAILY = "1d"
    
class OrderType(Enum):
    """Order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

# ==================================================================================
# DATA CLASSES
# ==================================================================================

@dataclass
class BacktestConfig:
    """Backtest configuration"""
    start_date: datetime
    end_date: datetime
    initial_capital: float
    data_frequency: DataFrequency
    execution_model: ExecutionModel
    commission: float = 1.0  # per contract
    slippage_model: str = "linear"
    use_ml_predictions: bool = True
    use_risk_management: bool = True
    max_positions: int = 10
    position_sizing: str = "kelly"
    walk_forward_periods: int = 12
    monte_carlo_runs: int = 1000
    
@dataclass
class BacktestEvent:
    """Event in backtest"""
    timestamp: datetime
    event_type: str  # 'market_data', 'signal', 'order', 'fill', 'risk'
    data: Dict[str, Any]
    
@dataclass
class BacktestPosition:
    """Position in backtest"""
    symbol: str
    strategy_id: str
    entry_time: datetime
    entry_price: float
    quantity: int
    position_type: str  # 'long', 'short', 'spread'
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: float = 0
    commission: float = 0
    slippage: float = 0
    
@dataclass
class BacktestResult:
    """Backtest results"""
    config: BacktestConfig
    performance_metrics: Dict[str, float]
    equity_curve: pd.DataFrame
    positions: List[BacktestPosition]
    risk_metrics: Dict[str, float]
    ml_performance: Dict[str, float]
    strategy_performance: Dict[str, Dict]
    execution_stats: Dict[str, float]
    optimization_results: Optional[Dict] = None
    monte_carlo_results: Optional[Dict] = None

# ==================================================================================
# EVENT-DRIVEN BACKTEST ENGINE
# ==================================================================================

class EnhancedBacktestEngine:
    """
    Enhanced event-driven backtesting engine with ML and risk integration
    """
    
    def __init__(self, config: BacktestConfig):
        """Initialize backtest engine"""
        self.config = config
        
        # Event queue
        self.event_queue = deque()
        
        # Portfolio state
        self.portfolio_value = config.initial_capital
        self.cash = config.initial_capital
        self.positions = {}
        self.closed_positions = []
        
        # Performance tracking
        self.equity_curve = []
        self.daily_returns = []
        self.metrics_history = []
        
        # Risk management
        self.current_var = 0
        self.tail_risk_score = 0
        self.max_loss_today = 0
        
        # ML predictions cache
        self.ml_predictions = {}
        
        # Strategy performance
        self.strategy_metrics = defaultdict(lambda: {
            'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0
        })
        
        # Execution statistics
        self.execution_stats = {
            'total_orders': 0,
            'filled_orders': 0,
            'rejected_orders': 0,
            'total_slippage': 0,
            'total_commission': 0
        }
        
        # Initialize components
        self._initialize_components()
        
        logger.info(f"Enhanced Backtest Engine initialized for {config.start_date} to {config.end_date}")
        
    def _initialize_components(self):
        """Initialize backtesting components"""
        
        # Initialize mock components for testing
        self.data_handler = MockDataHandler(self.config.data_frequency)
        self.execution_handler = MockExecutionHandler(self.config.execution_model)
        self.risk_manager = MockRiskManager()
        self.ml_engine = MockMLEngine()
        self.portfolio_manager = MockPortfolioManager()
        
        # Strategy registry
        self.strategies = {}
        
    # ==================================================================================
    # MAIN BACKTEST LOOP
    # ==================================================================================
    
    def run_backtest(self, strategies: List[Any], 
                     market_data: pd.DataFrame) -> BacktestResult:
        """Run the backtest"""
        
        logger.info("Starting backtest...")
        
        # Register strategies
        for strategy in strategies:
            self.register_strategy(strategy)
            
        # Initialize market data
        self.data_handler.load_data(market_data)
        
        # Main event loop
        self._run_event_loop()
        
        # Calculate final metrics
        results = self._calculate_results()
        
        logger.info("Backtest completed")
        return results
        
    def _run_event_loop(self):
        """Main event-driven loop"""
        
        current_date = self.config.start_date
        
        while current_date <= self.config.end_date:
            # Generate market events
            self._generate_market_events(current_date)
            
            # Process event queue
            while self.event_queue:
                event = self.event_queue.popleft()
                self._handle_event(event)
                
            # Update portfolio metrics
            self._update_portfolio_metrics(current_date)
            
            # Move to next time period
            current_date = self._next_timestamp(current_date)
            
    def _handle_event(self, event: BacktestEvent):
        """Handle a single event"""
        
        if event.event_type == 'market_data':
            self._handle_market_data(event)
        elif event.event_type == 'signal':
            self._handle_signal(event)
        elif event.event_type == 'order':
            self._handle_order(event)
        elif event.event_type == 'fill':
            self._handle_fill(event)
        elif event.event_type == 'risk':
            self._handle_risk_event(event)
            
    def _handle_market_data(self, event: BacktestEvent):
        """Handle market data event"""
        
        # Update current market state
        market_data = event.data
        
        # Get ML predictions if enabled
        if self.config.use_ml_predictions:
            predictions = self.ml_engine.get_predictions(market_data)
            self.ml_predictions[event.timestamp] = predictions
            
        # Generate signals for each strategy
        for strategy_id, strategy in self.strategies.items():
            signal = strategy.generate_signal(market_data, predictions)
            
            if signal:
                signal_event = BacktestEvent(
                    timestamp=event.timestamp,
                    event_type='signal',
                    data={'strategy_id': strategy_id, 'signal': signal}
                )
                self.event_queue.append(signal_event)
                
    def _handle_signal(self, event: BacktestEvent):
        """Handle trading signal"""
        
        signal_data = event.data
        strategy_id = signal_data['strategy_id']
        signal = signal_data['signal']
        
        # Check risk limits
        if self.config.use_risk_management:
            if not self.risk_manager.approve_signal(signal, self.positions):
                logger.debug(f"Signal rejected by risk manager: {strategy_id}")
                return
                
        # Generate order
        order = self._create_order_from_signal(signal, strategy_id)
        
        if order:
            order_event = BacktestEvent(
                timestamp=event.timestamp,
                event_type='order',
                data={'order': order}
            )
            self.event_queue.append(order_event)
            
    def _handle_order(self, event: BacktestEvent):
        """Handle order event"""
        
        order = event.data['order']
        self.execution_stats['total_orders'] += 1
        
        # Simulate execution
        fill = self.execution_handler.execute_order(
            order, 
            self.data_handler.get_current_price(order['symbol'])
        )
        
        if fill:
            self.execution_stats['filled_orders'] += 1
            
            fill_event = BacktestEvent(
                timestamp=event.timestamp,
                event_type='fill',
                data={'fill': fill}
            )
            self.event_queue.append(fill_event)
        else:
            self.execution_stats['rejected_orders'] += 1
            
    def _handle_fill(self, event: BacktestEvent):
        """Handle order fill"""
        
        fill = event.data['fill']
        
        # Update position
        position = self._update_position(fill)
        
        # Update cash
        self.cash -= (fill['price'] * fill['quantity'] + fill['commission'])
        self.execution_stats['total_commission'] += fill['commission']
        self.execution_stats['total_slippage'] += fill.get('slippage', 0)
        
        # Update strategy metrics
        self.strategy_metrics[fill['strategy_id']]['trades'] += 1
        
    def _handle_risk_event(self, event: BacktestEvent):
        """Handle risk management event"""
        
        risk_data = event.data
        
        if risk_data['type'] == 'stop_loss':
            self._close_position(risk_data['position_id'], risk_data['price'])
        elif risk_data['type'] == 'max_loss':
            self._close_all_positions()
        elif risk_data['type'] == 'var_breach':
            self._reduce_positions(risk_data['reduction_percent'])
            
    # ==================================================================================
    # WALK-FORWARD ANALYSIS
    # ==================================================================================
    
    def run_walk_forward_analysis(self, strategies: List[Any],
                                 market_data: pd.DataFrame) -> Dict[str, Any]:
        """Run walk-forward analysis"""
        
        logger.info("Starting walk-forward analysis...")
        
        periods = self.config.walk_forward_periods
        results = []
        
        # Split data into periods
        data_periods = self._split_data_periods(market_data, periods)
        
        for i in range(len(data_periods) - 1):
            # Train period
            train_data = data_periods[i]
            
            # Optimize on training data
            optimized_params = self._optimize_parameters(strategies, train_data)
            
            # Test period
            test_data = data_periods[i + 1]
            
            # Apply optimized parameters
            self._apply_parameters(strategies, optimized_params)
            
            # Run backtest on test period
            period_result = self.run_backtest(strategies, test_data)
            results.append(period_result)
            
        # Aggregate results
        walk_forward_results = self._aggregate_walk_forward_results(results)
        
        logger.info("Walk-forward analysis completed")
        return walk_forward_results
        
    def _split_data_periods(self, data: pd.DataFrame, periods: int) -> List[pd.DataFrame]:
        """Split data into periods for walk-forward analysis"""
        
        total_days = (self.config.end_date - self.config.start_date).days
        period_length = total_days // periods
        
        periods_data = []
        for i in range(periods):
            start_idx = i * period_length
            end_idx = (i + 1) * period_length if i < periods - 1 else len(data)
            periods_data.append(data.iloc[start_idx:end_idx])
            
        return periods_data
        
    def _optimize_parameters(self, strategies: List[Any], 
                           data: pd.DataFrame) -> Dict[str, Any]:
        """Optimize strategy parameters"""
        
        best_params = {}
        
        for strategy in strategies:
            # Grid search or other optimization
            param_grid = strategy.get_parameter_grid()
            best_sharpe = -float('inf')
            
            for params in param_grid:
                strategy.set_parameters(params)
                result = self.run_backtest([strategy], data)
                
                sharpe = result.performance_metrics.get('sharpe_ratio', 0)
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_params[strategy.name] = params
                    
        return best_params
        
    def _apply_parameters(self, strategies: List[Any], params: Dict[str, Any]):
        """Apply optimized parameters to strategies"""
        
        for strategy in strategies:
            if strategy.name in params:
                strategy.set_parameters(params[strategy.name])
                
    def _aggregate_walk_forward_results(self, results: List[BacktestResult]) -> Dict:
        """Aggregate walk-forward results"""
        
        aggregated = {
            'periods': len(results),
            'avg_sharpe': np.mean([r.performance_metrics['sharpe_ratio'] for r in results]),
            'avg_return': np.mean([r.performance_metrics['total_return'] for r in results]),
            'consistency': self._calculate_consistency(results),
            'period_results': [self._summarize_result(r) for r in results]
        }
        
        return aggregated
        
    # ==================================================================================
    # MONTE CARLO SIMULATION
    # ==================================================================================
    
    def run_monte_carlo_simulation(self, strategies: List[Any],
                                  market_data: pd.DataFrame) -> Dict[str, Any]:
        """Run Monte Carlo simulation"""
        
        logger.info(f"Starting Monte Carlo simulation with {self.config.monte_carlo_runs} runs...")
        
        results = []
        
        # Parallel execution
        with ProcessPoolExecutor(max_workers=mp.cpu_count()) as executor:
            futures = []
            
            for run in range(self.config.monte_carlo_runs):
                # Randomize market data
                randomized_data = self._randomize_market_data(market_data, run)
                
                # Submit backtest job
                future = executor.submit(
                    self._run_single_monte_carlo, 
                    strategies, 
                    randomized_data, 
                    run
                )
                futures.append(future)
                
            # Collect results
            for future in futures:
                result = future.result()
                results.append(result)
                
        # Analyze Monte Carlo results
        monte_carlo_analysis = self._analyze_monte_carlo_results(results)
        
        logger.info("Monte Carlo simulation completed")
        return monte_carlo_analysis
        
    def _run_single_monte_carlo(self, strategies: List[Any],
                               data: pd.DataFrame, run_id: int) -> Dict:
        """Run single Monte Carlo simulation"""
        
        # Create new engine instance for parallel execution
        engine = EnhancedBacktestEngine(self.config)
        
        # Run backtest
        result = engine.run_backtest(strategies, data)
        
        return {
            'run_id': run_id,
            'metrics': result.performance_metrics,
            'final_value': result.equity_curve.iloc[-1]['portfolio_value']
        }
        
    def _randomize_market_data(self, data: pd.DataFrame, seed: int) -> pd.DataFrame:
        """Randomize market data for Monte Carlo"""
        
        np.random.seed(seed)
        
        # Bootstrap returns
        returns = data['close'].pct_change().dropna()
        bootstrapped_returns = np.random.choice(returns, size=len(returns), replace=True)
        
        # Reconstruct price series
        randomized_data = data.copy()
        randomized_data['close'] = (1 + bootstrapped_returns).cumprod() * data['close'].iloc[0]
        
        # Adjust other columns proportionally
        for col in ['high', 'low', 'open']:
            if col in randomized_data.columns:
                ratio = randomized_data['close'] / data['close']
                randomized_data[col] = data[col] * ratio
                
        return randomized_data
        
    def _analyze_monte_carlo_results(self, results: List[Dict]) -> Dict:
        """Analyze Monte Carlo simulation results"""
        
        final_values = [r['final_value'] for r in results]
        sharpe_ratios = [r['metrics']['sharpe_ratio'] for r in results]
        max_drawdowns = [r['metrics']['max_drawdown'] for r in results]
        
        analysis = {
            'statistics': {
                'mean_final_value': np.mean(final_values),
                'std_final_value': np.std(final_values),
                'median_final_value': np.median(final_values),
                'percentile_5': np.percentile(final_values, 5),
                'percentile_95': np.percentile(final_values, 95),
                'mean_sharpe': np.mean(sharpe_ratios),
                'mean_max_drawdown': np.mean(max_drawdowns)
            },
            'risk_metrics': {
                'var_95': np.percentile(final_values, 5) - self.config.initial_capital,
                'cvar_95': np.mean([v for v in final_values if v <= np.percentile(final_values, 5)]) - self.config.initial_capital,
                'probability_of_loss': sum(1 for v in final_values if v < self.config.initial_capital) / len(final_values),
                'probability_of_ruin': sum(1 for v in final_values if v < self.config.initial_capital * 0.5) / len(final_values)
            },
            'distribution': {
                'values': final_values,
                'bins': np.histogram(final_values, bins=50)
            }
        }
        
        return analysis
        
    # ==================================================================================
    # POSITION MANAGEMENT
    # ==================================================================================
    
    def _create_order_from_signal(self, signal: Dict[str, Any], 
                                 strategy_id: str) -> Optional[Dict]:
        """Create order from trading signal"""
        
        # Check position limits
        if len(self.positions) >= self.config.max_positions:
            return None
            
        # Calculate position size
        position_size = self._calculate_position_size(signal, strategy_id)
        
        if position_size == 0:
            return None
            
        order = {
            'symbol': signal['symbol'],
            'strategy_id': strategy_id,
            'quantity': position_size,
            'order_type': signal.get('order_type', OrderType.MARKET),
            'direction': signal['direction'],
            'limit_price': signal.get('limit_price'),
            'stop_price': signal.get('stop_price')
        }
        
        return order
        
    def _calculate_position_size(self, signal: Dict[str, Any], 
                                strategy_id: str) -> int:
        """Calculate position size based on risk management"""
        
        if self.config.position_sizing == 'fixed':
            return 1
            
        elif self.config.position_sizing == 'kelly':
            # Kelly criterion
            win_rate = self.strategy_metrics[strategy_id]['wins'] / max(self.strategy_metrics[strategy_id]['trades'], 1)
            avg_win = signal.get('expected_profit', 100)
            avg_loss = signal.get('expected_loss', 50)
            
            if avg_loss == 0:
                return 1
                
            kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
            kelly = max(min(kelly, 0.25), 0)  # Cap at 25%
            
            position_value = self.portfolio_value * kelly
            position_size = int(position_value / signal.get('price', 100))
            
            return max(min(position_size, 10), 0)
            
        elif self.config.position_sizing == 'risk_parity':
            # Risk parity sizing
            target_risk = 0.02  # 2% risk per position
            position_volatility = signal.get('volatility', 0.20)
            
            if position_volatility == 0:
                return 1
                
            position_value = (target_risk * self.portfolio_value) / position_volatility
            position_size = int(position_value / signal.get('price', 100))
            
            return max(min(position_size, 10), 0)
            
        else:
            return 1
            
    def _update_position(self, fill: Dict[str, Any]) -> BacktestPosition:
        """Update or create position from fill"""
        
        position_id = f"{fill['symbol']}_{fill['strategy_id']}"
        
        if position_id in self.positions:
            # Update existing position
            position = self.positions[position_id]
            position.quantity += fill['quantity']
        else:
            # Create new position
            position = BacktestPosition(
                symbol=fill['symbol'],
                strategy_id=fill['strategy_id'],
                entry_time=fill['timestamp'],
                entry_price=fill['price'],
                quantity=fill['quantity'],
                position_type='long' if fill['quantity'] > 0 else 'short',
                commission=fill['commission']
            )
            self.positions[position_id] = position
            
        return position
        
    def _close_position(self, position_id: str, exit_price: float):
        """Close a position"""
        
        if position_id not in self.positions:
            return
            
        position = self.positions[position_id]
        
        # Calculate P&L
        if position.position_type == 'long':
            position.pnl = (exit_price - position.entry_price) * position.quantity
        else:
            position.pnl = (position.entry_price - exit_price) * position.quantity
            
        position.pnl -= position.commission * 2  # Entry and exit commission
        
        # Update strategy metrics
        strategy_id = position.strategy_id
        self.strategy_metrics[strategy_id]['pnl'] += position.pnl
        
        if position.pnl > 0:
            self.strategy_metrics[strategy_id]['wins'] += 1
        else:
            self.strategy_metrics[strategy_id]['losses'] += 1
            
        # Move to closed positions
        position.exit_time = datetime.now()
        position.exit_price = exit_price
        self.closed_positions.append(position)
        
        del self.positions[position_id]
        
        # Update cash
        self.cash += exit_price * position.quantity - position.commission
        
    def _close_all_positions(self):
        """Close all open positions"""
        
        for position_id in list(self.positions.keys()):
            current_price = self.data_handler.get_current_price(
                self.positions[position_id].symbol
            )
            self._close_position(position_id, current_price)
            
    def _reduce_positions(self, reduction_percent: float):
        """Reduce all positions by percentage"""
        
        for position_id, position in self.positions.items():
            reduce_qty = int(position.quantity * reduction_percent)
            if reduce_qty > 0:
                position.quantity -= reduce_qty
                # Update cash from partial close
                current_price = self.data_handler.get_current_price(position.symbol)
                self.cash += current_price * reduce_qty - position.commission
                
    # ==================================================================================
    # METRICS CALCULATION
    # ==================================================================================
    
    def _update_portfolio_metrics(self, timestamp: datetime):
        """Update portfolio metrics"""
        
        # Calculate portfolio value
        positions_value = sum(
            self.data_handler.get_current_price(p.symbol) * p.quantity
            for p in self.positions.values()
        )
        
        self.portfolio_value = self.cash + positions_value
        
        # Store equity curve point
        self.equity_curve.append({
            'timestamp': timestamp,
            'portfolio_value': self.portfolio_value,
            'cash': self.cash,
            'positions_value': positions_value,
            'positions_count': len(self.positions)
        })
        
        # Calculate daily return
        if len(self.equity_curve) > 1:
            prev_value = self.equity_curve[-2]['portfolio_value']
            daily_return = (self.portfolio_value - prev_value) / prev_value
            self.daily_returns.append(daily_return)
            
    def _calculate_results(self) -> BacktestResult:
        """Calculate final backtest results"""
        
        # Create equity curve DataFrame
        equity_df = pd.DataFrame(self.equity_curve)
        
        # Calculate performance metrics
        performance_metrics = self._calculate_performance_metrics(equity_df)
        
        # Calculate risk metrics
        risk_metrics = self._calculate_risk_metrics(equity_df)
        
        # Calculate ML performance
        ml_performance = self._calculate_ml_performance()
        
        # Create result object
        result = BacktestResult(
            config=self.config,
            performance_metrics=performance_metrics,
            equity_curve=equity_df,
            positions=self.closed_positions,
            risk_metrics=risk_metrics,
            ml_performance=ml_performance,
            strategy_performance=dict(self.strategy_metrics),
            execution_stats=self.execution_stats
        )
        
        return result
        
    def _calculate_performance_metrics(self, equity_df: pd.DataFrame) -> Dict[str, float]:
        """Calculate performance metrics"""
        
        initial_value = self.config.initial_capital
        final_value = equity_df.iloc[-1]['portfolio_value']
        
        # Returns
        total_return = (final_value - initial_value) / initial_value
        
        # Sharpe ratio
        if len(self.daily_returns) > 1:
            sharpe = np.sqrt(252) * np.mean(self.daily_returns) / np.std(self.daily_returns)
        else:
            sharpe = 0
            
        # Max drawdown
        running_max = equity_df['portfolio_value'].expanding().max()
        drawdown = (equity_df['portfolio_value'] - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Win rate
        wins = sum(1 for p in self.closed_positions if p.pnl > 0)
        total_trades = len(self.closed_positions)
        win_rate = wins / total_trades if total_trades > 0 else 0
        
        # Profit factor
        gross_profit = sum(p.pnl for p in self.closed_positions if p.pnl > 0)
        gross_loss = abs(sum(p.pnl for p in self.closed_positions if p.pnl < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        metrics = {
            'total_return': total_return,
            'annual_return': (1 + total_return) ** (252 / len(equity_df)) - 1,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_trades': total_trades,
            'final_value': final_value
        }
        
        return metrics
        
    def _calculate_risk_metrics(self, equity_df: pd.DataFrame) -> Dict[str, float]:
        """Calculate risk metrics"""
        
        if len(self.daily_returns) < 2:
            return {}
            
        returns = np.array(self.daily_returns)
        
        # VaR
        var_95 = np.percentile(returns, 5)
        var_99 = np.percentile(returns, 1)
        
        # CVaR
        cvar_95 = np.mean(returns[returns <= var_95])
        cvar_99 = np.mean(returns[returns <= var_99])
        
        # Sortino ratio
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0:
            sortino = np.sqrt(252) * np.mean(returns) / np.std(downside_returns)
        else:
            sortino = float('inf')
            
        # Calmar ratio
        max_dd = self._calculate_performance_metrics(equity_df)['max_drawdown']
        annual_return = self._calculate_performance_metrics(equity_df)['annual_return']
        calmar = annual_return / abs(max_dd) if max_dd != 0 else 0
        
        metrics = {
            'var_95': var_95,
            'var_99': var_99,
            'cvar_95': cvar_95,
            'cvar_99': cvar_99,
            'sortino_ratio': sortino,
            'calmar_ratio': calmar,
            'volatility': np.std(returns) * np.sqrt(252)
        }
        
        return metrics
        
    def _calculate_ml_performance(self) -> Dict[str, float]:
        """Calculate ML model performance"""
        
        if not self.ml_predictions:
            return {}
            
        # Placeholder for ML performance metrics
        return {
            'prediction_accuracy': 0.65,
            'feature_importance_stability': 0.80,
            'regime_detection_accuracy': 0.75
        }
        
    def _calculate_consistency(self, results: List[BacktestResult]) -> float:
        """Calculate consistency score across periods"""
        
        returns = [r.performance_metrics['total_return'] for r in results]
        positive_periods = sum(1 for r in returns if r > 0)
        
        return positive_periods / len(returns) if returns else 0
        
    def _summarize_result(self, result: BacktestResult) -> Dict:
        """Summarize a backtest result"""
        
        return {
            'total_return': result.performance_metrics['total_return'],
            'sharpe_ratio': result.performance_metrics['sharpe_ratio'],
            'max_drawdown': result.performance_metrics['max_drawdown'],
            'trades': result.performance_metrics['total_trades']
        }
        
    def _generate_market_events(self, timestamp: datetime):
        """Generate market data events"""
        
        # Get market data for timestamp
        market_data = self.data_handler.get_data(timestamp)
        
        if market_data is not None:
            event = BacktestEvent(
                timestamp=timestamp,
                event_type='market_data',
                data=market_data
            )
            self.event_queue.append(event)
            
    def _next_timestamp(self, current: datetime) -> datetime:
        """Get next timestamp based on frequency"""
        
        if self.config.data_frequency == DataFrequency.MINUTE:
            return current + timedelta(minutes=1)
        elif self.config.data_frequency == DataFrequency.MINUTE_5:
            return current + timedelta(minutes=5)
        elif self.config.data_frequency == DataFrequency.HOUR:
            return current + timedelta(hours=1)
        elif self.config.data_frequency == DataFrequency.DAILY:
            return current + timedelta(days=1)
        else:
            return current + timedelta(minutes=1)
            
    def register_strategy(self, strategy: Any):
        """Register a strategy"""
        
        strategy_id = strategy.get_id()
        self.strategies[strategy_id] = strategy
        logger.info(f"Registered strategy: {strategy_id}")

# ==================================================================================
# MOCK COMPONENTS FOR TESTING
# ==================================================================================

class MockDataHandler:
    """Mock data handler for testing"""
    
    def __init__(self, frequency: DataFrequency):
        self.frequency = frequency
        self.data = None
        self.current_index = 0
        
    def load_data(self, data: pd.DataFrame):
        self.data = data
        self.current_index = 0
        
    def get_data(self, timestamp: datetime) -> Optional[Dict]:
        if self.data is None or self.current_index >= len(self.data):
            return None
            
        row = self.data.iloc[self.current_index]
        self.current_index += 1
        
        return {
            'timestamp': timestamp,
            'open': row.get('open', 100),
            'high': row.get('high', 101),
            'low': row.get('low', 99),
            'close': row.get('close', 100),
            'volume': row.get('volume', 1000000)
        }
        
    def get_current_price(self, symbol: str) -> float:
        if self.data is None or self.current_index == 0:
            return 100.0
            
        return self.data.iloc[self.current_index - 1].get('close', 100)
        
class MockExecutionHandler:
    """Mock execution handler"""
    
    def __init__(self, model: ExecutionModel):
        self.model = model
        
    def execute_order(self, order: Dict, current_price: float) -> Optional[Dict]:
        # Simulate execution
        slippage = 0
        
        if self.model == ExecutionModel.MARKET_IMPACT:
            slippage = np.random.uniform(0, 0.001) * current_price
        elif self.model == ExecutionModel.REALISTIC:
            slippage = np.random.uniform(0, 0.002) * current_price
        elif self.model == ExecutionModel.ADVERSE:
            slippage = np.random.uniform(0.001, 0.005) * current_price
            
        fill_price = current_price + slippage if order['direction'] == 'buy' else current_price - slippage
        
        return {
            'symbol': order['symbol'],
            'strategy_id': order['strategy_id'],
            'quantity': order['quantity'],
            'price': fill_price,
            'timestamp': datetime.now(),
            'commission': 1.0,
            'slippage': slippage
        }
        
class MockRiskManager:
    """Mock risk manager"""
    
    def approve_signal(self, signal: Dict, positions: Dict) -> bool:
        # Simple risk checks
        if len(positions) >= 10:
            return False
            
        # Random approval for testing
        return np.random.random() > 0.1
        
class MockMLEngine:
    """Mock ML engine"""
    
    def get_predictions(self, market_data: Dict) -> Dict:
        return {
            'price_prediction': market_data['close'] * (1 + np.random.normal(0, 0.01)),
            'volatility_forecast': 0.15 + np.random.normal(0, 0.02),
            'regime': np.random.choice(['NORMAL', 'HIGH_VOL', 'TRENDING']),
            'confidence': np.random.uniform(0.5, 0.95)
        }
        
class MockPortfolioManager:
    """Mock portfolio manager"""
    
    def optimize_allocation(self, strategies: List) -> Dict:
        allocations = {}
        for strategy in strategies:
            allocations[strategy] = 1.0 / len(strategies)
        return allocations

# ==================================================================================
# STRATEGY BASE CLASS
# ==================================================================================

class BacktestStrategy:
    """Base class for backtest strategies"""
    
    def __init__(self, name: str):
        self.name = name
        self.parameters = {}
        
    def get_id(self) -> str:
        return self.name
        
    def generate_signal(self, market_data: Dict, ml_predictions: Dict) -> Optional[Dict]:
        """Generate trading signal"""
        # Override in subclass
        return None
        
    def get_parameter_grid(self) -> List[Dict]:
        """Get parameter grid for optimization"""
        return [self.parameters]
        
    def set_parameters(self, params: Dict):
        """Set strategy parameters"""
        self.parameters = params

# ==================================================================================
# FACTORY FUNCTION
# ==================================================================================

def create_backtest_engine(config: Dict[str, Any]) -> EnhancedBacktestEngine:
    """Factory function to create backtest engine"""
    
    backtest_config = BacktestConfig(
        start_date=pd.to_datetime(config['start_date']),
        end_date=pd.to_datetime(config['end_date']),
        initial_capital=config.get('initial_capital', 1000000),
        data_frequency=DataFrequency(config.get('data_frequency', 'daily')),
        execution_model=ExecutionModel(config.get('execution_model', 'realistic')),
        commission=config.get('commission', 1.0),
        slippage_model=config.get('slippage_model', 'linear'),
        use_ml_predictions=config.get('use_ml_predictions', True),
        use_risk_management=config.get('use_risk_management', True),
        max_positions=config.get('max_positions', 10),
        position_sizing=config.get('position_sizing', 'kelly'),
        walk_forward_periods=config.get('walk_forward_periods', 12),
        monte_carlo_runs=config.get('monte_carlo_runs', 1000)
    )
    
    return EnhancedBacktestEngine(backtest_config)

# ==================================================================================
# MAIN EXECUTION
# ==================================================================================

if __name__ == "__main__":
    # Example usage
    config = {
        'start_date': '2024-01-01',
        'end_date': '2024-12-31',
        'initial_capital': 1000000,
        'data_frequency': 'daily',
        'execution_model': 'realistic',
        'use_ml_predictions': True,
        'use_risk_management': True
    }
    
    # Create backtest engine
    engine = create_backtest_engine(config)
    
    # Create sample strategy
    class SampleStrategy(BacktestStrategy):
        def generate_signal(self, market_data: Dict, ml_predictions: Dict) -> Optional[Dict]:
            # Simple momentum strategy
            if ml_predictions.get('price_prediction', 0) > market_data['close'] * 1.01:
                return {
                    'symbol': 'SPY',
                    'direction': 'buy',
                    'price': market_data['close'],
                    'expected_profit': 100,
                    'expected_loss': 50,
                    'volatility': ml_predictions.get('volatility_forecast', 0.15)
                }
            return None
            
    # Create sample data
    dates = pd.date_range(start=config['start_date'], end=config['end_date'], freq='D')
    sample_data = pd.DataFrame({
        'date': dates,
        'open': np.random.uniform(440, 460, len(dates)),
        'high': np.random.uniform(445, 465, len(dates)),
        'low': np.random.uniform(435, 455, len(dates)),
        'close': np.random.uniform(440, 460, len(dates)),
        'volume': np.random.uniform(80000000, 120000000, len(dates))
    })
    
    # Run backtest
    strategies = [SampleStrategy('momentum')]
    result = engine.run_backtest(strategies, sample_data)
    
    # Print results
    print("\n=== Backtest Results ===")
    print(f"Total Return: {result.performance_metrics['total_return']:.2%}")
    print(f"Sharpe Ratio: {result.performance_metrics['sharpe_ratio']:.2f}")
    print(f"Max Drawdown: {result.performance_metrics['max_drawdown']:.2%}")
    print(f"Win Rate: {result.performance_metrics['win_rate']:.2%}")
    print(f"Total Trades: {result.performance_metrics['total_trades']}")
    
    # Run walk-forward analysis
    # walk_forward_results = engine.run_walk_forward_analysis(strategies, sample_data)
    # print(f"\nWalk-Forward Avg Sharpe: {walk_forward_results['avg_sharpe']:.2f}")
    
    # Run Monte Carlo simulation
    # monte_carlo_results = engine.run_monte_carlo_simulation(strategies, sample_data)
    # print(f"\nMonte Carlo 95% VaR: ${monte_carlo_results['risk_metrics']['var_95']:,.0f}")