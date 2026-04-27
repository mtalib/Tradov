#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC05_VolumeProfile.py
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
from datetime import datetime, timedelta, time as dt_time
from dataclasses import dataclass
from collections import deque
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderC_MarketData.SpyderC01_DataFeed import MarketTick
from Spyder.SpyderC_MarketData.SpyderC06_DataValidator import DataValidator
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

DEFAULT_PRICE_LEVELS = 500  # Number of price levels for volume profile
MIN_TICK_VOLUME = 1  # Minimum volume to consider
VWAP_LOOKBACK_PERIODS = [20, 50, 100, 200]  # VWAP calculation periods
POC_THRESHOLD = 0.70  # Point of Control threshold (70% of volume)
HVN_THRESHOLD = 0.85  # High Volume Node threshold (85th percentile)
LVN_THRESHOLD = 0.15  # Low Volume Node threshold (15th percentile)

# Institutional Flow Detection
BLOCK_SIZE_THRESHOLD = 10000  # Minimum shares for block trade
LARGE_TRADE_THRESHOLD = 50000  # Large institutional trade threshold
VOLUME_SPIKE_THRESHOLD = 3.0  # Standard deviations for volume spike
PRICE_IMPACT_THRESHOLD = 0.05  # Minimum price impact percentage

# Time-based Analysis
SESSION_PERIODS = {
    'pre_market': (dt_time(4, 0), dt_time(9, 30)),
    'opening': (dt_time(9, 30), dt_time(10, 30)),
    'morning': (dt_time(10, 30), dt_time(12, 0)),
    'lunch': (dt_time(12, 0), dt_time(14, 0)),
    'afternoon': (dt_time(14, 0), dt_time(15, 30)),
    'closing': (dt_time(15, 30), dt_time(16, 0)),
    'after_hours': (dt_time(16, 0), dt_time(20, 0))
}

# ==============================================================================
# ENUMS
# ==============================================================================
class VolumeNodeType(Enum):
    """Volume node classification."""
    HIGH_VOLUME_NODE = "hvn"
    LOW_VOLUME_NODE = "lvn"
    POINT_OF_CONTROL = "poc"
    VALUE_AREA_HIGH = "vah"
    VALUE_AREA_LOW = "val"
    NORMAL = "normal"

class FlowDirection(Enum):
    """Institutional flow direction."""
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    NEUTRAL = "neutral"
    ROTATION = "rotation"

class VWAPPosition(Enum):
    """Price position relative to VWAP."""
    ABOVE = "above"
    BELOW = "below"
    AT_VWAP = "at_vwap"
    RECLAIMING = "reclaiming"
    LOSING = "losing"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class VolumeLevel:
    """Individual volume level data."""
    price: float
    volume: int
    trades: int
    buy_volume: int
    sell_volume: int
    timestamp: datetime

    @property
    def imbalance_ratio(self) -> float:
        """Calculate buy/sell imbalance ratio."""
        if self.sell_volume == 0:
            return float('inf') if self.buy_volume > 0 else 0.0
        return self.buy_volume / self.sell_volume

    @property
    def net_volume(self) -> int:
        """Calculate net volume (buy - sell)."""
        return self.buy_volume - self.sell_volume

@dataclass
class VolumeNode:
    """Volume node (significant price level)."""
    price: float
    volume: int
    node_type: VolumeNodeType
    strength: float  # 0.0 to 1.0
    session: str
    first_touch: datetime
    last_touch: datetime
    touch_count: int = 0

    def __post_init__(self):
        self.touch_count = 1

@dataclass
class VWAPData:
    """VWAP calculation data."""
    vwap: float
    volume: int
    value: float  # cumulative price * volume
    period: int
    std_dev_1: float
    std_dev_2: float
    timestamp: datetime

@dataclass
class InstitutionalFlow:
    """Institutional flow analysis."""
    direction: FlowDirection
    strength: float  # 0.0 to 1.0
    volume: int
    avg_trade_size: float
    block_trades: int
    large_trades: int
    price_impact: float
    session: str
    confidence: float

