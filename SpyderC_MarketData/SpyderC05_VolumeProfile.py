#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderC05_VolumeProfile.py
Group: C (Market Data)
Purpose: Volume profile and liquidity analysis

Description:
    This module analyzes volume profiles and liquidity patterns for the Spyder trading
    system. It tracks volume at price levels, identifies high volume nodes (HVN) and
    low volume nodes (LVN), calculates VWAP, and monitors liquidity conditions. This
    information is crucial for identifying support/resistance levels and optimal entry/exit points.

Author: Mohamed Talib
Date: 2025-05-29
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import threading
import datetime
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict, deque
import bisect
import numpy as np

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
from scipy.stats import gaussian_kde
from ibapi.contract import Contract

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient
from SpyderC_MarketData.SpyderC01_DataFeed import DataFeedManager

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Volume profile parameters
PRICE_BUCKET_SIZE = 0.10  # $0.10 price buckets for SPY
VOLUME_PROFILE_WINDOW = 390  # Minutes in regular trading day
MIN_VOLUME_FOR_NODE = 100000  # Minimum volume to consider a price level
HVN_PERCENTILE = 70  # High Volume Node threshold (70th percentile)
LVN_PERCENTILE = 30  # Low Volume Node threshold (30th percentile)

# Update intervals
PROFILE_UPDATE_INTERVAL = 30  # seconds
VWAP_UPDATE_INTERVAL = 5  # seconds

# Liquidity thresholds
MIN_BID_ASK_SIZE = 100  # Minimum bid/ask size for liquidity
MAX_SPREAD_PERCENT = 0.02  # 2% maximum spread for liquid market

# ==============================================================================
# ENUMS
# ==============================================================================
class VolumeNodeType(Enum):
    """Volume node types"""
    HVN = "high_volume_node"  # High Volume Node (support/resistance)
    LVN = "low_volume_node"   # Low Volume Node (potential breakout)
    POC = "point_of_control"  # Point of Control (most volume)
    VAH = "value_area_high"   # Value Area High
    VAL = "value_area_low"    # Value Area Low

class LiquidityCondition(Enum):
    """Market liquidity conditions"""
    HIGH = "high_liquidity"
    NORMAL = "normal_liquidity"
    LOW = "low_liquidity"
    VERY_LOW = "very_low_liquidity"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class PriceLevel:
    """Volume at a specific price level"""
    price: float
    volume: int = 0
    buy_volume: int = 0
    sell_volume: int = 0
    trades: int = 0
    
    @property
    def net_volume(self) -> int:
        """Net buying/selling pressure"""
        return self.buy_volume - self.sell_volume
    
    @property
    def volume_ratio(self) -> float:
        """Buy/sell volume ratio"""
        if self.sell_volume > 0:
            return self.buy_volume / self.sell_volume
        return float('inf') if self.buy_volume > 0 else 1.0

class VolumeProfile:
    """Complete volume profile for a period"""
    start_time: datetime.datetime
    end_time: datetime.datetime
    price_levels: Dict[float, PriceLevel]
    total_volume: int = 0
    
    # Key levels
    poc: Optional[float] = None  # Point of Control
    vah: Optional[float] = None  # Value Area High
    val: Optional[float] = None  # Value Area Low
    
    # Statistics
    volume_weighted_price: float = 0.0
    average_trade_size: float = 0.0
    
    def calculate_key_levels(self, value_area_percent: float = 0.70) -> None:
        """Calculate POC, VAH, VAL"""
        if not self.price_levels:
            return
        
        # Sort price levels by volume
        sorted_levels = sorted(
            self.price_levels.items(),
            key=lambda x: x[1].volume,
            reverse=True
        )
        
        # POC is highest volume level
        if sorted_levels:
            self.poc = sorted_levels[0][0]
        
        # Calculate value area (70% of volume)
        value_area_volume = self.total_volume * value_area_percent
        cumulative_volume = 0
        value_area_prices = []
        
        for price, level in sorted_levels:
            cumulative_volume += level.volume
            value_area_prices.append(price)
            if cumulative_volume >= value_area_volume:
                break
        
        if value_area_prices:
            self.vah = max(value_area_prices)
            self.val = min(value_area_prices)
    
    def get_volume_nodes(self) -> Dict[VolumeNodeType, List[float]]:
        """Identify volume nodes (HVN, LVN)"""
        if not self.price_levels:
            return {}
        
        volumes = [level.volume for level in self.price_levels.values()]
        if not volumes:
            return {}
        
        # Calculate percentiles
        hvn_threshold = np.percentile(volumes, HVN_PERCENTILE)
        lvn_threshold = np.percentile(volumes, LVN_PERCENTILE)
        
        nodes = {
            VolumeNodeType.HVN: [],
            VolumeNodeType.LVN: [],
            VolumeNodeType.POC: [],
            VolumeNodeType.VAH: [],
            VolumeNodeType.VAL: []
        }
        
        # Classify nodes
        for price, level in self.price_levels.items():
            if level.volume >= hvn_threshold:
                nodes[VolumeNodeType.HVN].append(price)
            elif level.volume <= lvn_threshold and level.volume > 0:
                nodes[VolumeNodeType.LVN].append(price)
        
        # Add key levels
        if self.poc:
            nodes[VolumeNodeType.POC].append(self.poc)
        if self.vah:
            nodes[VolumeNodeType.VAH].append(self.vah)
        if self.val:
            nodes[VolumeNodeType.VAL].append(self.val)
        
        return nodes

