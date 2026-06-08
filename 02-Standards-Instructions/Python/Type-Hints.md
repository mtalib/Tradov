## 10. Standards/Python/Type-Hints.md

```markdown
# Type Hints Standards for Tradov Trading System

## Overview

Type hints are mandatory throughout the Tradov trading system to ensure code reliability, enable better IDE support, and catch potential errors before they can cause financial losses. This document defines comprehensive type annotation standards for all Python code.

## Basic Type Annotations

### Primitive Types
```python
from typing import Dict, List, Tuple, Set, Optional, Union, Any
from decimal import Decimal
from datetime import datetime, date, timedelta

# Basic types
account_balance: float = 100000.0
position_count: int = 5
is_market_open: bool = True
symbol: str = "SPY"

# Use Decimal for precise financial calculations
precise_price: Decimal = Decimal('450.25')
commission_rate: Decimal = Decimal('0.65')

# Date and time types
trade_timestamp: datetime = datetime.now()
expiry_date: date = date(2025, 2, 21)
hold_period: timedelta = timedelta(days=30)
```

### Collection Types
```python
from typing import Dict, List, Tuple, Set, Optional

# Lists with specific element types
stock_symbols: List[str] = ["SPY", "QQQ", "IWM"]
price_history: List[float] = [450.0, 451.25, 449.75]
trade_quantities: List[int] = [100, 200, 150]

# Dictionaries with specific key/value types
position_sizes: Dict[str, int] = {"SPY": 100, "QQQ": 50}
option_greeks: Dict[str, float] = {
    "delta": 0.45,
    "gamma": 0.012,
    "theta": -0.08
}

# Complex nested structures
portfolio_positions: Dict[str, List[Dict[str, Any]]] = {
    "SPY": [
        {"strike": 450.0, "expiry": "2025-02-21", "quantity": 10},
        {"strike": 455.0, "expiry": "2025-02-21", "quantity": -5}
    ]
}

# Tuples for fixed-length sequences
price_range: Tuple[float, float] = (445.0, 455.0)
option_specification: Tuple[str, float, datetime, str] = (
    "SPY", 450.0, datetime(2025, 2, 21), "CALL"
)

# Sets for unique collections
active_symbols: Set[str] = {"SPY", "QQQ", "IWM"}
```

## Function Type Annotations

### Basic Function Annotations
```python
def calculate_option_delta(
    spot_price: float,
    strike_price: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float = 0.02
) -> float:
    """Calculate option delta using Black-Scholes model."""
    # Implementation here
    return calculated_delta

def validate_trade_parameters(
    symbol: str,
    quantity: int,
    order_type: str,
    limit_price: Optional[float] = None
) -> bool:
    """Validate trade parameters before order submission."""
    # Implementation here
    return is_valid
```

### Functions with Complex Return Types
```python
def analyze_option_chain(
    symbol: str,
    expiry_date: datetime
) -> Dict[str, Dict[float, Dict[str, float]]]:
    """
    Analyze option chain and return structured data.
    
    Returns:
        Dictionary with structure:
        {
            'calls': {strike: {'bid': float, 'ask': float, 'iv': float}},
            'puts': {strike: {'bid': float, 'ask': float, 'iv': float}}
        }
    """
    return {
        'calls': {450.0: {'bid': 2.5, 'ask': 2.7, 'iv': 0.18}},
        'puts': {450.0: {'bid': 3.1, 'ask': 3.3, 'iv': 0.19}}
    }

def get_portfolio_performance(
    start_date: datetime,
    end_date: datetime
) -> Tuple[float, float, Dict[str, float]]:
    """
    Calculate portfolio performance metrics.
    
    Returns:
        Tuple of (total_return, sharpe_ratio, detailed_metrics)
    """
    total_return = 0.15
    sharpe_ratio = 1.45
    detailed_metrics = {
        'max_drawdown': 0.08,
        'win_rate': 0.72,
        'profit_factor': 1.85
    }
    return total_return, sharpe_ratio, detailed_metrics
