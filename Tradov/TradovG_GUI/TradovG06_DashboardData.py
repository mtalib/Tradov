#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Module: TradovG06_DashboardData.py
Purpose: Shared data models and types for Trading Dashboard
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-06-26 Time: 13:25:07

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
from datetime import datetime, time as dt_time, UTC
from enum import Enum
import pytz

from Tradov.TradovU_Utilities.TradovU49_SymbolCatalog import get_market_overview_symbols

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

# Legacy constant kept for compatibility; sourced from canonical catalog.
MARKET_SYMBOLS: dict[str, list[str]] = get_market_overview_symbols()

# Symbol descriptions for tooltips
SYMBOL_DESCRIPTIONS = {
    # Major Indices
    "DIA": "SPDR Dow Jones Industrial Average ETF",
    "TRAD": "SPDR S&P 500 ETF - Most liquid S&P 500 ETF",
    "QQQ": "Invesco QQQ Trust - NASDAQ 100 ETF",
    "IWM": "iShares Russell 2000 ETF - Small caps",
    # Market Breadth
    "$TICK": "NYSE Tick Index - Upticks minus downticks",
    "$TRIN": "Arms Index - Advance/Decline volume ratio",
    "$ADD": "Advance-Decline Line - Net advancing issues",
    "NYMO": "NYSE McClellan Oscillator - Breadth momentum",
    "CPC": "CBOE Put/Call Ratio - Equity options only",
    "SKEW": "CBOE Skew Index - Tail risk measure",
    "$VOLD": "NYSE Up/Down Volume Delta - Intraday breadth",
    "XLK": "Technology Select Sector SPDR ETF",
    "XLF": "Financial Select Sector SPDR ETF",
    "TNX": "CBOE 10-Year Treasury Yield Index",
    "RVOL": "Relative Volume - Current vs average volume",
    # Volatility
    "VIX": "CBOE Volatility Index - 30-day implied volatility",
    "VIX9D": "CBOE 9-Day Volatility Index - Short-term IV; leads VIX turns by 1–2 sessions",
    "VXV": "CBOE 3-Month Volatility Index - 93-day implied volatility",
    "VVIX": "VIX of VIX - Volatility of volatility index",
    # Options Analytics
    "IVR":    "TRAD IV Rank (0\u2013100): where current ATM IV sits in its 52-week range",
    "ATM_IV": "TRAD At-the-Money Implied Volatility \u2014 front-month nearest-strike (annualised %)",  # noqa: E501
    "VRP":    "Volatility Risk Premium = ATM IV \u2212 HV20; positive means IV trades above realised vol",  # noqa: E501
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
    "PCA-PROXY": "PCA Proxy - Sector ETF eigenfactor signal for broad TRAD leadership and dispersion",
    "PCA-IV": "PCA IV Surface Factor - Live TRAD implied-volatility surface eigenfactor; seeds until history is sufficient",
    "WRS": "Weighted Regime Score - Composite market regime signal",
    "PSR": "Probabilistic Sharpe Ratio - Strategy edge confidence",
    "SWAN": "Black Swan Risk Indicator - Tail risk monitor",
    "PMR": "Pivot Mean-Reversion Signal (S08) - DIS=disabled, ARMED=watching, fired shows direction/level/score",  # noqa: E501
    # Hidden / backend-only
    "SPX": "S&P 500 Index - Cash index value",
}


