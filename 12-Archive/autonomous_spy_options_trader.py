"""
Autonomous SPY Options Trading System
Implements Renaissance Technologies-inspired algorithmic trading for SPY options
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import warnings
warnings.filterwarnings('ignore')


class OptionType(Enum):
    """Option type enumeration"""
    CALL = "call"
    PUT = "put"


class SignalType(Enum):
    """Trading signal types"""
    BUY = 1
    SELL = -1
    HOLD = 0


@dataclass
class OptionContract:
    """Represents an option contract"""
    symbol: str
    strike: float
    expiry: datetime
    option_type: OptionType
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    implied_vol: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


@dataclass
class TradingSignal:
    """Represents a trading signal"""
    timestamp: datetime
    signal_type: SignalType
    contract: OptionContract
    confidence: float
    entry_price: float
    target_price: Optional[float]
    stop_loss: Optional[float]
    position_size: int
    reasoning: str


class PortfolioManager:
    """
    Manages portfolio positions and risk
    Implements Renaissance-style position sizing and risk management
    """
    
    def __init__(self, initial_capital: float = 100000, 
                 max_position_size: float = 0.05,
                 max_portfolio_risk: float = 0.02):
        """
        Args:
            initial_capital: Starting capital
            max_position_size: Maximum position size as fraction of capital (e.g., 0.05 = 5%)
            max_portfolio_risk: Maximum portfolio risk per trade (e.g., 0.02 = 2%)
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.max_position_size = max_position_size
        self.max_portfolio_risk = max_portfolio_risk
        self.positions: List[Dict] = []
        self.trade_history: List[Dict] = []
        
    def calculate_position_size(self, entry_price: float, stop_loss: float,
                                confidence: float) -> int:
        """
        Calculate position size using Renaissance-style risk-based sizing
        
        Position size is proportional to:
        1. Statistical confidence
        2. Risk per contract (entry - stop loss)
        3. Maximum portfolio risk limit
        
        Args:
            entry_price: Entry price per contract
            stop_loss: Stop loss price
            confidence: Signal confidence (0-1)
            
        Returns:
            Number of contracts to trade
        """
        # Risk per contract
        risk_per_contract = abs(entry_price - stop_loss)
        
        if risk_per_contract == 0:
            return 0
        
        # Maximum capital to risk on this trade
        max_risk_capital = self.current_capital * self.max_portfolio_risk
        
        # Adjust by confidence (higher confidence = larger position)
        adjusted_risk_capital = max_risk_capital * confidence
        
        # Calculate number of contracts
        num_contracts = int(adjusted_risk_capital / risk_per_contract)
        
        # Ensure we don't exceed max position size
        max_contracts_by_size = int((self.current_capital * self.max_position_size) / entry_price)
        num_contracts = min(num_contracts, max_contracts_by_size)
        
        # Ensure at least 1 contract if signal is strong enough
        if num_contracts == 0 and confidence > 0.7:
            num_contracts = 1
        
        return num_contracts
    
    def add_position(self, signal: TradingSignal) -> bool:
        """
        Add a new position to the portfolio
        
        Args:
            signal: Trading signal with position details
            
        Returns:
            True if position added successfully
        """
        position_value = signal.entry_price * signal.position_size * 100  # Options are per 100 shares
        
        if position_value > self.current_capital:
            return False
        
        position = {
            'entry_time': signal.timestamp,
            'contract': signal.contract,
            'signal_type': signal.signal_type,
            'entry_price': signal.entry_price,
            'position_size': signal.position_size,
            'stop_loss': signal.stop_loss,
            'target_price': signal.target_price,
            'confidence': signal.confidence,
            'current_pnl': 0
        }
        
        self.positions.append(position)
        self.current_capital -= position_value
        
        return True
    
    def update_positions(self, current_prices: Dict[str, float]) -> None:
        """
        Update all positions with current prices and check exit conditions
        
        Args:
            current_prices: Dictionary mapping contract symbols to current prices
        """
        positions_to_close = []
        
        for i, position in enumerate(self.positions):
            contract_symbol = position['contract'].symbol
            
            if contract_symbol not in current_prices:
                continue
            
            current_price = current_prices[contract_symbol]
            entry_price = position['entry_price']
            
            # Calculate P&L
            if position['signal_type'] == SignalType.BUY:
                pnl = (current_price - entry_price) * position['position_size'] * 100
            else:  # SELL
                pnl = (entry_price - current_price) * position['position_size'] * 100
            
            position['current_pnl'] = pnl
            
            # Check exit conditions
            should_exit = False
            exit_reason = ""
            
            # Stop loss hit
            if position['stop_loss'] is not None:
                if position['signal_type'] == SignalType.BUY and current_price <= position['stop_loss']:
                    should_exit = True
                    exit_reason = "Stop loss"
                elif position['signal_type'] == SignalType.SELL and current_price >= position['stop_loss']:
                    should_exit = True
                    exit_reason = "Stop loss"
            
            # Target price hit
            if position['target_price'] is not None:
                if position['signal_type'] == SignalType.BUY and current_price >= position['target_price']:
                    should_exit = True
                    exit_reason = "Target reached"
                elif position['signal_type'] == SignalType.SELL and current_price <= position['target_price']:
                    should_exit = True
                    exit_reason = "Target reached"
            
            if should_exit:
                positions_to_close.append((i, current_price, exit_reason))
        
        # Close positions (in reverse order to maintain indices)
        for i, exit_price, reason in reversed(positions_to_close):
            self.close_position(i, exit_price, reason)
    
    def close_position(self, position_idx: int, exit_price: float, reason: str) -> None:
        """
        Close a position and record the trade
        
        Args:
            position_idx: Index of position to close
            exit_price: Exit price
            reason: Reason for closing
        """
        position = self.positions[position_idx]
        
        # Calculate final P&L
        if position['signal_type'] == SignalType.BUY:
            pnl = (exit_price - position['entry_price']) * position['position_size'] * 100
        else:
            pnl = (position['entry_price'] - exit_price) * position['position_size'] * 100
        
        # Return capital
        position_value = exit_price * position['position_size'] * 100
        self.current_capital += position_value
        
        # Record trade
        trade_record = {
            'entry_time': position['entry_time'],
            'exit_time': datetime.now(),
            'contract': position['contract'].symbol,
            'signal_type': position['signal_type'],
            'entry_price': position['entry_price'],
            'exit_price': exit_price,
            'position_size': position['position_size'],
            'pnl': pnl,
            'return_pct': (pnl / (position['entry_price'] * position['position_size'] * 100)) * 100,
            'exit_reason': reason,
            'confidence': position['confidence']
        }
        
        self.trade_history.append(trade_record)
        
        # Remove position
        del self.positions[position_idx]
    
    def get_performance_metrics(self) -> Dict:
        """
        Calculate portfolio performance metrics
        
        Returns:
            Dictionary of performance metrics
        """
        if not self.trade_history:
            # Calculate current capital including open positions
            total_capital = self.current_capital
            for position in self.positions:
                position_value = position['entry_price'] * position['position_size'] * 100
                total_capital += position_value
            
            return {
                'total_trades': 0,
                'win_rate': 0,
                'avg_return': 0,
                'total_pnl': 0,
                'sharpe_ratio': 0,
                'current_capital': total_capital,
                'total_return': ((total_capital - self.initial_capital) / self.initial_capital) * 100
            }
        
        df = pd.DataFrame(self.trade_history)
        
        total_trades = len(df)
        winning_trades = len(df[df['pnl'] > 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        avg_return = df['return_pct'].mean()
        total_pnl = df['pnl'].sum()
        
        # Calculate Sharpe ratio (simplified)
        returns = df['return_pct'].values
        sharpe_ratio = (np.mean(returns) / np.std(returns)) if np.std(returns) > 0 else 0
        
        # Calculate current capital including open positions
        total_capital = self.current_capital
        for position in self.positions:
            # Add value of open positions
            position_value = position['entry_price'] * position['position_size'] * 100
            total_capital += position_value
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_return': avg_return,
            'total_pnl': total_pnl,
            'sharpe_ratio': sharpe_ratio,
            'current_capital': total_capital,
            'total_return': ((total_capital - self.initial_capital) / self.initial_capital) * 100
        }


class AutonomousSPYOptionsTrader:
    """
    Main autonomous trading system for SPY options
    Implements Renaissance Technologies-inspired algorithmic strategies
    """
    
    def __init__(self, initial_capital: float = 100000):
        """
        Args:
            initial_capital: Starting capital for trading
        """
        self.portfolio = PortfolioManager(initial_capital)
        self.min_confidence = 0.65  # Minimum confidence to trade (Renaissance: ~50.75% win rate)
        self.min_iv_percentile = 30  # Minimum IV percentile for buying options
        self.max_iv_percentile = 70  # Maximum IV percentile for selling options
        
    def analyze_option_chain(self, spy_price: float, option_chain: List[OptionContract],
                            spy_data: pd.DataFrame) -> List[TradingSignal]:
        """
        Analyze option chain and generate trading signals
        
        Args:
            spy_price: Current SPY price
            option_chain: List of available option contracts
            spy_data: Historical SPY price data
            
        Returns:
            List of trading signals
        """
        signals = []
        
        # Calculate market indicators
        zscore = self._calculate_zscore(spy_data['close'])
        iv_percentile = self._calculate_iv_percentile(spy_data['implied_vol'])
        
        for contract in option_chain:
            signal = self._evaluate_contract(contract, spy_price, zscore, iv_percentile)
            
            if signal and signal.confidence >= self.min_confidence:
                signals.append(signal)
        
        # Sort by confidence (highest first)
        signals.sort(key=lambda x: x.confidence, reverse=True)
        
        return signals
    
    def _calculate_zscore(self, prices: pd.Series, window: int = 20) -> float:
        """Calculate current Z-score"""
        if len(prices) < window:
            return 0.0
        
        recent_prices = prices.tail(window)
        mean = recent_prices.mean()
        std = recent_prices.std()
        
        if std == 0:
            return 0.0
        
        current_price = prices.iloc[-1]
        zscore = (current_price - mean) / std
        
        return zscore
    
    def _calculate_iv_percentile(self, iv_series: pd.Series, window: int = 252) -> float:
        """Calculate IV percentile"""
        if len(iv_series) < 2:
            return 50.0
        
        recent_iv = iv_series.tail(min(window, len(iv_series)))
        current_iv = iv_series.iloc[-1]
        
        percentile = (recent_iv < current_iv).sum() / len(recent_iv) * 100
        
        return percentile
    
    def _evaluate_contract(self, contract: OptionContract, spy_price: float,
                          zscore: float, iv_percentile: float) -> Optional[TradingSignal]:
        """
        Evaluate a single option contract for trading opportunity
        
        Args:
            contract: Option contract to evaluate
            spy_price: Current SPY price
            zscore: Current price Z-score
            iv_percentile: Current IV percentile
            
        Returns:
            TradingSignal if opportunity found, None otherwise
        """
        # Days to expiration
        days_to_expiry = (contract.expiry - datetime.now()).days
        
        # Skip if too close to expiration or too far out
        if days_to_expiry < 7 or days_to_expiry > 60:
            return None
        
        # Calculate moneyness
        if contract.option_type == OptionType.CALL:
            moneyness = (contract.strike - spy_price) / spy_price
        else:
            moneyness = (spy_price - contract.strike) / spy_price
        
        # Focus on slightly OTM options (higher probability, better risk/reward)
        if abs(moneyness) > 0.05 or abs(moneyness) < 0.01:
            return None
        
        # Mean reversion strategy
        signal_type = None
        confidence = 0.0
        reasoning = ""
        
        # Strategy 1: Mean reversion on extreme Z-scores
        if zscore > 2.0:  # Overbought
            # Buy puts (expect reversion down)
            if contract.option_type == OptionType.PUT and iv_percentile < self.max_iv_percentile:
                signal_type = SignalType.BUY
                confidence = min(0.5 + (zscore - 2.0) * 0.1, 0.95)
                reasoning = f"Mean reversion: Z-score {zscore:.2f} suggests overbought, buying puts"
                
        elif zscore < -2.0:  # Oversold
            # Buy calls (expect reversion up)
            if contract.option_type == OptionType.CALL and iv_percentile < self.max_iv_percentile:
                signal_type = SignalType.BUY
                confidence = min(0.5 + (abs(zscore) - 2.0) * 0.1, 0.95)
                reasoning = f"Mean reversion: Z-score {zscore:.2f} suggests oversold, buying calls"
        
        # Strategy 2: Theta decay (sell premium when IV is high)
        if iv_percentile > self.max_iv_percentile and days_to_expiry <= 30:
            # Sell options to capture theta decay
            if abs(moneyness) > 0.02:  # Further OTM for selling
                signal_type = SignalType.SELL
                confidence = 0.55 + (iv_percentile - 70) * 0.005
                reasoning = f"Theta decay: IV percentile {iv_percentile:.1f}%, selling premium"
        
        if signal_type is None:
            return None
        
        # Calculate entry, target, and stop loss
        mid_price = (contract.bid + contract.ask) / 2
        
        if signal_type == SignalType.BUY:
            entry_price = contract.ask  # Buy at ask
            target_price = entry_price * 1.5  # 50% profit target
            stop_loss = entry_price * 0.7  # 30% stop loss
        else:  # SELL
            entry_price = contract.bid  # Sell at bid
            target_price = entry_price * 0.5  # Close at 50% profit
            stop_loss = entry_price * 1.5  # 50% stop loss
        
        # Calculate position size
        position_size = self.portfolio.calculate_position_size(
            entry_price, stop_loss, confidence
        )
        
        if position_size == 0:
            return None
        
        signal = TradingSignal(
            timestamp=datetime.now(),
            signal_type=signal_type,
            contract=contract,
            confidence=confidence,
            entry_price=entry_price,
            target_price=target_price,
            stop_loss=stop_loss,
            position_size=position_size,
            reasoning=reasoning
        )
        
        return signal
    
    def execute_signals(self, signals: List[TradingSignal], max_new_positions: int = 3) -> None:
        """
        Execute trading signals (add positions to portfolio)
        
        Args:
            signals: List of trading signals
            max_new_positions: Maximum number of new positions to open
        """
        positions_added = 0
        
        for signal in signals:
            if positions_added >= max_new_positions:
                break
            
            success = self.portfolio.add_position(signal)
            
            if success:
                positions_added += 1
                print(f"[{signal.timestamp}] Opened {signal.signal_type.name} position:")
                print(f"  Contract: {signal.contract.symbol}")
                print(f"  Entry: ${signal.entry_price:.2f}")
                print(f"  Size: {signal.position_size} contracts")
                print(f"  Confidence: {signal.confidence:.2%}")
                print(f"  Reasoning: {signal.reasoning}\n")
    
    def run_trading_cycle(self, spy_price: float, option_chain: List[OptionContract],
                         spy_data: pd.DataFrame) -> None:
        """
        Run one complete trading cycle
        
        Args:
            spy_price: Current SPY price
            option_chain: Available option contracts
            spy_data: Historical SPY data
        """
        # Generate signals
        signals = self.analyze_option_chain(spy_price, option_chain, spy_data)
        
        # Execute signals
        if signals:
            self.execute_signals(signals)
        
        # Update existing positions
        current_prices = {contract.symbol: (contract.bid + contract.ask) / 2 
                         for contract in option_chain}
        self.portfolio.update_positions(current_prices)
        
        # Display performance
        metrics = self.portfolio.get_performance_metrics()
        print(f"Portfolio Performance:")
        print(f"  Total Trades: {metrics['total_trades']}")
        print(f"  Win Rate: {metrics['win_rate']:.2%}")
        print(f"  Total P&L: ${metrics['total_pnl']:.2f}")
        print(f"  Current Capital: ${metrics['current_capital']:.2f}")
        print(f"  Total Return: {metrics['total_return']:.2f}%\n")


# Example usage
if __name__ == "__main__":
    print("Renaissance-Style Autonomous SPY Options Trading System")
    print("=" * 70)
    print("Implementing statistical arbitrage and mean reversion strategies\n")
    
    # Initialize trader
    trader = AutonomousSPYOptionsTrader(initial_capital=100000)
    
    # Simulate SPY data
    dates = pd.date_range('2024-01-01', periods=252, freq='D')
    spy_prices = 450 + np.cumsum(np.random.randn(252) * 2)
    spy_data = pd.DataFrame({
        'close': spy_prices,
        'implied_vol': np.random.uniform(0.15, 0.30, 252)
    }, index=dates)
    
    # Simulate option chain
    current_spy = spy_prices[-1]
    option_chain = [
        OptionContract(
            symbol=f"SPY{datetime.now().strftime('%y%m%d')}C{int(current_spy + i)}",
            strike=current_spy + i,
            expiry=datetime.now() + timedelta(days=30),
            option_type=OptionType.CALL,
            bid=max(5 - abs(i) * 0.5, 0.5),
            ask=max(5.2 - abs(i) * 0.5, 0.6),
            last=max(5.1 - abs(i) * 0.5, 0.55),
            volume=1000,
            open_interest=5000,
            implied_vol=0.25,
            delta=0.5 - i * 0.05,
            gamma=0.02,
            theta=-0.05,
            vega=0.15,
            rho=0.03
        )
        for i in range(-5, 6)
    ]
    
    # Run trading cycle
    trader.run_trading_cycle(current_spy, option_chain, spy_data)
    
    print("\nSystem ready for autonomous trading!")
    print("Target win rate: ~50.75% (Renaissance style)")
    print("Strategy: Statistical arbitrage + Mean reversion + Theta decay")