```

### Functions with Union Types
```python
from typing import Union

def process_order_response(
    response: Union[str, Dict[str, Any], None]
) -> Optional[str]:
    """
    Process different types of order responses.
    
    Args:
        response: Can be error string, success dict, or None for timeout
        
    Returns:
        Order ID if successful, None otherwise
    """
    if isinstance(response, dict):
        return response.get('order_id')
    elif isinstance(response, str):
        # Handle error message
        return None
    else:
        # Handle None/timeout case
        return None

def parse_market_data(
    data: Union[bytes, str, Dict[str, Any]]
) -> Optional[Dict[str, float]]:
    """Parse market data from various input formats."""
    if isinstance(data, bytes):
        # Parse binary data
        pass
    elif isinstance(data, str):
        # Parse JSON string
        pass
    elif isinstance(data, dict):
        # Already parsed
        pass
    return parsed_data
```

## Class Type Annotations

### Class Attributes and Methods
```python
from typing import ClassVar, Optional, Dict, List
from dataclasses import dataclass
from decimal import Decimal

class TradingStrategy:
    """Base class for all trading strategies."""
    
    # Class variables
    DEFAULT_MAX_POSITIONS: ClassVar[int] = 10
    DEFAULT_RISK_PER_TRADE: ClassVar[float] = 0.02
    
    def __init__(self, name: str, initial_capital: Decimal) -> None:
        """Initialize trading strategy."""
        # Instance attributes with type annotations
        self.name: str = name
        self.initial_capital: Decimal = initial_capital
        self.current_positions: Dict[str, int] = {}
        self.trade_history: List[Dict[str, Any]] = []
        self.is_active: bool = False
        self.performance_metrics: Optional[Dict[str, float]] = None
        
    def add_position(
        self, 
        symbol: str, 
        quantity: int, 
        entry_price: Decimal
    ) -> bool:
        """Add new position to strategy."""
        # Implementation here
        return True
        
    def calculate_portfolio_value(self) -> Decimal:
        """Calculate current portfolio value."""
        # Implementation here
        return Decimal('0')
        
    def get_performance_metrics(self) -> Dict[str, float]:
        """Calculate and return performance metrics."""
        if self.performance_metrics is None:
            self.performance_metrics = self._calculate_metrics()
        return self.performance_metrics
        
    def _calculate_metrics(self) -> Dict[str, float]:
        """Private method to calculate performance metrics."""
        return {
            'total_return': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0
        }
```

### Generic Classes
```python
from typing import TypeVar, Generic, List, Optional

T = TypeVar('T')

class DataBuffer(Generic[T]):
    """Generic buffer for storing typed data."""
    
    def __init__(self, max_size: int) -> None:
        self.max_size: int = max_size
        self.buffer: List[T] = []
        
    def add(self, item: T) -> None:
        """Add item to buffer."""
        if len(self.buffer) >= self.max_size:
            self.buffer.pop(0)  # Remove oldest
        self.buffer.append(item)
        
    def get_latest(self) -> Optional[T]:
        """Get most recent item."""
        return self.buffer[-1] if self.buffer else None
        
    def get_all(self) -> List[T]:
        """Get all items in buffer."""
        return self.buffer.copy()

# Usage with specific types
price_buffer: DataBuffer


# Usage with specific types
price_buffer: DataBuffer[float] = DataBuffer(1000)
trade_buffer: DataBuffer[Dict[str, Any]] = DataBuffer(500)
```

### Dataclass Type Annotations
```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from decimal import Decimal

