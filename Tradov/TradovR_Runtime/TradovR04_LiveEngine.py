#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovR_Runtime
Module: TradovR04_LiveEngine.py
Purpose: TRADOV - Automated SPX Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    TRADOV - Automated SPX Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import concurrent.futures
import json
import queue
import re
import threading
import time as time_module
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
import os
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler
from Tradov.TradovA_Core.TradovA05_EventManager import get_event_manager, EventType

# Soft import: TradierServerError is only available when the broker layer is present.
try:
    from Tradov.TradovB_Broker.TradovB40_TradierClient import TradierServerError as _TradierServerError  # noqa: E501
except ImportError:
    class _TradierServerError(Exception):  # type: ignore[no-redef]
        """Stub used when TradovB40_TradierClient is not importable."""

MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
EXTENDED_HOURS_START = time(4, 0)
EXTENDED_HOURS_END = time(20, 0)
_ET = ZoneInfo("America/New_York")

# Safety limits - Load from environment variables with defaults
MAX_DAILY_TRADES = int(os.environ.get('MAX_DAILY_TRADES', 100))
MAX_POSITION_SIZE = int(os.environ.get('MAX_POSITION_SIZE', 10000))  # contracts
MAX_DAILY_LOSS = float(os.environ.get('MAX_DAILY_LOSS_USD', 10000))  # dollars
MAX_LIVE_TRADES = int(os.environ.get('TRADOV_MAX_LIVE_TRADES', 3))
MAX_PAIR_TRADES = int(os.environ.get('TRADOV_MAX_PAIR_TRADES', 3))
MAX_DIRECTIONAL_TRADES = int(os.environ.get('TRADOV_MAX_DIRECTIONAL_TRADES', 0))
EMERGENCY_STOP_LOSS = float(os.environ.get('EMERGENCY_STOP_LOSS_PCT', 0.05))  # 5% portfolio loss

# Confirmation settings - Opt-in for development mode
REQUIRE_LIVE_ORDER_CONFIRMATION = os.environ.get('REQUIRE_LIVE_ORDER_CONFIRMATION', 'false').lower() == 'true'  # noqa: E501
HIGH_RISK_ORDER_CONFIRMATION = os.environ.get('HIGH_RISK_ORDER_CONFIRMATION', 'true').lower() == 'true'  # noqa: E501
HIGH_RISK_ORDER_THRESHOLD_USD = float(os.environ.get('HIGH_RISK_ORDER_THRESHOLD_USD', 50000))  # $50k  # noqa: E501
# Consecutive Tradier 5xx errors before entering API Panic Mode and halting all trading.
API_PANIC_THRESHOLD = int(os.environ.get("API_PANIC_THRESHOLD", "3"))
ORPHAN_ORDER_PANIC_THRESHOLD = int(os.environ.get("ORPHAN_ORDER_PANIC_THRESHOLD", "3"))
ORPHAN_ORDER_PANIC_WINDOW_SECONDS = int(os.environ.get("ORPHAN_ORDER_PANIC_WINDOW_SECONDS", "300"))
HIGH_RISK_ORDER_PORTFOLIO_PCT = float(os.environ.get('HIGH_RISK_ORDER_PORTFOLIO_PCT', 0.25))  # 25% of portfolio  # noqa: E501
# CLOSE_POSITIONS_ON_EMERGENCY: when true, emergency_stop flattens all open positions
# immediately via market orders. Default is false so that a transient Tradier API outage
# (which now triggers emergency_stop via API Panic Mode after 3 consecutive 5xx errors)
# does not auto-liquidate legitimate positions. Operators who want automatic flattening
# must opt in explicitly by setting CLOSE_POSITIONS_ON_EMERGENCY=true in .env.
CLOSE_POSITIONS_ON_EMERGENCY = os.environ.get('CLOSE_POSITIONS_ON_EMERGENCY', 'false').lower() == 'true'  # noqa: E501

# Regime gate — SWAN tail-risk threshold (mirrors R08 paper engine)
SWAN_BLOCK_THRESHOLD = float(os.environ.get("SWAN_BLOCK_THRESHOLD", "2.0"))

# Execution parameters
ORDER_RETRY_LIMIT = 3
ORDER_TIMEOUT_SECONDS = 30
HEARTBEAT_INTERVAL = 5  # seconds
# A16 (v14): monitor tick runs once per second; a 5s cache cuts broker
# get_positions calls 5× while still reacting quickly after a fill (fills
# explicitly invalidate the cache, so the post-fill view is immediate).
POSITIONS_CACHE_TTL = 5.0
PAPER_OPTION_QUOTES_CACHE_TTL = 5.0
PAPER_OPTION_CHAIN_CACHE_TTL = 60.0

# ==============================================================================
# ENUMS
# ==============================================================================


class TradingMode(Enum):
    """Trading mode enumeration"""

    LIVE = "live"
    PAPER = "paper"
    SIMULATION = "simulation"
    EMERGENCY_STOP = "emergency_stop"


class ExecutionState(Enum):
    """Execution state enumeration"""

    INITIALIZED = "initialized"
    CONNECTED = "connected"
    TRADING = "trading"
    PAUSED = "paused"
    CLOSING = "closing"
    STOPPED = "stopped"
    ERROR = "error"


class SafetyCheckResult(Enum):
    """Safety check result enumeration"""

    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    OVERRIDE = "override"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class LiveTradingConfig:
    """Configuration for live trading"""

    account_id: str
    max_daily_trades: int = MAX_DAILY_TRADES
    max_position_size: int = MAX_POSITION_SIZE
    max_daily_loss: float = MAX_DAILY_LOSS
    max_live_trades: int = MAX_LIVE_TRADES
    max_pair_trades: int = MAX_PAIR_TRADES
    max_directional_trades: int = MAX_DIRECTIONAL_TRADES
    enable_extended_hours: bool = False
    require_confirmation: bool = REQUIRE_LIVE_ORDER_CONFIRMATION  # Autonomous by default
    high_risk_confirmation: bool = HIGH_RISK_ORDER_CONFIRMATION  # Selective confirmation for large orders  # noqa: E501
    high_risk_threshold_usd: float = HIGH_RISK_ORDER_THRESHOLD_USD
    high_risk_portfolio_pct: float = HIGH_RISK_ORDER_PORTFOLIO_PCT
    use_limit_orders_only: bool = False
    slippage_tolerance: float = 0.01  # 1%
    partial_fill_timeout: int = 60  # seconds
    close_positions_on_emergency: bool = CLOSE_POSITIONS_ON_EMERGENCY  # Env: CLOSE_POSITIONS_ON_EMERGENCY (default false, opt-in)  # noqa: E501


@dataclass
class TradingSession:
    """Trading session information"""

    session_id: str
    start_time: datetime
    end_time: datetime | None = None
    mode: TradingMode = TradingMode.LIVE
    trades_executed: int = 0
    orders_placed: int = 0
    orders_filled: int = 0
    orders_cancelled: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0


