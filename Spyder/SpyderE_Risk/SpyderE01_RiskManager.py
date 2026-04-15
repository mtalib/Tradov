#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderE_Risk
Module: SpyderE01_RiskManager.py
Purpose: Risk management using Tradier client

Author: SPYDER Trading System
Year Created: 2025
Last Updated: 2026-04-14

Module Description:
    Risk management for the Spyder trading system. Monitors positions,
    exposure, and risk metrics, and enforces risk limits for all trading
    activities. Position and account data are sourced from the Tradier
    client (SpyderB40_TradierClient). Legacy ConnectAPI wiring has been
    removed.

Module Constants:
    RISK_CHECK_INTERVAL (float): Risk check interval in seconds (default: 5.0)
    POSITION_UPDATE_INTERVAL (float): Position update interval in seconds (default: 10.0)
    DEFAULT_RISK_LIMITS (Dict): Default risk limits configuration

Change Log:
    2025-10-20 (v1.0.0):
        - Initial module creation
        - Implemented core risk management functionality
        - Added integration with Connect API
        - Implemented position monitoring and risk calculation

    2025-10-15 (v0.9.0):
        - Beta version for testing
        - Basic risk management structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import threading
import asyncio
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field
from enum import Enum, auto

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from threading import Event as ThreadEvent, RLock

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType

# ConnectAPI: removed with legacy broker (SpyderB01_ConnectAPI deleted).
# Tradier integration uses SpyderB40_TradierClient directly.
ConnectAPI = None

# MessageType enum — defined locally since B01_ConnectAPI was removed.
# Any connect_api passed to RiskManager must use these same enum values as
# handler registration keys, or supply a compatible enum via duck-typing.
from enum import Enum as _Enum, auto as _auto

class MessageType(_Enum):
    POSITION_UPDATE = _auto()
    ACCOUNT_SUMMARY_UPDATE = _auto()
    ORDER_STATUS = _auto()

try:
    from Spyder.SpyderB_Broker.SpyderB02_OrderManager import Order, OrderState
except ImportError:
    Order = None
    OrderState = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
RISK_CHECK_INTERVAL = 5.0  # seconds
POSITION_UPDATE_INTERVAL = 10.0  # seconds

DEFAULT_RISK_LIMITS = {
    'max_position_size': 1000,
    'max_total_exposure': 100000.0,
    'max_daily_loss': 10000.0,
    'max_single_order_size': 500,
    'max_orders_per_minute': 10,
    'max_concentration_ratio': 0.3,  # Max 30% in any single symbol
    'max_options_exposure': 50000.0,
    'max_margin_usage': 0.8  # Max 80% of available margin
}

# ==============================================================================
# ENUMS
# ==============================================================================
class RiskLevel(Enum):
    """Risk levels"""
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()

class RiskCheckResult(Enum):
    """Risk check results"""
    ALLOWED = auto()
    WARNING = auto()
    BLOCKED = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class RiskConfig:
    """Configuration for risk management"""
    risk_limits: dict[str, Any] = field(default_factory=lambda: DEFAULT_RISK_LIMITS.copy())
    enable_real_time_monitoring: bool = True
    risk_check_interval: float = RISK_CHECK_INTERVAL
    position_update_interval: float = POSITION_UPDATE_INTERVAL
    enable_automatic_order_cancellation: bool = False
    notification_threshold: RiskLevel = RiskLevel.HIGH

@dataclass
class Position:
    """Position representation"""
    symbol: str
    quantity: int
    market_price: float
    market_value: float
    average_fill_price: float
    unrealized_pnl: float
    realized_pnl: float
    currency: str = "USD"
    security_type: str = "STK"
    expiry: str | None = None
    strike: float | None = None
    right: str | None = None  # CALL/PUT
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class RiskMetrics:
    """Risk metrics representation"""
    timestamp: datetime
    total_exposure: float
    daily_pnl: float
    net_liquidation: float
    margin_used: float
    margin_available: float
    max_concentration: float
    concentration_symbol: str
    options_exposure: float
    risk_level: RiskLevel
    warnings: list[str] = field(default_factory=list)
    blocked_orders: list[str] = field(default_factory=list)

@dataclass
class RiskProfile:
    """Risk profile for strategy configurations."""
    account_size: float = 100000.0
    max_position_size: float = 0.02
    max_portfolio_risk: float = 0.06
    max_loss_per_trade: float = 0.01

