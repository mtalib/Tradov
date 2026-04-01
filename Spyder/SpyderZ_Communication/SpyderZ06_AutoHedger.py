#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderZ_Communication
Module: SpyderZ06_AutoHedger.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import threading
from datetime import date
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import multiprocessing as mp

warnings.filterwarnings('ignore')

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderZ07_MultiProcessManager import SpyderEngineProcess
from SpyderZ03_TradingCoordinator import EngineType, CommandType
from SpyderZ02_MessageProtocol import (
    ProtocolManager, SerializationFormat,
    OrderMessage, OptionOrderMessage
)
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Risk limits
MAX_PORTFOLIO_DELTA = 100.0      # Maximum absolute delta
MAX_PORTFOLIO_GAMMA = 50.0       # Maximum absolute gamma
MAX_PORTFOLIO_VEGA = 1000.0      # Maximum absolute vega
MAX_PORTFOLIO_THETA = -500.0     # Maximum negative theta (daily)

# Hedging thresholds
DELTA_HEDGE_THRESHOLD = 10.0     # Hedge when delta exceeds this
GAMMA_HEDGE_THRESHOLD = 5.0      # Hedge when gamma exceeds this
VEGA_HEDGE_THRESHOLD = 100.0     # Hedge when vega exceeds this

# Hedging parameters
MIN_HEDGE_INTERVAL = 60.0        # Minimum seconds between hedges
HEDGE_RATIO = 0.8                # Hedge 80% of exposure
GAMMA_SCALP_THRESHOLD = 2.0      # Gamma scalping threshold
DELTA_BAND_WIDTH = 5.0           # Delta neutral band

# Order parameters
DEFAULT_ORDER_SIZE = 100         # Default SPY shares for delta hedge
MAX_ORDER_SIZE = 1000            # Maximum order size
OPTION_LOT_SIZE = 10             # Option contracts per order

# Cost parameters
COMMISSION_PER_SHARE = 0.005     # $0.005 per share
COMMISSION_PER_OPTION = 0.65     # $0.65 per option contract
SLIPPAGE_BPS = 2                 # 2 basis points slippage

# Timing
GREEK_UPDATE_INTERVAL = 1.0      # Check Greeks every second
HEDGE_ANALYSIS_INTERVAL = 5.0    # Analyze hedge needs every 5 seconds
POSITION_SYNC_INTERVAL = 30.0    # Sync positions every 30 seconds

# ==============================================================================
# ENUMS
# ==============================================================================
class HedgeStrategy(Enum):
    """Available hedging strategies."""
    DELTA_NEUTRAL = "DELTA_NEUTRAL"
    GAMMA_NEUTRAL = "GAMMA_NEUTRAL"
    VEGA_NEUTRAL = "VEGA_NEUTRAL"
    DELTA_GAMMA_NEUTRAL = "DELTA_GAMMA_NEUTRAL"
    DYNAMIC_DELTA_BAND = "DYNAMIC_DELTA_BAND"
    GAMMA_SCALPING = "GAMMA_SCALPING"
    TAIL_RISK = "TAIL_RISK"

class HedgeInstrument(Enum):
    """Instruments available for hedging."""
    SPY_STOCK = "SPY_STOCK"
    SPY_OPTIONS = "SPY_OPTIONS"
    SPX_OPTIONS = "SPX_OPTIONS"
    ES_FUTURES = "ES_FUTURES"
    VIX_OPTIONS = "VIX_OPTIONS"
    COMBO = "COMBO"