@dataclass
class VolumeProfile:
    """Complete volume profile for a time period."""
    price_levels: list[VolumeLevel]
    volume_nodes: list[VolumeNode]
    poc_price: float
    value_area_high: float
    value_area_low: float
    total_volume: int
    period_start: datetime
    period_end: datetime
    session: str

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class VolumeProfileAnalyzer:
    """
    Volume profile analyzer for institutional flow detection.

    This class provides comprehensive volume profile analysis including VWAP calculations,
    volume distribution analysis, institutional flow detection, and volume-based support
    and resistance identification. It processes real-time tick data to build volume profiles
    and detect significant institutional activity.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        data_validator: Data validation instance
        price_levels: Current price level data
        volume_nodes: Identified volume nodes
        vwap_data: VWAP calculations for different periods
        flow_analysis: Current institutional flow analysis

    Example:
        >>> analyzer = VolumeProfileAnalyzer()
        >>> analyzer.initialize()
        >>> analyzer.start_analysis()
        >>> profile = analyzer.get_current_profile()
        >>> nodes = analyzer.get_volume_nodes()
    """

    def __init__(self, config: dict | None = None):
        """Initialize volume profile analyzer."""
        self.logger = SpyderLogger.get_logger("VolumeProfileAnalyzer")
        self.error_handler = SpyderErrorHandler()
        self.data_validator = DataValidator()

        # Configuration
        self.config = config or {}
        self.price_levels_count = self.config.get('price_levels', DEFAULT_PRICE_LEVELS)
        self.vwap_periods = self.config.get('vwap_periods', VWAP_LOOKBACK_PERIODS)

        # Data storage
        self.price_levels: dict[float, VolumeLevel] = {}
        self.volume_nodes: list[VolumeNode] = []
        self.vwap_data: dict[int, VWAPData] = {}
        self.flow_analysis: InstitutionalFlow | None = None

        # Real-time data
        self.tick_buffer: deque = deque(maxlen=10000)
        self.trade_buffer: deque = deque(maxlen=5000)
        self.current_session = "regular"

        # Analysis state
        self.is_analyzing = False
        self.last_update = None
        self.profile_cache: dict[str, VolumeProfile] = {}

        # Threading
        self._lock = threading.RLock()
        self._analysis_thread = None
        self._stop_event = threading.Event()

        # Event manager integration
        self.event_manager = get_event_manager()

        self.logger.info("Volume Profile Analyzer initialized")

    # ==========================================================================
    # INITIALIZATION METHODS
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize the volume profile analyzer.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Initialize data structures
            self._reset_analysis_data()

            # Register event callbacks
            self._register_event_callbacks()

            # Initialize VWAP calculations
            self._initialize_vwap()

            self.logger.info("Volume profile analyzer initialized successfully")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'initialize',
                'class': 'VolumeProfileAnalyzer'
            })
            return False

    def _reset_analysis_data(self) -> None:
        """Reset all analysis data structures."""
        with self._lock:
            self.price_levels.clear()
            self.volume_nodes.clear()
            self.vwap_data.clear()
            self.tick_buffer.clear()
            self.trade_buffer.clear()
            self.profile_cache.clear()
            self.flow_analysis = None
            self.last_update = None

    def _register_event_callbacks(self) -> None:
        """Register event manager callbacks."""
        if self.event_manager:
            self.event_manager.subscribe(EventType.MARKET_DATA, self._on_market_data)
            self.event_manager.subscribe(EventType.TRADE_EXECUTED, self._on_trade_data)

    def _initialize_vwap(self) -> None:
        """Initialize VWAP calculations for different periods."""
        for period in self.vwap_periods:
            self.vwap_data[period] = VWAPData(
                vwap=0.0,
                volume=0,
                value=0.0,
                period=period,
                std_dev_1=0.0,
                std_dev_2=0.0,
                timestamp=datetime.now()
            )

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start_analysis(self) -> None:
        """Start volume profile analysis."""
        if self.is_analyzing:
            self.logger.warning("Volume profile analysis already running")
            return

        try:
            self.is_analyzing = True
            self._stop_event.clear()

            # Start analysis thread
            self._analysis_thread = threading.Thread(
                target=self._analysis_loop,
                name="VolumeProfileAnalysis",
                daemon=True
            )
            self._analysis_thread.start()

            self.logger.info("Volume profile analysis started")

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'start_analysis'
            })
            self.is_analyzing = False

    def stop_analysis(self) -> None:
        """Stop volume profile analysis."""
        if not self.is_analyzing:
            return

        try:
            self.is_analyzing = False
            self._stop_event.set()

            if self._analysis_thread and self._analysis_thread.is_alive():
                self._analysis_thread.join(timeout=5.0)

            self.logger.info("Volume profile analysis stopped")

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'stop_analysis'
            })

    # ==========================================================================
    # DATA PROCESSING METHODS
    # ==========================================================================
    def _on_market_data(self, event: Event) -> None:
        """Handle incoming market data."""
        try:
            if not self.is_analyzing:
                return

            tick_data = event.data
            if not self._validate_tick_data(tick_data):
                return

            # Create market tick
            tick = MarketTick(
                symbol=tick_data.get('symbol', 'SPY'),
                price=float(tick_data['price']),
                size=int(tick_data.get('size', 0)),
                timestamp=tick_data.get('timestamp', datetime.now()),
                bid=float(tick_data.get('bid', 0)),
                ask=float(tick_data.get('ask', 0)),
                volume=int(tick_data.get('volume', 0))
            )

            # Process tick
            self._process_tick(tick)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_on_market_data',
                'data': str(event.data)[:100]
            })

    def _on_trade_data(self, event: Event) -> None:
        """Handle incoming trade data."""
        try:
            if not self.is_analyzing:
                return

            trade_data = event.data
            if not self._validate_trade_data(trade_data):
                return

            # Process trade for institutional flow analysis
            self._process_trade(trade_data)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_on_trade_data',
                'data': str(event.data)[:100]
            })

    def _process_tick(self, tick: MarketTick) -> None:
        """Process individual tick for volume profile."""
        with self._lock:
            # Add to tick buffer
            self.tick_buffer.append(tick)

            # Update price levels
            self._update_price_level(tick)

            # Update VWAP calculations
            self._update_vwap(tick)

            # Update session tracking
            self._update_session(tick.timestamp)

            self.last_update = tick.timestamp

    def _process_trade(self, trade_data: dict) -> None:
        """Process trade data for institutional flow analysis."""
        with self._lock:
            # Add to trade buffer
            self.trade_buffer.append(trade_data)

            # Detect block trades
            if trade_data.get('size', 0) >= BLOCK_SIZE_THRESHOLD:
                self._detect_institutional_flow(trade_data)

    # ==========================================================================
    # VOLUME PROFILE CALCULATION METHODS
    # ==========================================================================
    def _update_price_level(self, tick: MarketTick) -> None:
        """Update price level with new tick data."""
        price = round(tick.price, 2)  # Round to penny

        if price in self.price_levels:
            level = self.price_levels[price]
            level.volume += tick.size
            level.trades += 1
            level.timestamp = tick.timestamp

            # Estimate buy/sell based on bid/ask
            if tick.price >= tick.ask:
                level.buy_volume += tick.size
            elif tick.price <= tick.bid:
                level.sell_volume += tick.size
            else:
                # Split volume if between bid/ask
                level.buy_volume += tick.size // 2
                level.sell_volume += tick.size - (tick.size // 2)
        else:
            # Create new price level
            buy_vol = tick.size if tick.price >= tick.ask else tick.size // 2
            sell_vol = tick.size - buy_vol

            self.price_levels[price] = VolumeLevel(
                price=price,
                volume=tick.size,
                trades=1,
                buy_volume=buy_vol,
                sell_volume=sell_vol,
                timestamp=tick.timestamp
            )

    def _update_vwap(self, tick: MarketTick) -> None:
        """Update VWAP calculations for all periods."""
        if tick.size == 0:
            return

        for period in self.vwap_periods:
            vwap_data = self.vwap_data[period]

            # Add current tick to VWAP calculation
            vwap_data.volume += tick.size
            vwap_data.value += tick.price * tick.size
            vwap_data.vwap = vwap_data.value / vwap_data.volume if vwap_data.volume > 0 else 0.0
            vwap_data.timestamp = tick.timestamp

            # Calculate standard deviation bands
            if len(self.tick_buffer) >= period:
                recent_ticks = list(self.tick_buffer)[-period:]
                prices = [t.price for t in recent_ticks]
                std_dev = np.std(prices) if len(prices) > 1 else 0.0

                vwap_data.std_dev_1 = std_dev
                vwap_data.std_dev_2 = std_dev * 2

    def _detect_institutional_flow(self, trade_data: dict) -> None:
        """Detect and analyze institutional flow patterns."""
        try:
            trade_data.get('size', 0)
            price = trade_data.get('price', 0.0)
            timestamp = trade_data.get('timestamp', datetime.now())

            # Classify trade size

            # Calculate recent flow metrics
            recent_trades = [t for t in self.trade_buffer if
                           (timestamp - t.get('timestamp', timestamp)).seconds < 300]  # 5 minutes

            if not recent_trades:
                return

            total_volume = sum(t.get('size', 0) for t in recent_trades)
            avg_trade_size = total_volume / len(recent_trades)
            block_count = sum(1 for t in recent_trades if t.get('size', 0) >= BLOCK_SIZE_THRESHOLD)
            large_count = sum(1 for t in recent_trades if t.get('size', 0) >= LARGE_TRADE_THRESHOLD)

            # Determine flow direction
            direction = self._determine_flow_direction(recent_trades, price)

            # Calculate strength and confidence
            strength = min(1.0, (avg_trade_size / BLOCK_SIZE_THRESHOLD) * 0.5 + (block_count / len(recent_trades)))  # noqa: E501
            confidence = min(1.0, total_volume / (LARGE_TRADE_THRESHOLD * 10))

            # Update flow analysis
            self.flow_analysis = InstitutionalFlow(
                direction=direction,
                strength=strength,
                volume=total_volume,
                avg_trade_size=avg_trade_size,
                block_trades=block_count,
                large_trades=large_count,
                price_impact=self._calculate_price_impact(recent_trades),
                session=self.current_session,
                confidence=confidence
            )

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_detect_institutional_flow'
            })

    # ==========================================================================
    # ANALYSIS METHODS
    # ==========================================================================
    def _analysis_loop(self) -> None:
        """Main analysis loop running in separate thread."""
        while not self._stop_event.is_set() and self.is_analyzing:
            try:
                # Update volume nodes
                self._update_volume_nodes()

                # Generate volume profile
                self._generate_volume_profile()

                # Clean old data
                self._cleanup_old_data()

                # Sleep before next analysis
                time.sleep(1.0)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.error_handler.handle_error(e, {
                    'method': '_analysis_loop'
                })
                time.sleep(5.0)  # thread-safe: time.sleep() intentional

    def _update_volume_nodes(self) -> None:
        """Update volume nodes based on current price levels."""
        if not self.price_levels:
            return

        with self._lock:
            # Calculate volume statistics
            volumes = [level.volume for level in self.price_levels.values()]
            if not volumes:
                return

            sum(volumes)
            volume_percentiles = np.percentile(volumes, [LVN_THRESHOLD * 100, HVN_THRESHOLD * 100])

            # Find Point of Control (highest volume)
            poc_level = max(self.price_levels.values(), key=lambda x: x.volume)

            # Clear existing nodes
            self.volume_nodes.clear()

            # Identify volume nodes
            for level in self.price_levels.values():
                node_type = VolumeNodeType.NORMAL
                strength = level.volume / max(volumes) if volumes else 0.0

                if level == poc_level:
                    node_type = VolumeNodeType.POINT_OF_CONTROL
                    strength = 1.0
                elif level.volume >= volume_percentiles[1]:
                    node_type = VolumeNodeType.HIGH_VOLUME_NODE
                elif level.volume <= volume_percentiles[0]:
                    node_type = VolumeNodeType.LOW_VOLUME_NODE

                # Only add significant nodes
                if node_type != VolumeNodeType.NORMAL or strength > 0.3:
                    node = VolumeNode(
                        price=level.price,
                        volume=level.volume,
                        node_type=node_type,
                        strength=strength,
                        session=self.current_session,
                        first_touch=level.timestamp,
                        last_touch=level.timestamp
                    )
                    self.volume_nodes.append(node)

    def _generate_volume_profile(self) -> None:
        """Generate complete volume profile for current period."""
        if not self.price_levels:
            return

        with self._lock:
            # Calculate value area (70% of volume)
            sorted_levels = sorted(self.price_levels.values(), key=lambda x: x.volume, reverse=True)
            total_volume = sum(level.volume for level in sorted_levels)
            value_area_volume = total_volume * POC_THRESHOLD

            # Find value area boundaries
            cumulative_volume = 0
            value_area_levels = []

            for level in sorted_levels:
                cumulative_volume += level.volume
                value_area_levels.append(level)
                if cumulative_volume >= value_area_volume:
                    break

            if value_area_levels:
                prices = [level.price for level in value_area_levels]
                value_area_high = max(prices)
                value_area_low = min(prices)
                poc_price = max(value_area_levels, key=lambda x: x.volume).price
            else:
                value_area_high = value_area_low = poc_price = 0.0

            # Create volume profile
            profile = VolumeProfile(
                price_levels=list(self.price_levels.values()),
                volume_nodes=self.volume_nodes.copy(),
                poc_price=poc_price,
                value_area_high=value_area_high,
                value_area_low=value_area_low,
                total_volume=total_volume,
                period_start=min(level.timestamp for level in self.price_levels.values()) if self.price_levels else datetime.now(),  # noqa: E501
                period_end=max(level.timestamp for level in self.price_levels.values()) if self.price_levels else datetime.now(),  # noqa: E501
                session=self.current_session
            )

            # Cache profile
            cache_key = f"{self.current_session}_{datetime.now().strftime('%Y%m%d_%H')}"
            self.profile_cache[cache_key] = profile

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _validate_tick_data(self, data: dict) -> bool:
        """Validate incoming tick data."""
        required_fields = ['price', 'timestamp']
        return all(field in data for field in required_fields)

    def _validate_trade_data(self, data: dict) -> bool:
        """Validate incoming trade data."""
        required_fields = ['price', 'size', 'timestamp']
        return all(field in data for field in required_fields)

    def _update_session(self, timestamp: datetime) -> None:
        """Update current trading session based on timestamp."""
        current_time = timestamp.time()

        for session_name, (start_time, end_time) in SESSION_PERIODS.items():
            if start_time <= current_time < end_time:
                if self.current_session != session_name:
                    self.current_session = session_name
                    self.logger.debug("Session changed to: %s", session_name)
                break

    def _determine_flow_direction(self, trades: list[dict], current_price: float) -> FlowDirection:
        """Determine institutional flow direction."""
        if not trades:
            return FlowDirection.NEUTRAL

        # Analyze trade patterns
        buy_volume = sum(t.get('size', 0) for t in trades if t.get('price', 0) >= current_price)
        sell_volume = sum(t.get('size', 0) for t in trades if t.get('price', 0) < current_price)

        total_volume = buy_volume + sell_volume
        if total_volume == 0:
            return FlowDirection.NEUTRAL

        buy_ratio = buy_volume / total_volume

        if buy_ratio > 0.6:
            return FlowDirection.ACCUMULATION
        elif buy_ratio < 0.4:
            return FlowDirection.DISTRIBUTION
        else:
            return FlowDirection.NEUTRAL

    def _calculate_price_impact(self, trades: list[dict]) -> float:
        """Calculate price impact of recent trades."""
        if len(trades) < 2:
            return 0.0

        prices = [t.get('price', 0.0) for t in trades]
        return abs(max(prices) - min(prices)) / min(prices) if min(prices) > 0 else 0.0

    def _cleanup_old_data(self) -> None:
        """Clean up old data to manage memory usage."""
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(hours=1)  # Keep 1 hour of data

        with self._lock:
            # Clean old price levels
            old_prices = [price for price, level in self.price_levels.items()
                         if level.timestamp < cutoff_time]
            for price in old_prices:
                del self.price_levels[price]

            # Clean old cache entries
            old_cache_keys = [key for key, profile in self.profile_cache.items()
                            if profile.period_end < cutoff_time]
            for key in old_cache_keys:
                del self.profile_cache[key]

    # ==========================================================================
    # PUBLIC API METHODS
    # ==========================================================================
    def get_current_profile(self) -> VolumeProfile | None:
        """Get current volume profile."""
        cache_key = f"{self.current_session}_{datetime.now().strftime('%Y%m%d_%H')}"
        return self.profile_cache.get(cache_key)

    def get_volume_nodes(self) -> list[VolumeNode]:
        """Get current volume nodes."""
        with self._lock:
            return self.volume_nodes.copy()

    def get_vwap_data(self, period: int = 20) -> VWAPData | None:
        """Get VWAP data for specified period."""
        return self.vwap_data.get(period)

    def get_institutional_flow(self) -> InstitutionalFlow | None:
        """Get current institutional flow analysis."""
        return self.flow_analysis

    def get_poc_level(self) -> float | None:
        """Get current Point of Control price level."""
        profile = self.get_current_profile()
        return profile.poc_price if profile else None

    def get_value_area(self) -> tuple[float, float] | None:
        """Get current value area (VAH, VAL)."""
        profile = self.get_current_profile()
        if profile:
            return (profile.value_area_high, profile.value_area_low)
        return None

    def get_volume_at_price(self, price: float) -> int:
        """Get volume traded at specific price level."""
        rounded_price = round(price, 2)
        level = self.price_levels.get(rounded_price)
        return level.volume if level else 0

    def is_price_above_vwap(self, price: float, period: int = 20) -> bool | None:
        """Check if price is above VWAP for given period."""
        vwap_data = self.get_vwap_data(period)
        if vwap_data and vwap_data.vwap > 0:
            return price > vwap_data.vwap
        return None

    def get_support_resistance_levels(self) -> dict[str, list[float]]:
        """Get volume-based support and resistance levels."""
        levels = {'support': [], 'resistance': []}

        for node in self.volume_nodes:
            if node.node_type in [VolumeNodeType.HIGH_VOLUME_NODE, VolumeNodeType.POINT_OF_CONTROL]:
                if node.strength > 0.7:
                    levels['resistance'].append(node.price)
                else:
                    levels['support'].append(node.price)

        # Sort levels
        levels['support'].sort()
        levels['resistance'].sort(reverse=True)

        return levels

    # ==========================================================================
    # CLEANUP METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up volume profile analyzer resources."""
        try:
            # Stop analysis
            self.stop_analysis()

            # Clear data
            with self._lock:
                self.price_levels.clear()
                self.volume_nodes.clear()
                self.vwap_data.clear()
                self.tick_buffer.clear()
                self.trade_buffer.clear()
                self.profile_cache.clear()

            self.logger.info("Volume profile analyzer cleanup completed")

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'cleanup'
            })

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def get_volume_profile_analyzer(config: dict | None = None) -> VolumeProfileAnalyzer:
    """
    Get singleton instance of volume profile analyzer.

    Args:
        config: Optional configuration dictionary

    Returns:
        VolumeProfileAnalyzer instance
    """
    global _volume_analyzer_instance
    if _volume_analyzer_instance is None:
        _volume_analyzer_instance = VolumeProfileAnalyzer(config)
    return _volume_analyzer_instance

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Global instance
_volume_analyzer_instance: VolumeProfileAnalyzer | None = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code

    analyzer = VolumeProfileAnalyzer()

    if analyzer.initialize():

        # Start analysis
        analyzer.start_analysis()

        # Simulate some tick data
        import random
        base_price = 450.0

        for _i in range(100):
            # Generate synthetic tick
            price = base_price + random.normalvariate(0, 1.0)
            size = random.randint(100, 10000)

            tick = MarketTick(
                symbol="SPY",
                price=price,
                size=size,
                timestamp=datetime.now(),
                bid=price - 0.01,
                ask=price + 0.01,
                volume=size
            )

            analyzer._process_tick(tick)

        # Wait for analysis
        time.sleep(2)  # thread-safe: time.sleep() intentional

        # Get results
        profile = analyzer.get_current_profile()
        if profile:
            pass

        nodes = analyzer.get_volume_nodes()
        for _node in nodes[:5]:  # Show first 5
            pass

        vwap = analyzer.get_vwap_data(20)
        if vwap:
            pass

        flow = analyzer.get_institutional_flow()
        if flow:
            pass

        # Cleanup
        analyzer.cleanup()

    else:
        pass
