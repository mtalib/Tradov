11. Standards/Python/Patterns.md

```markdown
# Python Design Patterns for Spyder Trading System

## Overview

This document defines the design patterns and architectural patterns used throughout the Spyder trading system. Consistent application of these patterns ensures maintainable, testable, and reliable code for financial trading operations.

## Creational Patterns

### Singleton Pattern for System Components

```python
import threading
from typing import Optional, Dict, Any

class SpyderLogger:
    """Singleton logger instance for system-wide logging."""
    
    _instance: Optional['SpyderLogger'] = None
    _lock: threading.Lock = threading.Lock()
    
    def __new__(cls) -> 'SpyderLogger':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        if not self._initialized:
            self.loggers: Dict[str, Any] = {}
            self._initialized = True
    
    @classmethod
    def get_logger(cls, name: str) -> Any:
        """Get or create logger for specific module."""
        instance = cls()
        if name not in instance.loggers:
            instance.loggers[name] = cls._create_logger(name)
        return instance.loggers[name]
    
    @staticmethod
    def _create_logger(name: str) -> Any:
        """Create configured logger instance."""
        # Logger configuration logic
        pass

# Usage across the system
class TradingStrategy:
    def __init__(self):
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
```

### Factory Pattern for Strategy Creation

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Type
from enum import Enum

class StrategyType(Enum):
    IRON_CONDOR = "iron_condor"
    CREDIT_SPREAD = "credit_spread"
    STRADDLE = "straddle"
    ZERO_DTE = "zero_dte"

class TradingStrategy(ABC):
    """Abstract base class for all trading strategies."""
    
    @abstractmethod
    def generate_signals(self, market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def calculate_position_size(self, signal: Dict[str, Any]) -> int:
        pass

class StrategyFactory:
    """Factory for creating trading strategy instances."""
    
    _strategies: Dict[StrategyType, Type[TradingStrategy]] = {}
    
    @classmethod
    def register_strategy(
        cls, 
        strategy_type: StrategyType, 
        strategy_class: Type[TradingStrategy]
    ) -> None:
        """Register a strategy class with the factory."""
        cls._strategies[strategy_type] = strategy_class
    
    @classmethod
    def create_strategy(
        cls,
        strategy_type: StrategyType,
        name: str,
        config: Dict[str, Any]
    ) -> TradingStrategy:
        """Create strategy instance of specified type."""
        
        if strategy_type not in cls._strategies:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
        
        strategy_class = cls._strategies[strategy_type]
        return strategy_class(name, config)

# Strategy implementations
class IronCondorStrategy(TradingStrategy):
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
    
    def generate_signals(self, market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Iron Condor signal generation logic
        return []
    
    def calculate_position_size(self, signal: Dict[str, Any]) -> int:
        # Position sizing logic
        return 10

class CreditSpreadStrategy(TradingStrategy):
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
    
    def generate_signals(self, market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Credit spread signal generation logic
        return []
    
    def calculate_position_size(self, signal: Dict[str, Any]) -> int:
        # Position sizing logic
        return 5

# Register strategies with factory
StrategyFactory.register_strategy(StrategyType.IRON_CONDOR, IronCondorStrategy)
StrategyFactory.register_strategy(StrategyType.CREDIT_SPREAD, CreditSpreadStrategy)

# Usage
strategy = StrategyFactory.create_strategy(
    StrategyType.IRON_CONDOR,
    "ic_weekly",
    {"target_delta": 0.15, "max_dte": 45}
)
```

### Builder Pattern for Complex Order Construction