MARKET_SIGNAL_DIALOG_METADATA: dict[str, dict[str, object]] = {
    "VIX": {
        "full_name": "VIX - CBOE Volatility Index",
        "description": SYMBOL_DESCRIPTIONS["VIX"],
        "concept": "Market's expectation of future volatility, often called the 'fear gauge'",
        "signal_colors": [
            {"color": "positive", "text": "Green: VIX < 15 (Low volatility, calm markets)"},
            {"color": "neutral", "text": "Yellow: VIX 15-20 (Normal volatility)"},
            {"color": "negative", "text": "Red: VIX > 20 (High volatility, market stress)"},
        ],
    },
    "GEX": {
        "full_name": "GEX - Gamma Exposure",
        "description": SYMBOL_DESCRIPTIONS["GEX"],
        "concept": "Measures hedging pressure from options market makers; negative GEX increases volatility",
        "signal_colors": [
            {"color": "positive", "text": "Green: Positive GEX (>$1B) - Volatility suppression"},
            {"color": "neutral", "text": "Yellow: Near zero (-$1B to $1B) - Transitional"},
            {"color": "negative", "text": "Red: Negative GEX (<-$1B) - Volatility expansion"},
        ],
    },
    "DIX": {
        "full_name": "DIX - Dark Pool Index",
        "description": SYMBOL_DESCRIPTIONS["DIX"],
        "concept": "Tracks institutional buying; high DIX suggests smart money accumulation",
        "signal_colors": [
            {"color": "positive", "text": "Green: DIX > 45% (Bullish institutional buying)"},
            {"color": "neutral", "text": "Yellow: DIX 40-45% (Neutral)"},
            {"color": "negative", "text": "Red: DIX < 40% (Bearish, lack of institutional support)"},
        ],
    },
    "OGL": {
        "full_name": "OGL - Zero Gamma Level",
        "description": SYMBOL_DESCRIPTIONS["OGL"],
        "concept": "Key support/resistance level based on options positioning; acts as a magnet for price",
        "signal_colors": [
            {"color": "positive", "text": "Green: TRAD > OGL + 0.5% (Bullish positioning)"},
            {"color": "neutral", "text": "Yellow: TRAD within +/-0.5% of OGL (Neutral zone)"},
            {"color": "negative", "text": "Red: TRAD < OGL - 0.5% (Bearish positioning)"},
        ],
    },
    "DEX": {
        "full_name": "DEX - Delta Exposure",
        "description": SYMBOL_DESCRIPTIONS["DEX"],
        "concept": "Measures directional hedging flow; indicates market maker positioning bias",
        "signal_colors": [
            {"color": "positive", "text": "Green: Positive DEX (>$500M) - Bullish flow"},
            {"color": "neutral", "text": "Yellow: Neutral (-$500M to $500M)"},
            {"color": "negative", "text": "Red: Negative DEX (<-$500M) - Bearish flow"},
        ],
    },
    "SWAN": {
        "full_name": "BLACK SWAN RISK INDICATOR",
        "description": SYMBOL_DESCRIPTIONS["SWAN"],
        "concept": "Monitors multiple factors to detect potential for rare, extreme market events",
        "signal_colors": [
            {"color": "positive", "text": "Green: SWAN Score < 2.0 (Minimal tail risk)"},
            {"color": "neutral", "text": "Yellow: SWAN Score 2.0-3.0 (Elevated tail risk)"},
            {"color": "negative", "text": "Red: SWAN Score > 3.0 (Extreme tail risk warning)"},
        ],
    },
    "SKEW": {
        "full_name": "SKEW - CBOE SKEW Index",
        "description": SYMBOL_DESCRIPTIONS["SKEW"],
        "concept": "Tracks the relative cost of out-of-the-money puts vs calls; high skew indicates elevated tail risk",
        "signal_colors": [
            {"color": "positive", "text": "Green: SKEW < 125 (Normal tail risk)"},
            {"color": "neutral", "text": "Yellow: SKEW 125-135 (Elevated tail risk)"},
            {"color": "negative", "text": "Red: SKEW > 135 (Extreme tail risk)"},
        ],
    },
}


