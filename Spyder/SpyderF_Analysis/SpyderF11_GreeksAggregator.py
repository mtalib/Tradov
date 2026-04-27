#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderF_Analysis
Module: SpyderF11_GreeksAggregator.py
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
import threading
import time
from typing import Any
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from collections import defaultdict, deque
import json
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import hashlib
import numpy as np
import redis
from cachetools import TTLCache, LRUCache
from redis.exceptions import RedisError

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from Spyder.SpyderI_Integration.SpyderI03_ConfigManager import ConfigManager
from Spyder.SpyderE_Risk.SpyderE01_RiskManager import RiskManager

class GreeksValidationLevel(Enum):
    """Greeks validation levels."""
    NONE = 0
    BASIC = 1
    STRICT = 2
    LEAN = 3  # Low-latency validation

class GreeksLimitType(Enum):
    """Types of Greeks limits."""
    PORTFOLIO = "portfolio"
    STRATEGY = "strategy"
    UNDERLYING = "underlying"

class HedgingAction(Enum):
    """Possible hedging actions."""
    BUY_STOCK = "buy_stock"
    SELL_STOCK = "sell_stock"
    BUY_CALLS = "buy_calls"
    BUY_PUTS = "buy_puts"
    CLOSE_POSITION = "close_position"
    ADJUST_POSITION = "adjust_position"

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class PositionGreeks:
    """Greeks for a single position."""
    position_id: str
    symbol: str
    quantity: int
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    dollar_delta: float
    dollar_gamma: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for caching."""
        return {
            'position_id': self.position_id,
            'symbol': self.symbol,
            'quantity': self.quantity,
            'delta': self.delta,
            'gamma': self.gamma,
            'theta': self.theta,
            'vega': self.vega,
            'rho': self.rho,
            'dollar_delta': self.dollar_delta,
            'dollar_gamma': self.dollar_gamma,
            'timestamp': self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PositionGreeks':
        """Create from dictionary."""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

@dataclass
class AggregatedGreeks:
    """Aggregated Greeks for portfolio or strategy."""
    total_delta: float = 0.0
    total_gamma: float = 0.0
    total_theta: float = 0.0
    total_vega: float = 0.0
    total_rho: float = 0.0
    dollar_delta: float = 0.0
    dollar_gamma: float = 0.0
    net_contracts: int = 0
    position_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def add_position(self, position: PositionGreeks) -> None:
        """Add position Greeks to aggregate."""
        self.total_delta += position.delta * position.quantity
        self.total_gamma += position.gamma * position.quantity
        self.total_theta += position.theta * position.quantity
        self.total_vega += position.vega * position.quantity
        self.total_rho += position.rho * position.quantity
        self.dollar_delta += position.dollar_delta
        self.dollar_gamma += position.dollar_gamma
        self.net_contracts += position.quantity
        self.position_count += 1

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'total_delta': self.total_delta,
            'total_gamma': self.total_gamma,
            'total_theta': self.total_theta,
            'total_vega': self.total_vega,
            'total_rho': self.total_rho,
            'dollar_delta': self.dollar_delta,
            'dollar_gamma': self.dollar_gamma,
            'net_contracts': self.net_contracts,
            'position_count': self.position_count,
            'timestamp': self.timestamp.isoformat()
        }

@dataclass
class GreeksLimit:
    """Greeks limit configuration."""
    limit_type: GreeksLimitType
    max_delta: float | None = None
    max_gamma: float | None = None
    max_theta: float | None = None
    max_vega: float | None = None
    max_rho: float | None = None
    min_delta: float | None = None
    min_gamma: float | None = None
    min_theta: float | None = None
    min_vega: float | None = None
    min_rho: float | None = None

@dataclass
class GreeksAlert:
    """Greeks limit breach alert."""
    greek: str
    current_value: float
    limit_value: float
    breach_percentage: float
    limit_type: GreeksLimitType
    action_required: HedgingAction | None = None
    timestamp: datetime = field(default_factory=datetime.now)

# ==============================================================================
# GREEKS CALCULATION ENGINE
# ==============================================================================
class GreeksCalculationEngine:
    """
    High-performance Greeks calculation engine with caching.
    """

    def __init__(self, config_manager: ConfigManager, redis_client: redis.Redis | None = None):
        """Initialize calculation engine."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config_manager = config_manager

        # Load configuration
        self._load_config()

        # Initialize Redis
        self.redis_client = redis_client or self._init_redis()

        # Initialize local caches
        self._init_local_caches()

        # Initialize Greeks calculator
        self.greeks_calculator = GreeksCalculator(config_manager)

        # Thread pool for parallel calculations
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

        self.logger.info("GreeksCalculationEngine initialized with caching")

    def _load_config(self):
        """Load configuration."""
        config = self.config_manager.get_config('greeks_aggregator', {})

        # Cache settings
        self.cache_ttl = config.get('cache_ttl_seconds', 60)
        self.local_cache_size = config.get('local_cache_size', 1000)
        self.redis_prefix = config.get('redis_prefix', 'spyder:greeks:')

        # Performance settings
        self.max_workers = config.get('max_workers', 4)
        self.batch_size = config.get('batch_size', 100)
        self.use_parallel = config.get('use_parallel', True)

        # Redis settings
        self.redis_host = config.get('redis_host', 'localhost')
        self.redis_port = config.get('redis_port', 6379)
        self.redis_db = config.get('redis_db', 0)
        self.redis_password = config.get('redis_password', None)

    def _init_redis(self) -> redis.Redis | None:
        """Initialize Redis connection."""
        try:
            client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                password=self.redis_password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )

            # Test connection
            client.ping()
            self.logger.info("Redis connection established")
            return client

        except Exception as e:
            self.logger.warning("Redis connection failed, using local cache only: %s", e)
            return None

    def _init_local_caches(self):
        """Initialize local caches."""
        # TTL cache for position Greeks
        self.position_cache = TTLCache(
            maxsize=self.local_cache_size,
            ttl=self.cache_ttl
        )

        # LRU cache for aggregated Greeks
        self.aggregate_cache = LRUCache(maxsize=self.local_cache_size // 2)

        # Cache for market data
        self.market_cache = TTLCache(
            maxsize=100,
            ttl=5  # Short TTL for market data
        )

    def calculate_position_greeks(
        self,
        position: dict[str, Any],
        market_data: dict[str, float],
        force_recalc: bool = False
    ) -> PositionGreeks:
        """
        Calculate Greeks for a single position with caching.

        Args:
            position: Position dictionary
            market_data: Current market data
            force_recalc: Force recalculation

        Returns:
            PositionGreeks object
        """
        # Generate cache key
        cache_key = self._generate_cache_key(position, market_data)

        # Check local cache first
        if not force_recalc and cache_key in self.position_cache:
            return self.position_cache[cache_key]

        # Check Redis cache
        if not force_recalc and self.redis_client:
            redis_key = f"{self.redis_prefix}position:{cache_key}"
            try:
                cached_data = self.redis_client.get(redis_key)
                if cached_data:
                    greeks = PositionGreeks.from_dict(json.loads(cached_data))
                    self.position_cache[cache_key] = greeks
                    return greeks
            except RedisError as e:
                self.logger.warning("Redis read error: %s", e)

        # Calculate Greeks
        greeks = self._calculate_position_greeks_impl(position, market_data)

        # Cache results
        self.position_cache[cache_key] = greeks

        # Cache in Redis
        if self.redis_client:
            redis_key = f"{self.redis_prefix}position:{cache_key}"
            try:
                self.redis_client.setex(
                    redis_key,
                    self.cache_ttl,
                    json.dumps(greeks.to_dict())
                )
            except RedisError as e:
                self.logger.warning("Redis write error: %s", e)

        return greeks

    def calculate_portfolio_greeks(
        self,
        positions: list[dict[str, Any]],
        market_data: dict[str, float]
    ) -> AggregatedGreeks:
        """
        Calculate aggregated Greeks for portfolio with parallel processing.

        Args:
            positions: List of positions
            market_data: Current market data

        Returns:
            AggregatedGreeks object
        """
        # Check aggregate cache
        cache_key = self._generate_portfolio_cache_key(positions, market_data)
        if cache_key in self.aggregate_cache:
            return self.aggregate_cache[cache_key]

        aggregated = AggregatedGreeks()

        if self.use_parallel and len(positions) > self.batch_size:
            # Parallel calculation for large portfolios
            futures = []

            for position in positions:
                future = self.executor.submit(
                    self.calculate_position_greeks,
                    position,
                    market_data
                )
                futures.append(future)

            # Collect results
            for future in futures:
                try:
                    position_greeks = future.result(timeout=5)
                    aggregated.add_position(position_greeks)
                except Exception as e:
                    self.logger.error("Error calculating position Greeks: %s", e)
        else:
            # Sequential calculation for small portfolios
            for position in positions:
                try:
                    position_greeks = self.calculate_position_greeks(
                        position,
                        market_data
                    )
                    aggregated.add_position(position_greeks)
                except Exception as e:
                    self.logger.error("Error calculating position Greeks: %s", e)

        # Cache result
        self.aggregate_cache[cache_key] = aggregated

        return aggregated

    def _calculate_position_greeks_impl(
        self,
        position: dict[str, Any],
        market_data: dict[str, float]
    ) -> PositionGreeks:
        """Implementation of Greeks calculation."""
        # Extract position details
        symbol = position['symbol']
        quantity = position['quantity']
        option_type = position['option_type']
        strike = position['strike']
        expiry = position['expiry']

        # Get market data
        underlying_price = market_data.get('underlying_price', 0)
        volatility = market_data.get('volatility', 0.2)
        risk_free_rate = market_data.get('risk_free_rate', 0.05)

        # Calculate time to expiry
        time_to_expiry = (expiry - datetime.now(timezone.utc)).total_seconds() / (365 * 24 * 3600)

        # Calculate Greeks
        greeks = self.greeks_calculator.calculate_all_greeks(
            S=underlying_price,
            K=strike,
            T=time_to_expiry,
            r=risk_free_rate,
            sigma=volatility,
            option_type=option_type,
            style=position.get('style', 'american')  # Default to American
        )

        # Create PositionGreeks object
        return PositionGreeks(
            position_id=position['id'],
            symbol=symbol,
            quantity=quantity,
            delta=greeks['delta'],
            gamma=greeks['gamma'],
            theta=greeks['theta'],
            vega=greeks['vega'],
            rho=greeks['rho'],
            dollar_delta=greeks['delta'] * quantity * 100 * underlying_price,
            dollar_gamma=greeks['gamma'] * quantity * 100 * underlying_price ** 2 / 100
        )

    def _generate_cache_key(
        self,
        position: dict[str, Any],
        market_data: dict[str, float]
    ) -> str:
        """Generate cache key for position."""
        key_data = {
            'position_id': position['id'],
            'strike': position['strike'],
            'expiry': position['expiry'].isoformat(),
            'underlying_price': round(market_data.get('underlying_price', 0), 2),
            'volatility': round(market_data.get('volatility', 0), 4),
            'risk_free_rate': round(market_data.get('risk_free_rate', 0), 4)
        }

        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()

    def _generate_portfolio_cache_key(
        self,
        positions: list[dict[str, Any]],
        market_data: dict[str, float]
    ) -> str:
        """Generate cache key for portfolio."""
        position_ids = sorted([p['id'] for p in positions])
        key_data = {
            'position_ids': position_ids,
            'underlying_price': round(market_data.get('underlying_price', 0), 2),
            'volatility': round(market_data.get('volatility', 0), 4),
            'timestamp': int(time.time() // self.cache_ttl)  # Time bucket
        }

        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()

    def invalidate_cache(self, position_id: str | None = None):
        """Invalidate cache entries."""
        if position_id:
            # Invalidate specific position
            keys_to_remove = [
                k for k in self.position_cache
                if position_id in str(k)
            ]
            for key in keys_to_remove:
                del self.position_cache[key]

            # Invalidate Redis cache
            if self.redis_client:
                pattern = f"{self.redis_prefix}position:*{position_id}*"
                try:
                    for key in self.redis_client.scan_iter(pattern):
                        self.redis_client.delete(key)
                except RedisError as e:
                    self.logger.warning("Redis invalidation error: %s", e)
        else:
            # Clear all caches
            self.position_cache.clear()
            self.aggregate_cache.clear()

            # Clear Redis cache
            if self.redis_client:
                pattern = f"{self.redis_prefix}*"
                try:
                    for key in self.redis_client.scan_iter(pattern):
                        self.redis_client.delete(key)
                except RedisError as e:
                    self.logger.warning("Redis clear error: %s", e)

# ==============================================================================
# GREEKS VALIDATOR
# ==============================================================================
class LEANGreeksValidator:
    """
    Low-latency Greeks validation with configurable levels.
    """

    def __init__(self, risk_manager: RiskManager):
        """Initialize validator."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.risk_manager = risk_manager

        # Validation levels
        self.validation_levels = {
            GreeksValidationLevel.NONE: self._validate_none,
            GreeksValidationLevel.BASIC: self._validate_basic,
            GreeksValidationLevel.STRICT: self._validate_strict,
            GreeksValidationLevel.LEAN: self._validate_lean
        }

        # Default limits
        self.default_limits = GreeksLimit(
            limit_type=GreeksLimitType.PORTFOLIO,
            max_delta=1000,
            min_delta=-1000,
            max_gamma=100,
            min_gamma=-100,
            max_vega=5000,
            min_vega=-5000,
            max_theta=-10000,  # Theta is usually negative
            min_theta=-50000,
            max_rho=10000,
            min_rho=-10000
        )

    def validate_greeks(
        self,
        greeks: AggregatedGreeks,
        limits: GreeksLimit | None = None,
        level: GreeksValidationLevel = GreeksValidationLevel.LEAN
    ) -> tuple[bool, list[GreeksAlert]]:
        """
        Validate Greeks against limits.

        Returns:
            Tuple of (is_valid, alerts)
        """
        limits = limits or self.default_limits
        validation_func = self.validation_levels[level]
        return validation_func(greeks, limits)

    def _validate_none(
        self,
        greeks: AggregatedGreeks,
        limits: GreeksLimit
    ) -> tuple[bool, list[GreeksAlert]]:
        """No validation - always passes."""
        return True, []

    def _validate_basic(
        self,
        greeks: AggregatedGreeks,
        limits: GreeksLimit
    ) -> tuple[bool, list[GreeksAlert]]:
        """Basic validation - check major Greeks only."""
        alerts = []

        # Check delta
        if limits.max_delta and greeks.total_delta > limits.max_delta:
            alerts.append(GreeksAlert(
                greek='delta',
                current_value=greeks.total_delta,
                limit_value=limits.max_delta,
                breach_percentage=(greeks.total_delta - limits.max_delta) / limits.max_delta * 100,
                limit_type=limits.limit_type,
                action_required=HedgingAction.SELL_STOCK if greeks.total_delta > 0 else HedgingAction.BUY_STOCK  # noqa: E501
            ))

        # Check gamma
        if limits.max_gamma and abs(greeks.total_gamma) > limits.max_gamma:
            alerts.append(GreeksAlert(
                greek='gamma',
                current_value=greeks.total_gamma,
                limit_value=limits.max_gamma,
                breach_percentage=(abs(greeks.total_gamma) - limits.max_gamma) / limits.max_gamma * 100,  # noqa: E501
                limit_type=limits.limit_type,
                action_required=HedgingAction.ADJUST_POSITION
            ))

        return len(alerts) == 0, alerts

    def _validate_strict(
        self,
        greeks: AggregatedGreeks,
        limits: GreeksLimit
    ) -> tuple[bool, list[GreeksAlert]]:
        """Strict validation - check all Greeks."""
        alerts = []

        # Check all Greeks
        greeks_checks = [
            ('delta', greeks.total_delta, limits.max_delta, limits.min_delta),
            ('gamma', greeks.total_gamma, limits.max_gamma, limits.min_gamma),
            ('theta', greeks.total_theta, limits.max_theta, limits.min_theta),
            ('vega', greeks.total_vega, limits.max_vega, limits.min_vega),
            ('rho', greeks.total_rho, limits.max_rho, limits.min_rho)
        ]

        for greek_name, value, max_limit, min_limit in greeks_checks:
            if max_limit is not None and value > max_limit:
                alerts.append(self._create_alert(
                    greek_name, value, max_limit, limits.limit_type, 'max'
                ))
            elif min_limit is not None and value < min_limit:
                alerts.append(self._create_alert(
                    greek_name, value, min_limit, limits.limit_type, 'min'
                ))

        return len(alerts) == 0, alerts

    def _validate_lean(
        self,
        greeks: AggregatedGreeks,
        limits: GreeksLimit
    ) -> tuple[bool, list[GreeksAlert]]:
        """LEAN validation - optimized for low latency."""
        # Quick check on critical Greeks only
        if (limits.max_delta and abs(greeks.total_delta) > limits.max_delta * 1.1):
            # 10% buffer for LEAN mode
            return False, [GreeksAlert(
                greek='delta',
                current_value=greeks.total_delta,
                limit_value=limits.max_delta,
                breach_percentage=(abs(greeks.total_delta) - limits.max_delta) / limits.max_delta * 100,  # noqa: E501
                limit_type=limits.limit_type,
                action_required=HedgingAction.ADJUST_POSITION
            )]

        if (limits.max_gamma and abs(greeks.total_gamma) > limits.max_gamma * 1.2):
            # 20% buffer for gamma in LEAN mode
            return False, [GreeksAlert(
                greek='gamma',
                current_value=greeks.total_gamma,
                limit_value=limits.max_gamma,
                breach_percentage=(abs(greeks.total_gamma) - limits.max_gamma) / limits.max_gamma * 100,  # noqa: E501
                limit_type=limits.limit_type,
                action_required=HedgingAction.ADJUST_POSITION
            )]

        return True, []

    def _create_alert(
        self,
        greek: str,
        value: float,
        limit: float,
        limit_type: GreeksLimitType,
        breach_type: str
    ) -> GreeksAlert:
        """Create Greeks alert."""
        breach_pct = abs((value - limit) / limit * 100)

        # Determine action based on Greek and breach
        action = None
        if greek == 'delta':
            if breach_type == 'max' and value > 0:
                action = HedgingAction.SELL_STOCK
            elif breach_type == 'min' and value < 0:
                action = HedgingAction.BUY_STOCK
        elif greek == 'gamma' or greek == 'vega':
            action = HedgingAction.ADJUST_POSITION

        return GreeksAlert(
            greek=greek,
            current_value=value,
            limit_value=limit,
            breach_percentage=breach_pct,
            limit_type=limit_type,
            action_required=action
        )

# ==============================================================================
# MAIN GREEKS AGGREGATOR
# ==============================================================================
class GreeksAggregator:
    """
    Main Greeks aggregation system with real-time updates and risk integration.
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        risk_manager: RiskManager,
        redis_client: redis.Redis | None = None
    ):
        """Initialize Greeks aggregator."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config_manager = config_manager
        self.risk_manager = risk_manager

        # Initialize components
        self.calculation_engine = GreeksCalculationEngine(config_manager, redis_client)
        self.validator = LEANGreeksValidator(risk_manager)

        # Greeks storage
        self.position_greeks: dict[str, PositionGreeks] = {}
        self.portfolio_greeks = AggregatedGreeks()
        self.strategy_greeks: dict[str, AggregatedGreeks] = defaultdict(AggregatedGreeks)

        # Real-time updates
        self.update_callbacks: list[Callable] = []
        self.is_running = False
        self._stop_event = threading.Event()
        self.update_thread = None

        # Performance metrics
        self.metrics = {
            'calculations_per_second': deque(maxlen=100),
            'cache_hit_rate': deque(maxlen=100),
            'validation_time_ms': deque(maxlen=100)
        }

        self.logger.info("GreeksAggregator initialized with caching and parallel processing")

    def start_real_time_updates(self, update_interval: float = 1.0):
        """Start real-time Greeks updates."""
        if self.is_running:
            return

        self.is_running = True
        self._stop_event.clear()
        self.update_thread = threading.Thread(
            target=self._update_loop,
            args=(update_interval,),
            daemon=True
        )
        self.update_thread.start()
        self.logger.info("Started real-time Greeks updates")

    def stop_real_time_updates(self):
        """Stop real-time updates."""
        self.is_running = False
        self._stop_event.set()
        if self.update_thread:
            self.update_thread.join(timeout=5)
        self.logger.info("Stopped real-time Greeks updates")

    def add_update_callback(self, callback: Callable):
        """Add callback for Greeks updates."""
        self.update_callbacks.append(callback)

    def update_position(
        self,
        position: dict[str, Any],
        market_data: dict[str, float],
        force_recalc: bool = False
    ) -> PositionGreeks:
        """
        Update Greeks for a single position.

        Args:
            position: Position data
            market_data: Current market data
            force_recalc: Force recalculation

        Returns:
            Updated PositionGreeks
        """
        start_time = time.time()

        # Calculate Greeks
        position_greeks = self.calculation_engine.calculate_position_greeks(
            position,
            market_data,
            force_recalc
        )

        # Store in memory
        self.position_greeks[position['id']] = position_greeks

        # Update aggregates
        self._update_aggregates()

        # Track performance
        calc_time = time.time() - start_time
        self.metrics['calculations_per_second'].append(1 / calc_time if calc_time > 0 else 0)

        return position_greeks

    def update_portfolio(
        self,
        positions: list[dict[str, Any]],
        market_data: dict[str, float]
    ) -> AggregatedGreeks:
        """
        Update Greeks for entire portfolio.

        Args:
            positions: List of positions
            market_data: Current market data

        Returns:
            Updated portfolio Greeks
        """
        start_time = time.time()

        # Calculate all positions
        self.portfolio_greeks = self.calculation_engine.calculate_portfolio_greeks(
            positions,
            market_data
        )

        # Validate Greeks
        validation_start = time.time()
        is_valid, alerts = self.validator.validate_greeks(
            self.portfolio_greeks,
            level=GreeksValidationLevel.LEAN
        )
        validation_time = (time.time() - validation_start) * 1000
        self.metrics['validation_time_ms'].append(validation_time)

        # Handle alerts
        if alerts:
            self._handle_greeks_alerts(alerts)

        # Notify callbacks
        self._notify_callbacks()

        # Log performance
        total_time = time.time() - start_time
        self.logger.debug(
            f"Portfolio Greeks updated: {len(positions)} positions in {total_time:.3f}s"
        )

        return self.portfolio_greeks

    def get_portfolio_greeks(self) -> AggregatedGreeks:
        """Get current portfolio Greeks."""
        return self.portfolio_greeks

    def get_strategy_greeks(self, strategy_name: str) -> AggregatedGreeks:
        """Get Greeks for specific strategy."""
        return self.strategy_greeks.get(strategy_name, AggregatedGreeks())

    def get_position_greeks(self, position_id: str) -> PositionGreeks | None:
        """Get Greeks for specific position."""
        return self.position_greeks.get(position_id)

    def get_hedging_requirements(self) -> dict[str, float]:
        """
        Calculate hedging requirements based on current Greeks.

        Returns:
            Dictionary of hedging requirements
        """
        requirements = {}

        # Delta hedging
        if abs(self.portfolio_greeks.total_delta) > 50:
            requirements['delta_hedge'] = -self.portfolio_greeks.total_delta

        # Gamma hedging (using options)
        if abs(self.portfolio_greeks.total_gamma) > 10:
            requirements['gamma_hedge'] = -self.portfolio_greeks.total_gamma

        # Vega hedging
        if abs(self.portfolio_greeks.total_vega) > 500:
            requirements['vega_hedge'] = -self.portfolio_greeks.total_vega

        return requirements

    def get_performance_metrics(self) -> dict[str, float]:
        """Get performance metrics."""
        return {
            'avg_calculations_per_second': np.mean(self.metrics['calculations_per_second']) if self.metrics['calculations_per_second'] else 0,  # noqa: E501
            'cache_hit_rate': np.mean(self.metrics['cache_hit_rate']) if self.metrics['cache_hit_rate'] else 0,  # noqa: E501
            'avg_validation_time_ms': np.mean(self.metrics['validation_time_ms']) if self.metrics['validation_time_ms'] else 0,  # noqa: E501
            'total_positions': len(self.position_greeks),
            'cache_size': len(self.calculation_engine.position_cache)
        }

    def clear_cache(self):
        """Clear all caches."""
        self.calculation_engine.invalidate_cache()
        self.logger.info("Cleared all Greeks caches")

    def _update_loop(self, interval: float):
        """Real-time update loop."""
        while self.is_running:
            try:
                # Get current positions and market data
                # This would connect to your data sources
                positions = self._get_current_positions()
                market_data = self._get_current_market_data()

                if positions and market_data:
                    self.update_portfolio(positions, market_data)

                self._stop_event.wait(interval)

            except Exception as e:
                self.logger.error("Error in Greeks update loop: %s", e)
                self._stop_event.wait(interval)

    def _update_aggregates(self):
        """Update aggregated Greeks."""
        # Reset portfolio Greeks
        self.portfolio_greeks = AggregatedGreeks()

        # Reset strategy Greeks
        self.strategy_greeks.clear()

        # Aggregate all positions
        for position_greeks in self.position_greeks.values():
            self.portfolio_greeks.add_position(position_greeks)

            # Add to strategy Greeks (would need strategy mapping)
            # strategy = self._get_position_strategy(position_greeks.position_id)
            # self.strategy_greeks[strategy].add_position(position_greeks)

    def _handle_greeks_alerts(self, alerts: list[GreeksAlert]):
        """Handle Greeks limit alerts."""
        for alert in alerts:
            self.logger.warning(
                f"Greeks limit breach: {alert.greek} = {alert.current_value:.2f} "
                f"(limit: {alert.limit_value:.2f}, breach: {alert.breach_percentage:.1f}%)"
            )

            # Send to risk manager
            self.risk_manager.handle_greeks_breach(alert)

            # Notify callbacks
            for callback in self.update_callbacks:
                try:
                    callback('alert', alert)
                except Exception as e:
                    self.logger.error("Error in alert callback: %s", e)

    def _notify_callbacks(self):
        """Notify all registered callbacks."""
        for callback in self.update_callbacks:
            try:
                callback('update', self.portfolio_greeks)
            except Exception as e:
                self.logger.error("Error in update callback: %s", e)

    def _get_current_positions(self) -> list[dict[str, Any]]:
        """Get current positions (placeholder)."""
        # This would connect to your position tracking system
        return []

    def _get_current_market_data(self) -> dict[str, float]:
        """Get current market data (placeholder)."""
        # This would connect to your market data feed
        return {
            'underlying_price': 585.0,
            'volatility': 0.15,
            'risk_free_rate': 0.05
        }

# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================
if __name__ == "__main__":
    # Initialize components
    config_manager = ConfigManager()
    risk_manager = RiskManager(config_manager)

    # Initialize Redis (optional)
    try:
        redis_client = redis.Redis(host='localhost', port=6379, db=0)
        redis_client.ping()
    except Exception:
        redis_client = None

    # Create aggregator
    aggregator = GreeksAggregator(config_manager, risk_manager, redis_client)

    # Example positions
    positions = [
        {
            'id': 'pos1',
            'symbol': 'SPY',
            'quantity': 10,
            'option_type': 'call',
            'strike': 590,
            'expiry': datetime.now(timezone.utc) + timedelta(days=30),
            'style': 'american'
        },
        {
            'id': 'pos2',
            'symbol': 'SPY',
            'quantity': -5,
            'option_type': 'put',
            'strike': 580,
            'expiry': datetime.now(timezone.utc) + timedelta(days=30),
            'style': 'american'
        }
    ]

    # Market data
    market_data = {
        'underlying_price': 585.0,
        'volatility': 0.15,
        'risk_free_rate': 0.05
    }

    # Update portfolio Greeks
    portfolio_greeks = aggregator.update_portfolio(positions, market_data)


    # Get hedging requirements
    hedging = aggregator.get_hedging_requirements()
    for _hedge_type, _amount in hedging.items():
        pass

    # Performance metrics
    metrics = aggregator.get_performance_metrics()
    for _metric, _value in metrics.items():
        pass

    # Test cache performance
    import time

    # First calculation (cache miss)
    start = time.time()
    aggregator.update_portfolio(positions, market_data)
    first_time = time.time() - start

    # Second calculation (cache hit)
    start = time.time()
    aggregator.update_portfolio(positions, market_data)
    second_time = time.time() - start

    # Clear cache
    aggregator.clear_cache()

    # Start real-time updates
    aggregator.start_real_time_updates(update_interval=5.0)

    # Let it run for a bit
    time.sleep(10)  # thread-safe: time.sleep() intentional

    # Stop updates
    aggregator.stop_real_time_updates()