```python
from dataclasses import dataclass
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

@dataclass
class OptionLeg:
    """Individual option leg in a multi-leg strategy."""
    symbol: str
    strike: Decimal
    expiry: datetime
    option_type: str  # 'CALL' or 'PUT'
    action: str  # 'BUY' or 'SELL'
    quantity: int

@dataclass
class ComplexOrder:
    """Multi-leg options order."""
    strategy_name: str
    legs: List[OptionLeg]
    order_type: str
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: str = "DAY"
    
class ComplexOrderBuilder:
    """Builder for constructing complex multi-leg orders."""
    
    def __init__(self, strategy_name: str):
        self.strategy_name = strategy_name
        self.legs: List[OptionLeg] = []
        self.order_type = "LMT"
        self.limit_price: Optional[Decimal] = None
        self.stop_price: Optional[Decimal] = None
        self.time_in_force = "DAY"
    
    def add_call_leg(
        self,
        symbol: str,
        strike: Decimal,
        expiry: datetime,
        action: str,
        quantity: int
    ) -> 'ComplexOrderBuilder':
        """Add a call option leg to the order."""
        leg = OptionLeg(symbol, strike, expiry, "CALL", action, quantity)
        self.legs.append(leg)
        return self
    
    def add_put_leg(
        self,
        symbol: str,
        strike: Decimal,
        expiry: datetime,
        action: str,
        quantity: int
    ) -> 'ComplexOrderBuilder':
        """Add a put option leg to the order."""
        leg = OptionLeg(symbol, strike, expiry, "PUT", action, quantity)
        self.legs.append(leg)
        return self
    
    def set_limit_price(self, price: Decimal) -> 'ComplexOrderBuilder':
        """Set limit price for the order."""
        self.order_type = "LMT"
        self.limit_price = price
        return self
    
    def set_market_order(self) -> 'ComplexOrderBuilder':
        """Set as market order."""
        self.order_type = "MKT"
        self.limit_price = None
        return self
    
    def set_time_in_force(self, tif: str) -> 'ComplexOrderBuilder':
        """Set time in force (DAY, GTC, IOC, FOK)."""
        self.time_in_force = tif
        return self
    
    def build(self) -> ComplexOrder:
        """Build the complete complex order."""
        if not self.legs:
            raise ValueError("Order must have at least one leg")
        
        return ComplexOrder(
            strategy_name=self.strategy_name,
            legs=self.legs.copy(),
            order_type=self.order_type,
            limit_price=self.limit_price,
            stop_price=self.stop_price,
            time_in_force=self.time_in_force
        )

# Usage - Build Iron Condor Order
iron_condor = (ComplexOrderBuilder("iron_condor")
    .add_put_leg("SPY", Decimal("440"), datetime(2025, 2, 21), "SELL", 1)
    .add_put_leg("SPY", Decimal("435"), datetime(2025, 2, 21), "BUY", 1)
    .add_call_leg("SPY", Decimal("460"), datetime(2025, 2, 21), "SELL", 1)
    .add_call_leg("SPY", Decimal("465"), datetime(2025, 2, 21), "BUY", 1)
    .set_limit_price(Decimal("1.25"))
    .set_time_in_force("GTC")
    .build())
```

## Structural Patterns

### Adapter Pattern for Broker API Integration

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

class BrokerInterface(ABC):
    """Standard interface for all broker integrations."""
    
    @abstractmethod
    def connect(self) -> bool:
        pass
    
    @abstractmethod
    def submit_order(self, order: Dict[str, Any]) -> str:
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def get_account_info(self) -> Dict[str, Any]:
        pass

class IBKRClient:
    """Original IBKR client with specific API."""
    
    def establish_connection(self, host: str, port: int) -> bool:
        """IBKR-specific connection method."""
        # IBKR connection logic
        return True
    
    def place_order(self, contract: Any, order: Any) -> int:
        """IBKR-specific order placement."""
        # IBKR order logic
        return 12345
    
    def get_portfolio_positions(self) -> List[Any]:
        """IBKR-specific position retrieval."""
        # IBKR position logic
        return []

