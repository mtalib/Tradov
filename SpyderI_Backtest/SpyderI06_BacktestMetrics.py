#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderI04_BacktestMetrics.py
Group: I (Backtesting)
Purpose: Performance metrics for LOGIC VALIDATION ONLY

═══════════════════════════════════════════════════════════════════════
⚠️ ⚠️ ⚠️  CRITICAL WARNING - READ BEFORE USING  ⚠️ ⚠️ ⚠️
═══════════════════════════════════════════════════════════════════════

These metrics are calculated on FAKE BACKTESTING DATA!
They do NOT represent real trading performance!

WHY THESE METRICS ARE MISLEADING FOR OPTIONS:
❌ Sharpe Ratio: Ignores bid-ask spread impact (often 50% of profit)
❌ Win Rate: Assumes perfect fills (real fills often miss)
❌ Profit Factor: Based on unrealistic entry/exit prices
❌ Max Drawdown: Doesn't include assignment risk losses
❌ Return metrics: Ignore real execution costs and slippage

REAL OPTIONS TRADING HAS:
• Wide spreads that destroy theoretical profits
• Partial fills that leave you exposed
• Assignment risk that creates unexpected losses
• Greeks that change your P&L unpredictably
• Market makers who widen spreads when you need to exit

USE THIS MODULE ONLY TO:
✅ Verify metric calculation code works
✅ Test strategy logic flow
✅ Debug calculation errors
✅ Understand metric relationships

FOR REAL PERFORMANCE METRICS:
Paper trade for 4-8 weeks, then analyze with SpyderL07_PaperTradeLearner.py

═══════════════════════════════════════════════════════════════════════

Author: Mohamed Talib
Date: 2025-05-30
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import warnings
from datetime import datetime, timedelta

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
METRICS_WARNING = """
╔════════════════════════════════════════════════════════════════════════╗
║                    ⚠️  METRICS CALCULATOR WARNING ⚠️                     ║
╠════════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║ These metrics are calculated on FAKE DATA and are NOT REALISTIC!      ║
║                                                                        ║
║ In real options trading:                                               ║
║ • A 60% "win rate" becomes 40% after spreads and slippage            ║
║ • A 2.0 "Sharpe ratio" becomes negative with real execution costs    ║
║ • "Max drawdown" can double with assignment risk                      ║
║ • "Average win" shrinks by 30-50% due to bid-ask spreads            ║
║                                                                        ║
║ Example Reality Check:                                                 ║
║ Fake Backtest: +50% return, 1.5 Sharpe                               ║
║ Paper Trading: +5% return, 0.3 Sharpe                                ║
║ Live Trading: -10% return, negative Sharpe                           ║
║                                                                        ║
║ ONLY TRUST METRICS FROM ACTUAL PAPER/LIVE TRADING!                   ║
╚════════════════════════════════════════════════════════════════════════╝
"""