class HedgeOrderType(Enum):
    """Types of hedge orders."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TRAILING_STOP = "TRAILING_STOP"

class HedgeStatus(Enum):
    """Hedge execution status."""
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class GreekExposure:
    """Current Greek exposure of portfolio."""
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    delta_dollars: float = 0.0
    gamma_dollars: float = 0.0
    theta_dollars: float = 0.0
    vega_dollars: float = 0.0
    last_update: float = 0.0

    def needs_hedge(self, strategy: HedgeStrategy) -> bool:
        """Check if hedging is needed based on strategy."""
        if strategy == HedgeStrategy.DELTA_NEUTRAL:
            return abs(self.delta) > DELTA_HEDGE_THRESHOLD
        elif strategy == HedgeStrategy.GAMMA_NEUTRAL:
            return abs(self.gamma) > GAMMA_HEDGE_THRESHOLD
        elif strategy == HedgeStrategy.VEGA_NEUTRAL:
            return abs(self.vega) > VEGA_HEDGE_THRESHOLD
        elif strategy == HedgeStrategy.DELTA_GAMMA_NEUTRAL:
            return (abs(self.delta) > DELTA_HEDGE_THRESHOLD or
                   abs(self.gamma) > GAMMA_HEDGE_THRESHOLD)
        elif strategy == HedgeStrategy.DYNAMIC_DELTA_BAND:
            return abs(self.delta) > DELTA_BAND_WIDTH
        elif strategy == HedgeStrategy.GAMMA_SCALPING:
            return abs(self.gamma) > GAMMA_SCALP_THRESHOLD
        return False

    def get_hedge_priority(self) -> str:
        """Determine which Greek needs hedging most urgently."""
        exposures = {
            'delta': abs(self.delta) / max(DELTA_HEDGE_THRESHOLD, 1),
            'gamma': abs(self.gamma) / max(GAMMA_HEDGE_THRESHOLD, 1),
            'vega': abs(self.vega) / max(VEGA_HEDGE_THRESHOLD, 1)
        }
        return max(exposures, key=exposures.get)

@dataclass
class HedgeOrder:
    """Hedge order details."""
    order_id: str
    hedge_type: HedgeStrategy
    instrument: HedgeInstrument
    symbol: str
    quantity: int
    side: str  # 'BUY' or 'SELL'
    order_type: HedgeOrderType
    price: float | None = None
    status: HedgeStatus = HedgeStatus.PENDING
    created_time: float = field(default_factory=time.time)
    executed_time: float | None = None
    fill_price: float | None = None
    target_greek: str | None = None
    hedge_ratio: float = 1.0

    def to_order_message(self) -> OrderMessage:
        """Convert to protocol order message."""
        return OrderMessage(
            order_id=self.order_id,
            symbol=self.symbol,
            quantity=self.quantity,
            side=self.side,
            order_type=self.order_type.value,
            price=self.price,
            time_in_force='DAY',
            status=self.status.value
        )

@dataclass
class HedgeAnalysis:
    """Analysis of hedging requirements."""
    current_exposure: GreekExposure
    target_exposure: GreekExposure
    hedge_needed: bool
    hedge_instruments: list[HedgeInstrument]
    proposed_orders: list[HedgeOrder]
    expected_cost: float
    risk_reduction: float
    confidence: float

@dataclass
class HedgePerformance:
    """Hedge performance tracking."""
    total_hedges: int = 0
    successful_hedges: int = 0
    failed_hedges: int = 0
    total_cost: float = 0.0
    total_slippage: float = 0.0
    avg_execution_time: float = 0.0
    delta_reduction: float = 0.0
    gamma_reduction: float = 0.0
    vega_reduction: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate hedge success rate."""
        if self.total_hedges > 0:
            return self.successful_hedges / self.total_hedges
        return 0.0

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class AutoHedger(SpyderEngineProcess):
    """
    Automated portfolio hedging engine.

    This engine monitors portfolio Greeks and automatically generates hedge
    orders to maintain risk within defined limits. It supports multiple
    hedging strategies and can use various instruments including stocks,
    options, and futures.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        current_exposure: Current Greek exposure
        active_hedges: Currently active hedge orders
        hedge_history: Historical hedge performance

    Example:
        >>> hedger = AutoHedger(engine_type, shutdown_event, shm_name)
        >>> hedger.run()
    """

    def __init__(self, engine_type: EngineType, shutdown_event: mp.Event,
                 shared_memory_name: str):
        """Initialize the auto hedger."""
        super().__init__(engine_type, shutdown_event, shared_memory_name)

        self.error_handler = SpyderErrorHandler()

        # Protocol manager
        self.protocol = ProtocolManager(SerializationFormat.MSGPACK)

        # Greek tracking
        self.current_exposure = GreekExposure()
        self.target_exposure = GreekExposure()  # Target Greeks (usually near zero)
        self.greek_history = deque(maxlen=1000)

        # Hedge management
        self.active_hedges: dict[str, HedgeOrder] = {}
        self.hedge_history: list[HedgeOrder] = []
        self.last_hedge_time: dict[str, float] = {}  # Per Greek type

        # Strategy configuration
        self.active_strategies: set[HedgeStrategy] = {
            HedgeStrategy.DELTA_NEUTRAL,
            HedgeStrategy.GAMMA_NEUTRAL
        }
        self.enabled_instruments: set[HedgeInstrument] = {
            HedgeInstrument.SPY_STOCK,
            HedgeInstrument.SPY_OPTIONS
        }

        # Performance tracking
        self.performance = HedgePerformance()

        # Market data
        self.spot_price = 0.0
        self.option_chains: dict[date, list[Any]] = {}

        # Risk limits
        self.risk_limits = {
            'max_delta': MAX_PORTFOLIO_DELTA,
            'max_gamma': MAX_PORTFOLIO_GAMMA,
            'max_vega': MAX_PORTFOLIO_VEGA,
            'max_theta': MAX_PORTFOLIO_THETA
        }

        # Hedge parameters
        self.hedge_params = {
            'hedge_ratio': HEDGE_RATIO,
            'min_interval': MIN_HEDGE_INTERVAL,
            'delta_threshold': DELTA_HEDGE_THRESHOLD,
            'gamma_threshold': GAMMA_HEDGE_THRESHOLD,
            'vega_threshold': VEGA_HEDGE_THRESHOLD,
            'delta_band': DELTA_BAND_WIDTH
        }

        # Threading
        self.hedge_thread = None
        self.monitor_thread = None

        # Timing
        self.last_greek_update = 0.0
        self.last_hedge_analysis = 0.0
        self.last_position_sync = 0.0

        self.logger.info(f"{self.__class__.__name__} initialized")

    # ==========================================================================
    # PUBLIC METHODS - PROCESS INTERFACE
    # ==========================================================================
    def setup(self) -> None:
        """Set up hedger resources."""
        super().setup()

        # Start hedge monitoring thread
        self.hedge_thread = threading.Thread(
            target=self._hedge_monitoring_loop,
            name="HedgeMonitorThread",
            daemon=True
        )
        self.hedge_thread.start()

        # Start order monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._order_monitoring_loop,
            name="OrderMonitorThread",
            daemon=True
        )
        self.monitor_thread.start()

        self.logger.info("Auto hedger setup complete")

    def process_work(self) -> None:
        """Process hedger work - handle commands and Greek updates."""
        # Check for commands from coordinator
        if self.dealer_socket.poll(0):
            try:
                message = self.dealer_socket.recv_json()
                self._handle_command(message)
            except Exception as e:
                self.logger.error(f"Command processing error: {e}")

        # Check for Greek updates
        self._check_greek_updates()

    def get_metrics(self) -> dict[str, Any]:
        """Get hedger-specific metrics."""
        base_metrics = super().get_metrics()

        base_metrics.update({
            'current_delta': self.current_exposure.delta,
            'current_gamma': self.current_exposure.gamma,
            'current_vega': self.current_exposure.vega,
            'active_hedges': len(self.active_hedges),
            'total_hedges': self.performance.total_hedges,
            'success_rate': self.performance.success_rate,
            'total_cost': self.performance.total_cost,
            'active_strategies': [s.value for s in self.active_strategies]
        })

        return base_metrics

    # ==========================================================================
    # PUBLIC METHODS - HEDGING
    # ==========================================================================
    def analyze_hedge_requirements(self) -> HedgeAnalysis:
        """
        Analyze current exposure and determine hedge requirements.

        Returns:
            HedgeAnalysis with proposed hedge orders
        """
        analysis = HedgeAnalysis(
            current_exposure=self.current_exposure,
            target_exposure=self.target_exposure,
            hedge_needed=False,
            hedge_instruments=[],
            proposed_orders=[],
            expected_cost=0.0,
            risk_reduction=0.0,
            confidence=0.0
        )

        # Check each active strategy
        for strategy in self.active_strategies:
            if self.current_exposure.needs_hedge(strategy):
                analysis.hedge_needed = True

                # Generate hedge orders based on strategy
                if strategy == HedgeStrategy.DELTA_NEUTRAL:
                    orders = self._generate_delta_hedge_orders()
                elif strategy == HedgeStrategy.GAMMA_NEUTRAL:
                    orders = self._generate_gamma_hedge_orders()
                elif strategy == HedgeStrategy.VEGA_NEUTRAL:
                    orders = self._generate_vega_hedge_orders()
                elif strategy == HedgeStrategy.DELTA_GAMMA_NEUTRAL:
                    orders = self._generate_delta_gamma_hedge_orders()
                elif strategy == HedgeStrategy.GAMMA_SCALPING:
                    orders = self._generate_gamma_scalp_orders()
                else:
                    orders = []

                analysis.proposed_orders.extend(orders)

        # Calculate expected cost and risk reduction
        if analysis.proposed_orders:
            analysis.expected_cost = self._calculate_hedge_cost(analysis.proposed_orders)
            analysis.risk_reduction = self._calculate_risk_reduction(analysis.proposed_orders)
            analysis.confidence = self._calculate_hedge_confidence(analysis.proposed_orders)

        return analysis

    def execute_hedge(self, hedge_order: HedgeOrder) -> bool:
        """
        Execute a hedge order.

        Args:
            hedge_order: Hedge order to execute

        Returns:
            bool: Success status
        """
        try:
            # Check if we can hedge (time restrictions)
            greek_type = hedge_order.target_greek or 'general'
            last_hedge = self.last_hedge_time.get(greek_type, 0)

            if time.time() - last_hedge < self.hedge_params['min_interval']:
                self.logger.warning(f"Hedge interval not met for {greek_type}")
                return False

            # Add to active hedges
            self.active_hedges[hedge_order.order_id] = hedge_order

            # Create order message
            if hedge_order.instrument == HedgeInstrument.SPY_STOCK:
                order_msg = hedge_order.to_order_message()
            else:
                # For options, create option order
                order_msg = self._create_option_order(hedge_order)

            # Send order via coordinator
            self._send_order(order_msg, hedge_order)

            # Update last hedge time
            self.last_hedge_time[greek_type] = time.time()

            # Update performance tracking
            self.performance.total_hedges += 1

            self.logger.info(f"Hedge order executed: {hedge_order.order_id}")
            return True

        except Exception as e:
            self.logger.error(f"Hedge execution error: {e}")
            hedge_order.status = HedgeStatus.FAILED
            self.performance.failed_hedges += 1
            return False

    # ==========================================================================
    # PRIVATE METHODS - HEDGE GENERATION
    # ==========================================================================
    def _generate_delta_hedge_orders(self) -> list[HedgeOrder]:
        """Generate orders to hedge delta exposure."""
        orders = []

        # Calculate hedge requirement
        delta_to_hedge = -self.current_exposure.delta * self.hedge_params['hedge_ratio']

        if abs(delta_to_hedge) < 1.0:
            return orders  # Too small to hedge

        # Use SPY stock for delta hedging
        if HedgeInstrument.SPY_STOCK in self.enabled_instruments:
            # Calculate shares needed
            shares = int(round(delta_to_hedge * 100))  # 100 delta per 100 shares

            # Limit order size
            shares = np.clip(shares, -MAX_ORDER_SIZE, MAX_ORDER_SIZE)

            if shares != 0:
                order = HedgeOrder(
                    order_id=f"HEDGE_DELTA_{int(time.time()*1000)}",
                    hedge_type=HedgeStrategy.DELTA_NEUTRAL,
                    instrument=HedgeInstrument.SPY_STOCK,
                    symbol="SPY",
                    quantity=abs(shares),
                    side="BUY" if shares > 0 else "SELL",
                    order_type=HedgeOrderType.MARKET,
                    target_greek='delta',
                    hedge_ratio=self.hedge_params['hedge_ratio']
                )
                orders.append(order)

        return orders

    def _generate_gamma_hedge_orders(self) -> list[HedgeOrder]:
        """Generate orders to hedge gamma exposure."""
        orders = []

        # Gamma hedging requires options
        if HedgeInstrument.SPY_OPTIONS not in self.enabled_instruments:
            return orders

        gamma_to_hedge = -self.current_exposure.gamma * self.hedge_params['hedge_ratio']

        if abs(gamma_to_hedge) < 0.5:
            return orders  # Too small

        # Find suitable option for gamma hedging
        option = self._find_gamma_hedge_option(gamma_to_hedge)

        if option:
            # Calculate contracts needed
            option_gamma = self._estimate_option_gamma(option)
            if option_gamma > 0:
                contracts = int(round(gamma_to_hedge / option_gamma))

                if contracts != 0:
                    order = HedgeOrder(
                        order_id=f"HEDGE_GAMMA_{int(time.time()*1000)}",
                        hedge_type=HedgeStrategy.GAMMA_NEUTRAL,
                        instrument=HedgeInstrument.SPY_OPTIONS,
                        symbol=option['symbol'],
                        quantity=abs(contracts),
                        side="BUY" if contracts > 0 else "SELL",
                        order_type=HedgeOrderType.LIMIT,
                        price=option['mid_price'],
                        target_greek='gamma',
                        hedge_ratio=self.hedge_params['hedge_ratio']
                    )
                    orders.append(order)

        return orders

    def _generate_vega_hedge_orders(self) -> list[HedgeOrder]:
        """Generate orders to hedge vega exposure."""
        orders = []

        # Vega hedging requires options
        if HedgeInstrument.SPY_OPTIONS not in self.enabled_instruments:
            return orders

        vega_to_hedge = -self.current_exposure.vega * self.hedge_params['hedge_ratio']

        if abs(vega_to_hedge) < 10:
            return orders  # Too small

        # Find suitable option for vega hedging (prefer longer-dated)
        option = self._find_vega_hedge_option(vega_to_hedge)

        if option:
            # Calculate contracts needed
            option_vega = self._estimate_option_vega(option)
            if option_vega > 0:
                contracts = int(round(vega_to_hedge / option_vega))

                if contracts != 0:
                    order = HedgeOrder(
                        order_id=f"HEDGE_VEGA_{int(time.time()*1000)}",
                        hedge_type=HedgeStrategy.VEGA_NEUTRAL,
                        instrument=HedgeInstrument.SPY_OPTIONS,
                        symbol=option['symbol'],
                        quantity=abs(contracts),
                        side="BUY" if contracts > 0 else "SELL",
                        order_type=HedgeOrderType.LIMIT,
                        price=option['mid_price'],
                        target_greek='vega',
                        hedge_ratio=self.hedge_params['hedge_ratio']
                    )
                    orders.append(order)

        return orders

    def _generate_delta_gamma_hedge_orders(self) -> list[HedgeOrder]:
        """Generate orders to hedge both delta and gamma."""
        orders = []

        # This requires solving a system of equations
        # We need two instruments to hedge two Greeks

        # First, try to find an option that helps with both
        combined_option = self._find_combined_hedge_option(
            self.current_exposure.delta,
            self.current_exposure.gamma
        )

        if combined_option:
            # Calculate position size
            option_delta = self._estimate_option_delta(combined_option)
            option_gamma = self._estimate_option_gamma(combined_option)

            # Solve for hedge quantities
            # This is simplified - in practice would use optimization
            if option_gamma != 0:
                # Hedge gamma first
                gamma_contracts = -self.current_exposure.gamma / option_gamma

                # Check resulting delta
                residual_delta = self.current_exposure.delta + gamma_contracts * option_delta

                # Add option order
                if abs(gamma_contracts) >= 1:
                    order = HedgeOrder(
                        order_id=f"HEDGE_COMBINED_{int(time.time()*1000)}",
                        hedge_type=HedgeStrategy.DELTA_GAMMA_NEUTRAL,
                        instrument=HedgeInstrument.SPY_OPTIONS,
                        symbol=combined_option['symbol'],
                        quantity=abs(int(gamma_contracts)),
                        side="BUY" if gamma_contracts > 0 else "SELL",
                        order_type=HedgeOrderType.LIMIT,
                        price=combined_option['mid_price'],
                        target_greek='gamma',
                        hedge_ratio=self.hedge_params['hedge_ratio']
                    )
                    orders.append(order)

                # Hedge residual delta with stock
                if abs(residual_delta) > DELTA_HEDGE_THRESHOLD:
                    delta_order = self._create_delta_hedge_order(-residual_delta)
                    if delta_order:
                        orders.append(delta_order)

        else:
            # Fall back to separate hedges
            orders.extend(self._generate_gamma_hedge_orders())
            orders.extend(self._generate_delta_hedge_orders())

        return orders

    def _generate_gamma_scalp_orders(self) -> list[HedgeOrder]:
        """Generate gamma scalping orders."""
        orders = []

        # Gamma scalping involves trading the underlying based on gamma
        if self.current_exposure.gamma > GAMMA_SCALP_THRESHOLD:
            # Calculate scalp size based on recent price movement
            price_move = self._calculate_recent_price_move()

            if abs(price_move) > 0.5:  # Significant move
                # Scalp in opposite direction
                scalp_delta = -self.current_exposure.gamma * price_move * 100

                shares = int(round(scalp_delta))
                shares = np.clip(shares, -MAX_ORDER_SIZE, MAX_ORDER_SIZE)

                if abs(shares) >= 100:  # Minimum scalp size
                    order = HedgeOrder(
                        order_id=f"SCALP_{int(time.time()*1000)}",
                        hedge_type=HedgeStrategy.GAMMA_SCALPING,
                        instrument=HedgeInstrument.SPY_STOCK,
                        symbol="SPY",
                        quantity=abs(shares),
                        side="BUY" if shares > 0 else "SELL",
                        order_type=HedgeOrderType.LIMIT,
                        price=self.spot_price + (0.02 if shares < 0 else -0.02),
                        target_greek='gamma_scalp'
                    )
                    orders.append(order)

        return orders

    # ==========================================================================
    # PRIVATE METHODS - OPTION SELECTION
    # ==========================================================================
    def _find_gamma_hedge_option(self, target_gamma: float) -> dict | None:
        """Find suitable option for gamma hedging."""
        best_option = None
        best_score = float('inf')

        # Look for ATM options with high gamma
        target_strike = round(self.spot_price)

        for expiry, chain in self.option_chains.items():
            days_to_expiry = (expiry - date.today()).days

            # Prefer 7-30 day options for gamma
            if 7 <= days_to_expiry <= 30:
                for option in chain:
                    if abs(option['strike'] - target_strike) <= 5:
                        # Estimate gamma
                        est_gamma = self._estimate_option_gamma(option)

                        # Score based on gamma efficiency
                        contracts_needed = abs(target_gamma / est_gamma)
                        cost = contracts_needed * option['mid_price'] * 100

                        score = cost / abs(target_gamma)  # Cost per unit of gamma

                        if score < best_score:
                            best_score = score
                            best_option = option

        return best_option

    def _find_vega_hedge_option(self, target_vega: float) -> dict | None:
        """Find suitable option for vega hedging."""
        best_option = None
        best_score = float('inf')

        # Look for ATM options with longer expiry
        target_strike = round(self.spot_price)

        for expiry, chain in self.option_chains.items():
            days_to_expiry = (expiry - date.today()).days

            # Prefer 30-90 day options for vega
            if 30 <= days_to_expiry <= 90:
                for option in chain:
                    if abs(option['strike'] - target_strike) <= 10:
                        # Estimate vega
                        est_vega = self._estimate_option_vega(option)

                        # Score based on vega efficiency
                        contracts_needed = abs(target_vega / est_vega)
                        cost = contracts_needed * option['mid_price'] * 100

                        score = cost / abs(target_vega)  # Cost per unit of vega

                        if score < best_score:
                            best_score = score
                            best_option = option

        return best_option

    def _find_combined_hedge_option(self, target_delta: float,
                                   target_gamma: float) -> dict | None:
        """Find option that helps hedge both delta and gamma."""
        best_option = None
        best_score = float('inf')

        for expiry, chain in self.option_chains.items():
            days_to_expiry = (expiry - date.today()).days

            if 7 <= days_to_expiry <= 30:
                for option in chain:
                    # Estimate Greeks
                    est_delta = self._estimate_option_delta(option)
                    est_gamma = self._estimate_option_gamma(option)

                    if est_gamma != 0:
                        # Calculate hedge effectiveness
                        gamma_hedge_ratio = -target_gamma / est_gamma
                        delta_contribution = gamma_hedge_ratio * est_delta
                        residual_delta = target_delta + delta_contribution

                        # Score based on residual risk and cost
                        cost = abs(gamma_hedge_ratio) * option['mid_price'] * 100
                        residual_risk = abs(residual_delta) + abs(target_gamma) * 0.1

                        score = cost + residual_risk * 10  # Weight residual risk

                        if score < best_score:
                            best_score = score
                            best_option = option

        return best_option

    def _create_delta_hedge_order(self, delta_to_hedge: float) -> HedgeOrder | None:
        """Create a delta hedge order."""
        shares = int(round(delta_to_hedge * 100))
        shares = np.clip(shares, -MAX_ORDER_SIZE, MAX_ORDER_SIZE)

        if abs(shares) < 100:
            return None  # Too small

        return HedgeOrder(
            order_id=f"HEDGE_DELTA_{int(time.time()*1000)}",
            hedge_type=HedgeStrategy.DELTA_NEUTRAL,
            instrument=HedgeInstrument.SPY_STOCK,
            symbol="SPY",
            quantity=abs(shares),
            side="BUY" if shares > 0 else "SELL",
            order_type=HedgeOrderType.MARKET,
            target_greek='delta',
            hedge_ratio=self.hedge_params['hedge_ratio']
        )

    # ==========================================================================
    # PRIVATE METHODS - GREEK ESTIMATION
    # ==========================================================================
    def _estimate_option_delta(self, option: dict) -> float:
        """Estimate option delta (simplified Black-Scholes)."""
        # This is simplified - in production would use proper model
        moneyness = self.spot_price / option['strike']
        option.get('days_to_expiry', 30)

        if option['type'] == 'CALL':
            if moneyness > 1.1:  # Deep ITM
                return 0.9
            elif moneyness < 0.9:  # Deep OTM
                return 0.1
            else:  # ATM
                return 0.5
        else:  # PUT
            if moneyness < 0.9:  # Deep ITM
                return -0.9
            elif moneyness > 1.1:  # Deep OTM
                return -0.1
            else:  # ATM
                return -0.5

    def _estimate_option_gamma(self, option: dict) -> float:
        """Estimate option gamma."""
        # Gamma is highest ATM and decreases as we move away
        moneyness = self.spot_price / option['strike']
        days_to_expiry = option.get('days_to_expiry', 30)

        # Simple approximation
        atm_distance = abs(moneyness - 1.0)
        time_factor = 1 / np.sqrt(days_to_expiry / 365)

        gamma = 0.04 * np.exp(-atm_distance * 10) * time_factor

        return gamma

    def _estimate_option_vega(self, option: dict) -> float:
        """Estimate option vega."""
        # Vega is highest ATM with more time
        moneyness = self.spot_price / option['strike']
        days_to_expiry = option.get('days_to_expiry', 30)

        # Simple approximation
        atm_distance = abs(moneyness - 1.0)
        time_factor = np.sqrt(days_to_expiry / 365)

        vega = 0.3 * np.exp(-atm_distance * 5) * time_factor

        return vega

    # ==========================================================================
    # PRIVATE METHODS - COST AND RISK CALCULATIONS
    # ==========================================================================
    def _calculate_hedge_cost(self, orders: list[HedgeOrder]) -> float:
        """Calculate expected cost of hedge orders."""
        total_cost = 0.0

        for order in orders:
            # Commission
            if order.instrument == HedgeInstrument.SPY_STOCK:
                commission = order.quantity * COMMISSION_PER_SHARE
            else:
                commission = order.quantity * COMMISSION_PER_OPTION

            # Spread cost (simplified)
            if order.order_type == HedgeOrderType.MARKET:
                spread_cost = order.quantity * self.spot_price * SLIPPAGE_BPS / 10000
            else:
                spread_cost = 0  # Assume limit orders fill at mid

            total_cost += commission + spread_cost

        return total_cost

    def _calculate_risk_reduction(self, orders: list[HedgeOrder]) -> float:
        """Calculate expected risk reduction from hedge orders."""
        # Estimate post-hedge Greeks
        post_delta = self.current_exposure.delta
        post_gamma = self.current_exposure.gamma
        post_vega = self.current_exposure.vega

        for order in orders:
            if order.instrument == HedgeInstrument.SPY_STOCK:
                # Stock only affects delta
                delta_change = order.quantity / 100 * (1 if order.side == "BUY" else -1)
                post_delta += delta_change

            elif order.instrument == HedgeInstrument.SPY_OPTIONS:
                # Estimate option Greeks (simplified)
                multiplier = 1 if order.side == "BUY" else -1

                if order.target_greek == 'gamma':
                    post_gamma += order.quantity * 0.03 * multiplier  # Rough estimate
                elif order.target_greek == 'vega':
                    post_vega += order.quantity * 0.25 * multiplier

        # Calculate risk reduction percentage
        current_risk = (abs(self.current_exposure.delta) +
                       abs(self.current_exposure.gamma) * 10 +
                       abs(self.current_exposure.vega) * 0.1)

        post_risk = abs(post_delta) + abs(post_gamma) * 10 + abs(post_vega) * 0.1

        if current_risk > 0:
            reduction = (current_risk - post_risk) / current_risk
            return max(0, min(1, reduction))  # Clamp to [0, 1]

        return 0.0

    def _calculate_hedge_confidence(self, orders: list[HedgeOrder]) -> float:
        """Calculate confidence in hedge effectiveness."""
        if not orders:
            return 0.0

        # Factors affecting confidence
        confidence = 1.0

        # Reduce confidence for large orders
        for order in orders:
            if order.quantity > MAX_ORDER_SIZE * 0.5:
                confidence *= 0.8

        # Reduce confidence for multiple instruments
        if len(set(o.instrument for o in orders)) > 1:
            confidence *= 0.9

        # Reduce confidence if market is volatile
        # (This would check actual volatility in production)

        return confidence

    def _calculate_recent_price_move(self) -> float:
        """Calculate recent price movement for gamma scalping."""
        # This would use actual tick data in production
        # For now, return a dummy value
        return 0.0

    # ==========================================================================
    # PRIVATE METHODS - ORDER MANAGEMENT
    # ==========================================================================
    def _create_option_order(self, hedge_order: HedgeOrder) -> OptionOrderMessage:
        """Create option order message."""
        # Parse option symbol to get parameters
        # Format: SPY230630C00450000

        # This is simplified - would parse actual symbol in production
        return OptionOrderMessage(
            order_id=hedge_order.order_id,
            symbol=hedge_order.symbol,
            underlying="SPY",
            strike=450.0,  # Would parse from symbol
            expiry="20230630",  # Would parse from symbol
            option_type="CALL",  # Would parse from symbol
            quantity=hedge_order.quantity,
            side=hedge_order.side,
            order_type=hedge_order.order_type.value,
            price=hedge_order.price
        )

    def _send_order(self, order_msg: Any, hedge_order: HedgeOrder) -> None:
        """Send order via coordinator."""
        try:
            # Create event
            event = {
                'type': 'EVENT',
                'event_type': 'HEDGE_ORDER',
                'data': {
                    'order': order_msg.__dict__ if hasattr(order_msg, '__dict__') else order_msg,
                    'hedge_type': hedge_order.hedge_type.value,
                    'target_greek': hedge_order.target_greek
                }
            }

            self.dealer_socket.send_json(event)

            self.logger.info(f"Hedge order sent: {hedge_order.order_id}")

        except Exception as e:
            self.logger.error(f"Failed to send order: {e}")
            raise

    # ==========================================================================
    # PRIVATE METHODS - MONITORING LOOPS
    # ==========================================================================
    def _hedge_monitoring_loop(self) -> None:
        """Monitor Greeks and generate hedges."""
        while not self.shutdown_event.is_set():
            try:
                now = time.time()

                # Periodic hedge analysis
                if now - self.last_hedge_analysis > HEDGE_ANALYSIS_INTERVAL:
                    analysis = self.analyze_hedge_requirements()

                    if analysis.hedge_needed and analysis.proposed_orders:
                        # Execute hedges
                        for order in analysis.proposed_orders:
                            self.execute_hedge(order)

                    self.last_hedge_analysis = now

                time.sleep(0.5)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error(f"Hedge monitoring error: {e}")
                self.error_handler.handle_error(e, {"context": "hedge_monitoring"})

    def _order_monitoring_loop(self) -> None:
        """Monitor status of active hedge orders."""
        while not self.shutdown_event.is_set():
            try:
                # Check active orders
                for order_id, hedge_order in list(self.active_hedges.items()):
                    if hedge_order.status in [HedgeStatus.FILLED, HedgeStatus.CANCELLED,
                                            HedgeStatus.FAILED]:
                        # Move to history
                        self.hedge_history.append(hedge_order)
                        del self.active_hedges[order_id]

                        # Update performance
                        if hedge_order.status == HedgeStatus.FILLED:
                            self.performance.successful_hedges += 1
                            hedge_order.executed_time = time.time()

                            # Calculate execution time
                            exec_time = hedge_order.executed_time - hedge_order.created_time
                            self.performance.avg_execution_time = (
                                (self.performance.avg_execution_time *
                                 (self.performance.successful_hedges - 1) + exec_time) /
                                self.performance.successful_hedges
                            )

                time.sleep(1.0)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error(f"Order monitoring error: {e}")

    def _check_greek_updates(self) -> None:
        """Check for Greek updates from volatility engine."""
        # In production, this would receive updates via ZeroMQ
        # For now, we'll simulate with dummy updates

        now = time.time()
        if now - self.last_greek_update > GREEK_UPDATE_INTERVAL:
            # Simulate Greek update
            # In reality, this would come from volatility engine
            pass

    # ==========================================================================
    # PRIVATE METHODS - COMMAND HANDLING
    # ==========================================================================
    def _handle_command(self, message: dict) -> None:
        """Handle command from coordinator."""
        command_type = message.get('command_type')
        command_id = message.get('command_id')

        try:
            result = None

            if command_type == CommandType.STATUS.value:
                # Return hedger status
                result = {
                    'current_exposure': {
                        'delta': self.current_exposure.delta,
                        'gamma': self.current_exposure.gamma,
                        'vega': self.current_exposure.vega,
                        'theta': self.current_exposure.theta
                    },
                    'active_hedges': len(self.active_hedges),
                    'performance': {
                        'total_hedges': self.performance.total_hedges,
                        'success_rate': self.performance.success_rate,
                        'total_cost': self.performance.total_cost
                    },
                    'active_strategies': [s.value for s in self.active_strategies]
                }

            elif command_type == CommandType.CONFIGURE.value:
                # Update configuration
                config = message.get('data', {})

                if 'strategies' in config:
                    self.active_strategies = set(
                        HedgeStrategy[s] for s in config['strategies']
                    )

                if 'risk_limits' in config:
                    self.risk_limits.update(config['risk_limits'])

                if 'hedge_params' in config:
                    self.hedge_params.update(config['hedge_params'])

                result = {'status': 'configured'}

            elif command_type == "GREEK_UPDATE":
                # Handle Greek update from volatility engine
                data = message.get('data', {})
                self._update_greek_exposure(data)
                result = {'status': 'updated'}

            else:
                result = {'error': f'Unknown command: {command_type}'}

            # Send response
            response = {
                'type': 'RESPONSE',
                'command_id': command_id,
                'result': result
            }
            self.dealer_socket.send_json(response)

        except Exception as e:
            self.logger.error(f"Command handling error: {e}")
            error_response = {
                'type': 'RESPONSE',
                'command_id': command_id,
                'result': {'error': str(e)}
            }
            self.dealer_socket.send_json(error_response)

    def _update_greek_exposure(self, greek_data: dict) -> None:
        """Update current Greek exposure."""
        self.current_exposure.delta = greek_data.get('delta', 0)
        self.current_exposure.gamma = greek_data.get('gamma', 0)
        self.current_exposure.theta = greek_data.get('theta', 0)
        self.current_exposure.vega = greek_data.get('vega', 0)
        self.current_exposure.delta_dollars = greek_data.get('delta_dollars', 0)
        self.current_exposure.last_update = time.time()

        # Add to history
        self.greek_history.append({
            'timestamp': self.current_exposure.last_update,
            'delta': self.current_exposure.delta,
            'gamma': self.current_exposure.gamma,
            'vega': self.current_exposure.vega
        })

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up hedger resources."""
        # Cancel any pending orders
        for order_id, hedge_order in self.active_hedges.items():
            if hedge_order.status == HedgeStatus.PENDING:
                self.logger.info(f"Cancelling pending hedge: {order_id}")
                # Would send cancel request in production

        # Wait for threads to finish
        if self.hedge_thread:
            self.hedge_thread.join(timeout=1.0)
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)

        super().cleanup()
        self.logger.info("Auto hedger cleanup completed")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def simulate_greek_exposure() -> GreekExposure:
    """Generate simulated Greek exposure for testing."""
    import random

    return GreekExposure(
        delta=random.uniform(-50, 50),
        gamma=random.uniform(-10, 10),
        theta=random.uniform(-200, -50),
        vega=random.uniform(-500, 500),
        delta_dollars=random.uniform(-5000, 5000),
        gamma_dollars=random.uniform(-1000, 1000),
        theta_dollars=random.uniform(-200, -50),
        vega_dollars=random.uniform(-500, 500),
        last_update=time.time()
    )

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code

    # Test Greek exposure
    exposure = simulate_greek_exposure()

    # Test hedge requirements
    for strategy in HedgeStrategy:
        needs_hedge = exposure.needs_hedge(strategy)

    # Test hedge order creation
    hedge_order = HedgeOrder(
        order_id="TEST_001",
        hedge_type=HedgeStrategy.DELTA_NEUTRAL,
        instrument=HedgeInstrument.SPY_STOCK,
        symbol="SPY",
        quantity=100,
        side="BUY",
        order_type=HedgeOrderType.MARKET,
        target_greek='delta'
    )


    # Test performance metrics
    perf = HedgePerformance(
        total_hedges=100,
        successful_hedges=95,
        failed_hedges=5,
        total_cost=1500.0,
        avg_execution_time=0.5
    )


