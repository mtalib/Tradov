#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC03_OptionChain.py
Purpose: Options chain data management (Tradier API compatible)

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-22 Time: 14:40:00

BROKER NOTE:
    This module now uses Tradier API for option chain data.
    Greeks calculations use SpyderF06_GreeksCalculator.

    Current Architecture:
    - Tradier: GET /markets/options/chains endpoint for option chains
    - Massive: optional fallback market-data and historical-data path
    - Internal: Greeks calculations (SpyderF06_GreeksCalculator)

Module Description:
    Options chain data for the Spyder trading system. Fetches and maintains
    real-time option chains, calculates Greeks, tracks open interest and volume,
    and provides option selection utilities based on delta, gamma, and probability
    metrics. Data sourced from Tradier API (SpyderB40_TradierClient).
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import threading
import datetime
from typing import Any
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ib_async Contract removed — use Tradier API (SpyderB40_TradierClient.get_options_chain())
Contract = None  # type: ignore

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger  # noqa: E402
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler  # noqa: E402
from Spyder.SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar  # noqa: E402
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType  # noqa: E402

# B01_SpyderClient removed (legacy broker) — Tradier via SpyderB40_TradierClient
SpyderClient = None  # type: ignore

# B06_ContractBuilder removed (legacy broker)
ContractBuilder = None  # type: ignore
OptionRight = None  # type: ignore

try:
    from Spyder.SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
except ImportError:
    GreeksCalculator = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Update intervals
CHAIN_UPDATE_INTERVAL = 30  # seconds
GREEKS_UPDATE_INTERVAL = 10  # seconds
STALE_DATA_THRESHOLD = 300  # 5 minutes

# Option chain parameters
DEFAULT_STRIKE_COUNT = 40  # Number of strikes around ATM
DEFAULT_DAYS_TO_EXPIRY = [0, 1, 2, 3, 7, 14, 21, 30, 45, 60, 90, 120]  # Standard DTE
MIN_VOLUME_THRESHOLD = 10
MIN_OPEN_INTEREST_THRESHOLD = 50

# Greeks calculation parameters
RISK_FREE_RATE = 0.05  # Default risk-free rate
DIVIDEND_YIELD = 0.02  # SPY dividend yield

# Option selection criteria
MAX_BID_ASK_SPREAD_PCT = 0.1  # 10% max spread
MIN_DELTA_LIQUIDITY = 0.05  # Minimum delta for liquid options

# ==============================================================================
# ENUMS
# ==============================================================================

class OptionType(Enum):
    """Option types"""
    CALL = "C"
    PUT = "P"

class ChainStatus(Enum):
    """Option chain status"""
    LOADING = "loading"
    ACTIVE = "active"
    STALE = "stale"
    ERROR = "error"

