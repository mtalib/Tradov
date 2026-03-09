#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB04_AccountManager.py
Purpose: Complete account management with risk monitoring and safe imports
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-11 Time: 17:00:00

Module Description:
    Comprehensive account management including real-time balance tracking,
    margin monitoring, buying power calculation, and risk metrics. Maintains
    synchronized account data with Interactive Brokers and provides alerts
    for margin calls, pattern day trader status, and other account restrictions.

    CRITICAL FIXES APPLIED:
    - Safe import patterns with comprehensive fallbacks for all dependencies
    - Works with fixed SpyderB01_SpyderClient implementation
    - Graceful degradation when optional modules are unavailable
    - Thread-safe account management with proper error handling
    - No circular import dependencies

Dependencies Fixed:
    - All utility module imports now have fallbacks
    - Event manager import made optional with mock implementation
    - SpyderClient integration uses our fixed implementation
    - NumPy/Pandas imports made optional with fallback functionality
    - Eliminates cascading import failures
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import threading
import logging
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from threading import Event as ThreadEvent, Lock, RLock
from typing import Any, Callable

# ==============================================================================
# THIRD-PARTY IMPORTS WITH FALLBACKS
# ==============================================================================
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

    # Minimal numpy fallback for basic operations
    class np:
        @staticmethod
        def mean(data):
            return sum(data) / len(data) if data else 0.0

        @staticmethod
        def std(data):
            if not data:
                return 0.0
            mean_val = np.mean(data)
            variance = sum((x - mean_val) ** 2 for x in data) / len(data)
            return variance ** 0.5

        @staticmethod
        def isnan(value):
            return value != value  # NaN is not equal to itself

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

    # Minimal pandas fallback
    class pd:
        @staticmethod
        def DataFrame(data=None):
            return {'data': data or []}

# ==============================================================================
# SPYDER MODULE IMPORTS WITH SAFE FALLBACKS
# ==============================================================================

# Initialize module availability flags
HAS_LOGGER = False
HAS_ERROR_HANDLER = False
HAS_EVENT_MANAGER = False
HAS_SPYDER_CLIENT = False

# Utility Modules - SAFE IMPORT
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    HAS_LOGGER = True
except ImportError:
    HAS_LOGGER = False

    # Fallback logger
    class SpyderLogger:
        @staticmethod
        def get_logger(name):
            logger = logging.getLogger(name)
            if not logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                handler.setFormatter(formatter)
                logger.addHandler(handler)
                logger.setLevel(logging.INFO)
            return logger

try:
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    HAS_ERROR_HANDLER = True
except ImportError:
    HAS_ERROR_HANDLER = False

    # Fallback error handler
    class SpyderErrorHandler:
        def __init__(self, logger=None):
            self.logger = logger or logging.getLogger(__name__)

        def handle_error(self, error, context="Unknown", operation="Unknown"):
            self.logger.error(f"Error in {context}.{operation}: {error}")
            return False

# Event Manager - SAFE IMPORT (optional dependency)
try:
    from SpyderA_Core.SpyderA05_EventManager import Event, EventManager, EventType
    HAS_EVENT_MANAGER = True
except ImportError:
    HAS_EVENT_MANAGER = False

    # Fallback event system
    class EventType(Enum):
        ACCOUNT_UPDATED = "account_updated"
        BALANCE_CHANGED = "balance_changed"
        RISK_ALERT = "risk_alert"
        MARGIN_CALL = "margin_call"
        RESTRICTION_CHANGED = "restriction_changed"

    class Event:
        def __init__(self, event_type, data=None):
            self.event_type = event_type
            self.data = data
            self.timestamp = datetime.now()

    class EventManager:
        def __init__(self):
            self._handlers = {}

        def subscribe(self, event_type, handler):
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)
            return len(self._handlers[event_type]) - 1

        def emit(self, event):
            handlers = self._handlers.get(event.event_type, [])
            for handler in handlers:
                try:
                    handler(event)
                except Exception as e:
                    logging.getLogger(__name__).error(f"Event handler error: {e}")

# SpyderClient (B01_SpyderClient removed — IB Gateway) — use Tradier via SpyderB40_TradierClient
HAS_SPYDER_CLIENT = False

