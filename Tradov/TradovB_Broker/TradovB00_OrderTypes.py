#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovB_Broker
Module: TradovB00_OrderTypes.py
Purpose: Comprehensive order data structures for broker modules
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-11 Time: 15:45:00

Module Description:
    This module provides comprehensive order-related data structures used across
    all broker integration modules. It defines OrderRequest, OrderAction,
    OrderType, and other shared classes to ensure consistency and type safety
    throughout the trading system. This is the foundational module that all
    other broker modules depend on for order-related operations.

Key Features:
    - Complete order types for Tradier API and TRAD options trading
    - Advanced order attributes for institutional trading
    - Options-specific order structures for TRAD trading
    - Bracket order support for risk management
    - Comprehensive validation and serialization
    - Type-safe enums and data classes
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, UTC
from enum import Enum
from typing import Any

# ==============================================================================
# CORE ENUMS
# ==============================================================================

class OrderAction(Enum):
    """Order action types for buy/sell operations."""
    BUY = "BUY"
    SELL = "SELL"

    def __str__(self) -> str:
        return self.value

class OrderType(Enum):
    """Comprehensive order types supported by the broker API."""
    # Basic order types
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP LMT"

    # Advanced order types
    TRAILING_STOP = "TRAIL"
    TRAILING_STOP_LIMIT = "TRAIL LIMIT"
    MARKET_ON_CLOSE = "MOC"
    LIMIT_ON_CLOSE = "LOC"
    MARKET_ON_OPEN = "MOO"
    LIMIT_ON_OPEN = "LOO"

    # Algorithmic order types
    ADAPTIVE = "ADAPTIVE"
    ARRIVAL_PRICE = "Arrival Price"
    DARK_ICE = "Dark Ice"
    MIDPOINT = "Midpoint"
    TWAP = "TWAP"
    VWAP = "VWAP"

    # Options-specific
    VOLATILITY = "VOL"
    RELATIVE = "REL"

    def __str__(self) -> str:
        return self.value

class OrderStatus(Enum):
    """Order status lifecycle."""
    # Pre-submission
    PENDING = "PendingSubmit"
    PENDING_CANCEL = "PendingCancel"

    # Active states
    SUBMITTED = "Submitted"
    WORKING = "Working"
    PARTIALLY_FILLED = "PartiallyFilled"

    # Terminal states
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"

    # Error states
    INACTIVE = "Inactive"
    ERROR = "Error"

    def __str__(self) -> str:
        return self.value

    @property
    def is_active(self) -> bool:
        """Check if order is in an active state."""
        return self in {self.SUBMITTED, self.WORKING, self.PARTIALLY_FILLED}

    @property
    def is_terminal(self) -> bool:
        """Check if order is in a terminal state."""
        return self in {self.FILLED, self.CANCELLED, self.REJECTED}

    @classmethod
    def validate_transition(
        cls, current: "OrderStatus", proposed: "OrderStatus"
    ) -> bool:
        """A14 (v14): Return True if ``current → proposed`` is allowed.

        Terminal states (FILLED/CANCELLED/REJECTED) are sinks; any outbound
        transition from them is invalid. ERROR/INACTIVE are recovery states
        and may transition back into the active lifecycle.
        """
        if current is proposed:
            return True
        if current in _TERMINAL_STATES:
            return False
        return proposed in _VALID_TRANSITIONS.get(current, set())


# A14 (v14): Canonical state-machine table for OrderStatus transitions.
# Terminal states are deliberately omitted — they are sinks.
_TERMINAL_STATES: "frozenset[OrderStatus]" = frozenset({
    OrderStatus.FILLED,
    OrderStatus.CANCELLED,
    OrderStatus.REJECTED,
})

