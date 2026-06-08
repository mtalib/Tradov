8. Standards/Python/Docstring-Format.md

```markdown
# Python Docstring Standards for Tradov Trading System

## Overview

This document defines the docstring format and documentation standards used throughout the Tradov trading system. Consistent documentation is critical for maintaining a complex financial trading system where clarity and precision are essential.

## Google Style Docstrings

Tradov uses Google-style docstrings for all Python modules, classes, and functions. This format is clean, readable, and well-supported by documentation tools.

### Basic Function Docstring

```python
def calculate_option_price(
    spot_price: float,
    strike_price: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float = 0.02
) -> float:
    """
    Calculate European option price using Black-Scholes model.
    
    Args:
        spot_price: Current price of the underlying asset
        strike_price: Strike price of the option
        time_to_expiry: Time to expiration in years
        volatility: Implied volatility as a decimal (e.g., 0.20 for 20%)
        risk_free_rate: Risk-free interest rate as decimal (default: 0.02)
        
    Returns:
        Option price as float
        
    Raises:
        ValueError: If any input parameter is invalid
        ZeroDivisionError: If time_to_expiry is zero
        
    Example:
        >>> price = calculate_option_price(100.0, 105.0, 0.25, 0.20)
        >>> print(f"Option price: ${price:.2f}")
        Option price: $3.45
    """
```

### Complex Function with Multiple Return Types

```python
def analyze_trading_performance(
    trades: List[Dict[str, Any]],
    benchmark_returns: Optional[pd.Series] = None,
    risk_free_rate: float = 0.02
) -> Tuple[Dict[str, float], pd.DataFrame]:
    """
    Analyze trading performance and generate comprehensive metrics.
    
    This function calculates various performance metrics including returns,
    risk-adjusted measures, and drawdown analysis. It can optionally compare
    performance against a benchmark.
    
    Args:
        trades: List of trade dictionaries containing at minimum:
            - 'entry_time': Entry timestamp
            - 'exit_time': Exit timestamp  
            - 'pnl': Profit/loss for the trade
            - 'commission': Trading commission paid
        benchmark_returns: Optional benchmark return series for comparison.
            Index should be datetime, values should be decimal returns.
        risk_free_rate: Annual risk-free rate as decimal for Sharpe calculation
        
    Returns:
        Tuple containing:
        - metrics (Dict[str, float]): Performance metrics including:
            - 'total_return': Total return as decimal
            - 'sharpe_ratio': Risk-adjusted return measure
            - 'max_drawdown': Maximum drawdown experienced
            - 'win_rate': Percentage of winning trades
            - 'profit_factor': Ratio of gross profit to gross loss
        - trade_analysis (pd.DataFrame): Detailed trade-by-trade analysis
        
    Raises:
        ValueError: If trades list is empty or contains invalid data
        KeyError: If required trade fields are missing
        TypeError: If benchmark_returns is not a pandas Series
        
    Example:
        >>> trades = [
        ...     {'entry_time': '2025-01-01', 'exit_time': '2025-01-02', 
        ...      'pnl': 100.0, 'commission': 2.5},
        ...     {'entry_time': '2025-01-03', 'exit_time': '2025-01-04',
        ...      'pnl': -50.0, 'commission': 2.5}
        ... ]
        >>> metrics, analysis = analyze_trading_performance(trades)
        >>> print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        Sharpe Ratio: 1.45
        
    Note:
        Performance metrics are calculated assuming daily compounding.
        Benchmark comparison uses beta calculation if benchmark is provided.
    """