@dataclass
class TradeOrder:
    """Represents a trading order with type safety."""
    
    symbol: str
    quantity: int
    order_type: str
    price: Optional[Decimal] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Validate order data after initialization."""
        if self.quantity == 0:
            raise ValueError("Quantity cannot be zero")
        if self.order_type not in ['MKT', 'LMT', 'STP']:
            raise ValueError(f"Invalid order type: {self.order_type}")

@dataclass
class OptionContract:
    """Represents an option contract specification."""
    
    underlying: str
    strike: Decimal
    expiry: datetime
    option_type: str  # 'CALL' or 'PUT'
    multiplier: int = 100
    
    # Computed fields
    days_to_expiry: int = field(init=False)
    is_call: bool = field(init=False)
    
    def __post_init__(self) -> None:
        """Calculate computed fields."""
        self.days_to_expiry = (self.expiry.date() - datetime.now().date()).days
        self.is_call = self.option_type.upper() == 'CALL'
```

## Advanced Type Annotations

### Protocol Types (Structural Typing)
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class TradingDataProvider(Protocol):
    """Protocol defining interface for trading data providers."""
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for symbol."""
        ...
        
    def get_option_chain(
        self, 
        symbol: str, 
        expiry: datetime
    ) -> Dict[str, Dict[float, Dict[str, float]]]:
        """Get complete option chain data."""
        ...
        
    def subscribe_to_data(
        self, 
        symbol: str, 
        callback: Callable[[Dict[str, Any]], None]
    ) -> bool:
        """Subscribe to real-time data updates."""
        ...

class IBKRDataProvider:
    """IBKR implementation of trading data provider."""
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        # Implementation specific to IBKR
        return 450.25
        
    def get_option_chain(
        self, 
        symbol: str, 
        expiry: datetime
    ) -> Dict[str, Dict[float, Dict[str, float]]]:
        # IBKR-specific implementation
        return {}
        
    def subscribe_to_data(
        self, 
        symbol: str, 
        callback: Callable[[Dict[str, Any]], None]
    ) -> bool:
        # IBKR-specific subscription logic
        return True

# Type checking
def process_with_provider(provider: TradingDataProvider) -> None:
    """Function that works with any trading data provider."""
    price = provider.get_current_price("SPY")
    if price is not None:
        print(f"SPY price: ${price}")

# Usage
ibkr_provider = IBKRDataProvider()
process_with_provider(ibkr_provider)  # Type checker validates protocol compliance
```

### Callback and Function Types
```python
from typing import Callable, Awaitable, TypeAlias

# Type aliases for complex function signatures
OrderCallback: TypeAlias = Callable[[str, bool, str], None]
DataCallback: TypeAlias = Callable[[str, Dict[str, float]], None]
AsyncOrderCallback: TypeAlias = Callable[[str, bool, str], Awaitable[None]]

# Risk validation function type
RiskValidator: TypeAlias = Callable[
    [str, int, Decimal],  # symbol, quantity, price
    Tuple[bool, Optional[str]]  # (is_valid, error_message)
]

class OrderManager:
    """Order management with typed callbacks."""
    
    def __init__(self) -> None:
        self.order_callbacks: List[OrderCallback] = []
        self.data_callbacks: Dict[str, DataCallback] = {}
        
    def register_order_callback(self, callback: OrderCallback) -> None:
        """Register callback for order status updates."""
        self.order_callbacks.append(callback)
        
    def register_data_callback(
        self, 
        symbol: str, 
        callback: DataCallback
    ) -> None:
        """Register callback for market data updates."""
        self.data_callbacks[symbol] = callback
        
    def set_risk_validator(self, validator: RiskValidator) -> None:
        """Set custom risk validation function."""
        self.risk_validator = validator
        
    def submit_order(
        self,
        symbol: str,
        quantity: int,
        price: Decimal,
        callback: Optional[OrderCallback] = None
    ) -> str:
        """Submit order with optional callback."""
        # Validate order if validator is set
        if hasattr(self, 'risk_validator'):
            is_valid, error = self.risk_validator(symbol, quantity, price)
            if not is_valid:
                raise ValueError(f"Risk validation failed: {error}")
                
        # Submit order logic here
        order_id = "ORD_12345"
        
        # Notify callbacks
        if callback:
            callback(order_id, True, "Order submitted successfully")
            
        return order_id