class IBKRAdapter(BrokerInterface):
    """Adapter to make IBKR client conform to standard interface."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 4002):
        self._client = IBKRClient()
        self._host = host
        self._port = port
        self._connected = False
    
    def connect(self) -> bool:
        """Adapt IBKR connection to standard interface."""
        self._connected = self._client.establish_connection(self._host, self._port)
        return self._connected
    
    def submit_order(self, order: Dict[str, Any]) -> str:
        """Adapt order submission to standard interface."""
        # Convert standard order format to IBKR format
        ibkr_contract = self._create_ibkr_contract(order)
        ibkr_order = self._create_ibkr_order(order)
        
        order_id = self._client.place_order(ibkr_contract, ibkr_order)
        return str(order_id)
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Adapt position retrieval to standard interface."""
        ibkr_positions = self._client.get_portfolio_positions()
        return [self._convert_position(pos) for pos in ibkr_positions]
    
    def get_account_info(self) -> Dict[str, Any]:
        """Adapt account info to standard interface."""
        # Implementation specific to IBKR
        return {"account_id": "DU12345", "net_liquidation": 100000.0}
    
    def _create_ibkr_contract(self, order: Dict[str, Any]) -> Any:
        """Convert standard order to IBKR contract."""
        # Conversion logic
        pass
    
    def _create_ibkr_order(self, order: Dict[str, Any]) -> Any:
        """Convert standard order to IBKR order."""
        # Conversion logic
        pass
    
    def _convert_position(self, ibkr_position: Any) -> Dict[str, Any]:
        """Convert IBKR position to standard format."""
        return {
            "symbol": "SPY",
            "quantity": 100,
            "average_cost": 450.0
        }

# Usage - Same interface for any broker
def execute_trade_with_broker(broker: BrokerInterface, order: Dict[str, Any]) -> bool:
    """Execute trade using any broker implementation."""
    if not broker.connect():
        return False
    
    order_id = broker.submit_order(order)
    print(f"Order submitted: {order_id}")
    return True

# Can use any broker implementation
ibkr_broker = IBKRAdapter("127.0.0.1", 4002)
execute_trade_with_broker(ibkr_broker, {"symbol": "SPY", "quantity": 100})
```

### Decorator Pattern for Risk Management

```python
from functools import wraps
from typing import Callable, Any, Dict
from decimal import Decimal

class RiskDecorator:
    """Decorator for adding risk management to trading functions."""
    
    @staticmethod
    def position_limit(max_position_value: Decimal):
        """Decorator to enforce position size limits."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                # Extract order details from arguments
                order = args[0] if args else kwargs.get('order', {})
                
                # Calculate position value
                quantity = order.get('quantity', 0)
                price = order.get('price', Decimal('0'))
                position_value = abs(quantity) * price
                
                if position_value > max_position_value:
                    raise ValueError(
                        f"Position value ${position_value} exceeds limit ${max_position_value}"
                    )
                
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def market_hours_only():
        """Decorator to restrict trading to market hours."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                if not is_market_open():
                    raise ValueError("Trading not allowed outside market hours")
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def max_daily_trades(max_trades: int):
        """Decorator to enforce maximum daily trade count."""
        daily_trade_count = {}  # In practice, this would be persistent
        
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                from datetime import date
                today = date.today()
                
                if today not in daily_trade_count:
                    daily_trade_count[today] = 0
                
                if daily_trade_count[today] >= max_trades:
                    raise ValueError(f"Maximum daily trades ({max_trades}) exceeded")
                
                result = func(*args, **kwargs)
                daily_trade_count[today] += 1
                return result
            return wrapper
        return decorator

def is_market_open() -> bool:
    """Check if market is currently open."""
    # Implementation to check market hours
    return True

# Usage - Apply multiple risk decorators
class OrderExecutor:
    
    @RiskDecorator.position_limit(Decimal('5000'))
    @RiskDecorator.market_hours_only()
    @RiskDecorator.max_daily_trades(50)
    def execute_order(self, order: Dict[str, Any]) -> str:
        """Execute order with risk management applied."""
        # Order execution logic
        print(f"Executing order: {order}")
        return "ORDER_12345"