```

### Class Docstrings

```python
class TradingStrategy:
    """
    Base class for all trading strategies in the Tradov system.
    
    This abstract class defines the interface that all trading strategies
    must implement. It provides common functionality for position management,
    risk controls, and performance tracking.
    
    The strategy lifecycle follows this pattern:
    1. Initialize with configuration
    2. Start strategy execution
    3. Generate signals based on market data
    4. Execute trades through position manager
    5. Monitor performance and risk
    6. Stop strategy when needed
    
    Attributes:
        name: Unique identifier for this strategy instance
        is_active: Boolean indicating if strategy is currently running
        positions: Dictionary of current positions keyed by symbol
        performance_metrics: Real-time performance tracking
        
    Example:
        >>> config = StrategyConfig(max_positions=10, risk_per_trade=0.02)
        >>> strategy = MyCustomStrategy("iron_condor_v1", config)
        >>> strategy.start()
        >>> # Strategy will now generate and execute trades automatically
        
    Note:
        Subclasses must implement abstract methods: generate_signals(),
        calculate_position_size(), and validate_signal().
    """
    
    def __init__(self, name: str, config: StrategyConfig):
        """
        Initialize the trading strategy.
        
        Args:
            name: Unique name for this strategy instance
            config: Strategy configuration object containing parameters
                like max_positions, risk_per_trade, etc.
                
        Raises:
            ValueError: If name is empty or config is invalid
        """
        
    def start(self) -> bool:
        """
        Start the trading strategy.
        
        Initializes all required components, validates configuration,
        and begins monitoring market data for trading opportunities.
        
        Returns:
            True if strategy started successfully, False otherwise
            
        Raises:
            RuntimeError: If strategy is already running
            ConnectionError: If unable to connect to required services
        """
        
    def generate_signals(self, market_data: pd.DataFrame) -> List[TradingSignal]:
        """
        Generate trading signals based on current market data.
        
        This is an abstract method that must be implemented by subclasses.
        Each strategy will have its own logic for analyzing market data
        and generating trading opportunities.
        
        Args:
            market_data: DataFrame containing OHLCV data and any additional
                indicators. Index should be datetime, columns should include
                at minimum: 'open', 'high', 'low', 'close', 'volume'
                
        Returns:
            List of TradingSignal objects representing trading opportunities.
            Empty list if no signals generated.
            
        Raises:
            NotImplementedError: If called on base class
            ValueError: If market_data is invalid or empty
        """
```

### Module-Level Docstrings

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovD_Strategies
Module: TradovD02_IronCondor.py
Purpose: Iron Condor options strategy implementation

Author: Trading Team
Year Created: 2025
Last Updated: 2025-01-24 Time: 12:00:00

Module Description:
    This module implements the Iron Condor options trading strategy for the
    Tradov system. An Iron Condor is a neutral strategy that profits from
    low volatility by selling both a put spread and a call spread.
    
    The strategy combines:
    - Short put spread (sell higher strike put, buy lower strike put)
    - Short call spread (sell lower strike call, buy higher strike call)
    
    This creates a position that profits when the underlying stays within
    the short strike range while time decay reduces option values.

Key Features:
    - Dynamic strike selection based on volatility and market conditions
    - Automated position sizing with risk management integration
    - Real-time Greeks monitoring and position adjustment capabilities
    - Paper trading validation before live deployment
    
Strategy Parameters:
    - target_delta: Target delta for short strikes (default: 0.15)
    - max_dte: Maximum days to expiration (default: 45)
    - min_dte: Minimum days to expiration (default: 7)
    - profit_target: Percentage of credit to take profit (default: 0.25)
    - stop_loss: Multiple of credit to stop loss (default: 2.0)
    
Risk Controls:
    - Maximum position size limits per expiration
    - Portfolio-level exposure limits
    - Automatic position closure on adverse moves
    - Integration with system-wide risk management
    
Dependencies:
    - TradovB_Broker: For order execution and position management
    - TradovC_MarketData: For real-time options data
    - TradovE_Risk: For risk validation and position sizing
    - TradovN_OptionsAnalytics: For Greeks calculation and analysis
    
Performance Metrics:
    - Expected annual return: 12-18% based on backtesting
    - Maximum drawdown: Typically <8% with proper risk controls
    - Win rate: ~75% of trades profitable
    - Best market conditions: Low to moderate volatility environments

Change Log:
    2025-01-24 (v2.1.0):
        - Added dynamic strike selection algorithm
        - Improved Greeks-based position adjustment
        - Enhanced risk management integration
        - Added paper trading validation mode
    
    2025-01-15 (v2.0.0):
        - Complete rewrite using new strategy framework
        - Added real-time monitoring capabilities
        - Implemented automated position management
        - Improved backtesting integration
        
    2025-01-01 (v1.0.0):
        - Initial implementation
        - Basic Iron Condor functionality
        - Manual parameter adjustment
"""
```

## Specific Documentation Patterns

### Error Handling Documentation

```python
def validate_option_order(order_data: Dict[str, Any]) -> bool:
    """
    Validate option order data before submission.
    
    Performs comprehensive validation of option order parameters including
    strike prices, expiration dates, contract specifications, and risk limits.
    
    Args:
        order_data: Dictionary containing order information with required keys:
            - 'symbol': Underlying symbol (e.g., 'SPY')
            - 'strike': Strike price as float
            - 'expiry': Expiration date as datetime or ISO string
            - 'option_type': 'CALL' or 'PUT'
            - 'quantity': Number of contracts (positive for buy, negative for sell)
            - 'order_type': 'MKT', 'LMT', 'STP', etc.
            
    Returns:
        True if order passes all validation checks, False otherwise
        
    Raises:
        TypeError: If order_data is not a dictionary
        KeyError: If required order fields are missing
        ValueError: If order field values are invalid (e.g., negative strike)
        ConnectionError: If unable to validate contract specifications
        
    Example:
        >>> order = {
        ...     'symbol': 'SPY', 'strike': 450.0, 'expiry': '2025-02-21',
        ...     'option_type': 'CALL', 'quantity': 1, 'order_type': 'LMT'
        ... }
        >>> if validate_option_order(order):
        ...     print("Order is valid")
        Order is valid
        
    Validation Checks:
        - Symbol format and market availability
        - Strike price within reasonable bounds
        - Expiration date is future date and valid option expiry
        - Option type is 'CALL' or 'PUT'
        - Quantity is non-zero integer
        - Order type is supported
        - Position size within risk limits
        - Sufficient buying power (for long positions)
    """
```

