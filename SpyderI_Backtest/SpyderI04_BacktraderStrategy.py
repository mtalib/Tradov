#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderI03_BacktraderStrategy.py
Group: I (Backtesting)
Purpose: Backtrader strategy wrapper for SPYDER strategies

Description:
    This module wraps SPYDER strategies for use with Backtrader's Cerebro
    engine. It enables backtesting with IB historical data while maintaining
    clear warnings about the limitations of options backtesting.

Author: Mohamed Talib
Date: 2025-05-31
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import backtrader as bt
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy, Signal

# ==============================================================================
# CONSTANTS
# ==============================================================================
BACKTRADER_WARNING = """
═══════════════════════════════════════════════════════════════════════
⚠️  BACKTRADER OPTIONS BACKTESTING WARNING ⚠️
═══════════════════════════════════════════════════════════════════════

Even with Backtrader and IB data, options backtesting CANNOT simulate:
• Realistic bid-ask spreads (they change with market conditions)
• Actual fill quality (liquidity varies dramatically)
• Assignment risk (can cause unexpected losses)
• Pin risk near expiration
• Market maker behavior
• Greeks drift in fast markets

This is for STRATEGY LOGIC TESTING ONLY!
Do NOT use results for performance expectations!

For real performance validation, use PAPER TRADING!
═══════════════════════════════════════════════════════════════════════
"""

