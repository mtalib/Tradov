#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Module: SpyderG06_DashboardData.py
Purpose: Shared data models and types for Trading Dashboard
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-11-08

Module Description:
    Centralized data structures and types used across all dashboard components.
    This module contains dataclasses, enums, and constants that are shared
    between dashboard panels and widgets.

Components:
    - Data Classes: MarketData, GreekRisk, ConnectionInfo, Position, Order
    - Constants: Colors, Market symbols, Timeframes
    - Helper Functions: Market hours checking, formatting utilities
"""

from dataclasses import dataclass, field
from datetime import datetime, time as dt_time
from enum import Enum
import pytz

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Window dimensions
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080

# Market hours (Eastern Time)
MARKET_OPEN_TIME = dt_time(4, 0)  # 4:00 AM ET
MARKET_CLOSE_TIME = dt_time(16, 30)  # 4:30 PM ET

# Heartbeat and connection monitoring
HEARTBEAT_INTERVAL = 30000  # 30 seconds in milliseconds
HEARTBEAT_WARNING_TIME = 20000  # 20 seconds before next check (blue heart)

# Color scheme
COLORS = {
    "background": "#0a0a0a",
    "panel": "#1a1a1a",
    "border": "#333333",
    "text": "#ffffff",
    "text_dim": "#888888",
    "positive": "#00ff41",
    "negative": "#FF073A",
    "neutral": "#ffd700",
    "warning": "#ff9800",
    "automation_active": "#00b8d4",
    "connecting": "#00b8d4",
    "grid": "#2a2a2a",
    "orange": "#ff9800",
    "red": "#FF073A",
    "cyan": "#00ffff",
    "yellow": "#ffff00",
    "blue": "#4169E1",
    "purple": "#9370DB",
}

# Market symbols organized by category
MARKET_SYMBOLS = {
    "S&P CORE": ["SPY", "SPX"],
    "VOLATILITY": ["VIX", "VIX9D", "VXV", "VVIX"],
    "MARKET INTERNALS": ["$TICK", "$TRIN", "$ADD", "CPC", "SKEW"],
    "MAJOR INDICES": ["QQQ", "IWM"],
    "BONDS & CREDIT": ["TLT", "HYG", "LQD"],
    "CORRELATIONS": ["DXY", "GLD", "USO"],
    "OPTIONS ANALYTICS": ["IVR", "ATM_IV", "VRP"],
    "CUSTOM METRICS": ["GEX", "DEX", "OGL", "DIX", "SWAN", "PMR"],
}

# Symbol descriptions for tooltips
SYMBOL_DESCRIPTIONS = {
    # S&P Core
    "SPY": "SPDR S&P 500 ETF - Most liquid S&P 500 ETF",
    "SPX": "S&P 500 Index - Cash index value",
    # Volatility
    "VIX": "CBOE Volatility Index - 30-day implied volatility",
    "VIX9D": "CBOE 9-Day Volatility Index - Short-term IV; leads VIX turns by 1–2 sessions",
    "VXV": "CBOE 3-Month Volatility Index - 93-day implied volatility",
    "VVIX": "VIX of VIX - Volatility of volatility index",
    # Market Internals
    "$TICK": "NYSE Tick Index - Upticks minus downticks",
    "$TRIN": "Arms Index - Advance/Decline volume ratio",
    "$ADD": "Advance-Decline Line - Net advancing issues",
    "CPC": "CBOE Put/Call Ratio - Equity options only",
    "SKEW": "CBOE Skew Index - Tail risk measure",
    # Major Indices
    "QQQ": "Invesco QQQ Trust - NASDAQ 100 ETF",
    "IWM": "iShares Russell 2000 ETF - Small caps",
    # Bonds & Credit
    "TLT": "iShares 20+ Year Treasury Bond ETF",
    "HYG": "iShares High Yield Corporate Bond ETF - Credit stress indicator; widens before LQD",
    "LQD": "iShares Investment Grade Corporate Bond ETF",
    # Correlations
    "DXY": "US Dollar Index - Dollar strength",
    "GLD": "SPDR Gold Trust ETF - Gold proxy",
    "USO": "United States Oil Fund ETF - WTI crude oil proxy",
    # Custom Metrics
    "GEX": "Gamma Exposure - Market maker hedging pressure",
    "DEX": "Delta Exposure - Directional hedging flow",
    "OGL": "Zero Gamma Level - Key support/resistance",
    "DIX": "Dark Index - Dark pool buying percentage",
    "SWAN": "Black Swan Risk Indicator - Tail risk monitor",
    "PMR": "Pivot Mean-Reversion Signal (S08) - DIS=disabled, ARMED=watching, fired shows direction/level/score",
    # Options Analytics
    "IVR":    "SPY IV Rank (0\u2013100): where current ATM IV sits in its 52-week range",
    "ATM_IV": "SPY At-the-Money Implied Volatility \u2014 front-month nearest-strike (annualised %)",
    "VRP":    "Volatility Risk Premium = ATM IV \u2212 HV20; positive means IV trades above realised vol",
}


# ==============================================================================
# ENUMS
# ==============================================================================

class TradingMode(Enum):
    """Trading mode enumeration"""
    LIVE = "LIVE"
    PAPER = "PAPER"
    SIMULATION = "SIMULATION"


class ConnectionStatus(Enum):
    """Connection status enumeration"""
    CONNECTED = "CONNECTED"
    CONNECTING = "CONNECTING"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"


class OrderStatus(Enum):
    """Order status enumeration"""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    PARTIAL = "PARTIAL"


class OrderType(Enum):
    """Order type enumeration"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderAction(Enum):
    """Order action enumeration"""
    BUY = "BUY"
    SELL = "SELL"


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class MarketData:
    """Market data snapshot for a symbol"""
    symbol: str
    last: float
    change: float = 0.0
    change_pct: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    bid: float | None = None
    ask: float | None = None
    volume: int | None = None
    high: float | None = None
    low: float | None = None
    open: float | None = None
    close: float | None = None