MARKET_BREADTH_DIALOG_METADATA: dict[str, dict[str, object]] = {
    "$TICK": {
        "full_name": "NYSE TICK - Intraday Breadth Impulse",
        "description": SYMBOL_DESCRIPTIONS["$TICK"],
        "concept": "Tracks the real-time balance of upticking versus downticking NYSE stocks, which helps identify intraday breadth surges and flushes.",
        "signal_colors": [
            {"color": "positive", "text": "Green: Above +600 signals broad buying pressure"},
            {"color": "neutral", "text": "Yellow: Between -600 and +600 signals mixed breadth"},
            {"color": "warning", "text": "Orange: Below -600 signals oversold breadth pressure"},
            {"color": "negative", "text": "Red: Below -1000 signals an extreme bear-flush impulse"},
        ],
    },
    "$ADD": {
        "full_name": "NYSE ADD - Advance/Decline Line",
        "description": SYMBOL_DESCRIPTIONS["$ADD"],
        "concept": "Measures net advancing issues across the NYSE, which shows whether participation is broadening or narrowing beneath index price action.",
        "signal_colors": [
            {"color": "positive", "text": "Green: Above +500 signals broad participation to the upside"},
            {"color": "neutral", "text": "Yellow: Between -500 and +500 signals balanced participation"},
            {"color": "negative", "text": "Red: Below -500 signals broad participation to the downside"},
        ],
    },
    "$TRIN": {
        "full_name": "NYSE TRIN - Arms Index",
        "description": SYMBOL_DESCRIPTIONS["$TRIN"],
        "concept": "Compares advancing versus declining volume; lower values usually support bullish participation while higher values signal defensive or bearish pressure.",
        "signal_colors": [
            {"color": "positive", "text": "Green: Below 0.70 signals strong bullish participation"},
            {"color": "neutral", "text": "Yellow: Between 0.70 and 1.50 signals balanced volume breadth"},
            {"color": "negative", "text": "Red: Above 1.50 signals bearish or defensive breadth pressure"},
        ],
    },
    "NYMO": {
        "full_name": "NYMO - NYSE McClellan Oscillator",
        "description": SYMBOL_DESCRIPTIONS["NYMO"],
        "concept": "Summarizes breadth momentum over multiple sessions and helps distinguish sustained participation from short-lived intraday extremes.",
        "signal_colors": [
            {"color": "positive", "text": "Green: Above +40 signals strong breadth momentum"},
            {"color": "neutral", "text": "Yellow: Between -40 and +40 signals neutral breadth momentum"},
            {"color": "negative", "text": "Red: Below -40 signals weak or washed-out breadth momentum"},
        ],
    },
    "$VOLD": {
        "full_name": "NYSE VOLD - Up/Down Volume Delta",
        "description": SYMBOL_DESCRIPTIONS["$VOLD"],
        "concept": "Measures whether advancing volume or declining volume is dominating intraday tape participation.",
        "signal_colors": [
            {"color": "positive", "text": "Green: Positive delta signals buyers controlling more volume"},
            {"color": "neutral", "text": "Yellow: Near-flat delta signals mixed tape participation"},
            {"color": "negative", "text": "Red: Negative delta signals sellers controlling more volume"},
        ],
    },
    "RVOL": {
        "full_name": "RVOL - Relative Volume",
        "description": SYMBOL_DESCRIPTIONS["RVOL"],
        "concept": "Compares current session participation with the instrument's typical volume so moves can be judged as sponsored, normal, or thin.",
        "signal_colors": [
            {"color": "positive", "text": "Green: Above 1.5x signals expanding participation"},
            {"color": "neutral", "text": "Yellow: Between 0.8x and 1.5x signals normal participation"},
            {"color": "warning", "text": "Orange: Below 0.8x signals thin participation and lower conviction"},
        ],
    },
}


MARKET_OVERVIEW_DIALOG_METADATA: dict[str, dict[str, object]] = {
    **MARKET_SIGNAL_DIALOG_METADATA,
    **MARKET_BREADTH_DIALOG_METADATA,
}


def _copy_dialog_metadata(metadata: dict[str, object]) -> dict[str, object]:
    """Return a detached copy of shared dialog metadata."""
    return {
        "full_name": str(metadata["full_name"]),
        "description": str(metadata["description"]),
        "concept": str(metadata["concept"]),
        "signal_colors": [
            {"color": str(color_info["color"]), "text": str(color_info["text"])}
            for color_info in metadata.get("signal_colors", [])
        ],
    }


def get_market_signal_dialog_metadata(symbol: str) -> dict[str, object] | None:
    """Return shared dialog metadata for market metrics mirrored across dashboard surfaces."""
    metadata = MARKET_SIGNAL_DIALOG_METADATA.get(symbol)
    if metadata is None:
        return None
    return _copy_dialog_metadata(metadata)


def get_market_overview_dialog_metadata(symbol: str) -> dict[str, object] | None:
    """Return shared dialog metadata for Market Overview rows with richer framing."""
    metadata = MARKET_OVERVIEW_DIALOG_METADATA.get(symbol)
    if metadata is None:
        return None
    return _copy_dialog_metadata(metadata)


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
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
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
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
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
        self.last_update = datetime.now(UTC)
        if mode:
            self.connection_mode = mode
        if connected:
            self.last_successful_data = datetime.now(UTC)


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
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
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
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

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
            'allowed_strategies': ', '.join(self.allowed_strategies) if self.allowed_strategies else 'None',  # noqa: E501
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
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def get_time() -> str:
    """
    Get current time as formatted string

    Returns:
        str: Formatted time
    """
    return datetime.now(UTC).strftime("%H:%M:%S")


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
        'TRAD': 450.0,
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
        timestamp=datetime.now(UTC)
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
    spy_data = generate_simulation_market_data('TRAD')

    # Test Position
    position = generate_simulation_position('TRAD', 100)

    # Test GreekRisk
    greeks = GreekRisk(delta=45.5, gamma=-2.3, theta=-156.8, vega=-245.2)

    # Test helper functions