@dataclass
class SafetyCheck:
    """Safety check result"""

    check_name: str
    result: SafetyCheckResult
    message: str
    timestamp: datetime
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionMetrics:
    """Live execution metrics"""

    total_orders: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    partial_fills: int = 0
    average_fill_time: float = 0.0
    average_slippage: float = 0.0
    rejection_rate: float = 0.0


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class LiveEngine:
    """
    Live trading execution engine.

    This class manages all aspects of live trading including order execution,
    position monitoring, safety checks, and emergency controls.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        config: Live trading configuration
        state: Current execution state
        broker: Broker interface
        risk_manager: Risk management interface

    Example:
        >>> engine = LiveEngine(broker, risk_manager, config)
        >>> engine.initialize()
        >>> engine.start_trading()
    """

    def __init__(self, broker_interface, risk_manager, config: LiveTradingConfig,
                 telegram_bot=None, event_manager=None, fill_reconciler=None,
                 position_tracker=None):
        """Initialize the live engine."""
        self.logger = TradovLogger.get_logger(__name__)
        self.error_handler = TradovErrorHandler()
        self.config = config
        self.broker = broker_interface
        self.risk_manager = risk_manager
        self.telegram_bot = telegram_bot  # Optional TradovJ05_TelegramBot for high-risk alerts
        self._event_manager = event_manager or get_event_manager()

        # FillReconciler for ground-truth fill detection (S-11).
        self._reconciler = fill_reconciler

        # PositionTracker for recording fills (S-06).
        self._position_tracker = position_tracker

        # Subscribe to fills published by the FillReconciler so we can
        # increment metrics once a real fill is confirmed (not on acceptance).
        self._event_manager.subscribe(EventType.ORDER_FILLED, self._on_reconciler_fill)
        self._event_manager.subscribe(
            EventType.ORDER_PARTIALLY_FILLED, self._on_reconciler_partial_fill
        )
        # O-4: Hard kill-switch — any subscriber can halt order submission.
        self._event_manager.subscribe(EventType.KILL_SWITCH, self._on_kill_switch)
        # P0-2: Bridge EMERGENCY (emitted by E11/E13 on catastrophic loss) to
        # KILL_SWITCH so a single handler enforces the halt regardless of which
        # event the risk layer fires.
        self._event_manager.subscribe(EventType.EMERGENCY, self._on_emergency_bridge)
        # N1: threading.Event gives atomic set/check semantics across threads.
        # Use .is_set() in place of the old bool read, and .set() to activate.
        self._kill_switch_event: threading.Event = threading.Event()
        # Back-compat shim — read-only property so existing callers still work.
        # P0-10: Remove terminal orders from pending_orders to prevent stuck state
        # and memory leak.
        self._event_manager.subscribe(EventType.ORDER_CANCELLED, self._on_order_terminal_event)
        self._event_manager.subscribe(EventType.ORDER_EXPIRED, self._on_order_terminal_event)
        self._event_manager.subscribe(EventType.ORDER_REJECTED, self._on_order_terminal_event)
        self._event_manager.subscribe(EventType.ORDER_ORPHANED, self._on_order_orphaned)
        # B4 (v15): handle the reconciler's recovery event so the orphan flag is
        # cleared when the broker subsequently reports a terminal status.
        self._event_manager.subscribe(EventType.ORDER_UN_ORPHANED, self._on_order_un_orphaned)
        self._event_manager.subscribe(EventType.POSITION_UPDATED, self._on_position_updated)

        # State management
        self.state = ExecutionState.INITIALIZED
        account_id = str(getattr(config, "account_id", "") or "").upper()
        self.mode = TradingMode.PAPER if account_id.startswith("PAPER") else TradingMode.LIVE
        self.current_session: TradingSession | None = None

        # Order management
        self.pending_orders: dict[str, Any] = {}
        self._pending_orders_lock = threading.RLock()  # B4: guard all pending_orders access
        self.active_positions: dict[str, Any] = {}
        # A1 (v14): guard all writes to active_positions — reads within R04 also take
        # the lock. Strategy-side reads remain lock-free for now (A1-followup).
        self._active_positions_lock = threading.RLock()
        self.order_history: deque = deque(maxlen=1000)

        # Safety and monitoring
        self.safety_checks: list[SafetyCheck] = []
        self.emergency_stop = False
        self.daily_loss = 0.0
        self.daily_trades = 0
        self._realized_pnl_total = 0.0
        self._winning_trade_count = 0
        self._losing_trade_count = 0

        # Drawdown tracking — rolling peak of session P&L (P1-4)
        self._peak_session_pnl: float = 0.0

        # API Panic Mode — counts consecutive Tradier 5xx errors.
        self._api_error_count: int = 0
        self._api_panic_mode: bool = False
        self._orphan_order_times: deque = deque()

        # Execution metrics
        self.metrics = ExecutionMetrics()
        self.execution_times: deque = deque(maxlen=100)
        self.slippage_history: deque = deque(maxlen=100)

        # Threading for monitoring
        self.monitor_thread = None
        self.stop_event = threading.Event()
        self.order_queue = queue.Queue()

        # Heartbeat
        self.last_heartbeat = datetime.now(_ET)
        self.broker_connected = False

        # A16 (v14): TTL cache on broker.get_positions() so each monitor tick
        # doesn't burn a broker API call; invalidated on any fill so a freshly
        # opened position shows up within one monitor cycle rather than after
        # the TTL expires.
        self._positions_cache: list[Any] | None = None
        self._positions_cache_at: float = 0.0

        # Regime metrics — populated by update_regime_metrics() which should
        # be called by the CustomMetricsOrchestrator (S07) on each metrics tick.
        # Mirrors the equivalent dict in R08 PaperTradingQtWorker.
        self._regime_metrics: dict[str, Any] = {}
        self._positions_cache_lock = threading.Lock()

        # Internal paper positions still need live Tradier option marks for MTM.
        self._paper_option_quote_client = None
        self._paper_option_quote_client_unavailable = False
        self._paper_option_quote_cache: dict[str, float] = {}
        self._paper_option_quote_cache_at: float = 0.0
        self._paper_option_quote_lock = threading.RLock()
        self._paper_option_quote_misses: set[str] = set()
        self._paper_option_expiration_cache: dict[str, list[str]] = {}
        self._paper_option_expiration_cache_at: dict[str, float] = {}
        self._paper_option_chain_cache: dict[tuple[str, str], dict[str, list[float]]] = {}
        self._paper_option_chain_cache_at: dict[tuple[str, str], float] = {}

        # Optional A02 gate bridge: run decision-flow gates before R04 checks.
        self.trading_engine = None
        self._a02_decision_gate_enabled = (
            os.environ.get("R04_USE_A02_DECISION_FLOW_GATE", "false").strip().lower() == "true"
        )

        # H05 TradingSessionDB — live database.  Injected by R12
        # SessionSupervisor via set_session_db() after construction.
        # Records every confirmed fill so live history is persisted in an
        # identically-structured DB to the paper database.
        self._session_db = None  # TradingSessionDB | None

        # A24 (v14): hot-reload subscriber — if the A03 configuration manager
        # is importable, register ourselves so operator-initiated config
        # changes propagate without a restart. Structural fields (account_id,
        # env) are refused to avoid swapping broker identity mid-session.
        self._register_hot_reload_callback()

        self.logger.debug("LiveEngine initialized for account %s", config.account_id)

    def set_trading_engine(self, trading_engine: Any) -> None:
        """Attach TradingEngine for optional A02 decision-flow preflight gating."""
        self.trading_engine = trading_engine

    def _run_a02_decision_gate(self, order: dict[str, Any]) -> tuple[bool, str]:
        """Optionally run A02 Data->Regime->Strategy->Risk gates before R04 checks."""
        if not self._a02_decision_gate_enabled:
            return True, ""

        engine = self.trading_engine
        if engine is None:
            return True, ""

        gate_fn = getattr(engine, "_run_decision_flow_pipeline", None)
        if gate_fn is None:
            return True, ""

        strategy_id = str(
            order.get("strategy_id")
            or order.get("strategy")
            or order.get("source")
            or "live_engine"
        )
        side = str(order.get("side") or order.get("action") or "buy").strip().lower()
        action = "SELL" if side.startswith("sell") else "BUY"
        signal = {
            "symbol": order.get("symbol"),
            "action": action,
            "quantity": int(order.get("quantity", 0) or 0),
            "price": order.get("price") or order.get("limit_price"),
            "strategy_type": strategy_id,
            "metadata": {
                "strategy_id": strategy_id,
                "strategy_type": strategy_id,
                "source": "R04_LiveEngine",
            },
        }

        try:
            gate_ok, gate_reason = gate_fn(strategy_id, signal, include_execution=False)
            if gate_ok:
                return True, ""
            return False, str(gate_reason)
        except Exception as exc:
            self.logger.warning("A02 decision-flow preflight failed open: %s", exc)
            return True, ""

    # A24 (v14): fields whose change requires a full restart, not a reload.
    _STRUCTURAL_CONFIG_FIELDS: frozenset = frozenset({"account_id", "env", "environment"})

    def _register_hot_reload_callback(self) -> None:
        try:
            from Tradov.TradovA_Core.TradovA03_Configuration import (
                get_config_manager,
            )
            cfg_mgr = get_config_manager()
            if cfg_mgr is not None:
                cfg_mgr.register_callback("*", self._on_config_reload)
                self.logger.debug("R04: registered A03 hot-reload callback")
        except Exception as exc:
            # Non-fatal — config hot-reload is optional.
            self.logger.debug("R04: hot-reload registration skipped: %s", exc)

    def _on_config_reload(self, key: str, old_value: Any, new_value: Any) -> None:
        """A24 (v14): apply a config change, refusing structural fields.

        Logged regardless of whether the value is honored so an operator
        reading the R04 log sees every config event.
        """
        if key in self._STRUCTURAL_CONFIG_FIELDS:
            self.logger.error(
                "R04: refusing hot-reload of structural field %s "
                "(old=%s new=%s) — restart required",
                key, old_value, new_value,
            )
            return
        self.logger.info(
            "R04: config hot-reload %s: %s -> %s", key, old_value, new_value
        )
        # Apply known runtime-safe fields onto self.config dataclass (best-effort).
        for attr in (
            "max_daily_trades",
            "max_daily_loss",
            "max_position_size",
            "high_risk_threshold_usd",
            "close_positions_on_emergency",
            "enable_extended_hours",
        ):
            if key == attr and hasattr(self.config, attr):
                try:
                    setattr(self.config, attr, new_value)
                except Exception as exc:
                    self.logger.error(
                        "R04: failed to apply reload for %s: %s", attr, exc
                    )

    # ==========================================================================
    # PUBLIC METHODS - LIFECYCLE
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize the live engine.

        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.debug("Initializing live engine...")

            # Verify broker connection
            if not self._verify_broker_connection():
                self.logger.error("Broker connection failed")
                return False

            # Verify account access
            if not self._verify_account_access():
                self.logger.error("Account access verification failed")
                return False

            # Load current positions
            self._load_current_positions()

            # Initialize safety systems
            self._initialize_safety_systems()

            # Start monitoring thread
            self._start_monitoring()

            self.state = ExecutionState.CONNECTED
            self.logger.debug("Live engine initialized successfully")
            return True

        except Exception as e:
            self.logger.error("Initialization failed: %s", e)
            self.state = ExecutionState.ERROR
            return False

    def start_trading(self) -> bool:
        """
        Start live trading operations.

        Returns:
            bool: True if started successfully
        """
        try:
            if self.state != ExecutionState.CONNECTED:
                self.logger.error("Cannot start trading from state %s", self.state)
                return False

            # Perform pre-trading checks
            pre_trading_blockers = self._get_pre_trading_blockers()
            allow_after_hours_paper_session = (
                self.mode == TradingMode.PAPER
                and pre_trading_blockers == ["market_closed"]
            )
            if pre_trading_blockers and not allow_after_hours_paper_session:
                mode_label = "Paper" if self._mode_name() == "paper" else "Live"
                self.logger.error("%s pre-trading checks failed", mode_label)
                return False
            if allow_after_hours_paper_session:
                self.logger.debug(
                    "Paper trading session activated after hours; market-hours policy still gates new entries"
                )

            # Create trading session
            self.current_session = TradingSession(
                session_id=self._generate_session_id(), start_time=datetime.now(_ET), mode=self.mode
            )

            # Enable order processing
            self.state = ExecutionState.TRADING

            # Log trading start
            mode_label = "Paper" if self._mode_name() == "paper" else "Live"
            self.logger.debug("%s trading started - Session: %s", mode_label, self.current_session.session_id)  # noqa: E501

            # Emit trading started event
            self._emit_event(
                "live_trading_started",
                {
                    "session_id": self.current_session.session_id,
                    "account_id": self.config.account_id,
                    "mode": self.mode.value,
                },
            )

            return True

        except Exception as e:
            self.logger.error("Failed to start trading: %s", e)
            return False

    def stop_trading(self, reason: str = "User requested") -> bool:
        """
        Stop live trading operations.

        Args:
            reason: Reason for stopping

        Returns:
            bool: True if stopped successfully
        """
        try:
            self.logger.info("Stopping live trading: %s", reason)

            if self.state not in [ExecutionState.TRADING, ExecutionState.PAUSED]:
                self.logger.warning("Not in trading state: %s", self.state)
                return False

            # Set closing state
            self.state = ExecutionState.CLOSING

            # Cancel all pending orders
            self._cancel_all_pending_orders()

            # Close trading session
            if self.current_session:
                self.current_session.end_time = datetime.now(_ET)
                self._save_session_data()

            # Stop order processing
            self.state = ExecutionState.STOPPED

            # Emit trading stopped event
            self._emit_event(
                "live_trading_stopped",
                {
                    "session_id": self.current_session.session_id if self.current_session else None,
                    "reason": reason,
                    "final_pnl": self.current_session.total_pnl if self.current_session else 0,
                },
            )

            mode_label = "Paper" if self._mode_name() == "paper" else "Live"
            self.logger.info("%s trading stopped successfully", mode_label)
            return True

        except Exception as e:
            self.logger.error("Error stopping trading: %s", e)
            return False

    def pause_trading(self) -> bool:
        """
        Pause trading operations.

        Returns:
            bool: True if paused successfully
        """
        if self.state == ExecutionState.TRADING:
            self.state = ExecutionState.PAUSED
            self.logger.info("Trading paused")
            return True
        return False

    def resume_trading(self) -> bool:
        """
        Resume trading operations.

        Returns:
            bool: True if resumed successfully
        """
        if self.state == ExecutionState.PAUSED:
            self.state = ExecutionState.TRADING
            self.logger.info("Trading resumed")
            return True
        return False

    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            # Stop monitoring
            if self.monitor_thread:
                self.stop_event.set()
                self.monitor_thread.join(timeout=5)

            # Close broker connection
            if self.broker:
                disconnect = getattr(self.broker, "disconnect", None)
                if callable(disconnect):
                    disconnect()
                else:
                    # TradierClient currently exposes requests session directly.
                    session = getattr(self.broker, "session", None)
                    if session is not None and hasattr(session, "close"):
                        session.close()

            self.logger.info("Live engine cleanup completed")

        except Exception as e:
            self.logger.error("Error during cleanup: %s", e)

    def stop(self) -> None:
        """Lifecycle adapter used by SessionSupervisor shutdown.

        Ensures trading is stopped (if active), monitor threads are joined,
        and broker connections are closed via ``cleanup()``.
        """
        try:
            if self.state in (ExecutionState.TRADING, ExecutionState.PAUSED):
                self.stop_trading(reason="SessionSupervisor shutdown")
        except Exception as exc:
            self.logger.warning("LiveEngine.stop(): stop_trading failed: %s", exc)
        finally:
            self.cleanup()

    # ==========================================================================
    # PUBLIC METHODS - ORDER EXECUTION
    # ==========================================================================
    def set_session_db(self, db: Any) -> None:
        """Inject a TradingSessionDB (H05) instance for live-trade persistence.

        Called by R12 SessionSupervisor after engine construction so that every
        confirmed fill is written to ``data/tradov_live.db`` using the same
        schema as the paper database (``data/tradov_paper.db``).

        Args:
            db: A ``TradingSessionDB`` instance (from TradovH05_TradingSessionDB).
        """
        self._session_db = db

        get_open_positions = getattr(db, "get_open_positions", None)
        if self._mode_name() != "paper" or not callable(get_open_positions):
            return

        try:
            get_active_open_positions = getattr(db, "get_active_paper_open_positions", None)
            has_active_session_marker = getattr(db, "has_active_paper_session_marker", None)
            get_resume_eligible = getattr(db, "get_resume_eligible_open_positions", None)
            if callable(get_active_open_positions) and callable(has_active_session_marker) and has_active_session_marker():
                open_positions = get_active_open_positions()
            elif callable(get_resume_eligible):
                open_positions = get_resume_eligible()
            else:
                open_positions = get_open_positions()
        except Exception as exc:
            self.logger.warning("Paper position hydration from H05 failed: %s", exc)
            return

        if not isinstance(open_positions, list):
            return

        hydrated_positions: dict[str, Any] = {}
        for position in open_positions:
            if not isinstance(position, dict):
                continue
            symbol = str(position.get("symbol") or "").strip()
            if not symbol:
                continue
            try:
                quantity = int(position.get("quantity") or 0)
            except (TypeError, ValueError):
                quantity = 0
            if quantity == 0:
                continue
            hydrated_position = dict(position)
            hydrated_position.setdefault("position_source", "session_db_hydration")
            hydrated_positions[symbol] = hydrated_position

        if not hydrated_positions:
            return

        hydrated_positions = self._normalize_paper_option_positions(hydrated_positions)

        with self._active_positions_lock:
            if self.active_positions:
                return
            self.active_positions.update(hydrated_positions)

        self.logger.info(
            "Hydrated %s active positions from session DB for paper mode",
            len(hydrated_positions),
        )

        # Seed B03 (PositionTracker) so that close fills received before any
        # new fills are netted correctly instead of creating phantom longs.
        # Only primes symbols that B03 does not already have a fill record for.
        pt = self._position_tracker
        if pt is not None:
            try:
                tracker_positions = getattr(pt, "positions", None)
                tracker_lock = (
                    getattr(pt, "_position_lock", None) or getattr(pt, "lock", None)
                )
                if isinstance(tracker_positions, dict) and tracker_lock is not None:
                    with tracker_lock:
                        for sym, pos in hydrated_positions.items():
                            if sym in tracker_positions:
                                continue
                            qty = int(pos.get("quantity") or 0)
                            if qty == 0:
                                continue
                            tracker_positions[sym] = {
                                "symbol": sym,
                                "quantity": qty,
                                "average_fill_price": float(
                                    pos.get("entry_price") or 0.0
                                ),
                                "strategy_id": str(
                                    pos.get("strategy_id") or pos.get("strategy") or ""
                                ),
                                "strategy": str(pos.get("strategy") or ""),
                                "strategy_name": str(pos.get("strategy") or ""),
                            }
                    self.logger.info(
                        "Seeded B03 PositionTracker from %s hydrated paper positions",
                        len(hydrated_positions),
                    )
            except Exception as exc:
                self.logger.warning(
                    "Failed to seed B03 from H05 hydration: %s", exc
                )

        # Seed _realized_pnl_total from today's H05 trade history so that the
        # first account snapshot after a restart reflects previously-realized
        # P&L rather than resetting to $0.
        if self._realized_pnl_total == 0.0:
            try:
                pnl_summary_fn = getattr(db, "get_pnl_summary", None)
                if callable(pnl_summary_fn):
                    pnl_today = float(pnl_summary_fn().get("today", 0.0))
                    if pnl_today != 0.0:
                        self._realized_pnl_total = pnl_today
                        self.logger.info(
                            "Seeded _realized_pnl_total=%.2f from H05 today's trade history",
                            pnl_today,
                        )
            except Exception as exc:
                self.logger.warning("Failed to seed realized P&L from H05: %s", exc)

    def update_regime_metrics(self, metrics: dict[str, Any]) -> None:
        """Receive a fresh S07 CustomMetricsOrchestrator snapshot.

        Called by the metrics orchestrator on each update tick so the live
        engine has access to SWAN, GEX, and DIX for regime gating — the same
        data the paper engine (R08) uses.

        Args:
            metrics: Dict of metric name → value or {"value": ..., ...} entry.
        """
        self._regime_metrics = metrics

    @staticmethod
    def _regime_scalar(entry: Any) -> float | None:
        """Extract a numeric scalar from an S07 metric entry (dict or raw)."""
        if entry is None:
            return None
        if isinstance(entry, dict):
            entry = entry.get("value")
        try:
            return float(entry)
        except (TypeError, ValueError):
            return None

    def _regime_allows_entry(self) -> tuple[bool, str]:
        """Check whether the current regime permits opening a new position.

        Blocks entries when the SWAN tail-risk index reaches the configured
        threshold (default 2.0).  Returns ``(allowed, reason)``; reason is
        an empty string when the entry is allowed.
        """
        swan = self._regime_scalar(self._regime_metrics.get("SWAN"))
        try:
            if swan is not None and swan >= SWAN_BLOCK_THRESHOLD:
                return False, f"SWAN={swan:.2f} >= {SWAN_BLOCK_THRESHOLD} (extreme tail-risk regime)"  # noqa: E501
        except (TypeError, ValueError):
            pass
        return True, ""

    @staticmethod
    def _is_risk_reducing_order(order: dict[str, Any] | None) -> bool:
        """Return True when an order explicitly closes or reduces existing risk."""
        if not isinstance(order, dict):
            return False

        action = str(
            order.get("action")
            or order.get("side")
            or ""
        ).strip().lower()
        return action in {
            "close",
            "exit",
            "flatten",
            "reduce",
            "de_risk",
            "buy_to_close",
            "sell_to_close",
            "btc",
            "stc",
        }

    def _resolve_order_side(self, order: dict[str, Any] | None) -> str:
        """Canonicalize close-side tokens before queueing or replaying fills."""
        if not isinstance(order, dict):
            return "buy"

        symbol = str(order.get("symbol") or "").strip()
        side = str(order.get("side") or order.get("action") or "buy").strip().lower().replace("-", "_")
        action = str(order.get("action") or "").strip().lower().replace("-", "_")
        is_option = self._is_option_symbol(symbol)

        if action in {"close", "exit", "flatten", "reduce", "de_risk"}:
            if side in {"buy", "buy_to_close", "btc"}:
                return "buy_to_close" if is_option else "buy"
            if side in {"sell", "sell_to_close", "stc"}:
                return "sell_to_close" if is_option else "sell"

        if side != "close":
            return side

        tracked_candidates: list[Any] = []
        if symbol:
            with self._active_positions_lock:
                active_position = self.active_positions.get(symbol)
            if active_position is not None:
                tracked_candidates.append(active_position)

            position_tracker = getattr(self, "_position_tracker", None) or getattr(self, "position_tracker", None)
            if position_tracker is not None and hasattr(position_tracker, "get_position"):
                try:
                    tracked_position = position_tracker.get_position(symbol)
                except Exception:
                    tracked_position = None
                if tracked_position is not None:
                    tracked_candidates.append(tracked_position)

        for candidate in tracked_candidates:
            raw_quantity = candidate.get("quantity") if isinstance(candidate, dict) else getattr(candidate, "quantity", None)
            try:
                quantity = float(raw_quantity or 0.0)
            except (TypeError, ValueError):
                continue
            if quantity > 0:
                return "sell_to_close" if is_option else "sell"
            if quantity < 0:
                return "buy_to_close" if is_option else "buy"

        return side

    def _regime_preferred_direction(self) -> str | None:
        """Infer a preferred spread direction from the S07 regime snapshot.

        Heuristic (mirrors R08 paper engine):
        - DIX > 0.45 → hidden bullish accumulation → ``"bullish"``
        - DIX < 0.35 → hidden distribution → ``"bearish"``
        - GEX > 0 and SWAN < 1.0 → range-bound → ``"neutral"``
        - Otherwise → ``None``
        """
        dix = self._regime_scalar(self._regime_metrics.get("DIX"))
        gex = self._regime_scalar(self._regime_metrics.get("GEX"))
        swan = self._regime_scalar(self._regime_metrics.get("SWAN"))

        if dix is not None:
            if dix > 0.45:
                return "bullish"
            if dix < 0.35:
                return "bearish"

        if gex is not None and gex > 0 and (swan is None or swan < 1.0):
            return "neutral"

        return None

    def execute_order(self, order: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a live order.

        Args:
            order: Order details

        Returns:
            Execution result
        """
        try:
            # A19 (v14): Never mutate the caller's dict — strategies may retain
            # their order payload for logging and should not see our
            # engine-injected timestamp / order_id.
            order = dict(order)

            # O5 (v14): Stamp a correlation_id at the strategy→order boundary
            # so every downstream event (pending_orders entry, ORDER_SUBMITTED,
            # ORDER_FILLED via reconciler) can be linked back to the originating
            # strategy call. If the strategy already provided one, preserve it.
            order["correlation_id"] = order.get("correlation_id") or uuid.uuid4().hex
            risk_reducing_order = self._is_risk_reducing_order(order)

            # Check if trading is active
            if self.state != ExecutionState.TRADING:
                return {"status": "rejected", "reason": f"Trading not active: {self.state.value}"}

            # Optional A02 preflight gate bridge (Data->Regime->Strategy->Risk).
            if not risk_reducing_order:
                a02_ok, a02_reason = self._run_a02_decision_gate(order)
                if not a02_ok:
                    self.logger.warning("Live engine A02 gate blocked order: %s", a02_reason)
                    self._event_manager.emit(
                        EventType.RISK_VIOLATION,
                        {"symbol": order.get("symbol"), "reason": a02_reason},
                        source="LiveEngine.a02_decision_gate",
                    )
                    return {"status": "rejected", "reason": a02_reason}

                # Regime gate — SWAN / GEX / DIX (mirrors paper engine R08)
                regime_ok, regime_reason = self._regime_allows_entry()
                if not regime_ok:
                    self.logger.warning("Live engine regime gate blocked order: %s", regime_reason)
                    self._event_manager.emit(
                        EventType.RISK_VIOLATION,
                        {"symbol": order.get("symbol"), "reason": regime_reason},
                        source="LiveEngine.regime_gate",
                    )
                    return {"status": "rejected", "reason": regime_reason}

                # Perform safety checks
                safety_result = self._perform_order_safety_checks(order)
                if safety_result.result == SafetyCheckResult.FAILED:
                    self._event_manager.emit(
                        EventType.RISK_VIOLATION,
                        {"symbol": order.get("symbol"), "reason": safety_result.message},
                        source="LiveEngine",
                    )
                    return {
                        "status": "rejected",
                        "reason": safety_result.message,
                        "safety_check": safety_result,
                    }

            # Smart confirmation: only for development mode or high-risk orders
            if self.mode == TradingMode.LIVE and not risk_reducing_order:
                confirmation_result = self._check_order_confirmation_required(order)
                if confirmation_result['requires_confirmation']:
                    confirmed = self._request_order_confirmation(order, confirmation_result['reason'])  # noqa: E501
                    if not confirmed:
                        self.logger.warning("Order %s rejected: %s", order.get('symbol'), confirmation_result['reason'])  # noqa: E501
                        return {
                            "status": "rejected",
                            "reason": f"Order requires confirmation: {confirmation_result['reason']}",  # noqa: E501
                            "confirmation_declined": True,
                            "confirmation_reason": confirmation_result['reason']
                        }
                else:
                    # Autonomous mode - log and proceed
                    self.logger.info("Order %s proceeding autonomously (confirmation not required)", order.get('symbol'))  # noqa: E501

            order["side"] = self._resolve_order_side(order)

            # Add to order queue
            order["timestamp"] = datetime.now(_ET)
            order["order_id"] = self._generate_order_id()
            # P0-10: Prune stale entries before registering a new one.
            self._gc_pending_orders()
            # Pre-register a Future so _execute_order_internal can signal
            # completion without a poll loop.
            _fut: concurrent.futures.Future = concurrent.futures.Future()
            with self._pending_orders_lock:  # B4: thread-safe registration
                self.pending_orders[order["order_id"]] = {
                    "order": order,
                    "result": None,
                    "future": _fut,
                    "submitted_at": datetime.now(_ET),  # B4: tz-aware for GC comparison
                }
            self.order_queue.put(order)

            # Wait for execution result
            result = self._wait_for_execution(order["order_id"])

            # Update metrics
            self._update_execution_metrics(order, result)

            return result

        except Exception as e:
            self.logger.error("Order execution error: %s", e)
            return {"status": "error", "reason": str(e)}

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.

        Args:
            order_id: Order ID to cancel

        Returns:
            bool: True if cancelled successfully
        """
        # B1 (v15): snapshot presence under lock before any broker I/O to
        # eliminate the TOCTOU window and concurrent-pop KeyError.
        with self._pending_orders_lock:
            if order_id not in self.pending_orders:
                return False
        try:
            # Broker call is deliberately outside the lock — it can block.
            result = self.broker.cancel_order(order_id)
            if result:
                with self._pending_orders_lock:
                    self.pending_orders.pop(order_id, None)  # safe if already gone
                self.logger.info("Order %s cancelled", order_id)
            return result
        except Exception as e:
            self.logger.error("Error cancelling order %s: %s", order_id, e)
            return False

    def get_execution_status(self) -> dict[str, Any]:
        """
        Get current execution status.

        Returns:
            Status information
        """
        # B5 (v15): snapshot counts under their respective locks to avoid
        # reading partially-updated dicts from a concurrent monitor thread.
        with self._pending_orders_lock:
            pending_count = len(self.pending_orders)
        with self._active_positions_lock:
            positions_count = len(self.active_positions)
        return {
            "state": self.state.value,
            "mode": self.mode.value,
            "emergency_stop": self.emergency_stop,
            "session": {
                "id": self.current_session.session_id if self.current_session else None,
                "trades": self.current_session.trades_executed if self.current_session else 0,
                "pnl": self.current_session.total_pnl if self.current_session else 0,
            },
            "daily_stats": {
                "trades": self.daily_trades,
                "loss": self.daily_loss,
                "limit_reached": self.daily_trades >= self.config.max_daily_trades,
            },
            "pending_orders": pending_count,
            "active_positions": positions_count,
            "metrics": {
                "success_rate": self.metrics.successful_executions
                / max(1, self.metrics.total_orders),
                "avg_fill_time": self.metrics.average_fill_time,
                "avg_slippage": self.metrics.average_slippage,
            },
        }

    # ==========================================================================
    # PUBLIC METHODS - EMERGENCY CONTROLS
    # ==========================================================================
    def emergency_stop_all(self, reason: str) -> bool:
        """
        Emergency stop all trading activities.

        Args:
            reason: Reason for emergency stop

        Returns:
            bool: True if stopped successfully
        """
        try:
            self.logger.critical("EMERGENCY STOP INITIATED: %s", reason)

            # Set emergency stop flag
            self.emergency_stop = True
            self.mode = TradingMode.EMERGENCY_STOP

            # Cancel ALL orders immediately
            self._emergency_cancel_all_orders()

            # Close all positions if configured
            if self.config.close_positions_on_emergency:
                self._emergency_close_all_positions()

            # Stop trading
            self.stop_trading(f"Emergency: {reason}")

            # Send alerts
            self._send_emergency_alerts(reason)

            return True

        except Exception as e:
            self.logger.critical("Emergency stop failed: %s", e)
            return False

    def record_api_server_error(self) -> None:
        """
        Record one Tradier 5xx (server-side) error.

        Call this whenever the broker layer raises TradierServerError after
        all retries are exhausted.  If the count reaches API_PANIC_THRESHOLD
        the engine enters API Panic Mode: no new entries are accepted and all
        open positions are closed per close_positions_on_emergency.
        Auto-resets when reset_api_error_count() is called on success.
        """
        self._api_error_count += 1
        self.logger.warning(
            "Tradier API server error #%d (threshold=%d)",
            self._api_error_count, API_PANIC_THRESHOLD,
        )
        if self._api_error_count >= API_PANIC_THRESHOLD and not self._api_panic_mode:
            self._api_panic_mode = True
            self.emergency_stop_all(
                f"Tradier API unreachable - {self._api_error_count} consecutive 5xx errors"
            )

    def reset_api_error_count(self) -> None:
        """Reset the consecutive 5xx counter after a successful broker call."""
        if self._api_error_count > 0:
            self.logger.info(
                "Tradier API recovered — resetting error count (was %d)",
                self._api_error_count,
            )
        self._api_error_count = 0
        self._api_panic_mode = False

    # ==========================================================================
    # PRIVATE METHODS - INITIALIZATION
    # ==========================================================================
    def _verify_broker_connection(self) -> bool:
        """Verify broker connection is active."""
        try:
            # Support both broker interfaces:
            # 1) Paper-like adapters exposing is_connected()/get_account_info()
            # 2) TradierClient exposing account/balance endpoints directly
            connected_ok = True
            if hasattr(self.broker, "is_connected") and callable(getattr(self.broker, "is_connected")):  # noqa: B009, E501
                connected_ok = bool(self.broker.is_connected())

            account_ok = False
            if hasattr(self.broker, "get_account_info") and callable(getattr(self.broker, "get_account_info")):  # noqa: B009, E501
                account_ok = self.broker.get_account_info() is not None
            elif hasattr(self.broker, "get_account_balances") and callable(getattr(self.broker, "get_account_balances")):  # noqa: B009, E501
                balances = self.broker.get_account_balances()
                account_ok = bool(balances)

            return connected_ok and account_ok
        except Exception:
            return False

    def _verify_account_access(self) -> bool:
        """Verify account access and permissions."""
        try:
            if hasattr(self.broker, "get_account_info") and callable(getattr(self.broker, "get_account_info")):  # noqa: B009, E501
                account_info = self.broker.get_account_info()
                if account_info is None:
                    return False
                account_id = account_info.get("account_id")
                if account_id is None:
                    account_id = (
                        account_info.get("account", {}).get("account_id")
                        if isinstance(account_info.get("account"), dict)
                        else None
                    )
                trading_enabled = account_info.get("trading_enabled", True)
                return account_id == self.config.account_id and bool(trading_enabled)

            # Tradier compatibility path: successful balance call + matching client
            # account id implies credentials and account access are valid.
            if hasattr(self.broker, "get_account_balances") and callable(getattr(self.broker, "get_account_balances")):  # noqa: B009, E501
                balances = self.broker.get_account_balances()
                broker_account_id = getattr(self.broker, "account_id", None)
                return bool(balances) and broker_account_id == self.config.account_id

            return False
        except Exception:
            return False

    def _load_current_positions(self):
        """Load current positions from broker."""
        try:
            positions = self.broker.get_positions()
            # Tradier may return nested payloads:
            # {"positions": {"position": [...]}} or {"positions": {"position": {...}}}
            if isinstance(positions, dict):
                positions_field = positions.get("positions")
                if isinstance(positions_field, dict):
                    raw_positions = positions_field.get("position")
                elif positions_field in (None, "null"):
                    raw_positions = []
                else:
                    raw_positions = positions_field
                if isinstance(raw_positions, list):
                    positions = raw_positions
                elif isinstance(raw_positions, dict):
                    positions = [raw_positions]
                elif raw_positions in (None, "null"):
                    positions = []
                else:
                    positions = []
            if not isinstance(positions, list):
                self.logger.error(
                    "_load_current_positions: broker returned non-list: %r", type(positions)
                )
                return
            # B2 (v15): update in-place under lock instead of replacing the object.
            # Replacing the object (self.active_positions = {...}) defeats the
            # _active_positions_lock because any thread already holding a reference
            # to the old dict continues to see stale data and concurrent writes are
            # lost.
            with self._active_positions_lock:
                existing_positions = {
                    symbol: dict(position)
                    for symbol, position in self.active_positions.items()
                    if isinstance(position, dict)
                }
            new_map = {
                p["symbol"]: self._merge_active_position_metadata(
                    existing_positions.get(p["symbol"]),
                    p,
                )
                for p in positions
            }
            with self._active_positions_lock:
                self.active_positions.clear()
                self.active_positions.update(new_map)
            if self._mode_name() == "paper" and getattr(self, "_session_db", None) is None:
                self.logger.debug(
                    "Loaded %s broker-reported active positions during paper bootstrap",
                    len(self.active_positions),
                )
            else:
                self.logger.debug(
                    "Loaded %s broker-reported active positions",
                    len(self.active_positions),
                )
        except Exception as e:
            self.logger.error("Failed to load positions: %s", e)

    def _initialize_safety_systems(self):
        """Initialize all safety systems."""
        # Register safety checks
        self.safety_checks = []

        # Daily limits
        self._register_safety_check("daily_trade_limit", self._check_daily_trade_limit)
        self._register_safety_check("daily_loss_limit", self._check_daily_loss_limit)

        # Position limits
        self._register_safety_check("position_size", self._check_position_size_limit)
        self._register_safety_check("portfolio_exposure", self._check_portfolio_exposure)

        # Market conditions
        self._register_safety_check("market_hours", self._check_market_hours)
        self._register_safety_check("volatility", self._check_market_volatility)

    # ==========================================================================
    # PRIVATE METHODS - MONITORING
    # ==========================================================================
    def _start_monitoring(self):
        """Start monitoring thread."""
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop, name="LiveEngineMonitor"
        )
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def _monitoring_loop(self):
        """Main monitoring loop."""
        while not self.stop_event.is_set():
            try:
                # Process order queue
                self._process_order_queue()

                # Monitor positions
                self._monitor_positions()

                # Check heartbeat
                self._check_heartbeat()

                # Perform periodic safety checks
                if self.state == ExecutionState.TRADING:
                    self._perform_periodic_safety_checks()

                # Sleep
                self.stop_event.wait(1)

            except Exception as e:
                self.logger.error("Monitoring error: %s", e)

    def _process_order_queue(self):
        """Process orders from queue."""
        while not self.order_queue.empty():
            try:
                order = self.order_queue.get_nowait()
                self._execute_order_internal(order)
            except queue.Empty:
                break
            except Exception as e:
                self.logger.error("Error processing order: %s", e)

    def _get_positions_cached(self) -> list[Any]:
        """A16 (v14): TTL-cached wrapper over ``broker.get_positions()``.

        The monitor tick fires every second; without this the engine burns a
        broker round-trip per tick. Cache is invalidated on every fill so new
        positions surface immediately rather than after the TTL elapses.
        """
        # ``time`` is shadowed by ``datetime.time`` at module scope, so use the
        # already-standard ``datetime.now(timezone.utc).timestamp()`` pattern for elapsed math.
        now = datetime.now(_ET).timestamp()
        with self._positions_cache_lock:
            if (
                self._positions_cache is not None
                and (now - self._positions_cache_at) < POSITIONS_CACHE_TTL
            ):
                return self._positions_cache
        positions = self.broker.get_positions()
        if isinstance(positions, dict):
            positions_field = positions.get("positions")
            if isinstance(positions_field, dict):
                raw_positions = positions_field.get("position")
            elif positions_field in (None, "null"):
                raw_positions = []
            else:
                raw_positions = positions_field
            if isinstance(raw_positions, list):
                positions = raw_positions
            elif isinstance(raw_positions, dict):
                positions = [raw_positions]
            elif raw_positions in (None, "null"):
                positions = []
            else:
                positions = []
        elif not isinstance(positions, list):
            positions = []
        with self._positions_cache_lock:
            self._positions_cache = positions
            self._positions_cache_at = datetime.now(_ET).timestamp()
        return positions

    def _invalidate_positions_cache(self) -> None:
        """Drop the cached positions snapshot so the next call hits the broker."""
        with self._positions_cache_lock:
            self._positions_cache = None
            self._positions_cache_at = 0.0

    def _monitor_positions(self):
        """Monitor active positions."""
        try:
            # A16 (v14): TTL-cached broker call — invalidated on every fill.
            positions = self._get_positions_cached()

            # A1 (v14): guard writes; _should_trigger_stop_loss is pure on its
            # arg so it can run outside the lock. _execute_stop_loss calls the
            # broker and must not hold the lock.
            with self._active_positions_lock:
                for position in positions:
                    symbol = position["symbol"]
                    self.active_positions[symbol] = self._merge_active_position_metadata(
                        self.active_positions.get(symbol),
                        position,
                    )

            if self._mode_name() == "paper":
                positions = self._mark_paper_positions_to_market()

            for position in positions:
                if self._should_trigger_stop_loss(position):
                    self._execute_stop_loss(position)

        except Exception as e:
            self.logger.error("Position monitoring error: %s", e)

    def get_active_positions_snapshot(self) -> dict[str, Any]:
        """A1 (v14): thread-safe deep copy of active_positions for readers.

        Strategy-side readers that need a consistent view should call this
        instead of reading ``self.active_positions`` directly.
        """
        import copy
        with self._active_positions_lock:
            return copy.deepcopy(self.active_positions)

    @staticmethod
    def _merge_active_position_metadata(
        existing: dict[str, Any] | None,
        incoming: dict[str, Any],
    ) -> dict[str, Any]:
        """Preserve carryover and strategy metadata across position refreshes."""
        merged = dict(incoming)
        if not isinstance(existing, dict):
            return merged

        for key in (
            "position_source",
            "_paper_open_origin",
            "strategy_id",
            "strategy",
            "strategy_name",
            "strategy_type",
            "pair_key",
            "opened_at",
            "order_id",
            "underlying_symbol",
            "expiration",
            "strike",
            "option_type",
        ):
            if merged.get(key) in (None, "") and existing.get(key) not in (None, ""):
                merged[key] = existing.get(key)

        return merged

    @staticmethod
    def _normalize_strategy_type(value: Any) -> str:
        return str(value or "").strip().lower()

    @classmethod
    def _extract_trade_identity(cls, payload: dict[str, Any] | None) -> tuple[str, str, str, str]:
        """Extract a stable trade identity from an order or position payload."""
        if not isinstance(payload, dict):
            return "", "", "", ""

        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        strategy_id = str(
            payload.get("strategy_id")
            or payload.get("strategy")
            or payload.get("strategy_name")
            or metadata.get("strategy_id")
            or metadata.get("strategy")
            or metadata.get("strategy_name")
            or ""
        ).strip()
        strategy_type = cls._normalize_strategy_type(
            payload.get("strategy_type")
            or metadata.get("strategy_type")
            or payload.get("pair_key")
            or metadata.get("pair_key")
            or payload.get("strategy")
            or metadata.get("strategy")
            or payload.get("strategy_name")
            or metadata.get("strategy_name")
        )
        pair_key = str(payload.get("pair_key") or metadata.get("pair_key") or "").strip()
        slot_kind = "pair" if pair_key or "pair" in strategy_type else "directional"
        slot_id = pair_key if slot_kind == "pair" and pair_key else strategy_id
        return strategy_id, strategy_type, slot_kind, slot_id

    def _collect_live_trade_slots(self) -> dict[str, set[str]]:
        """Collect currently live trade slots split by pair and directional types."""
        pair_slots: set[str] = set()
        directional_slots: set[str] = set()

        with self._pending_orders_lock:
            pending_orders = [
                entry.get("order")
                for entry in self.pending_orders.values()
                if isinstance(entry, dict) and isinstance(entry.get("order"), dict)
            ]

        with self._active_positions_lock:
            active_positions = [
                position
                for position in self.active_positions.values()
                if isinstance(position, dict)
            ]

        for payload in (*pending_orders, *active_positions):
            strategy_id, _, slot_kind, slot_id = self._extract_trade_identity(payload)
            if slot_kind == "pair":
                if slot_id:
                    pair_slots.add(slot_id)
                elif strategy_id:
                    pair_slots.add(strategy_id)
                continue

            if strategy_id:
                directional_slots.add(strategy_id)

        return {
            "pair": pair_slots,
            "directional": directional_slots,
        }

    def _project_live_trade_slots(self, order: dict[str, Any]) -> dict[str, set[str]]:
        """Project live slot counts after admitting one additional order."""
        live_slots = self._collect_live_trade_slots()
        projected = {
            "pair": set(live_slots["pair"]),
            "directional": set(live_slots["directional"]),
        }

        _, _, slot_kind, slot_id = self._extract_trade_identity(order)
        if slot_kind == "pair":
            if slot_id:
                projected["pair"].add(slot_id)
        elif order.get("strategy_id") or order.get("strategy") or order.get("strategy_name"):
            projected["directional"].add(
                str(
                    order.get("strategy_id")
                    or order.get("strategy")
                    or order.get("strategy_name")
                    or ""
                ).strip()
            )

        return projected

    def _check_heartbeat(self):
        """Check broker connection heartbeat."""
        now = datetime.now(_ET)
        # A18 (v14): .seconds drops sign + day overflow — use .total_seconds()
        # so a day-boundary tick or clock skew doesn't produce a wildly wrong
        # delta that silently suppresses the heartbeat call.
        if (now - self.last_heartbeat).total_seconds() > HEARTBEAT_INTERVAL:
            try:
                if self.broker.heartbeat():
                    self.last_heartbeat = now
                    self.broker_connected = True
                else:
                    self.broker_connected = False
                    self.logger.warning("Broker heartbeat failed")
            except Exception:
                self.broker_connected = False

    # ==========================================================================
    # PRIVATE METHODS - SAFETY CHECKS
    # ==========================================================================
    def _get_pre_trading_blockers(self) -> list[str]:
        """Return named blockers that prevent starting a trading session."""
        blockers: list[str] = []

        # Market hours check
        if not self._is_market_open():
            self.logger.debug("Market is not open")
            if not self.config.enable_extended_hours:
                blockers.append("market_closed")

        # Account balance check
        if hasattr(self.broker, "get_account_info") and callable(self.broker.get_account_info):
            account_info = self.broker.get_account_info() or {}
        elif hasattr(self.broker, "get_account_balances") and callable(self.broker.get_account_balances):
            raw = self.broker.get_account_balances()
            account_info = raw.get("balances", raw) if isinstance(raw, dict) else {}
        else:
            account_info = {}
        margin = account_info.get("margin", {}) if isinstance(account_info, dict) else {}
        buying_power = (
            account_info.get("buying_power")
            or margin.get("option_buying_power")
            or margin.get("stock_buying_power")
            or account_info.get("total_cash")
            or 0
        )
        is_paper = getattr(self, "mode", None) == TradingMode.PAPER
        if float(buying_power) < 1000 and not is_paper:
            self.logger.warning("Low buying power")
        elif float(buying_power) < 1000 and is_paper:
            self.logger.debug("Paper account buying power pre-sync: %.2f", float(buying_power))

        # Risk limits check
        if not self.risk_manager.check_daily_limits():
            self.logger.error("Risk limits already exceeded")
            blockers.append("risk_limits_exceeded")

        return blockers

    def _perform_pre_trading_checks(self) -> bool:
        """Perform pre-trading safety checks."""
        return len(self._get_pre_trading_blockers()) == 0

    def _perform_order_safety_checks(self, order: dict[str, Any]) -> SafetyCheck:
        """Perform safety checks on an order."""
        if self._is_risk_reducing_order(order):
            return SafetyCheck(
                check_name="risk_reducing_order",
                result=SafetyCheckResult.PASSED,
                message="Risk-reducing order bypasses entry-only safety gates",
                timestamp=datetime.now(_ET),
            )

        for option_symbol_key in ("symbol", "option_symbol"):
            option_symbol = str(order.get(option_symbol_key) or "").strip().upper()
            if not option_symbol or not self._is_option_symbol(option_symbol):
                continue

            option_details = self._parse_occ_option_symbol(option_symbol)
            if not option_details:
                continue

            option_underlying = str(option_details.get("underlying") or "").strip().upper()
            if option_underlying and option_underlying != "SPXW":
                return SafetyCheck(
                    check_name="spxw_only_option_entry_policy",
                    result=SafetyCheckResult.FAILED,
                    message=(
                        "SPXW-only option entry policy violation: "
                        f"{option_symbol_key}={option_symbol} underlying={option_underlying}"
                    ),
                    timestamp=datetime.now(_ET),
                )

        if self._would_flatten_multileg_strategy(order):
            strategy_id = order.get("strategy_id") or order.get("strategy") or "multi_leg"
            return SafetyCheck(
                check_name="multileg_dispatch",
                result=SafetyCheckResult.FAILED,
                message=(
                    f"Multi-leg option strategy {strategy_id} requires explicit "
                    "option-leg routing"
                ),
                timestamp=datetime.now(_ET),
            )

        projected_slots = self._project_live_trade_slots(order)
        projected_pair_trades = len(projected_slots["pair"])
        projected_directional_trades = len(projected_slots["directional"])
        projected_total_trades = projected_pair_trades + projected_directional_trades

        if projected_total_trades > self.config.max_live_trades:
            return SafetyCheck(
                check_name="live_trade_limit",
                result=SafetyCheckResult.FAILED,
                message=(
                    f"Live trade limit exceeded: {projected_total_trades}/"
                    f"{self.config.max_live_trades}"
                ),
                timestamp=datetime.now(_ET),
            )

        if projected_pair_trades > self.config.max_pair_trades:
            return SafetyCheck(
                check_name="pair_trade_limit",
                result=SafetyCheckResult.FAILED,
                message=(
                    f"Pair trade limit exceeded: {projected_pair_trades}/"
                    f"{self.config.max_pair_trades}"
                ),
                timestamp=datetime.now(_ET),
            )

        if projected_directional_trades > self.config.max_directional_trades:
            return SafetyCheck(
                check_name="directional_trade_limit",
                result=SafetyCheckResult.FAILED,
                message=(
                    f"Directional trade limit exceeded: {projected_directional_trades}/"
                    f"{self.config.max_directional_trades}"
                ),
                timestamp=datetime.now(_ET),
            )

        # Check daily trade limit
        if self.daily_trades >= self.config.max_daily_trades:
            return SafetyCheck(
                check_name="daily_trade_limit",
                result=SafetyCheckResult.FAILED,
                message="Daily trade limit reached",
                timestamp=datetime.now(_ET),
            )

        # Check position size
        if order.get("quantity", 0) > self.config.max_position_size:
            return SafetyCheck(
                check_name="position_size",
                result=SafetyCheckResult.FAILED,
                message="Position size exceeds limit",
                timestamp=datetime.now(_ET),
            )

        # Check market hours
        if not self._is_trading_allowed():
            return SafetyCheck(
                check_name="market_hours",
                result=SafetyCheckResult.FAILED,
                message="Trading not allowed at this time",
                timestamp=datetime.now(_ET),
            )

        return SafetyCheck(
            check_name="order_safety",
            result=SafetyCheckResult.PASSED,
            message="All checks passed",
            timestamp=datetime.now(_ET),
        )

    def _perform_periodic_safety_checks(self):
        """Perform periodic safety checks during trading."""
        # Check daily loss
        if self.daily_loss > self.config.max_daily_loss:
            self.logger.error("Daily loss limit exceeded")
            self.emergency_stop_all("Daily loss limit exceeded")

        # Check portfolio drawdown
        if self._calculate_portfolio_drawdown() > EMERGENCY_STOP_LOSS:
            self.logger.error("Emergency stop loss triggered")
            self.emergency_stop_all("Portfolio drawdown limit exceeded")

    # ==========================================================================
    # PRIVATE METHODS - HELPERS
    # ==========================================================================
    def _check_order_confirmation_required(self, order: dict[str, Any]) -> dict[str, Any]:
        """
        Determine if an order requires user confirmation.

        Confirmation is required in two scenarios:
        1. Development mode: REQUIRE_LIVE_ORDER_CONFIRMATION=true (all orders)
        2. High-risk orders: Exceeds $ threshold or % of portfolio (selective)

        Args:
            order: Order details

        Returns:
            Dict with:
                - requires_confirmation: bool
                - reason: str (why confirmation is needed)
                - risk_level: str (normal/high/critical)
        """
        try:
            # Development mode: require confirmation for ALL orders
            if self.config.require_confirmation:
                return {
                    'requires_confirmation': True,
                    'reason': 'Development mode - all orders require confirmation',
                    'risk_level': 'development'
                }

            # Production autonomous mode: selective confirmation for high-risk only
            if not self.config.high_risk_confirmation:
                # Fully autonomous - no confirmation ever
                return {
                    'requires_confirmation': False,
                    'reason': 'Fully autonomous mode',
                    'risk_level': 'normal'
                }

            # Check if order meets high-risk criteria
            order_value = self._calculate_order_value(order)

            # Get portfolio value for percentage check
            portfolio_value = self._get_portfolio_value()
            order_pct = order_value / portfolio_value if portfolio_value > 0 else 0

            reasons = []
            risk_level = 'normal'

            # Check absolute dollar threshold
            if order_value > self.config.high_risk_threshold_usd:
                reasons.append(f"Order value ${order_value:,.2f} exceeds threshold ${self.config.high_risk_threshold_usd:,.2f}")  # noqa: E501
                risk_level = 'high'

            # Check portfolio percentage threshold
            if order_pct > self.config.high_risk_portfolio_pct:
                reasons.append(f"Order represents {order_pct*100:.1f}% of portfolio (limit: {self.config.high_risk_portfolio_pct*100:.1f}%)")  # noqa: E501
                risk_level = 'critical' if order_pct > 0.5 else 'high'

            if reasons:
                return {
                    'requires_confirmation': True,
                    'reason': '; '.join(reasons),
                    'risk_level': risk_level,
                    'order_value': order_value,
                    'portfolio_pct': order_pct
                }

            # Normal order - proceed autonomously
            return {
                'requires_confirmation': False,
                'reason': 'Normal order within autonomous parameters',
                'risk_level': 'normal',
                'order_value': order_value,
                'portfolio_pct': order_pct
            }

        except Exception as e:
            self.logger.error("Error checking confirmation requirement: %s", e, exc_info=True)
            # Fail safe: require confirmation on error
            return {
                'requires_confirmation': True,
                'reason': f'Error evaluating risk: {str(e)}',
                'risk_level': 'error'
            }

    def _request_order_confirmation(self, order: dict[str, Any], reason: str) -> bool:
        """
        Request explicit user confirmation before executing a high-risk order.

        This method is ONLY called for:
        - Development mode (all orders)
        - High-risk orders exceeding thresholds

        Args:
            order: Order details to confirm
            reason: Why confirmation is required

        Returns:
            bool: True if confirmed, False if declined

        Note:
            In production autonomous mode, this should rarely be called.
            When called, it integrates with GUI/monitoring systems for approval.
        """
        try:
            # Log the confirmation request
            self.logger.warning("="*60)
            self.logger.warning("HIGH-RISK ORDER CONFIRMATION REQUIRED")
            self.logger.warning("="*60)
            self.logger.warning("Reason: %s", reason)
            self.logger.warning("Symbol: %s", order.get('symbol', 'N/A'))
            self.logger.warning("Side: %s", order.get('side', 'N/A'))
            self.logger.warning("Quantity: %s", order.get('quantity', 'N/A'))
            self.logger.warning("Order Type: %s", order.get('type', 'N/A'))
            self.logger.warning("Price: %s", order.get('price', 'MARKET'))
            self.logger.warning(f"Estimated Value: ${self._calculate_order_value(order):,.2f}")
            self.logger.warning("="*60)

            # Emit event for GUI/monitoring to display confirmation dialog
            self._emit_event('high_risk_order_confirmation_requested', {
                'order': order,
                'reason': reason,
                'timestamp': datetime.now(_ET).isoformat()
            })

            # Integration points:
            # 1. TradovJ05_TelegramBot — mobile push notification with APPROVE/REJECT inline keyboard  # noqa: E501
            # 2. TradovG09_RiskParametersDialog — GUI dialog (not applicable in headless/backend mode)  # noqa: E501
            confirm_timeout = int(os.environ.get('HIGH_RISK_CONFIRM_TIMEOUT_SECS', '60'))
            if self.telegram_bot is not None:
                try:
                    result = self.telegram_bot.send_confirmation_request(
                        order=order, reason=reason, timeout=confirm_timeout
                    )
                    if result is True:
                        self.logger.warning("High-risk order APPROVED by operator via Telegram.")
                        return True
                    if result is False:
                        self.logger.critical("High-risk order REJECTED by operator via Telegram.")
                        return False
                    # result is None → timed out; fall through to autonomous decision
                    self.logger.warning(
                        f"Telegram confirmation timed out after {confirm_timeout}s "
                        "— falling back to autonomous risk decision."
                    )
                except Exception as _tg_err:
                    self.logger.error(
                        "Telegram confirmation error: %s — falling back to autonomous decision.", _tg_err  # noqa: E501
                    )

            # Testing override (paper-mode only)
            if os.environ.get('AUTO_CONFIRM_HIGH_RISK_ORDERS', 'false').lower() == 'true':
                self.logger.warning("AUTO_CONFIRM_HIGH_RISK_ORDERS enabled — auto-approved (TESTING ONLY)")  # noqa: E501
                return True

            # Autonomous decision: delegate to the E-series risk engine
            approved = self._autonomous_risk_decision(order, reason)
            if approved:
                self.logger.warning("Autonomous risk assessment: APPROVED")
            else:
                self.logger.critical("Autonomous risk assessment: REJECTED — order blocked by risk engine")  # noqa: E501
            return approved

        except Exception as e:
            self.logger.error("Error requesting order confirmation: %s", e, exc_info=True)
            return False  # Fail safe: reject on error

    def _autonomous_risk_decision(self, order: dict[str, Any], reason: str) -> bool:
        """
        Make an autonomous approve/reject decision for a high-risk order using
        the E-series risk engine. Called instead of human/Telegram confirmation.

        Args:
            order:  Order details dict.
            reason: The trigger reason (e.g. "position size limit").

        Returns:
            True  — risk engine approves the order.
            False — risk engine rejects; order must not be submitted.
        """
        try:
            # --- 1. Check circuit breaker / daily limits via risk_manager ---
            if hasattr(self.risk_manager, 'check_daily_limits'):
                if not self.risk_manager.check_daily_limits():
                    self.logger.warning("Autonomous rejection: daily risk limits already exceeded.")
                    return False

            # --- 2. Check current risk metrics for drawdown / exposure ---
            if hasattr(self.risk_manager, 'get_risk_metrics'):
                metrics = self.risk_manager.get_risk_metrics()
                if metrics is not None:
                    # Reject if daily P&L loss exceeds 75 % of the configured maximum
                    max_daily = getattr(self.config, 'max_daily_loss', None)
                    if max_daily and hasattr(metrics, 'daily_pnl'):
                        if metrics.daily_pnl < -(abs(max_daily) * 0.75):
                            self.logger.warning(
                                f"Autonomous rejection: daily P&L {metrics.daily_pnl:.2f} "
                                f"approaching limit {max_daily:.2f}."
                            )
                            return False

            # --- 3. Favour rejection for explicit position-size violations ---
            trigger_lower = reason.lower()
            hard_blocks = ("position size", "daily loss", "exposure limit", "drawdown")
            if any(kw in trigger_lower for kw in hard_blocks):
                self.logger.warning(
                    "Autonomous rejection: hard-block trigger in reason: '%s'.", reason
                )
                return False

            # --- 4. All checks passed — approve ---
            self.logger.info(
                "Autonomous approval: no hard-block conditions triggered for reason '%s'.", reason
            )
            return True

        except Exception as e:
            self.logger.error("Autonomous risk decision error: %s", e, exc_info=True)
            return False  # Fail safe: reject on error

    def _calculate_order_value(self, order: dict[str, Any]) -> float:
        """
        Calculate the dollar value of an order.

        Args:
            order: Order details

        Returns:
            Estimated order value in USD
        """
        try:
            quantity = order.get('quantity', 0)
            price = order.get('price', 0)
            symbol = order.get('symbol', '')

            # For market orders, estimate using current market price
            if price == 0 or order.get('type', '').lower() == 'market':
                # Fetch current market price from broker
                try:
                    quotes = self.broker.get_quotes([symbol]) if symbol else {}
                    quote = quotes.get('quote', quotes) if isinstance(quotes, dict) else {}
                    if isinstance(quote, list) and quote:
                        quote = quote[0]
                    price = float(quote.get('last', 0) or quote.get('close', 0) or 0)
                except Exception:
                    self.logger.warning("Could not fetch live price for %s, using order price", symbol)  # noqa: E501
                if price == 0:
                    self.logger.warning("No price available for order value calculation on %s", symbol)  # noqa: E501
                    return 0.0

            # For options, multiply by contract multiplier (usually 100)
            multiplier = 100 if self._is_option_symbol(symbol) else 1

            return abs(quantity * price * multiplier)

        except Exception as e:
            self.logger.error("Error calculating order value: %s", e)
            return 0.0

    def _get_portfolio_value(self) -> float:
        """
        Get current portfolio value.

        Returns:
            Portfolio value in USD
        """
        try:
            # Get from broker interface — B40 uses get_account_balances(); B04 uses get_account_info()
            if hasattr(self.broker, "get_account_info") and callable(self.broker.get_account_info):
                account_info = self.broker.get_account_info() or {}
            elif hasattr(self.broker, "get_account_balances") and callable(self.broker.get_account_balances):
                raw = self.broker.get_account_balances()
                account_info = raw.get("balances", raw) if isinstance(raw, dict) else {}
            else:
                account_info = {}
            return float(account_info.get("total_equity", 0.0) or 0.0)
        except Exception as e:
            self.logger.error("Error getting portfolio value: %s", e)
            return 0.0

    def _is_option_symbol(self, symbol: str) -> bool:
        """
        Check if symbol is an option.

        Args:
            symbol: Symbol to check

        Returns:
            True if option symbol
        """
        # Options typically have format: TRAD240315C00450000
        return len(symbol) > 10 and any(c in symbol for c in ['C', 'P'])

    def _would_flatten_multileg_strategy(self, order: dict[str, Any]) -> bool:
        """Detect generic order submissions that would flatten multileg strategies."""
        if order.get("multileg_leg_execution"):
            return False

        symbol = str(order.get("symbol") or "").strip().upper()
        option_symbol = str(order.get("option_symbol") or "").strip().upper()
        if self._is_option_symbol(symbol) or self._is_option_symbol(option_symbol):
            return False

        strategy_candidates = [
            order.get("strategy_id"),
            order.get("strategy"),
            order.get("strategy_name"),
        ]
        normalized_candidates = {
            re.sub(r"[^a-z0-9]+", "_", str(candidate or "").strip().lower()).strip("_")
            for candidate in strategy_candidates
            if str(candidate or "").strip()
        }
        if not normalized_candidates:
            return False

        multileg_keywords = (
            "spread",
            "condor",
            "butterfly",
            "calendar",
            "straddle",
            "strangle",
            "lizard",
            "ratio",
        )
        return any(
            any(keyword in candidate for keyword in multileg_keywords)
            for candidate in normalized_candidates
        )

    @staticmethod
    def _parse_occ_option_symbol(symbol: str) -> dict[str, Any]:
        """Parse an OCC option symbol into underlying, expiration, strike, and type."""
        match = re.match(r"^([A-Z]{1,6})(\d{6})([CP])(\d{8})$", str(symbol or "").strip().upper())
        if not match:
            return {}
        try:
            expiration = datetime.strptime(match.group(2), "%y%m%d").date().isoformat()
        except ValueError:
            expiration = ""
        return {
            "underlying": match.group(1),
            "expiration": expiration,
            "strike": int(match.group(4)) / 1000.0,
            "option_type": "call" if match.group(3) == "C" else "put",
        }

    def _mode_name(self) -> str:
        """Return the normalized runtime trading mode name."""
        mode = getattr(self, "mode", None)
        value = getattr(mode, "value", mode)
        return str(value or "").lower()

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        prefix = "PAPER" if self._mode_name() == "paper" else "LIVE"
        return f"{prefix}_{datetime.now(_ET).strftime('%Y%m%d_%H%M%S')}"

    def _generate_order_id(self) -> str:
        """Generate unique order ID."""
        return f"ORD_{datetime.now(_ET).strftime('%Y%m%d_%H%M%S%f')}"

    def _is_market_open(self) -> bool:
        """Check if market is open (ET-aware; honours early-close calendar)."""
        now_et = datetime.now(_ET)
        try:
            from Tradov.TradovU_Utilities.TradovU10_TradingCalendar import get_trading_calendar

            return bool(get_trading_calendar().is_market_open(now_et))
        except Exception:
            now_t = now_et.time()
            return MARKET_OPEN <= now_t <= MARKET_CLOSE

    def _is_trading_allowed(self) -> bool:
        """Check if trading is allowed at current time (ET-aware)."""
        now = datetime.now(_ET).time()

        if self.config.enable_extended_hours:
            return EXTENDED_HOURS_START <= now <= EXTENDED_HOURS_END
        else:
            return self._is_market_open()

    def _calculate_portfolio_drawdown(self) -> float:
        """Calculate current portfolio drawdown as a fraction of portfolio equity.

        Uses session P&L to compute a rolling peak-to-trough drawdown expressed
        as a fraction of the starting portfolio equity (not peak session P&L).
        Dividing by the session P&L peak is incorrect when the peak is tiny
        (e.g., a $2 mark-to-market blip after opening a new position) because
        even a $3 subsequent swing would report a 150% drawdown and falsely
        trigger the 5% emergency threshold.

        Falls back to daily-loss / max-daily-loss ratio when no session is
        active.
        """
        try:
            if self.current_session is not None:
                session_pnl: float = float(getattr(self.current_session, "total_pnl", 0.0) or 0.0)
                if session_pnl > self._peak_session_pnl:
                    self._peak_session_pnl = session_pnl
                # Drawdown is meaningful only when we have had positive equity.
                # Scale by portfolio equity (not peak P&L) so a small mark-to-
                # market fluctuation on a freshly-opened position does not
                # produce a spuriously large drawdown fraction.
                if self._peak_session_pnl > 0:
                    # Use max_daily_loss as a proxy for account scale when
                    # peak session P&L is tiny (e.g., right after opening a
                    # position the peak may be only a few dollars).
                    account_scale = max(
                        abs(float(self.config.max_daily_loss or 0.0)),
                        self._peak_session_pnl,
                        1.0,
                    )
                    return (self._peak_session_pnl - session_pnl) / account_scale
            # Fallback: fraction of daily-loss limit consumed
            if self.config.max_daily_loss > 0:
                return min(self.daily_loss / self.config.max_daily_loss, 1.0)
            return 0.0
        except Exception:
            return 0.0

    def _emit_event(self, event_type: str, data: dict[str, Any]):
        """Emit event through event manager."""
        # Would integrate with TradovA05_EventManager
        self.logger.debug("Event: %s - %s", event_type, data)

    def _save_session_data(self):
        """Save trading session data."""
        if self.current_session:
            # Would save to database
            self.logger.info("Session %s saved", self.current_session.session_id)

    # ==========================================================================
    # PRIVATE METHODS - SAFETY CHECK REGISTRY
    # ==========================================================================

    def _register_safety_check(self, name: str, check_fn) -> None:
        """Register a named safety-check function."""
        if not hasattr(self, '_safety_check_registry'):
            self._safety_check_registry: dict[str, Any] = {}
        self._safety_check_registry[name] = check_fn

    def _check_daily_trade_limit(self) -> SafetyCheck:
        passed = self.daily_trades < self.config.max_daily_trades
        return SafetyCheck(
            check_name="daily_trade_limit",
            result=SafetyCheckResult.PASSED if passed else SafetyCheckResult.FAILED,
            message=f"Daily trades: {self.daily_trades}/{self.config.max_daily_trades}",
            timestamp=datetime.now(_ET),
        )

    def _check_daily_loss_limit(self) -> SafetyCheck:
        passed = self.daily_loss <= self.config.max_daily_loss
        return SafetyCheck(
            check_name="daily_loss_limit",
            result=SafetyCheckResult.PASSED if passed else SafetyCheckResult.FAILED,
            message=f"Daily loss: {self.daily_loss:.2f}/{self.config.max_daily_loss:.2f}",
            timestamp=datetime.now(_ET),
        )

    def _check_position_size_limit(self) -> SafetyCheck:
        # v27 fix: previously returned PASSED unconditionally, giving the
        # FALSE impression of safety coverage. Defer the actual gate to
        # E01.validate_signal (which enforces max_position_size + concentration)
        # and surface this as WARNING so operators see the missing native check.
        return SafetyCheck(
            check_name="position_size",
            result=SafetyCheckResult.WARNING,
            message="R04 native position-size check is a stub; relying on E01.validate_signal",
            timestamp=datetime.now(_ET),
        )

    def _check_portfolio_exposure(self) -> SafetyCheck:
        return SafetyCheck(
            check_name="portfolio_exposure",
            result=SafetyCheckResult.WARNING,
            message="R04 native portfolio-exposure check is a stub; relying on E01.validate_signal",
            timestamp=datetime.now(_ET),
        )

    def _check_market_hours(self) -> SafetyCheck:
        allowed = self._is_trading_allowed()
        return SafetyCheck(
            check_name="market_hours",
            result=SafetyCheckResult.PASSED if allowed else SafetyCheckResult.WARNING,
            message="Market open" if allowed else "Outside trading hours",
            timestamp=datetime.now(_ET),
        )

    def _check_market_volatility(self) -> SafetyCheck:
        # v27 fix: previously PASSED unconditionally. Surface as WARNING so
        # the missing native check is visible — actual VIX gating lives in
        # D31._classify_market_regime_unified and E09 VolatilityRiskManager.
        return SafetyCheck(
            check_name="volatility",
            result=SafetyCheckResult.WARNING,
            message="R04 native volatility check is a stub; relying on D31 regime gating + E09",
            timestamp=datetime.now(_ET),
        )

    # ==========================================================================
    # PRIVATE METHODS - ORDER EXECUTION INTERNALS
    # ==========================================================================

    def _on_order_terminal_event(self, event) -> None:
        """P0-10: Remove terminal (cancelled/expired/rejected) orders from
        pending_orders so the dict does not grow unboundedly."""
        order_id = (getattr(event, "data", None) or {}).get("order_id")
        if order_id:
            with self._pending_orders_lock:  # B4: thread-safe removal
                removed = self.pending_orders.pop(order_id, None)  # B4: pop avoids KeyError on duplicate events  # noqa: E501
            if removed is not None:
                self.logger.debug(
                    "Removed terminal order %s from pending_orders (event: %s)",
                    order_id,
                    getattr(event, "event_type", "unknown"),
                )

    def _normalize_reconciler_fill(self, fill: dict[str, Any]) -> dict[str, Any]:
        """Normalize FillReconciler payloads for persistence and position tracking."""
        normalized = dict(fill or {})
        raw_fill = normalized.get("raw") if isinstance(normalized.get("raw"), dict) else {}
        order_id = str(normalized.get("order_id") or "")

        pending_order: dict[str, Any] = {}
        pending_result: dict[str, Any] = {}
        if order_id:
            with self._pending_orders_lock:
                pending_entry = self.pending_orders.get(order_id) or {}
            if isinstance(pending_entry.get("order"), dict):
                pending_order = pending_entry["order"]
            if isinstance(pending_entry.get("result"), dict):
                pending_result = pending_entry["result"]

        symbol = (
            normalized.get("symbol")
            or raw_fill.get("symbol")
            or pending_order.get("symbol")
            or pending_result.get("symbol")
            or ""
        )
        fill_action = (
            normalized.get("action")
            or raw_fill.get("action")
            or pending_order.get("action")
            or pending_result.get("action")
            or ""
        )
        side = self._resolve_order_side(
            {
                "symbol": symbol,
                "side": (
                    normalized.get("side")
                    or raw_fill.get("side")
                    or pending_order.get("side")
                    or pending_result.get("side")
                    or "buy"
                ),
                "action": fill_action,
            }
        )
        quantity = int(
            normalized.get("quantity")
            or normalized.get("exec_quantity")
            or raw_fill.get("quantity")
            or raw_fill.get("exec_quantity")
            or pending_order.get("quantity")
            or pending_order.get("qty")
            or pending_result.get("quantity")
            or pending_result.get("qty")
            or 0
        )
        fill_price = float(
            normalized.get("fill_price")
            or normalized.get("avg_fill_price")
            or raw_fill.get("avg_fill_price")
            or raw_fill.get("price")
            or pending_result.get("fill_price")
            or pending_result.get("avg_fill_price")
            or pending_result.get("price")
            or pending_order.get("price")
            or pending_order.get("limit_price")
            or 0.0
        )
        strategy = str(
            normalized.get("strategy")
            or pending_order.get("strategy")
            or pending_order.get("strategy_name")
            or pending_order.get("strategy_id")
            or ""
        )
        option_details = self._parse_occ_option_symbol(symbol) if self._is_option_symbol(str(symbol)) else {}
        expiration = (
            normalized.get("expiration")
            or raw_fill.get("expiration")
            or pending_order.get("expiration")
            or pending_result.get("expiration")
            or option_details.get("expiration")
            or ""
        )
        strike_value = (
            normalized.get("strike")
            or raw_fill.get("strike")
            or pending_order.get("strike")
            or pending_result.get("strike")
            or option_details.get("strike")
        )
        try:
            strike = float(strike_value) if strike_value not in (None, "") else None
        except (TypeError, ValueError):
            strike = None
        option_type = str(
            normalized.get("option_type")
            or raw_fill.get("option_type")
            or pending_order.get("option_type")
            or pending_result.get("option_type")
            or option_details.get("option_type")
            or ""
        ).lower()
        underlying_symbol = str(
            normalized.get("underlying_symbol")
            or raw_fill.get("underlying_symbol")
            or pending_order.get("multileg_parent_symbol")
            or pending_order.get("underlying_symbol")
            or option_details.get("underlying")
            or symbol
        )

        normalized.update(
            {
                "symbol": str(symbol),
                "side": side,
                "quantity": quantity,
                "fill_price": fill_price,
                "avg_fill_price": fill_price,
                "timestamp": normalized.get("timestamp") or raw_fill.get("transaction_date"),
                "tradier_order_id": normalized.get("tradier_order_id") or raw_fill.get("id") or "",
                "strategy": strategy,
                "expiration": str(expiration or ""),
                "strike": strike,
                "option_type": option_type,
                "underlying_symbol": underlying_symbol,
            }
        )
        return normalized

    @staticmethod
    def _signed_fill_quantity(fill_side: Any, quantity: Any) -> int:
        """Return signed fill quantity using the same buy/sell semantics as B03."""
        try:
            normalized_qty = abs(int(quantity or 0))
        except (TypeError, ValueError):
            return 0

        normalized_side = str(fill_side or "buy").strip().lower().replace("-", "_")
        is_buy = normalized_side.startswith("buy") or normalized_side in {
            "long",
            "cover",
            "bto",
            "btc",
        }
        return normalized_qty if is_buy else -normalized_qty

    def _calculate_realized_pnl_from_fill(
        self,
        *,
        symbol: str,
        fill_side: Any,
        fill_quantity: Any,
        fill_price: float,
        existing_position: dict[str, Any] | None,
    ) -> float:
        """Estimate realized P&L for the portion of a fill that closes exposure."""
        if not isinstance(existing_position, dict):
            return 0.0

        try:
            existing_qty = int(existing_position.get("quantity") or 0)
        except (TypeError, ValueError):
            return 0.0
        if existing_qty == 0:
            return 0.0

        signed_fill_qty = self._signed_fill_quantity(fill_side, fill_quantity)
        if signed_fill_qty == 0 or existing_qty * signed_fill_qty >= 0:
            return 0.0

        try:
            entry_price = float(existing_position.get("entry_price") or 0.0)
        except (TypeError, ValueError):
            return 0.0
        if entry_price <= 0.0 or fill_price <= 0.0:
            return 0.0

        closed_qty = min(abs(existing_qty), abs(signed_fill_qty))
        multiplier = 100.0 if self._is_option_symbol(str(symbol)) else 1.0
        if existing_qty > 0:
            return (fill_price - entry_price) * closed_qty * multiplier
        return (entry_price - fill_price) * closed_qty * multiplier

    def _record_realized_pnl(self, realized_pnl: float) -> None:
        """Update engine-level realized P&L counters for confirmed closes."""
        if abs(realized_pnl) <= 1e-9:
            return

        self._realized_pnl_total += realized_pnl
        if realized_pnl > 0.0:
            self._winning_trade_count += 1
        else:
            self._losing_trade_count += 1
            self.daily_loss += abs(realized_pnl)

    @staticmethod
    def _coerce_datetime(value: Any) -> datetime | None:
        """Best-effort conversion for persisted timestamp fields."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    def _position_price_multiplier(self, symbol: Any) -> float:
        """Return the instrument multiplier used for P&L calculations."""
        return 100.0 if self._is_option_symbol(str(symbol)) else 1.0

    def _calculate_unrealized_pnl(self, position: dict[str, Any]) -> float:
        """Calculate unrealized P&L for the current marked price."""
        try:
            quantity = int(position.get("quantity") or 0)
            entry_price = float(position.get("entry_price") or 0.0)
            current_price = float(position.get("current_price") or 0.0)
        except (TypeError, ValueError):
            return 0.0

        if quantity == 0 or entry_price <= 0.0 or current_price <= 0.0:
            return 0.0

        multiplier = self._position_price_multiplier(position.get("symbol"))
        if quantity > 0:
            return (current_price - entry_price) * quantity * multiplier
        return (entry_price - current_price) * abs(quantity) * multiplier

    def _get_paper_account_base_balance(self) -> float:
        """Return the paper account's starting cash balance."""
        try:
            if hasattr(self.broker, "get_account_balances") and callable(self.broker.get_account_balances):
                account_payload = self.broker.get_account_balances() or {}
                account = account_payload.get("account") if isinstance(account_payload, dict) else {}
                if isinstance(account, dict):
                    balance = account.get("balance")
                    if balance not in (None, ""):
                        return float(balance)
        except Exception:
            pass

        try:
            return float(getattr(self.broker, "_account_balance", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _record_paper_account_snapshot(self, total_unrealized_pnl: float) -> None:
        """Persist a paper-mode account snapshot for dashboard truth."""
        if self._mode_name() != "paper" or self._session_db is None:
            return

        cash = self._get_paper_account_base_balance() + self._realized_pnl_total
        equity = cash + total_unrealized_pnl
        if self.current_session is not None:
            self.current_session.total_pnl = self._realized_pnl_total + total_unrealized_pnl

        try:
            self._session_db.record_account_snapshot(
                cash=float(cash),
                equity=float(equity),
                buying_power=float(equity),
                realized_pnl=float(self._realized_pnl_total),
                unrealized_pnl=float(total_unrealized_pnl),
                total_trades=int(
                    getattr(self.current_session, "trades_executed", self.daily_trades) or self.daily_trades
                ),
                winning_trades=int(self._winning_trade_count),
                losing_trades=int(self._losing_trade_count),
                max_drawdown=float(self._calculate_portfolio_drawdown()),
            )
        except Exception as exc:
            self.logger.warning("Paper account snapshot persistence failed: %s", exc)

    def _paper_position_has_session_lineage(self, symbol: str) -> bool:
        """Return True when a paper position still has live/open H05 backing."""
        if self._mode_name() != "paper" or self._session_db is None:
            return True

        normalized_symbol = str(symbol or "").strip()
        if not normalized_symbol:
            return False

        try:
            get_open_positions = getattr(self._session_db, "get_open_positions", None)
            if callable(get_open_positions):
                for row in get_open_positions():
                    if not isinstance(row, dict):
                        continue
                    row_symbol = str(row.get("symbol") or "").strip()
                    if row_symbol == normalized_symbol:
                        return True

            get_latest_position = getattr(
                self._session_db,
                "get_latest_position_for_symbol",
                None,
            )
            if callable(get_latest_position):
                latest_row = get_latest_position(normalized_symbol)
                latest_status = str(
                    (latest_row or {}).get("status") or ""
                ).strip().upper()
                if latest_status == "CLOSED":
                    return False

            has_trade_history = getattr(self._session_db, "has_trade_history_for_symbol", None)
            if callable(has_trade_history):
                return bool(has_trade_history(normalized_symbol))
        except Exception as exc:
            self.logger.warning(
                "Paper lineage check failed for %s: %s",
                normalized_symbol,
                exc,
            )
            return True

        return False

    def _get_paper_option_quote_client(self) -> Any | None:
        """Return a lazy live-data client for internal paper mark-to-market."""
        if self._paper_option_quote_client_unavailable:
            return None

        with self._paper_option_quote_lock:
            if self._paper_option_quote_client is not None:
                return self._paper_option_quote_client

            try:
                try:
                    from Tradov.TradovB_Broker.TradovB40_TradierClient import (
                        create_tradier_client_from_env,
                    )
                except ImportError:
                    from TradovB_Broker.TradovB40_TradierClient import (  # type: ignore[no-redef]
                        create_tradier_client_from_env,
                    )

                self._paper_option_quote_client = create_tradier_client_from_env()
            except Exception as exc:
                self._paper_option_quote_client_unavailable = True
                self.logger.debug("Paper option quote client unavailable: %s", exc)
                return None

            return self._paper_option_quote_client

    @staticmethod
    def _extract_quote_records(payload: Any) -> list[dict[str, Any]]:
        """Normalize Tradier quote payloads into a list of quote dicts."""
        if not isinstance(payload, dict):
            return []

        quotes = payload.get("quotes", payload)
        if isinstance(quotes, dict):
            quote_records = quotes.get("quote", quotes)
        else:
            quote_records = quotes

        if isinstance(quote_records, dict):
            return [quote_records]
        if isinstance(quote_records, list):
            return [quote for quote in quote_records if isinstance(quote, dict)]
        return []

    @staticmethod
    def _extract_live_quote_price(quote: dict[str, Any]) -> float | None:
        """Choose the best available live price from a Tradier quote payload."""

        def _safe_float(value: Any) -> float:
            try:
                return float(value or 0.0)
            except (TypeError, ValueError):
                return 0.0

        mark_price = _safe_float(quote.get("mark"))
        if mark_price > 0.0:
            return mark_price

        mid_price = _safe_float(quote.get("mid"))
        if mid_price > 0.0:
            return mid_price

        bid_price = _safe_float(quote.get("bid"))
        ask_price = _safe_float(quote.get("ask"))
        if bid_price > 0.0 and ask_price > 0.0:
            return (bid_price + ask_price) / 2.0

        for key in ("last", "close", "bid", "ask"):
            fallback_price = _safe_float(quote.get(key))
            if fallback_price > 0.0:
                return fallback_price

        return None

    def _get_live_option_chain_strikes(
        self,
        underlying: str,
        expiration: str,
    ) -> dict[str, list[float]]:
        """Return available live option strikes grouped by option type."""
        normalized_underlying = str(underlying or "").strip().upper()
        normalized_expiration = str(expiration or "").strip()
        if not normalized_underlying or not normalized_expiration:
            return {}

        cache_key = (normalized_underlying, normalized_expiration)
        now_ts = time_module.time()
        with self._paper_option_quote_lock:
            cache_age = now_ts - float(self._paper_option_chain_cache_at.get(cache_key, 0.0) or 0.0)
            if cache_age < PAPER_OPTION_CHAIN_CACHE_TTL:
                cached = self._paper_option_chain_cache.get(cache_key, {})
                return {
                    option_type: list(strikes)
                    for option_type, strikes in cached.items()
                }

        quote_client = self._get_paper_option_quote_client()
        if quote_client is None:
            return {}

        try:
            chain = quote_client.get_option_chain_with_greeks(
                normalized_underlying,
                normalized_expiration,
            )
        except Exception as exc:
            self.logger.debug(
                "Paper option chain fetch failed for %s %s: %s",
                normalized_underlying,
                normalized_expiration,
                exc,
            )
            return {}

        grouped_strikes: dict[str, set[float]] = {"call": set(), "put": set()}
        for contract in chain or []:
            option_type = str(getattr(contract, "option_type", "") or "").strip().lower()
            if option_type not in grouped_strikes:
                continue
            try:
                strike = float(getattr(contract, "strike", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
            if strike > 0.0:
                grouped_strikes[option_type].add(strike)

        normalized_grouped = {
            option_type: sorted(strikes)
            for option_type, strikes in grouped_strikes.items()
            if strikes
        }
        with self._paper_option_quote_lock:
            self._paper_option_chain_cache[cache_key] = {
                option_type: list(strikes)
                for option_type, strikes in normalized_grouped.items()
            }
            self._paper_option_chain_cache_at[cache_key] = now_ts

        return normalized_grouped

    def _get_live_option_expiration_dates(self, underlying: str) -> list[str]:
        """Return listed live expirations for the underlying symbol."""
        normalized_underlying = str(underlying or "").strip().upper()
        if not normalized_underlying:
            return []

        now_ts = time_module.time()
        with self._paper_option_quote_lock:
            cache_age = now_ts - float(
                self._paper_option_expiration_cache_at.get(normalized_underlying, 0.0) or 0.0
            )
            if cache_age < PAPER_OPTION_CHAIN_CACHE_TTL:
                return list(self._paper_option_expiration_cache.get(normalized_underlying, []))

        quote_client = self._get_paper_option_quote_client()
        if quote_client is None:
            return []

        try:
            response = quote_client.get_option_expirations(normalized_underlying)
        except Exception as exc:
            self.logger.debug(
                "Paper option expirations unavailable for %s: %s",
                normalized_underlying,
                exc,
            )
            return []

        raw_dates: list[str] | str = []
        if isinstance(response, dict):
            expirations_bucket = response.get("expirations")
            if isinstance(expirations_bucket, dict):
                raw_dates = expirations_bucket.get("date") or []

        if isinstance(raw_dates, str):
            raw_dates = [raw_dates]

        normalized_dates: set[str] = set()
        for raw_date in raw_dates if isinstance(raw_dates, list) else []:
            text = str(raw_date or "").strip()
            if not text:
                continue
            try:
                normalized_dates.add(datetime.fromisoformat(text).date().isoformat())
            except ValueError:
                continue

        ordered_dates = sorted(normalized_dates)
        with self._paper_option_quote_lock:
            self._paper_option_expiration_cache[normalized_underlying] = list(ordered_dates)
            self._paper_option_expiration_cache_at[normalized_underlying] = now_ts

        return ordered_dates

    @staticmethod
    def _select_live_option_expiration(
        available_expirations: list[str],
        target_expiration: str,
    ) -> str:
        """Select the listed expiration closest to the requested target date."""
        try:
            target_date = datetime.fromisoformat(str(target_expiration).strip()).date()
        except ValueError:
            return str(target_expiration or "").strip()

        parsed_expirations: list[str] = []
        for expiration in available_expirations:
            text = str(expiration or "").strip()
            if not text:
                continue
            try:
                datetime.fromisoformat(text).date()
            except ValueError:
                continue
            parsed_expirations.append(text)

        if not parsed_expirations:
            return target_date.isoformat()
        if target_date.isoformat() in parsed_expirations:
            return target_date.isoformat()

        return min(
            parsed_expirations,
            key=lambda expiration_text: (
                abs((datetime.fromisoformat(expiration_text).date() - target_date).days),
                0 if datetime.fromisoformat(expiration_text).date() <= target_date else 1,
                expiration_text,
            ),
        )

    def _resolve_live_option_expiration(self, underlying: str, target_expiration: str) -> str:
        """Snap a target expiration onto a live listed contract when available."""
        normalized_target = str(target_expiration or "").strip()
        if not normalized_target:
            return normalized_target

        available_expirations = self._get_live_option_expiration_dates(underlying)
        if not available_expirations:
            return normalized_target

        resolved_expiration = self._select_live_option_expiration(
            available_expirations,
            normalized_target,
        )
        if resolved_expiration != normalized_target:
            self.logger.info(
                "Resolved paper option expiration to listed contract: %s %s -> %s",
                underlying,
                normalized_target,
                resolved_expiration,
            )

        return resolved_expiration

    @staticmethod
    def _select_live_chain_strike(
        available_strikes: list[float],
        target_strike: float,
        direction: str,
    ) -> float:
        """Snap a target strike to the nearest live-chain strike."""
        ordered = sorted(
            float(strike)
            for strike in available_strikes
            if float(strike or 0.0) > 0.0
        )
        if not ordered:
            return float(target_strike)

        if direction == "down":
            lower = [strike for strike in ordered if strike <= target_strike]
            if lower:
                return lower[-1]
        elif direction == "up":
            upper = [strike for strike in ordered if strike >= target_strike]
            if upper:
                return upper[0]

        return min(ordered, key=lambda strike: abs(strike - target_strike))

    def _normalize_paper_option_positions(
        self,
        positions: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Repair invalid internal-paper option symbols to quoteable live-chain contracts."""
        if self._mode_name() != "paper" or not positions:
            return positions

        try:
            try:
                from Tradov.TradovB_Broker.TradovB40_TradierClient import build_option_symbol
            except ImportError:
                from TradovB_Broker.TradovB40_TradierClient import build_option_symbol  # type: ignore[no-redef]
        except Exception as exc:
            self.logger.debug("Paper option symbol normalization unavailable: %s", exc)
            return positions

        normalized_positions: dict[str, dict[str, Any]] = {}
        repaired_symbols: list[tuple[str, str]] = []
        dropped_duplicate_symbols: list[tuple[str, str]] = []
        occupied_symbols = {str(symbol or "").strip().upper() for symbol in positions}

        for symbol, position in positions.items():
            normalized_symbol = str(symbol or "").strip().upper()
            if not normalized_symbol or not self._is_option_symbol(normalized_symbol):
                normalized_positions[symbol] = position
                continue

            option_details = self._parse_occ_option_symbol(normalized_symbol)
            if not option_details:
                normalized_positions[symbol] = position
                continue

            option_type = str(option_details.get("option_type") or "").strip().lower()
            underlying = option_details.get("underlying", "")
            current_expiration = str(option_details.get("expiration") or "").strip()
            resolved_expiration = self._resolve_live_option_expiration(
                underlying,
                current_expiration,
            ) or current_expiration
            available_strikes = self._get_live_option_chain_strikes(
                underlying,
                resolved_expiration,
            )
            contract_strikes = available_strikes.get(option_type, [])
            current_strike = float(option_details.get("strike") or 0.0)
            expiration_changed = resolved_expiration != current_expiration
            if not contract_strikes:
                normalized_positions[symbol] = position
                continue

            normalized_strike = current_strike
            if not any(abs(strike - current_strike) < 1e-9 for strike in contract_strikes):
                # Strike absent from live chain. Only attempt to repair when
                # the expiration is also being remapped — in that case the
                # symbol will be rebuilt from scratch anyway. When the
                # expiration is correct the chain may be a partial snapshot;
                # keep the position intact to avoid incorrectly collapsing
                # separate SELL and BUY legs onto the same strike.
                if not expiration_changed:
                    normalized_positions[symbol] = position
                    continue
                target_direction = "down" if option_type == "put" else "up"
                normalized_strike = self._select_live_chain_strike(
                    contract_strikes,
                    current_strike,
                    target_direction,
                )

            if not expiration_changed and abs(normalized_strike - current_strike) < 1e-9:
                normalized_positions[symbol] = position
                continue

            normalized_option_symbol = build_option_symbol(
                underlying,
                resolved_expiration,
                option_type,
                normalized_strike,
            )
            if normalized_option_symbol in occupied_symbols and normalized_option_symbol != normalized_symbol:
                dropped_duplicate_symbols.append((normalized_symbol, normalized_option_symbol))
                if self._session_db is not None:
                    delete_open_position = getattr(self._session_db, "delete_open_position", None)
                    if callable(delete_open_position):
                        try:
                            delete_open_position(
                                position_id=f"{self.mode.value}:{normalized_symbol}",
                            )
                        except Exception as exc:
                            self.logger.warning(
                                "Paper option duplicate cleanup failed for %s -> %s: %s",
                                normalized_symbol,
                                normalized_option_symbol,
                                exc,
                            )

                try:
                    broker_last_prices = getattr(self.broker, "_last_prices", None)
                    if (
                        isinstance(broker_last_prices, dict)
                        and normalized_symbol in broker_last_prices
                        and normalized_option_symbol not in broker_last_prices
                    ):
                        broker_last_prices[normalized_option_symbol] = broker_last_prices[normalized_symbol]
                except Exception:
                    pass
                continue

            repaired_position = dict(position)
            repaired_position["symbol"] = normalized_option_symbol
            repaired_position["strike"] = normalized_strike
            repaired_position["expiration"] = (
                resolved_expiration
                or current_expiration
                or position.get("expiration")
            )
            repaired_position["option_type"] = option_type
            normalized_positions[normalized_option_symbol] = repaired_position
            occupied_symbols.discard(normalized_symbol)
            occupied_symbols.add(normalized_option_symbol)
            repaired_symbols.append((normalized_symbol, normalized_option_symbol))

            if self._session_db is not None:
                rekey_open_position = getattr(self._session_db, "rekey_open_position", None)
                if callable(rekey_open_position):
                    try:
                        rekey_open_position(
                            old_position_id=f"{self.mode.value}:{normalized_symbol}",
                            new_position_id=f"{self.mode.value}:{normalized_option_symbol}",
                            new_symbol=normalized_option_symbol,
                            expiration=str(repaired_position.get("expiration") or "") or None,
                            strike=normalized_strike,
                            option_type=option_type,
                        )
                    except Exception as exc:
                        self.logger.warning(
                            "Paper option symbol rekey failed for %s -> %s: %s",
                            normalized_symbol,
                            normalized_option_symbol,
                            exc,
                        )

            try:
                broker_last_prices = getattr(self.broker, "_last_prices", None)
                if isinstance(broker_last_prices, dict) and normalized_symbol in broker_last_prices:
                    broker_last_prices[normalized_option_symbol] = broker_last_prices.pop(normalized_symbol)
            except Exception:
                pass

        if repaired_symbols:
            self.logger.warning(
                "Normalized invalid internal paper option symbols to live-chain contracts: %s",
                ", ".join(f"{old}->{new}" for old, new in repaired_symbols),
            )

        if dropped_duplicate_symbols:
            self.logger.warning(
                "Dropped superseded invalid internal paper option symbols: %s",
                ", ".join(f"{old}->{new}" for old, new in dropped_duplicate_symbols),
            )

        return normalized_positions

    def _refresh_paper_option_market_prices(
        self,
        positions: dict[str, dict[str, Any]],
    ) -> dict[str, float]:
        """Fetch live Tradier quotes for active internal-paper option positions."""
        if self._mode_name() != "paper":
            return {}

        option_symbols = sorted(
            {
                str(symbol or "").strip().upper()
                for symbol in positions
                if str(symbol or "").strip() and self._is_option_symbol(str(symbol))
            }
        )
        if not option_symbols:
            return {}

        now_ts = time_module.time()
        with self._paper_option_quote_lock:
            cached_quotes = {
                symbol: float(price)
                for symbol, price in self._paper_option_quote_cache.items()
                if symbol in option_symbols and float(price or 0.0) > 0.0
            }
            cache_age = now_ts - float(self._paper_option_quote_cache_at or 0.0)
            if cache_age < PAPER_OPTION_QUOTES_CACHE_TTL:
                return cached_quotes

        quote_client = self._get_paper_option_quote_client()
        if quote_client is None:
            return {}

        try:
            payload = quote_client.get_quotes(option_symbols)
        except Exception as exc:
            self.logger.debug("Paper option quote refresh failed: %s", exc)
            with self._paper_option_quote_lock:
                self._paper_option_quote_cache_at = now_ts
                return {
                    symbol: float(price)
                    for symbol, price in self._paper_option_quote_cache.items()
                    if symbol in option_symbols and float(price or 0.0) > 0.0
                }

        refreshed_quotes: dict[str, float] = {}
        for quote in self._extract_quote_records(payload):
            symbol = str(quote.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            live_price = self._extract_live_quote_price(quote)
            if live_price is not None and live_price > 0.0:
                refreshed_quotes[symbol] = float(live_price)

        unresolved_symbols = sorted(
            symbol for symbol in option_symbols if symbol not in refreshed_quotes
        )
        with self._paper_option_quote_lock:
            if refreshed_quotes:
                self._paper_option_quote_cache.update(refreshed_quotes)
            self._paper_option_quote_cache_at = now_ts
            new_misses = [
                symbol
                for symbol in unresolved_symbols
                if symbol not in self._paper_option_quote_misses
            ]
            self._paper_option_quote_misses = set(unresolved_symbols)
            merged_quotes = {
                symbol: float(price)
                for symbol, price in self._paper_option_quote_cache.items()
                if symbol in option_symbols and float(price or 0.0) > 0.0
            }

        if refreshed_quotes:
            try:
                broker_last_prices = getattr(self.broker, "_last_prices", None)
                if isinstance(broker_last_prices, dict):
                    broker_last_prices.update(refreshed_quotes)
                else:
                    self.broker._last_prices = dict(refreshed_quotes)
            except Exception:
                pass

        if new_misses:
            self.logger.warning(
                "Paper MTM could not resolve live option quotes for: %s",
                ", ".join(new_misses),
            )

        return merged_quotes

    def _mark_paper_positions_to_market(self) -> list[dict[str, Any]]:
        """Refresh paper positions from cached market prices and persist marks."""
        if self._mode_name() != "paper":
            return []

        last_prices = getattr(self.broker, "_last_prices", {}) or {}
        with self._active_positions_lock:
            positions = {
                symbol: dict(position)
                for symbol, position in self.active_positions.items()
                if isinstance(position, dict)
            }

        stale_symbols = [
            symbol
            for symbol in positions
            if not self._paper_position_has_session_lineage(symbol)
        ]
        if stale_symbols:
            for symbol in stale_symbols:
                positions.pop(symbol, None)
            with self._active_positions_lock:
                for symbol in stale_symbols:
                    self.active_positions.pop(symbol, None)
            self.logger.warning(
                "Dropped %s stale paper positions without session lineage",
                len(stale_symbols),
            )

        positions = self._normalize_paper_option_positions(positions)

        # Re-hydrate any OPEN H05 positions that are missing from
        # active_positions (safety net for positions evicted by the normalize
        # step or any other path that removes them without a close fill).
        if self._session_db is not None:
            try:
                get_open_positions = getattr(self._session_db, "get_open_positions", None)
                if callable(get_open_positions):
                    for row in get_open_positions():
                        if not isinstance(row, dict):
                            continue
                        row_symbol = str(row.get("symbol") or "").strip()
                        if not row_symbol or row_symbol in positions:
                            continue
                        row_qty = int(row.get("quantity") or 0)
                        if row_qty == 0:
                            continue
                        self.logger.info(
                            "MTM re-hydrating evicted paper position from H05: %s qty=%d",
                            row_symbol,
                            row_qty,
                        )
                        positions[row_symbol] = {
                            "symbol": row_symbol,
                            "quantity": row_qty,
                            "entry_price": float(row.get("entry_price") or 0.0),
                            "current_price": float(
                                row.get("current_price") or row.get("entry_price") or 0.0
                            ),
                            "unrealized_pnl": float(row.get("unrealized_pnl") or 0.0),
                            "realized_pnl": float(row.get("realized_pnl") or 0.0),
                            "strategy_id": str(
                                row.get("strategy_id")
                                or row.get("strategy")
                                or row.get("strategy_name")
                                or ""
                            ),
                            "strategy": str(row.get("strategy") or ""),
                            "strategy_name": str(
                                row.get("strategy_name") or row.get("strategy") or ""
                            ),
                            "position_source": "session_db_hydration",
                            "opened_at": self._coerce_datetime(row.get("opened_at")),
                            "expiration": str(row.get("expiration") or "") or None,
                            "strike": (
                                float(row["strike"])
                                if row.get("strike") not in (None, "")
                                else None
                            ),
                            "option_type": str(row.get("option_type") or "") or None,
                        }
                        # Also prime B03 if it has no fill record yet so that
                        # close fills from R14 are netted correctly rather than
                        # creating a phantom long.
                        pt = self._position_tracker
                        if pt is not None:
                            try:
                                tp = getattr(pt, "positions", None)
                                tl = getattr(pt, "_position_lock", None) or getattr(pt, "lock", None)
                                if isinstance(tp, dict) and tl is not None:
                                    with tl:
                                        if row_symbol not in tp:
                                            tp[row_symbol] = {
                                                "symbol": row_symbol,
                                                "quantity": row_qty,
                                                "average_fill_price": float(
                                                    row.get("entry_price") or 0.0
                                                ),
                                                "strategy_id": str(
                                                    row.get("strategy_id")
                                                    or row.get("strategy")
                                                    or ""
                                                ),
                                                "strategy": str(row.get("strategy") or ""),
                                                "strategy_name": str(
                                                    row.get("strategy") or ""
                                                ),
                                            }
                            except Exception:
                                pass
            except Exception as exc:
                self.logger.warning("Paper position re-hydration failed: %s", exc)

        with self._active_positions_lock:
            self.active_positions.clear()
            self.active_positions.update(positions)

        live_option_prices = self._refresh_paper_option_market_prices(positions)
        if live_option_prices:
            last_prices = dict(last_prices)
            last_prices.update(live_option_prices)

        total_unrealized_pnl = 0.0
        for symbol, position in positions.items():
            try:
                mark_price = float(
                    last_prices.get(symbol)
                    or position.get("current_price")
                    or position.get("entry_price")
                    or 0.0
                )
            except (TypeError, ValueError):
                mark_price = 0.0

            if mark_price > 0.0:
                position["current_price"] = mark_price
            if position.get("cost_basis") in (None, ""):
                position["cost_basis"] = position.get("entry_price", 0.0)
            if position.get("strategy_id") in (None, ""):
                position["strategy_id"] = position.get("strategy") or position.get("strategy_name") or ""
            position["unrealized_pnl"] = self._calculate_unrealized_pnl(position)
            total_unrealized_pnl += float(position.get("unrealized_pnl") or 0.0)

        with self._active_positions_lock:
            for symbol, position in positions.items():
                entry = self.active_positions.get(symbol)
                if entry is not None:
                    entry.update(position)

        if self._session_db is not None:
            for symbol, position in positions.items():
                try:
                    self._session_db.upsert_position(
                        position_id=f"{self.mode.value}:{symbol}",
                        symbol=symbol,
                        strategy=str(position.get("strategy") or position.get("strategy_id") or ""),
                        quantity=int(position.get("quantity") or 0),
                        entry_price=float(position.get("entry_price") or 0.0),
                        current_price=float(position.get("current_price") or 0.0),
                        unrealized_pnl=float(position.get("unrealized_pnl") or 0.0),
                        realized_pnl=float(position.get("realized_pnl") or 0.0),
                        status="OPEN",
                        opened_at=self._coerce_datetime(position.get("opened_at")),
                        expiration=str(position.get("expiration") or "") or None,
                        strike=(
                            float(position.get("strike"))
                            if position.get("strike") not in (None, "")
                            else None
                        ),
                        option_type=str(position.get("option_type") or "") or None,
                    )
                except Exception as exc:
                    self.logger.warning("Paper position mark persistence failed for %s: %s", symbol, exc)

        self._record_paper_account_snapshot(total_unrealized_pnl)

        # Notify the dashboard so it re-reads H05 and refreshes the P&L
        # column.  Throttled to once every 5 s to match the option-quote cache
        # TTL — there is no point re-drawing more often than prices change.
        now_ts = time_module.time()
        last_emit = float(getattr(self, "_last_mtm_gui_emit_at", 0.0) or 0.0)
        if positions and (now_ts - last_emit) >= PAPER_OPTION_QUOTES_CACHE_TTL:
            self._last_mtm_gui_emit_at = now_ts
            first_symbol = next(iter(positions), None)
            if first_symbol and self._event_manager is not None:
                try:
                    self._event_manager.emit(
                        EventType.POSITION_UPDATED,
                        {"symbol": first_symbol, "source": "mark_to_market"},
                        source="LiveEngine",
                    )
                except Exception:
                    pass

        return list(positions.values())

    def _on_reconciler_fill(self, event) -> None:
        """Update engine metrics when FillReconciler confirms a fill."""
        if getattr(event, "source", None) != "FillReconciler":
            return
        # A16 (v14): a fill changes positions on the broker side; drop the
        # cache so the next monitor tick fetches fresh data.
        self._invalidate_positions_cache()
        fill = self._normalize_reconciler_fill(event.data or {})
        order_id = fill.get("order_id")
        symbol = str(fill.get("symbol", "") or "")
        with self._active_positions_lock:
            existing_position = dict(self.active_positions.get(symbol) or {})
        realized_pnl = self._calculate_realized_pnl_from_fill(
            symbol=symbol,
            fill_side=fill.get("side"),
            fill_quantity=fill.get("quantity", fill.get("qty", 0)),
            fill_price=float(fill.get("avg_fill_price", fill.get("price", 0.0)) or 0.0),
            existing_position=existing_position,
        )
        self._record_realized_pnl(realized_pnl)
        if order_id:
            with self._pending_orders_lock:  # B4: thread-safe lookup
                hit = order_id in self.pending_orders
            if hit:
                self.metrics.successful_executions += 1
                self.daily_trades += 1
                if self.current_session:
                    self.current_session.trades_executed += 1
        # Forward fill data to PositionTracker (S-06).
        if self._position_tracker is not None:
            try:
                self._position_tracker.record_fill(fill)
            except Exception as exc:
                self.logger.error("PositionTracker.record_fill error: %s", exc)

        # Persist fill to live DB (H05) for parity with paper DB.
        if self._session_db is not None:
            try:
                self._session_db.record_trade(
                    symbol=symbol,
                    trade_type=str(fill.get("side", "fill")).upper(),
                    side=str(fill.get("side", "buy")).lower(),
                    quantity=int(fill.get("quantity", fill.get("qty", 0))),
                    price=float(fill.get("avg_fill_price", fill.get("price", 0.0))),
                    commission=float(fill.get("commission", 0.0)),
                    realized_pnl=float(realized_pnl),
                    strategy=str(fill.get("strategy", "")),
                    order_id=str(order_id) if order_id else None,
                    expiration=str(fill.get("expiration", "") or "") or None,
                    strike=(
                        float(fill.get("strike"))
                        if fill.get("strike") not in (None, "")
                        else None
                    ),
                    option_type=str(fill.get("option_type", "") or "") or None,
                    notes="live fill via FillReconciler",
                )
            except Exception as _db_err:
                self.logger.warning("Live DB trade record failed: %s", _db_err)

    def _on_reconciler_partial_fill(self, event) -> None:
        """Update engine metrics when FillReconciler confirms a partial fill.

        A7 (v14): membership check takes ``_pending_orders_lock`` so a
        concurrent terminal-event handler cannot drop the entry between the
        ``in`` test and the metrics update.
        """
        if getattr(event, "source", None) != "FillReconciler":
            return
        order_id = (event.data or {}).get("order_id")
        if not order_id:
            return
        with self._pending_orders_lock:
            hit = order_id in self.pending_orders
        if hit:
            self.metrics.successful_executions += 1

    def _on_position_updated(self, event) -> None:
        """Persist PositionTracker net positions to the session database."""
        if getattr(event, "source", None) != "PositionTracker":
            return

        data = getattr(event, "data", None) or {}
        symbol = str(data.get("symbol") or "")
        if not symbol:
            return

        try:
            quantity = int(data.get("quantity"))
        except (TypeError, ValueError):
            return

        position_snapshot = data.get("position") if isinstance(data.get("position"), dict) else {}
        order_id = str(data.get("order_id") or "")
        pending_order: dict[str, Any] = {}

        try:
            fill_price = float(data.get("fill_price") or 0.0)
        except (TypeError, ValueError):
            fill_price = 0.0

        with self._active_positions_lock:
            existing_position = self.active_positions.get(symbol) or {}

        try:
            existing_quantity = int(existing_position.get("quantity") or 0)
        except (TypeError, ValueError):
            existing_quantity = 0

        existing_strategy = str(existing_position.get("strategy") or "")
        existing_opened_at = self._coerce_datetime(existing_position.get("opened_at"))
        try:
            existing_entry_price = float(existing_position.get("entry_price") or 0.0)
        except (TypeError, ValueError):
            existing_entry_price = 0.0

        strategy = ""
        if order_id:
            with self._pending_orders_lock:
                pending_entry = self.pending_orders.get(order_id) or {}
            pending_order = pending_entry.get("order") if isinstance(pending_entry.get("order"), dict) else {}
            strategy = str(
                pending_order.get("strategy")
                or pending_order.get("strategy_name")
                or pending_order.get("strategy_id")
                or ""
            )
        if not strategy:
            strategy = str(position_snapshot.get("strategy") or existing_strategy or "")

        strategy_id = str(
            data.get("strategy_id")
            or pending_order.get("strategy_id")
            or position_snapshot.get("strategy_id")
            or existing_position.get("strategy_id")
            or strategy
            or ""
        ).strip()
        strategy_name = str(
            data.get("strategy_name")
            or pending_order.get("strategy_name")
            or pending_order.get("strategy")
            or position_snapshot.get("strategy_name")
            or position_snapshot.get("strategy")
            or strategy
            or ""
        ).strip()
        strategy_type = str(
            data.get("strategy_type")
            or pending_order.get("strategy_type")
            or (pending_order.get("metadata", {}) if isinstance(pending_order.get("metadata"), dict) else {}).get("strategy_type")
            or position_snapshot.get("strategy_type")
            or existing_position.get("strategy_type")
            or ""
        ).strip().lower()
        pair_key = str(
            data.get("pair_key")
            or pending_order.get("pair_key")
            or (pending_order.get("metadata", {}) if isinstance(pending_order.get("metadata"), dict) else {}).get("pair_key")
            or position_snapshot.get("pair_key")
            or existing_position.get("pair_key")
            or ""
        ).strip()

        fill_quantity = abs(existing_quantity - quantity) or data.get("filled_quantity") or data.get("quantity")
        realized_pnl = self._calculate_realized_pnl_from_fill(
            symbol=symbol,
            fill_side=(pending_order.get("side") if pending_order else None) or data.get("side"),
            fill_quantity=fill_quantity,
            fill_price=fill_price,
            existing_position=existing_position,
        )

        try:
            entry_price = float(position_snapshot.get("average_fill_price") or 0.0)
        except (TypeError, ValueError):
            entry_price = 0.0
        if entry_price <= 0.0:
            entry_price = existing_entry_price if existing_entry_price > 0.0 else fill_price

        opened_at = existing_opened_at or datetime.now(_ET)
        current_price = fill_price if fill_price > 0.0 else None
        status = "OPEN" if quantity != 0 else "CLOSED"
        closed_at = datetime.now(_ET) if quantity == 0 else None
        option_details = self._parse_occ_option_symbol(symbol) if self._is_option_symbol(symbol) else {}
        expiration = str(
            position_snapshot.get("expiration")
            or pending_order.get("expiration")
            or option_details.get("expiration")
            or ""
        )
        strike_value = (
            position_snapshot.get("strike")
            or pending_order.get("strike")
            or option_details.get("strike")
        )
        try:
            strike = float(strike_value) if strike_value not in (None, "") else None
        except (TypeError, ValueError):
            strike = None
        option_type = str(
            position_snapshot.get("option_type")
            or pending_order.get("option_type")
            or option_details.get("option_type")
            or ""
        ).lower()
        underlying_symbol = str(
            position_snapshot.get("underlying_symbol")
            or pending_order.get("multileg_parent_symbol")
            or option_details.get("underlying")
            or symbol
        )

        with self._active_positions_lock:
            if quantity == 0:
                self.active_positions.pop(symbol, None)
            else:
                self.active_positions[symbol] = self._merge_active_position_metadata(
                    self.active_positions.get(symbol),
                    {
                    "symbol": symbol,
                    "quantity": quantity,
                    "entry_price": entry_price,
                    "current_price": current_price or entry_price,
                    "strategy": strategy,
                    "strategy_id": strategy_id,
                    "strategy_name": strategy_name,
                    "strategy_type": strategy_type or None,
                    "pair_key": pair_key or None,
                    "opened_at": opened_at,
                    "order_id": order_id,
                    "underlying_symbol": underlying_symbol,
                    "expiration": expiration or None,
                    "strike": strike,
                    "option_type": option_type or None,
                    },
                )

        if self._session_db is None:
            return

        try:
            self._session_db.upsert_position(
                position_id=f"{self.mode.value}:{symbol}",
                symbol=symbol,
                strategy=strategy,
                quantity=quantity,
                entry_price=entry_price,
                current_price=current_price,
                realized_pnl=float(realized_pnl),
                status=status,
                opened_at=opened_at,
                closed_at=closed_at,
                expiration=expiration or None,
                strike=strike,
                option_type=option_type or None,
            )
        except Exception as exc:
            self.logger.warning("Session DB position upsert failed: %s", exc)

    def _on_order_orphaned(self, event) -> None:
        """N3: Escalate and persist orphaned orders after reconciler poll failures."""
        data = getattr(event, "data", None) or {}
        order_id = str(data.get("order_id") or "")
        broker_order_id = str(data.get("broker_order_id") or "")
        last_error = str(data.get("last_error") or "unknown")
        orphaned_at = datetime.now(_ET)

        if order_id:
            with self._pending_orders_lock:
                entry = self.pending_orders.setdefault(order_id, {})
                entry["orphaned"] = True
                entry["orphaned_at"] = orphaned_at
                entry["orphan_reason"] = last_error
                if broker_order_id:
                    entry["tradier_order_id"] = broker_order_id

        self.logger.error(
            "ORDER_ORPHANED: order_id=%s broker_order_id=%s reason=%s",
            order_id or "unknown",
            broker_order_id or "unknown",
            last_error,
        )

        # Optional safety escalation: if too many orphans occur within a
        # rolling window, trigger KILL_SWITCH to prevent blind trading.
        now = orphaned_at
        window_seconds = max(1, ORPHAN_ORDER_PANIC_WINDOW_SECONDS)
        threshold = max(1, ORPHAN_ORDER_PANIC_THRESHOLD)
        cutoff = now - timedelta(seconds=window_seconds)
        self._orphan_order_times.append(now)
        while self._orphan_order_times and self._orphan_order_times[0] < cutoff:
            self._orphan_order_times.popleft()

        if len(self._orphan_order_times) >= threshold and not self._kill_switch_event.is_set():
            reason = (
                f"ORPHAN_ORDER threshold reached: {len(self._orphan_order_times)} "
                f"within {window_seconds}s"
            )
            self.logger.critical("%s — escalating to KILL_SWITCH", reason)
            self._kill_switch_event.set()
            self._write_kill_lock(reason)
            try:
                self._event_manager.emit(
                    EventType.KILL_SWITCH,
                    {
                        "reason": reason,
                        "source": "ORDER_ORPHANED",
                        "order_id": order_id or None,
                        "broker_order_id": broker_order_id or None,
                    },
                    source="LiveEngine",
                )
            except Exception as exc:
                self.logger.error("_on_order_orphaned: failed to emit KILL_SWITCH: %s", exc)

    def _on_order_un_orphaned(self, event) -> None:
        """B4 (v15): Clear the orphan flag when FillReconciler recovers an order.

        The FillReconciler emits ORDER_UN_ORPHANED when a previously-orphaned
        order subsequently returns a terminal status from the broker.  Clearing
        the flag here prevents the order from being treated as a zombie on the
        next monitor tick.
        """
        data = getattr(event, "data", None) or {}
        order_id = str(data.get("order_id") or "")
        if not order_id:
            return
        with self._pending_orders_lock:
            entry = self.pending_orders.get(order_id)
            if entry is not None:
                entry.pop("orphaned", None)
                entry.pop("orphaned_at", None)
                entry.pop("orphan_reason", None)
        self.logger.info(
            "ORDER_UN_ORPHANED: order_id=%s — orphan flag cleared", order_id
        )

    # ------------------------------------------------------------------
    # N1: Kill-lock persistence helpers
    # ------------------------------------------------------------------

    _KILL_LOCK_PATH: Path = Path.home() / ".tradov_kill_lock"

    @property
    def _kill_switch_active(self) -> bool:
        """Back-compat shim: True if the kill-switch Event is set."""
        return self._kill_switch_event.is_set()

    def _write_kill_lock(self, reason: str) -> None:
        """Persist kill-switch state to disk so a restart cannot clear it.

        Writes ~/.tradov_kill_lock containing {reason, ts, account_id}.
        The launcher refuses to start while this file is present.

        v27 SPEC-19: paper mode normally skips the lock-file (so dev iteration
        is not blocked), but operators can opt in via
        ``TRADOV_KILL_LOCK_FORCE=1`` to drill the live-mode persistence path
        before launch.
        """
        account_id = str(getattr(self.config, "account_id", "unknown") or "unknown")
        force = os.environ.get("TRADOV_KILL_LOCK_FORCE", "").strip().lower() in (
            "1", "true", "yes", "on",
        )
        if account_id.upper().startswith("PAPER") and not force:
            self.logger.critical(
                "🔓 Paper mode kill-switch: lock file persistence skipped (reason=%s). "
                "Set TRADOV_KILL_LOCK_FORCE=1 to drill the live-mode lock-file path.",
                reason,
            )
            return
        try:
            payload = {
                "reason": reason,
                "ts": datetime.now(ZoneInfo("America/New_York")).isoformat(),
                "account_id": account_id,
            }
            self._KILL_LOCK_PATH.write_text(json.dumps(payload, indent=2))
            self.logger.critical(
                "🔒 Kill-lock written to %s — restart will be blocked.",
                self._KILL_LOCK_PATH,
            )
        except Exception as exc:
            self.logger.error("Failed to write kill-lock file: %s", exc)

    def _on_kill_switch(self, event: Any) -> None:
        """O-4: Handle KILL_SWITCH event — halt all new order submissions."""
        reason = (getattr(event, "data", None) or {}).get("reason", "KILL_SWITCH event received")
        self._kill_switch_event.set()
        self._write_kill_lock(reason)
        self.logger.critical("🔴 KILL SWITCH ACTIVATED: %s — no further orders will be submitted", reason)  # noqa: E501

    def _on_emergency_bridge(self, event: Any) -> None:
        """P0-2: Bridge EMERGENCY events from E11/E13 to the KILL_SWITCH handler.

        E11 (MaxLossProtection) and E13 (DayProfitTarget) emit EventType.EMERGENCY
        on catastrophic loss breach.  This bridge re-emits KILL_SWITCH so the
        single _on_kill_switch handler enforces the halt, and also activates the
        flag directly in case the re-emit is asynchronous.
        """
        data = getattr(event, "data", None) or {}
        reason = data.get("reason", "EMERGENCY event received")
        self.logger.critical("🚨 EMERGENCY received — escalating to KILL_SWITCH: %s", reason)
        self._kill_switch_event.set()
        self._write_kill_lock(reason)
        try:
            self._event_manager.emit(
                EventType.KILL_SWITCH,
                {"reason": reason, "source": "EMERGENCY_bridge", "original_data": data},
                source="LiveEngine",
            )
        except Exception as exc:
            self.logger.error("_on_emergency_bridge: failed to re-emit KILL_SWITCH: %s", exc)

    def _execute_order_internal(self, order: dict[str, Any]) -> None:
        """Submit an order through the broker and track the result."""
        order_id = order.get("order_id")
        try:
            result = self._broker_submit(order)
            # Any broker round-trip that returns without a TradierServerError
            # is a successful API contact — clear the panic counter even if
            # the order itself wasn't accepted/filled.
            self.reset_api_error_count()
            status = (result or {}).get("status", "error")
            if status in ("accepted", "filled", "partial"):
                # Emit ORDER_SUBMITTED on any successful broker acknowledgement.
                self._event_manager.emit(
                    EventType.ORDER_SUBMITTED,
                    {
                        "order_id": order_id,
                        "symbol": order.get("symbol"),
                        # O5 (v14): propagate correlation_id for trade-chain tracing.
                        "correlation_id": order.get("correlation_id"),
                    },
                    source="LiveEngine",
                )
                if status == "accepted":
                    # Real broker returned an order-ID — hand off to the
                    # FillReconciler for ground-truth fill detection.
                    tradier_id = (result or {}).get("tradier_order_id")
                    if self._reconciler is not None and tradier_id:
                        order_type = order.get("order_type", "market").lower()
                        self._reconciler.track(
                            str(order_id), tradier_id, order_type
                        )
                    else:
                        # No reconciler (paper/test env): treat acceptance as fill.
                        self.metrics.successful_executions += 1
                        self.daily_trades += 1
                        if self.current_session:
                            self.current_session.trades_executed += 1
                        _paper_symbol = str(order.get("symbol") or "")
                        _paper_side = str(order.get("side") or "buy").lower()
                        _paper_qty = int(order.get("quantity") or 0)
                        _paper_price = float(
                            (result or {}).get("fill_price")
                            or (result or {}).get("price")
                            or order.get("price")
                            or 0.0
                        )
                        # Fix B1: include symbol so D31 _on_terminal_order_event can
                        # clear the pending entry reservation for the underlying.
                        self._event_manager.emit(
                            EventType.ORDER_FILLED,
                            {"order_id": order_id, "result": result, "symbol": _paper_symbol},
                            source="LiveEngine",
                        )
                        # Fix B2: persist paper fill to session DB (H05) for trade records.
                        if self._session_db is not None and _paper_symbol:
                            try:
                                _strike = order.get("strike")
                                self._session_db.record_trade(
                                    symbol=_paper_symbol,
                                    trade_type=_paper_side.upper(),
                                    side=_paper_side,
                                    quantity=_paper_qty,
                                    price=_paper_price,
                                    commission=0.0,
                                    realized_pnl=0.0,
                                    strategy=str(order.get("strategy_id") or order.get("strategy") or ""),
                                    order_id=str(order_id) if order_id else None,
                                    expiration=str(order.get("expiration") or "") or None,
                                    strike=float(_strike) if _strike not in (None, "") else None,
                                    option_type=str(order.get("option_type") or "") or None,
                                    notes="paper fill via LiveEngine",
                                )
                            except Exception as _db_err:
                                self.logger.warning("Paper fill DB record failed: %s", _db_err)
                        # Fix B3: forward paper fill to PositionTracker so active_positions
                        # stays consistent and POSITION_UPDATED events are emitted.
                        if self._position_tracker is not None and _paper_symbol and _paper_qty:
                            try:
                                self._position_tracker.record_fill({
                                    "symbol": _paper_symbol,
                                    "side": _paper_side,
                                    "quantity": _paper_qty,
                                    "fill_price": _paper_price,
                                    "strategy_id": str(order.get("strategy_id") or order.get("strategy") or ""),
                                    "strategy_name": str(order.get("strategy_name") or order.get("strategy") or order.get("strategy_id") or ""),
                                    "order_id": str(order_id) if order_id else "",
                                })
                            except Exception as _pt_err:
                                self.logger.warning("Paper fill position tracker record failed: %s", _pt_err)
                elif status == "filled":
                    # Direct fill: mock / paper engine without reconciler.
                    self.metrics.successful_executions += 1
                    self.daily_trades += 1
                    if self.current_session:
                        self.current_session.trades_executed += 1
                    _paper_symbol = str(order.get("symbol") or "")
                    _paper_side = str(order.get("side") or "buy").lower()
                    _paper_qty = int(order.get("quantity") or 0)
                    _paper_price = float(
                        (result or {}).get("fill_price")
                        or (result or {}).get("price")
                        or order.get("price")
                        or 0.0
                    )
                    # Fix B1: include symbol for pending-reservation clearing.
                    self._event_manager.emit(
                        EventType.ORDER_FILLED,
                        {"order_id": order_id, "result": result, "symbol": _paper_symbol},
                        source="LiveEngine",
                    )
                    # Fix B2: persist to session DB.
                    if self._session_db is not None and _paper_symbol:
                        try:
                            _strike = order.get("strike")
                            self._session_db.record_trade(
                                symbol=_paper_symbol,
                                trade_type=_paper_side.upper(),
                                side=_paper_side,
                                quantity=_paper_qty,
                                price=_paper_price,
                                commission=0.0,
                                realized_pnl=0.0,
                                strategy=str(order.get("strategy_id") or order.get("strategy") or ""),
                                order_id=str(order_id) if order_id else None,
                                expiration=str(order.get("expiration") or "") or None,
                                strike=float(_strike) if _strike not in (None, "") else None,
                                option_type=str(order.get("option_type") or "") or None,
                                notes="paper fill via LiveEngine",
                            )
                        except Exception as _db_err:
                            self.logger.warning("Paper fill DB record failed: %s", _db_err)
                    # Fix B3: forward to PositionTracker.
                    if self._position_tracker is not None and _paper_symbol and _paper_qty:
                        try:
                            self._position_tracker.record_fill({
                                "symbol": _paper_symbol,
                                "side": _paper_side,
                                "quantity": _paper_qty,
                                "fill_price": _paper_price,
                                "strategy_id": str(order.get("strategy_id") or order.get("strategy") or ""),
                                "strategy_name": str(order.get("strategy_name") or order.get("strategy") or order.get("strategy_id") or ""),
                                "order_id": str(order_id) if order_id else "",
                            })
                        except Exception as _pt_err:
                            self.logger.warning("Paper fill position tracker record failed: %s", _pt_err)
                else:  # "partial"
                    self.metrics.successful_executions += 1
                    self._event_manager.emit(
                        EventType.ORDER_PARTIALLY_FILLED,
                        {"order_id": order_id, "result": result},
                        source="LiveEngine",
                    )
            else:
                self.metrics.failed_executions += 1
                self._event_manager.emit(
                    EventType.ORDER_REJECTED,
                    {"order_id": order_id, "result": result},
                    source="LiveEngine",
                )
            self._resolve_order_future(order_id, order, result)
        except _TradierServerError as exc:
            # Tradier 5xx: record failure; may trigger API Panic Mode
            self.logger.error("Tradier 5xx error for order %s: %s", order_id, exc)
            self.metrics.failed_executions += 1
            result = {"status": "error", "reason": str(exc)}
            self._resolve_order_future(order_id, order, result)
            self._event_manager.emit(
                EventType.ORDER_REJECTED,
                {"order_id": order_id, "result": result},
                source="LiveEngine",
            )
            self.record_api_server_error()
        except Exception as exc:
            self.logger.error("Internal order execution failed for %s: %s", order_id, exc)
            self.metrics.failed_executions += 1
            result = {"status": "error", "reason": str(exc)}
            self._resolve_order_future(order_id, order, result)
            self._event_manager.emit(
                EventType.ORDER_REJECTED,
                {"order_id": order_id, "result": result},
                source="LiveEngine",
            )
        finally:
            self.metrics.total_orders += 1

    def _broker_submit(self, order: dict[str, Any]) -> dict[str, Any]:
        """Route an order dict to the broker via the BrokerProtocol interface.

        All conformant brokers (B40 TradierClient, R15 PaperBroker) expose
        ``place_order(**kwargs)`` returning ``{"order": {"id": ...}}``.

        Args:
            order: Order dictionary with keys: symbol, side, quantity,
                   order_type, price (optional), order_id (optional).

        Returns:
            Result dict with at least a ``status`` key.

        Raises:
            RuntimeError: If no FillReconciler is attached in live mode.
        """
        # O-4: Hard kill switch — refuse all new orders when activated.
        # Must be checked FIRST so a KILL_SWITCH/EMERGENCY halt is honoured
        # even when no FillReconciler is attached (e.g. early in startup).
        if self._kill_switch_event.is_set():
            raise RuntimeError(
                "KILL_SWITCH is active — refusing order submission. "
                "Restart the engine to clear the kill switch."
            )
        # O-3: Refuse order submission in live mode without a FillReconciler.
        if self._reconciler is None and self.mode == TradingMode.LIVE:
            raise RuntimeError(
                "No FillReconciler attached — refusing order submission in live mode. "
                "Attach a FillReconciler via SessionSupervisor before starting live trading."
            )
        broker = self.broker
        try:
            try:
                from Tradov.TradovB_Broker.TradovB40_TradierClient import (
                    OrderSide, OrderType as _OrderType, TradierServerError as _TradierServerError,
                )
            except ImportError:
                from TradovB_Broker.TradovB40_TradierClient import (  # type: ignore[no-redef]
                    OrderSide, OrderType as _OrderType, TradierServerError as _TradierServerError,
                )

            side_str = self._resolve_order_side(order)
            _side_map = {
                "buy": OrderSide.BUY,
                "sell": OrderSide.SELL,
                "buy_to_open": OrderSide.BUY_TO_OPEN,
                "buy_to_close": OrderSide.BUY_TO_CLOSE,
                "sell_to_open": OrderSide.SELL_TO_OPEN,
                "sell_to_close": OrderSide.SELL_TO_CLOSE,
            }
            side = _side_map.get(side_str, OrderSide.BUY)
            otype_str = str(order.get("order_type", order.get("type", "market"))).lower()
            _otype_map = {
                "market": _OrderType.MARKET,
                "limit": _OrderType.LIMIT,
                "stop": _OrderType.STOP,
                "stop_limit": _OrderType.STOP_LIMIT,
            }
            otype = _otype_map.get(otype_str, _OrderType.MARKET)
            limit_price = order.get("price") or order.get("limit_price")
            if otype == _OrderType.MARKET:
                limit_price = None

            # P0-9: Stable idempotency tag — Tradier deduplicates within ~24 h.
            order_id_str = str(order.get("order_id") or id(order))
            _tag = f"tradov-{order_id_str}"

            # P0-8: Distinguish Tradier 5xx from other failures so the API
            # panic-mode counter is incremented only on server-side faults.
            try:
                response = broker.place_order(
                    symbol=order["symbol"],
                    side=side,
                    quantity=int(order.get("quantity", 0)),
                    order_type=otype,
                    limit_price=limit_price,
                    tag=_tag,
                )
                self.reset_api_error_count()   # P0-8: clear counter on success
            except _TradierServerError as server_exc:
                self.record_api_server_error()  # P0-8: may trigger EMERGENCY at threshold
                self.logger.error(
                    "Tradier server error (5xx) on place_order: %s", server_exc, exc_info=True
                )
                raise

            tradier_order_id = (response or {}).get("order", {}).get("id")
            return {
                "status": "accepted" if tradier_order_id else "rejected",
                "order_id": order.get("order_id"),
                "tradier_order_id": tradier_order_id,
                "raw": response,
            }
        except _TradierServerError:
            raise  # already logged by the inner block above
        except (TimeoutError, ConnectionError, json.JSONDecodeError, OSError) as exc:
            # N2: Treat transient connectivity/serialization failures as API
            # server-error equivalents so panic mode can engage safely.
            self.record_api_server_error()
            self.logger.error("Transient broker error in _broker_submit: %s", exc, exc_info=True)
            raise
        except Exception as exc:
            self.logger.error("broker.place_order failed: %s", exc, exc_info=True)
            return {"status": "error", "reason": str(exc)}

    def _resolve_order_future(self, order_id: str, order: dict[str, Any], result: dict[str, Any]) -> None:  # noqa: E501
        """Store result in pending_orders and signal the associated Future.

        A2 (v14): take ``_pending_orders_lock`` for the read+write, then release
        before calling ``fut.set_result`` (which invokes user callbacks).
        A11 (v14): ``fut.set_result`` guarded by ``not fut.done()`` so repeated
        resolutions (paper broker double-fill, reconciler re-emit) are idempotent.
        """
        with self._pending_orders_lock:
            entry = self.pending_orders.get(order_id)
            if entry is None:
                self.pending_orders[order_id] = {"order": order, "result": result}
                return
            entry["result"] = result
            fut: concurrent.futures.Future | None = entry.get("future")
        if fut is not None and not fut.done():
            try:
                fut.set_result(result)
            except concurrent.futures.InvalidStateError:
                # Raced with another resolver — already done. Idempotent no-op.
                pass

    def _wait_for_execution(self, order_id: str, timeout: int = ORDER_TIMEOUT_SECONDS) -> dict[str, Any]:  # noqa: E501
        """Block until the broker confirms order execution or timeout expires.

        Waits on a ``concurrent.futures.Future`` pre-registered by
        ``execute_order`` — zero CPU cost until the fill callback fires.
        Falls back to a dict lookup if no Future is registered (e.g. in
        legacy unit test contexts that bypass ``execute_order``).
        """
        entry = self.pending_orders.get(order_id, {})
        fut: concurrent.futures.Future | None = entry.get("future")
        if fut is not None:
            try:
                return fut.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                return {"status": "timeout", "reason": f"Order {order_id} not confirmed within {timeout}s"}  # noqa: E501
            except Exception as exc:
                return {"status": "error", "reason": str(exc)}
        # Fallback: no Future registered — return whatever is already stored.
        result = entry.get("result")
        if result is not None:
            return result
        return {"status": "error", "reason": f"No Future registered for order {order_id}"}

    def _update_execution_metrics(self, order: dict[str, Any], result: dict[str, Any]) -> None:
        """Update rolling execution metrics from a completed order."""
        if result.get("status") == "filled":
            fill_time = result.get("fill_time_ms", 0)
            n = max(1, self.metrics.successful_executions)
            self.metrics.average_fill_time = (
                (self.metrics.average_fill_time * (n - 1) + fill_time) / n
            )
            slippage = result.get("slippage", 0.0)
            self.metrics.average_slippage = (
                (self.metrics.average_slippage * (n - 1) + slippage) / n
            )
        total = max(1, self.metrics.total_orders)
        self.metrics.rejection_rate = self.metrics.failed_executions / total

    # ==========================================================================
    # PRIVATE METHODS - STOP LOSS
    # ==========================================================================

    def _should_trigger_stop_loss(self, position: dict[str, Any]) -> bool:
        """Return True if the position's unrealised loss exceeds its stop level."""
        stop_loss_pct = position.get("stop_loss_pct")
        entry_price = position.get("entry_price", 0)
        current_price = position.get("current_price", entry_price)
        if stop_loss_pct and entry_price > 0:
            loss_pct = (entry_price - current_price) / entry_price
            return loss_pct >= stop_loss_pct
        return False

    def _execute_stop_loss(self, position: dict[str, Any]) -> None:
        """Close a position that has breached its stop-loss level."""
        symbol = position.get("symbol", "UNKNOWN")
        self.logger.warning("Stop-loss triggered for %s — closing position", symbol)
        try:
            # B12 (v15): use the symbol key, not "id" which may be absent or
            # refer to a broker-internal numeric ID unrecognised by close_position.
            self.broker.close_position(symbol, urgency="IMMEDIATE", reason="stop_loss")
        except Exception as exc:
            self.logger.error("Stop-loss close failed for %s: %s", symbol, exc)

    def _gc_pending_orders(self, max_age: timedelta | None = None) -> int:
        """P0-10: Evict pending_orders entries older than *max_age* (default 24 h).

        Returns the number of evicted entries.
        """
        if max_age is None:
            max_age = timedelta(hours=24)
        # B4: Use tz-aware cutoff to match tz-aware submitted_at timestamps.
        cutoff = datetime.now(_ET) - max_age
        # B4: Snapshot keys under the lock; remove outside to minimise lock hold time.
        with self._pending_orders_lock:
            snapshot = list(self.pending_orders.items())
        stale = []
        for oid, entry in snapshot:
            sa = entry.get("submitted_at")
            if sa is None:
                continue
            # B4: Warn and skip naive timestamps — they cannot be safely compared.
            if sa.tzinfo is None:
                self.logger.warning(
                    "GC: pending_order %s has naive submitted_at — skipping eviction", oid
                )
                continue
            if sa < cutoff:
                stale.append(oid)
        with self._pending_orders_lock:
            for oid in stale:
                entry = self.pending_orders.pop(oid, None)
                if entry is not None:
                    self.logger.warning(
                        "GC: evicting stale pending_order %s (age > %s)", oid, max_age
                    )
        return len(stale)

    # ==========================================================================
    # PRIVATE METHODS - EMERGENCY CONTROLS
    # ==========================================================================

    def _cancel_all_pending_orders(self) -> None:
        """Cancel every pending order via the broker.

        A3 (v14): snapshot under ``_pending_orders_lock``, iterate outside the
        lock (broker calls can block), and use ``pop(_, None)`` so concurrent
        terminal events cannot trigger KeyError.
        A8 (v14): collect failed order IDs and escalate to KILL_SWITCH if any
        cancellations fail — a partial-cancel can leave live broker-side orders
        that keep executing against a halted system.
        """
        with self._pending_orders_lock:
            order_ids = list(self.pending_orders.keys())
        failed_order_ids: list[str] = []
        failure_reasons: list[str] = []
        for order_id in order_ids:
            try:
                self.broker.cancel_order(order_id)
                with self._pending_orders_lock:
                    self.pending_orders.pop(order_id, None)
                self.logger.info("Cancelled pending order %s", order_id)
            except Exception as exc:
                failed_order_ids.append(order_id)
                failure_reasons.append(f"{order_id}:{exc}")
                self.logger.error("Failed to cancel order %s: %s", order_id, exc)

        if failed_order_ids and not self._kill_switch_event.is_set():
            reason = (
                f"CANCEL_ALL failed for {len(failed_order_ids)}/{len(order_ids)} orders — "
                f"escalating to KILL_SWITCH: {';'.join(failure_reasons)}"
            )
            self.logger.critical(reason)
            self._kill_switch_event.set()
            try:
                self._write_kill_lock(reason)
            except Exception as exc:  # pragma: no cover
                self.logger.error("Failed to write kill lock: %s", exc)
            try:
                self._event_manager.emit(
                    EventType.KILL_SWITCH,
                    {
                        "reason": reason,
                        "source": "CANCEL_ALL",
                        "failed_order_ids": failed_order_ids,
                    },
                    source="LiveEngine",
                )
            except Exception as exc:  # pragma: no cover
                self.logger.error("Failed to emit KILL_SWITCH: %s", exc)

    def _emergency_cancel_all_orders(self) -> None:
        """Emergency cancellation — drain the queue then cancel all pending orders."""
        # Drain the order queue first so no new orders reach the broker
        while not self.order_queue.empty():
            try:
                self.order_queue.get_nowait()
            except Exception:
                break
        self._cancel_all_pending_orders()

    def _emergency_close_all_positions(self) -> None:
        """Flatten all active positions immediately (Level-3 / portfolio-loss stop).

        A1 (v14): snapshot and purge under ``_active_positions_lock`` so that a
        concurrent ``_monitor_positions`` iteration cannot raise RuntimeError or
        KeyError. Broker calls are made outside the lock.
        """
        self.logger.critical("EMERGENCY: closing all active positions")
        with self._active_positions_lock:
            snapshot = list(self.active_positions.items())
        for symbol, position in snapshot:
            try:
                self.broker.close_position(
                    position.get("id", symbol),
                    urgency="IMMEDIATE",
                    reason="emergency_stop",
                    force=True,
                )
                with self._active_positions_lock:
                    self.active_positions.pop(symbol, None)
                self.logger.info("Emergency-closed position: %s", symbol)
            except Exception as exc:
                self.logger.error("Failed to emergency-close %s: %s", symbol, exc)

    def _send_emergency_alerts(self, reason: str) -> None:
        """Log a critical alert and emit an emergency event."""
        self.logger.critical("EMERGENCY ALERT — trading halted: %s", reason)
        self._emit_event(
            "emergency_stop",
            {
                "reason": reason,
                "account_id": self.config.account_id,
                "timestamp": datetime.now(_ET).isoformat(),
                "daily_loss": self.daily_loss,
                "daily_trades": self.daily_trades,
            },
        )

    def record_kill_switch_drill(
        self,
        operator: str = "operator",
        notes: str = "",
    ) -> None:
        """Stage 4 — record a successful kill-switch / emergency-flatten drill.

        Call this after a controlled paper-mode drill run to reset
        the staleness counter checked by Q14's ``_check_kill_switch_test_staleness``.
        Writes ``~/.tradov_kill_test.json`` with the current timestamp.

        Args:
            operator: Identifier of the person who ran the drill.
            notes:    Free-form notes about the drill outcome.
        """
        import json as _json
        from pathlib import Path as _Path
        _KILL_TEST_PATH = _Path.home() / ".tradov_kill_test.json"
        payload = {
            "last_test_ts": datetime.now(_ET).isoformat(),
            "operator": operator,
            "notes": notes,
            "account_id": self.config.account_id,
        }
        try:
            _KILL_TEST_PATH.write_text(_json.dumps(payload, indent=2), encoding="utf-8")
            self.logger.info(
                "✅ Kill-switch drill recorded (operator=%s notes=%r ts=%s)",
                operator,
                notes,
                payload["last_test_ts"],
            )
        except Exception as exc:
            self.logger.error("Failed to write kill-switch drill record: %s", exc)

    def handle_broker_reconnect(self, reason: str = "broker_disconnect") -> None:
        """Stage 4 — log a structured reconnect attempt with an audit trail.

        Called whenever the broker layer detects a WebSocket or REST disconnect
        and is attempting to reconnect.  Writes a timestamped record so the
        operator / EOD review can see every reconnect that occurred in a session.

        Args:
            reason: Short token describing why reconnect was triggered.
        """
        import json as _json
        from pathlib import Path as _Path
        ts = datetime.now(_ET).isoformat()
        self.logger.warning(
            "BROKER_RECONNECT_ATTEMPT — reason=%s ts=%s account=%s",
            reason,
            ts,
            self.config.account_id,
        )
        # Append to a session-scoped reconnect log in market_data/reconnect_log/
        try:
            log_dir = _Path(__file__).resolve().parents[2] / "market_data" / "reconnect_log"
            log_dir.mkdir(parents=True, exist_ok=True)
            today = datetime.now(_ET).strftime("%Y-%m-%d")
            log_path = log_dir / f"reconnect_{today}.jsonl"
            entry = {
                "ts": ts,
                "reason": reason,
                "account_id": self.config.account_id,
                "daily_trades": self.daily_trades,
                "emergency_stop": self.emergency_stop,
            }
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(_json.dumps(entry) + "\n")
        except Exception as exc:
            self.logger.error("handle_broker_reconnect: failed to write audit log: %s", exc)


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def create_live_engine(
    broker,
    risk_manager,
    config: dict[str, Any],
    telegram_bot: Any = None,
    event_manager: Any = None,
    fill_reconciler: Any = None,
    position_tracker: Any = None,
    trading_engine: Any = None,
) -> LiveEngine:
    """
    Factory function to create live engine.

    Args:
        broker: Broker interface
        risk_manager: Risk manager interface
        config: Configuration dictionary
        telegram_bot: Optional TradovJ05 TelegramBot for high-risk order confirmation.
            When provided, high-risk orders block on an inline-keyboard Approve/Reject
            message before execution.  When None the autonomous risk-decision fallback
            is used instead.
        event_manager: Optional shared EventManager instance. When None the singleton
            from get_event_manager() is used.

    Returns:
        Configured LiveEngine instance
    """
    live_config = LiveTradingConfig(
        account_id=config.get("account_id"),
        max_daily_trades=config.get("max_daily_trades", MAX_DAILY_TRADES),
        max_position_size=config.get("max_position_size", MAX_POSITION_SIZE),
        max_daily_loss=config.get("max_daily_loss", MAX_DAILY_LOSS),
        max_live_trades=config.get("max_live_trades", MAX_LIVE_TRADES),
        max_pair_trades=config.get("max_pair_trades", MAX_PAIR_TRADES),
        max_directional_trades=config.get("max_directional_trades", MAX_DIRECTIONAL_TRADES),
        enable_extended_hours=config.get("enable_extended_hours", False),
        require_confirmation=config.get("require_confirmation", True),
    )

    engine = LiveEngine(
        broker,
        risk_manager,
        live_config,
        telegram_bot=telegram_bot,
        event_manager=event_manager,
        fill_reconciler=fill_reconciler,
        position_tracker=position_tracker,
    )
    if trading_engine is not None:
        engine.set_trading_engine(trading_engine)

    if bool(config.get("use_a02_decision_flow_gate", False)):
        engine._a02_decision_gate_enabled = True

    return engine


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing
    pass
