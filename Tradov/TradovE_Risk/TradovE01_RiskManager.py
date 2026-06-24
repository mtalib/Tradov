#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovE_Risk
Module: TradovE01_RiskManager.py
Purpose: Risk management using Tradier client

Author: TRADOV Trading System
Year Created: 2025
Last Updated: 2026-04-14

Module Description:
    Risk management for the Tradov trading system. Monitors positions,
    exposure, and risk metrics, and enforces risk limits for all trading
    activities. Position and account data are sourced from the Tradier
    client (TradovB40_TradierClient). Legacy ConnectAPI wiring has been
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
import os  # noqa: F401
import threading
import asyncio
from datetime import UTC, datetime
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
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler
from Tradov.TradovU_Utilities.TradovU03_DateTimeUtils import now_et  # P2-5: tz-aware ET timestamps
from Tradov.TradovA_Core.TradovA05_EventManager import get_event_manager, EventType
from Tradov.TradovE_Risk.TradovE00_RiskProtocol import (
    OverlayPretradeVerdict,
    RiskValidationRequest,
    RiskValidationResult,
)

# ConnectAPI: removed with legacy broker (TradovB01_ConnectAPI deleted).
# Tradier integration uses TradovB40_TradierClient directly.
ConnectAPI = None

# MessageType enum — defined locally since B01_ConnectAPI was removed.
# Any connect_api passed to RiskManager must use these same enum values as
# handler registration keys, or supply a compatible enum via duck-typing.
from enum import Enum as _Enum, auto as _auto  # noqa: E402

class MessageType(_Enum):
    POSITION_UPDATE = _auto()
    ACCOUNT_SUMMARY_UPDATE = _auto()
    ORDER_STATUS = _auto()

