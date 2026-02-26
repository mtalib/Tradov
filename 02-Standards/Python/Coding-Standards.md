 Standards/Python/Coding-Standards.md

```markdown
# Python Coding Standards for Spyder Trading System

## Overview

This document defines the coding standards and conventions used throughout the Spyder trading system. Consistency in coding style improves readability, maintainability, and reduces the likelihood of errors in a system that handles real financial transactions.

## File Structure & Organization

### Module File Template

Every Python module in the Spyder system should follow this structure:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_ModuleName
Module: SpyderXNN_SpecificFunction.py
Purpose: Brief description of what this module does

Author: [Author Name]
Year Created: 2025
Last Updated: 2025-01-XX Time: HH:MM:SS

Module Description:
    Detailed description of the module's functionality, its role in the system,
    and any important implementation details or assumptions.

Module Constants:
    CONSTANT_NAME (type): Description of constant (default: value)
    
Dependencies:
    - List of critical dependencies
    - External APIs or services used
    - Hardware or system requirements

Change Log:
    2025-01-XX (vX.X.X):
        - Description of changes made
        - Bug fixes or enhancements
        - Breaking changes (if any)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30.0
DEFAULT_BUFFER_SIZE = 1024

# ==============================================================================
# ENUMS AND DATA STRUCTURES
# ==============================================================================
class ModuleState(Enum):
    """Enumeration of possible module states"""
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    ERROR = "error"

@dataclass
class ModuleConfig:
    """Configuration data structure for module initialization"""
    name: str
    version: str = "1.0.0"
    enabled: bool = True
    debug_mode: bool = False

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class StandardModule:
    """
    Standard module template following Spyder conventions.
    
    This class demonstrates the expected structure, documentation,
    and coding patterns for all modules in the Spyder system.
    """
    
    def __init__(self, config: Optional[ModuleConfig] = None):
        """Initialize the module with configuration."""
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.config = config or ModuleConfig(name=self.__class__.__name__)
        self.state = ModuleState.INITIALIZING
        
    def initialize(self) -> bool:
        """Initialize module components and validate configuration."""
        try:
            # Initialization logic here
            self.state = ModuleState.READY
            return True
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            self.state = ModuleState.ERROR
            return False

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def utility_function(param: str) -> str:
    """
    Example utility function following naming conventions.
    
    Args:
        param: Description of parameter
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When param is invalid
    """
    if not param:
        raise ValueError("Parameter cannot be empty")
    return f"Processed: {param}"

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("Module template executed successfully")
```

## Naming Conventions

### Module and File Naming
- **Module Names**: `SpyderX_CategoryName` (e.g., `SpyderB_Broker`)
- **File Names**: `SpyderXNN_SpecificFunction.py` (e.g., `SpyderB01_ConnectionManager.py`)
- **Series Letters**: Follow the established series system (A=Core, B=Broker, etc.)
- **Numbers**: Sequential numbering within each series (01, 02, 03...)

### Variable and Function Naming
```python
# Variables: snake_case
current_price = 100.50
max_position_size = 1000
is_market_open = True

# Functions: snake_case with descriptive names
def calculate_option_delta(spot_price: float, strike: float) -> float:
    pass

def validate_order_parameters(order_data: dict) -> bool:
    pass

# Classes: PascalCase
class PositionManager:
    pass

class OrderExecutionEngine:
    pass

# Constants: UPPER_SNAKE_CASE
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30.0
API_BASE_URL = "https://api.example.com"

# Private methods: leading underscore
def _internal_calculation(self, data: Any) -> float:
    pass

def _validate_configuration(self) -> bool:
    pass
```

## Type Annotations

### Required Type Hints
All function signatures must include type hints:

```python
# Function parameters and return types
def process_market_data(
    symbol: str,
    price_data: List[float],
    volume_data: Optional[List[int]] = None
) -> Dict[str, Any]:
    """Process market data and return analysis results."""
    pass

# Class attributes with type hints
class TradingStrategy:
    name: str
    max_positions: int
    current_positions: Dict[str, Position]
    is_active: bool
    
    def __init__(self, name: str) -> None:
        self.name = name
        self.max_positions = 10
        self.current_positions = {}
        self.is_active = True

# Complex type annotations
from typing import Union, Optional, Callable, TypeVar, Generic

OrderCallback = Callable[[str, bool], None]
PriceDict = Dict[str, Union[float, int]]
OptionalDataFrame = Optional[pd.DataFrame]

T = TypeVar('T')
class DataContainer(Generic[T]):
    def __init__(self, data: T) -> None:
        self.data = data
```