# Risk-free rate for Sharpe (but Sharpe is meaningless on fake data)
RISK_FREE_RATE = 0.05
TRADING_DAYS_YEAR = 252

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class FakeTradeMetrics:
    """Trade metrics calculated on FAKE DATA - NOT REALISTIC!"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # These are all FAKE metrics
    fake_win_rate: float = 0.0
    fake_profit_factor: float = 0.0
    fake_avg_win: float = 0.0
    fake_avg_loss: float = 0.0
    fake_largest_win: float = 0.0
    fake_largest_loss: float = 0.0
    
    # Reality check
    is_realistic: bool = False
    warning: str = "These metrics are based on FAKE data!"
    reality_discount: float = 0.5  # Real performance is often 50% worse

class FakeRiskMetrics:
    """Risk metrics calculated on FAKE DATA - NOT REALISTIC!"""
    # Fake volatility metrics
    fake_volatility: float = 0.0
    fake_downside_deviation: float = 0.0
    fake_max_drawdown: float = 0.0
    fake_max_drawdown_duration: int = 0
    
    # Fake risk ratios (meaningless for real trading)
    fake_sharpe_ratio: float = 0.0
    fake_sortino_ratio: float = 0.0
    fake_calmar_ratio: float = 0.0
    
    # Reality check
    is_realistic: bool = False
    warning: str = "Real risk is MUCH higher than these fake metrics!"
    assignment_risk_ignored: bool = True
    spread_cost_ignored: bool = True

class FakePerformanceMetrics:
    """Overall performance metrics - ALL FAKE!"""
    # Big warning
    warning: str = field(default=METRICS_WARNING)
    is_valid_for_decisions: bool = field(default=False)
    
    # Fake returns
    fake_total_return: float = 0.0
    fake_annual_return: float = 0.0
    fake_monthly_returns: List[float] = field(default_factory=list)
    
    # Fake trade metrics
    trade_metrics: FakeTradeMetrics = field(default_factory=FakeTradeMetrics)
    
    # Fake risk metrics
    risk_metrics: FakeRiskMetrics = field(default_factory=FakeRiskMetrics)
    
    # Debug info (somewhat useful)
    calculation_errors: List[str] = field(default_factory=list)
    data_quality_issues: List[str] = field(default_factory=list)
    
    def print_reality_check(self):
        """Print reality check for users"""
        print("\n" + "="*80)
        print("REALITY CHECK - THESE METRICS ARE FAKE!")
        print("="*80)
        print("\nFake Metrics vs Reality:")
        print(f"  Fake Win Rate: {self.trade_metrics.fake_win_rate:.1%}")
        print(f"  Real Win Rate: Probably {self.trade_metrics.fake_win_rate * 0.7:.1%} or worse")
        print(f"\n  Fake Sharpe: {self.risk_metrics.fake_sharpe_ratio:.2f}")
        print(f"  Real Sharpe: Likely negative after costs")
        print(f"\n  Fake Max Drawdown: {self.risk_metrics.fake_max_drawdown:.1%}")
        print(f"  Real Max Drawdown: Could be 2x worse with assignment risk")
        print("\nUSE PAPER TRADING FOR REAL METRICS!")
        print("="*80 + "\n")

# ==============================================================================
# METRICS CALCULATOR CLASS
# ==============================================================================
class BacktestMetricsCalculator:
    """
    Calculate performance metrics on FAKE DATA for LOGIC TESTING ONLY.
    
    ⚠️ WARNING: These metrics are NOT realistic for options trading!
    
    Real options trading performance is dramatically different due to:
    - Bid-ask spreads (often $0.10-$0.50 per contract)
    - Liquidity constraints (can't exit when you want)
    - Assignment risk (unexpected losses)
    - Greeks behavior (non-linear P&L)
    - Market maker games (spreads widen when you need them most)
    
    Use this ONLY to verify calculation logic works correctly.
    """
    
    def __init__(self):
        """Initialize metrics calculator for FAKE DATA."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Print warning
        print(METRICS_WARNING)
        warnings.warn(
            "BacktestMetricsCalculator uses FAKE data - metrics not valid for trading!",
            UserWarning,
            stacklevel=2
        )
        
        self.logger.warning("MetricsCalculator initialized - FOR LOGIC TESTING ONLY!")
        self.logger.warning("These metrics do NOT represent real trading performance!")
    
    # ==========================================================================
    # FAKE METRICS CALCULATION
    # ==========================================================================
    def calculate_fake_metrics(
        self,
        fake_trades: List[Dict[str, Any]],
        fake_equity_curve: pd.Series,
        initial_capital: float
    ) -> FakePerformanceMetrics:
        """
        Calculate fake metrics for LOGIC TESTING ONLY.
        
        ⚠️ These metrics are NOT realistic!
        
        Args:
            fake_trades: List of fake trades
            fake_equity_curve: Fake equity curve
            initial_capital: Starting capital
            
        Returns:
            FakePerformanceMetrics with warnings
        """
        self.logger.warning("Calculating FAKE metrics - not valid for trading!")
        
        metrics = FakePerformanceMetrics()
        metrics.print_reality_check()  # Show warning immediately
        
        try:
            # Calculate fake trade metrics
            metrics.trade_metrics = self._calculate_fake_trade_metrics(fake_trades)
            
            # Calculate fake returns
            fake_returns = self._calculate_fake_returns(fake_equity_curve, initial_capital)
            metrics.fake_total_return = fake_returns['total']
            metrics.fake_annual_return = fake_returns['annual']
            metrics.fake_monthly_returns = fake_returns['monthly']
            
            # Calculate fake risk metrics
            metrics.risk_metrics = self._calculate_fake_risk_metrics(
                fake_equity_curve,
                fake_returns['daily_returns']
            )
            
            # Add data quality warnings
            metrics.data_quality_issues.append("Based on perfect fills - not realistic!")
            metrics.data_quality_issues.append("Ignores bid-ask spreads")
            metrics.data_quality_issues.append("No assignment risk modeled")
            metrics.data_quality_issues.append("Greeks behavior simplified")
            
        except Exception as e:
            self.logger.error(f"Error calculating fake metrics: {e}")
            metrics.calculation_errors.append(str(e))
        
        return metrics
    
    def _calculate_fake_trade_metrics(self, fake_trades: List[Dict[str, Any]]) -> FakeTradeMetrics:
        """Calculate fake trade metrics - NOT REALISTIC!"""
        trade_metrics = FakeTradeMetrics()
        
        if not fake_trades:
            return trade_metrics
        
        # Count trades (but fills are fake)
        trade_metrics.total_trades = len(fake_trades)
        
        # Separate fake winners/losers
        fake_winners = [t for t in fake_trades if t.get('pnl', 0) > 0]
        fake_losers = [t for t in fake_trades if t.get('pnl', 0) < 0]
        
        trade_metrics.winning_trades = len(fake_winners)
        trade_metrics.losing_trades = len(fake_losers)
        
        # Fake win rate (real win rate is much lower)
        if trade_metrics.total_trades > 0:
            trade_metrics.fake_win_rate = trade_metrics.winning_trades / trade_metrics.total_trades
        
        # Fake profit metrics (ignore real costs)
        if fake_winners:
            gross_fake_profit = sum(t['pnl'] for t in fake_winners)
            trade_metrics.fake_avg_win = gross_fake_profit / len(fake_winners)
            trade_metrics.fake_largest_win = max(t['pnl'] for t in fake_winners)
        
        if fake_losers:
            gross_fake_loss = abs(sum(t['pnl'] for t in fake_losers))
            trade_metrics.fake_avg_loss = gross_fake_loss / len(fake_losers)
            trade_metrics.fake_largest_loss = min(t['pnl'] for t in fake_losers)
            
            # Fake profit factor (meaningless without real costs)
            if gross_fake_loss > 0:
                trade_metrics.fake_profit_factor = gross_fake_profit / gross_fake_loss if fake_winners else 0
        
        return trade_metrics
    
    def _calculate_fake_returns(
        self,
        fake_equity_curve: pd.Series,
        initial_capital: float
    ) -> Dict[str, Any]:
        """Calculate fake returns - NOT REALISTIC!"""
        if len(fake_equity_curve) < 2:
            return {
                'total': 0.0,
                'annual': 0.0,
                'monthly': [],
                'daily_returns': pd.Series()
            }
        
        # Fake total return
        fake_total_return = (fake_equity_curve.iloc[-1] - initial_capital) / initial_capital
        
        # Fake annualized return (ignores real trading friction)
        days = len(fake_equity_curve)
        years = days / TRADING_DAYS_YEAR
        fake_annual_return = (1 + fake_total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # Fake daily returns
        fake_daily_returns = fake_equity_curve.pct_change().fillna(0)
        
        # Fake monthly returns (if enough data)
        fake_monthly_returns = []
        if hasattr(fake_equity_curve.index, 'to_period'):
            monthly = fake_equity_curve.resample('M').last()
            fake_monthly_returns = monthly.pct_change().dropna().tolist()
        
        return {
            'total': fake_total_return,
            'annual': fake_annual_return,
            'monthly': fake_monthly_returns,
            'daily_returns': fake_daily_returns
        }
    
    def _calculate_fake_risk_metrics(
        self,
        fake_equity_curve: pd.Series,
        fake_daily_returns: pd.Series
    ) -> FakeRiskMetrics:
        """Calculate fake risk metrics - NOT REALISTIC!"""
        risk_metrics = FakeRiskMetrics()
        
        if len(fake_daily_returns) < 2:
            return risk_metrics
        
        # Fake volatility (real volatility includes gap risk, assignment risk, etc.)
        risk_metrics.fake_volatility = fake_daily_returns.std() * np.sqrt(TRADING_DAYS_YEAR)
        
        # Fake downside deviation (ignores tail risk)
        downside_returns = fake_daily_returns[fake_daily_returns < 0]
        if len(downside_returns) > 0:
            risk_metrics.fake_downside_deviation = downside_returns.std() * np.sqrt(TRADING_DAYS_YEAR)
        
        # Fake max drawdown (doesn't include assignment losses)
        drawdown = self._calculate_fake_drawdown(fake_equity_curve)
        risk_metrics.fake_max_drawdown = drawdown['max_drawdown']
        risk_metrics.fake_max_drawdown_duration = drawdown['max_duration']
        
        # Fake Sharpe ratio (meaningless without real costs)
        if risk_metrics.fake_volatility > 0:
            excess_return = fake_daily_returns.mean() * TRADING_DAYS_YEAR - RISK_FREE_RATE
            risk_metrics.fake_sharpe_ratio = excess_return / risk_metrics.fake_volatility
        
        # Fake Sortino ratio (ignores real downside risk)
        if risk_metrics.fake_downside_deviation > 0:
            excess_return = fake_daily_returns.mean() * TRADING_DAYS_YEAR - RISK_FREE_RATE
            risk_metrics.fake_sortino_ratio = excess_return / risk_metrics.fake_downside_deviation
        
        # Fake Calmar ratio (based on fake drawdown)
        if risk_metrics.fake_max_drawdown > 0:
            annual_return = fake_daily_returns.mean() * TRADING_DAYS_YEAR
            risk_metrics.fake_calmar_ratio = annual_return / risk_metrics.fake_max_drawdown
        
        return risk_metrics
    
    def _calculate_fake_drawdown(self, fake_equity_curve: pd.Series) -> Dict[str, float]:
        """Calculate fake drawdown - NOT REALISTIC!"""
        if len(fake_equity_curve) < 2:
            return {'max_drawdown': 0.0, 'max_duration': 0}
        
        # Calculate running maximum
        running_max = fake_equity_curve.expanding().max()
        
        # Calculate drawdown
        drawdown = (fake_equity_curve - running_max) / running_max
        
        # Find max drawdown (but it's fake!)
        max_drawdown = abs(drawdown.min())
        
        # Calculate duration (simplified)
        underwater = drawdown < 0
        duration = 0
        max_duration = 0
        
        for is_underwater in underwater:
            if is_underwater:
                duration += 1
                max_duration = max(max_duration, duration)
            else:
                duration = 0
        
        return {
            'max_drawdown': max_drawdown,
            'max_duration': max_duration
        }
    
    # ==========================================================================
    # REPORTING
    # ==========================================================================
    def generate_fake_report(self, metrics: FakePerformanceMetrics) -> str:
        """Generate report emphasizing FAKE nature of metrics"""
        report = []
        report.append("=" * 80)
        report.append("FAKE BACKTEST METRICS - NOT VALID FOR TRADING!")
        report.append("=" * 80)
        report.append("")
        report.append("⚠️  ALL METRICS BELOW ARE BASED ON UNREALISTIC ASSUMPTIONS! ⚠️")
        report.append("")
        
        # Trade metrics
        report.append("--- FAKE TRADE METRICS (Ignoring Spreads & Slippage) ---")
        report.append(f"Total Trades: {metrics.trade_metrics.total_trades}")
        report.append(f"Fake Win Rate: {metrics.trade_metrics.fake_win_rate:.1%} (Real: Much Lower)")
        report.append(f"Fake Profit Factor: {metrics.trade_metrics.fake_profit_factor:.2f} (Real: <1.0)")
        report.append(f"Fake Avg Win: ${metrics.trade_metrics.fake_avg_win:.2f} (Real: -50% after costs)")
        report.append(f"Fake Avg Loss: ${metrics.trade_metrics.fake_avg_loss:.2f} (Real: Worse)")
        report.append("")
        
        # Risk metrics
        report.append("--- FAKE RISK METRICS (Ignoring Assignment & Gap Risk) ---")
        report.append(f"Fake Sharpe Ratio: {metrics.risk_metrics.fake_sharpe_ratio:.2f} (Real: Negative?)")
        report.append(f"Fake Max Drawdown: {metrics.risk_metrics.fake_max_drawdown:.1%} (Real: 2x Worse)")
        report.append(f"Fake Volatility: {metrics.risk_metrics.fake_volatility:.1%} (Real: Higher)")
        report.append("")
        
        # Returns
        report.append("--- FAKE RETURNS (Perfect Fills, No Costs) ---")
        report.append(f"Fake Total Return: {metrics.fake_total_return:.1%}")
        report.append(f"Fake Annual Return: {metrics.fake_annual_return:.1%}")
        report.append("")
        
        # Data quality issues
        report.append("--- WHY THESE METRICS ARE FAKE ---")
        for issue in metrics.data_quality_issues:
            report.append(f"• {issue}")
        report.append("")
        
        # Reality check
        report.append("--- REALITY CHECK ---")
        report.append("In real options trading:")
        report.append("• Bid-ask spreads eat 20-50% of theoretical profit")
        report.append("• Slippage on market orders adds 1-5% loss per trade")
        report.append("• Assignment risk can create 100%+ losses")
        report.append("• Liquidity issues prevent exits at desired prices")
        report.append("• Market makers widen spreads when you need to exit")
        report.append("")
        
        report.append("--- WHAT TO DO INSTEAD ---")
        report.append("1. Use these metrics ONLY to verify code logic")
        report.append("2. Start PAPER TRADING immediately")
        report.append("3. Trade for 4-8 weeks with real market data")
        report.append("4. Analyze REAL results with SpyderL07_PaperTradeLearner.py")
        report.append("5. Only trust metrics from actual trading!")
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def calculate_reality_adjusted_estimate(
        self,
        fake_metrics: FakePerformanceMetrics
    ) -> Dict[str, float]:
        """
        Provide reality-adjusted estimates to show how bad real trading might be.
        
        ⚠️ Even these adjustments are optimistic!
        """
        adjustments = {
            'fake_win_rate': fake_metrics.trade_metrics.fake_win_rate,
            'reality_adjusted_win_rate': fake_metrics.trade_metrics.fake_win_rate * 0.7,
            'pessimistic_win_rate': fake_metrics.trade_metrics.fake_win_rate * 0.5,
            
            'fake_sharpe': fake_metrics.risk_metrics.fake_sharpe_ratio,
            'reality_adjusted_sharpe': max(-0.5, fake_metrics.risk_metrics.fake_sharpe_ratio - 1.5),
            'pessimistic_sharpe': -1.0,
            
            'fake_return': fake_metrics.fake_total_return,
            'reality_adjusted_return': fake_metrics.fake_total_return * 0.2,
            'pessimistic_return': -0.20,
            
            'fake_max_dd': fake_metrics.risk_metrics.fake_max_drawdown,
            'reality_adjusted_max_dd': min(0.50, fake_metrics.risk_metrics.fake_max_drawdown * 2),
            'pessimistic_max_dd': 0.75
        }
        
        print("\n" + "="*80)
        print("REALITY ADJUSTMENT ESTIMATES")
        print("(Even these are probably optimistic!)")
        print("="*80)
        
        print("\nWin Rate:")
        print(f"  Fake Backtest: {adjustments['fake_win_rate']:.1%}")
        print(f"  Reality Adjusted: {adjustments['reality_adjusted_win_rate']:.1%}")
        print(f"  Pessimistic: {adjustments['pessimistic_win_rate']:.1%}")
        
        print("\nSharpe Ratio:")
        print(f"  Fake Backtest: {adjustments['fake_sharpe']:.2f}")
        print(f"  Reality Adjusted: {adjustments['reality_adjusted_sharpe']:.2f}")
        print(f"  Pessimistic: {adjustments['pessimistic_sharpe']:.2f}")
        
        print("\nTotal Return:")
        print(f"  Fake Backtest: {adjustments['fake_return']:.1%}")
        print(f"  Reality Adjusted: {adjustments['reality_adjusted_return']:.1%}")
        print(f"  Pessimistic: {adjustments['pessimistic_return']:.1%}")
        
        print("\nMax Drawdown:")
        print(f"  Fake Backtest: {adjustments['fake_max_dd']:.1%}")
        print(f"  Reality Adjusted: {adjustments['reality_adjusted_max_dd']:.1%}")
        print(f"  Pessimistic: {adjustments['pessimistic_max_dd']:.1%}")
        
        print("\nREMEMBER: Only paper trading gives real performance data!")
        print("="*80 + "\n")
        
        return adjustments

# ==============================================================================
# COMPARISON UTILITIES
# ==============================================================================
class FakeVsRealComparison:
    """
    Shows the dramatic difference between fake backtest and real trading.
    
    This is educational to show why backtesting fails for options.
    """
    
    @staticmethod
    def show_typical_differences():
        """Show typical differences between fake and real metrics"""
        examples = """
        ═══════════════════════════════════════════════════════════════════
                     TYPICAL FAKE BACKTEST vs REAL TRADING
        ═══════════════════════════════════════════════════════════════════
        
        EXAMPLE 1: Iron Condor Strategy
        --------------------------------
        Fake Backtest:
        • Win Rate: 85%
        • Avg Win: $150
        • Avg Loss: $500
        • Sharpe: 1.8
        • Annual Return: +35%
        
        Real Trading:
        • Win Rate: 65% (missed fills, early exits)
        • Avg Win: $80 (bid-ask spread eats profit)
        • Avg Loss: $750 (slippage on stop losses)
        • Sharpe: -0.3
        • Annual Return: -15%
        
        Why the Difference?
        • $0.10-0.20 bid-ask on 4-leg trade = $40-80 cost
        • Stops hit at worst prices during volatility
        • Can't exit when you want (liquidity)
        • Assignment risk creates unexpected losses
        
        EXAMPLE 2: 0DTE Strategy
        -------------------------
        Fake Backtest:
        • 200 trades/month
        • Win Rate: 70%
        • Avg profit: $50
        • Monthly return: +15%
        
        Real Trading:
        • 100 trades/month (many signals unfillable)
        • Win Rate: 45% (wide spreads prevent good entries)
        • Avg profit: $15 (after costs)
        • Monthly return: -8%
        
        Why the Difference?
        • 0DTE spreads widen dramatically
        • Can't get filled at mid price
        • Gamma risk ignored in backtest
        • Pin risk at expiration
        
        EXAMPLE 3: Credit Spread Strategy
        ---------------------------------
        Fake Backtest:
        • Profit Factor: 2.5
        • Max Drawdown: 15%
        • 90% winning months
        
        Real Trading:
        • Profit Factor: 0.8 (losing money)
        • Max Drawdown: 45% (assignment losses)
        • 40% winning months
        
        Why the Difference?
        • Early assignment on tested shorts
        • Spread widening prevents adjustments
        • Overnight gaps create losses
        • Actual volatility higher than modeled
        
        ═══════════════════════════════════════════════════════════════════
        CONCLUSION: ALWAYS PAPER TRADE BEFORE BELIEVING ANY METRICS!
        ═══════════════════════════════════════════════════════════════════
        """
        print(examples)
    
    @staticmethod
    def calculate_spread_impact(
        fake_pnl: float,
        num_legs: int,
        avg_spread_per_leg: float = 0.10
    ) -> Dict[str, float]:
        """
        Show impact of bid-ask spreads on P&L.
        
        Args:
            fake_pnl: Fake P&L from backtest
            num_legs: Number of option legs
            avg_spread_per_leg: Average spread per contract
            
        Returns:
            Reality-adjusted P&L
        """
        # Calculate spread cost
        spread_cost = num_legs * avg_spread_per_leg * 100  # Per contract
        
        # Adjust P&L
        real_pnl = fake_pnl - spread_cost
        
        impact = {
            'fake_pnl': fake_pnl,
            'spread_cost': spread_cost,
            'real_pnl': real_pnl,
            'pnl_reduction_pct': (spread_cost / abs(fake_pnl) * 100) if fake_pnl != 0 else 0
        }
        
        print(f"\nSpread Impact Analysis:")
        print(f"  Fake P&L: ${fake_pnl:.2f}")
        print(f"  Spread Cost ({num_legs} legs × ${avg_spread_per_leg}): ${spread_cost:.2f}")
        print(f"  Real P&L: ${real_pnl:.2f}")
        print(f"  Impact: {impact['pnl_reduction_pct']:.1f}% of profit lost to spreads")
        
        return impact

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================
def demonstrate_metrics_are_fake():
    """Demonstrate that metrics are fake and not useful for trading"""
    print("\n" + "="*80)
    print("DEMONSTRATING WHY BACKTEST METRICS ARE FAKE")
    print("="*80 + "\n")
    
    # Create fake data
    fake_trades = [
        {'pnl': 100, 'entry_time': datetime.now()},
        {'pnl': 150, 'entry_time': datetime.now()},
        {'pnl': -50, 'entry_time': datetime.now()},
        {'pnl': 200, 'entry_time': datetime.now()},
        {'pnl': -75, 'entry_time': datetime.now()},
    ]
    
    # Create fake equity curve
    fake_equity = pd.Series([100000, 100100, 100250, 100200, 100400, 100325])
    
    # Calculate fake metrics
    calculator = BacktestMetricsCalculator()
    fake_metrics = calculator.calculate_fake_metrics(fake_trades, fake_equity, 100000)
    
    # Show report
    report = calculator.generate_fake_report(fake_metrics)
    print(report)
    
    # Show reality adjustments
    calculator.calculate_reality_adjusted_estimate(fake_metrics)
    
    # Show typical differences
    FakeVsRealComparison.show_typical_differences()
    
    # Show spread impact
    print("\n" + "="*80)
    print("SPREAD IMPACT EXAMPLE")
    print("="*80)
    FakeVsRealComparison.calculate_spread_impact(
        fake_pnl=200,  # $200 "profit"
        num_legs=4,    # Iron Condor
        avg_spread_per_leg=0.15  # Realistic spread
    )

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    print(METRICS_WARNING)
    
    # Demonstrate fake metrics
    demonstrate_metrics_are_fake()
    
    print("\n" + "="*80)
    print("REMEMBER:")
    print("1. These metrics are for LOGIC TESTING ONLY")
    print("2. Real performance comes from PAPER TRADING")
    print("3. Use SpyderL07_PaperTradeLearner.py for real analysis")
    print("4. Never trust backtest results for options!")
    print("="*80 + "\n")
        