@dataclass
class RiskCheckResponse:
    """Risk check response"""
    result: RiskCheckResult
    order_id: str | None = None
    reason: str | None = None
    risk_metrics: RiskMetrics | None = None
    timestamp: datetime = field(default_factory=datetime.now)

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class RiskManager:
    """
    Risk management using Connect API.

    This class provides risk management functionality using the Connect API.
    It monitors positions, exposure, and risk metrics, and enforces risk limits
    for all trading activities. This module replaces the legacy broker
    risk management components.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling system
        config: Risk management configuration
        connect_api: Connect API instance
        order_manager: Order manager instance
        _positions: Dictionary of current positions
        _risk_metrics: Current risk metrics
        _risk_lock: Thread lock for risk operations
        _shutdown_event: Event for coordinated shutdown
    """

    def __init__(
        self,
        config: RiskConfig,
        connect_api: Any = None,
        order_manager: Any | None = None,
        tradier_client: Any | None = None,
    ):
        """
        Initialize the risk manager.

        Args:
            config: Risk management configuration
            connect_api: Deprecated — legacy ConnectAPI shim, always None
            order_manager: Order manager instance
            tradier_client: Tradier client used for position and account sync
        """
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self._config = config
        self.config = config

        # Broker integration
        self.connect_api = connect_api
        self.tradier_client = tradier_client
        self.order_manager = order_manager

        # Risk management
        self._positions: dict[str, Position] = {}
        self._risk_metrics: RiskMetrics | None = None
        self._risk_lock = RLock()
        self._shutdown_event = ThreadEvent()

        # Monitoring
        self._risk_thread: threading.Thread | None = None
        self._position_thread: threading.Thread | None = None

        # Daily tracking
        self._daily_start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self._daily_start_value = 0.0
        self._daily_high = 0.0
        self._daily_low = float('inf')

        # Market-data staleness gate — set via mark_data_stale(); blocks new trade entries
        self._data_stale: bool = False
        # Tracks which watched symbols are currently stale; gate clears only when all are fresh
        self._stale_symbols: set[str] = set()

        # Subscribe to proactive staleness events from DataValidator (C06)
        _em = get_event_manager()
        _em.subscribe(EventType.DATA_STALE, self._on_data_stale)
        _em.subscribe(EventType.DATA_FRESH, self._on_data_fresh)

        # Metrics
        self.metrics = {
            'risk_checks': 0,
            'warnings': 0,
            'blocks': 0,
            'position_updates': 0,
            'start_time': datetime.now()
        }

        # Register message handlers
        self._register_handlers()

        self.logger.info("RiskManager initialized")

    @property
    def config(self) -> RiskConfig:
        """Primary risk configuration object."""
        return self._config

    @config.setter
    def config(self, value: RiskConfig) -> None:
        self._config = value

    def _register_handlers(self):
        """Register message handlers with the Connect API (no-op when connect_api is None)."""
        if self.connect_api is None:
            self.logger.debug(
                "RiskManager: connect_api is None — skipping handler registration"
            )
            return
        self.connect_api.register_handler(MessageType.POSITION_UPDATE, self._handle_position_update)
        self.connect_api.register_handler(MessageType.ACCOUNT_SUMMARY_UPDATE, self._handle_account_summary_update)

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================

    async def start(self) -> bool:
        """
        Start the risk manager.

        Returns:
            bool: True if start successful
        """
        try:
            self.logger.info("Starting RiskManager...")

            # Connect to Connect API if not already connected
            if self.connect_api is not None:
                if self.connect_api.state != "AUTHENTICATED":
                    if not await self.connect_api.connect():
                        return False
            else:
                self.logger.info(
                    "RiskManager: no connect_api configured — "
                    "running in standalone mode (position sync via ConnectAPI unavailable)"
                )

            # Request initial positions
            await self._request_positions()

            # Request initial account summary
            await self._request_account_summary()

            # Start monitoring threads
            if self.config.enable_real_time_monitoring:
                self._start_risk_monitoring()
                self._start_position_monitoring()

            self.logger.info("RiskManager started successfully")
            return True

        except Exception as e:
            self.logger.error("Failed to start risk manager: %s", e, exc_info=True)
            self.error_handler.handle_error(e, "start")
            return False

    async def stop(self) -> bool:
        """
        Stop the risk manager.

        Returns:
            bool: True if stop successful
        """
        try:
            self.logger.info("Stopping RiskManager...")

            # Signal shutdown
            self._shutdown_event.set()

            # Stop monitoring threads
            self._stop_risk_monitoring()
            self._stop_position_monitoring()

            self.logger.info("RiskManager stopped successfully")
            return True

        except Exception as e:
            self.logger.error("Failed to stop risk manager: %s", e, exc_info=True)
            self.error_handler.handle_error(e, "stop")
            return False

    def initialize(self) -> bool:
        """Legacy synchronous startup hook used by older runtime callers."""
        return True

    # ==========================================================================
    # RISK CHECKING
    # ==========================================================================

    async def check_order_risk(self, order: Order) -> RiskCheckResponse:
        """
        Check if an order is within risk limits.

        Args:
            order: Order to check

        Returns:
            Risk check response

        Note on TOCTOU:
            The entire check is performed inside a single _risk_lock acquisition
            so that position state cannot change mid-check.  However, a window
            still exists between this method returning ALLOWED and the order
            actually reaching the broker.  Callers must re-verify critical limits
            (e.g. daily loss) at submission time using the broker's own risk
            filters, or hold the lock externally across check + submit.
        """
        try:
            with self._risk_lock:
                self.metrics['risk_checks'] += 1

                # Block new entries while upstream market data is stale.
                if self._data_stale:
                    return RiskCheckResponse(
                        result=RiskCheckResult.BLOCKED,
                        order_id=order.order_id,
                        reason="Market data feed is stale; trading disabled until fresh data arrives",
                    )

                # Block naked put orders — unlimited downside risk, prohibited by policy.
                # A naked put is a single-leg sell-to-open put with no protective long leg.
                is_sell_to_open = order.side.lower() in ("sell", "sell_to_open")
                is_put = (order.right or "").lower() in ("put", "p")
                is_single_leg = order.order_class.lower() == "option" and not order.legs
                if is_sell_to_open and is_put and is_single_leg:
                    return RiskCheckResponse(
                        result=RiskCheckResult.BLOCKED,
                        order_id=order.order_id,
                        reason="Naked put orders are prohibited by risk policy; use a defined-risk spread instead",
                    )

                # Get current risk metrics
                risk_metrics = self._calculate_risk_metrics()

                # Check order size
                if order.quantity > self.config.risk_limits['max_single_order_size']:
                    return RiskCheckResponse(
                        result=RiskCheckResult.BLOCKED,
                        order_id=order.order_id,
                        reason=f"Order size {order.quantity} exceeds maximum {self.config.risk_limits['max_single_order_size']}",
                        risk_metrics=risk_metrics
                    )

                # Check position size
                current_position = self._positions.get(order.symbol, Position(
                    symbol=order.symbol,
                    quantity=0,
                    market_price=0.0,
                    market_value=0.0,
                    average_fill_price=0.0,
                    unrealized_pnl=0.0,
                    realized_pnl=0.0
                ))

                # Calculate new position size
                if order.side.lower() in ("buy", "buy_to_open", "buy_to_close"):
                    new_position_size = current_position.quantity + order.quantity
                else:
                    new_position_size = current_position.quantity - order.quantity

                if abs(new_position_size) > self.config.risk_limits['max_position_size']:
                    return RiskCheckResponse(
                        result=RiskCheckResult.BLOCKED,
                        order_id=order.order_id,
                        reason=f"New position size {abs(new_position_size)} exceeds maximum {self.config.risk_limits['max_position_size']}",
                        risk_metrics=risk_metrics
                    )

                # Check total exposure
                order_value = order.quantity * (order.price or current_position.market_price)
                new_total_exposure = risk_metrics.total_exposure + order_value

                if new_total_exposure > self.config.risk_limits['max_total_exposure']:
                    return RiskCheckResponse(
                        result=RiskCheckResult.BLOCKED,
                        order_id=order.order_id,
                        reason=f"New total exposure {new_total_exposure} exceeds maximum {self.config.risk_limits['max_total_exposure']}",
                        risk_metrics=risk_metrics
                    )

                # Check daily loss
                if risk_metrics.daily_pnl < -self.config.risk_limits['max_daily_loss']:
                    return RiskCheckResponse(
                        result=RiskCheckResult.BLOCKED,
                        order_id=order.order_id,
                        reason=f"Daily loss {risk_metrics.daily_pnl} exceeds maximum {self.config.risk_limits['max_daily_loss']}",
                        risk_metrics=risk_metrics
                    )

                # Check concentration
                new_symbol_value = current_position.market_value + order_value
                new_concentration = new_symbol_value / new_total_exposure if new_total_exposure > 0 else 0

                if new_concentration > self.config.risk_limits['max_concentration_ratio']:
                    return RiskCheckResponse(
                        result=RiskCheckResult.WARNING,
                        order_id=order.order_id,
                        reason=f"New concentration {new_concentration:.2%} exceeds maximum {self.config.risk_limits['max_concentration_ratio']:.2%}",
                        risk_metrics=risk_metrics
                    )

                # Check margin usage
                total_margin = risk_metrics.margin_used + risk_metrics.margin_available
                if total_margin > 0 and risk_metrics.margin_used / total_margin > self.config.risk_limits['max_margin_usage']:
                    return RiskCheckResponse(
                        result=RiskCheckResult.WARNING,
                        order_id=order.order_id,
                        reason=f"Margin usage {risk_metrics.margin_used / total_margin:.2%} exceeds maximum {self.config.risk_limits['max_margin_usage']:.2%}",
                        risk_metrics=risk_metrics
                    )

                # Order is allowed
                return RiskCheckResponse(
                    result=RiskCheckResult.ALLOWED,
                    order_id=order.order_id,
                    risk_metrics=risk_metrics
                )

        except Exception as e:
            self.logger.error("Error checking order risk: %s", e, exc_info=True)
            self.error_handler.handle_error(e, "check_order_risk")
            return RiskCheckResponse(
                result=RiskCheckResult.BLOCKED,
                order_id=order.order_id,
                reason=f"Error checking order risk: {str(e)}"
            )

    def mark_data_stale(self, stale: bool) -> None:
        """
        Signal whether the market data feed is currently stale.

        When stale=True all new trade entries are blocked by check_order_risk()
        until this method is called again with stale=False.

        Wire this to SpyderC06_DataValidator's staleness callback so that any
        tick older than the configured threshold (recommend <=5 s) automatically
        disables new entries without manual intervention.

        Args:
            stale: True to block new entries; False to re-enable.
        """
        with self._risk_lock:
            self._data_stale = stale
        if stale:
            self.logger.warning(
                "RiskManager: market data feed marked STALE — all new trade entries BLOCKED"
            )
        else:
            self.logger.info(
                "RiskManager: market data feed marked FRESH — trade entries re-enabled"
            )

    # ==========================================================================
    # DATA STALENESS EVENT HANDLERS (wired by __init__ via EventManager)
    # ==========================================================================

    def _on_data_stale(self, event: Any) -> None:
        """Handle DATA_STALE event emitted by SpyderC06_DataValidator.

        Adds the affected symbol to the stale-symbol set and gates new entries
        the moment any watched symbol goes silent.
        """
        symbol = (event.data or {}).get("symbol", "unknown")
        age = (event.data or {}).get("age_seconds", 0.0)
        with self._risk_lock:
            self._stale_symbols.add(symbol)
        self.mark_data_stale(True)
        self.logger.warning(
            "DATA_STALE received for %s (age=%.1fs) — trade gate CLOSED", symbol, age
        )

    def _on_data_fresh(self, event: Any) -> None:
        """Handle DATA_FRESH event emitted by SpyderC06_DataValidator.

        Removes the symbol from the stale set; clears the gate only once *all*
        previously-stale symbols have recovered (OR logic across watched symbols).
        """
        symbol = (event.data or {}).get("symbol", "unknown")
        with self._risk_lock:
            self._stale_symbols.discard(symbol)
            remaining = set(self._stale_symbols)
        if not remaining:
            self.mark_data_stale(False)
            self.logger.info("DATA_FRESH received for %s — all symbols fresh, gate OPEN", symbol)
        else:
            self.logger.info(
                "DATA_FRESH received for %s — still stale: %s", symbol, sorted(remaining)
            )

    # ==========================================================================
    # POSITION MONITORING
    # ==========================================================================

    def get_positions(self) -> dict[str, Position]:
        """
        Get current positions.

        Returns:
            Dictionary of current positions
        """
        with self._risk_lock:
            return dict(self._positions)

    def get_position(self, symbol: str) -> Position | None:
        """
        Get position for a symbol.

        Returns:
            Position or None if not found
        """
        with self._risk_lock:
            return self._positions.get(symbol)

    def get_risk_metrics(self) -> RiskMetrics | None:
        """
        Get current risk metrics.

        Returns:
            Current risk metrics or None if not available
        """
        with self._risk_lock:
            return self._risk_metrics

    def validate_signal(self, request: Any) -> Any:
        """Satisfies RiskManagerProtocol.validate_signal().

        Maps a RiskValidationRequest from the D↔E series boundary into the
        internal synchronous risk checks and returns a RiskValidationResult.
        All state reads are performed under _risk_lock for TOCTOU safety.

        Args:
            request: RiskValidationRequest from SpyderE00_RiskProtocol.

        Returns:
            RiskValidationResult indicating approval, risk score, and any
            violated rule codes.
        """
        from Spyder.SpyderE_Risk.SpyderE00_RiskProtocol import RiskValidationResult
        try:
            with self._risk_lock:
                # --- Stale data gate ---
                if self._data_stale:
                    return RiskValidationResult(
                        approved=False,
                        rejection_reason="Market data feed is stale; trading disabled until fresh data arrives",
                        risk_score=1.0,
                        violations=["DATA_STALE"],
                    )

                # Block naked puts — strategy_type is carried in metadata.
                strategy_type = (request.metadata or {}).get("strategy_type", "")
                if strategy_type == "naked_put":
                    return RiskValidationResult(
                        approved=False,
                        rejection_reason="Naked put orders are prohibited by risk policy; use a defined-risk spread instead",
                        risk_score=1.0,
                        violations=["NAKED_PUT_PROHIBITED"],
                    )

                risk_metrics = self._calculate_risk_metrics()
                qty = request.quantity
                symbol = request.symbol
                entry_price = float(request.entry_price or 0.0)

                # --- Order size ---
                max_order = self.config.risk_limits["max_single_order_size"]
                if qty > max_order:
                    return RiskValidationResult(
                        approved=False,
                        rejection_reason=f"Quantity {qty} exceeds single-order limit {max_order}",
                        violations=["ORDER_SIZE_EXCEEDED"],
                    )

                # --- Position size ---
                current_pos = self._positions.get(symbol)
                current_qty = current_pos.quantity if current_pos else 0
                new_qty = abs(current_qty + qty)
                max_pos = self.config.risk_limits["max_position_size"]
                if new_qty > max_pos:
                    return RiskValidationResult(
                        approved=False,
                        rejection_reason=f"New position size {new_qty} exceeds limit {max_pos}",
                        violations=["POSITION_SIZE_EXCEEDED"],
                    )

                # --- Total exposure ---
                ref_price = entry_price or (current_pos.market_price if current_pos else 0.0)
                order_value = qty * ref_price
                new_exposure = risk_metrics.total_exposure + order_value
                max_exp = self.config.risk_limits["max_total_exposure"]
                if new_exposure > max_exp:
                    return RiskValidationResult(
                        approved=False,
                        rejection_reason=f"Total exposure {new_exposure:.0f} exceeds limit {max_exp:.0f}",
                        violations=["EXPOSURE_EXCEEDED"],
                    )

                # --- Daily loss ---
                if risk_metrics.daily_pnl < -self.config.risk_limits["max_daily_loss"]:
                    return RiskValidationResult(
                        approved=False,
                        rejection_reason=f"Daily P&L {risk_metrics.daily_pnl:.0f} exceeds max daily loss limit",
                        violations=["DAILY_LOSS_EXCEEDED"],
                    )

                # --- Soft warnings (approved but flagged) ---
                violations: list[str] = []
                new_symbol_value = (current_pos.market_value if current_pos else 0.0) + order_value
                concentration = new_symbol_value / new_exposure if new_exposure > 0 else 0.0
                if concentration > self.config.risk_limits["max_concentration_ratio"]:
                    violations.append("CONCENTRATION_WARNING")

                total_margin = risk_metrics.margin_used + risk_metrics.margin_available
                if total_margin > 0 and (risk_metrics.margin_used / total_margin) > self.config.risk_limits["max_margin_usage"]:
                    violations.append("MARGIN_WARNING")

                risk_score = min(1.0, risk_metrics.total_exposure / max_exp) if max_exp > 0 else 0.0
                return RiskValidationResult(
                    approved=True,
                    risk_score=risk_score,
                    max_safe_quantity=qty,
                    violations=violations,
                )

        except Exception as exc:
            self.logger.error("validate_signal error: %s", exc, exc_info=True)
            return RiskValidationResult(
                approved=False,
                rejection_reason=f"Internal risk check error: {exc}",
                risk_score=1.0,
                violations=["INTERNAL_ERROR"],
            )

    def check_trade(self, trade_request: dict[str, Any]) -> dict[str, Any]:
        """Compatibility adapter for legacy runtime callers.

        Older A/P/Q/K modules still send plain dict payloads via ``check_trade``.
        Map that request onto the typed E00 validation contract.
        """
        from Spyder.SpyderE_Risk.SpyderE00_RiskProtocol import (
            BoundarySignalType,
            RiskValidationRequest,
        )

        action = str(trade_request.get("action", "buy")).lower()
        if action in {"buy", "buy_to_open", "buy_to_close"}:
            signal_type = BoundarySignalType.BUY
        elif action in {"sell", "sell_to_open", "sell_to_close", "sell_short"}:
            signal_type = BoundarySignalType.SELL
        elif action in {"close", "exit"}:
            signal_type = BoundarySignalType.CLOSE
        elif action == "adjust":
            signal_type = BoundarySignalType.ADJUST
        else:
            signal_type = BoundarySignalType.HOLD

        metadata = dict(trade_request.get("metadata") or {})
        if "strategy_id" in trade_request and "strategy_id" not in metadata:
            metadata["strategy_id"] = trade_request["strategy_id"]
        if "type" in trade_request and "security_type" not in metadata:
            metadata["security_type"] = trade_request["type"]
        if "value" in trade_request and "notional_value" not in metadata:
            metadata["notional_value"] = trade_request["value"]

        request = RiskValidationRequest(
            symbol=str(trade_request.get("symbol", "")),
            quantity=int(trade_request.get("quantity", 0) or 0),
            signal_type=signal_type,
            strategy_id=str(trade_request.get("strategy_id", "")),
            entry_price=float(trade_request.get("price") or 0.0),
            metadata=metadata,
        )
        result = self.validate_signal(request)
        return {
            "approved": result.approved,
            "reason": result.rejection_reason,
            "risk_score": result.risk_score,
            "max_safe_quantity": result.max_safe_quantity,
            "violations": list(result.violations),
        }

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================

    async def _request_positions(self):
        """Fetch positions from the Tradier client and push through the handler."""
        if self.tradier_client is None:
            self.logger.debug(
                "RiskManager: tradier_client not configured — skipping position sync"
            )
            return

        try:
            response = await self.tradier_client.get_positions_async()
        except Exception as e:
            self.logger.error("Tradier position fetch failed: %s", e, exc_info=True)
            self.error_handler.handle_error(e, "_request_positions")
            return

        for update in self._iter_tradier_positions(response):
            await self._handle_position_update(update)

        self.logger.debug("Requested position updates via Tradier client")

    async def _request_account_summary(self):
        """Fetch account balances from Tradier and push through the handler."""
        if self.tradier_client is None:
            self.logger.debug(
                "RiskManager: tradier_client not configured — skipping account summary sync"
            )
            return

        try:
            response = await self.tradier_client.get_account_balances_async()
        except Exception as e:
            self.logger.error("Tradier balance fetch failed: %s", e, exc_info=True)
            self.error_handler.handle_error(e, "_request_account_summary")
            return

        balances = (response or {}).get("balances") or {}
        summary = {
            "NetLiquidation": float(balances.get("total_equity", 0.0) or 0.0),
            "TotalCashValue": float(balances.get("total_cash", 0.0) or 0.0),
            "MarginUsed": float(
                (balances.get("margin") or {}).get("option_buying_power", 0.0) or 0.0
            ),
            "MarginAvailable": float(balances.get("option_short_value", 0.0) or 0.0),
        }
        await self._handle_account_summary_update(summary)
        self.logger.debug("Requested account summary via Tradier client")

    @staticmethod
    def _iter_tradier_positions(response: dict[str, Any]):
        """Yield dict updates in the shape _handle_position_update expects."""
        if not response:
            return
        positions_node = response.get("positions")
        if not positions_node or positions_node == "null":
            return
        raw = positions_node.get("position") if isinstance(positions_node, dict) else None
        if raw is None:
            return
        items = raw if isinstance(raw, list) else [raw]
        for item in items:
            try:
                qty = float(item.get("quantity", 0) or 0)
                cost_basis = float(item.get("cost_basis", 0.0) or 0.0)
                avg_cost = cost_basis / qty if qty else 0.0
                yield {
                    "Symbol": item.get("symbol", ""),
                    "Position": int(qty),
                    "MarketPrice": 0.0,
                    "MarketValue": cost_basis,
                    "AverageCost": avg_cost,
                    "UnrealizedPNL": 0.0,
                    "RealizedPNL": 0.0,
                    "Currency": "USD",
                    "SecurityType": "STK",
                }
            except (TypeError, ValueError):
                continue

    async def _handle_position_update(self, data: dict[str, Any]):
        """
        Handle position update message.

        Args:
            data: Position update data
        """
        try:
            symbol = data.get("Symbol", "")
            if not symbol:
                self.logger.warning("Position update missing Symbol")
                return

            # Update position
            with self._risk_lock:
                position = Position(
                    symbol=symbol,
                    quantity=int(data.get("Position", 0)),
                    market_price=float(data.get("MarketPrice", 0.0)),
                    market_value=float(data.get("MarketValue", 0.0)),
                    average_fill_price=float(data.get("AverageCost", 0.0)),
                    unrealized_pnl=float(data.get("UnrealizedPNL", 0.0)),
                    realized_pnl=float(data.get("RealizedPNL", 0.0)),
                    currency=data.get("Currency", "USD"),
                    security_type=data.get("SecurityType", "STK"),
                    expiry=data.get("ExpirationDate"),
                    strike=float(data.get("Strike", 0.0)) if data.get("Strike") else None,
                    right=data.get("Right"),
                    last_updated=datetime.now()
                )

                self._positions[symbol] = position
                self.metrics['position_updates'] += 1

                # Update risk metrics
                self._risk_metrics = self._calculate_risk_metrics()

                # Log position update
                self.logger.debug("Position updated: %s - %s @ %s", symbol, position.quantity, position.market_price)

        except Exception as e:
            self.logger.error("Error handling position update: %s", e, exc_info=True)
            self.error_handler.handle_error(e, "_handle_position_update")

    async def _handle_account_summary_update(self, data: dict[str, Any]):
        """
        Handle account summary update message.

        Args:
            data: Account summary data
        """
        try:
            # Update account summary
            with self._risk_lock:
                # Update risk metrics
                self._risk_metrics = self._calculate_risk_metrics()

                # Log account summary update
                self.logger.debug("Account summary updated")

        except Exception as e:
            self.logger.error("Error handling account summary update: %s", e, exc_info=True)
            self.error_handler.handle_error(e, "_handle_account_summary_update")

    def _calculate_risk_metrics(self) -> RiskMetrics:
        """
        Calculate current risk metrics.

        Returns:
            Current risk metrics
        """
        try:
            # Calculate total exposure
            total_exposure = sum(abs(pos.market_value) for pos in self._positions.values())

            # Calculate daily PnL
            daily_pnl = sum(pos.unrealized_pnl + pos.realized_pnl for pos in self._positions.values())

            # Calculate concentration
            max_concentration = 0.0
            concentration_symbol = ""

            if total_exposure > 0:
                for symbol, position in self._positions.items():
                    concentration = abs(position.market_value) / total_exposure
                    if concentration > max_concentration:
                        max_concentration = concentration
                        concentration_symbol = symbol

            # Calculate options exposure
            options_exposure = sum(
                abs(pos.market_value) for pos in self._positions.values()
                if pos.security_type == "OPT"
            )

            # Determine risk level
            risk_level = RiskLevel.LOW
            warnings = []
            blocked_orders = []

            # Check daily loss
            if daily_pnl < -self.config.risk_limits['max_daily_loss']:
                risk_level = RiskLevel.CRITICAL
                warnings.append(f"Daily loss {daily_pnl} exceeds maximum {self.config.risk_limits['max_daily_loss']}")

            # Check total exposure
            if total_exposure > self.config.risk_limits['max_total_exposure']:
                risk_level = RiskLevel.HIGH
                warnings.append(f"Total exposure {total_exposure} exceeds maximum {self.config.risk_limits['max_total_exposure']}")

            # Check concentration
            if max_concentration > self.config.risk_limits['max_concentration_ratio']:
                if risk_level.value < RiskLevel.MEDIUM.value:
                    risk_level = RiskLevel.MEDIUM
                warnings.append(f"Concentration {max_concentration:.2%} in {concentration_symbol} exceeds maximum {self.config.risk_limits['max_concentration_ratio']:.2%}")

            # Check options exposure
            if options_exposure > self.config.risk_limits['max_options_exposure']:
                if risk_level.value < RiskLevel.MEDIUM.value:
                    risk_level = RiskLevel.MEDIUM
                warnings.append(f"Options exposure {options_exposure} exceeds maximum {self.config.risk_limits['max_options_exposure']}")

            # Get account data from AccountManager if available
            net_liq = 0.0
            margin_used_val = 0.0
            margin_avail = 0.0

            try:
                # Import AccountManager and get account data
                from Spyder.SpyderB_Broker.SpyderB04_AccountManager import AccountManager
                account_mgr = AccountManager.get_instance()
                if account_mgr:
                    net_liq = account_mgr.get_net_liquidation()
                    # Get margin from account info
                    account_info = account_mgr.get_account_info()
                    if account_info:
                        margin_used_val = getattr(account_info, 'margin_used', 0.0)
                        margin_avail = getattr(account_info, 'margin_available', 0.0)
            except (ImportError, AttributeError) as e:
                self.logger.debug("Could not retrieve account data: %s", e)

            # Create risk metrics
            risk_metrics = RiskMetrics(
                timestamp=datetime.now(),
                total_exposure=total_exposure,
                daily_pnl=daily_pnl,
                net_liquidation=net_liq,
                margin_used=margin_used_val,
                margin_available=margin_avail,
                max_concentration=max_concentration,
                concentration_symbol=concentration_symbol,
                options_exposure=options_exposure,
                risk_level=risk_level,
                warnings=warnings,
                blocked_orders=blocked_orders
            )

            return risk_metrics

        except Exception as e:
            self.logger.error("Error calculating risk metrics: %s", e, exc_info=True)
            self.error_handler.handle_error(e, "_calculate_risk_metrics")

            # Return default risk metrics
            return RiskMetrics(
                timestamp=datetime.now(),
                total_exposure=0.0,
                daily_pnl=0.0,
                net_liquidation=0.0,
                margin_used=0.0,
                margin_available=0.0,
                max_concentration=0.0,
                concentration_symbol="",
                options_exposure=0.0,
                risk_level=RiskLevel.LOW,
                warnings=[f"Error calculating risk metrics: {str(e)}"],
                blocked_orders=[]
            )