## Error Handling Patterns

### Standard Exception Handling
```python
def execute_trade_order(order_data: dict) -> bool:
    """Execute a trading order with comprehensive error handling."""
    try:
        # Validate input data
        if not self._validate_order_data(order_data):
            raise ValueError("Invalid order data provided")
            
        # Attempt order execution
        result = self._submit_order_to_broker(order_data)
        
        if result.success:
            self.logger.info(f"Order executed successfully: {result.order_id}")
            return True
        else:
            self.logger.warning(f"Order execution failed: {result.error_message}")
            return False
            
    except ConnectionError as e:
        self.logger.error(f"Connection error during order execution: {e}")
        # Implement retry logic
        return self._retry_order_execution(order_data)
        
    except ValueError as e:
        self.logger.error(f"Invalid order data: {e}")
        # Don't retry for validation errors
        return False
        
    except Exception as e:
        self.logger.error(f"Unexpected error during order execution: {e}")
        # Log full traceback for debugging
        self.logger.exception("Full traceback:")
        return False

def _retry_order_execution(self, order_data: dict, max_retries: int = 3) -> bool:
    """Retry order execution with exponential backoff."""
    for attempt in range(max_retries):
        try:
            time.sleep(2 ** attempt)  # Exponential backoff
            return self.execute_trade_order(order_data)
        except Exception as e:
            self.logger.warning(f"Retry attempt {attempt + 1} failed: {e}")
    
    return False
```

### Custom Exception Classes
```python
class SpyderException(Exception):
    """Base exception class for all Spyder-specific errors."""
    pass

class TradingError(SpyderException):
    """Raised when trading operations fail."""
    pass

class DataValidationError(SpyderException):
    """Raised when data validation fails."""
    
    def __init__(self, message: str, invalid_data: Any = None):
        super().__init__(message)
        self.invalid_data = invalid_data

class ConnectionTimeoutError(SpyderException):
    """Raised when connection operations timeout."""
    
    def __init__(self, timeout_duration: float, operation: str):
        super().__init__(f"Operation '{operation}' timed out after {timeout_duration}s")
        self.timeout_duration = timeout_duration
        self.operation = operation
```

## Logging Standards

### Logger Configuration
```python
class SpyderModule:
    """Standard module with proper logging setup."""
    
    def __init__(self, name: str):
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.name = name
        
    def process_data(self, data: Any) -> bool:
        """Process data with appropriate logging."""
        self.logger.debug(f"Starting data processing for {self.name}")
        
        try:
            # Processing logic
            result = self._perform_processing(data)
            
            if result:
                self.logger.info(f"Data processing completed successfully")
                return True
            else:
                self.logger.warning(f"Data processing completed with issues")
                return False
                
        except Exception as e:
            self.logger.error(f"Data processing failed: {e}")
            self.logger.exception("Full traceback:")
            return False
            
        finally:
            self.logger.debug(f"Data processing finished for {self.name}")
```

### Log Message Guidelines
```python
# Good logging practices
self.logger.debug("Detailed debugging information")
self.logger.info("General system information")
self.logger.warning("Potential issues that don't stop execution")
self.logger.error("Error conditions that affect functionality")
self.logger.critical("Critical errors that may cause system shutdown")

# Include relevant context in log messages
self.logger.info(f"Order executed: {order_id}, Symbol: {symbol}, Qty: {quantity}")
self.logger.error(f"Connection failed after {retry_count} attempts to {host}:{port}")
self.logger.warning(f"Position size {position_size} exceeds limit {max_size}")

# Avoid logging sensitive information
# BAD: self.logger.info(f"API key: {api_key}")  # Never log credentials
# GOOD: self.logger.info("API authentication successful")
```

## Documentation Standards

