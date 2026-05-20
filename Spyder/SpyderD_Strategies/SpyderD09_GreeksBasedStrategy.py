#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD09_GreeksBasedStrategy.py
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
from typing import Any
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from enum import Enum, auto
from collections import defaultdict
import threading
import queue
import uuid
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (
    BaseStrategy, TradingSignal, SignalType, SignalStrength,
    StrategyPosition, EventManager, RiskProfile, Event, EventType
)
from Spyder.SpyderU_Utilities.SpyderU07_Constants import SPY_CONTRACT_MULTIPLIER
try:
    from Spyder.SpyderN_OptionsAnalytics.SpyderN07_OPRAGreeksHandler import OPRAGreeksHandler
    _D09_N07_AVAILABLE = True
except ImportError:
    OPRAGreeksHandler = None  # type: ignore[assignment,misc]
    _D09_N07_AVAILABLE = False

try:
    from Spyder.SpyderN_OptionsAnalytics.SpyderN11_OptionsGreeksFlow import GreeksFlowAnalyzer
    _D09_N11_AVAILABLE = True
except ImportError:
    GreeksFlowAnalyzer = None  # type: ignore[assignment,misc]
    _D09_N11_AVAILABLE = False

try:
    from Spyder.SpyderN_OptionsAnalytics.SpyderN04_OptionsGreeksCalculator import (
        get_n04_calculator as _d09_get_n04_calculator,
    )
    _D09_N04_AVAILABLE = True
except ImportError:
    _d09_get_n04_calculator = None  # type: ignore[assignment]
    _D09_N04_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy parameters
MAX_POSITION_DELTA = 1000      # Maximum portfolio delta
MAX_POSITION_GAMMA = 500       # Maximum portfolio gamma
MAX_POSITION_VEGA = 5000       # Maximum portfolio vega
TARGET_DELTA_NEUTRAL = 0       # Target for delta-neutral

# Gamma scalping parameters
GAMMA_SCALP_THRESHOLD = 50     # Minimum gamma to initiate scalp
DELTA_REBALANCE_THRESHOLD = 100 # Delta threshold for rebalancing
GAMMA_PROFIT_TARGET = 0.50     # Target profit per gamma scalp

# Greeks cache parameters
GREEKS_CACHE_SIZE = 10000      # Maximum cached Greeks entries
GREEKS_CACHE_TTL = 60          # Cache TTL in seconds
GREEKS_UPDATE_INTERVAL = 0.1   # Update interval in seconds

# Risk parameters
MAX_GREEK_EXPOSURE = 10000     # Maximum dollar exposure per Greek
STOP_LOSS_MULTIPLIER = 2.0     # Stop loss as multiple of expected profit
MAX_CONCURRENT_POSITIONS = 20   # Maximum positions

# Performance parameters
LATENCY_THRESHOLD_MS = 10      # Maximum acceptable latency
MIN_EDGE_THRESHOLD = 0.10      # Minimum edge to trade

# ==============================================================================
# ENUMS
# ==============================================================================
class GreeksStrategy(Enum):
    """Types of Greeks-based strategies"""
    DELTA_NEUTRAL = auto()
    GAMMA_SCALPING = auto()
    VEGA_TRADING = auto()
    THETA_HARVESTING = auto()
    VOLATILITY_ARBITRAGE = auto()
    PIN_RISK_MANAGEMENT = auto()

class GreeksSignalType(Enum):
    """Greeks-based signal types"""
    DELTA_HEDGE = auto()
    GAMMA_SCALP = auto()
    VEGA_TRADE = auto()
    THETA_COLLECT = auto()
    VOL_ARB = auto()
    GREEK_IMBALANCE = auto()

class GreeksCacheStatus(Enum):
    """Cache status for Greeks data"""
    FRESH = auto()
    STALE = auto()
    MISSING = auto()
    ERROR = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class GreeksSnapshot:
    """Point-in-time Greeks data"""
    timestamp: datetime
    symbol: str
    strike: float
    expiry: datetime
    option_type: str  # 'call' or 'put'

    # Greeks
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float

    # Pricing
    bid: float
    ask: float
    mid: float
    iv: float
    underlying_price: float

    # Market data
    volume: int
    open_interest: int
    bid_size: int
    ask_size: int

    # Cache metadata
    cache_status: GreeksCacheStatus
    latency_ms: float

@dataclass
class GreeksPosition:
    """Greeks-focused position tracking"""
    position_id: str
    strategy_type: GreeksStrategy
    entry_time: datetime
    contracts: dict[str, int]  # symbol -> quantity

    # Portfolio Greeks
    net_delta: float = 0.0
    net_gamma: float = 0.0
    net_theta: float = 0.0
    net_vega: float = 0.0

    # P&L tracking
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    gamma_pnl: float = 0.0
    theta_pnl: float = 0.0
    vega_pnl: float = 0.0

    # Risk metrics
    max_delta_exposure: float = 0.0
    max_gamma_exposure: float = 0.0
    hedge_effectiveness: float = 0.0

    # Performance
    trade_count: int = 0
    rebalance_count: int = 0
    avg_latency_ms: float = 0.0

@dataclass
class GreeksArbitrage:
    """Greeks arbitrage opportunity"""
    arb_id: str
    arb_type: str  # 'put_call_parity', 'calendar', 'butterfly'
    contracts: list[str]
    theoretical_value: float
    market_value: float
    edge: float
    edge_percent: float
    confidence: float
    expiry_time: datetime
    greeks_impact: dict[str, float]