@dataclass
class GreekRisk:
    """Options Greek risk metrics"""
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float = 0.0

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary"""
        return {
            'delta': self.delta,
            'gamma': self.gamma,
            'theta': self.theta,
            'vega': self.vega,
            'rho': self.rho
        }


@dataclass
class Position:
    """Trading position"""
    symbol: str
    quantity: int
    avg_cost: float
    current_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    position_type: str = "STOCK"  # STOCK, OPTION, FUTURE
    expiry: str | None = None
    strike: float | None = None
    right: str | None = None  # CALL, PUT

    @property
    def market_value(self) -> float:
        """Calculate current market value"""
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        """Calculate cost basis"""
        return self.quantity * self.avg_cost

    @property
    def pnl_pct(self) -> float:
        """Calculate P&L percentage"""
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100


@dataclass
class Order:
    """Trading order"""
    order_id: str
    symbol: str
    action: OrderAction
    order_type: OrderType
    quantity: int
    status: OrderStatus
    limit_price: float | None = None
    stop_price: float | None = None
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    filled_timestamp: datetime | None = None

    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled"""
        return self.status == OrderStatus.FILLED

    @property
    def is_active(self) -> bool:
        """Check if order is still active"""
        return self.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL]

    @property
    def remaining_quantity(self) -> int:
        """Calculate remaining quantity"""
        return self.quantity - self.filled_quantity


@dataclass
class ConnectionInfo:
    """Connection and status information"""
    ib_connected: bool = False
    bridge_connected: bool = False
    connection_mode: str = "DISCONNECTED"
    market_data_status: str = "NONE"
    trading_active: bool = False
    last_update: datetime | None = None
    last_successful_data: datetime | None = None
    data_was_live: bool = False
    simulation_mode: bool = False

    def update_connection_status(self, connected: bool, mode: str = None):
        """Update connection status"""
        self.ib_connected = connected
        self.last_update = datetime.now()
        if mode:
            self.connection_mode = mode
        if connected:
            self.last_successful_data = datetime.now()