### Docstring Format (Google Style)
```python
def calculate_options_greeks(
    spot_price: float,
    strike_price: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float = 0.02,
    dividend_yield: float = 0.0
) -> Dict[str, float]:
    """
    Calculate options Greeks using Black-Scholes model.
    
    This function computes the standard option sensitivities (Greeks)
    for European-style options using the Black-Scholes formula.
    
    Args:
        spot_price: Current price of the underlying asset
        strike_price: Strike price of the option
        time_to_expiry: Time to expiration in years
        volatility: Implied volatility as a decimal (e.g., 0.20 for 20%)
        risk_free_rate: Risk-free interest rate as decimal (default: 0.02)
        dividend_yield: Dividend yield as decimal (default: 0.0)
        
    Returns:
        Dictionary containing calculated Greeks:
        - 'delta': Price sensitivity
        - 'gamma': Delta sensitivity  
        - 'theta': Time decay
        - 'vega': Volatility sensitivity
        - 'rho': Interest rate sensitivity
        
    Raises:
        ValueError: If any input parameter is invalid
        ZeroDivisionError: If time_to_expiry is zero or negative
        
    Example:
        >>> greeks = calculate_options_greeks(100.0, 105.0, 0.25, 0.20)
        >>> print(f"Delta: {greeks['delta']:.4f}")
        Delta: 0.4321
        
    Note:
        This implementation assumes European-style options and constant
        volatility and interest rates.
    """
    # Validation
    if spot_price <= 0:
        raise ValueError("Spot price must be positive")
    if strike_price <= 0:
        raise ValueError("Strike price must be positive")
    if time_to_expiry <= 0:
        raise ValueError("Time to expiry must be positive")
    if volatility <= 0:
        raise ValueError("Volatility must be positive")
        
    # Implementation here...
    return {
        'delta': calculated_delta,
        'gamma': calculated_gamma,
        'theta': calculated_theta,
        'vega': calculated_vega,
        'rho': calculated_rho
    }
```

## Class Design Patterns

### Standard Class Structure
```python
class TradingStrategy:
    """
    Base class for all trading strategies in the Spyder system.
    
    This class provides the standard interface and common functionality
    that all trading strategies should implement or inherit.
    """
    
    # Class-level constants
    DEFAULT_MAX_POSITIONS = 10
    DEFAULT_RISK_PER_TRADE = 0.02
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the trading strategy.
        
        Args:
            name: Unique name for this strategy instance
            config: Optional configuration dictionary
        """
        # Public attributes
        self.name = name
        self.is_active = False
        self.positions = {}
        
        # Private attributes
        self._config = config or {}
        self._logger = SpyderLogger.get_logger(f"{self.__class__.__name__}.{name}")
        self._risk_manager = None
        
        # Initialize strategy
        self._initialize_strategy()
        
    def _initialize_strategy(self) -> None:
        """Initialize strategy-specific components."""
        self._logger.info(f"Initializing strategy: {self.name}")
        # Implementation here...
        
    def start(self) -> bool:
        """Start the trading strategy."""
        try:
            if self.is_active:
                self._logger.warning(f"Strategy {self.name} is already active")
                return True
                
            # Startup logic here...
            self.is_active = True
            self._logger.info(f"Strategy {self.name} started successfully")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to start strategy {self.name}: {e}")
            return False
            
    def stop(self) -> bool:
        """Stop the trading strategy."""
        try:
            if not self.is_active:
                self._logger.warning(f"Strategy {self.name} is already stopped")
                return True
                
            # Cleanup logic here...
            self.is_active = False
            self._logger.info(f"Strategy {self.name} stopped successfully")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to stop strategy {self.name}: {e}")
            return False
            
    # Abstract methods that subclasses must implement
    def generate_signals(self, market_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate trading signals based on market data."""
        raise NotImplementedError("Subclasses must implement generate_signals")
        
    def calculate_position_size(self, signal: Dict[str, Any]) -> float:
        """Calculate appropriate position size for a signal."""
        raise NotImplementedError("Subclasses must implement calculate_position_size")
```

## Performance Guidelines

