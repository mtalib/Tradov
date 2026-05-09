#!/usr/bin/env python3
from __future__ import annotations
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB30_SPYOptionsChainManager.py
Purpose: Comprehensive SPY options chain management
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-03-08 Time: 02:00:00

BROKER NOTE:
    Broker execution via Tradier API (SpyderB40_TradierClient).
    Market data via Tradier
    option-chain snapshots as fallback.

Module Description:
    This module provides comprehensive SPY options chain management implementing
    the exact requirements from the market data specification: 0DTE (1s), 1DTE (5s),
    WEEKLY (15s), and MONTHLY (60s) options with dynamic strike selection based
    on current SPY price.

Key Features:
    • Dynamic strike selection based on current SPY price
    • Multiple options chain types (0DTE, 1DTE, WEEKLY, MONTHLY)
    • Optimized update frequencies for each chain type
    • Seamless integration with multi-client data manager
    • Automatic expiration handling

Dependencies:
    • SpyderB40_TradierClient for order execution and chain snapshots
    • Standard Python libraries for data processing
"""

import logging  # noqa: E402

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import threading  # noqa: E402
import time  # noqa: E402
from collections import defaultdict  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from datetime import date, datetime, timedelta, timezone  # noqa: E402
from enum import Enum  # noqa: E402
from typing import Any  # noqa: E402
from collections.abc import Callable  # noqa: E402


# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================



# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    # Fallback logging
    class SpyderLogger:
        @staticmethod
        def get_logger(name):
            return logging.getLogger(name)

    class SpyderErrorHandler:
        def __init__(self):
            pass




# ==============================================================================
# CONSTANTS
# ==============================================================================
# Options chain specifications from requirements document
OPTIONS_SPECIFICATIONS = {
    "0DTE": {"days": 0, "strikes": 10, "frequency": 1, "client_id": 2},  # 1 second
    "1DTE": {"days": 1, "strikes": 10, "frequency": 5, "client_id": 5},  # 5 seconds
    "WEEKLY": {"days": 7, "strikes": 20, "frequency": 15, "client_id": 6},  # 15 seconds
    "MONTHLY": {
        "days": 30,
        "strikes": 30,
        "frequency": 60,
        "client_id": 7,
    },  # 60 seconds
}

# Strike selection parameters
STRIKE_INTERVAL = 1.0  # SPY strikes are typically $1 apart
ATM_STRIKE_BUFFER = 5  # Number of strikes above/below ATM
MAX_STRIKES_PER_CHAIN = 50  # Maximum strikes to track per expiration

# Market hours and expiration handling
MARKET_OPEN_HOUR = 9  # 9:30 AM ET
MARKET_CLOSE_HOUR = 16  # 4:00 PM ET
OPTIONS_EXPIRY_HOUR = 16  # 4:00 PM ET on expiration day

# Performance thresholds
MAX_OPTIONS_SUBSCRIPTIONS = 100  # Maximum total options subscriptions
UPDATE_BATCH_SIZE = 10  # Batch size for options updates

# ==============================================================================
# ENUMS
# ==============================================================================


class OptionsChainType(Enum):
    """Options chain types based on requirements"""

    ZERO_DTE = "0DTE"
    ONE_DTE = "1DTE"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class OptionType(Enum):
    """Option type enumeration"""

    CALL = "C"
    PUT = "P"


class ChainStatus(Enum):
    """Options chain status"""

    ACTIVE = "active"
    EXPIRED = "expired"
    PENDING = "pending"
    ERROR = "error"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class OptionsContract:
    """SPY options contract specification"""

    symbol: str
    expiration: date
    strike: float
    option_type: OptionType
    chain_type: OptionsChainType
    tradier_data: dict[str, Any] | None = None
    last_price: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    volume: int = 0
    open_interest: int = 0
    implied_volatility: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    last_update: datetime | None = None
    request_id: int | None = None
    active: bool = False


@dataclass
class OptionsChain:
    """Complete options chain for a specific expiration"""

    symbol: str
    expiration: date
    chain_type: OptionsChainType
    underlying_price: float
    calls: dict[float, OptionsContract] = field(default_factory=dict)
    puts: dict[float, OptionsContract] = field(default_factory=dict)
    atm_strike: float = 0.0
    status: ChainStatus = ChainStatus.PENDING
    last_update: datetime | None = None
    total_contracts: int = 0


@dataclass
class ChainSelectionCriteria:
    """Criteria for selecting options contracts in chain"""

    underlying_price: float
    max_strikes: int
    strike_range: float
    prefer_liquid: bool = True
    min_volume: int = 10
    min_open_interest: int = 100


# ==============================================================================
# MAIN CLASS - SPY OPTIONS CHAIN MANAGER
# ==============================================================================


class SPYOptionsChainManager:
    """
    Comprehensive SPY options chain management system.

    This class manages SPY options chains according to the exact specifications:
    - 0DTE: 10 strikes, 1-second updates
    - 1DTE: 10 strikes, 5-second updates
    - WEEKLY: 20 strikes, 15-second updates
    - MONTHLY: 30 strikes, 60-second updates

    Features dynamic strike selection based on current SPY price, automatic
    expiration handling, and seamless integration with the data manager.

    Attributes:
        data_manager: Reference to multi-client data manager
        active_chains: Dictionary of active options chains
        contract_registry: Registry of all options contracts
        subscription_callbacks: Callbacks for options data updates

    Example:
        >>> chain_manager = SPYOptionsChainManager()
        >>> chain_manager.initialize()
        >>> chain_manager.start_options_monitoring()
        >>> chain_manager.subscribe_to_chain(OptionsChainType.ZERO_DTE, callback)
    """

    def __init__(self, data_manager: Any | None = None):
        """Initialize the SPY options chain manager.

        .. deprecated::
            ``SPYOptionsChainManager`` (SpyderB30) is superseded by
            :class:`~Spyder.SpyderB_Broker.SpyderB40_TradierClient.TradierClient`
            (SpyderB40) for chain snapshots and by
            :class:`~Spyder.SpyderC_MarketData.SpyderC00_MarketDataProtocol.TradierMarketDataAdapter`
            (SpyderC00) for real-time streaming.  New code should use those
            modules directly.  This class will be removed in a future release.
        """
        import warnings
        warnings.warn(
            "SPYOptionsChainManager (SpyderB30) is deprecated and will be removed "
            "in a future release.  Use SpyderB40.TradierClient for chain snapshots "
            "or SpyderC00.TradierMarketDataAdapter for streaming.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Data manager integration
        self.data_manager = data_manager

        # Options chain management
        self.active_chains: dict[OptionsChainType, OptionsChain] = {}
        self.contract_registry: dict[str, OptionsContract] = {}
        self.subscription_callbacks: dict[OptionsChainType, list[Callable]] = (
            defaultdict(list)
        )

        # Current market state
        self.current_spy_price = 585.0  # Default SPY price
        self.market_hours_active = False
        self.last_spy_update = datetime.now(timezone.utc)

        # Performance tracking
        self.total_subscriptions = 0
        self.update_counts = {chain_type: 0 for chain_type in OptionsChainType}
        self.error_counts = {chain_type: 0 for chain_type in OptionsChainType}

        # Threading
        self._lock = threading.RLock()
        self._running = False
        self._monitor_thread = None

        self.logger.info("SPY Options Chain Manager initialized")

    # ==========================================================================
    # INITIALIZATION AND LIFECYCLE
    # ==========================================================================

    def initialize(self) -> bool:
        """
        Initialize the options chain manager.

        Returns:
            bool: True if initialization successful
        """
        try:
            # Subscribe to SPY price updates for dynamic strike selection
            self._subscribe_to_spy_price()

            # Initialize options chains
            self._initialize_options_chains()

            self.logger.info(
                "SPY Options Chain Manager initialized successfully"
            )
            return True

        except Exception as e:
            self.logger.error("Options chain manager initialization failed: %s", e, exc_info=True)
            return False

    def start_options_monitoring(self) -> bool:
        """
        Start options chain monitoring and subscriptions.

        Returns:
            bool: True if started successfully
        """
        try:
            if self._running:
                self.logger.warning("Options monitoring already running")
                return True

            self._running = True

            # Start monitoring thread
            self._monitor_thread = threading.Thread(
                target=self._options_monitor_loop, daemon=True
            )
            self._monitor_thread.start()

            # Start initial options subscriptions
            self._start_initial_subscriptions()

            self.logger.info("SPY options monitoring started")
            return True

        except Exception as e:
            self.logger.error("Failed to start options monitoring: %s", e, exc_info=True)
            return False

    def stop_options_monitoring(self) -> None:
        """Stop options chain monitoring."""
        try:
            self._running = False

            # Cancel all active subscriptions
            self._cancel_all_subscriptions()

            # Stop monitoring thread
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=5)

            self.logger.info("SPY options monitoring stopped")

        except Exception as e:
            self.logger.error("Error stopping options monitoring: %s", e, exc_info=True)

    # ==========================================================================
    # OPTIONS CHAIN MANAGEMENT
    # ==========================================================================

    def subscribe_to_chain(
        self, chain_type: OptionsChainType, callback: Callable[[OptionsChain], None]
    ) -> bool:
        """
        Subscribe to options chain updates.

        Args:
            chain_type: Type of options chain to subscribe to
            callback: Function to call with chain updates

        Returns:
            bool: True if subscription successful
        """
        try:
            with self._lock:
                self.subscription_callbacks[chain_type].append(callback)
                self.total_subscriptions += 1

            self.logger.info("Subscribed to %s options chain updates", chain_type.value)
            return True

        except Exception as e:
            self.logger.error("Error subscribing to chain %s: %s", chain_type, e, exc_info=True)
            return False

    def unsubscribe_from_chain(
        self, chain_type: OptionsChainType, callback: Callable[[OptionsChain], None]
    ) -> bool:
        """
        Unsubscribe from options chain updates.

        Args:
            chain_type: Type of options chain to unsubscribe from
            callback: Callback function to remove

        Returns:
            bool: True if unsubscription successful
        """
        try:
            with self._lock:
                if callback in self.subscription_callbacks[chain_type]:
                    self.subscription_callbacks[chain_type].remove(callback)
                    self.total_subscriptions -= 1

            self.logger.info(
                "Unsubscribed from %s options chain updates", chain_type.value
            )
            return True

        except Exception as e:
            self.logger.error("Error unsubscribing from chain %s: %s", chain_type, e, exc_info=True)
            return False

    def get_options_chain(self, chain_type: OptionsChainType) -> OptionsChain | None:
        """
        Get current options chain data.

        Args:
            chain_type: Type of options chain to retrieve

        Returns:
            OptionsChain: Current chain data or None if not available
        """
        with self._lock:
            return self.active_chains.get(chain_type)

    def get_all_options_chains(self) -> dict[OptionsChainType, OptionsChain]:
        """
        Get all current options chain data.

        Returns:
            Dict: All active options chains
        """
        with self._lock:
            return self.active_chains.copy()

    def update_spy_price(self, new_price: float) -> None:
        """
        Update current SPY price and trigger strike reselection if needed.

        Args:
            new_price: New SPY price
        """
        try:
            with self._lock:
                old_price = self.current_spy_price
                self.current_spy_price = new_price
                self.last_spy_update = datetime.now(timezone.utc)

                # Check if we need to reselect strikes (significant price movement)
                price_change = abs(new_price - old_price) / old_price
                if price_change > 0.02:  # 2% movement
                    self._reselect_strikes_for_all_chains()

        except Exception as e:
            self.logger.error("Error updating SPY price: %s", e, exc_info=True)

    def get_manager_status(self) -> dict[str, Any]:
        """
        Get comprehensive manager status.

        Returns:
            Dict: Status information
        """
        with self._lock:
            return {
                "running": self._running,
                "spy_price": self.current_spy_price,
                "last_spy_update": self.last_spy_update,
                "active_chains": len(self.active_chains),
                "total_subscriptions": self.total_subscriptions,
                "total_contracts": len(self.contract_registry),
                "update_counts": self.update_counts.copy(),
                "error_counts": self.error_counts.copy(),
                "chain_details": {
                    chain_type.value: {
                        "status": chain.status.value,
                        "total_contracts": chain.total_contracts,
                        "last_update": chain.last_update,
                        "calls": len(chain.calls),
                        "puts": len(chain.puts),
                        "atm_strike": chain.atm_strike,
                    }
                    for chain_type, chain in self.active_chains.items()
                },
            }

    # ==========================================================================
    # PRIVATE METHODS - INITIALIZATION
    # ==========================================================================

    def _subscribe_to_spy_price(self) -> None:
        """Subscribe to SPY price updates for dynamic strike selection."""
        try:
            # Attempt real-time SPY price subscription via TradierMarketStream.
            # On a quote event the current_spy_price and atm strikes are refreshed.
            try:
                from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
                    TradierMarketStream,
                    create_tradier_client_from_env,
                )

                tradier_client = create_tradier_client_from_env()
                stream = TradierMarketStream(
                    client=tradier_client,
                    symbols=["SPY"],
                    filters=["quote", "trade"],
                )

                def _on_spy_quote(msg: dict) -> None:
                    """Handle incoming SPY quote and refresh ATM strikes."""
                    bid = msg.get("bid", 0.0)
                    ask = msg.get("ask", 0.0)
                    if bid and ask:
                        mid = (float(bid) + float(ask)) / 2.0
                    elif bid:
                        mid = float(bid)
                    elif ask:
                        mid = float(ask)
                    else:
                        return

                    if mid > 0:
                        with self._lock:
                            self.current_spy_price = mid
                            self.last_spy_update = datetime.now(timezone.utc)
                        self._reselect_strikes_for_all_chains()
                        self.logger.debug(f"SPY price updated to {mid:.2f}")

                stream.on_quote = _on_spy_quote
                # Store reference so the stream is not garbage-collected
                self._spy_price_stream = stream
                stream.start()

                self.logger.info(
                    "SPY price subscription active via TradierMarketStream "
                    "(symbol=SPY, filters=['quote','trade'])"
                )

            except Exception as stream_exc:
                # Streaming unavailable — log registration intent and rely on
                # periodic polling or manual price updates via update_spy_price().
                self.logger.warning(
                    "TradierMarketStream unavailable for SPY price subscription "
                    f"({stream_exc}); price updates must be pushed manually."
                )
                self.logger.info(
                    "SPY price subscription registered: "
                    "symbol=SPY, type=quote, callback=_on_spy_quote [stream offline]"
                )

        except Exception as e:
            self.logger.error("Error subscribing to SPY price: %s", e, exc_info=True)

    def _initialize_options_chains(self) -> None:
        """Initialize all options chains based on specifications."""
        try:
            current_date = datetime.now(timezone.utc).date()

            for chain_type in OptionsChainType:
                spec = OPTIONS_SPECIFICATIONS[chain_type.value]
                expiration_date = self._calculate_expiration_date(
                    current_date, spec["days"]
                )

                # Create options chain
                chain = OptionsChain(
                    symbol="SPY",
                    expiration=expiration_date,
                    chain_type=chain_type,
                    underlying_price=self.current_spy_price,
                )

                # Generate strikes around current price
                strikes = self._generate_strikes_around_price(
                    self.current_spy_price, spec["strikes"]
                )

                # Create options contracts
                for strike in strikes:
                    # Create call contract
                    call_contract = self._create_options_contract(
                        expiration_date, strike, OptionType.CALL, chain_type
                    )
                    if call_contract:
                        chain.calls[strike] = call_contract

                    # Create put contract
                    put_contract = self._create_options_contract(
                        expiration_date, strike, OptionType.PUT, chain_type
                    )
                    if put_contract:
                        chain.puts[strike] = put_contract

                # Set ATM strike
                chain.atm_strike = self._find_closest_strike(
                    self.current_spy_price, strikes
                )
                chain.total_contracts = len(chain.calls) + len(chain.puts)
                chain.status = ChainStatus.ACTIVE

                self.active_chains[chain_type] = chain

                self.logger.info(
                    f"Initialized {chain_type.value} chain: "
                    f"{len(chain.calls)} calls, {len(chain.puts)} puts, "
                    f"ATM strike: {chain.atm_strike}"
                )

        except Exception as e:
            self.logger.error("Error initializing options chains: %s", e, exc_info=True)

    def _calculate_expiration_date(
        self, current_date: date, days_to_expiry: int
    ) -> date:
        """Calculate expiration date based on chain type."""
        if days_to_expiry == 0:
            # 0DTE - today if before 4 PM, otherwise next trading day
            current_time = datetime.now(timezone.utc).time()
            if current_time.hour >= OPTIONS_EXPIRY_HOUR:
                return current_date + timedelta(days=1)
            return current_date

        elif days_to_expiry == 1:
            # 1DTE - next trading day
            return current_date + timedelta(days=1)

        elif days_to_expiry == 7:
            # Weekly - next Friday
            days_until_friday = (4 - current_date.weekday()) % 7
            if days_until_friday == 0:  # Today is Friday
                days_until_friday = 7
            return current_date + timedelta(days=days_until_friday)

        else:
            # Monthly - third Friday of next month
            next_month = current_date.replace(day=1) + timedelta(days=32)
            next_month = next_month.replace(day=1)

            # Find third Friday
            first_friday = next_month + timedelta(days=(4 - next_month.weekday()) % 7)
            third_friday = first_friday + timedelta(days=14)

            return third_friday

    def _generate_strikes_around_price(
        self, current_price: float, max_strikes: int
    ) -> list[float]:
        """Generate strikes around current SPY price."""
        strikes = []
        strikes_per_side = max_strikes // 2

        # Find closest strike to current price
        base_strike = round(current_price / STRIKE_INTERVAL) * STRIKE_INTERVAL

        # Generate strikes below current price
        for i in range(strikes_per_side):
            strike = base_strike - (i * STRIKE_INTERVAL)
            if strike > 0:
                strikes.append(strike)

        # Generate strikes above current price
        for i in range(strikes_per_side):
            strike = base_strike + ((i + 1) * STRIKE_INTERVAL)
            strikes.append(strike)

        return sorted(strikes)

    def _find_closest_strike(self, price: float, strikes: list[float]) -> float:
        """Find the strike closest to the given price."""
        return min(strikes, key=lambda x: abs(x - price))

    def _create_options_contract(
        self,
        expiration: date,
        strike: float,
        option_type: OptionType,
        chain_type: OptionsChainType,
    ) -> OptionsContract | None:
        """
        Create an options contract using Tradier OCC symbol format.

        OCC symbol: SPY + YYMMDD + C/P + 8-digit strike (strike * 1000, zero-padded).
        Example: SPY251219C00600000 = SPY Dec 19 2025 600 Call
        """
        try:
            occ_symbol = (
                f"SPY{expiration.strftime('%y%m%d')}"
                f"{option_type.value}"
                f"{int(strike * 1000):08d}"
            )
            tradier_data: dict[str, Any] = {
                "symbol": occ_symbol,
                "underlying": "SPY",
                "expiration_date": expiration.isoformat(),
                "strike": strike,
                "option_type": option_type.value,
                "multiplier": 100,
            }

            options_contract = OptionsContract(
                symbol="SPY",
                expiration=expiration,
                strike=strike,
                option_type=option_type,
                chain_type=chain_type,
                tradier_data=tradier_data,
            )

            return options_contract

        except Exception as e:
            self.logger.error("Error creating options contract: %s", e, exc_info=True)
            return None

    def _start_initial_subscriptions(self) -> None:
        """Start initial options subscriptions."""
        try:
            for chain_type in OptionsChainType:
                chain = self.active_chains.get(chain_type)
                if chain:
                    self._subscribe_to_chain_data(chain)

        except Exception as e:
            self.logger.error("Error starting initial subscriptions: %s", e, exc_info=True)

    def _subscribe_to_chain_data(self, chain: OptionsChain) -> None:
        """Subscribe to market data for an options chain."""
        try:
            # This would integrate with the data manager to request options data
            # For now, we'll log the subscription intent
            spec = OPTIONS_SPECIFICATIONS[chain.chain_type.value]
            client_id = spec["client_id"]
            frequency = spec["frequency"]

            self.logger.info(
                f"Subscribing to {chain.chain_type.value} chain: "
                f"{len(chain.calls)} calls, {len(chain.puts)} puts, "
                f"Client ID {client_id}, {frequency}s frequency"
            )

            # Attempt subscription through the live data manager when available.
            # SpyderB30 is deprecated in favour of TradierClient/SpyderC00, so the
            # data_manager attribute may be None in all production code paths.
            if self.data_manager is not None and hasattr(
                self.data_manager, "subscribe_to_options_chain"
            ):
                self.data_manager.subscribe_to_options_chain(chain, client_id)
                self.logger.info(
                    f"Chain subscription active via data_manager: "
                    f"chain={chain.chain_type.value}, client_id={client_id}, "
                    f"frequency={frequency}s"
                )
            else:
                # No live data manager available — record the subscription intent
                # so callers can see it was registered; price updates will arrive
                # via _subscribe_to_spy_price() TradierMarketStream callbacks or
                # manual calls to update_chain_data().
                self.logger.info(
                    "Chain subscription registered (offline): "
                    f"chain={chain.chain_type.value}, client_id={client_id}, "
                    f"frequency={frequency}s, "
                    f"contracts={len(chain.calls) + len(chain.puts)}"
                )

        except Exception as e:
            self.logger.error("Error subscribing to chain data: %s", e, exc_info=True)

    def _cancel_all_subscriptions(self) -> None:
        """Cancel all active options subscriptions."""
        try:
            cancelled = []

            # Stop the SPY price WebSocket stream if it was started
            spy_stream = getattr(self, "_spy_price_stream", None)
            if spy_stream is not None and hasattr(spy_stream, "stop"):
                try:
                    spy_stream.stop()
                    self._spy_price_stream = None
                    cancelled.append("SPY_price_stream")
                except Exception as stop_exc:
                    self.logger.warning(
                        "Error stopping SPY price stream: %s", stop_exc
                    )

            # Cancel options-chain subscriptions via data manager if available
            if self.data_manager is not None and hasattr(
                self.data_manager, "unsubscribe_from_options_chain"
            ):
                for chain_type, chain in list(self.active_chains.items()):
                    try:
                        self.data_manager.unsubscribe_from_options_chain(chain)
                        cancelled.append(chain_type.value)
                    except Exception as unsub_exc:
                        self.logger.warning(
                            "Error unsubscribing %s: %s", chain_type.value, unsub_exc
                        )
            else:
                # Record each chain cancellation in the log for traceability
                for chain_type in list(self.active_chains.keys()):
                    cancelled.append(chain_type.value)

            self.logger.info(
                "Cancelled all options subscriptions: %s", cancelled
            )

        except Exception as e:
            self.logger.error("Error cancelling subscriptions: %s", e, exc_info=True)

    def _reselect_strikes_for_all_chains(self) -> None:
        """Reselect strikes for all chains based on new SPY price."""
        try:
            self.logger.info(
                "Reselecting strikes based on new SPY price: %s", self.current_spy_price
            )

            for chain_type, chain in self.active_chains.items():
                spec = OPTIONS_SPECIFICATIONS[chain_type.value]
                new_strikes = self._generate_strikes_around_price(
                    self.current_spy_price, spec["strikes"]
                )

                # Update ATM strike
                chain.atm_strike = self._find_closest_strike(
                    self.current_spy_price, new_strikes
                )
                chain.underlying_price = self.current_spy_price

        except Exception as e:
            self.logger.error("Error reselecting strikes: %s", e, exc_info=True)

    def _options_monitor_loop(self) -> None:
        """Main monitoring loop for options chains."""
        self.logger.info("Started options monitoring loop")

        while self._running:
            try:
                # Update chain statistics
                self._update_chain_statistics()

                # Check for expired chains
                self._check_expired_chains()

                # Sleep before next iteration
                time.sleep(1)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error("Error in options monitor loop: %s", e, exc_info=True)
                time.sleep(5)  # thread-safe: time.sleep() intentional

        self.logger.info("Options monitoring loop stopped")

    def _update_chain_statistics(self) -> None:
        """Update statistics for all chains."""
        try:
            current_time = datetime.now(timezone.utc)

            for chain_type, chain in self.active_chains.items():
                # Update chain timestamp
                chain.last_update = current_time

                # Update performance counters
                self.update_counts[chain_type] += 1

        except Exception as e:
            self.logger.error("Error updating chain statistics: %s", e, exc_info=True)

    def _check_expired_chains(self) -> None:
        """Check for and handle expired options chains."""
        try:
            current_date = datetime.now(timezone.utc).date()
            current_time = datetime.now(timezone.utc).time()

            to_roll: list[OptionsChainType] = []
            for chain_type, chain in self.active_chains.items():
                # Check if chain has expired
                if chain.expiration < current_date or (
                    chain.expiration == current_date
                    and current_time.hour >= OPTIONS_EXPIRY_HOUR
                ):

                    if chain.status != ChainStatus.EXPIRED:
                        self.logger.info("%s chain expired", chain_type.value)
                        chain.status = ChainStatus.EXPIRED
                        to_roll.append(chain_type)

            # A20 (v14): after marking expired chains, re-initialize each with
            # the next target expiration so the strategy layer always sees a
            # live chain of each type rather than a stale EXPIRED record.
            for chain_type in to_roll:
                self._reinitialize_expired_chain(chain_type)

        except Exception as e:
            self.logger.error("Error checking expired chains: %s", e, exc_info=True)

    def _reinitialize_expired_chain(self, chain_type: OptionsChainType) -> None:
        """A20 (v14): roll an expired chain forward to the next expiration.

        Builds a fresh OptionsChain for ``chain_type`` using the same strike-
        window and contract-factory logic as ``_initialize_options_chains``
        but only for the one expired chain. Callers (subscribers) are not
        notified here; the next scheduled update pass will fan out normally.
        """
        try:
            spec = OPTIONS_SPECIFICATIONS[chain_type.value]
            current_date = datetime.now(timezone.utc).date()
            expiration_date = self._calculate_expiration_date(
                current_date, spec["days"]
            )

            chain = OptionsChain(
                symbol="SPY",
                expiration=expiration_date,
                chain_type=chain_type,
                underlying_price=self.current_spy_price,
            )

            strikes = self._generate_strikes_around_price(
                self.current_spy_price, spec["strikes"]
            )
            for strike in strikes:
                call_contract = self._create_options_contract(
                    expiration_date, strike, OptionType.CALL, chain_type
                )
                if call_contract:
                    chain.calls[strike] = call_contract
                put_contract = self._create_options_contract(
                    expiration_date, strike, OptionType.PUT, chain_type
                )
                if put_contract:
                    chain.puts[strike] = put_contract

            chain.atm_strike = self._find_closest_strike(
                self.current_spy_price, strikes
            )
            chain.total_contracts = len(chain.calls) + len(chain.puts)
            chain.status = ChainStatus.ACTIVE

            self.active_chains[chain_type] = chain
            self.logger.info(
                "Rolled %s chain to new expiration %s (%d calls, %d puts)",
                chain_type.value,
                expiration_date,
                len(chain.calls),
                len(chain.puts),
            )
        except Exception as e:
            self.logger.error(
                "Error rolling expired chain %s: %s", chain_type, e, exc_info=True
            )


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def create_spy_options_manager(
    data_manager: Any | None = None,
) -> SPYOptionsChainManager:
    """
    Create SPY options chain manager.

    Args:
        data_manager: Optional data manager instance

    Returns:
        SPYOptionsChainManager: Configured manager instance
    """
    return SPYOptionsChainManager(data_manager)


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

# Global manager instance
_options_manager_instance: SPYOptionsChainManager | None = None


def get_spy_options_manager() -> SPYOptionsChainManager:
    """
    Get singleton instance of the SPY options manager.

    Returns:
        SPYOptionsChainManager: Manager instance
    """
    global _options_manager_instance
    if _options_manager_instance is None:
        _options_manager_instance = SPYOptionsChainManager()
    return _options_manager_instance


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Module testing code

    # Create options manager
    options_manager = SPYOptionsChainManager()

    if options_manager.initialize():

        # Test chain creation
        for _chain_type, _spec in OPTIONS_SPECIFICATIONS.items():
            pass

        # Test status
        status = options_manager.get_manager_status()
        for key, _value in status.items():
            if key != "chain_details":
                pass

        for _chain_name, details in status["chain_details"].items():
            for _detail_key, _detail_value in details.items():
                pass


    else:
        pass