### Async Function Documentation

```python
async def fetch_option_chain_data(
    symbol: str,
    expiry_date: datetime,
    timeout: float = 30.0
) -> Optional[Dict[str, Any]]:
    """
    Asynchronously fetch complete option chain data for given symbol and expiry.
    
    This coroutine retrieves bid/ask prices, volumes, implied volatilities,
    and Greeks for all strikes in the specified option chain. Uses connection
    pooling for efficient data retrieval.
    
    Args:
        symbol: Underlying symbol (e.g., 'SPY', 'QQQ')
        expiry_date: Option expiration date
        timeout: Maximum time to wait for data in seconds
        
    Returns:
        Dictionary containing option chain data if successful, None if failed.
        Structure:
        {
            'symbol': str,
            'expiry': datetime,
            'calls': {strike: option_data, ...},
            'puts': {strike: option_data, ...},
            'timestamp': datetime
        }
        
    Raises:
        asyncio.TimeoutError: If data fetch exceeds timeout
        ConnectionError: If unable to connect to data provider
        ValueError: If symbol is invalid or expiry_date is in the past
        
    Example:
        >>> chain = await fetch_option_chain_data('SPY', 
        ...                                       datetime(2025, 2, 21))
        >>> if chain:
        ...     calls = chain['calls']
        ...     puts = chain['puts']
        
    Note:
        This function requires an active event loop and established connection
        to the options data provider. Use appropriate async context managers.
    """
```

### Property Documentation

```python
class PortfolioManager:
    """Portfolio management with real-time position tracking."""
    
    @property
    def total_portfolio_value(self) -> float:
        """
        Current total value of all positions in the portfolio.
        
        Calculates mark-to-market value of all positions including:
        - Long stock positions at current market price
        - Short stock positions at current market price  
        - Option positions at current bid/ask midpoint
        - Cash balance
        
        Returns:
            Total portfolio value in base currency (USD)
            
        Note:
            Values are updated in real-time as market data changes.
            Calculation includes unrealized gains/losses.
        """
        
    @property
    def available_buying_power(self) -> float:
        """
        Available buying power for new positions.
        
        Calculates remaining buying power considering:
        - Current cash balance
        - Margin requirements for existing positions
        - Reserved capital for risk management
        - Regulatory requirements (Pattern Day Trader rules, etc.)
        
        Returns:
            Available buying power in USD
            
        Note:
            This is a conservative estimate that includes safety margins.
            Actual buying power may vary based on specific order requirements.
        """
```

### Generator and Iterator Documentation

```python
def yield_historical_data(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    chunk_size: int = 1000
) -> Generator[pd.DataFrame, None, None]:
    """
    Generator that yields historical market data in chunks.
    
    Efficiently processes large historical datasets by yielding data in
    manageable chunks. Useful for backtesting or analysis that would
    otherwise consume too much memory.
    
    Args:
        symbol: Security symbol to retrieve data for
        start_date: Beginning of date range (inclusive)
        end_date: End of date range (inclusive)
        chunk_size: Number of rows per chunk (default: 1000)
        
    Yields:
        pd.DataFrame: Chunk of historical data with columns:
            - 'timestamp': Date/time index
            - 'open', 'high', 'low', 'close': OHLC prices
            - 'volume': Trading volume
            - Additional columns may be present
            
    Raises:
        ValueError: If date range is invalid or symbol not found
        IOError: If unable to access historical data source
        
    Example:
        >>> for chunk in yield_historical_data('SPY', 
        ...                                    datetime(2024, 1, 1),
        ...                                    datetime(2024, 12, 31)):
        ...     analysis = analyze_chunk(chunk)
        ...     results.append(analysis)
        
    Note:
        Data is yielded in chronological order. Each chunk contains
        complete trading days - partial days are not split across chunks.
    """
```

## Documentation Best Practices

### Required Sections

Every docstring should include:
1. **Brief summary** (one line)
2. **Detailed description** (if needed)
3. **Args** (if function takes parameters)
4. **Returns** (if function returns values)
5. **Raises** (if function can raise exceptions)
6. **Example** (for complex functions)