```

### Async Type Annotations
```python
from typing import AsyncGenerator, AsyncIterator
import asyncio

async def fetch_market_data_stream(
    symbol: str,
    duration: timedelta
) -> AsyncGenerator[Dict[str, float], None]:
    """Async generator for streaming market data."""
    
    end_time = datetime.now() + duration
    
    while datetime.now() < end_time:
        # Simulate fetching real-time data
        await asyncio.sleep(1)
        
        yield {
            'symbol': symbol,
            'price': 450.0 + random.random() * 5,
            'volume': random.randint(1000, 10000),
            'timestamp': datetime.now().timestamp()
        }

async def process_data_stream(
    data_stream: AsyncIterator[Dict[str, float]]
) -> List[Dict[str, float]]:
    """Process async data stream and collect results."""
    
    results: List[Dict[str, float]] = []
    
    async for data_point in data_stream:
        # Process each data point
        processed_data = {
            'symbol': data_point['symbol'],
            'processed_price': data_point['price'] * 1.01,  # Apply some processing
            'timestamp': data_point['timestamp']
        }
        results.append(processed_data)
        
    return results

# Usage
async def main() -> None:
    stream = fetch_market_data_stream("SPY", timedelta(minutes=5))
    results = await process_data_stream(stream)
    print(f"Processed {len(results)} data points")
```

## Financial Domain-Specific Types

### Custom Type Aliases
```python
from typing import TypeAlias, NewType
from decimal import Decimal
from datetime import datetime

# New types for domain-specific values
Price = NewType('Price', Decimal)
Quantity = NewType('Quantity', int)
OptionStrike = NewType('OptionStrike', Decimal)
ImpliedVolatility = NewType('ImpliedVolatility', float)

# Type aliases for complex structures
GreeksDict: TypeAlias = Dict[str, float]  # delta, gamma, theta, vega, rho
OptionChain: TypeAlias = Dict[str, Dict[OptionStrike, Dict[str, Any]]]
TradeResult: TypeAlias = Tuple[bool, str, Optional[Decimal]]  # success, message, pnl

# Position type with specific structure
Position: TypeAlias = Dict[str, Union[str, int, Decimal, datetime]]

def calculate_option_price(
    spot: Price,
    strike: OptionStrike,
    iv: ImpliedVolatility,
    time_to_expiry: float
) -> Price:
    """Calculate option price with domain-specific types."""
    # Implementation using Black-Scholes
    calculated_price = Decimal('5.25')  # Placeholder
    return Price(calculated_price)

def validate_position_size(
    symbol: str,
    quantity: Quantity,
    current_price: Price
) -> bool:
    """Validate position size meets risk requirements."""
    max_position_value = Decimal('10000')  # $10,000 max position
    position_value = current_price * abs(quantity)
    return position_value <= max_position_value
```

### Enum Types with Type Safety
```python
from enum import Enum, auto
from typing import Literal

class OrderType(Enum):
    """Enumeration of valid order types."""
    MARKET = "MKT"
    LIMIT = "LMT" 
    STOP = "STP"
    STOP_LIMIT = "STP_LMT"

class OptionType(Enum):
    """Enumeration of option types."""
    CALL = "CALL"
    PUT = "PUT"

class OrderStatus(Enum):
    """Enumeration of order statuses."""
    PENDING = auto()
    SUBMITTED = auto()
    FILLED = auto()
    CANCELLED = auto()
    REJECTED = auto()

# Using Literal types for restricted string values
TradingAction = Literal["BUY", "SELL", "BUY_TO_OPEN", "SELL_TO_CLOSE"]
MarketSession = Literal["REGULAR", "PREMARKET", "AFTERHOURS"]