```

## Behavioral Patterns

### Strategy Pattern for Trading Algorithms

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class MarketSignal:
    """Market signal generated by trading strategy."""
    symbol: str
    action: str  # 'BUY', 'SELL'
    strength: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    metadata: Dict[str, Any]

class SignalGenerator(ABC):
    """Abstract strategy for generating trading signals."""
    
    @abstractmethod
    def generate_signals(self, market_data: Dict[str, Any]) -> List[MarketSignal]:
        pass

class TechnicalAnalysisStrategy(SignalGenerator):
    """Signal generation based on technical indicators."""
    
    def __init__(self, indicators: List[str]):
        self.indicators = indicators
    
    def generate_signals(self, market_data: Dict[str, Any]) -> List[MarketSignal]:
        """Generate signals based on technical analysis."""
        signals = []
        
        # RSI oversold/overbought
        if 'rsi' in self.indicators:
            rsi = market_data.get('rsi', 50)
            if rsi < 30:
                signals.append(MarketSignal(
                    symbol=market_data['symbol'],
                    action='BUY',
                    strength=0.8,
                    confidence=0.7,
                    metadata={'indicator': 'RSI', 'value': rsi}
                ))
            elif rsi > 70:
                signals.append(MarketSignal(
                    symbol=market_data['symbol'],
                    action='SELL',
                    strength=0.8,
                    confidence=0.7,
                    metadata={'indicator': 'RSI', 'value': rsi}
                ))
        
        return signals

class VolatilityStrategy(SignalGenerator):
    """Signal generation based on volatility analysis."""
    
    def __init__(self, vol_threshold: float = 0.25):
        self.vol_threshold = vol_threshold
    
    def generate_signals(self, market_data: Dict[str, Any]) -> List[MarketSignal]:
        """Generate signals based on volatility patterns."""
        signals = []
        
        implied_vol = market_data.get('implied_volatility', 0.2)
        historical_vol = market_data.get('historical_volatility', 0.2)
        
        # High IV relative to HV suggests selling premium
        if implied_vol > historical_vol * 1.2:
            signals.append(MarketSignal(
                symbol=market_data['symbol'],
                action='SELL_PREMIUM',
                strength=0.9,
                confidence=0.8,
                metadata={
                    'iv': implied_vol,
                    'hv': historical_vol,
                    'iv_rank': implied_vol / historical_vol
                }
            ))
        
        return signals

class TradingContext:
    """Context that uses different signal generation strategies."""
    
    def __init__(self, strategy: SignalGenerator):
        self._strategy = strategy
    
    def set_strategy(self, strategy: SignalGenerator) -> None:
        """Change signal generation strategy at runtime."""
        self._strategy = strategy
    
    def analyze_market(self, market_data: Dict[str, Any]) -> List[MarketSignal]:
        """Analyze market using current strategy."""
        return self._strategy.generate_signals(market_data)

# Usage - Can switch strategies dynamically
market_data = {
    'symbol': 'SPY',
    'rsi': 75,
    'implied_volatility': 0.28,
    'historical_volatility': 0.20
}

# Start with technical analysis
context = TradingContext(TechnicalAnalysisStrategy(['rsi', 'macd']))
signals = context.analyze_market(market_data)
print(f"Technical signals: {len(signals)}")

# Switch to volatility strategy
context.set_strategy(VolatilityStrategy(0.25))
signals = context.analyze_market(market_data)
print(f"Volatility signals: {len(signals)}")
```

### Observer Pattern for Market Data Distribution

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Set
import threading

class MarketDataObserver(ABC):
    """Abstract observer for market data updates."""
    
    @abstractmethod
    def update(self, symbol: str, data: Dict[str, Any]) -> None:
        pass

class MarketDataSubject:
    """Subject that distributes market data to observers."""
    
    def __init__(self):
        self._observers: Dict[str, Set[MarketDataObserver]] = {}
        self._lock = threading.Lock()
    
    def subscribe(self, symbol: str, observer: MarketDataObserver) -> None:
        """Subscribe observer to symbol updates."""
        with self._lock:
            if symbol not in self._observers:
                self._observers[symbol] = set()
            self._observers[symbol].add(observer)
    
    def unsubscribe(self, symbol: str, observer: MarketDataObserver) -> None:
        """Unsubscribe observer from symbol updates."""
        with self._lock:
            if symbol in self._observers:
                self._observers[symbol].discard(observer)
                if not self._observers[symbol]:
                    del self._observers[symbol]
    
    def notify_observers(self, symbol: str, data: Dict[str, Any]) -> None:
        """Notify all observers of symbol data update."""
        with self._lock:
            observers = self._observers.get(symbol, set()).copy()
        
        # Notify outside the lock to prevent deadlocks
        for observer in observers:
            try:
                observer.update(symbol, data)
            except Exception as e:
                print(f"Error notifying observer: {e}")