### Efficient Code Patterns
```python
# Use list comprehensions for simple transformations
prices = [float(p) for p in price_strings if p.strip()]

# Use generator expressions for memory efficiency
total = sum(calculate_value(item) for item in large_dataset)

# Use built-in functions when possible
max_price = max(price_list)
sorted_data = sorted(data_list, key=lambda x: x.timestamp)

# Avoid repeated calculations in loops
# BAD:
for i in range(len(data)):
    result = expensive_function(data[i])  # Called every iteration

# GOOD:
expensive_result = expensive_function()  # Called once
for item in data:
    result = expensive_result * item.value

# Use pandas for vectorized operations
# BAD:
returns = []
for i in range(1, len(prices)):
    returns.append((prices[i] - prices[i-1]) / prices[i-1])

# GOOD:
returns = prices.pct_change().dropna()
```

### Memory Management
```python
class DataProcessor:
    """Example of proper resource management."""
    
    def __init__(self):
        self._cache = {}
        self._max_cache_size = 1000
        
    def process_large_dataset(self, file_path: str) -> pd.DataFrame:
        """Process large dataset with memory management."""
        try:
            # Process in chunks to manage memory
            chunk_size = 10000
            processed_chunks = []
            
            for chunk in pd.read_csv(file_path, chunksize=chunk_size):
                processed_chunk = self._process_chunk(chunk)
                processed_chunks.append(processed_chunk)
                
                # Clear intermediate data
                del chunk
                
            return pd.concat(processed_chunks, ignore_index=True)
            
        finally:
            # Cleanup
            processed_chunks.clear()
            self._cleanup_cache()
            
    def _cleanup_cache(self) -> None:
        """Clean up cache when it gets too large."""
        if len(self._cache) > self._max_cache_size:
            # Keep only most recent entries
            sorted_keys = sorted(self._cache.keys())
            keys_to_remove = sorted_keys[:-self._max_cache_size//2]
            
            for key in keys_to_remove:
                del self._cache[key]
```

## Testing Integration

### Test-Friendly Code Structure
```python
class OrderManager:
    """Order management with dependency injection for testing."""
    
    def __init__(self, broker_client=None, risk_manager=None):
        self._broker_client = broker_client or DefaultBrokerClient()
        self._risk_manager = risk_manager or DefaultRiskManager()
        self._logger = SpyderLogger.get_logger(self.__class__.__name__)
        
    def submit_order(self, order_data: dict) -> bool:
        """Submit order with validation and risk checks."""
        # Validate order
        if not self._validate_order(order_data):
            return False
            
        # Risk check
        if not self._risk_manager.validate_order(order_data):
            self._logger.warning("Order rejected by risk manager")
            return False
            
        # Submit to broker
        try:
            result = self._broker_client.submit_order(order_data)
            return result.success
        except Exception as e:
            self._logger.error(f"Order submission failed: {e}")
            return False
            
    def _validate_order(self, order_data: dict) -> bool:
        """Validate order data structure."""
        required_fields = ['symbol', 'quantity', 'order_type', 'price']
        return all(field in order_data for field in required_fields)
```

## Code Quality Checklist

### Pre-Commit Checklist
- [ ] All functions have type hints
- [ ] All public methods have docstrings
- [ ] No hardcoded credentials or sensitive data
- [ ] Appropriate error handling with logging
- [ ] No `print()` statements (use logging instead)
- [ ] Constants defined at module level
- [ ] Private methods prefixed with underscore
- [ ] Imports organized (standard, third-party, local)
- [ ] File follows standard template structure
- [ ] Code follows PEP 8 style guidelines
- [ ] No obvious security vulnerabilities
- [ ] Performance considerations addressed

### Code Review Guidelines
- **Functionality**: Does the code do what it's supposed to do?
- **Readability**: Is the code easy to understand?
- **Maintainability**: Will this code be easy to modify later?
- **Security**: Are there any security implications?
- **Performance**: Are there any performance bottlenecks?
- **Testing**: Is the code structured to be testable?
- **Documentation**: Is the code adequately documented?
- **Standards**: Does the code follow Spyder conventions?

---

Following these coding standards ensures consistency, maintainability, and reliability across the entire Spyder trading system. These standards are living documents that evolve with the system and development best practices.