@dataclass
class AccountInfo:
    """Account information"""
    account_id: str
    net_liquidation: float = 0.0
    total_cash: float = 0.0
    settled_cash: float = 0.0
    buying_power: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    day_trades_remaining: int = 0
    trading_mode: TradingMode = TradingMode.PAPER

    @property
    def total_pnl(self) -> float:
        """Calculate total P&L"""
        return self.unrealized_pnl + self.realized_pnl


@dataclass
class SignalData:
    """Trading signal data"""
    signal_name: str
    value: float
    status: str  # BULLISH, BEARISH, NEUTRAL, WARNING
    timestamp: datetime = field(default_factory=datetime.now)
    description: str | None = None

    def get_status_color(self) -> str:
        """Get color based on status"""
        status_colors = {
            'BULLISH': COLORS['positive'],
            'BEARISH': COLORS['negative'],
            'NEUTRAL': COLORS['neutral'],
            'WARNING': COLORS['warning'],
        }
        return status_colors.get(self.status, COLORS['text_dim'])


@dataclass
class EventClockState:
    """Event-clock state and policy display for dashboard"""
    state: str = "clear"  # pre/live/post/clear
    enabled: bool = True
    sources: str = "calendar+manual"  # manual, calendar, calendar+manual
    allowed_strategies: list[str] = field(default_factory=list)
    blackout_pre_minutes: int = 30
    blackout_post_minutes: int = 30
    max_size_multiplier: float = 0.25
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def state_color(self) -> str:
        """Get color based on event-clock state"""
        state_colors = {
            'clear': COLORS['positive'],      # Green
            'pre': COLORS['warning'],          # Orange
            'live': COLORS['negative'],        # Red
            'post': COLORS['warning'],         # Orange
        }
        return state_colors.get(self.state, COLORS['text_dim'])

    @property
    def state_label(self) -> str:
        """Get human-readable state label"""
        state_labels = {
            'clear': '✓ CLEAR',
            'pre': '⊕ PRE-EVENT',
            'live': '◆ LIVE EVENT',
            'post': '⊖ POST-EVENT',
        }
        return state_labels.get(self.state, 'UNKNOWN')

    def to_dict(self) -> dict:
        """Convert to dictionary for display"""
        return {
            'state': self.state,
            'state_label': self.state_label,
            'enabled': self.enabled,
            'sources': self.sources,
            'allowed_strategies': ', '.join(self.allowed_strategies) if self.allowed_strategies else 'None',
            'blackout_pre_minutes': self.blackout_pre_minutes,
            'blackout_post_minutes': self.blackout_post_minutes,
            'max_size_multiplier': f'{self.max_size_multiplier:.2%}',
            'timestamp': self.timestamp.strftime('%H:%M:%S'),
        }


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def is_market_hours() -> bool:
    """
    Check if current time is within market hours (4:00 AM - 4:30 PM ET)

    Returns:
        bool: True if within market hours, False otherwise
    """
    eastern = pytz.timezone("US/Eastern")
    now_et = datetime.now(eastern).time()
    return MARKET_OPEN_TIME <= now_et <= MARKET_CLOSE_TIME


def format_currency(value: float, decimals: int = 2) -> str:
    """
    Format a value as currency

    Args:
        value: The value to format
        decimals: Number of decimal places

    Returns:
        str: Formatted currency string
    """
    if value >= 0:
        return f"${value:,.{decimals}f}"
    else:
        return f"-${abs(value):,.{decimals}f}"