try:
    from Tradov.TradovB_Broker.TradovB02_OrderManager import Order, OrderState
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
    'max_margin_usage': 0.8,  # Max 80% of available margin
    'overlay_max_daily_risk_used_fraction': 0.60,
    'overlay_max_expected_slippage_bps': 25.0,
    'overlay_max_projected_delta': 0.10,
    'overlay_max_projected_gamma': 0.02,
    'overlay_max_projected_vega': 0.10,
    'overlay_max_projected_theta': 0.10,
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
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

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
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

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
        self.logger = TradovLogger.get_logger(self.__class__.__name__)
        self.error_handler = TradovErrorHandler()

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
        # P1-2: cold-start guard. Signals are rejected until at least one
        # account summary sync succeeds, preventing blind trading on empty state.
        self._account_state_synced: bool = False

        # Monitoring
        self._risk_thread: threading.Thread | None = None
        self._position_thread: threading.Thread | None = None

        # Daily tracking
        self._daily_start_time = now_et().replace(hour=0, minute=0, second=0, microsecond=0)
        self._daily_start_value = 0.0
        self._daily_high = 0.0
        self._daily_low = float('inf')

        # Market-data staleness gate — set via mark_data_stale(); blocks new trade entries
        self._data_stale: bool = False
        # Tracks which watched symbols are currently stale; gate clears only when all are fresh
        self._stale_symbols: set[str] = set()
        # P2-2: when staleness began; used to trigger FLATTEN_REQUEST after timeout
        self._stale_since: datetime | None = None
        self._stale_flatten_emitted: bool = False
        self._stale_flatten_timeout_s: float = 300.0  # 5 minutes

        # Y03 RiskSentinelAgent veto state — updated via wire_agent_bus().
        # Values mirror CircuitBreakerState: "normal" | "caution" | "warning" | "halt"
        self._y03_veto_state: str = "normal"
        self._observe_only_agents: bool = self._resolve_observe_only_agents()

        # Stage 3: decision-quality SLO gate (vol-surface / dealer-flow / lead-lag).
        # When True, validate_signal() rejects entries if S07 reports absent or
        # low-confidence data for the three required quality buckets.
        self._enforce_decision_quality_slo: bool = True

        # Subscribe to proactive staleness events from DataValidator (C06)
        _em = get_event_manager()
        _em.subscribe(EventType.DATA_STALE, self._on_data_stale)
        _em.subscribe(EventType.DATA_FRESH, self._on_data_fresh)

        # Subscribe to fill-driven position updates from PositionTracker (S-06)
        _em.subscribe(EventType.POSITION_UPDATED, self._on_position_updated)

        # Metrics
        self.metrics = {
            'risk_checks': 0,
            'warnings': 0,
            'blocks': 0,
            'position_updates': 0,
            'start_time': now_et()
        }

        # Cached account balances from last successful Tradier sync.
        # Keys match _request_account_summary summary dict.
        self._cached_account_balances: dict[str, float] = {}

        # Register message handlers
        self._register_handlers()

        # A24 (v14): A03 hot-reload subscriber so operator-adjusted risk
        # limits take effect without a restart. Structural identity fields
        # are refused to prevent mid-session account/env swaps.
        self._register_hot_reload_callback()

        self.logger.debug("RiskManager initialized")

    _STRUCTURAL_CONFIG_FIELDS: frozenset = frozenset({"account_id", "env", "environment"})

    def _resolve_observe_only_agents(self) -> bool:
        """Resolve whether agent vetoes should be telemetry-only by default."""
        env_value = os.getenv("TRADOV_OBSERVE_ONLY_AGENTS")
        if env_value is not None:
            normalized = env_value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False

        readiness_cfg = self._config.get("autonomous_readiness", {}) if isinstance(self._config, dict) else {}
        configured = readiness_cfg.get("observe_only_agents") if isinstance(readiness_cfg, dict) else None
        if isinstance(configured, bool):
            return configured
        return True

    def wire_agent_bus(self, bus: Any) -> None:
        """Subscribe to Y03 RiskSentinelAgent circuit-breaker veto signals.

        Call this once after construction (e.g. from A02 TradingEngine after
        get_risk_manager()) to connect the live Y03 veto channel.

        Args:
            bus: AgentMessageBus instance (TradovI06_AgentMessageBus).
        """
        try:
            bus.subscribe(
                subscriber_id="E01_RiskManager",
                topics=["risk.circuit_breaker"],
                callback=self._on_y03_circuit_breaker,
                name="E01 Risk Manager",
            )
            self.logger.info("E01 subscribed to Y03 risk.circuit_breaker veto channel")
        except Exception as exc:
            self.logger.warning("Could not subscribe to agent bus: %s", exc)

    def _on_y03_circuit_breaker(self, message: Any) -> None:
        """Handle a Y03 RiskSentinelAgent circuit-breaker state change.

        Args:
            message: AgentOutput or dict with a ``circuit_breaker`` key whose
                value is one of: ``"normal"``, ``"caution"``, ``"warning"``,
                ``"halt"``.
        """
        try:
            content = message if isinstance(message, dict) else getattr(message, "content", message)
            if isinstance(content, dict):
                state = content.get("circuit_breaker", "normal")
            else:
                state = str(content)
            self._y03_veto_state = state
            if state in ("warning", "halt"):
                self.logger.warning("Y03 RiskSentinel veto active: circuit_breaker=%s", state)
            else:
                self.logger.info("Y03 RiskSentinel veto cleared: circuit_breaker=%s", state)
        except Exception as exc:
            self.logger.error("Error processing Y03 circuit-breaker message: %s", exc)

    def _register_hot_reload_callback(self) -> None:
        try:
            from Tradov.TradovA_Core.TradovA03_Configuration import (
                get_config_manager,
            )
            cfg_mgr = get_config_manager()
            if cfg_mgr is not None:
                cfg_mgr.register_callback("risk_limits.*", self._on_config_reload)
                cfg_mgr.register_callback("risk.*", self._on_config_reload)
                self.logger.debug("E01: registered A03 hot-reload callback")
        except Exception as exc:
            # B13 (v15): log at ERROR so silent failure of callback registration
            # is visible in production logs. Hot-reload of risk limits will be
            # silently disabled until the system is restarted.
            self.logger.error(
                "E01: config reload callbacks not registered — hot-reload DISABLED: %s", exc
            )

    def _on_config_reload(self, key: str, old_value: Any, new_value: Any) -> None:
        """A24 (v14): apply a risk-limit change; refuse structural fields."""
        if any(key.endswith(f) for f in self._STRUCTURAL_CONFIG_FIELDS):
            self.logger.error(
                "E01: refusing hot-reload of structural field %s "
                "(old=%s new=%s) — restart required",
                key, old_value, new_value,
            )
            return
        self.logger.info(
            "E01: config hot-reload %s: %s -> %s", key, old_value, new_value
        )
        # Apply onto self.config.risk_limits — keyed by the last path segment.
        leaf = key.rsplit(".", 1)[-1]
        try:
            if (
                hasattr(self.config, "risk_limits")
                and isinstance(self.config.risk_limits, dict)
                and leaf in self.config.risk_limits
            ):
                with self._risk_lock:
                    self.config.risk_limits[leaf] = new_value
        except Exception as exc:
            self.logger.error("E01: failed to apply reload for %s: %s", key, exc)

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
        self.connect_api.register_handler(MessageType.ACCOUNT_SUMMARY_UPDATE, self._handle_account_summary_update)  # noqa: E501

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================

    def mark_account_synced(self) -> None:
        """Force-mark account state as synced.

        Call this from paper/test harnesses after ``start()`` when the broker
        does not support a real balance fetch and the cold-start gate would
        otherwise block all signals indefinitely.
        """
        with self._risk_lock:
            self._account_state_synced = True
        self.logger.debug("RiskManager: account state force-synced (paper/test mode)")

    async def start(self) -> bool:
        """
        Start the risk manager.

        Returns:
            bool: True if start successful
        """
        try:
            self.logger.debug("Starting RiskManager...")

            # Connect to Connect API if not already connected
            if self.connect_api is not None:
                if self.connect_api.state != "AUTHENTICATED":
                    if not await self.connect_api.connect():
                        return False
            else:
                self.logger.debug(
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

            self.logger.debug("RiskManager started successfully")
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

    def stop_sync(self) -> None:
        """Synchronous stop adapter for SessionSupervisor component loop.

        Signals shutdown and joins the monitoring threads without requiring an
        async event loop.  This prevents the position-monitoring daemon thread
        from outliving the interpreter and triggering
        ``cannot schedule new futures after interpreter shutdown``.

        Also serves as the no-arg ``stop()`` alias used by the component loop
        (see ``stop`` property below).
        """
        try:
            self.logger.info("Stopping RiskManager (sync)...")
            self._shutdown_event.set()
            self._stop_risk_monitoring()
            self._stop_position_monitoring()
            self.logger.info("RiskManager stopped (sync)")
        except Exception as e:
            self.logger.error("RiskManager stop_sync error: %s", e)

    def _start_risk_monitoring(self):
        """Start risk monitoring thread."""
        if not self._risk_thread:
            self._risk_thread = threading.Thread(
                target=self._risk_monitoring_loop,
                daemon=True,
                name="RiskMonitoring"
            )
            self._risk_thread.start()
            self.logger.debug("Risk monitoring started")

    def _stop_risk_monitoring(self):
        """Stop risk monitoring thread."""
        if self._risk_thread:
            self._risk_thread.join(timeout=5.0)
            self._risk_thread = None
            self.logger.info("Risk monitoring stopped")

    def _risk_monitoring_loop(self):
        """Risk monitoring loop."""
        while not self._shutdown_event.is_set():
            try:
                # Update risk metrics.
                with self._risk_lock:
                    self._risk_metrics = self._calculate_risk_metrics()

                # Check if risk level exceeds notification threshold.
                if self._risk_metrics and self._risk_metrics.risk_level.value >= self.config.notification_threshold.value:  # noqa: E501
                    self.logger.warning("Risk level %s exceeded threshold", self._risk_metrics.risk_level.name)  # noqa: E501
                    self._send_risk_notifications(self._risk_metrics)

                # Emit FLATTEN_REQUEST if data has been stale beyond timeout.
                stale_since = self._stale_since
                if (
                    stale_since is not None
                    and not self._stale_flatten_emitted
                    and (now_et() - stale_since).total_seconds() >= self._stale_flatten_timeout_s
                ):
                    self._stale_flatten_emitted = True
                    elapsed = (now_et() - stale_since).total_seconds()
                    self.logger.critical(
                        "RiskManager: data stale for %.0fs (threshold %.0fs) — emitting FLATTEN_REQUEST",  # noqa: E501
                        elapsed, self._stale_flatten_timeout_s,
                    )
                    try:
                        _em = get_event_manager()
                        _em.emit(
                            EventType.FLATTEN_REQUEST,
                            {
                                "reason": "data_stale",
                                "stale_seconds": elapsed,
                                "symbols": sorted(self._stale_symbols),
                            },
                        )
                    except Exception as _fe:
                        self.logger.error("Failed to emit FLATTEN_REQUEST: %s", _fe)

                # Wait for next check.
                self._shutdown_event.wait(self.config.risk_check_interval)

            except Exception as e:
                self.logger.error("Error in risk monitoring loop: %s", e, exc_info=True)
                self.error_handler.handle_error(e, "_risk_monitoring_loop")
                self._shutdown_event.wait(1.0)  # Wait before retry.

    def _start_position_monitoring(self):
        """Start position monitoring thread."""
        if not self._position_thread:
            self._position_thread = threading.Thread(
                target=self._position_monitoring_loop,
                daemon=True,
                name="PositionMonitoring"
            )
            self._position_thread.start()
            self.logger.debug("Position monitoring started")

    def _stop_position_monitoring(self):
        """Stop position monitoring thread."""
        if self._position_thread:
            self._position_thread.join(timeout=5.0)
            self._position_thread = None
            self.logger.info("Position monitoring stopped")

    def _position_monitoring_loop(self):
        """Position monitoring loop.

        v27 SPEC-15: hold a single persistent event loop for the lifetime of
        the thread instead of asyncio.run() per cycle. The previous pattern
        created and destroyed an event loop every 30s, breaking any client
        that caches a loop (Tradier websocket, aiohttp sessions).
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Request position updates on the persistent loop.
                    loop.run_until_complete(self._request_positions())

                    # Wait for next update.
                    self._shutdown_event.wait(self.config.position_update_interval)

                except Exception as e:
                    self.logger.error("Error in position monitoring loop: %s", e, exc_info=True)
                    self.error_handler.handle_error(e, "_position_monitoring_loop")
                    self._shutdown_event.wait(1.0)  # Wait before retry.
        finally:
            try:
                loop.close()
            except Exception:
                pass

    def _send_risk_notifications(self, risk_metrics: RiskMetrics):
        """
        Send risk notifications.

        Args:
            risk_metrics: Risk metrics
        """
        try:
            # Log warnings.
            for warning in risk_metrics.warnings:
                self.logger.warning("Risk warning: %s", warning)

            # Send structured notifications when breach threshold is met.
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

                # Attempt AlertManager notification (email/SMS/Telegram channels).
                try:
                    from Tradov.TradovJ_Alerts.TradovJ01_AlertManager import AlertManager
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
                except Exception as notify_exc:
                    self.logger.warning(
                        "AlertManager notification failed (continuing): %s", notify_exc
                    )

        except Exception as exc:
            self.logger.error("Failed to send risk notifications: %s", exc, exc_info=True)

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
                        reason="Market data feed is stale; trading disabled until fresh data arrives",  # noqa: E501
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
                        reason="Naked put orders are prohibited by risk policy; use a defined-risk spread instead",  # noqa: E501
                    )

                # Get current risk metrics
                risk_metrics = self._calculate_risk_metrics()

                # Check order size
                if order.quantity > self.config.risk_limits['max_single_order_size']:
                    return RiskCheckResponse(
                        result=RiskCheckResult.BLOCKED,
                        order_id=order.order_id,
                        reason=f"Order size {order.quantity} exceeds maximum {self.config.risk_limits['max_single_order_size']}",  # noqa: E501
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
                        reason=f"New position size {abs(new_position_size)} exceeds maximum {self.config.risk_limits['max_position_size']}",  # noqa: E501
                        risk_metrics=risk_metrics
                    )

                # Check total exposure
                order_value = order.quantity * (order.price or current_position.market_price)
                new_total_exposure = risk_metrics.total_exposure + order_value

                if new_total_exposure > self.config.risk_limits['max_total_exposure']:
                    return RiskCheckResponse(
                        result=RiskCheckResult.BLOCKED,
                        order_id=order.order_id,
                        reason=f"New total exposure {new_total_exposure} exceeds maximum {self.config.risk_limits['max_total_exposure']}",  # noqa: E501
                        risk_metrics=risk_metrics
                    )

                # Check daily loss
                if risk_metrics.daily_pnl < -self.config.risk_limits['max_daily_loss']:
                    return RiskCheckResponse(
                        result=RiskCheckResult.BLOCKED,
                        order_id=order.order_id,
                        reason=f"Daily loss {risk_metrics.daily_pnl} exceeds maximum {self.config.risk_limits['max_daily_loss']}",  # noqa: E501
                        risk_metrics=risk_metrics
                    )

                # Check concentration
                new_symbol_value = current_position.market_value + order_value
                new_concentration = new_symbol_value / new_total_exposure if new_total_exposure > 0 else 0  # noqa: E501

                if new_concentration > self.config.risk_limits['max_concentration_ratio']:
                    return RiskCheckResponse(
                        result=RiskCheckResult.WARNING,
                        order_id=order.order_id,
                        reason=f"New concentration {new_concentration:.2%} exceeds maximum {self.config.risk_limits['max_concentration_ratio']:.2%}",  # noqa: E501
                        risk_metrics=risk_metrics
                    )

                # Check margin usage
                total_margin = risk_metrics.margin_used + risk_metrics.margin_available
                if total_margin > 0 and risk_metrics.margin_used / total_margin > self.config.risk_limits['max_margin_usage']:  # noqa: E501
                    return RiskCheckResponse(
                        result=RiskCheckResult.WARNING,
                        order_id=order.order_id,
                        reason=f"Margin usage {risk_metrics.margin_used / total_margin:.2%} exceeds maximum {self.config.risk_limits['max_margin_usage']:.2%}",  # noqa: E501
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

    # ------------------------------------------------------------------
    # Stage 3: decision-quality SLO gate
    # ------------------------------------------------------------------

    def _check_decision_quality_slo(self) -> tuple[bool, str, list[str]]:
        """Check vol-surface and dealer-flow SLOs via S07.

        Called from validate_signal() as a risk-layer defense-in-depth gate
        (the primary enforcement point is the D31/F09 entry trust gate).

        Returns:
            Tuple of (approved, rejection_reason, violations).
            Fails open when S07 is unavailable so the system can still
            function in paper/backtest contexts where S07 is not started.
        """
        try:
            from Tradov.TradovS_Signals.TradovS07_CustomMetricsOrchestrator import (
                get_metrics_orchestrator,
            )
        except ImportError:
            try:
                from TradovS_Signals.TradovS07_CustomMetricsOrchestrator import (  # type: ignore[no-redef]
                    get_metrics_orchestrator,
                )
            except ImportError:
                return True, "", []

        try:
            conditions = get_metrics_orchestrator().get_current_market_conditions()
        except Exception as exc:
            self.logger.debug("E01 SLO: S07 unreachable (%s) — gate passes", exc)
            return True, "", []

        def _absent(v: Any) -> bool:
            return v is None or (isinstance(v, float) and v != v)

        failures: list[str] = []

        # Vol-surface: confidence must be present and above floor
        # (mirrors F09 market_structure_policy min_surface_confidence=0.55)
        surface_confidence = conditions.get("surface_confidence")
        if _absent(surface_confidence):
            failures.append("vol_surface_absent")
        elif float(surface_confidence) < 0.55:
            failures.append(f"vol_surface_confidence_low({float(surface_confidence):.2f})")

        # Dealer-flow: wall confidence must be present and above floor
        # (mirrors F09 market_structure_policy min_wall_confidence=0.55)
        wall_confidence = conditions.get("wall_confidence")
        if _absent(wall_confidence):
            failures.append("dealer_flow_absent")
        elif float(wall_confidence) < 0.55:
            failures.append(f"dealer_flow_confidence_low({float(wall_confidence):.2f})")

        if not failures:
            return True, "", []

        return (
            False,
            f"Decision-quality SLO gate failed: {', '.join(failures)}",
            ["DECISION_QUALITY_SLO_FAILED"],
        )

    def mark_data_stale(self, stale: bool) -> None:
        """
        Signal whether the market data feed is currently stale.

        When stale=True all new trade entries are blocked by check_order_risk()
        until this method is called again with stale=False.

        Wire this to TradovC06_DataValidator's staleness callback so that any
        tick older than the configured threshold (recommend <=5 s) automatically
        disables new entries without manual intervention.

        Args:
            stale: True to block new entries; False to re-enable.
        """
        with self._risk_lock:
            self._data_stale = stale
        if stale:
            # P2-2: record when staleness began (only on first transition to stale)
            if self._stale_since is None:
                self._stale_since = now_et()
            self.logger.warning(
                "RiskManager: market data feed marked STALE — all new trade entries BLOCKED"
            )
        else:
            # P2-2: cleared — reset timer and flatten-emitted flag
            self._stale_since = None
            self._stale_flatten_emitted = False
            self.logger.info(
                "RiskManager: market data feed marked FRESH — trade entries re-enabled"
            )

    # ==========================================================================
    # DATA STALENESS EVENT HANDLERS (wired by __init__ via EventManager)
    # ==========================================================================

    def _on_data_stale(self, event: Any) -> None:
        """Handle DATA_STALE event emitted by TradovC06_DataValidator.

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
        """Handle DATA_FRESH event emitted by TradovC06_DataValidator.

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

    def _on_position_updated(self, event: Any) -> None:
        """Update internal position state from a PositionTracker POSITION_UPDATED event.

        Called whenever B03 PositionTracker confirms a fill has changed a
        position (S-06).  Merges the incoming net quantity into
        ``self._positions`` under ``_risk_lock`` so that subsequent
        ``validate_signal`` calls see ground-truth position sizes.

        Args:
            event: EventManager Event whose ``data`` dict has at least
                   ``symbol`` (str) and ``quantity`` (int, signed net).
        """
        data   = event.data or {}
        symbol = data.get("symbol")
        qty    = data.get("quantity")

        if not symbol or qty is None:
            return

        # A6 (v14): reject updates with missing or non-positive fill price for
        # position *creation*. Silently defaulting to 0.0 produced risk
        # positions that priced at zero and evaded loss checks. A qty==0
        # close-out does not need a price and is allowed to proceed.
        raw_price = data.get("fill_price")
        fill_price: float | None
        if qty == 0:
            fill_price = None
        else:
            try:
                fill_price = float(raw_price) if raw_price is not None else None
            except (TypeError, ValueError):
                fill_price = None
            if fill_price is None or fill_price <= 0.0:
                self.logger.error(
                    "E01: rejecting POSITION_UPDATED for %s — invalid fill_price=%r "
                    "(qty=%s). Position not created.",
                    symbol, raw_price, qty,
                )
                try:
                    get_event_manager().emit(
                        EventType.SYSTEM_ERROR,
                        {
                            "source": "E01.RiskManager",
                            "reason": "invalid_fill_price",
                            "symbol": symbol,
                            "fill_price": raw_price,
                            "quantity": qty,
                        },
                        source="RiskManager",
                    )
                except Exception as exc:
                    self.logger.error("E01: failed to emit SYSTEM_ERROR: %s", exc)
                return

        with self._risk_lock:
            if qty == 0:
                self._positions.pop(symbol, None)
            else:
                existing = self._positions.get(symbol)
                if existing is not None:
                    existing.quantity = int(qty)
                    existing.last_updated = now_et()
                else:
                    self._positions[symbol] = Position(
                        symbol=symbol,
                        quantity=int(qty),
                        market_price=float(fill_price),
                        market_value=0.0,
                        average_fill_price=float(fill_price),
                        unrealized_pnl=0.0,
                        realized_pnl=0.0,
                    )
            self.metrics["position_updates"] = self.metrics.get("position_updates", 0) + 1

        self.logger.debug(
            "_on_position_updated: %s net_qty=%s", symbol, qty
        )

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

    @staticmethod
    def _coerce_overlay_float(value: Any) -> float | None:
        """Return a float for overlay metadata values when possible."""
        if value is None:
            return None

        text = str(value).strip()
        if not text:
            return None

        try:
            return float(text)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_overlay_bool(value: Any) -> bool | None:
        """Return a bool for overlay metadata values when possible."""
        if isinstance(value, bool):
            return value
        if value is None:
            return None

        text = str(value).strip().lower()
        if not text:
            return None
        if text in {"1", "true", "yes", "on", "blocked"}:
            return True
        if text in {"0", "false", "no", "off", "clear"}:
            return False
        return None

    def _build_overlay_verdict(
        self,
        *,
        allow: bool,
        reason_code: str,
        limits_snapshot: dict[str, Any],
        computed_values: dict[str, Any],
    ) -> OverlayPretradeVerdict:
        """Build a stable typed overlay-slot verdict."""
        return OverlayPretradeVerdict(
            allow=bool(allow),
            reason_code=str(reason_code or ""),
            limits_snapshot=dict(limits_snapshot),
            computed_values=dict(computed_values),
        )

    def validate_overlay_slot(self, request: RiskValidationRequest) -> OverlayPretradeVerdict:
        """Run the overlay-slot pre-trade risk gate.

        Args:
            request: Overlay-slot request passed across the E↔D boundary.

        Returns:
            OverlayPretradeVerdict with the allow/deny decision, thresholds,
            and computed values used by the check.

        Raises:
            TypeError: If request is not a RiskValidationRequest instance.
        """
        if not isinstance(request, RiskValidationRequest):
            raise TypeError(
                f"validate_overlay_slot expects RiskValidationRequest, got {type(request).__name__}"
            )

        metadata = request.metadata if isinstance(request.metadata, dict) else {}
        projected_greeks = (
            metadata.get("projected_post_trade_greeks")
            if isinstance(metadata.get("projected_post_trade_greeks"), dict)
            else {}
        )
        execution_quality = (
            metadata.get("execution_quality")
            if isinstance(metadata.get("execution_quality"), dict)
            else {}
        )
        limits_snapshot = {
            "overlay_max_daily_risk_used_fraction": float(
                self.config.risk_limits.get("overlay_max_daily_risk_used_fraction", 0.60)
            ),
            "overlay_max_expected_slippage_bps": float(
                self.config.risk_limits.get("overlay_max_expected_slippage_bps", 25.0)
            ),
            "overlay_max_projected_delta": float(
                self.config.risk_limits.get("overlay_max_projected_delta", 0.10)
            ),
            "overlay_max_projected_gamma": float(
                self.config.risk_limits.get("overlay_max_projected_gamma", 0.02)
            ),
            "overlay_max_projected_vega": float(
                self.config.risk_limits.get("overlay_max_projected_vega", 0.10)
            ),
            "overlay_max_projected_theta": float(
                self.config.risk_limits.get("overlay_max_projected_theta", 0.10)
            ),
            "max_daily_loss": float(self.config.risk_limits.get("max_daily_loss", 0.0)),
        }

        try:
            with self._risk_lock:
                if len(self._positions) == 0 and not self._account_state_synced:
                    return self._build_overlay_verdict(
                        allow=False,
                        reason_code="risk_state_cold",
                        limits_snapshot=limits_snapshot,
                        computed_values={"symbol": request.symbol},
                    )

                if self._data_stale:
                    return self._build_overlay_verdict(
                        allow=False,
                        reason_code="data_stale",
                        limits_snapshot=limits_snapshot,
                        computed_values={"symbol": request.symbol},
                    )

                if self._y03_veto_state in ("warning", "halt") and not self._observe_only_agents:
                    return self._build_overlay_verdict(
                        allow=False,
                        reason_code="agent_veto",
                        limits_snapshot=limits_snapshot,
                        computed_values={
                            "symbol": request.symbol,
                            "circuit_breaker": self._y03_veto_state,
                        },
                    )

                risk_metrics = self._calculate_risk_metrics()
                strategy_type = str(metadata.get("strategy_type") or "").strip().lower()
                daily_risk_used_fraction = self._coerce_overlay_float(
                    metadata.get("daily_risk_used_fraction")
                )
                event_window_blocked = self._coerce_overlay_bool(
                    metadata.get("event_window_blocked")
                )
                bid_ask_width_ok = self._coerce_overlay_bool(
                    execution_quality.get("bid_ask_width_ok")
                )
                expected_slippage_bps = self._coerce_overlay_float(
                    execution_quality.get("expected_slippage_bps")
                )

                computed_values: dict[str, Any] = {
                    "symbol": request.symbol,
                    "strategy_type": strategy_type,
                    "daily_risk_used_fraction": daily_risk_used_fraction,
                    "projected_post_trade_greeks": {},
                    "execution_quality": {
                        "bid_ask_width_ok": bid_ask_width_ok,
                        "expected_slippage_bps": expected_slippage_bps,
                    },
                    "event_window_blocked": event_window_blocked,
                    "current_total_exposure": risk_metrics.total_exposure,
                    "current_daily_pnl": risk_metrics.daily_pnl,
                }
                missing_inputs: list[str] = []

                if not strategy_type:
                    missing_inputs.append("strategy_type")
                elif strategy_type != "pivot_mean_reversion":
                    return self._build_overlay_verdict(
                        allow=False,
                        reason_code="not_overlay_candidate",
                        limits_snapshot=limits_snapshot,
                        computed_values=computed_values,
                    )

                if daily_risk_used_fraction is None:
                    missing_inputs.append("daily_risk_used_fraction")
                if event_window_blocked is None:
                    missing_inputs.append("event_window_blocked")
                if bid_ask_width_ok is None:
                    missing_inputs.append("execution_quality.bid_ask_width_ok")
                if expected_slippage_bps is None:
                    missing_inputs.append("execution_quality.expected_slippage_bps")

                greek_limits = {
                    "delta": limits_snapshot["overlay_max_projected_delta"],
                    "gamma": limits_snapshot["overlay_max_projected_gamma"],
                    "vega": limits_snapshot["overlay_max_projected_vega"],
                    "theta": limits_snapshot["overlay_max_projected_theta"],
                }
                greek_values: dict[str, float] = {}
                for greek_name in ("delta", "gamma", "vega", "theta"):
                    greek_value = self._coerce_overlay_float(projected_greeks.get(greek_name))
                    if greek_value is None:
                        missing_inputs.append(f"projected_post_trade_greeks.{greek_name}")
                        continue
                    greek_values[greek_name] = greek_value

                computed_values["projected_post_trade_greeks"] = dict(greek_values)

                if missing_inputs:
                    computed_values["missing_inputs"] = missing_inputs
                    return self._build_overlay_verdict(
                        allow=False,
                        reason_code="missing_inputs",
                        limits_snapshot=limits_snapshot,
                        computed_values=computed_values,
                    )

                if event_window_blocked:
                    return self._build_overlay_verdict(
                        allow=False,
                        reason_code="event_window",
                        limits_snapshot=limits_snapshot,
                        computed_values=computed_values,
                    )

                if not bid_ask_width_ok:
                    computed_values["execution_quality_failure"] = "bid_ask_width"
                    return self._build_overlay_verdict(
                        allow=False,
                        reason_code="execution_quality",
                        limits_snapshot=limits_snapshot,
                        computed_values=computed_values,
                    )

                if expected_slippage_bps > limits_snapshot["overlay_max_expected_slippage_bps"]:
                    computed_values["execution_quality_failure"] = "expected_slippage_bps"
                    return self._build_overlay_verdict(
                        allow=False,
                        reason_code="execution_quality",
                        limits_snapshot=limits_snapshot,
                        computed_values=computed_values,
                    )

                if daily_risk_used_fraction > limits_snapshot["overlay_max_daily_risk_used_fraction"]:
                    return self._build_overlay_verdict(
                        allow=False,
                        reason_code="daily_risk_limit",
                        limits_snapshot=limits_snapshot,
                        computed_values=computed_values,
                    )

                for greek_name, greek_limit in greek_limits.items():
                    if abs(greek_values[greek_name]) > greek_limit:
                        computed_values["risk_limit_failure"] = greek_name
                        return self._build_overlay_verdict(
                            allow=False,
                            reason_code="risk_limit",
                            limits_snapshot=limits_snapshot,
                            computed_values=computed_values,
                        )

                return self._build_overlay_verdict(
                    allow=True,
                    reason_code="admitted",
                    limits_snapshot=limits_snapshot,
                    computed_values=computed_values,
                )
        except Exception as exc:
            self.logger.error("validate_overlay_slot error: %s", exc, exc_info=True)
            return self._build_overlay_verdict(
                allow=False,
                reason_code="internal_error",
                limits_snapshot=limits_snapshot,
                computed_values={
                    "symbol": request.symbol,
                    "error": str(exc),
                },
            )

    def validate_signal(self, request: RiskValidationRequest) -> RiskValidationResult:
        """Satisfies RiskManagerProtocol.validate_signal().

        Maps a RiskValidationRequest from the D↔E series boundary into the
        internal synchronous risk checks and returns a RiskValidationResult.
        All state reads are performed under _risk_lock for TOCTOU safety.

        Args:
            request: RiskValidationRequest from TradovE00_RiskProtocol.

        Returns:
            RiskValidationResult indicating approval, risk score, and any
            violated rule codes.

        Raises:
            TypeError: If request is not a RiskValidationRequest instance.
        """
        if not isinstance(request, RiskValidationRequest):
            raise TypeError(
                f"validate_signal expects RiskValidationRequest, got {type(request).__name__}"
            )
        from Tradov.TradovE_Risk.TradovE00_RiskProtocol import RiskValidationResult  # noqa: F811
        try:
            with self._risk_lock:
                # P1-2: cold-start gate — if we still have no positions and
                # account state has not been synced yet, reject new signals.
                if len(self._positions) == 0 and not self._account_state_synced:
                    return RiskValidationResult(
                        approved=False,
                        rejection_reason="risk_state_cold",
                        risk_score=1.0,
                        violations=["RISK_STATE_COLD"],
                    )

                # --- Stale data gate ---
                if self._data_stale:
                    return RiskValidationResult(
                        approved=False,
                        rejection_reason="Market data feed is stale; trading disabled until fresh data arrives",  # noqa: E501
                        risk_score=1.0,
                        violations=["DATA_STALE"],
                    )

                # --- Y03 RiskSentinelAgent veto gate ---
                if self._y03_veto_state in ("warning", "halt"):
                    if not self._observe_only_agents:
                        return RiskValidationResult(
                            approved=False,
                            rejection_reason=f"Y03 RiskSentinel veto active: circuit_breaker={self._y03_veto_state}",  # noqa: E501
                            risk_score=1.0,
                            violations=["AGENT_VETO"],
                        )
                    self.logger.warning(
                        "Y03 veto observed (non-blocking): circuit_breaker=%s",
                        self._y03_veto_state,
                    )

                # --- Stage 3: decision-quality SLO gate ---
                if self._enforce_decision_quality_slo:
                    slo_ok, slo_reason, slo_violations = self._check_decision_quality_slo()
                    if not slo_ok:
                        return RiskValidationResult(
                            approved=False,
                            rejection_reason=slo_reason,
                            risk_score=1.0,
                            violations=slo_violations,
                        )

                # Block naked puts — strategy_type is carried in metadata.
                strategy_type = (request.metadata or {}).get("strategy_type", "")
                if strategy_type == "naked_put":
                    return RiskValidationResult(
                        approved=False,
                        rejection_reason="Naked put orders are prohibited by risk policy; use a defined-risk spread instead",  # noqa: E501
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
                        rejection_reason=f"Total exposure {new_exposure:.0f} exceeds limit {max_exp:.0f}",  # noqa: E501
                        violations=["EXPOSURE_EXCEEDED"],
                    )

                # --- Daily loss ---
                if risk_metrics.daily_pnl < -self.config.risk_limits["max_daily_loss"]:
                    return RiskValidationResult(
                        approved=False,
                        rejection_reason=f"Daily P&L {risk_metrics.daily_pnl:.0f} exceeds max daily loss limit",  # noqa: E501
                        violations=["DAILY_LOSS_EXCEEDED"],
                    )

                # --- Soft warnings (approved but flagged) ---
                violations: list[str] = []
                new_symbol_value = (current_pos.market_value if current_pos else 0.0) + order_value
                concentration = new_symbol_value / new_exposure if new_exposure > 0 else 0.0
                if concentration > self.config.risk_limits["max_concentration_ratio"]:
                    violations.append("CONCENTRATION_WARNING")

                total_margin = risk_metrics.margin_used + risk_metrics.margin_available
                if total_margin > 0 and (risk_metrics.margin_used / total_margin) > self.config.risk_limits["max_margin_usage"]:  # noqa: E501
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

    def check_daily_limits(self) -> bool:
        """Check whether daily risk limits are within acceptable bounds.

        Called by runtime engines (e.g. TradovR04_LiveEngine) before starting
        or continuing a trading session.

        Returns:
            True  — trading is permitted (all daily limits within bounds).
            False — a daily limit has been breached; caller should halt trading.
        """
        with self._risk_lock:
            if self._data_stale:
                self.logger.warning(
                    "check_daily_limits: market data is stale — returning False"
                )
                return False
            try:
                metrics = self._calculate_risk_metrics()
                max_loss = self.config.risk_limits.get("max_daily_loss", 0.0)
                if metrics.daily_pnl < -abs(max_loss):
                    self.logger.warning(
                        "Daily loss limit breached: P&L %.2f < -%.2f",
                        metrics.daily_pnl,
                        max_loss,
                    )
                    return False
                return True
            except Exception as exc:
                self.logger.error(
                    "check_daily_limits error: %s", exc, exc_info=True
                )
                return False  # Fail safe

    def check_trade(self, trade_request: dict[str, Any]) -> dict[str, Any]:
        """Compatibility adapter for legacy runtime callers.

        Older A/P/Q/K modules still send plain dict payloads via ``check_trade``.
        Map that request onto the typed E00 validation contract.
        """
        from Tradov.TradovE_Risk.TradovE00_RiskProtocol import (
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
            # v27 SPEC-10: in live mode, refuse to mark synced when no broker
            # client is configured. The cold-start guard must remain active so
            # validate_signal rejects every signal — silently failing open here
            # would let degraded boots approve orders against a zero baseline.
            if os.environ.get("TRADING_MODE", "paper").lower() == "live":
                self.logger.error(
                    "RiskManager: TRADING_MODE=live but tradier_client is None — "
                    "leaving cold-start guard engaged; all signals will be rejected."
                )
                return
            self.logger.debug(
                "RiskManager: tradier_client not configured — running standalone; "
                "marking account state synced so signals are not cold-start rejected."
            )
            with self._risk_lock:
                self._account_state_synced = True
            return

        try:
            response = await self.tradier_client.get_account_balances_async()
        except Exception as e:
            self.logger.error("Tradier balance fetch failed: %s", e, exc_info=True)
            self.error_handler.handle_error(e, "_request_account_summary")
            # If the broker is not a live TradierClient (e.g. PaperBroker, stub),
            # a failed balance call must not permanently lock the cold-start gate —
            # it would silently block all signals for the entire session.
            from Tradov.TradovB_Broker.TradovB40_TradierClient import TradierClient  # noqa: PLC0415
            if not isinstance(self.tradier_client, TradierClient):
                self.logger.warning(
                    "RiskManager: non-Tradier broker balance call failed; "
                    "marking account synced to unblock cold-start gate."
                )
                with self._risk_lock:
                    self._account_state_synced = True
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
        with self._risk_lock:
            self._account_state_synced = True
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
                # v27 SPEC-9: the Tradier positions endpoint does NOT return
                # UnrealizedPNL / RealizedPNL fields. Writing 0.0 every cycle
                # destroyed any PnL value cached from another source, masking
                # daily-loss limits. Preserve existing PnL when the payload
                # omits the field; only write when explicitly present.
                existing = self._positions.get(symbol)
                if "UnrealizedPNL" in data:
                    unrealized_pnl = float(data["UnrealizedPNL"])
                elif existing is not None:
                    unrealized_pnl = existing.unrealized_pnl
                else:
                    unrealized_pnl = 0.0
                if "RealizedPNL" in data:
                    realized_pnl = float(data["RealizedPNL"])
                elif existing is not None:
                    realized_pnl = existing.realized_pnl
                else:
                    realized_pnl = 0.0

                position = Position(
                    symbol=symbol,
                    quantity=int(data.get("Position", 0)),
                    market_price=float(data.get("MarketPrice", 0.0)),
                    market_value=float(data.get("MarketValue", 0.0)),
                    average_fill_price=float(data.get("AverageCost", 0.0)),
                    unrealized_pnl=unrealized_pnl,
                    realized_pnl=realized_pnl,
                    currency=data.get("Currency", "USD"),
                    security_type=data.get("SecurityType", "STK"),
                    expiry=data.get("ExpirationDate"),
                    strike=float(data.get("Strike", 0.0)) if data.get("Strike") else None,
                    right=data.get("Right"),
                    last_updated=now_et()
                )

                self._positions[symbol] = position
                self.metrics['position_updates'] += 1

                # Update risk metrics
                self._risk_metrics = self._calculate_risk_metrics()

                # Log position update
                self.logger.debug("Position updated: %s - %s @ %s", symbol, position.quantity, position.market_price)  # noqa: E501

        except Exception as e:
            self.logger.error("Error handling position update: %s", e, exc_info=True)
            self.error_handler.handle_error(e, "_handle_position_update")

    async def _handle_account_summary_update(self, data: dict[str, Any]):
        """
        Handle account summary update message.

        Args:
            data: Account summary data with keys NetLiquidation, TotalCashValue,
                  MarginUsed, MarginAvailable (floats).
        """
        try:
            with self._risk_lock:
                # Cache the fetched balances so _calculate_risk_metrics can use
                # them directly instead of falling back to an AccountManager import.
                self._cached_account_balances = {
                    "net_liquidation": float(data.get("NetLiquidation") or 0.0),
                    "total_cash": float(data.get("TotalCashValue") or 0.0),
                    "margin_used": float(data.get("MarginUsed") or 0.0),
                    "margin_available": float(data.get("MarginAvailable") or 0.0),
                }
                # Recompute risk metrics with the freshly cached values.
                self._risk_metrics = self._calculate_risk_metrics()

                self.logger.debug(
                    "Account summary cached — NLV=%.2f cash=%.2f margin_used=%.2f",
                    self._cached_account_balances["net_liquidation"],
                    self._cached_account_balances["total_cash"],
                    self._cached_account_balances["margin_used"],
                )

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

            # v27 SPEC-9: source daily P&L from the Tradier balances endpoint
            # (close_pl / day_change), NOT from summing local Position.unrealized_pnl
            # +realized_pnl. The positions endpoint does not return PnL fields,
            # so the local sum was always 0.0 — silently disabling the daily-loss
            # kill switch. Fall back to the legacy local sum only when the
            # broker-fed value is unavailable (e.g. paper-mode boot before the
            # first balance fetch).
            cached_balances = getattr(self, "_cached_account_balances", {}) or {}
            broker_daily_pnl = cached_balances.get("close_pl")
            if broker_daily_pnl is None:
                broker_daily_pnl = cached_balances.get("day_change")
            if broker_daily_pnl is not None:
                daily_pnl = float(broker_daily_pnl)
            else:
                daily_pnl = sum(
                    pos.unrealized_pnl + pos.realized_pnl
                    for pos in self._positions.values()
                )

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
                warnings.append(f"Daily loss {daily_pnl} exceeds maximum {self.config.risk_limits['max_daily_loss']}")  # noqa: E501

            # Check total exposure
            if total_exposure > self.config.risk_limits['max_total_exposure']:
                risk_level = RiskLevel.HIGH
                warnings.append(f"Total exposure {total_exposure} exceeds maximum {self.config.risk_limits['max_total_exposure']}")  # noqa: E501

            # Check concentration
            if max_concentration > self.config.risk_limits['max_concentration_ratio']:
                if risk_level.value < RiskLevel.MEDIUM.value:
                    risk_level = RiskLevel.MEDIUM
                warnings.append(f"Concentration {max_concentration:.2%} in {concentration_symbol} exceeds maximum {self.config.risk_limits['max_concentration_ratio']:.2%}")  # noqa: E501

            # Check options exposure
            if options_exposure > self.config.risk_limits['max_options_exposure']:
                if risk_level.value < RiskLevel.MEDIUM.value:
                    risk_level = RiskLevel.MEDIUM
                warnings.append(f"Options exposure {options_exposure} exceeds maximum {self.config.risk_limits['max_options_exposure']}")  # noqa: E501

            # Use cached Tradier account balances when available; fall back to
            # AccountManager singleton for backwards-compatibility with older callers.
            cached = getattr(self, "_cached_account_balances", {})
            net_liq = cached.get("net_liquidation", 0.0)
            margin_used_val = cached.get("margin_used", 0.0)
            margin_avail = cached.get("margin_available", 0.0)

            if net_liq == 0.0:
                try:
                    from Tradov.TradovB_Broker.TradovB04_AccountManager import AccountManager
                    account_mgr = AccountManager.get_instance()
                    if account_mgr:
                        net_liq = account_mgr.get_net_liquidation()
                        account_info = account_mgr.get_account_info()
                        if account_info:
                            margin_used_val = getattr(account_info, 'margin_used', 0.0)
                            margin_avail = getattr(account_info, 'margin_available', 0.0)
                except (ImportError, AttributeError) as e:
                    self.logger.debug("Could not retrieve account data: %s", e)

            # Create risk metrics
            risk_metrics = RiskMetrics(
                timestamp=now_et(),
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
                timestamp=now_et(),
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

    # ==========================================================================
    # PUBLIC UTILITY METHODS
    # ==========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get current risk manager status."""
        with self._risk_lock:
            uptime = now_et() - self.metrics['start_time']
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
                'position_updates': self.metrics.get('position_updates', 0),
                'uptime_seconds': uptime.total_seconds(),
                'start_time': self.metrics['start_time'].isoformat(),
            }

    def get_metrics(self) -> dict[str, Any]:
        """Get risk manager performance metrics."""
        with self._risk_lock:
            uptime = now_et() - self.metrics['start_time']
            check_rate = 0.0
            if uptime.total_seconds() > 0:
                check_rate = self.metrics['risk_checks'] / uptime.total_seconds()
            return {
                'risk_checks': self.metrics['risk_checks'],
                'warnings': self.metrics['warnings'],
                'blocks': self.metrics['blocks'],
                'position_updates': self.metrics.get('position_updates', 0),
                'check_rate': check_rate,
                'uptime_seconds': uptime.total_seconds(),
                'start_time': self.metrics['start_time'].isoformat(),
            }


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