### Optional Sections

Include when relevant:
- **Note**: Important implementation details
- **Warning**: Critical usage warnings
- **See Also**: References to related functions
- **References**: Academic papers or external sources
- **Todo**: Known limitations or future improvements

### Writing Guidelines

#### Be Specific and Precise
```python
# Good
def calculate_implied_volatility(option_price: float, ...) -> float:
    """
    Calculate implied volatility using Newton-Raphson method.
    
    Iteratively solves for the volatility that makes the Black-Scholes
    theoretical price equal to the observed market price.
    """

# Bad  
def calculate_iv(price: float, ...) -> float:
    """Calculate IV."""
```

#### Use Standard Terminology
```python
# Good - uses standard financial terms
def calculate_delta_hedge_ratio(position: Dict[str, Any]) -> float:
    """
    Calculate the hedge ratio needed to achieve delta neutrality.
    
    Args:
        position: Dictionary containing position details including
            quantity, delta, and underlying exposure
            
    Returns:
        Number of shares needed to hedge delta exposure
    """

# Bad - unclear terminology
def calc_hedge(pos: dict) -> float:
    """Figure out hedge amount."""
```

#### Include Units and Formats
```python
def calculate_time_to_expiry(expiry_date: datetime) -> float:
    """
    Calculate time to expiration in years.
    
    Args:
        expiry_date: Option expiration date (market close)
        
    Returns:
        Time to expiry as decimal years (e.g., 0.25 for 3 months)
    """
```

#### Document Risk and Financial Impact
```python
def execute_market_order(symbol: str, quantity: int) -> bool:
    """
    Execute market order immediately at current market price.
    
    WARNING: Market orders execute immediately but price is not guaranteed.
    Use limit orders if price control is important.
    
    Args:
        symbol: Stock or option symbol
        quantity: Number of shares/contracts (positive=buy, negative=sell)
        
    Returns:
        True if order executed successfully
        
    Raises:
        InsufficientFundsError: If not enough buying power
        MarketClosedError: If market is closed
        
    Note:
        This function executes real trades that affect account balance.
        Always validate orders in paper trading first.
    """
```

## Code Examples in Docstrings

### Simple Examples
```python
def format_option_symbol(symbol: str, expiry: datetime, strike: float, 
                        option_type: str) -> str:
    """
    Format option symbol according to OCC standard.
    
    Example:
        >>> format_option_symbol('SPY', datetime(2025, 2, 21), 450.0, 'CALL')
        'SPY250221C00450000'
    """
```

### Complex Examples
```python
def backtest_strategy(strategy, start_date, end_date, initial_capital=100000):
    """
    Run comprehensive backtest of trading strategy.
    
    Example:
        >>> from datetime import datetime
        >>> from strategies import IronCondorStrategy
        >>> 
        >>> strategy = IronCondorStrategy({
        ...     'target_delta': 0.15,
        ...     'max_dte': 45,
        ...     'profit_target': 0.25
        ... })
        >>> 
        >>> results = backtest_strategy(
        ...     strategy=strategy,
        ...     start_date=datetime(2023, 1, 1),
        ...     end_date=datetime(2023, 12, 31),
        ...     initial_capital=100000
        ... )
        >>> 
        >>> print(f"Total Return: {results['total_return']:.1%}")
        >>> print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        >>> print(f"Max Drawdown: {results['max_drawdown']:.1%}")
        Total Return: 15.3%
        Sharpe Ratio: 1.42
        Max Drawdown: 6.8%
    """
```

## Testing and Validation

### Docstring Testing
Use doctest for simple examples:
```python
def calculate_annual_return(start_value: float, end_value: float, 
                          years: float) -> float:
    """
    Calculate annualized return rate.
    
    Args:
        start_value: Initial investment value
        end_value: Final investment value  
        years: Number of years held
        
    Returns:
        Annual return as decimal (e.g., 0.15 for 15%)
        
    Example:
        >>> calculate_annual_return(100000, 115000, 1.0)
        0.15
        >>> calculate_annual_return(100000, 150000, 2.0)  # doctest: +ELLIPSIS
        0.224...
    """
    return (end_value / start_value) ** (1 / years) - 1
```

### Documentation Validation
```python
def validate_docstrings():
    """
    Validate that all public functions have proper docstrings.
    
    This function can be used in tests to ensure documentation
    completeness across the codebase.
    """
    # Implementation for checking docstring presence and format
```

---

Following these docstring standards ensures that the Tradov codebase maintains high-quality, consistent documentation that serves both current developers and future maintainers of this critical financial system.
```