def get_risk_manager(
    portfolio_value: float | None = None,
    config: dict[str, Any] | None = None,
    connect_api: Any | None = None,
    order_manager: Any | None = None,
    tradier_client: Any | None = None,
) -> RiskManager:
    """Legacy factory retained for older runtime modules.

    The current E01 constructor is explicit, but several production callers
    still expect a factory-style entry point.
    """
    risk_limits = DEFAULT_RISK_LIMITS.copy()
    if portfolio_value is not None:
        risk_limits["max_total_exposure"] = max(
            risk_limits["max_total_exposure"],
            float(portfolio_value),
        )

    raw_config = dict(config or {})
    risk_limits.update(raw_config.get("risk_limits") or {})

    risk_config = RiskConfig(
        risk_limits=risk_limits,
        enable_real_time_monitoring=bool(raw_config.get("enable_real_time_monitoring", True)),
        risk_check_interval=float(raw_config.get("risk_check_interval", RISK_CHECK_INTERVAL)),
        position_update_interval=float(
            raw_config.get("position_update_interval", POSITION_UPDATE_INTERVAL)
        ),
        enable_automatic_order_cancellation=bool(
            raw_config.get("enable_automatic_order_cancellation", False)
        ),
    )
    return RiskManager(
        config=risk_config,
        connect_api=connect_api,
        order_manager=order_manager,
        tradier_client=tradier_client,
    )

    def _start_risk_monitoring(self):
        """Start risk monitoring thread"""
        if not self._risk_thread:
            self._risk_thread = threading.Thread(
                target=self._risk_monitoring_loop,
                daemon=True,
                name="RiskMonitoring"
            )
            self._risk_thread.start()
            self.logger.info("Risk monitoring started")

    def _stop_risk_monitoring(self):
        """Stop risk monitoring thread"""
        if self._risk_thread:
            self._risk_thread.join(timeout=5.0)
            self._risk_thread = None
            self.logger.info("Risk monitoring stopped")

    def _risk_monitoring_loop(self):
        """Risk monitoring loop"""
        while not self._shutdown_event.is_set():
            try:
                # Update risk metrics
                with self._risk_lock:
                    self._risk_metrics = self._calculate_risk_metrics()

                # Check if risk level exceeds notification threshold
                if self._risk_metrics and self._risk_metrics.risk_level.value >= self.config.notification_threshold.value:
                    self.logger.warning("Risk level %s exceeded threshold", self._risk_metrics.risk_level.name)

                    # Send notifications
                    self._send_risk_notifications(self._risk_metrics)

                # Wait for next check
                self._shutdown_event.wait(self.config.risk_check_interval)

            except Exception as e:
                self.logger.error("Error in risk monitoring loop: %s", e, exc_info=True)
                self.error_handler.handle_error(e, "_risk_monitoring_loop")
                self._shutdown_event.wait(1.0)  # Wait before retry

    def _start_position_monitoring(self):
        """Start position monitoring thread"""
        if not self._position_thread:
            self._position_thread = threading.Thread(
                target=self._position_monitoring_loop,
                daemon=True,
                name="PositionMonitoring"
            )
            self._position_thread.start()
            self.logger.info("Position monitoring started")

    def _stop_position_monitoring(self):
        """Stop position monitoring thread"""
        if self._position_thread:
            self._position_thread.join(timeout=5.0)
            self._position_thread = None
            self.logger.info("Position monitoring stopped")

    def _position_monitoring_loop(self):
        """Position monitoring loop"""
        while not self._shutdown_event.is_set():
            try:
                # Request position updates
                asyncio.create_task(self._request_positions())

                # Wait for next update
                self._shutdown_event.wait(self.config.position_update_interval)

            except Exception as e:
                self.logger.error("Error in position monitoring loop: %s", e, exc_info=True)
                self.error_handler.handle_error(e, "_position_monitoring_loop")
                self._shutdown_event.wait(1.0)  # Wait before retry

    def _send_risk_notifications(self, risk_metrics: RiskMetrics):
        """
        Send risk notifications.

        Args:
            risk_metrics: Risk metrics
        """
        try:
            # Log warnings
            for warning in risk_metrics.warnings:
                self.logger.warning("Risk warning: %s", warning)

            # Send structured notifications when breach threshold is met
            if risk_metrics.risk_level.value >= self.config.notification_threshold.value:
                breach_details = {
                    'severity': risk_metrics.risk_level.name,
                    'timestamp': risk_metrics.timestamp.isoformat(),
                    'total_exposure': risk_metrics.total_exposure,
                    'daily_pnl': risk_metrics.daily_pnl,
                    'options_exposure': risk_metrics.options_exposure,
                    'margin_used': risk_metrics.margin_used,
                    'warnings': risk_metrics.warnings,
                    'blocked_orders': risk_metrics.blocked_orders,
                }

                # Attempt AlertManager notification (email/SMS/Telegram channels)
                try:
                    from Spyder.SpyderJ_Alerts.SpyderJ01_AlertManager import AlertManager
                    alert_manager = AlertManager()
                    alert_message = (
                        f"RISK BREACH [{risk_metrics.risk_level.name}] "
                        f"at {risk_metrics.timestamp.strftime('%Y-%m-%d %H:%M:%S')} | "
                        f"Exposure: {risk_metrics.total_exposure:,.2f} | "
                        f"Daily PnL: {risk_metrics.daily_pnl:,.2f} | "
                        f"Warnings: {'; '.join(risk_metrics.warnings)}"
                    )
                    alert_manager.generate_predictive_alerts({
                        'alert_type': 'risk_breach',
                        'message': alert_message,
                        'severity': risk_metrics.risk_level.name,
                        'breach_details': breach_details,
                    })
                    self.logger.info(
                        f"Risk breach notification dispatched via AlertManager: "
                        f"level={risk_metrics.risk_level.name}"
                    )
                except Exception as alert_exc:
                    # AlertManager unavailable — emit structured WARNING with full breach context
                    self.logger.warning(
                        "RISK_BREACH | severity=%(severity)s | "
                        "timestamp=%(timestamp)s | "
                        "total_exposure=%(total_exposure).2f | "
                        "daily_pnl=%(daily_pnl).2f | "
                        "options_exposure=%(options_exposure).2f | "
                        "margin_used=%(margin_used).2f | "
                        "warnings=%(warnings)s",
                        breach_details,
                    )
                    self.logger.debug(
                        "AlertManager unavailable for risk breach notification: %s", alert_exc
                    )

        except Exception as e:
            self.logger.error("Error sending risk notifications: %s", e, exc_info=True)
            self.error_handler.handle_error(e, "_send_risk_notifications")

    # ==========================================================================
    # PUBLIC UTILITY METHODS
    # ==========================================================================

    def get_status(self) -> dict[str, Any]:
        """
        Get current risk manager status.

        Returns:
            Dictionary containing status information
        """
        with self._risk_lock:
            # Calculate uptime
            uptime = datetime.now() - self.metrics['start_time']

            # Get risk metrics
            risk_metrics = self._risk_metrics

            return {
                'monitoring_enabled': self.config.enable_real_time_monitoring,
                'risk_level': risk_metrics.risk_level.name if risk_metrics else None,
                'total_exposure': risk_metrics.total_exposure if risk_metrics else 0.0,
                'daily_pnl': risk_metrics.daily_pnl if risk_metrics else 0.0,
                'positions_count': len(self._positions),
                'warnings_count': len(risk_metrics.warnings) if risk_metrics else 0,
                'blocked_orders_count': len(risk_metrics.blocked_orders) if risk_metrics else 0,
                'risk_checks': self.metrics['risk_checks'],
                'warnings': self.metrics['warnings'],
                'blocks': self.metrics['blocks'],
                'position_updates': self.metrics['position_updates'],
                'uptime_seconds': uptime.total_seconds(),
                'start_time': self.metrics['start_time'].isoformat()
            }

    def get_metrics(self) -> dict[str, Any]:
        """
        Get risk manager metrics.

        Returns:
            Dictionary containing metrics
        """
        with self._risk_lock:
            # Calculate uptime
            uptime = datetime.now() - self.metrics['start_time']

            # Calculate check rate
            check_rate = 0.0
            if uptime.total_seconds() > 0:
                check_rate = self.metrics['risk_checks'] / uptime.total_seconds()

            return {
                'risk_checks': self.metrics['risk_checks'],
                'warnings': self.metrics['warnings'],
                'blocks': self.metrics['blocks'],
                'position_updates': self.metrics['position_updates'],
                'check_rate': check_rate,
                'uptime_seconds': uptime.total_seconds(),
                'start_time': self.metrics['start_time'].isoformat()
            }


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_risk_manager(
    config: RiskConfig,
    connect_api: Any = None,
    order_manager: Any | None = None,
    tradier_client: Any | None = None,
) -> RiskManager:
    """
    Factory function to create a risk manager instance.

    Args:
        config: Risk management configuration
        connect_api: Deprecated legacy param, kept for positional compatibility
        order_manager: Order manager instance
        tradier_client: Tradier client for position/account sync

    Returns:
        RiskManager instance
    """
    return RiskManager(
        config,
        connect_api=connect_api,
        order_manager=order_manager,
        tradier_client=tradier_client,
    )


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code

    # This would require actual Connect API to test

    pass