_VALID_TRANSITIONS: "dict[OrderStatus, frozenset[OrderStatus]]" = {
    OrderStatus.PENDING: frozenset({
        OrderStatus.SUBMITTED,
        OrderStatus.PENDING_CANCEL,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.ERROR,
        OrderStatus.INACTIVE,
    }),
    OrderStatus.PENDING_CANCEL: frozenset({
        OrderStatus.CANCELLED,
        OrderStatus.FILLED,  # race: broker fills before cancel lands
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.REJECTED,
        OrderStatus.ERROR,
    }),
    OrderStatus.SUBMITTED: frozenset({
        OrderStatus.WORKING,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.PENDING_CANCEL,
        OrderStatus.ERROR,
        OrderStatus.INACTIVE,
    }),
    OrderStatus.WORKING: frozenset({
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.PENDING_CANCEL,
        OrderStatus.ERROR,
        OrderStatus.INACTIVE,
    }),
    OrderStatus.PARTIALLY_FILLED: frozenset({
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.PENDING_CANCEL,
        OrderStatus.ERROR,
    }),
    OrderStatus.INACTIVE: frozenset({
        OrderStatus.PENDING,
        OrderStatus.SUBMITTED,
        OrderStatus.CANCELLED,
        OrderStatus.ERROR,
    }),
    OrderStatus.ERROR: frozenset({
        OrderStatus.PENDING,
        OrderStatus.SUBMITTED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.INACTIVE,
    }),
}

class TimeInForce(Enum):
    """Time in force options."""
    DAY = "DAY"           # Day order
    GTC = "GTC"           # Good till canceled
    IOC = "IOC"           # Immediate or cancel
    FOK = "FOK"           # Fill or kill
    GTD = "GTD"           # Good till date
    OPG = "OPG"           # Market open

    def __str__(self) -> str:
        return self.value

class TriggerMethod(Enum):
    """Trigger method for stop orders."""
    DEFAULT = 0
    DOUBLE_BID_ASK = 1
    LAST = 2
    DOUBLE_LAST = 3
    BID_ASK = 4
    LAST_OR_BID_ASK = 7
    MIDPOINT = 8

class OCAType(Enum):
    """One-Cancels-All group types."""
    CANCEL_WITH_BLOCK = 1
    REDUCE_WITH_BLOCK = 2
    REDUCE_NON_BLOCK = 3

class SecType(Enum):
    """Security types for contracts."""
    STOCK = "STK"
    OPTION = "OPT"
    FUTURE = "FUT"
    FOREX = "CASH"
    INDEX = "IND"
    CFD = "CFD"
    COMMODITY = "CMDTY"
    BOND = "BOND"
    FUND = "FUND"

    def __str__(self) -> str:
        return self.value

class OptionRight(Enum):
    """Option rights (Call/Put)."""
    CALL = "C"
    PUT = "P"

    def __str__(self) -> str:
        return self.value

class OrderOrigin(Enum):
    """Order origin for regulatory purposes."""
    CUSTOMER = 0
    FIRM = 1
    UNKNOWN = 2

# ==============================================================================
# CONTRACT DATA STRUCTURES
# ==============================================================================

@dataclass
class ContractDetails:
    """Contract specification for trading instruments."""
    symbol: str
    sec_type: SecType
    exchange: str = "SMART"
    currency: str = "USD"

    # Options-specific
    strike: float | None = None
    expiry: str | None = None  # YYYYMMDD format
    right: OptionRight | None = None
    multiplier: str | None = None

    # Futures-specific
    last_trade_date: str | None = None

    # Identification
    con_id: int | None = None
    local_symbol: str | None = None
    trading_class: str | None = None

    def __post_init__(self):
        """Validate contract details."""
        if self.sec_type == SecType.OPTION:
            if not all([self.strike, self.expiry, self.right]):
                raise ValueError("Options require strike, expiry, and right")

    @property
    def full_symbol(self) -> str:
        """Generate full symbol representation."""
        if self.sec_type == SecType.OPTION:
            return f"{self.symbol}_{self.expiry}_{self.right.value}{self.strike}"
        return self.symbol

    def to_broker_contract(self) -> dict[str, Any]:
        """Convert to broker contract format."""
        contract_dict = {
            'symbol': self.symbol,
            'secType': self.sec_type.value,
            'exchange': self.exchange,
            'currency': self.currency
        }

        if self.strike is not None:
            contract_dict['strike'] = self.strike
        if self.expiry:
            contract_dict['lastTradeDateOrContractMonth'] = self.expiry
        if self.right:
            contract_dict['right'] = self.right.value
        if self.multiplier:
            contract_dict['multiplier'] = self.multiplier
        if self.con_id:
            contract_dict['conId'] = self.con_id

        return contract_dict

@dataclass
class ComboLeg:
    """Combination leg for spread orders."""
    con_id: int
    ratio: int = 1
    action: str = "BUY"  # BUY or SELL
    exchange: str = "SMART"
    open_close: int = 0  # 0=Same, 1=Open, 2=Close
    short_sale_slot: int = 0
    designated_location: str = ""
    exempt_code: int = -1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return asdict(self)