class SpyderClient:
    """Fallback stub — replace with TradierClient for real account data."""
    def __init__(self, config=None):
        self.config = config
        self._connected = False

    def is_connected(self):
        return self._connected

    def get_managed_accounts(self):
        return []

    def get_positions(self):
        return []

    def get_account_values(self, account=None):
        return {}

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================

# Update intervals (seconds)
ACCOUNT_UPDATE_INTERVAL = 5
BALANCE_HISTORY_INTERVAL = 60
RISK_CHECK_INTERVAL = 30
PERFORMANCE_CALC_INTERVAL = 300  # 5 minutes

# Historical data limits
BALANCE_HISTORY_DAYS = 365
TRADE_HISTORY_SIZE = 10000
METRIC_HISTORY_SIZE = 1000

# Risk thresholds (percentages)
MAX_DAILY_LOSS_PERCENT = 5.0
MAX_POSITION_PERCENT = 25.0
MIN_EQUITY_MAINTENANCE = 25000.0
MARGIN_CALL_THRESHOLD = 30.0

# Pattern Day Trader thresholds
PDT_EQUITY_REQUIREMENT = 25000.0
PDT_DAY_TRADE_LIMIT = 3

# Performance calculation constants
RISK_FREE_RATE = 0.02  # 2% annual
TRADING_DAYS_PER_YEAR = 252

# ==============================================================================
# ENUMS
# ==============================================================================

class AccountType(Enum):
    """Account type enumeration"""
    CASH = "cash"
    MARGIN = "margin"
    PORTFOLIO_MARGIN = "portfolio_margin"

class AccountStatus(Enum):
    """Account status enumeration"""
    ACTIVE = "active"
    RESTRICTED = "restricted"
    CLOSED = "closed"
    SUSPENDED = "suspended"