# ==============================================================================
# GREEKS CACHE MANAGER
# ==============================================================================
class GreeksCacheManager:
    """Thread-safe Greeks cache with TTL"""

    def __init__(self, max_size: int = GREEKS_CACHE_SIZE, ttl: int = GREEKS_CACHE_TTL):
        self.max_size = max_size
        self.ttl = ttl
        self.cache: dict[str, GreeksSnapshot] = {}
        self.access_times: dict[str, datetime] = {}
        self.lock = threading.RLock()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'updates': 0,
            'evictions': 0
        }

    def get(self, symbol: str) -> GreeksSnapshot | None:
        """Get Greeks from cache"""
        with self.lock:
            if symbol in self.cache:
                # Check TTL
                if (datetime.now(UTC) - self.access_times[symbol]).seconds <= self.ttl:
                    self.stats['hits'] += 1
                    self.access_times[symbol] = datetime.now(UTC)
                    return self.cache[symbol]
                else:
                    # Stale data
                    self.cache[symbol].cache_status = GreeksCacheStatus.STALE

            self.stats['misses'] += 1
            return None

    def put(self, symbol: str, greeks: GreeksSnapshot) -> None:
        """Put Greeks in cache"""
        with self.lock:
            # Evict if at capacity
            if len(self.cache) >= self.max_size and symbol not in self.cache:
                self._evict_oldest()

            self.cache[symbol] = greeks
            self.access_times[symbol] = datetime.now(UTC)
            self.stats['updates'] += 1

    def _evict_oldest(self) -> None:
        """Evict oldest entry"""
        if not self.access_times:
            return

        oldest = min(self.access_times.items(), key=lambda x: x[1])
        del self.cache[oldest[0]]
        del self.access_times[oldest[0]]
        self.stats['evictions'] += 1

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            total_requests = self.stats['hits'] + self.stats['misses']
            hit_rate = self.stats['hits'] / total_requests if total_requests > 0 else 0

            return {
                'size': len(self.cache),
                'hit_rate': hit_rate,
                **self.stats
            }

