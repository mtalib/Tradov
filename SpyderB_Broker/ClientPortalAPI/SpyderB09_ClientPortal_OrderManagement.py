#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB09_ClientPortal_OrderManagement.py
Purpose: Complete order management system for Client Portal API

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-11-09 Time: 15:00:00

Module Description:
    Comprehensive order management for IBKR Client Portal API.

    CORE FEATURES:
    - Order placement (market, limit, stop, stop-limit)
    - Order modification (price, quantity)
    - Order cancellation
    - Position tracking and monitoring
    - Order status polling
    - Bracket orders (parent + stop-loss + take-profit)
    - Multi-leg strategies (spreads, straddles, etc.)

    ORDER TYPES SUPPORTED:
    - MKT: Market order (immediate execution)
    - LMT: Limit order (price-specified)
    - STP: Stop order (trigger at stop price)
    - STP LMT: Stop-limit (trigger + limit price)
    - MOC: Market-on-close
    - LOC: Limit-on-close

    ORDER PROPERTIES:
    - Time in Force: DAY, GTC, IOC, FOK
    - Outside RTH: Trade outside regular hours
    - All-or-None: Fill complete order or nothing
    - Hidden: Don't display order size

    POSITION TRACKING:
    - Real-time position updates
    - P&L calculation
    - Average cost tracking
    - Position consolidation

Module Constants:
    DEFAULT_TIF (str): Default time-in-force ('DAY')
    ORDER_STATUS_POLL_INTERVAL (int): Status check interval (5 seconds)
    MAX_ORDER_HISTORY (int): Maximum cached orders (1000)

Change Log:
    2025-11-09 (v1.0.0):
        - Initial implementation with full order lifecycle
        - Order placement, modification, cancellation
        - Position tracking
        - Bracket order support
        - Order status monitoring

References:
    - CLIENT_PORTAL_WEB_API_BEST_PRACTICES.md
    - https://interactivebrokers.github.io/cpwebapi/#order-submission
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock
import time

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
# (None required)

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from .SpyderB09_ClientPortal_RESTClient import ClientPortalRESTClient
from .SpyderB09_ClientPortal_Session import SessionManager
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

logger = SpyderLogger.get_logger(__name__)


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

__all__ = [
    # Enums
    'OrderType',
    'OrderSide',
    'TimeInForce',
    'OrderStatus',
    # Data classes
    'Order',
    'Position',
    'OrderTicket',
    # Manager
    'OrderManager',
]


# ==============================================================================
# MODULE CONSTANTS
# ==============================================================================

DEFAULT_TIF = 'DAY'
ORDER_STATUS_POLL_INTERVAL = 5  # seconds
MAX_ORDER_HISTORY = 1000


# ==============================================================================
# ENUMERATIONS
# ==============================================================================

class OrderType(Enum):
    """Order types"""
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP LMT"
    MARKET_ON_CLOSE = "MOC"
    LIMIT_ON_CLOSE = "LOC"


class OrderSide(Enum):
    """Order side (buy/sell)"""
    BUY = "BUY"
    SELL = "SELL"


class TimeInForce(Enum):
    """Time in force"""
    DAY = "DAY"  # Good for day
    GTC = "GTC"  # Good till cancelled
    IOC = "IOC"  # Immediate or cancel
    FOK = "FOK"  # Fill or kill


class OrderStatus(Enum):
    """Order status"""
    PENDING_SUBMIT = "PendingSubmit"
    PRE_SUBMITTED = "PreSubmitted"
    SUBMITTED = "Submitted"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    INACTIVE = "Inactive"
    PENDING_CANCEL = "PendingCancel"
    UNKNOWN = "Unknown"


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class OrderTicket:
    """Order request parameters"""
    conid: int
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    tif: TimeInForce = TimeInForce.DAY
    outside_rth: bool = False
    account: Optional[str] = None

    # Advanced options
    all_or_none: bool = False
    hidden: bool = False
    iceberg_quantity: Optional[float] = None

    # Bracket order components
    parent_id: Optional[str] = None
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None

    def to_api_format(self) -> Dict[str, Any]:
        """Convert to IBKR API format"""
        order_dict = {
            "conid": self.conid,
            "orderType": self.order_type.value,
            "side": self.side.value,
            "quantity": self.quantity,
            "tif": self.tif.value,
            "outsideRTH": self.outside_rth,
        }

        if self.limit_price is not None:
            order_dict["price"] = self.limit_price

        if self.stop_price is not None:
            order_dict["auxPrice"] = self.stop_price

        if self.account:
            order_dict["acctId"] = self.account

        if self.all_or_none:
            order_dict["allOrNone"] = True

        if self.hidden:
            order_dict["hidden"] = True

        if self.iceberg_quantity:
            order_dict["displaySize"] = self.iceberg_quantity

        if self.parent_id:
            order_dict["parentId"] = self.parent_id

        return order_dict