# ==============================================================================
# CORE ORDER DATA STRUCTURES
# ==============================================================================

@dataclass
class OrderRequest:
    """
    Comprehensive order request structure with full broker API compatibility.
    This is the primary order structure used throughout the TRADOV system.
    """
    # Required fields
    contract: ContractDetails
    action: OrderAction
    total_quantity: int | float
    order_type: OrderType

    # Price fields
    lmt_price: float | None = None
    aux_price: float | None = None  # Stop price for stop orders

    # Time in force
    tif: TimeInForce = TimeInForce.DAY

    # Order identification
    order_id: int | None = None
    client_id: int | None = None
    perm_id: int | None = None
    parent_id: int | None = None
    order_ref: str | None = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # Account and transmission
    account: str | None = None
    transmit: bool = True

    # Advanced order attributes
    oca_group: str | None = None
    oca_type: OCAType | None = None

    # Execution options
    display_size: int | None = None
    trigger_method: TriggerMethod | None = None
    outside_rth: bool = False
    hidden: bool = False

    # Discretionary and timing
    discretionary_amt: float = 0.0
    good_after_time: str | None = None  # YYYYMMDD HH:MM:SS
    good_till_date: str | None = None   # YYYYMMDD HH:MM:SS

    # Advanced features
    sweep_to_fill: bool = False
    all_or_none: bool = False
    min_qty: int | None = None
    percent_offset: float | None = None

    # Trailing stops
    trail_stop_price: float | None = None
    trailing_percent: float | None = None

    # Financial advisors
    fa_group: str | None = None
    fa_method: str | None = None
    fa_percentage: str | None = None
    fa_profile: str | None = None

    # Institutional and regulatory
    designated_location: str | None = None
    open_close: str | None = None  # "O"=Open, "C"=Close
    origin: OrderOrigin = OrderOrigin.CUSTOMER
    short_sale_slot: int = 0  # 1=Broker, 2=Third party
    exempt_code: int = -1

    # Combination orders
    combo_legs: list[ComboLeg] = field(default_factory=list)
    smart_combo_routing_params: list[tuple[str, str]] = field(default_factory=list)

    # Algorithmic orders
    algo_strategy: str | None = None
    algo_params: dict[str, str] = field(default_factory=dict)

    # Volatility orders (for options)
    volatility: float | None = None
    volatility_type: int | None = None  # 1=daily, 2=annual
    delta_neutral_order_type: str | None = None
    delta_neutral_aux_price: float | None = None

    # Status tracking
    status: OrderStatus = OrderStatus.PENDING
    filled: float = 0.0
    remaining: float = 0.0
    avg_fill_price: float = 0.0
    last_fill_price: float = 0.0

    # Timestamps
    created_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    submitted_time: datetime | None = None
    filled_time: datetime | None = None

    # Metadata
    strategy_name: str | None = None
    notes: str | None = None

    def __post_init__(self):
        """Post-initialization validation."""
        self._validate_order()

    def _validate_order(self) -> None:
        """Comprehensive order validation."""
        # Quantity validation
        if self.total_quantity <= 0:
            raise ValueError("Order quantity must be positive")

        # Price validation based on order type
        if self.order_type == OrderType.LIMIT and self.lmt_price is None:
            raise ValueError("Limit orders require limit price")

        if self.order_type == OrderType.STOP and self.aux_price is None:
            raise ValueError("Stop orders require stop price")

        if self.order_type == OrderType.STOP_LIMIT:
            if self.lmt_price is None or self.aux_price is None:
                raise ValueError("Stop-limit orders require both limit and stop prices")

        # Trailing stop validation
        if self.order_type == OrderType.TRAILING_STOP:
            if self.trail_stop_price is None and self.trailing_percent is None:
                raise ValueError("Trailing stops require either trail price or trailing percent")

        # Combination order validation
        if self.combo_legs and self.contract.sec_type not in [SecType.OPTION, SecType.FUTURE]:
            raise ValueError("Combination orders only supported for options and futures")

    def transition_to(self, new_status: OrderStatus) -> bool:
        """A14 (v14): Validated transition to a new OrderStatus.

        Always applies the transition (log-only for one release cycle) so we
        don't mask bugs during the v14 paper soak. Returns True if the
        transition was valid, False otherwise. Invalid transitions are logged
        and a ``SYSTEM_ERROR`` event is emitted so the soak report surfaces
        them.
        """
        old_status = self.status
        valid = OrderStatus.validate_transition(old_status, new_status)
        self.status = new_status
        if not valid:
            try:
                import logging
                logging.getLogger(__name__).error(
                    "Invalid OrderStatus transition: %s → %s (order_ref=%s)",
                    old_status,
                    new_status,
                    self.order_ref,
                )
            except Exception:
                pass
            try:
                from Tradov.TradovA_Core.TradovA05_EventManager import (
                    EventType,
                    get_event_manager,
                )
                get_event_manager().emit(
                    EventType.SYSTEM_ERROR,
                    {
                        "source": "OrderStatus.transition_to",
                        "message": "invalid_order_status_transition",
                        "from": str(old_status),
                        "to": str(new_status),
                        "order_ref": self.order_ref,
                    },
                    source="OrderRequest",
                )
            except Exception:
                pass
        return valid

    @property
    def is_buy(self) -> bool:
        """Check if order is a buy order."""
        return self.action == OrderAction.BUY

    @property
    def is_sell(self) -> bool:
        """Check if order is a sell order."""
        return self.action == OrderAction.SELL

    @property
    def is_option(self) -> bool:
        """Check if order is for an option."""
        return self.contract.sec_type == SecType.OPTION

    @property
    def is_combo(self) -> bool:
        """Check if order is a combination order."""
        return len(self.combo_legs) > 0

    @property
    def notional_value(self) -> float | None:
        """Calculate notional value of the order."""
        if self.order_type == OrderType.MARKET:
            return None  # Cannot calculate without market price

        price = self.lmt_price or self.aux_price
        if price is None:
            return None

        multiplier = 100 if self.is_option else 1
        return abs(self.total_quantity * price * multiplier)

    def to_broker_order(self) -> dict[str, Any]:
        """Convert to broker order format."""
        ib_order = {
            'action': self.action.value,
            'totalQuantity': self.total_quantity,
            'orderType': self.order_type.value,
            'tif': self.tif.value,
            'transmit': self.transmit,
            'outsideRth': self.outside_rth,
            'hidden': self.hidden
        }

        # Add optional fields
        if self.lmt_price is not None:
            ib_order['lmtPrice'] = self.lmt_price
        if self.aux_price is not None:
            ib_order['auxPrice'] = self.aux_price
        if self.order_ref:
            ib_order['orderRef'] = self.order_ref
        if self.account:
            ib_order['account'] = self.account
        if self.parent_id:
            ib_order['parentId'] = self.parent_id
        if self.oca_group:
            ib_order['ocaGroup'] = self.oca_group
        if self.oca_type:
            ib_order['ocaType'] = self.oca_type.value

        return ib_order

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Convert enums to values
        data['action'] = self.action.value
        data['order_type'] = self.order_type.value
        data['tif'] = self.tif.value
        data['status'] = self.status.value
        data['contract'] = asdict(self.contract)

        # Handle datetime serialization
        data['created_time'] = self.created_time.isoformat()
        if self.submitted_time:
            data['submitted_time'] = self.submitted_time.isoformat()
        if self.filled_time:
            data['filled_time'] = self.filled_time.isoformat()

        return data

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