def format_percentage(value: float, decimals: int = 2, with_sign: bool = True) -> str:
    """
    Format a value as percentage

    Args:
        value: The value to format
        decimals: Number of decimal places
        with_sign: Whether to include + sign for positive values

    Returns:
        str: Formatted percentage string
    """
    if with_sign and value > 0:
        return f"+{value:.{decimals}f}%"
    return f"{value:.{decimals}f}%"


def format_number(value: float, decimals: int = 2, abbreviate: bool = False) -> str:
    """
    Format a number with optional abbreviation (K, M, B)

    Args:
        value: The value to format
        decimals: Number of decimal places
        abbreviate: Whether to abbreviate large numbers

    Returns:
        str: Formatted number string
    """
    if not abbreviate:
        return f"{value:,.{decimals}f}"

    abs_value = abs(value)
    sign = "-" if value < 0 else ""

    if abs_value >= 1_000_000_000:
        return f"{sign}{abs_value/1_000_000_000:.{decimals}f}B"
    elif abs_value >= 1_000_000:
        return f"{sign}{abs_value/1_000_000:.{decimals}f}M"
    elif abs_value >= 1_000:
        return f"{sign}{abs_value/1_000:.{decimals}f}K"
    else:
        return f"{sign}{abs_value:.{decimals}f}"


def get_color_for_value(value: float, invert: bool = False) -> str:
    """
    Get color based on value (positive/negative)

    Args:
        value: The value to check
        invert: If True, negative is green (e.g., for theta decay)

    Returns:
        str: Color hex code
    """
    if value == 0:
        return COLORS['neutral']

    if invert:
        return COLORS['positive'] if value < 0 else COLORS['negative']
    else:
        return COLORS['positive'] if value > 0 else COLORS['negative']


def get_timestamp() -> str:
    """
    Get current timestamp as formatted string

    Returns:
        str: Formatted timestamp
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_time() -> str:
    """
    Get current time as formatted string

    Returns:
        str: Formatted time
    """
    return datetime.now().strftime("%H:%M:%S")


# ==============================================================================
# SIMULATION DATA GENERATORS
# ==============================================================================

def generate_simulation_market_data(symbol: str) -> MarketData:
    """
    Generate simulated market data for testing

    Args:
        symbol: The symbol to generate data for

    Returns:
        MarketData: Simulated market data
    """
    import random

    # Base prices for common symbols
    base_prices = {
        'SPY': 450.0,
        'QQQ': 380.0,
        'IWM': 195.0,
        'VIX': 15.0,
        'SPX': 4500.0,
    }

    base_price = base_prices.get(symbol, 100.0)
    last = base_price + random.uniform(-5, 5)
    change = random.uniform(-3, 3)
    change_pct = (change / last) * 100

    return MarketData(
        symbol=symbol,
        last=last,
        change=change,
        change_pct=change_pct,
        bid=last - 0.02,
        ask=last + 0.02,
        volume=random.randint(1000000, 10000000),
        high=last + random.uniform(0, 3),
        low=last - random.uniform(0, 3),
        timestamp=datetime.now()
    )


def generate_simulation_position(symbol: str, quantity: int = 100) -> Position:
    """
    Generate simulated position for testing

    Args:
        symbol: The symbol
        quantity: Position quantity

    Returns:
        Position: Simulated position
    """
    import random

    avg_cost = 450.0 + random.uniform(-10, 10)
    current_price = avg_cost + random.uniform(-5, 5)
    unrealized_pnl = (current_price - avg_cost) * quantity

    return Position(
        symbol=symbol,
        quantity=quantity,
        avg_cost=avg_cost,
        current_price=current_price,
        unrealized_pnl=unrealized_pnl,
        position_type="STOCK"
    )


if __name__ == '__main__':
    # Test the data structures

    # Test MarketData
    spy_data = generate_simulation_market_data('SPY')

    # Test Position
    position = generate_simulation_position('SPY', 100)

    # Test GreekRisk
    greeks = GreekRisk(delta=45.5, gamma=-2.3, theta=-156.8, vega=-245.2)

    # Test helper functions