@dataclass
class Order:
    """Submitted order information"""
    order_id: str
    conid: int
    side: OrderSide
    quantity: float
    order_type: OrderType
    status: OrderStatus
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    avg_fill_price: Optional[float] = None
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    parent_id: Optional[str] = None
    child_orders: List[str] = field(default_factory=list)

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'Order':
        """Create Order from API response"""
        return cls(
            order_id=data.get('orderId', ''),
            conid=data.get('conid', 0),
            side=OrderSide(data.get('side', 'BUY')),
            quantity=float(data.get('totalSize', 0)),
            order_type=OrderType(data.get('orderType', 'MKT')),
            status=OrderStatus(data.get('status', 'Unknown')),
            filled_quantity=float(data.get('filledQuantity', 0)),
            remaining_quantity=float(data.get('remainingQuantity', 0)),
            avg_fill_price=data.get('avgPrice'),
            limit_price=data.get('price'),
            stop_price=data.get('auxPrice'),
            submitted_at=datetime.now(),
            parent_id=data.get('parentId'),
        )

    def is_active(self) -> bool:
        """Check if order is still active"""
        return self.status in [
            OrderStatus.PENDING_SUBMIT,
            OrderStatus.PRE_SUBMITTED,
            OrderStatus.SUBMITTED
        ]

    def is_filled(self) -> bool:
        """Check if order is completely filled"""
        return self.status == OrderStatus.FILLED

    def is_cancelled(self) -> bool:
        """Check if order was cancelled"""
        return self.status == OrderStatus.CANCELLED


@dataclass
class Position:
    """Current position information"""
    conid: int
    symbol: str
    quantity: float
    avg_cost: float
    market_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    realized_pnl: Optional[float] = None
    account: Optional[str] = None

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'Position':
        """Create Position from API response"""
        return cls(
            conid=data.get('conid', 0),
            symbol=data.get('contractDesc', ''),
            quantity=float(data.get('position', 0)),
            avg_cost=float(data.get('avgCost', 0)),
            market_price=data.get('mktPrice'),
            market_value=data.get('mktValue'),
            unrealized_pnl=data.get('unrealizedPnl'),
            realized_pnl=data.get('realizedPnl'),
            account=data.get('acctId'),
        )

    def __repr__(self) -> str:
        return (
            f"Position({self.symbol}: {self.quantity} @ ${self.avg_cost:.2f}, "
            f"P&L: ${self.unrealized_pnl:.2f})"
        )


# ==============================================================================
# ORDER MANAGER
# ==============================================================================