class UpdateType(Enum):
    """Types of option chain updates"""
    FULL_REFRESH = "full_refresh"
    INCREMENTAL = "incremental"
    GREEKS_ONLY = "greeks_only"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class OptionContract:
    """Individual option contract data"""
    symbol: str
    expiry: datetime.date
    strike: float
    option_type: OptionType

    # Market data
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    volume: int = 0
    open_interest: int = 0

    # Greeks
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    rho: float | None = None
    implied_volatility: float | None = None

    # Derived metrics
    intrinsic_value: float | None = None
    time_value: float | None = None
    moneyness: float | None = None

    # Legacy fields (unused after broker migration)
    contract_id: int | None = None
    ib_contract: Any | None = None
    ticker_id: int | None = None
    last_update: datetime.datetime = field(default_factory=datetime.datetime.now)

    @property
    def mid_price(self) -> float | None:
        """Calculate mid price"""
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2.0
        return self.last

    @property
    def spread(self) -> float | None:
        """Calculate bid-ask spread"""
        if self.bid is not None and self.ask is not None:
            return self.ask - self.bid
        return None

    @property
    def spread_percent(self) -> float | None:
        """Calculate spread as percentage of mid price"""
        if self.spread is not None and self.mid_price is not None and self.mid_price > 0:
            return (self.spread / self.mid_price) * 100.0
        return None

    @property
    def days_to_expiry(self) -> int:
        """Calculate days to expiry"""
        today = datetime.date.today()
        return (self.expiry - today).days

    def is_otm(self, underlying_price: float) -> bool:
        """Check if option is out of the money"""
        if self.option_type == OptionType.CALL:
            return self.strike > underlying_price
        else:
            return self.strike < underlying_price

    def is_itm(self, underlying_price: float) -> bool:
        """Check if option is in the money"""
        return not self.is_otm(underlying_price)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            'symbol': self.symbol,
            'expiry': self.expiry,
            'strike': self.strike,
            'type': self.option_type.value,
            'bid': self.bid,
            'ask': self.ask,
            'last': self.last,
            'mid': self.mid_price,
            'volume': self.volume,
            'open_interest': self.open_interest,
            'delta': self.delta,
            'gamma': self.gamma,
            'theta': self.theta,
            'vega': self.vega,
            'rho': self.rho,
            'iv': self.implied_volatility,
            'intrinsic': self.intrinsic_value,
            'time_value': self.time_value,
            'moneyness': self.moneyness,
            'spread': self.spread,
            'spread_pct': self.spread_percent,
            'dte': self.days_to_expiry,
            'last_update': self.last_update
        }

@dataclass
class OptionChain:
    """Complete option chain for a single expiration"""
    symbol: str
    expiry: datetime.date
    underlying_price: float
    calls: dict[float, OptionContract] = field(default_factory=dict)
    puts: dict[float, OptionContract] = field(default_factory=dict)
    last_update: datetime.datetime = field(default_factory=datetime.datetime.now)
    status: ChainStatus = ChainStatus.LOADING

    @property
    def all_strikes(self) -> list[float]:
        """Get all available strikes sorted"""
        return sorted(set(list(self.calls.keys()) + list(self.puts.keys())))

    @property
    def atm_strike(self) -> float:
        """Get at-the-money strike"""
        strikes = self.all_strikes
        if not strikes:
            return self.underlying_price
        return min(strikes, key=lambda x: abs(x - self.underlying_price))

    @property
    def days_to_expiry(self) -> int:
        """Calculate days to expiry"""
        today = datetime.date.today()
        return (self.expiry - today).days

    def get_otm_options(self) -> tuple[list[OptionContract], list[OptionContract]]:
        """Get OTM calls and puts"""
        otm_calls = []
        otm_puts = []

        for strike, call in self.calls.items():
            if strike > self.underlying_price:
                otm_calls.append(call)

        for strike, put in self.puts.items():
            if strike < self.underlying_price:
                otm_puts.append(put)

        return otm_calls, otm_puts

    def get_liquid_options(self, min_volume: int = MIN_VOLUME_THRESHOLD,
                          min_oi: int = MIN_OPEN_INTEREST_THRESHOLD,
                          max_spread_pct: float = MAX_BID_ASK_SPREAD_PCT) -> list[OptionContract]:
        """Get liquid options based on volume, OI, and spread criteria"""
        liquid_options = []

        for option in list(self.calls.values()) + list(self.puts.values()):
            if (option.volume >= min_volume and
                option.open_interest >= min_oi and
                option.spread_percent is not None and
                option.spread_percent <= max_spread_pct):
                liquid_options.append(option)

        return liquid_options

    def calculate_put_call_ratio(self) -> float | None:
        """Calculate put/call volume ratio"""
        total_call_volume = sum(call.volume for call in self.calls.values())
        total_put_volume = sum(put.volume for put in self.puts.values())

        if total_call_volume > 0:
            return total_put_volume / total_call_volume
        return None

    def get_skew_data(self) -> dict[str, list[float]]:
        """Get volatility skew data"""
        strikes = []
        call_ivs = []
        put_ivs = []

        for strike in self.all_strikes:
            if strike in self.calls and self.calls[strike].implied_volatility is not None:
                strikes.append(strike)
                call_ivs.append(self.calls[strike].implied_volatility)

            if strike in self.puts and self.puts[strike].implied_volatility is not None:
                if strike not in strikes:
                    strikes.append(strike)
                put_ivs.append(self.puts[strike].implied_volatility)

        return {
            'strikes': strikes,
            'call_ivs': call_ivs,
            'put_ivs': put_ivs
        }

    def to_dataframe(self) -> pd.DataFrame:
        """Convert chain to DataFrame"""
        data = []

        # Add calls
        for strike, option in self.calls.items():
            data.append({**option.to_dict(), 'strike': strike})

        # Add puts
        for strike, option in self.puts.items():
            data.append({**option.to_dict(), 'strike': strike})

        if data:
            df = pd.DataFrame(data)
            df.sort_values(['type', 'strike'], inplace=True)
            return df

        return pd.DataFrame()