# ==============================================================================
# SPECIALIZED ORDER TYPES
# ==============================================================================

@dataclass
class BracketOrder:
    """
    Bracket order for risk management - combines parent, profit-taking, and stop-loss orders.
    Essential for automated options trading with defined risk parameters.
    """
    parent_order: OrderRequest
    profit_target_price: float | None = None
    stop_loss_price: float | None = None
    profit_target_offset: float | None = None
    stop_loss_offset: float | None = None

    def __post_init__(self):
        """Validate bracket order configuration."""
        if not (self.profit_target_price or self.profit_target_offset):
            raise ValueError("Bracket order requires profit target price or offset")

        if not (self.stop_loss_price or self.stop_loss_offset):
            raise ValueError("Bracket order requires stop loss price or offset")

    def generate_orders(self) -> tuple[OrderRequest, OrderRequest, OrderRequest]:
        """Generate the three orders that comprise the bracket."""
        # Parent order
        parent = self.parent_order
        parent.transmit = False  # Don't transmit until all orders are ready

        # Calculate prices if using offsets
        if self.parent_order.lmt_price:
            base_price = self.parent_order.lmt_price
        else:
            raise ValueError("Bracket orders require parent order with limit price")

        # Profit target order
        if self.profit_target_price:
            profit_price = self.profit_target_price
        else:
            if self.parent_order.is_buy:
                profit_price = base_price + self.profit_target_offset
            else:
                profit_price = base_price - self.profit_target_offset

        profit_order = OrderRequest(
            contract=parent.contract,
            action=OrderAction.SELL if parent.is_buy else OrderAction.BUY,
            total_quantity=parent.total_quantity,
            order_type=OrderType.LIMIT,
            lmt_price=profit_price,
            parent_id=parent.order_id,
            transmit=False
        )

        # Stop loss order
        if self.stop_loss_price:
            stop_price = self.stop_loss_price
        else:
            if self.parent_order.is_buy:
                stop_price = base_price - self.stop_loss_offset
            else:
                stop_price = base_price + self.stop_loss_offset

        stop_order = OrderRequest(
            contract=parent.contract,
            action=OrderAction.SELL if parent.is_buy else OrderAction.BUY,
            total_quantity=parent.total_quantity,
            order_type=OrderType.STOP,
            aux_price=stop_price,
            parent_id=parent.order_id,
            transmit=True  # Transmit the last order
        )

        return parent, profit_order, stop_order