# ==============================================================================
# GREEKS BASED STRATEGY CLASS
# ==============================================================================
class GreeksBasedStrategy(BaseStrategy):
    """
    High-speed Greeks-based trading strategy.

    Leverages pre-calculated Greeks from OPRA feeds for ultra-low latency
    trading decisions including delta-neutral strategies and gamma scalping.
    """

    def __init__(self, event_manager: EventManager, risk_profile: RiskProfile,
                 config: dict[str, Any]):
        """Initialize Greeks-based strategy"""
        super().__init__("GreeksBasedStrategy", event_manager, risk_profile, config)

        # Components — soft-initialized; N04 is the preferred source of truth for Greeks
        self.opra_handler = OPRAGreeksHandler() if _D09_N07_AVAILABLE else None
        self.greeks_flow = GreeksFlowAnalyzer() if _D09_N11_AVAILABLE else None

        # N04 singleton — authoritative BSM Greeks + portfolio-level aggregation
        self._n04_calculator: Any | None = None
        if _D09_N04_AVAILABLE:
            try:
                self._n04_calculator = _d09_get_n04_calculator()
            except Exception as _exc:
                self.logger.debug("N04 not yet available at D09 init: %s", _exc)

        # Configuration
        self.enable_delta_neutral = config.get('enable_delta_neutral', True)
        self.enable_gamma_scalping = config.get('enable_gamma_scalping', True)
        self.enable_vega_trading = config.get('enable_vega_trading', False)
        self.max_latency_ms = config.get('max_latency_ms', LATENCY_THRESHOLD_MS)

        # Greeks cache
        self.greeks_cache = GreeksCacheManager()

        # Position tracking
        self.greeks_positions: dict[str, GreeksPosition] = {}
        self.portfolio_greeks = {
            'delta': 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0
        }

        # Threading for high-speed updates
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.greeks_queue = queue.Queue(maxsize=1000)
        self.update_thread = None
        self.stop_event = threading.Event()

        # Performance tracking
        self.latency_buffer = []
        self.arbitrage_opportunities: dict[str, GreeksArbitrage] = {}

        # Strategy metrics
        self.greeks_metrics = {
            'delta_hedges': 0,
            'gamma_scalps': 0,
            'vega_trades': 0,
            'arbitrage_captured': 0,
            'avg_latency_ms': 0.0,
            'total_greek_pnl': 0.0
        }

        # Start background threads
        self._start_background_tasks()

        self.logger.info("GreeksBasedStrategy initialized with OPRA integration")

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================

    def _get_n04(self) -> Any | None:
        """Lazy-resolve the N04 OptionsGreeksCalculator singleton."""
        if not _D09_N04_AVAILABLE:
            return None
        if self._n04_calculator is None:
            try:
                self._n04_calculator = _d09_get_n04_calculator()
            except Exception as exc:
                self.logger.debug("N04 calculator unavailable: %s", exc)
        return self._n04_calculator

    def _start_background_tasks(self) -> None:
        """Start background processing threads"""
        # Greeks update thread
        self.update_thread = threading.Thread(
            target=self._greeks_update_loop,
            daemon=True
        )
        self.update_thread.start()

        # Arbitrage detection thread
        self.executor.submit(self._arbitrage_detection_loop)

    def _greeks_update_loop(self) -> None:
        """Background thread for processing Greeks updates"""
        while not self.stop_event.is_set():
            try:
                # Get Greeks update from queue
                update = self.greeks_queue.get(timeout=1)
                if update:
                    self._process_greeks_update(update)
            except queue.Empty:
                continue
            except Exception as e:
                self.error_handler.handle_error(e, {'method': '_greeks_update_loop'})

    # ==========================================================================
    # REQUIRED ABSTRACT METHOD IMPLEMENTATIONS
    # ==========================================================================

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Generate Greeks-based trading signals"""
        signals = []

        try:
            # Update portfolio Greeks from OPRA
            self._update_portfolio_greeks()

            # Check for delta-neutral opportunities
            if self.enable_delta_neutral:
                delta_signals = self._generate_delta_neutral_signals()
                signals.extend(delta_signals)

            # Check for gamma scalping opportunities
            if self.enable_gamma_scalping:
                gamma_signals = self._generate_gamma_scalping_signals(market_data)
                signals.extend(gamma_signals)

            # Check for vega trading opportunities
            if self.enable_vega_trading:
                vega_signals = self._generate_vega_trading_signals()
                signals.extend(vega_signals)

            # Check arbitrage opportunities
            arb_signals = self._check_arbitrage_opportunities()
            signals.extend(arb_signals)

            # Filter by latency requirements
            signals = self._filter_by_latency(signals)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'generate_signals',
                'market_data_shape': market_data.shape
            })

        return signals

    def validate_signal(self, signal: TradingSignal) -> bool:
        """Validate Greeks-based signal"""
        try:
            # Check signal validity
            if not signal.is_valid():
                return False

            # Check Greeks data freshness
            greeks_data = signal.metadata.get('greeks_data', {})
            if greeks_data.get('cache_status') == GreeksCacheStatus.STALE.name:
                return False

            # Check latency
            if greeks_data.get('latency_ms', float('inf')) > self.max_latency_ms:
                return False

            # Check edge threshold
            if greeks_data.get('edge', 0) < MIN_EDGE_THRESHOLD:
                return False

            # Validate Greeks limits
            portfolio_impact = greeks_data.get('portfolio_impact', {})

            if abs(portfolio_impact.get('delta', 0)) > MAX_POSITION_DELTA:
                return False

            if abs(portfolio_impact.get('gamma', 0)) > MAX_POSITION_GAMMA:
                return False

            return not abs(portfolio_impact.get('vega', 0)) > MAX_POSITION_VEGA

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'validate_signal',
                'signal_id': signal.signal_id
            })
            return False

    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Calculate position size based on Greeks exposure"""
        try:
            greeks_data = signal.metadata.get('greeks_data', {})
            signal_type = greeks_data.get('signal_type')

            # Base size on Greek exposure limits
            if signal_type == GreeksSignalType.DELTA_HEDGE.name:
                # Size to neutralize delta
                target_delta = -self.portfolio_greeks['delta']
                contract_delta = greeks_data.get('contract_delta', 50)
                contracts = int(target_delta / contract_delta)

            elif signal_type == GreeksSignalType.GAMMA_SCALP.name:
                # Size based on gamma exposure
                max_gamma_value = MAX_GREEK_EXPOSURE / 100  # $100 per 1% move
                contract_gamma = greeks_data.get('contract_gamma', 1)
                contracts = int(max_gamma_value / (contract_gamma * SPY_CONTRACT_MULTIPLIER))

            elif signal_type == GreeksSignalType.VEGA_TRADE.name:
                # Size based on vega exposure
                max_vega_value = MAX_GREEK_EXPOSURE / 100  # $100 per 1% vol move
                contract_vega = greeks_data.get('contract_vega', 0.5)
                contracts = int(max_vega_value / (contract_vega * SPY_CONTRACT_MULTIPLIER))

            else:
                # Default sizing
                contracts = 1

            # Apply limits
            contracts = max(1, min(abs(contracts), 50))

            # Adjust for signal strength
            if signal.strength == SignalStrength.WEAK:
                contracts = max(1, contracts // 2)
            elif signal.strength == SignalStrength.VERY_STRONG:
                contracts = min(50, int(contracts * 1.5))

            return contracts

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'calculate_position_size',
                'signal_id': signal.signal_id
            })
            return 1

    def should_exit_position(self, position: StrategyPosition,
                           market_data: pd.DataFrame) -> tuple[bool, str]:
        """Determine if Greeks position should be exited"""
        try:
            # Get Greeks position
            greeks_pos = self.greeks_positions.get(position.position_id)
            if not greeks_pos:
                return False, ""

            # Update position Greeks
            self._update_position_greeks(greeks_pos)

            # Check strategy-specific exit conditions
            if greeks_pos.strategy_type == GreeksStrategy.DELTA_NEUTRAL:
                # Exit if delta drifts too far
                if abs(greeks_pos.net_delta) > DELTA_REBALANCE_THRESHOLD * 2:
                    return True, "Delta drift exceeded limits"

            elif greeks_pos.strategy_type == GreeksStrategy.GAMMA_SCALPING:
                # Exit if gamma drops too low
                if abs(greeks_pos.net_gamma) < GAMMA_SCALP_THRESHOLD * 0.5:
                    return True, "Gamma too low for scalping"

                # Exit if profit target reached
                if greeks_pos.gamma_pnl >= GAMMA_PROFIT_TARGET * greeks_pos.net_gamma * SPY_CONTRACT_MULTIPLIER:  # noqa: E501
                    return True, "Gamma scalp profit target reached"

            elif greeks_pos.strategy_type == GreeksStrategy.VEGA_TRADING:
                # Exit if vega exposure flips
                if greeks_pos.net_vega * greeks_pos.vega_pnl < 0:
                    return True, "Vega exposure unfavorable"

            # General exit conditions

            # Stop loss
            if greeks_pos.unrealized_pnl < -MAX_GREEK_EXPOSURE:
                return True, "Stop loss triggered"

            # Time decay for short premium
            if greeks_pos.net_theta < 0 and greeks_pos.theta_pnl < -MAX_GREEK_EXPOSURE * 0.5:
                return True, "Excessive theta decay"

            # Pin risk near expiry
            if self._check_pin_risk(greeks_pos):
                return True, "Pin risk detected"

            return False, ""

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'should_exit_position',
                'position_id': position.position_id
            })
            return False, ""

    # ==========================================================================
    # GREEKS UPDATE METHODS
    # ==========================================================================

    def _update_portfolio_greeks(self) -> None:
        """Update portfolio-level Greeks from N04 (preferred) or OPRA feed (fallback)."""
        try:
            # Fast path: use N04 authoritative portfolio Greeks when available
            n04 = self._get_n04()
            if n04 is not None:
                try:
                    pg = n04.portfolio_greeks
                    self.portfolio_greeks = {
                        'delta': pg.total_delta,
                        'gamma': pg.total_gamma,
                        'theta': pg.total_theta,
                        'vega':  pg.total_vega,
                    }
                    self.logger.debug(
                        "Portfolio Greeks (N04): delta=%.2f gamma=%.4f theta=%.2f vega=%.2f",
                        pg.total_delta, pg.total_gamma, pg.total_theta, pg.total_vega,
                    )
                    return
                except Exception as exc:
                    self.logger.debug("N04 portfolio_greeks unavailable, using OPRA fallback: %s", exc)  # noqa: E501

            # Fallback: reset and sum Greeks across all tracked positions
            self.portfolio_greeks = {
                'delta': 0.0,
                'gamma': 0.0,
                'theta': 0.0,
                'vega': 0.0
            }

            # Sum Greeks across all positions
            for position in self.greeks_positions.values():
                self._update_position_greeks(position)

                self.portfolio_greeks['delta'] += position.net_delta
                self.portfolio_greeks['gamma'] += position.net_gamma
                self.portfolio_greeks['theta'] += position.net_theta
                self.portfolio_greeks['vega'] += position.net_vega

            # Log portfolio Greeks
            self.logger.debug(f"Portfolio Greeks: Delta={self.portfolio_greeks['delta']:.0f}, "
                            f"Gamma={self.portfolio_greeks['gamma']:.0f}, "
                            f"Theta={self.portfolio_greeks['theta']:.0f}, "
                            f"Vega={self.portfolio_greeks['vega']:.0f}")

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_update_portfolio_greeks'})

    def _update_position_greeks(self, position: GreeksPosition) -> None:
        """Update Greeks for a specific position"""
        try:
            # Reset position Greeks
            position.net_delta = 0.0
            position.net_gamma = 0.0
            position.net_theta = 0.0
            position.net_vega = 0.0

            latencies = []

            # Get Greeks for each contract
            for symbol, quantity in position.contracts.items():
                # Try cache first
                greeks = self.greeks_cache.get(symbol)

                if not greeks or greeks.cache_status == GreeksCacheStatus.STALE:
                    # Fetch from OPRA
                    start_time = datetime.now(UTC)
                    greeks = self._fetch_greeks_from_opra(symbol)
                    latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

                    if greeks:
                        greeks.latency_ms = latency_ms
                        self.greeks_cache.put(symbol, greeks)
                        latencies.append(latency_ms)

                if greeks:
                    # Sum position Greeks
                    position.net_delta += greeks.delta * quantity * SPY_CONTRACT_MULTIPLIER
                    position.net_gamma += greeks.gamma * quantity * SPY_CONTRACT_MULTIPLIER
                    position.net_theta += greeks.theta * quantity * SPY_CONTRACT_MULTIPLIER
                    position.net_vega += greeks.vega * quantity * SPY_CONTRACT_MULTIPLIER

            # Update average latency
            if latencies:
                position.avg_latency_ms = sum(latencies) / len(latencies)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_position_greeks',
                'position_id': position.position_id
            })

    def _fetch_greeks_from_opra(self, symbol: str) -> GreeksSnapshot | None:
        """Fetch Greeks from OPRA feed"""
        try:
            # In production, this would connect to actual OPRA feed
            # For now, return simulated data

            # Parse symbol (e.g., "SPY_450C_20250117")
            parts = symbol.split('_')
            if len(parts) != 3:
                return None

            parts[0]
            strike_type = parts[1]
            strike = float(strike_type[:-1])
            option_type = 'call' if strike_type[-1] == 'C' else 'put'
            expiry_str = parts[2]
            expiry = datetime.strptime(expiry_str, '%Y%m%d')

            # Derive BSM Greeks via N04 for accuracy; fall back to hardcoded defaults
            _sim_spot = 450.0
            _tte = max((expiry - datetime.now(UTC)).total_seconds() / (365 * 24 * 3600), 1e-6)
            _sim_iv = 0.20
            _sim_rf = 0.05
            _opt_type_str = 'CALL' if option_type == 'call' else 'PUT'

            n04 = self._get_n04()
            if n04 is not None:
                try:
                    _bsm = n04.calculate_greeks(
                        spot=_sim_spot,
                        strike=strike,
                        time_to_expiry=_tte,
                        volatility=_sim_iv,
                        risk_free_rate=_sim_rf,
                        option_type=_opt_type_str,
                    )
                    _delta = _bsm.get('delta', 0.5 if option_type == 'call' else -0.5)
                    _gamma = _bsm.get('gamma', 0.02)
                    _theta = _bsm.get('theta', -0.05)
                    _vega  = _bsm.get('vega',  0.15)
                    _rho   = _bsm.get('rho',   0.01)
                except Exception as exc:
                    self.logger.debug("N04 calculate_greeks failed for %s: %s", symbol, exc)
                    _delta = 0.5 if option_type == 'call' else -0.5
                    _gamma, _theta, _vega, _rho = 0.02, -0.05, 0.15, 0.01
            else:
                _delta = 0.5 if option_type == 'call' else -0.5
                _gamma, _theta, _vega, _rho = 0.02, -0.05, 0.15, 0.01

            # Build snapshot (in production this would come from OPRA)
            return GreeksSnapshot(
                timestamp=datetime.now(UTC),
                symbol=symbol,
                strike=strike,
                expiry=expiry,
                option_type=option_type,
                delta=_delta,
                gamma=_gamma,
                theta=_theta,
                vega=_vega,
                rho=_rho,
                bid=2.50,
                ask=2.55,
                mid=2.525,
                iv=_sim_iv,
                underlying_price=_sim_spot,
                volume=1000,
                open_interest=5000,
                bid_size=100,
                ask_size=150,
                cache_status=GreeksCacheStatus.FRESH,
                latency_ms=0
            )

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_fetch_greeks_from_opra',
                'symbol': symbol
            })
            return None

    def _process_greeks_update(self, update: dict[str, Any]) -> None:
        """Process real-time Greeks update"""
        try:
            symbol = update.get('symbol')
            if not symbol:
                return

            # Create Greeks snapshot
            greeks = GreeksSnapshot(
                timestamp=datetime.now(UTC),
                symbol=symbol,
                strike=update.get('strike', 0),
                expiry=update.get('expiry', datetime.now(UTC)),
                option_type=update.get('option_type', 'call'),
                delta=update.get('delta', 0),
                gamma=update.get('gamma', 0),
                theta=update.get('theta', 0),
                vega=update.get('vega', 0),
                rho=update.get('rho', 0),
                bid=update.get('bid', 0),
                ask=update.get('ask', 0),
                mid=update.get('mid', 0),
                iv=update.get('iv', 0),
                underlying_price=update.get('underlying_price', 0),
                volume=update.get('volume', 0),
                open_interest=update.get('open_interest', 0),
                bid_size=update.get('bid_size', 0),
                ask_size=update.get('ask_size', 0),
                cache_status=GreeksCacheStatus.FRESH,
                latency_ms=update.get('latency_ms', 0)
            )

            # Update cache
            self.greeks_cache.put(symbol, greeks)

            # Check for trading opportunities
            self._check_greeks_opportunities(greeks)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_process_greeks_update',
                'update': update
            })

    # ==========================================================================
    # SIGNAL GENERATION METHODS
    # ==========================================================================

    def _generate_delta_neutral_signals(self) -> list[TradingSignal]:
        """Generate delta-neutral hedging signals"""
        signals = []

        try:
            # Check if delta hedge needed
            if abs(self.portfolio_greeks['delta']) > DELTA_REBALANCE_THRESHOLD:
                # Find best hedge instrument
                hedge_option = self._find_best_delta_hedge()

                if hedge_option:
                    signal = self._create_greeks_signal(
                        GreeksSignalType.DELTA_HEDGE,
                        hedge_option,
                        -self.portfolio_greeks['delta']  # Target delta
                    )

                    if signal:
                        signals.append(signal)
                        self.greeks_metrics['delta_hedges'] += 1

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_generate_delta_neutral_signals'})

        return signals

    def _generate_gamma_scalping_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Generate gamma scalping signals"""
        signals = []

        try:
            # Check if we have sufficient gamma
            if abs(self.portfolio_greeks['gamma']) >= GAMMA_SCALP_THRESHOLD:
                current_price = market_data['close'].iloc[-1]

                # Calculate expected gamma profit
                price_move = market_data['close'].pct_change().rolling(5).std().iloc[-1]
                expected_gamma_profit = 0.5 * self.portfolio_greeks['gamma'] * (price_move ** 2) * current_price ** 2  # noqa: E501

                if expected_gamma_profit > GAMMA_PROFIT_TARGET:
                    # Find ATM straddle for gamma scalping
                    gamma_option = self._find_best_gamma_option(current_price)

                    if gamma_option:
                        signal = self._create_greeks_signal(
                            GreeksSignalType.GAMMA_SCALP,
                            gamma_option,
                            expected_gamma_profit
                        )

                        if signal:
                            signals.append(signal)
                            self.greeks_metrics['gamma_scalps'] += 1

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_generate_gamma_scalping_signals'})

        return signals

    def _generate_vega_trading_signals(self) -> list[TradingSignal]:
        """Generate vega trading signals"""
        signals = []

        try:
            # Analyze volatility regime
            vol_regime = self._analyze_volatility_regime()

            # Long vega in low vol, short vega in high vol
            if vol_regime == 'low' and self.portfolio_greeks['vega'] < 1000:
                # Buy vega
                vega_option = self._find_best_vega_option('long')

                if vega_option:
                    signal = self._create_greeks_signal(
                        GreeksSignalType.VEGA_TRADE,
                        vega_option,
                        1000  # Target vega
                    )

                    if signal:
                        signals.append(signal)
                        self.greeks_metrics['vega_trades'] += 1

            elif vol_regime == 'high' and self.portfolio_greeks['vega'] > -1000:
                # Sell vega
                vega_option = self._find_best_vega_option('short')

                if vega_option:
                    signal = self._create_greeks_signal(
                        GreeksSignalType.VEGA_TRADE,
                        vega_option,
                        -1000  # Target vega
                    )

                    if signal:
                        signals.append(signal)
                        self.greeks_metrics['vega_trades'] += 1

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_generate_vega_trading_signals'})

        return signals

    def _check_arbitrage_opportunities(self) -> list[TradingSignal]:
        """Check for Greeks-based arbitrage opportunities"""
        signals = []

        try:
            # Put-call parity arbitrage
            parity_arbs = self._check_put_call_parity()
            for arb in parity_arbs:
                if arb.edge_percent > MIN_EDGE_THRESHOLD:
                    signal = self._create_arbitrage_signal(arb)
                    if signal:
                        signals.append(signal)

            # Calendar spread arbitrage
            calendar_arbs = self._check_calendar_arbitrage()
            for arb in calendar_arbs:
                if arb.edge_percent > MIN_EDGE_THRESHOLD:
                    signal = self._create_arbitrage_signal(arb)
                    if signal:
                        signals.append(signal)

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_check_arbitrage_opportunities'})

        return signals

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def _find_best_delta_hedge(self) -> GreeksSnapshot | None:
        """Find best option for delta hedging"""
        try:
            target_delta = -self.portfolio_greeks['delta'] / SPY_CONTRACT_MULTIPLIER
            best_option = None
            min_diff = float('inf')

            # Search cached options
            for _symbol, greeks in self.greeks_cache.cache.items():
                if greeks.cache_status == GreeksCacheStatus.FRESH:
                    delta_diff = abs(greeks.delta - target_delta)

                    if delta_diff < min_diff and delta_diff < 0.10:
                        min_diff = delta_diff
                        best_option = greeks

            return best_option

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_find_best_delta_hedge'})
            return None

    def _find_best_gamma_option(self, spot_price: float) -> GreeksSnapshot | None:
        """Find best option for gamma scalping"""
        try:
            best_option = None
            max_gamma = 0

            # Look for ATM options with high gamma
            for _symbol, greeks in self.greeks_cache.cache.items():
                if greeks.cache_status == GreeksCacheStatus.FRESH:
                    # Check if ATM
                    if abs(greeks.strike - spot_price) / spot_price < 0.01:
                        if greeks.gamma > max_gamma:
                            max_gamma = greeks.gamma
                            best_option = greeks

            return best_option

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_find_best_gamma_option'})
            return None

    def _find_best_vega_option(self, direction: str) -> GreeksSnapshot | None:
        """Find best option for vega trading"""
        try:
            best_option = None
            max_vega = 0

            # Look for options with high vega
            for _symbol, greeks in self.greeks_cache.cache.items():
                if greeks.cache_status == GreeksCacheStatus.FRESH:
                    # Check DTE for vega trading (30-60 days optimal)
                    dte = (greeks.expiry - datetime.now(UTC)).days

                    if 30 <= dte <= 60:
                        if greeks.vega > max_vega:
                            max_vega = greeks.vega
                            best_option = greeks

            return best_option

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_find_best_vega_option'})
            return None

    def _create_greeks_signal(self, signal_type: GreeksSignalType,
                            option: GreeksSnapshot,
                            target_value: float) -> TradingSignal | None:
        """Create trading signal from Greeks analysis"""
        try:
            # Calculate contracts needed
            if signal_type == GreeksSignalType.DELTA_HEDGE:
                contracts = int(target_value / option.delta)
                strength = SignalStrength.STRONG
            elif signal_type == GreeksSignalType.GAMMA_SCALP:
                contracts = 10  # Standard size for gamma scalping
                strength = SignalStrength.VERY_STRONG if option.gamma > 0.03 else SignalStrength.MODERATE  # noqa: E501
            elif signal_type == GreeksSignalType.VEGA_TRADE:
                contracts = int(abs(target_value) / option.vega)
                strength = SignalStrength.MODERATE
            else:
                contracts = 1
                strength = SignalStrength.WEAK

            # Create signal
            signal = TradingSignal(
                signal_id=str(uuid.uuid4()),
                signal_type=SignalType.BUY if contracts > 0 else SignalType.SELL,
                symbol=option.symbol,
                strength=strength,
                confidence=0.8,  # High confidence with fresh Greeks
                entry_price=option.mid,
                stop_loss=0,  # Managed by Greeks
                take_profit=0,  # Managed by Greeks
                position_size=abs(contracts),
                timestamp=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(seconds=30),  # Short expiry for fast execution  # noqa: E501
                metadata={
                    'strategy': 'greeks_based',
                    'greeks_data': {
                        'signal_type': signal_type.name,
                        'contract_delta': option.delta,
                        'contract_gamma': option.gamma,
                        'contract_theta': option.theta,
                        'contract_vega': option.vega,
                        'iv': option.iv,
                        'cache_status': option.cache_status.name,
                        'latency_ms': option.latency_ms,
                        'portfolio_impact': {
                            'delta': option.delta * contracts * SPY_CONTRACT_MULTIPLIER,
                            'gamma': option.gamma * contracts * SPY_CONTRACT_MULTIPLIER,
                            'theta': option.theta * contracts * SPY_CONTRACT_MULTIPLIER,
                            'vega': option.vega * contracts * SPY_CONTRACT_MULTIPLIER
                        },
                        'edge': target_value / 100  # Simplified edge calculation
                    }
                }
            )

            return signal

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_create_greeks_signal'})
            return None

    def _check_pin_risk(self, position: GreeksPosition) -> bool:
        """Check for pin risk near expiry"""
        try:
            # Check each contract in position
            for symbol in position.contracts:
                greeks = self.greeks_cache.get(symbol)
                if greeks:
                    dte = (greeks.expiry - datetime.now(UTC)).days

                    # Pin risk exists near expiry with high gamma
                    if dte <= 1 and abs(greeks.gamma) > 0.05:
                        # Check if near strike
                        if abs(greeks.underlying_price - greeks.strike) / greeks.strike < 0.01:
                            return True

            return False

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_check_pin_risk'})
            return False

    def _analyze_volatility_regime(self) -> str:
        """Analyze current volatility regime"""
        # Simplified - would use actual vol analysis
        # Check average IV across options
        total_iv = 0
        count = 0

        for greeks in self.greeks_cache.cache.values():
            if greeks.cache_status == GreeksCacheStatus.FRESH:
                total_iv += greeks.iv
                count += 1

        avg_iv = total_iv / count if count > 0 else 0.20

        if avg_iv < 0.15:
            return 'low'
        elif avg_iv > 0.30:
            return 'high'
        else:
            return 'normal'

    def _check_put_call_parity(self) -> list[GreeksArbitrage]:
        """Check for put-call parity violations"""
        arbitrages = []

        # Group options by strike and expiry
        options_by_strike = defaultdict(list)

        for _symbol, greeks in self.greeks_cache.cache.items():
            if greeks.cache_status == GreeksCacheStatus.FRESH:
                key = (greeks.strike, greeks.expiry)
                options_by_strike[key].append(greeks)

        # Check each strike/expiry combination
        for (strike, expiry), options in options_by_strike.items():
            calls = [o for o in options if o.option_type == 'call']
            puts = [o for o in options if o.option_type == 'put']

            if calls and puts:
                call = calls[0]
                put = puts[0]

                # Put-call parity: C - P = S - K * e^(-r*t)
                r = 0.05  # Risk-free rate
                t = (expiry - datetime.now(UTC)).days / 365

                theoretical_diff = call.underlying_price - strike * np.exp(-r * t)
                actual_diff = call.mid - put.mid

                edge = theoretical_diff - actual_diff
                edge_percent = abs(edge) / call.underlying_price

                if edge_percent > MIN_EDGE_THRESHOLD:
                    arb = GreeksArbitrage(
                        arb_id=str(uuid.uuid4()),
                        arb_type='put_call_parity',
                        contracts=[call.symbol, put.symbol],
                        theoretical_value=theoretical_diff,
                        market_value=actual_diff,
                        edge=edge,
                        edge_percent=edge_percent,
                        confidence=0.9,
                        expiry_time=datetime.now(UTC) + timedelta(minutes=5),
                        greeks_impact={
                            'delta': 0,  # Neutral
                            'gamma': 0,  # Neutral
                            'theta': call.theta - put.theta,
                            'vega': 0  # Neutral
                        }
                    )
                    arbitrages.append(arb)

        return arbitrages

    def _check_calendar_arbitrage(self) -> list[GreeksArbitrage]:
        """Check for calendar spread arbitrage"""
        arbitrages = []

        # Group options by strike and type
        options_by_strike = defaultdict(list)

        for _symbol, greeks in self.greeks_cache.cache.items():
            if greeks.cache_status == GreeksCacheStatus.FRESH:
                key = (greeks.strike, greeks.option_type)
                options_by_strike[key].append(greeks)

        # Check each strike
        for (_strike, _option_type), options in options_by_strike.items():
            if len(options) >= 2:
                # Sort by expiry
                sorted_options = sorted(options, key=lambda x: x.expiry)

                for i in range(len(sorted_options) - 1):
                    near = sorted_options[i]
                    far = sorted_options[i + 1]

                    # Calendar spread should have positive value
                    spread_value = far.mid - near.mid

                    # Check if mispriced based on theta
                    days_between = (far.expiry - near.expiry).days
                    expected_value = near.theta * days_between / 365

                    edge = spread_value - expected_value
                    edge_percent = abs(edge) / near.mid if near.mid > 0 else 0

                    if edge_percent > MIN_EDGE_THRESHOLD and edge > 0:
                        arb = GreeksArbitrage(
                            arb_id=str(uuid.uuid4()),
                            arb_type='calendar',
                            contracts=[near.symbol, far.symbol],
                            theoretical_value=expected_value,
                            market_value=spread_value,
                            edge=edge,
                            edge_percent=edge_percent,
                            confidence=0.7,
                            expiry_time=datetime.now(UTC) + timedelta(minutes=10),
                            greeks_impact={
                                'delta': far.delta - near.delta,
                                'gamma': far.gamma - near.gamma,
                                'theta': far.theta - near.theta,
                                'vega': far.vega - near.vega
                            }
                        )
                        arbitrages.append(arb)

        return arbitrages

    def _create_arbitrage_signal(self, arb: GreeksArbitrage) -> TradingSignal | None:
        """Create signal from arbitrage opportunity"""
        try:
            # Determine signal strength based on edge
            if arb.edge_percent > 0.02:
                strength = SignalStrength.VERY_STRONG
            elif arb.edge_percent > 0.015:
                strength = SignalStrength.STRONG
            elif arb.edge_percent > 0.01:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK

            # Create signal
            signal = TradingSignal(
                signal_id=arb.arb_id,
                signal_type=SignalType.BUY,  # Arbitrage is always a package
                symbol='SPY',  # Base symbol
                strength=strength,
                confidence=arb.confidence,
                entry_price=arb.market_value,
                stop_loss=arb.market_value - arb.edge * 2,  # 2x edge as stop
                take_profit=arb.theoretical_value,
                position_size=1,  # Package deal
                timestamp=datetime.now(UTC),
                expires_at=arb.expiry_time,
                metadata={
                    'strategy': 'greeks_arbitrage',
                    'arbitrage_data': {
                        'type': arb.arb_type,
                        'contracts': arb.contracts,
                        'edge': arb.edge,
                        'edge_percent': arb.edge_percent,
                        'greeks_impact': arb.greeks_impact
                    }
                }
            )

            return signal

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_create_arbitrage_signal'})
            return None

    def _filter_by_latency(self, signals: list[TradingSignal]) -> list[TradingSignal]:
        """Filter signals by latency requirements"""
        filtered = []

        for signal in signals:
            greeks_data = signal.metadata.get('greeks_data', {})
            latency_ms = greeks_data.get('latency_ms', float('inf'))

            if latency_ms <= self.max_latency_ms:
                filtered.append(signal)
            else:
                self.logger.warning("Signal %s filtered due to latency: %sms", signal.signal_id, latency_ms)  # noqa: E501

        return filtered

    def _arbitrage_detection_loop(self) -> None:
        """Background loop for arbitrage detection"""
        while not self.stop_event.is_set():
            try:
                # Check for arbitrage every second
                arbs = []
                arbs.extend(self._check_put_call_parity())
                arbs.extend(self._check_calendar_arbitrage())

                # Store significant arbitrages
                for arb in arbs:
                    if arb.edge_percent > MIN_EDGE_THRESHOLD:
                        self.arbitrage_opportunities[arb.arb_id] = arb

                # Clean expired arbitrages
                current_time = datetime.now(UTC)
                expired = [
                    arb_id for arb_id, arb in self.arbitrage_opportunities.items()
                    if current_time > arb.expiry_time
                ]

                for arb_id in expired:
                    del self.arbitrage_opportunities[arb_id]

                # Sleep
                threading.Event().wait(1)

            except Exception as e:
                self.error_handler.handle_error(e, {'method': '_arbitrage_detection_loop'})

    def _check_greeks_opportunities(self, greeks: GreeksSnapshot) -> None:
        """Check for immediate opportunities from Greeks update"""
        try:
            # Check for extreme Greeks that need immediate attention

            # High gamma opportunity
            if abs(greeks.gamma) > 0.05:
                self.logger.info("High gamma detected: %s gamma=%s", greeks.symbol, greeks.gamma)

            # High vega opportunity
            if abs(greeks.vega) > 0.30:
                self.logger.info("High vega detected: %s vega=%s", greeks.symbol, greeks.vega)

            # Near-zero bid (exercise/assignment risk)
            if greeks.bid < 0.05 and greeks.delta > 0.90:
                self.logger.warning("Deep ITM option near zero: %s", greeks.symbol)

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_check_greeks_opportunities'})

    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================

    def open_greeks_position(self, signal: TradingSignal) -> GreeksPosition | None:
        """Open a new Greeks-based position"""
        try:
            greeks_data = signal.metadata.get('greeks_data', {})
            signal_type = GreeksSignalType[greeks_data.get('signal_type', 'DELTA_HEDGE')]

            # Map signal type to strategy type
            strategy_map = {
                GreeksSignalType.DELTA_HEDGE: GreeksStrategy.DELTA_NEUTRAL,
                GreeksSignalType.GAMMA_SCALP: GreeksStrategy.GAMMA_SCALPING,
                GreeksSignalType.VEGA_TRADE: GreeksStrategy.VEGA_TRADING
            }

            # Create position
            position = GreeksPosition(
                position_id=str(uuid.uuid4()),
                strategy_type=strategy_map.get(signal_type, GreeksStrategy.DELTA_NEUTRAL),
                entry_time=datetime.now(UTC),
                contracts={signal.symbol: signal.position_size}
            )

            # Update position Greeks
            self._update_position_greeks(position)

            # Add to tracking
            self.greeks_positions[position.position_id] = position

            # Update metrics
            self.greeks_metrics['total_greek_pnl'] = sum(
                p.unrealized_pnl for p in self.greeks_positions.values()
            )

            # Publish event
            self.event_manager.publish(Event.create(
                EventType.POSITION_OPENED,
                self.name,
                {
                    'position_id': position.position_id,
                    'strategy_type': position.strategy_type.name,
                    'net_greeks': {
                        'delta': position.net_delta,
                        'gamma': position.net_gamma,
                        'theta': position.net_theta,
                        'vega': position.net_vega
                    }
                }
            ))

            self.logger.info("Opened Greeks position: %s", position.position_id)
            return position

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'open_greeks_position',
                'signal_id': signal.signal_id
            })
            return None

    def close_greeks_position(self, position_id: str, reason: str) -> bool:
        """Close Greeks position"""
        try:
            position = self.greeks_positions.get(position_id)
            if not position:
                return False

            # Update final P&L
            position.realized_pnl = position.unrealized_pnl

            # Remove from active
            del self.greeks_positions[position_id]

            # Update metrics
            if position.strategy_type == GreeksStrategy.GAMMA_SCALPING:
                self.greeks_metrics['arbitrage_captured'] += position.gamma_pnl

            # Publish event
            self.event_manager.publish(Event.create(
                EventType.POSITION_CLOSED,
                self.name,
                {
                    'position_id': position_id,
                    'realized_pnl': position.realized_pnl,
                    'exit_reason': reason,
                    'trade_count': position.trade_count
                }
            ))

            self.logger.info(f"Closed Greeks position {position_id}: P&L ${position.realized_pnl:.2f}")  # noqa: E501
            return True

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'close_greeks_position',
                'position_id': position_id
            })
            return False

    # ==========================================================================
    # CLEANUP
    # ==========================================================================

    def cleanup(self) -> None:
        """Clean up resources"""
        try:
            # Stop background threads
            self.stop_event.set()
            if self.update_thread:
                self.update_thread.join(timeout=5)

            # Shutdown executor
            self.executor.shutdown(wait=True)

            # Clear cache
            self.greeks_cache.cache.clear()

            self.logger.info("GreeksBasedStrategy cleanup completed")

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'cleanup'})

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def get_strategy_summary(self) -> dict[str, Any]:
        """Get comprehensive strategy summary"""
        cache_stats = self.greeks_cache.get_stats()

        # Calculate average latency
        if self.latency_buffer:
            avg_latency = sum(self.latency_buffer) / len(self.latency_buffer)
        else:
            avg_latency = 0

        return {
            'strategy': 'GreeksBasedStrategy',
            'state': self.state,
            'portfolio_greeks': self.portfolio_greeks.copy(),
            'active_positions': len(self.greeks_positions),
            'position_types': {
                strategy.name: sum(1 for p in self.greeks_positions.values()
                                 if p.strategy_type == strategy)
                for strategy in GreeksStrategy
            },
            'cache_performance': {
                'size': cache_stats['size'],
                'hit_rate': cache_stats['hit_rate'],
                'avg_latency_ms': avg_latency
            },
            'arbitrage_opportunities': len(self.arbitrage_opportunities),
            'metrics': self.greeks_metrics.copy()
        }

# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":
    # Test Greeks-based strategy
    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000,
        max_position_size=0.02,
        max_portfolio_risk=0.06,
        max_loss_per_trade=0.01
    )

    config = {
        'enable_delta_neutral': True,
        'enable_gamma_scalping': True,
        'enable_vega_trading': True,
        'max_latency_ms': 10
    }

    strategy = GreeksBasedStrategy(event_manager, risk_profile, config)
    strategy.start()

    # Simulate some Greeks data
    test_greeks = {
        'symbol': 'SPY_450C_20250131',
        'strike': 450,
        'expiry': datetime(2025, 1, 31),
        'option_type': 'call',
        'delta': 0.55,
        'gamma': 0.025,
        'theta': -0.08,
        'vega': 0.20,
        'bid': 5.50,
        'ask': 5.60,
        'mid': 5.55,
        'iv': 0.18,
        'underlying_price': 448,
        'volume': 2500,
        'latency_ms': 5
    }

    # Add to queue for processing
    strategy.greeks_queue.put(test_greeks)

    # Create market data
    dates = pd.date_range(end=datetime.now(UTC), periods=100, freq='1min')
    prices = 450 + np.cumsum(np.random.randn(100) * 0.1)

    market_data = pd.DataFrame({
        'open': prices,
        'high': prices + 0.1,
        'low': prices - 0.1,
        'close': prices,
        'volume': np.random.randint(100000, 500000, 100)
    }, index=dates)

    # Generate signals
    signals = strategy.generate_signals(market_data)

    for _greek, _value in strategy.portfolio_greeks.items():
        pass

    cache_stats = strategy.greeks_cache.get_stats()

    for signal in signals:
        greeks_data = signal.metadata.get('greeks_data', {})

    # Get summary
    summary = strategy.get_strategy_summary()

    # Cleanup
    strategy.cleanup()
    strategy.stop()