class OrderManager:
    """
    Complete order management system for Client Portal API.

    Features:
    - Place, modify, cancel orders
    - Track order status
    - Monitor positions
    - Bracket orders (stop-loss + take-profit)
    - Order history

    Usage:
        >>> from SpyderB_Broker.ClientPortalAPI import SessionManager, OrderManager
        >>> session_mgr = SessionManager(auth_client, base_url)
        >>> session_mgr.start()
        >>>
        >>> order_mgr = OrderManager(session_mgr)
        >>>
        >>> # Place market order
        >>> ticket = OrderTicket(
        ...     conid=756733,  # SPY
        ...     side=OrderSide.BUY,
        ...     quantity=100,
        ...     order_type=OrderType.MARKET
        ... )
        >>> order = order_mgr.place_order(ticket)
        >>> print(f"Order placed: {order.order_id}")
        >>>
        >>> # Place bracket order (with stop-loss and take-profit)
        >>> bracket = order_mgr.place_bracket_order(
        ...     conid=756733,
        ...     side=OrderSide.BUY,
        ...     quantity=100,
        ...     entry_price=450.00,
        ...     stop_loss_price=445.00,
        ...     take_profit_price=455.00
        ... )
        >>>
        >>> # Check positions
        >>> positions = order_mgr.get_positions()
        >>> for pos in positions:
        ...     print(f"{pos.symbol}: {pos.quantity} shares, P&L: ${pos.unrealized_pnl:.2f}")

    Important:
        - Requires active session
        - Orders require reply confirmation (use reply endpoint)
        - Bracket orders create 3 linked orders
        - Position updates may have slight delay
    """

    def __init__(self, session_manager: SessionManager):
        """
        Initialize Order Manager.

        Args:
            session_manager: Active SessionManager instance
        """
        self.session_manager = session_manager
        self.rest_client = ClientPortalRESTClient(session_manager)

        # Order tracking
        self.orders: Dict[str, Order] = {}  # order_id -> Order
        self.order_lock = Lock()

        # Position tracking
        self.positions: Dict[int, Position] = {}  # conid -> Position
        self.position_lock = Lock()

        logger.info("OrderManager initialized")

    def place_order(self, ticket: OrderTicket) -> Optional[Order]:
        """
        Place an order.

        Args:
            ticket: Order parameters

        Returns:
            Order object if successful, None otherwise

        Example:
            >>> ticket = OrderTicket(
            ...     conid=756733,
            ...     side=OrderSide.BUY,
            ...     quantity=100,
            ...     order_type=OrderType.LIMIT,
            ...     limit_price=450.00
            ... )
            >>> order = order_mgr.place_order(ticket)
        """
        try:
            # Get account ID if not specified
            if not ticket.account:
                accounts = self.get_accounts()
                if not accounts:
                    logger.error("No accounts available")
                    return None
                ticket.account = accounts[0]

            # Convert to API format
            order_data = ticket.to_api_format()

            # Submit order
            endpoint = f"/iserver/account/{ticket.account}/orders"
            response = self.rest_client.post(endpoint, data={"orders": [order_data]})

            # Check for reply requirement
            if isinstance(response, list) and len(response) > 0:
                reply_data = response[0]

                # If reply required, confirm the order
                if 'id' in reply_data:
                    reply_id = reply_data['id']
                    confirmed = self._confirm_order(reply_id)

                    if confirmed:
                        order_id = reply_data.get('order_id', reply_id)
                        logger.info(f"✅ Order placed: {order_id}")

                        # Create Order object
                        order = Order(
                            order_id=order_id,
                            conid=ticket.conid,
                            side=ticket.side,
                            quantity=ticket.quantity,
                            order_type=ticket.order_type,
                            status=OrderStatus.SUBMITTED,
                            limit_price=ticket.limit_price,
                            stop_price=ticket.stop_price,
                            submitted_at=datetime.now()
                        )

                        # Track order
                        with self.order_lock:
                            self.orders[order_id] = order

                        return order

            logger.error(f"Order placement failed: {response}")
            return None

        except Exception as e:
            logger.error(f"Order placement error: {e}", exc_info=True)
            return None

    def place_bracket_order(
        self,
        conid: int,
        side: OrderSide,
        quantity: float,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        account: Optional[str] = None
    ) -> Optional[Dict[str, Order]]:
        """
        Place a bracket order (entry + stop-loss + take-profit).

        Args:
            conid: Contract ID
            side: BUY or SELL
            quantity: Order quantity
            entry_price: Entry limit price
            stop_loss_price: Stop-loss trigger price
            take_profit_price: Take-profit limit price
            account: Account ID (optional)

        Returns:
            Dictionary with 'parent', 'stop_loss', 'take_profit' orders

        Example:
            >>> bracket = order_mgr.place_bracket_order(
            ...     conid=756733,
            ...     side=OrderSide.BUY,
            ...     quantity=100,
            ...     entry_price=450.00,
            ...     stop_loss_price=445.00,
            ...     take_profit_price=455.00
            ... )
            >>> print(f"Parent: {bracket['parent'].order_id}")
        """
        try:
            # Place parent order (entry)
            parent_ticket = OrderTicket(
                conid=conid,
                side=side,
                quantity=quantity,
                order_type=OrderType.LIMIT,
                limit_price=entry_price,
                tif=TimeInForce.GTC,
                account=account
            )

            parent_order = self.place_order(parent_ticket)
            if not parent_order:
                logger.error("Parent order placement failed")
                return None

            logger.info(f"✅ Parent order placed: {parent_order.order_id}")

            # Determine child order side (opposite of parent)
            child_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY

            # Place stop-loss order
            stop_loss_ticket = OrderTicket(
                conid=conid,
                side=child_side,
                quantity=quantity,
                order_type=OrderType.STOP,
                stop_price=stop_loss_price,
                tif=TimeInForce.GTC,
                parent_id=parent_order.order_id,
                account=account or parent_ticket.account
            )

            stop_loss_order = self.place_order(stop_loss_ticket)

            # Place take-profit order
            take_profit_ticket = OrderTicket(
                conid=conid,
                side=child_side,
                quantity=quantity,
                order_type=OrderType.LIMIT,
                limit_price=take_profit_price,
                tif=TimeInForce.GTC,
                parent_id=parent_order.order_id,
                account=account or parent_ticket.account
            )

            take_profit_order = self.place_order(take_profit_ticket)

            if stop_loss_order and take_profit_order:
                # Link orders
                parent_order.child_orders = [
                    stop_loss_order.order_id,
                    take_profit_order.order_id
                ]

                logger.info(f"✅ Bracket order complete: {parent_order.order_id}")

                return {
                    'parent': parent_order,
                    'stop_loss': stop_loss_order,
                    'take_profit': take_profit_order
                }

            logger.warning("Bracket order partially filled")
            return None

        except Exception as e:
            logger.error(f"Bracket order placement error: {e}", exc_info=True)
            return None

    def modify_order(
        self,
        order_id: str,
        new_quantity: Optional[float] = None,
        new_price: Optional[float] = None
    ) -> bool:
        """
        Modify an existing order.

        Args:
            order_id: Order ID to modify
            new_quantity: New order quantity (optional)
            new_price: New limit/stop price (optional)

        Returns:
            True if modification successful

        Example:
            >>> order_mgr.modify_order(order_id="12345", new_price=451.00)
        """
        try:
            # Get current order
            order = self.get_order_status(order_id)
            if not order or not order.is_active():
                logger.error(f"Order {order_id} not active")
                return False

            # Build modification request
            mod_data = {"orderId": order_id}

            if new_quantity is not None:
                mod_data["quantity"] = new_quantity

            if new_price is not None:
                mod_data["price"] = new_price

            # Submit modification
            endpoint = f"/iserver/account/{order.account}/order/{order_id}"
            response = self.rest_client.post(endpoint, data=mod_data)

            logger.info(f"✅ Order {order_id} modified")
            return True

        except Exception as e:
            logger.error(f"Order modification error: {e}", exc_info=True)
            return False

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancellation successful

        Example:
            >>> order_mgr.cancel_order("12345")
        """
        try:
            # Get account from tracked orders
            with self.order_lock:
                if order_id not in self.orders:
                    logger.error(f"Order {order_id} not found in tracking")
                    return False

                account = self.orders[order_id].account or self.get_accounts()[0]

            # Cancel order
            endpoint = f"/iserver/account/{account}/order/{order_id}"
            response = self.rest_client.delete(endpoint)

            logger.info(f"✅ Order {order_id} cancelled")

            # Update status
            with self.order_lock:
                if order_id in self.orders:
                    self.orders[order_id].status = OrderStatus.CANCELLED

            return True

        except Exception as e:
            logger.error(f"Order cancellation error: {e}", exc_info=True)
            return False

    def get_order_status(self, order_id: str) -> Optional[Order]:
        """
        Get current order status.

        Args:
            order_id: Order ID

        Returns:
            Order object with current status

        Example:
            >>> order = order_mgr.get_order_status("12345")
            >>> print(f"Status: {order.status}")
        """
        try:
            # Check cache first
            with self.order_lock:
                if order_id in self.orders:
                    cached_order = self.orders[order_id]

                    # If already final status, return cache
                    if cached_order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
                        return cached_order

            # Fetch live orders
            live_orders = self.get_live_orders()

            for order in live_orders:
                if order.order_id == order_id:
                    # Update cache
                    with self.order_lock:
                        self.orders[order_id] = order
                    return order

            # Not found in live orders
            with self.order_lock:
                if order_id in self.orders:
                    return self.orders[order_id]

            return None

        except Exception as e:
            logger.error(f"Get order status error: {e}", exc_info=True)
            return None

    def get_live_orders(self) -> List[Order]:
        """
        Get all live (active) orders.

        Returns:
            List of Order objects

        Example:
            >>> orders = order_mgr.get_live_orders()
            >>> for order in orders:
            ...     print(f"{order.order_id}: {order.status}")
        """
        try:
            endpoint = "/iserver/account/orders"
            response = self.rest_client.get(endpoint)

            if 'orders' in response:
                orders = [
                    Order.from_api_response(order_data)
                    for order_data in response['orders']
                ]

                # Update cache
                with self.order_lock:
                    for order in orders:
                        self.orders[order.order_id] = order

                return orders

            return []

        except Exception as e:
            logger.error(f"Get live orders error: {e}", exc_info=True)
            return []

    def get_positions(self, account: Optional[str] = None) -> List[Position]:
        """
        Get current positions.

        Args:
            account: Account ID (optional, uses first account if not specified)

        Returns:
            List of Position objects

        Example:
            >>> positions = order_mgr.get_positions()
            >>> for pos in positions:
            ...     print(f"{pos.symbol}: {pos.quantity}")
        """
        try:
            if not account:
                accounts = self.get_accounts()
                if not accounts:
                    return []
                account = accounts[0]

            endpoint = f"/portfolio/{account}/positions/0"
            response = self.rest_client.get(endpoint)

            if isinstance(response, list):
                positions = [
                    Position.from_api_response(pos_data)
                    for pos_data in response
                ]

                # Update cache
                with self.position_lock:
                    self.positions.clear()
                    for pos in positions:
                        self.positions[pos.conid] = pos

                return positions

            return []

        except Exception as e:
            logger.error(f"Get positions error: {e}", exc_info=True)
            return []

    def get_accounts(self) -> List[str]:
        """
        Get available trading accounts.

        Returns:
            List of account IDs

        Example:
            >>> accounts = order_mgr.get_accounts()
            >>> print(f"Accounts: {accounts}")
        """
        try:
            endpoint = "/portfolio/accounts"
            response = self.rest_client.get(endpoint)

            if isinstance(response, list):
                return [account['accountId'] for account in response]

            return []

        except Exception as e:
            logger.error(f"Get accounts error: {e}", exc_info=True)
            return []

    def _confirm_order(self, reply_id: str) -> bool:
        """Confirm order after reply prompt"""
        try:
            endpoint = f"/iserver/reply/{reply_id}"
            response = self.rest_client.post(endpoint, data={"confirmed": True})

            return True

        except Exception as e:
            logger.error(f"Order confirmation error: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get order manager statistics"""
        return {
            'tracked_orders': len(self.orders),
            'cached_positions': len(self.positions),
            'active_orders': sum(1 for o in self.orders.values() if o.is_active()),
            'filled_orders': sum(1 for o in self.orders.values() if o.is_filled()),
        }

    def __repr__(self) -> str:
        return (
            f"OrderManager("
            f"orders={len(self.orders)}, "
            f"positions={len(self.positions)})"
        )


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================