@dataclass
class SpreadOrder:
    """
    Multi-leg spread order for options strategies (Iron Condor, Credit Spreads, etc.).
    """
    legs: list[OrderRequest]
    net_premium: float | None = None
    strategy_name: str | None = None

    def __post_init__(self):
        """Validate spread order."""
        if len(self.legs) < 2:
            raise ValueError("Spread orders require at least 2 legs")

        # Ensure all legs are for options
        for leg in self.legs:
            if leg.contract.sec_type != SecType.OPTION:
                raise ValueError("Spread orders are only for options")

    @property
    def total_legs(self) -> int:
        """Get total number of legs."""
        return len(self.legs)

    @property
    def is_credit_spread(self) -> bool:
        """Check if this is a credit spread (net premium received)."""
        return self.net_premium is not None and self.net_premium > 0

    @property
    def is_debit_spread(self) -> bool:
        """Check if this is a debit spread (net premium paid)."""
        return self.net_premium is not None and self.net_premium < 0

# ==============================================================================
# EXECUTION AND FILL DATA STRUCTURES
# ==============================================================================

@dataclass
class Execution:
    """Order execution details."""
    order_id: int
    exec_id: str
    time: datetime
    account: str
    exchange: str
    side: str
    shares: float
    price: float
    perm_id: int
    client_id: int
    liquidation: int = 0
    cum_qty: float = 0.0
    avg_price: float = 0.0

    @property
    def notional_value(self) -> float:
        """Calculate execution notional value."""
        return abs(self.shares * self.price)

@dataclass
class Commission:
    """Commission details for executions."""
    commission: float
    currency: str
    realized_pnl: float | None = None
    yield_: float | None = None
    yield_redemption_date: int | None = None

@dataclass
class Fill:
    """Complete fill information combining execution and commission."""
    execution: Execution
    commission: Commission

    @property
    def net_proceeds(self) -> float:
        """Calculate net proceeds after commission."""
        gross = self.execution.notional_value
        if self.execution.side == "BOT":  # Bought
            return -(gross + abs(self.commission.commission))
        else:  # Sold
            return gross - abs(self.commission.commission)

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_market_order(contract: ContractDetails, action: OrderAction,
                       quantity: int | float, **kwargs) -> OrderRequest:
    """Create a market order."""
    return OrderRequest(
        contract=contract,
        action=action,
        total_quantity=quantity,
        order_type=OrderType.MARKET,
        **kwargs
    )

def create_limit_order(contract: ContractDetails, action: OrderAction,
                      quantity: int | float, limit_price: float,
                      **kwargs) -> OrderRequest:
    """Create a limit order."""
    return OrderRequest(
        contract=contract,
        action=action,
        total_quantity=quantity,
        order_type=OrderType.LIMIT,
        lmt_price=limit_price,
        **kwargs
    )

def create_stop_order(contract: ContractDetails, action: OrderAction,
                     quantity: int | float, stop_price: float,
                     **kwargs) -> OrderRequest:
    """Create a stop order."""
    return OrderRequest(
        contract=contract,
        action=action,
        total_quantity=quantity,
        order_type=OrderType.STOP,
        aux_price=stop_price,
        **kwargs
    )