# ==============================================================================
# BACKTRADER STRATEGY WRAPPER
# ==============================================================================
class SpyderBacktraderStrategy(bt.Strategy):
    """
    Wrapper to use SPYDER strategies with Backtrader.
    
    ⚠️ WARNING: For LOGIC TESTING ONLY!
    Results do NOT represent real trading performance!
    """
    
    # Parameters
    params = (
        ('spyder_strategy', None),  # SPYDER strategy instance
        ('position_size', 1),       # Contracts per trade
        ('use_limit_orders', False),  # Use limit orders (still unrealistic)
        ('slippage_pct', 0.001),    # Fake slippage (real is 10x worse)
        ('commission', 0.65),       # Per contract commission
        ('debug', True),            # Debug logging
        ('logic_test_only', True),  # Emphasize purpose
    )
    
    def __init__(self):
        """Initialize Backtrader strategy wrapper"""
        self.logger = SpyderLogger.get_logger(__name__)
        
        # Print warning
        print(BACKTRADER_WARNING)
        warnings.warn(
            "Backtrader options backtesting is for LOGIC TESTING ONLY!",
            UserWarning,
            stacklevel=2
        )
        
        # Validate SPYDER strategy
        if not self.params.spyder_strategy:
            raise ValueError("Must provide spyder_strategy parameter")
        
        self.spyder_strategy = self.params.spyder_strategy
        
        # Track signals for debugging
        self.generated_signals = []
        self.executed_trades = []
        self.rejected_signals = []
        
        # Position tracking
        self.active_positions = {}
        
        # Setup indicators if needed
        self._setup_indicators()
        
        self.logger.info(
            f"SpyderBacktraderStrategy initialized with {self.spyder_strategy.__class__.__name__}"
        )
        self.logger.warning("Results are for LOGIC TESTING ONLY!")
    
    def _setup_indicators(self):
        """Setup any indicators needed by the strategy"""
        # Example: SMA for trend following strategies
        if hasattr(self.spyder_strategy, 'sma_period'):
            self.sma = bt.indicators.SimpleMovingAverage(
                self.datas[0].close,
                period=self.spyder_strategy.sma_period
            )
        
        # Add other indicators as needed
        # Remember: These are calculated on fake/incomplete data!
    
    def next(self):
        """Called on each bar"""
        # Get current datetime
        current_dt = self.datas[0].datetime.datetime(0)
        
        # Prepare market data for SPYDER strategy
        market_data = self._prepare_market_data()
        
        # Generate signal from SPYDER strategy
        try:
            signal = self.spyder_strategy.generate_signal(market_data)
            
            if signal:
                self.generated_signals.append({
                    'datetime': current_dt,
                    'signal': signal
                })
                
                if self.params.debug:
                    self.log(f"Signal generated: {signal.signal_type} {signal.symbol}")
                
                # Execute signal (unrealistic execution)
                self._execute_signal(signal)
            
        except Exception as e:
            self.logger.error(f"Error generating signal: {e}")
        
        # Check exit conditions
        self._check_exits()
    
    def _prepare_market_data(self) -> Dict[str, Any]:
        """Prepare market data for SPYDER strategy"""
        # Get SPY data (main data feed)
        spy = self.datas[0]
        
        market_data = {
            'timestamp': spy.datetime.datetime(0),
            'symbol': 'SPY',
            'open': spy.open[0],
            'high': spy.high[0],
            'low': spy.low[0],
            'close': spy.close[0],
            'volume': spy.volume[0],
            
            # Add fake bid-ask (unrealistic)
            'bid': spy.close[0] - 0.01,
            'ask': spy.close[0] + 0.01,
            'spread': 0.02,  # Fake tight spread
            
            # Market internals (would need separate feeds)
            'vix': 15.0,  # Fake VIX
            'tick': 0,    # Fake TICK
            'add': 0,     # Fake ADD
        }
        
        # Add option data if available
        if len(self.datas) > 1:
            # Assume additional data feeds are options
            for i, data in enumerate(self.datas[1:], 1):
                option_symbol = f"option_{i}"
                market_data[option_symbol] = {
                    'close': data.close[0],
                    'volume': data.volume[0],
                    'bid': data.close[0] - 0.05,  # Fake spread
                    'ask': data.close[0] + 0.05,
                    
                    # Fake Greeks (completely unrealistic)
                    'delta': 0.5,
                    'gamma': 0.01,
                    'theta': -0.05,
                    'vega': 0.10,
                    'iv': 0.20
                }
        
        return market_data
    
    def _execute_signal(self, signal: Signal):
        """
        Execute trading signal.
        
        ⚠️ This execution is COMPLETELY UNREALISTIC for options!
        """
        # Check if we already have a position
        if signal.symbol in self.active_positions:
            if self.params.debug:
                self.log(f"Already have position in {signal.symbol}")
            self.rejected_signals.append({
                'signal': signal,
                'reason': 'Already positioned'
            })
            return
        
        # Determine which data feed to use
        data_feed = self._get_data_feed(signal.symbol)
        if data_feed is None:
            if self.params.debug:
                self.log(f"No data feed for {signal.symbol}")
            self.rejected_signals.append({
                'signal': signal,
                'reason': 'No data feed'
            })
            return
        
        # Calculate size (unrealistic - no position sizing constraints)
        size = self.params.position_size
        
        # Place order (unrealistic execution)
        if signal.signal_type == 'BUY':
            if self.params.use_limit_orders and signal.limit_price:
                # Limit order (still fills unrealistically well)
                order = self.buy(
                    data=data_feed,
                    size=size,
                    price=signal.limit_price,
                    exectype=bt.Order.Limit
                )
            else:
                # Market order (no realistic slippage)
                order = self.buy(
                    data=data_feed,
                    size=size,
                    exectype=bt.Order.Market
                )
        else:  # SELL
            if self.params.use_limit_orders and signal.limit_price:
                order = self.sell(
                    data=data_feed,
                    size=size,
                    price=signal.limit_price,
                    exectype=bt.Order.Limit
                )
            else:
                order = self.sell(
                    data=data_feed,
                    size=size,
                    exectype=bt.Order.Market
                )
        
        # Track position
        self.active_positions[signal.symbol] = {
            'signal': signal,
            'order': order,
            'entry_time': self.datas[0].datetime.datetime(0),
            'size': size
        }
        
        if self.params.debug:
            self.log(f"Order placed: {signal.signal_type} {size} {signal.symbol}")
    
    def _check_exits(self):
        """Check exit conditions for positions"""
        current_time = self.datas[0].datetime.datetime(0)
        
        for symbol, position in list(self.active_positions.items()):
            signal = position['signal']
            
            # Time-based exit
            if signal.metadata.get('exit_time'):
                if current_time >= signal.metadata['exit_time']:
                    self._exit_position(symbol, 'Time exit')
                    continue
            
            # Get current price (unrealistic - perfect pricing)
            data_feed = self._get_data_feed(symbol)
            if data_feed is None:
                continue
            
            current_price = data_feed.close[0]
            entry_price = position.get('entry_price', current_price)
            
            # Calculate P&L (ignores spreads, commissions, etc.)
            if signal.signal_type == 'BUY':
                pnl_pct = (current_price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - current_price) / entry_price
            
            # Stop loss (unrealistic - perfect execution)
            if signal.stop_loss and pnl_pct <= -signal.stop_loss:
                self._exit_position(symbol, f'Stop loss at {pnl_pct:.1%}')
                continue
            
            # Take profit (unrealistic - perfect execution)
            if signal.take_profit and pnl_pct >= signal.take_profit:
                self._exit_position(symbol, f'Take profit at {pnl_pct:.1%}')
    
    def _exit_position(self, symbol: str, reason: str):
        """Exit a position"""
        if symbol not in self.active_positions:
            return
        
        position = self.active_positions[symbol]
        data_feed = self._get_data_feed(symbol)
        
        if data_feed is None:
            return
        
        # Close position (unrealistic - perfect exit)
        if position['signal'].signal_type == 'BUY':
            self.sell(data=data_feed, size=position['size'])
        else:
            self.buy(data=data_feed, size=position['size'])
        
        # Remove from active positions
        del self.active_positions[symbol]
        
        if self.params.debug:
            self.log(f"Position closed: {symbol} - {reason}")
    
    def _get_data_feed(self, symbol: str):
        """Get data feed for symbol"""
        # For SPY, use main data
        if symbol == 'SPY':
            return self.datas[0]
        
        # For options, would need to map symbol to data feed
        # This is simplified - real implementation would be more complex
        
        # Try to find in additional data feeds
        # In practice, you'd maintain a symbol->data mapping
        
        return None
    
    def notify_order(self, order):
        """Handle order notifications"""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f'BUY EXECUTED (FAKE), Price: {order.executed.price:.2f}, '
                    f'Cost: {order.executed.value:.2f}, '
                    f'Comm: {order.executed.comm:.2f}'
                )
            else:
                self.log(
                    f'SELL EXECUTED (FAKE), Price: {order.executed.price:.2f}, '
                    f'Cost: {order.executed.value:.2f}, '
                    f'Comm: {order.executed.comm:.2f}'
                )
            
            # Update position with execution price
            for symbol, position in self.active_positions.items():
                if position['order'] == order:
                    position['entry_price'] = order.executed.price
                    self.executed_trades.append({
                        'symbol': symbol,
                        'price': order.executed.price,
                        'size': order.executed.size,
                        'datetime': self.datas[0].datetime.datetime(0)
                    })
                    break
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
    
    def notify_trade(self, trade):
        """Handle trade notifications"""
        if not trade.isclosed:
            return
        
        # Log fake P&L (doesn't include realistic costs)
        self.log(
            f'FAKE TRADE PROFIT, GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}'
        )
        self.log('Remember: Real trades would have much worse results!')
    
    def log(self, txt, dt=None):
        """Logging function"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} {txt}')
    
    def stop(self):
        """Called when backtesting ends"""
        print("\n" + "="*60)
        print("BACKTEST COMPLETE - LOGIC TEST RESULTS")
        print("="*60)
        
        print(f"\nSignals Generated: {len(self.generated_signals)}")
        print(f"Trades Executed: {len(self.executed_trades)}")
        print(f"Signals Rejected: {len(self.rejected_signals)}")
        
        # Show rejection reasons
        if self.rejected_signals:
            print("\nRejection Reasons:")
            reasons = {}
            for rejection in self.rejected_signals:
                reason = rejection['reason']
                reasons[reason] = reasons.get(reason, 0) + 1
            
            for reason, count in reasons.items():
                print(f"  {reason}: {count}")
        
        # Final value (FAKE!)
        print(f"\nFinal Portfolio Value: ${self.broker.getvalue():.2f}")
        print("⚠️  This value is FAKE and does NOT represent real trading!")
        print("⚠️  Real trading would likely show significant losses!")
        
        print("\nFor realistic results, use PAPER TRADING!")
        print("="*60 + "\n")

# ==============================================================================
# CEREBRO CONFIGURATION
# ==============================================================================
def create_cerebro_engine(
    spyder_strategy: BaseStrategy,
    initial_cash: float = 100000,
    commission: float = 0.65
) -> bt.Cerebro:
    """
    Create configured Cerebro engine for options backtesting.
    
    ⚠️ WARNING: Results are for LOGIC TESTING ONLY!
    
    Args:
        spyder_strategy: SPYDER strategy instance
        initial_cash: Starting capital
        commission: Per contract commission
        
    Returns:
        Configured Cerebro instance
    """
    print("\n" + "="*60)
    print("CREATING CEREBRO ENGINE FOR LOGIC TESTING")
    print("Results do NOT represent real trading performance!")
    print("="*60 + "\n")
    
    cerebro = bt.Cerebro()
    
    # Add strategy
    cerebro.addstrategy(
        SpyderBacktraderStrategy,
        spyder_strategy=spyder_strategy,
        debug=True,
        logic_test_only=True
    )
    
    # Set initial cash
    cerebro.broker.setcash(initial_cash)
    
    # Set commission (simplified - real options have complex fee structures)
    cerebro.broker.setcommission(
        commission=commission,
        mult=100,  # Options multiplier
        margin=None,
        commtype=bt.CommInfoBase.COMM_FIXED
    )
    
    # Add fake slippage (real slippage is much worse)
    cerebro.broker.set_slippage_perc(
        perc=0.001,  # 0.1% - real options can have 5-10% slippage!
        slip_open=True,
        slip_limit=False,  # Limits still fill too well
        slip_match=True
    )
    
    # Add analyzers for debugging
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    
    # Disable optimization (not meaningful with fake data)
    cerebro.optreturn = False
    
    return cerebro

# ==============================================================================
# BACKTEST RUNNER
# ==============================================================================
def run_logic_test_backtest(
    cerebro: bt.Cerebro,
    spy_data: pd.DataFrame,
    option_feeds: Optional[Dict[str, bt.feeds.PandasData]] = None,
    plot: bool = False
) -> None:
    """
    Run backtesting for logic testing.
    
    Args:
        cerebro: Configured Cerebro instance
        spy_data: SPY historical data
        option_feeds: Optional dict of option data feeds
        plot: Whether to plot results (not recommended for options)
    """
    # Add SPY data
    spy_feed = bt.feeds.PandasData(
        dataname=spy_data,
        datetime=None,
        open='open',
        high='high',
        low='low',
        close='close',
        volume='volume'
    )
    cerebro.adddata(spy_feed, name='SPY')
    
    # Add option feeds if provided
    if option_feeds:
        print(f"Adding {len(option_feeds)} option feeds...")
        for symbol, feed in option_feeds.items():
            cerebro.adddata(feed, name=symbol)
    
    # Run backtest
    print("\nRunning backtest (LOGIC TEST ONLY)...")
    results = cerebro.run()
    
    # Get analyzers
    strat = results[0]
    trades = strat.analyzers.trades.get_analysis()
    returns = strat.analyzers.returns.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()
    
    # Print analysis
    print("\n" + "="*60)
    print("LOGIC TEST ANALYSIS (NOT REAL PERFORMANCE!)")
    print("="*60)
    
    print("\nTrade Analysis:")
    print(f"  Total Trades: {trades.total.closed}")
    print(f"  Won: {trades.won.total}")
    print(f"  Lost: {trades.lost.total}")
    
    if trades.total.closed > 0:
        win_rate = trades.won.total / trades.total.closed * 100
        print(f"  Win Rate: {win_rate:.1f}%")
    
    print("\nReturns (FAKE!):")
    print(f"  Total Return: {returns.rtot:.2%}")
    
    print("\nDrawdown (FAKE!):")
    print(f"  Max Drawdown: {drawdown.max.drawdown:.2%}")
    
    print("\n⚠️  These metrics are based on:")
    print("  - Perfect fills (not realistic)")
    print("  - No bid-ask spreads")
    print("  - No assignment risk")
    print("  - Simplified commission")
    print("  - No market impact")
    
    print("\nUse PAPER TRADING for real performance data!")
    print("="*60 + "\n")
    
    # Plot if requested (not meaningful for options)
    if plot:
        print("Plotting (remember: this is FAKE data!)...")
        cerebro.plot(style='candlestick', volume=False)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    print("SpyderBacktraderStrategy module")
    print("\nThis wraps SPYDER strategies for use with Backtrader")
    print("Remember: Options backtesting provides LOGIC TESTING ONLY!")
    print("Results do NOT predict real trading performance!")
    print("\nFor real performance validation:")
    print("1. Use paper trading for 4-8 weeks")
    print("2. Analyze with SpyderL07_PaperTradeLearner.py")
    print("3. Start live trading with small size")