# Concrete observers
class StrategyObserver(MarketDataObserver):
    """Observer that generates trading signals."""
    
    def __init__(self, name: str):
        self.name = name
    
    def update(self, symbol: str, data: Dict[str, Any]) -> None:
        """Process market data update and generate signals."""
        price = data.get('price', 0)
        print(f"Strategy {self.name}: {symbol} price updated to ${price}")
        
        # Generate trading signals based on price update
        if price > 450:
            print(f"Strategy {self.name}: Consider selling {symbol}")

class RiskObserver(MarketDataObserver):
    """Observer that monitors risk metrics."""
    
    def update(self, symbol: str, data: Dict[str, Any]) -> None:
        """Monitor position risk based on price changes."""
        price = data.get('price', 0)
        volatility = data.get('volatility', 0.2)
        
        if volatility > 0.5:
            print(f"Risk Alert: High volatility in {symbol}: {volatility:.1%}")

class PerformanceObserver(MarketDataObserver):
    """Observer that tracks performance metrics."""
    
    def __init__(self):
        self.price_history: Dict[str, List[float]] = {}
    
    def update(self, symbol: str, data: Dict[str, Any]) -> None:
        """Track price history for performance calculations."""
        price = data.get('price', 0)
        
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        self.price_history[symbol].append(price)
        
        # Keep only last 100 prices
        if len(self.price_history[symbol]) > 100:
            self.price_history[symbol].pop(0)

# Usage
market_data_hub = MarketDataSubject()

# Create observers
strategy1 = StrategyObserver("IronCondor")
strategy2 = StrategyObserver("CreditSpread")
risk_monitor = RiskObserver()
perf_tracker = PerformanceObserver()

# Subscribe to SPY updates
market_data_hub.subscribe("SPY", strategy1)
market_data_hub.subscribe("SPY", strategy2)
market_data_hub.subscribe("SPY", risk_monitor)
market_data_hub.subscribe("SPY", perf_tracker)

# Simulate market data update
market_data_hub.notify_observers("SPY", {
    'price': 451.25,
    'volume': 1000000,
    'volatility': 0.22
})
```

### Command Pattern for Order Management

```python
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime

class Command(ABC):
    """Abstract command interface."""
    
    @abstractmethod
    def execute(self) -> bool:
        pass
    
    @abstractmethod
    def undo(self) -> bool:
        pass

class OrderCommand(Command):
    """Base class for order-related commands."""
    
    def __init__(self, order_id: str):
        self.order_id = order_id
        self.timestamp = datetime.now()
        self.executed = False

class SubmitOrderCommand(OrderCommand):
    """Command to submit a trading order."""
    
    def __init__(self, order_id: str, order_data: Dict[str, Any], broker_client):
        super().__init__(order_id)
        self.order_data = order_data
        self.broker_client = broker_client
    
    def execute(self) -> bool:
        """Submit the order to broker."""
        try:
            result = self.broker_client.submit_order(self.order_data)
            self.executed = True
            print(f"Order {self.order_id} submitted successfully")
            return True
        except Exception as e:
            print(f"Failed to submit order {self.order_id}: {e}")
            return False
    
    def undo(self) -> bool:
        """Cancel the submitted order."""
        if not self.executed:
            return True
        
        try:
            result = self.broker_client.cancel_order(self.order_id)
            print(f"Order {self.order_id} cancelled")
            return True
        except Exception as e:
            print(f"Failed to cancel order {self.order_id}: {e}")
            return False

class ModifyOrderCommand(OrderCommand):
    """Command to modify an existing order."""
    
    def __init__(
        self, 
        order_id: str, 
        modifications: Dict[str, Any], 
        broker_client
    ):
        super().__init__(order_id)
        self.modifications = modifications
        self.broker_client = broker_client
        self.original_values: Optional[Dict[str, Any]] = None
    
    def execute(self) -> bool:
        """Modify the existing order."""
        try:
            # Store original values for undo
            self.original_values = self.broker_client.get_order_details(self.order_id)
            
            result = self.broker_client.modify_order(self.order_id, self.modifications)
            self.executed = True
            print(f"Order {self.order_id} modified successfully")
            return True
        except Exception as e:
            print(f"Failed to modify order {self.order_id}: {e}")
            return False
    
    def undo(self) -> bool:
        """Revert order modifications."""
        if not self.executed or not self.original_values:
            return True
        
        try:
            result = self.broker_client.modify_order(self.order_id, self.original_values)
            print(f"Order {self.order_id} modifications reverted")
            return True
        except Exception as e:
            print(f"Failed to revert order {self.order_id}: {e}")
            return False

