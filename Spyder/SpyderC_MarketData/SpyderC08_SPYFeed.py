#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC08_SPYFeed.py
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
import os
import sys
from typing import Dict, List, Optional, Any, Tuple, Deque
from dataclasses import dataclass, field
from enum import Enum
import json
from datetime import datetime, timedelta
import threading
import time
from collections import deque, defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import statistics
import bisect
import pandas as pd
import numpy as np
from scipy import stats

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderA_Core.SpyderA05_EventManager import Event, EventType, EventBus

SPY_SYMBOL = "SPY"

# Trade sizes
RETAIL_SIZE = 100
INSTITUTIONAL_SIZE = 10000
BLOCK_SIZE = 50000

# Time windows
TICK_WINDOW = 100  # Number of ticks to keep
TIME_WINDOW_1MIN = 60
TIME_WINDOW_5MIN = 300
TIME_WINDOW_15MIN = 900

# Market hours
MARKET_OPEN = "09:30"
MARKET_CLOSE = "16:00"
PRE_MARKET_OPEN = "04:00"
AFTER_MARKET_CLOSE = "20:00"

# Thresholds
SPREAD_ALERT_THRESHOLD = 0.05  # $0.05 spread alert
VOLUME_SPIKE_THRESHOLD = 3.0  # 3x average volume
PRICE_SPIKE_THRESHOLD = 0.002  # 0.2% price spike

# ==============================================================================
# ENUMS
# ==============================================================================
class TickType(Enum):
    """Type of tick data"""
    TRADE = "trade"
    BID = "bid"
    ASK = "ask"
    QUOTE = "quote"

class TradeDirection(Enum):
    """Trade direction classification"""
    BUY = "buy"
    SELL = "sell"
    NEUTRAL = "neutral"

class MarketSession(Enum):
    """Market session type"""
    PRE_MARKET = "pre_market"
    REGULAR = "regular"
    AFTER_HOURS = "after_hours"
    CLOSED = "closed"

class OrderFlowType(Enum):
    """Order flow classification"""
    RETAIL_BUY = "retail_buy"
    RETAIL_SELL = "retail_sell"
    INSTITUTIONAL_BUY = "institutional_buy"
    INSTITUTIONAL_SELL = "institutional_sell"
    BLOCK_BUY = "block_buy"
    BLOCK_SELL = "block_sell"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class TickData:
    """Individual tick data"""
    timestamp: datetime
    tick_type: TickType
    price: float
    size: int
    bid: float = 0.0
    ask: float = 0.0
    bid_size: int = 0
    ask_size: int = 0
    exchange: str = ""
    conditions: List[str] = field(default_factory=list)
    
@dataclass
class Level2Data:
    """Level 2 market depth data"""
    timestamp: datetime
    bids: List[Tuple[float, int, str]]  # (price, size, exchange)
    asks: List[Tuple[float, int, str]]  # (price, size, exchange)
    
@dataclass
class TradeData:
    """Processed trade data"""
    timestamp: datetime
    price: float
    size: int
    direction: TradeDirection
    flow_type: OrderFlowType
    vwap_deviation: float
    spread_at_trade: float
    liquidity_score: float
    
@dataclass
class MarketMicrostructure:
    """Market microstructure metrics"""
    timestamp: datetime
    bid_ask_spread: float
    spread_percentage: float
    bid_depth: int
    ask_depth: int
    order_imbalance: float
    liquidity_score: float
    volatility: float
    tick_direction: int  # -1, 0, 1
    
@dataclass
class SPYAnalysis:
    """Comprehensive SPY analysis"""
    timestamp: datetime
    last_price: float
    vwap: Dict[str, float]  # Multiple timeframes
    volume: Dict[str, int]  # Multiple timeframes
    trade_count: Dict[str, int]
    buy_volume: int
    sell_volume: int
    order_flow_score: float  # -1 to 1
    momentum_score: float
    liquidity_score: float
    microstructure: MarketMicrostructure
    trend: str  # "bullish", "bearish", "neutral"
    volatility_regime: str  # "low", "normal", "high", "extreme"
    signals: List[Dict[str, Any]]
    
# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SPYFeedProcessor:
    """
    High-frequency SPY data processor with microstructure analysis.
    
    This class processes real-time SPY tick data, analyzes market microstructure,
    tracks order flow, and generates trading signals based on market dynamics.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        event_bus: Event management system
        tick_buffer: Buffer for recent ticks
        trades_buffer: Buffer for processed trades
        
    Example:
        >>> processor = SPYFeedProcessor()
        >>> processor.initialize()
        >>> processor.process_tick(tick_data)
    """
    
    def __init__(self):
        """Initialize the SPY feed processor."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_bus = EventBus()
        
        # Data buffers
        self.tick_buffer: Deque[TickData] = deque(maxlen=10000)
        self.trades_buffer: Deque[TradeData] = deque(maxlen=5000)
        self.level2_history: Deque[Level2Data] = deque(maxlen=1000)
        
        # Current state
        self.current_bid = 0.0
        self.current_ask = 0.0
        self.current_price = 0.0
        self.current_level2: Optional[Level2Data] = None
        
        # VWAP tracking
        self.vwap_calculators = {
            '1min': VWAPCalculator(TIME_WINDOW_1MIN),
            '5min': VWAPCalculator(TIME_WINDOW_5MIN),
            '15min': VWAPCalculator(TIME_WINDOW_15MIN)
        }
        
        # Volume tracking
        self.volume_tracker = VolumeTracker()
        self.flow_analyzer = OrderFlowAnalyzer()
        
        # Analysis state
        self.current_analysis: Optional[SPYAnalysis] = None
        self.microstructure_history: Deque[MarketMicrostructure] = deque(maxlen=1000)
        
        # Statistics
        self.stats = {
            'ticks_processed': 0,
            'trades_processed': 0,
            'errors': 0,
            'last_update': datetime.now()
        }
        
        # Control flags
        self.is_running = False
        self.analysis_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
        # Callbacks
        self.tick_callbacks: List[callable] = []
        self.analysis_callbacks: List[callable] = []
        
        self.logger.info("SPYFeedProcessor initialized")
        
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize SPY feed processing.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing SPY feed processor")
            
            # Subscribe to events
            self.event_bus.subscribe(EventType.MARKET_DATA, self._handle_market_data)
            self.event_bus.subscribe(EventType.LEVEL2_DATA, self._handle_level2_data)
            
            # Start processing
            self.start()
            
            self.logger.info("SPY feed processor initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            return False
            
    def start(self) -> None:
        """Start feed processing."""
        if not self.is_running:
            self.is_running = True
            
            # Start analysis thread
            self.analysis_thread = threading.Thread(
                target=self._analysis_loop,
                daemon=True
            )
            self.analysis_thread.start()
            
            self.logger.info("SPY feed processing started")
            
    def stop(self) -> None:
        """Stop feed processing."""
        self.is_running = False
        if self.analysis_thread:
            self.analysis_thread.join(timeout=5)
        self.logger.info("SPY feed processing stopped")
        
    def process_tick(self, tick: TickData) -> None:
        """
        Process incoming tick data.
        
        Args:
            tick: Tick data to process
        """
        with self.lock:
            # Add to buffer
            self.tick_buffer.append(tick)
            self.stats['ticks_processed'] += 1
            
            # Update current state
            if tick.tick_type == TickerField.TRADE:
                self.current_price = tick.price
                self._process_trade(tick)
            elif tick.tick_type == TickerField.BID:
                self.current_bid = tick.price
            elif tick.tick_type == TickerField.ASK:
                self.current_ask = tick.price
                
            # Update VWAP
            if tick.tick_type == TickerField.TRADE:
                for vwap in self.vwap_calculators.values():
                    vwap.add_trade(tick.price, tick.size, tick.timestamp)
                    
            # Notify callbacks
            for callback in self.tick_callbacks:
                try:
                    callback(tick)
                except Exception as e:
                    self.logger.error(f"Tick callback error: {e}")
                    
    def process_level2(self, level2: Level2Data) -> None:
        """
        Process Level 2 market depth data.
        
        Args:
            level2: Level 2 data
        """
        with self.lock:
            self.current_level2 = level2
            self.level2_history.append(level2)
            
            # Update best bid/ask
            if level2.bids:
                self.current_bid = level2.bids[0][0]
            if level2.asks:
                self.current_ask = level2.asks[0][0]
                
    def get_current_analysis(self) -> Optional[SPYAnalysis]:
        """
        Get current SPY analysis.
        
        Returns:
            Current analysis or None
        """
        return self.current_analysis
        
    def get_market_session(self) -> MarketSession:
        """
        Get current market session.
        
        Returns:
            Current market session
        """
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        
        if current_time < PRE_MARKET_OPEN:
            return MarketSession.CLOSED
        elif current_time < MARKET_OPEN:
            return MarketSession.PRE_MARKET
        elif current_time < MARKET_CLOSE:
            return MarketSession.REGULAR
        elif current_time < AFTER_MARKET_CLOSE:
            return MarketSession.AFTER_HOURS
        else:
            return MarketSession.CLOSED
            
    def register_tick_callback(self, callback: callable) -> None:
        """Register callback for tick updates."""
        self.tick_callbacks.append(callback)
        
    def register_analysis_callback(self, callback: callable) -> None:
        """Register callback for analysis updates."""
        self.analysis_callbacks.append(callback)
        
    # ==========================================================================
    # PROCESSING METHODS
    # ==========================================================================
    def _process_trade(self, tick: TickData) -> None:
        """Process trade tick."""
        try:
            # Classify trade direction
            direction = self._classify_trade_direction(
                tick.price, 
                self.current_bid, 
                self.current_ask
            )
            
            # Classify order flow
            flow_type = self._classify_order_flow(tick.size, direction)
            
            # Calculate metrics
            spread = self.current_ask - self.current_bid if self.current_ask > 0 else 0
            vwap_1min = self.vwap_calculators['1min'].get_vwap()
            vwap_deviation = (tick.price - vwap_1min) / vwap_1min if vwap_1min > 0 else 0
            
            # Calculate liquidity score
            liquidity_score = self._calculate_liquidity_score()
            
            # Create trade data
            trade = TradeData(
                timestamp=tick.timestamp,
                price=tick.price,
                size=tick.size,
                direction=direction,
                flow_type=flow_type,
                vwap_deviation=vwap_deviation,
                spread_at_trade=spread,
                liquidity_score=liquidity_score
            )
            
            # Add to buffer
            self.trades_buffer.append(trade)
            self.stats['trades_processed'] += 1
            
            # Update trackers
            self.volume_tracker.add_trade(trade)
            self.flow_analyzer.add_trade(trade)
            
        except Exception as e:
            self.logger.error(f"Error processing trade: {e}")
            self.stats['errors'] += 1
            
    def _classify_trade_direction(self, price: float, bid: float, ask: float) -> TradeDirection:
        """Classify trade direction based on price vs bid/ask."""
        if bid <= 0 or ask <= 0:
            return TradeDirection.NEUTRAL
            
        mid = (bid + ask) / 2
        
        if price >= ask:
            return TradeDirection.BUY
        elif price <= bid:
            return TradeDirection.SELL
        elif price > mid:
            return TradeDirection.BUY
        elif price < mid:
            return TradeDirection.SELL
        else:
            return TradeDirection.NEUTRAL
            
    def _classify_order_flow(self, size: int, direction: TradeDirection) -> OrderFlowType:
        """Classify order flow based on size and direction."""
        if size >= BLOCK_SIZE:
            return OrderFlowType.BLOCK_BUY if direction == TradeDirection.BUY else OrderFlowType.BLOCK_SELL
        elif size >= INSTITUTIONAL_SIZE:
            return OrderFlowType.INSTITUTIONAL_BUY if direction == TradeDirection.BUY else OrderFlowType.INSTITUTIONAL_SELL
        else:
            return OrderFlowType.RETAIL_BUY if direction == TradeDirection.BUY else OrderFlowType.RETAIL_SELL
            
    def _calculate_liquidity_score(self) -> float:
        """Calculate current liquidity score."""
        if not self.current_level2:
            return 0.5
            
        # Calculate bid/ask depth
        bid_depth = sum(size for _, size, _ in self.current_level2.bids[:10])
        ask_depth = sum(size for _, size, _ in self.current_level2.asks[:10])
        total_depth = bid_depth + ask_depth
        
        # Calculate spread
        spread = self.current_ask - self.current_bid if self.current_ask > 0 else 0
        spread_score = 1.0 - min(spread / 0.10, 1.0)  # Lower spread = higher score
        
        # Calculate depth score
        depth_score = min(total_depth / 100000, 1.0)  # More depth = higher score
        
        # Combined score
        liquidity_score = (spread_score * 0.5 + depth_score * 0.5)
        
        return liquidity_score
        
    # ==========================================================================
    # ANALYSIS METHODS
    # ==========================================================================
    def _analysis_loop(self) -> None:
        """Main analysis loop."""
        while self.is_running:
            try:
                # Perform analysis
                analysis = self._perform_analysis()
                if analysis:
                    self.current_analysis = analysis
                    
                    # Notify callbacks
                    for callback in self.analysis_callbacks:
                        try:
                            callback(analysis)
                        except Exception as e:
                            self.logger.error(f"Analysis callback error: {e}")
                            
                    # Publish event
                    event = Event(
                        type=EventType.SPY_ANALYSIS,
                        data={
                            'analysis': analysis,
                            'timestamp': datetime.now()
                        }
                    )
                    self.event_bus.publish(event)
                    
                time.sleep(1)  # Analysis every second
                
            except Exception as e:
                self.logger.error(f"Analysis loop error: {e}")
                time.sleep(1)
                
    def _perform_analysis(self) -> Optional[SPYAnalysis]:
        """Perform comprehensive SPY analysis."""
        try:
            with self.lock:
                # Get microstructure
                microstructure = self._analyze_microstructure()
                if microstructure:
                    self.microstructure_history.append(microstructure)
                    
                # Get VWAP values
                vwap_values = {
                    '1min': self.vwap_calculators['1min'].get_vwap(),
                    '5min': self.vwap_calculators['5min'].get_vwap(),
                    '15min': self.vwap_calculators['15min'].get_vwap()
                }
                
                # Get volume metrics
                volume_metrics = self.volume_tracker.get_metrics()
                flow_metrics = self.flow_analyzer.get_metrics()
                
                # Calculate scores
                order_flow_score = flow_metrics.get('flow_score', 0.0)
                momentum_score = self._calculate_momentum_score()
                liquidity_score = microstructure.liquidity_score if microstructure else 0.5
                
                # Determine trend
                trend = self._determine_trend()
                volatility_regime = self._determine_volatility_regime()
                
                # Generate signals
                signals = self._generate_signals(
                    microstructure,
                    order_flow_score,
                    momentum_score,
                    volatility_regime
                )
                
                # Create analysis
                analysis = SPYAnalysis(
                    timestamp=datetime.now(),
                    last_price=self.current_price,
                    vwap=vwap_values,
                    volume=volume_metrics.get('volume', {}),
                    trade_count=volume_metrics.get('trade_count', {}),
                    buy_volume=flow_metrics.get('buy_volume', 0),
                    sell_volume=flow_metrics.get('sell_volume', 0),
                    order_flow_score=order_flow_score,
                    momentum_score=momentum_score,
                    liquidity_score=liquidity_score,
                    microstructure=microstructure,
                    trend=trend,
                    volatility_regime=volatility_regime,
                    signals=signals
                )
                
                return analysis
                
        except Exception as e:
            self.logger.error(f"Error performing analysis: {e}")
            return None
            
    def _analyze_microstructure(self) -> Optional[MarketMicrostructure]:
        """Analyze market microstructure."""
        try:
            # Calculate spread
            spread = self.current_ask - self.current_bid if self.current_ask > 0 else 0
            spread_pct = spread / self.current_price * 100 if self.current_price > 0 else 0
            
            # Get depth if available
            bid_depth = 0
            ask_depth = 0
            if self.current_level2:
                bid_depth = sum(size for _, size, _ in self.current_level2.bids[:5])
                ask_depth = sum(size for _, size, _ in self.current_level2.asks[:5])
                
            # Calculate order imbalance
            total_depth = bid_depth + ask_depth
            imbalance = (bid_depth - ask_depth) / total_depth if total_depth > 0 else 0
            
            # Calculate volatility (using recent ticks)
            volatility = self._calculate_tick_volatility()
            
            # Calculate tick direction
            tick_direction = 0
            if len(self.tick_buffer) >= 2:
                recent_trades = [t for t in list(self.tick_buffer)[-10:] 
                               if t.tick_type == TickerField.TRADE]
                if len(recent_trades) >= 2:
                    if recent_trades[-1].price > recent_trades[-2].price:
                        tick_direction = 1
                    elif recent_trades[-1].price < recent_trades[-2].price:
                        tick_direction = -1
                        
            # Calculate liquidity score
            liquidity_score = self._calculate_liquidity_score()
            
            return MarketMicrostructure(
                timestamp=datetime.now(),
                bid_ask_spread=spread,
                spread_percentage=spread_pct,
                bid_depth=bid_depth,
                ask_depth=ask_depth,
                order_imbalance=imbalance,
                liquidity_score=liquidity_score,
                volatility=volatility,
                tick_direction=tick_direction
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing microstructure: {e}")
            return None
            
    def _calculate_tick_volatility(self) -> float:
        """Calculate volatility from recent ticks."""
        try:
            recent_trades = [t for t in list(self.tick_buffer)[-100:] 
                           if t.tick_type == TickerField.TRADE]
            
            if len(recent_trades) < 10:
                return 0.0
                
            prices = [t.price for t in recent_trades]
            returns = np.diff(np.log(prices))
            
            if len(returns) > 0:
                return np.std(returns) * np.sqrt(252 * 6.5 * 60 * 60)  # Annualized
            else:
                return 0.0
                
        except Exception as e:
            self.logger.error(f"Error calculating volatility: {e}")
            return 0.0
            
    def _calculate_momentum_score(self) -> float:
        """Calculate momentum score."""
        try:
            if len(self.trades_buffer) < 20:
                return 0.0
                
            recent_trades = list(self.trades_buffer)[-20:]
            
            # Price momentum
            price_start = recent_trades[0].price
            price_end = recent_trades[-1].price
            price_momentum = (price_end - price_start) / price_start
            
            # Volume momentum
            buy_volume = sum(t.size for t in recent_trades if t.direction == TradeDirection.BUY)
            sell_volume = sum(t.size for t in recent_trades if t.direction == TradeDirection.SELL)
            total_volume = buy_volume + sell_volume
            
            volume_momentum = (buy_volume - sell_volume) / total_volume if total_volume > 0 else 0
            
            # Combined momentum
            momentum = (price_momentum * 0.6 + volume_momentum * 0.4)
            
            return np.clip(momentum * 100, -1, 1)
            
        except Exception as e:
            self.logger.error(f"Error calculating momentum: {e}")
            return 0.0
            
    def _determine_trend(self) -> str:
        """Determine current trend."""
        try:
            # Get VWAPs
            vwap_1min = self.vwap_calculators['1min'].get_vwap()
            vwap_5min = self.vwap_calculators['5min'].get_vwap()
            
            if self.current_price <= 0 or vwap_1min <= 0:
                return "neutral"
                
            # Price vs VWAP
            price_vs_vwap1 = (self.current_price - vwap_1min) / vwap_1min
            price_vs_vwap5 = (self.current_price - vwap_5min) / vwap_5min if vwap_5min > 0 else 0
            
            # Momentum
            momentum = self._calculate_momentum_score()
            
            # Determine trend
            if price_vs_vwap1 > 0.001 and price_vs_vwap5 > 0.001 and momentum > 0.2:
                return "bullish"
            elif price_vs_vwap1 < -0.001 and price_vs_vwap5 < -0.001 and momentum < -0.2:
                return "bearish"
            else:
                return "neutral"
                
        except Exception as e:
            self.logger.error(f"Error determining trend: {e}")
            return "neutral"
            
    def _determine_volatility_regime(self) -> str:
        """Determine volatility regime."""
        try:
            volatility = self._calculate_tick_volatility()
            
            if volatility < 0.10:
                return "low"
            elif volatility < 0.15:
                return "normal"
            elif volatility < 0.25:
                return "high"
            else:
                return "extreme"
                
        except Exception as e:
            self.logger.error(f"Error determining volatility: {e}")
            return "normal"
            
    def _generate_signals(self, microstructure: MarketMicrostructure,
                         order_flow: float, momentum: float, 
                         volatility: str) -> List[Dict[str, Any]]:
        """Generate trading signals."""
        signals = []
        
        try:
            # Order flow signal
            if abs(order_flow) > 0.7:
                signals.append({
                    'type': 'order_flow',
                    'direction': 'bullish' if order_flow > 0 else 'bearish',
                    'strength': abs(order_flow),
                    'message': f"Strong {'buying' if order_flow > 0 else 'selling'} pressure"
                })
                
            # Momentum signal
            if abs(momentum) > 0.5:
                signals.append({
                    'type': 'momentum',
                    'direction': 'bullish' if momentum > 0 else 'bearish',
                    'strength': abs(momentum),
                    'message': f"Strong {'upward' if momentum > 0 else 'downward'} momentum"
                })
                
            # Microstructure signals
            if microstructure:
                # Spread signal
                if microstructure.spread_percentage > 0.05:
                    signals.append({
                        'type': 'spread',
                        'direction': 'caution',
                        'strength': 0.5,
                        'message': 'Wide spread - poor liquidity'
                    })
                    
                # Imbalance signal
                if abs(microstructure.order_imbalance) > 0.3:
                    signals.append({
                        'type': 'imbalance',
                        'direction': 'bullish' if microstructure.order_imbalance > 0 else 'bearish',
                        'strength': abs(microstructure.order_imbalance),
                        'message': f"Order book {'skewed to bids' if microstructure.order_imbalance > 0 else 'skewed to asks'}"
                    })
                    
            # Volatility signal
            if volatility in ['high', 'extreme']:
                signals.append({
                    'type': 'volatility',
                    'direction': 'caution',
                    'strength': 0.7 if volatility == 'high' else 1.0,
                    'message': f'{volatility.capitalize()} volatility environment'
                })
                
        except Exception as e:
            self.logger.error(f"Error generating signals: {e}")
            
        return signals
        
    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    def _handle_market_data(self, event: Event) -> None:
        """Handle market data events."""
        try:
            data = event.data
            symbol = data.get('symbol', '')
            
            if symbol == SPY_SYMBOL:
                # Create tick data
                tick = TickData(
                    timestamp=datetime.now(),
                    tick_type=TickerField.TRADE,
                    price=data.get('last', 0),
                    size=data.get('size', 0),
                    bid=data.get('bid', 0),
                    ask=data.get('ask', 0),
                    bid_size=data.get('bid_size', 0),
                    ask_size=data.get('ask_size', 0),
                    exchange=data.get('exchange', ''),
                    conditions=data.get('conditions', [])
                )
                
                self.process_tick(tick)
                
        except Exception as e:
            self.logger.error(f"Error handling market data: {e}")
            
    def _handle_level2_data(self, event: Event) -> None:
        """Handle Level 2 data events."""
        try:
            data = event.data
            symbol = data.get('symbol', '')
            
            if symbol == SPY_SYMBOL:
                level2 = Level2Data(
                    timestamp=datetime.now(),
                    bids=data.get('bids', []),
                    asks=data.get('asks', [])
                )
                
                self.process_level2(level2)
                
        except Exception as e:
            self.logger.error(f"Error handling Level 2: {e}")