@dataclass
class OptionSelectionCriteria:
    """Criteria for option selection"""
    min_delta: float | None = None
    max_delta: float | None = None
    min_gamma: float | None = None
    min_theta: float | None = None
    min_vega: float | None = None
    min_volume: int | None = None
    min_open_interest: int | None = None
    max_spread_percent: float | None = None
    min_days_to_expiry: int | None = None
    max_days_to_expiry: int | None = None
    min_implied_volatility: float | None = None
    max_implied_volatility: float | None = None
    otm_only: bool = False
    itm_only: bool = False
    liquid_only: bool = True

# ==============================================================================
# MAIN CLASS
# ==============================================================================

class OptionChainManager:
    """
    Manages option chain data and analysis.

    Features:
    - Real-time option chain updates
    - Greeks calculation and monitoring
    - Option selection by various criteria
    - Volatility smile analysis
    - Put/call ratio tracking
    - Open interest analysis
    """

    def __init__(self, ib_client: SpyderClient, event_manager: EventManager):
        """
        Initialize option chain manager.

        Args:
            ib_client: Connected SpyderClient instance (legacy parameter name)
            event_manager: Event manager for publishing updates
        """
        self.ib_client = ib_client
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Data storage
        self.option_chains: dict[datetime.date, OptionChain] = {}
        self.active_subscriptions: dict[int, OptionContract] = {}  # ticker_id -> contract
        self.contract_builder = None  # ContractBuilder removed — legacy broker deprecated; use Tradier REST API  # noqa: E501
        if GreeksCalculator is None:
            raise ImportError(
                "GreeksCalculator unavailable — check SpyderF06_GreeksCalculator imports"
            )
        self.greeks_calculator = GreeksCalculator()
        self.trading_calendar = TradingCalendar()

        # Configuration
        self.symbol = "SPY"  # Primary symbol
        self.underlying_price = 0.0
        self.strike_range = DEFAULT_STRIKE_COUNT
        self.target_expirations = DEFAULT_DAYS_TO_EXPIRY

        # Threading
        self.running = False
        self.update_thread: threading.Thread | None = None
        self._data_lock = threading.RLock()

        # Tracking
        self.next_ticker_id = 5000
        self.request_timestamps: dict[int, datetime.datetime] = {}

        # Setup callbacks
        self._setup_callbacks()

        self.logger.debug("Option Chain Manager initialized")

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================

    def start(self) -> bool:
        """
        Start the option chain manager.

        Returns:
            True if started successfully
        """
        try:
            if self.running:
                self.logger.warning("Option Chain Manager already running")
                return True

            if not self.ib_client.is_connected():
                self.logger.error("Data client not connected")
                return False

            self.running = True

            # Start update thread
            self.update_thread = threading.Thread(
                target=self._update_loop,
                name="OptionChainUpdater",
                daemon=True
            )
            self.update_thread.start()

            # Initial load
            self._load_initial_chains()

            self.logger.info("Option Chain Manager started")
            return True

        except Exception as e:
            self.logger.error("Failed to start Option Chain Manager: %s", e, exc_info=True)
            return False

    def stop(self):
        """Stop the option chain manager"""
        try:
            self.running = False

            # Cancel all subscriptions
            self._cancel_all_subscriptions()

            # Stop update thread
            if self.update_thread and self.update_thread.is_alive():
                self.update_thread.join(timeout=5.0)

            self.logger.info("Option Chain Manager stopped")

        except Exception as e:
            self.logger.error("Error stopping Option Chain Manager: %s", e, exc_info=True)

    def load_chain(self, expiry: datetime.date) -> bool:
        """
        Load option chain for specific expiration.

        Args:
            expiry: Expiration date

        Returns:
            True if load initiated successfully
        """
        try:
            # Create chain entry
            with self._data_lock:
                if expiry not in self.option_chains:
                    self.option_chains[expiry] = OptionChain(
                        symbol=self.symbol,
                        expiry=expiry,
                        underlying_price=self.underlying_price,
                        status=ChainStatus.LOADING
                    )

            # Get option contracts from data provider
            self._request_option_contracts(expiry)

            self.logger.info("Loading option chain for %s", expiry)
            return True

        except Exception as e:
            self.logger.error("Error loading chain for %s: %s", expiry, e, exc_info=True)
            return False

    def get_chain(self, expiry: datetime.date) -> OptionChain | None:
        """Get option chain for expiration"""
        with self._data_lock:
            return self.option_chains.get(expiry)

    def get_all_chains(self) -> dict[datetime.date, OptionChain]:
        """Get all option chains"""
        with self._data_lock:
            return self.option_chains.copy()

    def get_expirations(self) -> list[datetime.date]:
        """Get loaded expiration dates"""
        with self._data_lock:
            return sorted(self.option_chains.keys())

    def get_expiry_dates(self) -> list[datetime.date]:
        """Backward-compatible alias for callers expecting get_expiry_dates()."""
        return self.get_expirations()

    def get_underlying_price(self) -> float:
        """Return current underlying price used by chain analytics."""
        return float(self.underlying_price or 0.0)

    def get_option_chain(self, expiry: datetime.date) -> pd.DataFrame:
        """Backward-compatible chain accessor returning a DataFrame.

        This normalizes legacy callers (e.g., N09) that expect a pandas table.
        """
        chain = self.get_chain(expiry)
        if chain is None:
            return pd.DataFrame()
        return chain.to_dataframe()

    def select_options(self, criteria: OptionSelectionCriteria) -> list[OptionContract]:
        """
        Select options based on criteria.

        Args:
            criteria: Selection criteria

        Returns:
            List of matching option contracts
        """
        matching_options = []

        with self._data_lock:
            for chain in self.option_chains.values():
                # Check expiry constraints
                if criteria.min_days_to_expiry is not None:
                    if chain.days_to_expiry < criteria.min_days_to_expiry:
                        continue

                if criteria.max_days_to_expiry is not None:
                    if chain.days_to_expiry > criteria.max_days_to_expiry:
                        continue

                # Check all options in chain
                all_options = list(chain.calls.values()) + list(chain.puts.values())

                for option in all_options:
                    if self._matches_criteria(option, criteria, chain.underlying_price):
                        matching_options.append(option)

        return matching_options

    def get_liquid_options(self, expiry: datetime.date | None = None) -> list[OptionContract]:
        """Get liquid options for expiry or all expirations"""
        liquid_options = []

        with self._data_lock:
            chains_to_check = [self.option_chains[expiry]] if expiry and expiry in self.option_chains else self.option_chains.values()  # noqa: E501

            for chain in chains_to_check:
                liquid_options.extend(chain.get_liquid_options())

        return liquid_options

    def calculate_portfolio_greeks(self, positions: dict[str, int]) -> dict[str, float]:
        """
        Calculate portfolio-level Greeks.

        Args:
            positions: Dict of option symbol -> quantity

        Returns:
            Portfolio Greeks dictionary
        """
        portfolio_greeks = {
            'delta': 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'rho': 0.0
        }

        with self._data_lock:
            for chain in self.option_chains.values():
                for option in list(chain.calls.values()) + list(chain.puts.values()):
                    option_key = f"{option.symbol}_{option.expiry}_{option.strike}_{option.option_type.value}"  # noqa: E501

                    if option_key in positions:
                        quantity = positions[option_key]

                        if option.delta is not None:
                            portfolio_greeks['delta'] += option.delta * quantity
                        if option.gamma is not None:
                            portfolio_greeks['gamma'] += option.gamma * quantity
                        if option.theta is not None:
                            portfolio_greeks['theta'] += option.theta * quantity
                        if option.vega is not None:
                            portfolio_greeks['vega'] += option.vega * quantity
                        if option.rho is not None:
                            portfolio_greeks['rho'] += option.rho * quantity

        return portfolio_greeks

    def export_chain_data(self, expiry: datetime.date) -> pd.DataFrame:
        """Export chain data to DataFrame"""
        chain = self.get_chain(expiry)
        if chain:
            return chain.to_dataframe()
        return pd.DataFrame()

    def get_skew_analysis(self, expiry: datetime.date) -> dict[str, Any] | None:
        """Get volatility skew analysis for expiration"""
        chain = self.get_chain(expiry)
        if not chain:
            return None

        skew_data = chain.get_skew_data()

        if not skew_data['strikes']:
            return None

        # Calculate skew metrics
        atm_strike = chain.atm_strike
        atm_idx = skew_data['strikes'].index(atm_strike) if atm_strike in skew_data['strikes'] else None  # noqa: E501

        analysis = {
            'expiry': expiry,
            'atm_strike': atm_strike,
            'strikes': skew_data['strikes'],
            'call_ivs': skew_data['call_ivs'],
            'put_ivs': skew_data['put_ivs'],
            'atm_iv': None,
            'skew_slope': None,
            'put_call_iv_spread': None
        }

        if atm_idx is not None and atm_idx < len(skew_data['call_ivs']):
            analysis['atm_iv'] = skew_data['call_ivs'][atm_idx]

        # Calculate average skew slope (simplified)
        if len(skew_data['call_ivs']) > 2:
            iv_changes = [skew_data['call_ivs'][i+1] - skew_data['call_ivs'][i]
                         for i in range(len(skew_data['call_ivs'])-1)]
            analysis['skew_slope'] = np.mean(iv_changes) if iv_changes else None

        return analysis

    # ==========================================================================
    # PRIVATE METHODS - CORE FUNCTIONALITY
    # ==========================================================================

    def _setup_callbacks(self):
        """Setup data provider callbacks"""
        self.ib_client.ib.tickPrice = self._on_tick_price
        self.ib_client.ib.tickSize = self._on_tick_size
        self.ib_client.ib.tickOptionComputation = self._on_tick_option_computation
        self.ib_client.ib.error = self._on_error

    def _load_initial_chains(self):
        """Load initial option chains"""
        try:
            # Get current SPY price first
            self._update_underlying_price()

            # Load chains for target expirations
            expiry_dates = self._get_target_expiry_dates()

            for expiry in expiry_dates:
                self.load_chain(expiry)
                time.sleep(0.1)  # thread-safe: time.sleep() intentional

        except Exception as e:
            self.logger.error("Error loading initial chains: %s", e, exc_info=True)

    def _get_target_expiry_dates(self) -> list[datetime.date]:
        """Get target expiration dates based on DTE preferences"""
        today = datetime.date.today()
        target_dates = []

        for dte in self.target_expirations:
            target_date = today + datetime.timedelta(days=dte)

            # Find next valid expiry (typically Friday)
            while target_date.weekday() != 4:  # Friday = 4
                target_date += datetime.timedelta(days=1)

            target_dates.append(target_date)

        return target_dates

    def _request_option_contracts(self, expiry: datetime.date):
        """Request option contracts for expiration"""
        try:
            # Create underlying contract
            self.contract_builder.build_stock(self.symbol)

            # Request security definition parameters
            # This is a simplified approach - in practice you'd use reqSecDefOptParams
            self._create_option_contracts_for_expiry(expiry)

        except Exception as e:
            self.logger.error("Error requesting contracts for %s: %s", expiry, e, exc_info=True)

    def _create_option_contracts_for_expiry(self, expiry: datetime.date):
        """Create option contracts around ATM for expiry"""
        try:
            expiry_str = expiry.strftime("%Y%m%d")
            atm_price = self.underlying_price or 500.0  # Default if no underlying price

            # Generate strikes around ATM
            strike_interval = 1.0 if atm_price < 100 else 5.0
            strikes = []

            for i in range(-self.strike_range // 2, self.strike_range // 2 + 1):
                strike = round((atm_price + (i * strike_interval)) / strike_interval) * strike_interval  # noqa: E501
                if strike > 0:
                    strikes.append(strike)

            with self._data_lock:
                chain = self.option_chains.get(expiry)
                if not chain:
                    return

                # Create call and put contracts
                for strike in strikes:
                    # Create call
                    call_contract = self.contract_builder.build_option(
                        symbol=self.symbol,
                        expiry=expiry_str,
                        strike=strike,
                        option_type=OptionRight.CALL
                    )

                    call_option = OptionContract(
                        symbol=self.symbol,
                        expiry=expiry,
                        strike=strike,
                        option_type=OptionType.CALL,
                        ib_contract=call_contract
                    )

                    chain.calls[strike] = call_option

                    # Create put
                    put_contract = self.contract_builder.build_option(
                        symbol=self.symbol,
                        expiry=expiry_str,
                        strike=strike,
                        option_type=OptionRight.PUT
                    )

                    put_option = OptionContract(
                        symbol=self.symbol,
                        expiry=expiry,
                        strike=strike,
                        option_type=OptionType.PUT,
                        ib_contract=put_contract
                    )

                    chain.puts[strike] = put_option

                # Start market data subscriptions
                self._subscribe_to_chain_data(chain)

        except Exception as e:
            self.logger.error("Error creating contracts for %s: %s", expiry, e, exc_info=True)

    def _subscribe_to_chain_data(self, chain: OptionChain):
        """Subscribe to market data for option chain"""
        try:
            all_options = list(chain.calls.values()) + list(chain.puts.values())

            for option in all_options:
                if option.ib_contract:
                    ticker_id = self._get_next_ticker_id()
                    option.ticker_id = ticker_id

                    # Store subscription
                    self.active_subscriptions[ticker_id] = option

                    # Request market data
                    self.ib_client.ib.reqMktData(
                        ticker_id,
                        option.ib_contract,
                        "100,101,104,105,106",  # Generic ticks for options
                        False,  # Not snapshot
                        False,  # Regular snapshot
                        []
                    )

                    time.sleep(0.01)  # thread-safe: time.sleep() intentional

            chain.status = ChainStatus.ACTIVE

        except Exception as e:
            self.logger.error("Error subscribing to chain data: %s", e, exc_info=True)
            chain.status = ChainStatus.ERROR

    def _update_underlying_price(self):
        """Update underlying asset price"""
        try:
            # This would typically request real-time data for SPY
            # For now, we'll use a placeholder
            self.underlying_price = 500.0  # Placeholder

        except Exception as e:
            self.logger.error("Error updating underlying price: %s", e, exc_info=True)

    def _matches_criteria(self, option: OptionContract, criteria: OptionSelectionCriteria, underlying_price: float) -> bool:  # noqa: E501
        """Check if option matches selection criteria"""
        # Delta constraints
        if criteria.min_delta is not None and (option.delta is None or option.delta < criteria.min_delta):  # noqa: E501
            return False
        if criteria.max_delta is not None and (option.delta is None or option.delta > criteria.max_delta):  # noqa: E501
            return False

        # Gamma constraints
        if criteria.min_gamma is not None and (option.gamma is None or option.gamma < criteria.min_gamma):  # noqa: E501
            return False

        # Theta constraints
        if criteria.min_theta is not None and (option.theta is None or option.theta < criteria.min_theta):  # noqa: E501
            return False

        # Vega constraints
        if criteria.min_vega is not None and (option.vega is None or option.vega < criteria.min_vega):  # noqa: E501
            return False

        # Volume constraints
        if criteria.min_volume is not None and option.volume < criteria.min_volume:
            return False

        # Open interest constraints
        if criteria.min_open_interest is not None and option.open_interest < criteria.min_open_interest:  # noqa: E501
            return False

        # Spread constraints
        if criteria.max_spread_percent is not None and option.spread_percent is not None:
            if option.spread_percent > criteria.max_spread_percent:
                return False

        # IV constraints
        if criteria.min_implied_volatility is not None and (option.implied_volatility is None or option.implied_volatility < criteria.min_implied_volatility):  # noqa: E501
            return False
        if criteria.max_implied_volatility is not None and (option.implied_volatility is None or option.implied_volatility > criteria.max_implied_volatility):  # noqa: E501
            return False

        # Moneyness constraints
        if criteria.otm_only and not option.is_otm(underlying_price):
            return False
        if criteria.itm_only and not option.is_itm(underlying_price):
            return False

        # Liquidity constraints
        if criteria.liquid_only:
            if (option.volume < MIN_VOLUME_THRESHOLD or
                option.open_interest < MIN_OPEN_INTEREST_THRESHOLD or
                (option.spread_percent is not None and option.spread_percent > MAX_BID_ASK_SPREAD_PCT)):  # noqa: E501
                return False

        return True

    # ==========================================================================
    # PRIVATE METHODS - CALLBACKS
    # ==========================================================================

    def _on_tick_price(self, ticker_id: int, tick_type: int, price: float, attrib):
        """Handle tick price updates"""
        if ticker_id not in self.active_subscriptions:
            return

        try:
            option = self.active_subscriptions[ticker_id]

            # Map tick types
            if tick_type == 1:  # Bid
                option.bid = price
            elif tick_type == 2:  # Ask
                option.ask = price
            elif tick_type == 4:  # Last
                option.last = price

            option.last_update = datetime.datetime.now(datetime.UTC)

        except Exception as e:
            self.logger.error("Error processing tick price for %s: %s", ticker_id, e, exc_info=True)

    def _on_tick_size(self, ticker_id: int, tick_type: int, size: int):
        """Handle tick size updates"""
        if ticker_id not in self.active_subscriptions:
            return

        try:
            option = self.active_subscriptions[ticker_id]

            # Map tick types
            if tick_type == 5:  # Last size = volume
                option.volume = size
            elif tick_type == 27 or tick_type == 28:  # Call option open interest
                option.open_interest = size

        except Exception as e:
            self.logger.error("Error processing tick size for %s: %s", ticker_id, e, exc_info=True)

    def _on_tick_option_computation(self, ticker_id: int, tick_type: int,
                                   impl_vol: float, delta: float, opt_price: float,
                                   pv_dividend: float, gamma: float, vega: float,
                                   theta: float, und_price: float):
        """Handle option Greeks updates"""
        if ticker_id not in self.active_subscriptions:
            return

        try:
            option = self.active_subscriptions[ticker_id]

            # Update Greeks
            if delta != -1.0:
                option.delta = delta
            if gamma != -1.0:
                option.gamma = gamma
            if theta != -1.0:
                option.theta = theta
            if vega != -1.0:
                option.vega = vega
            if impl_vol != -1.0:
                option.implied_volatility = impl_vol

            # Update intrinsic and time value
            if opt_price != -1.0 and und_price != -1.0:
                if option.option_type == OptionType.CALL:
                    option.intrinsic_value = max(0, und_price - option.strike)
                else:
                    option.intrinsic_value = max(0, option.strike - und_price)

                option.time_value = opt_price - option.intrinsic_value
                option.moneyness = und_price / option.strike

            option.last_update = datetime.datetime.now(datetime.UTC)

        except Exception as e:
            self.logger.error("Error processing option computation for %s: %s", ticker_id, e, exc_info=True)  # noqa: E501

    def _on_error(self, req_id: int, error_code: int, error_string: str, contract=None):
        """Handle data provider errors"""
        if req_id in self.active_subscriptions:
            option = self.active_subscriptions[req_id]
            self.logger.error("Option data error [%s %s %s]: %s - %s", option.symbol, option.strike, option.option_type.value, error_code, error_string)  # noqa: E501

    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================

    def _get_next_ticker_id(self) -> int:
        """Get next available ticker ID"""
        ticker_id = self.next_ticker_id
        self.next_ticker_id += 1
        return ticker_id

    def _cancel_all_subscriptions(self):
        """Cancel all active market data subscriptions"""
        for ticker_id in list(self.active_subscriptions.keys()):
            try:
                self.ib_client.ib.cancelMktData(ticker_id)
            except Exception as e:
                self.logger.warning("Error cancelling subscription %s: %s", ticker_id, e, exc_info=True)  # noqa: E501

        self.active_subscriptions.clear()

    def _update_loop(self):
        """Main update loop for chain management"""
        self.logger.info("Option chain update loop started")

        while self.running:
            try:
                # Update underlying price
                self._update_underlying_price()

                # Check for stale data
                self._check_stale_data()

                # Publish chain status
                self._publish_chain_status()

                # Sleep
                time.sleep(CHAIN_UPDATE_INTERVAL)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error("Update loop error: %s", e, exc_info=True)
                time.sleep(1.0)  # thread-safe: time.sleep() intentional

        self.logger.info("Option chain update loop stopped")

    def _check_stale_data(self):
        """Check for stale option data"""
        current_time = datetime.datetime.now(datetime.UTC)
        stale_threshold = datetime.timedelta(seconds=STALE_DATA_THRESHOLD)

        with self._data_lock:
            for chain in self.option_chains.values():
                if current_time - chain.last_update > stale_threshold:
                    if chain.status == ChainStatus.ACTIVE:
                        chain.status = ChainStatus.STALE
                        self.logger.warning("Chain %s marked as stale", chain.expiry)

    def _publish_chain_status(self):
        """Publish chain status event"""
        try:
            status_summary = {}

            with self._data_lock:
                for expiry, chain in self.option_chains.items():
                    status_summary[expiry.isoformat()] = {
                        'status': chain.status.value,
                        'calls_count': len(chain.calls),
                        'puts_count': len(chain.puts),
                        'last_update': chain.last_update.isoformat(),
                        'dte': chain.days_to_expiry
                    }

            event = Event(
                EventType.MARKET_DATA_OPTION_CHAIN,
                {
                    'symbol': self.symbol,
                    'underlying_price': self.underlying_price,
                    'chains': status_summary,
                    'timestamp': datetime.datetime.now(datetime.UTC).isoformat()
                }
            )

            self.event_manager.publish(event)

        except Exception as e:
            self.logger.error("Error publishing chain status: %s", e, exc_info=True)

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def create_spy_option_contract(expiry: str, strike: float, option_type: str):
    """Create SPY option contract descriptor.

    .. deprecated::
        Use SpyderB40_TradierClient for option chain data instead.
    """
    return {'symbol': 'SPY', 'expiry': expiry, 'strike': strike, 'type': option_type, 'exchange': 'SMART'}  # noqa: E501

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test option chain manager
    from SpyderA_Core.SpyderA05_EventManager import EventManager

    # Mock data client for testing
    class MockIBClient:
        def __init__(self):
            self.callbacks = defaultdict(list)

        def register_callback(self, event, callback):
            self.callbacks[event].append(callback)

        def reqMktData(self, ticker_id, contract, generic_ticks, snapshot, regulatory_snapshot, mkt_data_options):  # noqa: E501
            pass

        def is_connected(self):
            return True

    # Test manager
    event_manager = EventManager()
    mock_client = MockIBClient()

    manager = OptionChainManager(mock_client, event_manager)

    if manager.start():

        # Test loading a chain
        expiry = datetime.date.today() + datetime.timedelta(days=30)
        if manager.load_chain(expiry):
            pass

        # Test selection criteria
        criteria = OptionSelectionCriteria(
            min_delta=0.1,
            max_delta=0.9,
            min_volume=10,
            liquid_only=True
        )

        selected = manager.select_options(criteria)

        manager.stop()
    else:
        pass