def submit_order(
    symbol: str,
    action: TradingAction,
    order_type: OrderType,
    quantity: int,
    session: MarketSession = "REGULAR"
) -> str:
    """Submit order with type-safe parameters."""
    
    # Type checker ensures only valid values can be passed
    print(f"Submitting {action} order for {quantity} shares of {symbol}")
    print(f"Order type: {order_type.value}, Session: {session}")
    
    return "ORDER_12345"

# Usage - type checker validates these calls
submit_order("SPY", "BUY", OrderType.LIMIT, 100, "REGULAR")  # ✅ Valid
# submit_order("SPY", "INVALID", OrderType.LIMIT, 100)  # ❌ Type error
```

### Complex Financial Data Structures
```python
from typing import TypedDict, Optional, Union
from datetime import datetime
from decimal import Decimal

class OptionQuote(TypedDict):
    """Typed dictionary for option quote data."""
    bid: Decimal
    ask: Decimal
    last: Optional[Decimal]
    volume: int
    open_interest: int
    implied_volatility: float
    delta: float
    gamma: float
    theta: float
    vega: float

class TradeExecution(TypedDict):
    """Typed dictionary for trade execution details."""
    trade_id: str
    symbol: str
    quantity: int
    execution_price: Decimal
    commission: Decimal
    timestamp: datetime
    order_type: str
    execution_venue: str

class PortfolioPosition(TypedDict, total=False):  # total=False allows optional keys
    """Portfolio position with optional fields."""
    symbol: str  # Required
    quantity: int  # Required  
    average_cost: Decimal  # Required
    current_price: Optional[Decimal]  # Optional
    unrealized_pnl: Optional[Decimal]  # Optional
    last_updated: Optional[datetime]  # Optional

def process_option_quote(symbol: str, quote: OptionQuote) -> bool:
    """Process option quote with type safety."""
    
    # Type checker ensures all required fields are present
    bid_ask_spread = quote['ask'] - quote['bid']
    
    if bid_ask_spread > Decimal('0.10'):
        print(f"Wide spread on {symbol}: ${bid_ask_spread}")
        
    # Optional fields need explicit checking
    if quote['last'] is not None:
        print(f"Last trade: ${quote['last']}")
        
    return True
```

## Type Checking and Validation

### Runtime Type Checking
```python
from typing import get_type_hints, get_origin, get_args
import inspect

def validate_function_call(func: Callable, *args, **kwargs) -> bool:
    """Runtime validation of function arguments against type hints."""
    
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)
    
    # Bind arguments to parameter names
    bound_args = sig.bind(*args, **kwargs)
    bound_args.apply_defaults()
    
    # Validate each argument
    for param_name, value in bound_args.arguments.items():
        if param_name in type_hints:
            expected_type = type_hints[param_name]
            
            if not _is_instance_of_type(value, expected_type):
                print(f"Type error: {param_name} expected {expected_type}, got {type(value)}")
                return False
                
    return True

def _is_instance_of_type(value: Any, expected_type: type) -> bool:
    """Check if value matches expected type (simplified implementation)."""
    
    # Handle Optional types
    if get_origin(expected_type) is Union:
        type_args = get_args(expected_type)
        if type(None) in type_args:  # Optional type
            if value is None:
                return True
            # Check against non-None types
            non_none_types = [t for t in type_args if t is not type(None)]
            return any(isinstance(value, t) for t in non_none_types)
    
    # Handle basic types
    return isinstance(value, expected_type)

# Decorator for automatic type validation
def type_validated(func: Callable) -> Callable:
    """Decorator to add runtime type validation."""
    
    def wrapper(*args, **kwargs):
        if not validate_function_call(func, *args, **kwargs):
            raise TypeError(f"Type validation failed for {func.__name__}")
        return func(*args, **kwargs)
    
    return wrapper

# Usage
@type_validated
def calculate_portfolio_value(
    positions: Dict[str, int],
    prices: Dict[str, Decimal]
) -> Decimal:
    """Calculate total portfolio value with runtime type checking."""
    total = Decimal('0')
    for symbol, quantity in positions.items():
        if symbol in prices:
            total += quantity * prices[symbol]
    return total