def create_stop_limit_order(contract: ContractDetails, action: OrderAction,
                           quantity: int | float, stop_price: float,
                           limit_price: float, **kwargs) -> OrderRequest:
    """Create a stop-limit order."""
    return OrderRequest(
        contract=contract,
        action=action,
        total_quantity=quantity,
        order_type=OrderType.STOP_LIMIT,
        aux_price=stop_price,
        lmt_price=limit_price,
        **kwargs
    )

def create_spy_option_contract(expiry: str, strike: float,
                              right: OptionRight) -> ContractDetails:
    """Create TRAD option contract."""
    return ContractDetails(
        symbol="TRAD",
        sec_type=SecType.OPTION,
        exchange="SMART",
        currency="USD",
        expiry=expiry,
        strike=strike,
        right=right,
        multiplier="100"
    )

def create_iron_condor_spread(short_call_strike: float, long_call_strike: float,
                             short_put_strike: float, long_put_strike: float,
                             expiry: str, quantity: int = 1) -> SpreadOrder:
    """Create an Iron Condor spread order."""
    # Create the four legs
    legs = [
        # Short Call
        OrderRequest(
            contract=create_spy_option_contract(expiry, short_call_strike, OptionRight.CALL),
            action=OrderAction.SELL,
            total_quantity=quantity,
            order_type=OrderType.LIMIT
        ),
        # Long Call
        OrderRequest(
            contract=create_spy_option_contract(expiry, long_call_strike, OptionRight.CALL),
            action=OrderAction.BUY,
            total_quantity=quantity,
            order_type=OrderType.LIMIT
        ),
        # Short Put
        OrderRequest(
            contract=create_spy_option_contract(expiry, short_put_strike, OptionRight.PUT),
            action=OrderAction.SELL,
            total_quantity=quantity,
            order_type=OrderType.LIMIT
        ),
        # Long Put
        OrderRequest(
            contract=create_spy_option_contract(expiry, long_put_strike, OptionRight.PUT),
            action=OrderAction.BUY,
            total_quantity=quantity,
            order_type=OrderType.LIMIT
        )
    ]

    return SpreadOrder(legs=legs, strategy_name="Iron Condor")

# ==============================================================================
# VALIDATION FUNCTIONS
# ==============================================================================

def validate_order_request(order: OrderRequest) -> tuple[bool, list[str]]:
    """
    Comprehensive order validation.

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    try:
        # Let the order validate itself
        order._validate_order()
    except ValueError as e:
        errors.append(str(e))

    # Additional business logic validation
    if order.total_quantity > 10000:
        errors.append("Order quantity exceeds maximum allowed (10,000)")

    if order.is_option and order.total_quantity > 1000:
        errors.append("Option order quantity exceeds maximum allowed (1,000)")

    # Price reasonableness checks
    if order.lmt_price and order.lmt_price > 1000000:
        errors.append("Limit price appears unreasonable (> $1M)")

    return len(errors) == 0, errors

# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    # Enums
    'OrderAction', 'OrderType', 'OrderStatus', 'TimeInForce', 'TriggerMethod',
    'OCAType', 'SecType', 'OptionRight', 'OrderOrigin',

    # Core data structures
    'ContractDetails', 'ComboLeg', 'OrderRequest',

    # Specialized orders
    'BracketOrder', 'SpreadOrder',

    # Execution data
    'Execution', 'Commission', 'Fill',

    # Factory functions
    'create_market_order', 'create_limit_order', 'create_stop_order',
    'create_stop_limit_order', 'create_spy_option_contract', 'create_iron_condor_spread',

    # Validation
    'validate_order_request'
]

# ==============================================================================
# MODULE TEST
# ==============================================================================

if __name__ == "__main__":
    # Example usage and testing

    # Create a sample TRAD option contract
    spy_contract = create_spy_option_contract("20250321", 580.0, OptionRight.CALL)

    # Create a limit order
    order = create_limit_order(
        contract=spy_contract,
        action=OrderAction.BUY,
        quantity=10,
        limit_price=2.50,
        strategy_name="Test Order"
    )


    # Validate order
    is_valid, errors = validate_order_request(order)
    if errors:
        for _error in errors:
            pass

    # Create an Iron Condor
    ic_spread = create_iron_condor_spread(
        short_call_strike=590.0,
        long_call_strike=595.0,
        short_put_strike=570.0,
        long_put_strike=565.0,
        expiry="20250321",
        quantity=5
    )