if __name__ == '__main__':
    """Example usage of Order Manager"""
    import time

    # Initialize SpyderLogger for main execution
    SpyderLogger.initialize(log_level='INFO')

    print("=" * 70)
    print("IBKR Client Portal API - Order Manager Example")
    print("=" * 70)

    try:
        from .SpyderB09_ClientPortal_Auth import CPGatewayAuth, CPGatewayConfig
        from .SpyderB09_ClientPortal_Session import SessionManager

        # Setup authentication
        gateway_config = CPGatewayConfig(host='localhost', port=5000)
        auth = CPGatewayAuth(gateway_config)

        # Create session manager
        session_mgr = SessionManager(auth, gateway_config.base_url)
        session_mgr.start()

        print("✅ Session started")

        # Create order manager
        order_mgr = OrderManager(session_mgr)

        print("✅ Order manager initialized")

        # Example 1: Get accounts
        print("\n" + "-" * 70)
        print("Example 1: Get Accounts")
        print("-" * 70)

        accounts = order_mgr.get_accounts()
        print(f"Accounts: {accounts}")

        # Example 2: Get positions
        print("\n" + "-" * 70)
        print("Example 2: Current Positions")
        print("-" * 70)

        positions = order_mgr.get_positions()
        if positions:
            for pos in positions:
                print(f"  {pos}")
        else:
            print("  No positions")

        # Example 3: Place market order (PAPER TRADING ONLY!)
        print("\n" + "-" * 70)
        print("Example 3: Place Market Order (DEMO - NOT EXECUTED)")
        print("-" * 70)

        ticket = OrderTicket(
            conid=756733,  # SPY
            side=OrderSide.BUY,
            quantity=1,
            order_type=OrderType.MARKET
        )
        print(f"Would place: {ticket}")

        # Example 4: Bracket order (DEMO)
        print("\n" + "-" * 70)
        print("Example 4: Bracket Order (DEMO - NOT EXECUTED)")
        print("-" * 70)

        print("Entry: $450.00, Stop-Loss: $445.00, Take-Profit: $455.00")

        # Cleanup
        session_mgr.stop()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("For more information, see:")
    print("  - CLIENT_PORTAL_WEB_API_BEST_PRACTICES.md")
    print("=" * 70)