```

### Type Checking Configuration
```python
# mypy.ini configuration for type checking
"""
[mypy]
python_version = 3.13
strict = True
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
disallow_incomplete_defs = True
check_untyped_defs = True
disallow_untyped_decorators = True
no_implicit_optional = True
warn_redundant_casts = True
warn_unused_ignores = True
warn_unreachable = True
strict_equality = True

# Specific rules for Tradov modules
[mypy-TradovB_Broker.*]
strict_optional = True

[mypy-TradovD_Strategies.*]
disallow_any_generics = True

[mypy-TradovE_Risk.*]
strict = True
disallow_any_expr = True
"""

# Type checking utility functions
def run_type_check_on_module(module_path: str) -> bool:
    """Run mypy type checking on specific module."""
    import subprocess
    
    result = subprocess.run([
        'mypy', 
        module_path,
        '--strict',
        '--show-error-codes'
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✅ Type checking passed for {module_path}")
        return True
    else:
        print(f"❌ Type errors in {module_path}:")
        print(result.stdout)
        return False
```

## Best Practices Summary

### Type Annotation Guidelines

1. **Always annotate function signatures**
   ```python
   # Good
   def calculate_pnl(entry_price: Decimal, exit_price: Decimal, quantity: int) -> Decimal:
       return (exit_price - entry_price) * quantity
   
   # Bad
   def calculate_pnl(entry_price, exit_price, quantity):
       return (exit_price - entry_price) * quantity
   ```

2. **Use specific types over generic ones**
   ```python
   # Good
   def get_option_strikes(symbol: str) -> List[Decimal]:
       return [Decimal('445.0'), Decimal('450.0'), Decimal('455.0')]
   
   # Bad
   def get_option_strikes(symbol: str) -> List[Any]:
       return [445.0, 450.0, 455.0]
   ```

3. **Prefer Union over Any when possible**
   ```python
   # Good
   def process_response(response: Union[Dict[str, Any], str, None]) -> bool:
       # Implementation handles each type appropriately
       pass
   
   # Bad
   def process_response(response: Any) -> bool:
       # No type information available
       pass
   ```

4. **Use NewType for domain-specific values**
   ```python
   # Good
   Price = NewType('Price', Decimal)
   Quantity = NewType('Quantity', int)
   
   def calculate_trade_value(price: Price, quantity: Quantity) -> Decimal:
       return price * quantity
   
   # Bad
   def calculate_trade_value(price: Decimal, quantity: int) -> Decimal:
       return price * quantity
   ```

5. **Document complex type structures**
   ```python
   # Type alias with documentation
   OptionChainData: TypeAlias = Dict[
       str,  # 'calls' or 'puts'
       Dict[
           Decimal,  # strike price
           Dict[str, Union[Decimal, float, int]]  # quote data
       ]
   ]
   ```

### Common Patterns in Financial Code

```python
# Pattern 1: Optional return for data that might not be available
def get_current_price(symbol: str) -> Optional[Price]:
    """Returns current price or None if market is closed."""
    pass

# Pattern 2: Union types for different response formats
def parse_market_data(
    data: Union[str, bytes, Dict[str, Any]]
) -> Optional[Dict[str, float]]:
    """Parse market data from various input formats."""
    pass

# Pattern 3: Callable types for strategy callbacks
StrategySignalHandler: TypeAlias = Callable[
    [str, Dict[str, Any]],  # symbol, signal_data
    Optional[str]           # order_id or None
]

# Pattern 4: TypedDict for structured data
class RiskMetrics(TypedDict):
    max_drawdown: float
    var_95: Decimal
    expected_shortfall: Decimal
    beta: float
```

---

Following these type annotation standards ensures the Tradov trading system maintains type safety throughout its codebase, reducing runtime errors and improving code maintainability in this critical financial application.