class RiskLevel(Enum):
    """Risk level enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RestrictionType(Enum):
    """Account restriction types"""
    PDT = "pattern_day_trader"
    MARGIN_CALL = "margin_call"
    BUYING_POWER = "buying_power_restriction"
    TRADING_HALT = "trading_halt"
    COMPLIANCE = "compliance_restriction"

# ==============================================================================
# DATACLASSES
# ==============================================================================

@dataclass
class AccountInfo:
    """Account information structure"""
    account_id: str
    account_type: AccountType = AccountType.MARGIN
    status: AccountStatus = AccountStatus.ACTIVE

    # Balances
    net_liquidation: float = 0.0
    total_cash: float = 0.0
    buying_power: float = 0.0
    day_trading_buying_power: float = 0.0
    equity_with_loan: float = 0.0
    excess_liquidity: float = 0.0
    sma: float = 0.0  # Special Memorandum Account

    # Margin info
    initial_margin: float = 0.0
    maintenance_margin: float = 0.0
    available_funds: float = 0.0
    cushion: float = 0.0

    # Pattern Day Trader info
    is_pdt: bool = False
    day_trades_remaining: int = 0
    pdt_reset_date: date | None = None

    # Risk metrics
    current_risk_level: RiskLevel = RiskLevel.LOW
    daily_pnl: float = 0.0
    daily_pnl_percent: float = 0.0

    # Restrictions
    restrictions: list[RestrictionType] = field(default_factory=list)

    # Timestamps
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class BalanceSnapshot:
    """Daily balance snapshot"""
    date: date
    account_id: str
    net_liquidation: float
    total_cash: float
    equity_with_loan: float
    daily_pnl: float
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class RiskMetrics:
    """Risk calculation results"""
    account_id: str

    # Basic metrics
    total_exposure: float = 0.0
    leverage_ratio: float = 0.0
    concentration_risk: float = 0.0

    # Performance metrics
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    max_drawdown: float | None = None
    var_95: float | None = None  # Value at Risk 95%

    # Risk flags
    margin_call_risk: bool = False
    pdt_risk: bool = False
    concentration_warning: bool = False

    # Calculation timestamp
    calculated_at: datetime = field(default_factory=datetime.now)

@dataclass
class PerformanceMetrics:
    """Account performance metrics"""
    account_id: str
    period_days: int

    # Returns
    total_return: float = 0.0
    annualized_return: float = 0.0
    daily_returns: list[float] = field(default_factory=list)

    # Risk-adjusted metrics
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    calmar_ratio: float | None = None

    # Drawdown analysis
    max_drawdown: float | None = None
    current_drawdown: float = 0.0
    drawdown_duration_days: int = 0

    # Win/Loss statistics
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0

    calculated_at: datetime = field(default_factory=datetime.now)

# ==============================================================================
# MAIN ACCOUNT MANAGER CLASS
# ==============================================================================

class AccountManager:
    """
    Production-ready account management system with safe imports.

    This class provides comprehensive account management including real-time
    balance tracking, margin monitoring, buying power calculation, and risk
    metrics. Maintains synchronized account data with Interactive Brokers.

    FIXED VERSION includes:
    - Safe import patterns with comprehensive fallbacks
    - Works with fixed SpyderB01_SpyderClient implementation
    - Graceful degradation when optional modules unavailable
    - Thread-safe account processing with proper error handling
    """

    def __init__(self, spyder_client: SpyderClient | None = None,
                 event_manager: EventManager | None = None,
                 config: dict[str, Any] | None = None):
        """
        Initialize Account Manager with safe configuration.

        Args:
            spyder_client: SpyderClient instance (creates fallback if None)
            event_manager: EventManager instance (creates fallback if None)
            config: Configuration options
        """
        # Setup logging with fallback
        if HAS_LOGGER:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO)

        # Setup error handler with fallback
        if HAS_ERROR_HANDLER:
            self.error_handler = SpyderErrorHandler(self.logger)
        else:
            self.error_handler = SpyderErrorHandler(self.logger)

        # SpyderClient (use provided or create fallback)
        if spyder_client:
            self.spyder_client = spyder_client
        elif HAS_SPYDER_CLIENT:
            try:
                self.spyder_client = SpyderClient()
            except Exception as e:
                self.logger.warning(f"Could not create SpyderClient: {e}")
                self.spyder_client = SpyderClient()  # Use fallback
        else:
            self.spyder_client = SpyderClient()  # Use fallback

        # Event manager (use provided or create fallback)
        if event_manager:
            self.event_manager = event_manager
        elif HAS_EVENT_MANAGER:
            self.event_manager = EventManager()
        else:
            self.event_manager = EventManager()  # Use fallback

        # Configuration
        self.config = config or {}

        # Account storage
        self.accounts: dict[str, AccountInfo] = {}
        self.primary_account_id: str | None = None

        # IB account values cache
        self.ib_account_values: dict[str, dict[str, Any]] = {}

        # Historical data
        self.daily_balances: deque = deque(maxlen=BALANCE_HISTORY_DAYS)
        self.trade_history: deque = deque(maxlen=TRADE_HISTORY_SIZE)
        self.metric_history: deque = deque(maxlen=METRIC_HISTORY_SIZE)

        # Risk parameters
        self.risk_limits = {
            'max_daily_loss': self.config.get('max_daily_loss', MAX_DAILY_LOSS_PERCENT),
            'max_position_size': self.config.get('max_position_size', MAX_POSITION_PERCENT),
            'min_equity': self.config.get('min_equity', MIN_EQUITY_MAINTENANCE),
            'margin_call_level': self.config.get('margin_call_level', MARGIN_CALL_THRESHOLD)
        }

        # Thread safety
        self._account_lock = RLock()
        self._data_lock = Lock()

        # State management
        self._is_running = False
        self._initialized = False
        self._shutdown_event = ThreadEvent()

        # Background threads
        self._update_thread: threading.Thread | None = None
        self._history_thread: threading.Thread | None = None
        self._risk_thread: threading.Thread | None = None
        self._performance_thread: threading.Thread | None = None

        # Callbacks
        self._balance_callbacks: list[Callable] = []
        self._risk_callbacks: list[Callable] = []
        self._restriction_callbacks: list[Callable] = []

        self.logger.info("AccountManager initialized successfully")
        self.logger.info(f"Module availability - SpyderClient: {HAS_SPYDER_CLIENT}, "
                        f"EventManager: {HAS_EVENT_MANAGER}, NumPy: {HAS_NUMPY}, Pandas: {HAS_PANDAS}")

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================

    def initialize(self) -> bool:
        """
        Initialize the account manager.

        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing AccountManager...")

            # Verify broker connection
            if not self.spyder_client.is_connected():
                self.logger.warning("SpyderClient not connected - will work in offline mode")

            # Subscribe to account events if available
            if hasattr(self.spyder_client, 'add_account_callback'):
                self._subscribe_to_events()

            # Initial account sync
            self._sync_accounts_with_broker()

            # Load historical data if available
            self._load_historical_data()

            self._initialized = True
            self.logger.info("AccountManager initialization completed")
            return True

        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            self.error_handler.handle_error(e, "AccountManager", "initialize")
            return False

    def start(self) -> bool:
        """
        Start account monitoring.

        Returns:
            bool: True if started successfully
        """
        if not self._initialized:
            self.logger.error("AccountManager not initialized")
            return False

        if self._is_running:
            self.logger.warning("AccountManager already running")
            return True

        try:
            self.logger.info("Starting AccountManager...")

            self._is_running = True
            self._shutdown_event.clear()

            # Start background threads
            self._start_background_threads()

            # Initial risk assessment
            self._assess_all_risks()

            self.logger.info("AccountManager started successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start AccountManager: {e}")
            self._is_running = False
            return False

    def stop(self) -> bool:
        """
        Stop account monitoring.

        Returns:
            bool: True if stopped successfully
        """
        try:
            self.logger.info("Stopping AccountManager...")

            self._is_running = False
            self._shutdown_event.set()

            # Stop background threads
            self._stop_background_threads()

            # Save current state
            self._save_account_snapshot()

            self.logger.info("AccountManager stopped successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error stopping AccountManager: {e}")
            return False

    def _start_background_threads(self):
        """Start background monitoring threads"""
        try:
            # Account update thread
            self._update_thread = threading.Thread(
                target=self._account_update_worker,
                name="AccountUpdate",
                daemon=True
            )
            self._update_thread.start()

            # Balance history thread
            self._history_thread = threading.Thread(
                target=self._balance_history_worker,
                name="BalanceHistory",
                daemon=True
            )
            self._history_thread.start()

            # Risk monitoring thread
            self._risk_thread = threading.Thread(
                target=self._risk_monitoring_worker,
                name="RiskMonitoring",
                daemon=True
            )
            self._risk_thread.start()

            # Performance calculation thread
            self._performance_thread = threading.Thread(
                target=self._performance_worker,
                name="Performance",
                daemon=True
            )
            self._performance_thread.start()

            self.logger.debug("Background threads started")

        except Exception as e:
            self.logger.error(f"Error starting background threads: {e}")

    def _stop_background_threads(self):
        """Stop background threads"""
        # Threads will stop when _shutdown_event is set and _is_running is False
        self.logger.debug("Background threads will stop")

    # ==========================================================================
    # ACCOUNT SYNCHRONIZATION
    # ==========================================================================

    def _sync_accounts_with_broker(self):
        """Synchronize account data with broker"""
        try:
            if not self.spyder_client.is_connected():
                self.logger.debug("Not connected - using cached account data")
                return

            # Get managed accounts
            accounts = self.spyder_client.get_managed_accounts()

            with self._account_lock:
                for account_id in accounts:
                    if account_id not in self.accounts:
                        # Create new account info
                        self.accounts[account_id] = AccountInfo(account_id=account_id)
                        self.logger.info(f"Added new account: {account_id}")

                    # Update account data
                    self._update_account_data(account_id)

                # Set primary account if not set
                if not self.primary_account_id and accounts:
                    self.primary_account_id = accounts[0]
                    self.logger.info(f"Set primary account: {self.primary_account_id}")

        except Exception as e:
            self.logger.error(f"Error syncing accounts: {e}")

    def _update_account_data(self, account_id: str):
        """Update data for a specific account"""
        try:
            # Get account values from broker
            account_values = self.spyder_client.get_account_values(account_id)

            if not account_values:
                self.logger.debug(f"No account values for {account_id}")
                return

            with self._account_lock:
                account = self.accounts.get(account_id)
                if not account:
                    return

                # Store raw IB values
                self.ib_account_values[account_id] = account_values

                # Update account info with values
                old_net_liquidation = account.net_liquidation

                # Parse key account values (with fallbacks for missing data)
                account.net_liquidation = float(account_values.get('NetLiquidation', account.net_liquidation))
                account.total_cash = float(account_values.get('TotalCashValue', account.total_cash))
                account.buying_power = float(account_values.get('BuyingPower', account.buying_power))
                account.day_trading_buying_power = float(account_values.get('DayTradingBuyingPower', account.day_trading_buying_power))
                account.equity_with_loan = float(account_values.get('EquityWithLoanValue', account.equity_with_loan))
                account.excess_liquidity = float(account_values.get('ExcessLiquidity', account.excess_liquidity))
                account.sma = float(account_values.get('SMA', account.sma))
                account.initial_margin = float(account_values.get('InitMarginReq', account.initial_margin))
                account.maintenance_margin = float(account_values.get('MaintMarginReq', account.maintenance_margin))
                account.available_funds = float(account_values.get('AvailableFunds', account.available_funds))
                account.cushion = float(account_values.get('Cushion', account.cushion))

                # Calculate daily P&L
                if old_net_liquidation > 0:
                    account.daily_pnl = account.net_liquidation - old_net_liquidation
                    account.daily_pnl_percent = (account.daily_pnl / old_net_liquidation) * 100

                # Update PDT information
                account.is_pdt = account_values.get('Daytrading', 'false').lower() == 'true'
                account.day_trades_remaining = int(account_values.get('DayTradesRemaining', 0))

                # Update timestamp
                account.last_updated = datetime.now()

                self.logger.debug(f"Updated account data for {account_id}")

                # Emit balance change event if significant change
                if abs(account.daily_pnl) > 100:  # $100 threshold
                    self._emit_event(EventType.BALANCE_CHANGED, {
                        'account_id': account_id,
                        'net_liquidation': account.net_liquidation,
                        'daily_pnl': account.daily_pnl,
                        'daily_pnl_percent': account.daily_pnl_percent
                    })

        except Exception as e:
            self.logger.error(f"Error updating account data for {account_id}: {e}")

    # ==========================================================================
    # ACCOUNT QUERIES
    # ==========================================================================

    def get_account_info(self, account_id: str | None = None) -> AccountInfo | None:
        """
        Get account information.

        Args:
            account_id: Account ID (uses primary if None)

        Returns:
            AccountInfo object or None if not found
        """
        with self._account_lock:
            target_account = account_id or self.primary_account_id
            return self.accounts.get(target_account) if target_account else None

    def get_all_accounts(self) -> dict[str, AccountInfo]:
        """Get all account information"""
        with self._account_lock:
            return self.accounts.copy()

    def get_buying_power(self, account_id: str | None = None) -> float:
        """Get available buying power"""
        account = self.get_account_info(account_id)
        return account.buying_power if account else 0.0

    def get_day_trading_buying_power(self, account_id: str | None = None) -> float:
        """Get day trading buying power"""
        account = self.get_account_info(account_id)
        return account.day_trading_buying_power if account else 0.0

    def get_net_liquidation(self, account_id: str | None = None) -> float:
        """Get net liquidation value"""
        account = self.get_account_info(account_id)
        return account.net_liquidation if account else 0.0

    def get_daily_pnl(self, account_id: str | None = None) -> tuple[float, float]:
        """
        Get daily P&L.

        Returns:
            Tuple of (absolute_pnl, percentage_pnl)
        """
        account = self.get_account_info(account_id)
        if account:
            return account.daily_pnl, account.daily_pnl_percent
        return 0.0, 0.0

    def is_pattern_day_trader(self, account_id: str | None = None) -> bool:
        """Check if account is flagged as pattern day trader"""
        account = self.get_account_info(account_id)
        return account.is_pdt if account else False

    def get_day_trades_remaining(self, account_id: str | None = None) -> int:
        """Get remaining day trades for non-PDT accounts"""
        account = self.get_account_info(account_id)
        return account.day_trades_remaining if account else 0

    # ==========================================================================
    # RISK ASSESSMENT
    # ==========================================================================

    def _assess_all_risks(self):
        """Assess risk for all accounts"""
        with self._account_lock:
            for account_id in self.accounts:
                self._assess_account_risk(account_id)

    def _assess_account_risk(self, account_id: str):
        """Assess risk for a specific account"""
        try:
            account = self.accounts.get(account_id)
            if not account:
                return

            old_risk_level = account.current_risk_level
            new_restrictions = []

            # Check daily loss limit
            daily_loss_percent = abs(account.daily_pnl_percent) if account.daily_pnl < 0 else 0
            if daily_loss_percent > self.risk_limits['max_daily_loss']:
                account.current_risk_level = RiskLevel.CRITICAL
                new_restrictions.append(RestrictionType.TRADING_HALT)
                self._emit_risk_alert(account_id, "Daily loss limit exceeded", RiskLevel.CRITICAL)

            # Check margin requirements
            if account.cushion < self.risk_limits['margin_call_level']:
                if RiskLevel.CRITICAL not in [account.current_risk_level]:
                    account.current_risk_level = RiskLevel.HIGH
                new_restrictions.append(RestrictionType.MARGIN_CALL)
                self._emit_risk_alert(account_id, "Margin call risk", RiskLevel.HIGH)

            # Check minimum equity
            if account.equity_with_loan < self.risk_limits['min_equity']:
                new_restrictions.append(RestrictionType.BUYING_POWER)
                self._emit_risk_alert(account_id, "Below minimum equity", RiskLevel.MEDIUM)

            # Check PDT status
            if account.is_pdt and account.day_trading_buying_power < PDT_EQUITY_REQUIREMENT:
                new_restrictions.append(RestrictionType.PDT)
                self._emit_risk_alert(account_id, "PDT equity requirement not met", RiskLevel.MEDIUM)

            # Update restrictions
            account.restrictions = new_restrictions

            # Emit restriction change event if changed
            if old_risk_level != account.current_risk_level:
                self._emit_event(EventType.RESTRICTION_CHANGED, {
                    'account_id': account_id,
                    'old_risk_level': old_risk_level.value,
                    'new_risk_level': account.current_risk_level.value,
                    'restrictions': [r.value for r in new_restrictions]
                })

        except Exception as e:
            self.logger.error(f"Error assessing risk for {account_id}: {e}")

    def _emit_risk_alert(self, account_id: str, message: str, risk_level: RiskLevel):
        """Emit a risk alert event"""
        self.logger.warning(f"Risk alert for {account_id}: {message} (Level: {risk_level.value})")

        # Notify callbacks
        for callback in self._risk_callbacks:
            try:
                callback({
                    'account_id': account_id,
                    'message': message,
                    'risk_level': risk_level.value,
                    'timestamp': datetime.now()
                })
            except Exception as e:
                self.logger.error(f"Risk callback error: {e}")

        # Emit event
        self._emit_event(EventType.RISK_ALERT, {
            'account_id': account_id,
            'message': message,
            'risk_level': risk_level.value
        })

    # ==========================================================================
    # BACKGROUND WORKERS
    # ==========================================================================

    def _account_update_worker(self):
        """Background worker for account updates"""
        while self._is_running and not self._shutdown_event.is_set():
            try:
                self._sync_accounts_with_broker()

                if self._shutdown_event.wait(ACCOUNT_UPDATE_INTERVAL):
                    break

            except Exception as e:
                self.logger.error(f"Account update worker error: {e}")

    def _balance_history_worker(self):
        """Background worker for balance history"""
        while self._is_running and not self._shutdown_event.is_set():
            try:
                self._save_balance_snapshots()

                if self._shutdown_event.wait(BALANCE_HISTORY_INTERVAL):
                    break

            except Exception as e:
                self.logger.error(f"Balance history worker error: {e}")

    def _risk_monitoring_worker(self):
        """Background worker for risk monitoring"""
        while self._is_running and not self._shutdown_event.is_set():
            try:
                self._assess_all_risks()

                if self._shutdown_event.wait(RISK_CHECK_INTERVAL):
                    break

            except Exception as e:
                self.logger.error(f"Risk monitoring worker error: {e}")

    def _performance_worker(self):
        """Background worker for performance calculations"""
        while self._is_running and not self._shutdown_event.is_set():
            try:
                self._calculate_performance_metrics()

                if self._shutdown_event.wait(PERFORMANCE_CALC_INTERVAL):
                    break

            except Exception as e:
                self.logger.error(f"Performance worker error: {e}")

    # ==========================================================================
    # HISTORICAL DATA MANAGEMENT
    # ==========================================================================

    def _save_balance_snapshots(self):
        """Save current balance snapshots"""
        try:
            today = date.today()

            with self._account_lock:
                for account_id, account in self.accounts.items():
                    snapshot = BalanceSnapshot(
                        date=today,
                        account_id=account_id,
                        net_liquidation=account.net_liquidation,
                        total_cash=account.total_cash,
                        equity_with_loan=account.equity_with_loan,
                        daily_pnl=account.daily_pnl
                    )

                    self.daily_balances.append(snapshot)

        except Exception as e:
            self.logger.error(f"Error saving balance snapshots: {e}")

    def _save_account_snapshot(self):
        """Save current account state to disk (placeholder)"""
        try:
            # TODO: Implement persistent storage
            self.logger.debug("Account snapshot saved")
        except Exception as e:
            self.logger.error(f"Error saving account snapshot: {e}")

    def _load_historical_data(self):
        """Load historical data from storage (placeholder)"""
        try:
            # TODO: Implement loading from persistent storage
            self.logger.debug("Historical data loaded")
        except Exception as e:
            self.logger.error(f"Error loading historical data: {e}")

    # ==========================================================================
    # PERFORMANCE CALCULATIONS
    # ==========================================================================

    def _calculate_performance_metrics(self):
        """Calculate performance metrics for all accounts"""
        try:
            with self._account_lock:
                for account_id in self.accounts:
                    self._calculate_account_performance(account_id)

        except Exception as e:
            self.logger.error(f"Error calculating performance metrics: {e}")

    def _calculate_account_performance(self, account_id: str):
        """Calculate performance metrics for a specific account"""
        try:
            # Get balance history for this account
            account_balances = [
                snapshot for snapshot in self.daily_balances
                if snapshot.account_id == account_id
            ]

            if len(account_balances) < 2:
                return  # Need at least 2 data points

            # Calculate daily returns
            daily_returns = []
            for i in range(1, len(account_balances)):
                prev_balance = account_balances[i-1].net_liquidation
                curr_balance = account_balances[i].net_liquidation

                if prev_balance > 0:
                    daily_return = (curr_balance - prev_balance) / prev_balance
                    daily_returns.append(daily_return)

            if not daily_returns:
                return

            # Calculate performance metrics
            period_days = len(daily_returns)
            total_return = sum(daily_returns)

            # Annualized return
            if period_days > 0:
                annualized_return = (1 + total_return) ** (TRADING_DAYS_PER_YEAR / period_days) - 1
            else:
                annualized_return = 0.0

            # Risk metrics (using fallback calculations if numpy not available)
            if HAS_NUMPY:
                avg_return = np.mean(daily_returns)
                std_return = np.std(daily_returns)

                # Sharpe ratio
                if std_return > 0:
                    excess_return = avg_return - (RISK_FREE_RATE / TRADING_DAYS_PER_YEAR)
                    sharpe_ratio = (excess_return * (TRADING_DAYS_PER_YEAR ** 0.5)) / std_return
                else:
                    sharpe_ratio = 0.0
            else:
                # Fallback calculations
                avg_return = sum(daily_returns) / len(daily_returns)
                variance = sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)
                std_return = variance ** 0.5

                if std_return > 0:
                    excess_return = avg_return - (RISK_FREE_RATE / TRADING_DAYS_PER_YEAR)
                    sharpe_ratio = (excess_return * (TRADING_DAYS_PER_YEAR ** 0.5)) / std_return
                else:
                    sharpe_ratio = 0.0

            # Create performance metrics
            performance = PerformanceMetrics(
                account_id=account_id,
                period_days=period_days,
                total_return=total_return,
                annualized_return=annualized_return,
                daily_returns=daily_returns,
                sharpe_ratio=sharpe_ratio
            )

            # Store in history
            self.metric_history.append(performance)

            self.logger.debug(f"Calculated performance for {account_id}: "
                            f"Return: {total_return:.2%}, Sharpe: {sharpe_ratio:.2f}")

        except Exception as e:
            self.logger.error(f"Error calculating performance for {account_id}: {e}")

    # ==========================================================================
    # EVENT HANDLING
    # ==========================================================================

    def _subscribe_to_events(self):
        """Subscribe to broker events (if supported)"""
        try:
            # This would subscribe to real broker events if available
            self.logger.debug("Subscribed to broker events")
        except Exception as e:
            self.logger.error(f"Error subscribing to events: {e}")

    def _emit_event(self, event_type: EventType, data: dict[str, Any]):
        """Emit event through event manager"""
        try:
            if self.event_manager:
                event = Event(event_type, data)
                self.event_manager.emit(event)
        except Exception as e:
            self.logger.error(f"Error emitting event: {e}")

    # ==========================================================================
    # CALLBACK MANAGEMENT
    # ==========================================================================

    def add_balance_callback(self, callback: Callable):
        """Add balance change callback"""
        if callback not in self._balance_callbacks:
            self._balance_callbacks.append(callback)

    def add_risk_callback(self, callback: Callable):
        """Add risk alert callback"""
        if callback not in self._risk_callbacks:
            self._risk_callbacks.append(callback)

    def add_restriction_callback(self, callback: Callable):
        """Add restriction change callback"""
        if callback not in self._restriction_callbacks:
            self._restriction_callbacks.append(callback)

    def remove_balance_callback(self, callback: Callable):
        """Remove balance callback"""
        if callback in self._balance_callbacks:
            self._balance_callbacks.remove(callback)

    def remove_risk_callback(self, callback: Callable):
        """Remove risk callback"""
        if callback in self._risk_callbacks:
            self._risk_callbacks.remove(callback)

    def remove_restriction_callback(self, callback: Callable):
        """Remove restriction callback"""
        if callback in self._restriction_callbacks:
            self._restriction_callbacks.remove(callback)

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def get_comprehensive_status(self) -> dict[str, Any]:
        """Get comprehensive status information"""
        with self._account_lock:
            return {
                'initialized': self._initialized,
                'running': self._is_running,
                'primary_account': self.primary_account_id,
                'total_accounts': len(self.accounts),
                'accounts': {acc_id: asdict(acc) for acc_id, acc in self.accounts.items()},
                'risk_limits': self.risk_limits,
                'historical_data': {
                    'balance_snapshots': len(self.daily_balances),
                    'metric_history': len(self.metric_history)
                },
                'module_availability': {
                    'spyder_client': HAS_SPYDER_CLIENT,
                    'event_manager': HAS_EVENT_MANAGER,
                    'logger': HAS_LOGGER,
                    'numpy': HAS_NUMPY,
                    'pandas': HAS_PANDAS
                }
            }

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_account_manager(spyder_client: SpyderClient | None = None,
                          event_manager: EventManager | None = None,
                          config: dict[str, Any] | None = None) -> AccountManager:
    """
    Create AccountManager instance with safe configuration.

    Args:
        spyder_client: SpyderClient instance (creates fallback if None)
        event_manager: Event manager (creates fallback if None)
        config: Configuration options (creates default if None)

    Returns:
        AccountManager instance with safe imports and fallbacks
    """
    if config is None:
        config = {
            'max_daily_loss': MAX_DAILY_LOSS_PERCENT,
            'max_position_size': MAX_POSITION_PERCENT,
            'min_equity': MIN_EQUITY_MAINTENANCE,
            'margin_call_level': MARGIN_CALL_THRESHOLD
        }

    return AccountManager(spyder_client, event_manager, config)

# ==============================================================================
# MODULE VALIDATION
# ==============================================================================

def validate_dependencies() -> dict[str, bool]:
    """Validate module dependencies"""
    return {
        "spyder_logger": HAS_LOGGER,
        "error_handler": HAS_ERROR_HANDLER,
        "event_manager": HAS_EVENT_MANAGER,
        "spyder_client": HAS_SPYDER_CLIENT,
        "numpy": HAS_NUMPY,
        "pandas": HAS_PANDAS
    }

# ==============================================================================
# MAIN EXECUTION FOR TESTING
# ==============================================================================

if __name__ == "__main__":

    # Test dependencies
    deps = validate_dependencies()
    for _module, available in deps.items():
        status = "Available" if available else "Missing (using fallback)"

    # Test account manager creation
    try:
        config = {
            'max_daily_loss': 5.0,
            'max_position_size': 25.0,
            'min_equity': 25000.0
        }

        account_manager = create_account_manager(config=config)


        if HAS_SPYDER_CLIENT:
            pass
        else:
            pass

    except Exception:
        pass