class OrderManager:
    """Invoker that manages order commands."""
    
    def __init__(self):
        self.command_history: List[Command] = []
        self.current_index = -1
    
    def execute_command(self, command: Command) -> bool:
        """Execute a command and add to history."""
        if command.execute():
            # Remove any commands after current index (for redo functionality)
            self.command_history = self.command_history[:self.current_index + 1]
            
            # Add new command
            self.command_history.append(command)
            self.current_index += 1
            return True
        return False
    
    def undo_last_command(self) -> bool:
        """Undo the last executed command."""
        if self.current_index >= 0:
            command = self.command_history[self.current_index]
            if command.undo():
                self.current_index -= 1
                return True
        return False
    
    def redo_command(self) -> bool:
        """Redo a previously undone command."""
        if self.current_index < len(self.command_history) - 1:
            self.current_index += 1
            command = self.command_history[self.current_index]
            return command.execute()
        return False
    
    def get_command_history(self) -> List[Dict[str, Any]]:
        """Get history of executed commands."""
        return [
            {
                'order_id': cmd.order_id,
                'timestamp': cmd.timestamp,
                'type': cmd.__class__.__name__,
                'executed': cmd.executed
            }
            for cmd in self.command_history
        ]

# Usage
class MockBrokerClient:
    def submit_order(self, order_data: Dict[str, Any]) -> str:
        return "SUCCESS"
    
    def cancel_order(self, order_id: str) -> str:
        return "CANCELLED"
    
    def modify_order(self, order_id: str, modifications: Dict[str, Any]) -> str:
        return "MODIFIED"
    
    def get_order_details(self, order_id: str) -> Dict[str, Any]:
        return {"price": 450.0, "quantity": 100}

broker = MockBrokerClient()
order_manager = OrderManager()

# Submit an order
submit_cmd = SubmitOrderCommand(
    "ORDER_001",
    {"symbol": "SPY", "quantity": 100, "price": 450.0},
    broker
)
order_manager.execute_command(submit_cmd)

# Modify the order
modify_cmd = ModifyOrderCommand(
    "ORDER_001",
    {"price": 451.0},
    broker
)
order_manager.execute_command(modify_cmd)

# Undo modification
order_manager.undo_last_command()

# View command history
history = order_manager.get_command_history()
for cmd in history:
    print(f"{cmd['timestamp']}: {cmd['type']} - {cmd['order_id']}")
```

## Financial Domain-Specific Patterns

### State Machine Pattern for Order Lifecycle

```python
from enum import Enum, auto
from typing import Dict, Any, Optional, Callable
from abc import ABC, abstractmethod

class OrderState(Enum):
    """Enumeration of order states."""
    PENDING = auto()
    SUBMITTED = auto()
    ACKNOWLEDGED = auto()
    PARTIALLY_FILLED = auto()
    FILLED = auto()
    CANCELLED = auto()
    REJECTED = auto()
    ERROR = auto()

class OrderEvent(Enum):
    """Enumeration of order events."""
    SUBMIT = auto()
    ACKNOWLEDGE = auto()
    PARTIAL_FILL = auto()
    FILL = auto()
    CANCEL = auto()
    REJECT = auto()
    ERROR = auto()

class OrderStateHandler(ABC):
    """Abstract handler for order state logic."""
    
    @abstractmethod
    def handle(self, order: 'Order', event: OrderEvent, data: Dict[str, Any]) -> OrderState:
        pass

class PendingStateHandler(OrderStateHandler):
    """Handler for pending order state."""
    
    def handle(self, order: 'Order', event: OrderEvent, data: Dict[str, Any]) -> OrderState:
        if event == OrderEvent.SUBMIT:
            order.submit_to_broker()
            return OrderState.SUBMITTED
        elif event == OrderEvent.REJECT:
            order.set_rejection_reason