class VWAPData:
    """Volume Weighted Average Price data"""
    timestamp: datetime.datetime
    vwap: float
    upper_band: float  # VWAP + n*std
    lower_band: float  # VWAP - n*std
    cumulative_volume: int
    cumulative_pv: float  # Price * Volume
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'vwap': self.vwap,
            'upper_band': self.upper_band,
            'lower_band': self.lower_band,
            'volume': self.cumulative_volume
        }

class LiquiditySnapshot:
    """Market liquidity snapshot"""
    timestamp: datetime.datetime
    bid_size: int
    ask_size: int
    spread: float
    spread_percent: float
    avg_trade_size: float
    trades_per_minute: int
    liquidity_score: float  # 0-100
    condition: LiquidityCondition

# ==============================================================================
# VOLUME PROFILE MANAGER CLASS
# ==============================================================================
class VolumeProfileManager:
    """
    Manages volume profile and liquidity analysis.
    
    Features:
    - Real-time volume profile construction
    - High/Low volume node identification
    - VWAP calculation with bands
    - Liquidity monitoring
    - Delta volume analysis
    - Market profile visualization data
    """
    
    def __init__(
        self,
        ib_client: IBClient,
        event_manager: EventManager,
        data_feed: DataFeedManager
    ):
        """
        Initialize volume profile manager.
        
        Args:
            ib_client: IB client instance
            event_manager: Event manager instance
            data_feed: Data feed manager instance
        """
        self.ib_client = ib_client
        self.event_manager = event_manager
        self.data_feed = data_feed
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Trading calendar
        self.calendar = TradingCalendar()
        
        # Volume profiles
        self.current_profile: Optional[VolumeProfile] = None
        self.historical_profiles: deque = deque(maxlen=20)  # Keep 20 days
        
        # VWAP tracking
        self.vwap_data: deque = deque(maxlen=VOLUME_PROFILE_WINDOW)
        self.current_vwap = VWAPData(
            timestamp=datetime.datetime.now(),
            vwap=0.0,
            upper_band=0.0,
            lower_band=0.0,
            cumulative_volume=0,
            cumulative_pv=0.0
        )
        
        # Liquidity tracking
        self.liquidity_snapshots: deque = deque(maxlen=120)  # 10 minutes
        self.current_liquidity = LiquiditySnapshot(
            timestamp=datetime.datetime.now(),
            bid_size=0,
            ask_size=0,
            spread=0.0,
            spread_percent=0.0,
            avg_trade_size=0.0,
            trades_per_minute=0,
            liquidity_score=50.0,
            condition=LiquidityCondition.NORMAL
        )
        
        # Trade tracking
        self.recent_trades: deque = deque(maxlen=1000)
        self._trade_lock = threading.RLock()
        
        # Update threads
        self._profile_thread: Optional[threading.Thread] = None
        self._vwap_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Subscribe to market data events
        self._subscribe_to_events()
        
        self.logger.info("VolumeProfileManager initialized")
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> None:
        """Start volume profile tracking"""
        if self._running:
            return
        
        self._running = True
        
        # Initialize new profile
        self._initialize_daily_profile()
        
        # Start update threads
        self._profile_thread = threading.Thread(
            target=self._profile_update_loop,
            daemon=True,
            name="VolumeProfileUpdater"
        )
        self._profile_thread.start()
        
        self._vwap_thread = threading.Thread(
            target=self._vwap_update_loop,
            daemon=True,
            name="VWAPUpdater"
        )
        self._vwap_thread.start()
        
        self.logger.info("Volume profile tracking started")
    
    def stop(self) -> None:
        """Stop volume profile tracking"""
        self._running = False
        
        # Save current profile
        if self.current_profile:
            self._save_profile(self.current_profile)
        
        # Wait for threads
        if self._profile_thread:
            self._profile_thread.join(timeout=5.0)
        if self._vwap_thread:
            self._vwap_thread.join(timeout=5.0)
        
        self.logger.info("Volume profile tracking stopped")
    
    # ==========================================================================
    # PROFILE MANAGEMENT
    # ==========================================================================
    def _initialize_daily_profile(self) -> None:
        """Initialize new daily volume profile"""
        now = datetime.datetime.now()
        
        # Save previous profile if exists
        if self.current_profile:
            self._save_profile(self.current_profile)
        
        # Create new profile
        self.current_profile = VolumeProfile(
            start_time=now.replace(hour=9, minute=30, second=0, microsecond=0),
            end_time=now.replace(hour=16, minute=0, second=0, microsecond=0),
            price_levels={}
        )
        
        # Reset VWAP
        self.current_vwap = VWAPData(
            timestamp=now,
            vwap=0.0,
            upper_band=0.0,
            lower_band=0.0,
            cumulative_volume=0,
            cumulative_pv=0.0
        )
        self.vwap_data.clear()
        
        self.logger.info("Initialized new daily volume profile")
    
    def _save_profile(self, profile: VolumeProfile) -> None:
        """Save completed profile"""
        profile.calculate_key_levels()
        self.historical_profiles.append(profile)
        
        # Emit profile complete event
        self.event_manager.emit(Event(
            EventType.MARKET_DATA,
            {
                'type': 'volume_profile_complete',
                'date': profile.start_time.date().isoformat(),
                'total_volume': profile.total_volume,
                'poc': profile.poc,
                'vah': profile.vah,
                'val': profile.val
            }
        ))
    
    def _get_price_bucket(self, price: float) -> float:
        """Round price to nearest bucket"""
        return round(price / PRICE_BUCKET_SIZE) * PRICE_BUCKET_SIZE
    
    # ==========================================================================
    # TRADE PROCESSING
    # ==========================================================================
    def _process_trade(self, symbol: str, price: float, size: int, is_buy: bool) -> None:
        """Process individual trade for volume profile"""
        if symbol != "SPY" or not self.current_profile:
            return
        
        with self._trade_lock:
            # Get price bucket
            bucket_price = self._get_price_bucket(price)
            
            # Update or create price level
            if bucket_price not in self.current_profile.price_levels:
                self.current_profile.price_levels[bucket_price] = PriceLevel(price=bucket_price)
            
            level = self.current_profile.price_levels[bucket_price]
            level.volume += size
            level.trades += 1
            
            if is_buy:
                level.buy_volume += size
            else:
                level.sell_volume += size
            
            # Update totals
            self.current_profile.total_volume += size
            
            # Track recent trades
            self.recent_trades.append({
                'timestamp': datetime.datetime.now(),
                'price': price,
                'size': size,
                'is_buy': is_buy
            })
    
    # ==========================================================================
    # UPDATE LOOPS
    # ==========================================================================
    def _profile_update_loop(self) -> None:
        """Update volume profile periodically"""
        while self._running:
            try:
                # Check if new day
                if self._is_new_trading_day():
                    self._initialize_daily_profile()
                
                # Update profile calculations
                if self.current_profile:
                    self.current_profile.calculate_key_levels()
                    
                    # Calculate volume-weighted price
                    total_pv = sum(
                        price * level.volume 
                        for price, level in self.current_profile.price_levels.items()
                    )
                    if self.current_profile.total_volume > 0:
                        self.current_profile.volume_weighted_price = (
                            total_pv / self.current_profile.total_volume
                        )
                    
                    # Emit update
                    self._emit_profile_update()
                
                # Update liquidity
                self._update_liquidity()
                
                time.sleep(PROFILE_UPDATE_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Error in profile update loop: {e}")
    
    def _vwap_update_loop(self) -> None:
        """Update VWAP calculations"""
        while self._running:
            try:
                self._calculate_vwap()
                time.sleep(VWAP_UPDATE_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Error in VWAP update loop: {e}")
    
    def _calculate_vwap(self) -> None:
        """Calculate current VWAP with bands"""
        with self._trade_lock:
            if not self.recent_trades:
                return
            
            # Get recent trades (last minute)
            cutoff_time = datetime.datetime.now() - datetime.timedelta(minutes=1)
            recent = [t for t in self.recent_trades if t['timestamp'] > cutoff_time]
            
            if recent:
                # Update cumulative values
                for trade in recent:
                    self.current_vwap.cumulative_volume += trade['size']
                    self.current_vwap.cumulative_pv += trade['price'] * trade['size']
                
                # Calculate VWAP
                if self.current_vwap.cumulative_volume > 0:
                    vwap = self.current_vwap.cumulative_pv / self.current_vwap.cumulative_volume
                    self.current_vwap.vwap = vwap
                    
                    # Calculate standard deviation for bands
                    prices = [t['price'] for t in recent]
                    if len(prices) > 1:
                        std_dev = np.std(prices)
                        self.current_vwap.upper_band = vwap + 2 * std_dev
                        self.current_vwap.lower_band = vwap - 2 * std_dev
                
                self.current_vwap.timestamp = datetime.datetime.now()
                
                # Store VWAP data point
                self.vwap_data.append(self.current_vwap)
                
                # Emit VWAP update
                self.event_manager.emit(Event(
                    EventType.MARKET_DATA,
                    {
                        'type': 'vwap_update',
                        'vwap': self.current_vwap.vwap,
                        'upper_band': self.current_vwap.upper_band,
                        'lower_band': self.current_vwap.lower_band,
                        'volume': self.current_vwap.cumulative_volume
                    }
                ))
    
    def _update_liquidity(self) -> None:
        """Update liquidity metrics"""
        # Get current market data from data feed
        market_data = self.data_feed.get_market_data("SPY")
        if not market_data:
            return
        
        # Calculate metrics
        bid_size = market_data.get('bid_size', 0)
        ask_size = market_data.get('ask_size', 0)
        bid = market_data.get('bid', 0)
        ask = market_data.get('ask', 0)
        
        spread = ask - bid if ask > 0 and bid > 0 else 0
        spread_percent = spread / bid * 100 if bid > 0 else 0
        
        # Calculate average trade size
        with self._trade_lock:
            if self.recent_trades:
                recent_sizes = [t['size'] for t in list(self.recent_trades)[-100:]]
                avg_trade_size = np.mean(recent_sizes)
            else:
                avg_trade_size = 0
            
            # Trades per minute
            cutoff_time = datetime.datetime.now() - datetime.timedelta(minutes=1)
            trades_per_minute = sum(
                1 for t in self.recent_trades 
                if t['timestamp'] > cutoff_time
            )
        
        # Calculate liquidity score (0-100)
        liquidity_score = self._calculate_liquidity_score(
            bid_size, ask_size, spread_percent, trades_per_minute
        )
        
        # Determine condition
        if liquidity_score >= 80:
            condition = LiquidityCondition.HIGH
        elif liquidity_score >= 50:
            condition = LiquidityCondition.NORMAL
        elif liquidity_score >= 20:
            condition = LiquidityCondition.LOW
        else:
            condition = LiquidityCondition.VERY_LOW
        
        # Create snapshot
        self.current_liquidity = LiquiditySnapshot(
            timestamp=datetime.datetime.now(),
            bid_size=bid_size,
            ask_size=ask_size,
            spread=spread,
            spread_percent=spread_percent,
            avg_trade_size=avg_trade_size,
            trades_per_minute=trades_per_minute,
            liquidity_score=liquidity_score,
            condition=condition
        )
        
        self.liquidity_snapshots.append(self.current_liquidity)
    
    def _calculate_liquidity_score(
        self,
        bid_size: int,
        ask_size: int,
        spread_percent: float,
        trades_per_minute: int
    ) -> float:
        """Calculate liquidity score (0-100)"""
        score = 0.0
        
        # Size component (40%)
        total_size = bid_size + ask_size
        if total_size >= 1000:
            score += 40
        elif total_size >= 500:
            score += 30
        elif total_size >= 100:
            score += 20
        else:
            score += 10
        
        # Spread component (30%)
        if spread_percent <= 0.01:  # 1 basis point
            score += 30
        elif spread_percent <= 0.02:
            score += 20
        elif spread_percent <= 0.05:
            score += 10
        else:
            score += 5
        
        # Activity component (30%)
        if trades_per_minute >= 100:
            score += 30
        elif trades_per_minute >= 50:
            score += 20
        elif trades_per_minute >= 20:
            score += 10
        else:
            score += 5
        
        return min(100, score)
    
    # ==========================================================================
    # EVENT HANDLING
    # ==========================================================================
    def _subscribe_to_events(self) -> None:
        """Subscribe to relevant market data events"""
        self.event_manager.subscribe(
            self._on_market_data_event,
            [EventType.TRADE, EventType.QUOTE]
        )
    
    def _on_market_data_event(self, event: Event) -> None:
        """Handle market data events"""
        if event.type == EventType.TRADE:
            # Process trade for volume profile
            data = event.data
            self._process_trade(
                symbol=data.get('symbol', ''),
                price=data.get('price', 0),
                size=data.get('size', 0),
                is_buy=data.get('is_buy', True)
            )
    
    def _emit_profile_update(self) -> None:
        """Emit volume profile update event"""
        if not self.current_profile:
            return
        
        nodes = self.current_profile.get_volume_nodes()
        
        self.event_manager.emit(Event(
            EventType.MARKET_DATA,
            {
                'type': 'volume_profile_update',
                'total_volume': self.current_profile.total_volume,
                'poc': self.current_profile.poc,
                'vah': self.current_profile.vah,
                'val': self.current_profile.val,
                'hvn_levels': nodes.get(VolumeNodeType.HVN, []),
                'lvn_levels': nodes.get(VolumeNodeType.LVN, [])
            }
        ))
    
    # ==========================================================================
    # QUERIES
    # ==========================================================================
    def get_current_profile(self) -> Optional[VolumeProfile]:
        """Get current volume profile"""
        return self.current_profile
    
    def get_volume_at_price(self, price: float) -> Optional[PriceLevel]:
        """Get volume data at specific price level"""
        if not self.current_profile:
            return None
        
        bucket_price = self._get_price_bucket(price)
        return self.current_profile.price_levels.get(bucket_price)
    
    def get_key_levels(self) -> Dict[str, Optional[float]]:
        """Get key price levels (POC, VAH, VAL)"""
        if not self.current_profile:
            return {'poc': None, 'vah': None, 'val': None}
        
        return {
            'poc': self.current_profile.poc,
            'vah': self.current_profile.vah,
            'val': self.current_profile.val
        }
    
    def get_volume_nodes(self) -> Dict[VolumeNodeType, List[float]]:
        """Get all volume nodes"""
        if not self.current_profile:
            return {}
        
        return self.current_profile.get_volume_nodes()
    
    def get_current_vwap(self) -> VWAPData:
        """Get current VWAP data"""
        return self.current_vwap
    
    def get_vwap_history(self, minutes: int = 30) -> pd.DataFrame:
        """Get VWAP history as DataFrame"""
        if not self.vwap_data:
            return pd.DataFrame()
        
        cutoff_time = datetime.datetime.now() - datetime.timedelta(minutes=minutes)
        data = [
            vwap.to_dict() 
            for vwap in self.vwap_data 
            if vwap.timestamp >= cutoff_time
        ]
        
        if data:
            df = pd.DataFrame(data)
            df.set_index('timestamp', inplace=True)
            return df
        
        return pd.DataFrame()
    
    def get_liquidity_condition(self) -> LiquidityCondition:
        """Get current liquidity condition"""
        return self.current_liquidity.condition
    
    def get_liquidity_score(self) -> float:
        """Get current liquidity score"""
        return self.current_liquidity.liquidity_score
    
    def get_delta_volume(self) -> Dict[str, Any]:
        """Get buy/sell volume delta analysis"""
        if not self.current_profile:
            return {}
        
        total_buy = sum(
            level.buy_volume 
            for level in self.current_profile.price_levels.values()
        )
        total_sell = sum(
            level.sell_volume 
            for level in self.current_profile.price_levels.values()
        )
        
        return {
            'buy_volume': total_buy,
            'sell_volume': total_sell,
            'net_volume': total_buy - total_sell,
            'buy_ratio': total_buy / (total_buy + total_sell) if (total_buy + total_sell) > 0 else 0.5
        }
    
    def export_profile_data(self) -> pd.DataFrame:
        """Export current profile to DataFrame"""
        if not self.current_profile:
            return pd.DataFrame()
        
        data = []
        for price, level in sorted(self.current_profile.price_levels.items()):
            data.append({
                'price': price,
                'volume': level.volume,
                'buy_volume': level.buy_volume,
                'sell_volume': level.sell_volume,
                'net_volume': level.net_volume,
                'trades': level.trades
            })
        
        if data:
            return pd.DataFrame(data)
        
        return pd.DataFrame()
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def _is_new_trading_day(self) -> bool:
        """Check if it's a new trading day"""
        if not self.current_profile:
            return True
        
        now = datetime.datetime.now()
        return (self.calendar.is_trading_day(now.date()) and 
                now.date() != self.current_profile.start_time.date())

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test volume profile manager
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    from SpyderC_MarketData.SpyderC01_DataFeed import DataFeedManager
    
    # Mock IB client
    class MockIBClient:
        pass
    
    # Mock data feed
    class MockDataFeed:
        def get_market_data(self, symbol):
            return {
                'bid': 450.00,
                'ask': 450.02,
                'bid_size': 500,
                'ask_size': 600,
                'last': 450.01,
                'volume': 1000000
            }
    
    # Initialize
    event_manager = EventManager()
    ib_client = MockIBClient()
    data_feed = MockDataFeed()
    
    volume_manager = VolumeProfileManager(ib_client, event_manager, data_feed)
    
    # Start manager
    volume_manager.start()
    
    # Simulate some trades
    print("Simulating trades...")
    import random
    
    for i in range(50):
        price = 450.0 + random.uniform(-1, 1)
        size = random.randint(100, 1000)
        is_buy = random.random() > 0.5
        
        volume_manager._process_trade("SPY", price, size, is_buy)
    
    # Wait for calculations
    time.sleep(2)
    
    # Get key levels
    print("\nKey Levels:")
    levels = volume_manager.get_key_levels()
    for key, value in levels.items():
        print(f"  {key.upper()}: ${value:.2f}" if value else f"  {key.upper()}: N/A")
    
    # Get volume nodes
    print("\nVolume Nodes:")
    nodes = volume_manager.get_volume_nodes()
    for node_type, prices in nodes.items():
        if prices:
            print(f"  {node_type.value}: {[f'${p:.2f}' for p in prices[:3]]}")
    
    # Get VWAP
    vwap = volume_manager.get_current_vwap()
    print(f"\nVWAP: ${vwap.vwap:.2f}")
    print(f"  Upper Band: ${vwap.upper_band:.2f}")
    print(f"  Lower Band: ${vwap.lower_band:.2f}")
    
    # Get liquidity
    print(f"\nLiquidity:")
    print(f"  Score: {volume_manager.get_liquidity_score():.1f}/100")
    print(f"  Condition: {volume_manager.get_liquidity_condition().value}")
    
    # Get delta volume
    print("\nDelta Volume Analysis:")
    delta = volume_manager.get_delta_volume()
    for key, value in delta.items():
        print(f"  {key}: {value:,.0f}" if isinstance(value, (int, float)) else f"  {key}: {value}")
    
    # Export profile data
    print("\nVolume Profile Data:")
    df = volume_manager.export_profile_data()
    if not df.empty:
        print(df.head(10))
    
    # Stop manager
    volume_manager.stop()