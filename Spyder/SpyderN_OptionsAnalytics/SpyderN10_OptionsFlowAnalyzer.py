#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderN10_OptionsFlowAnalyzer.py
Group: N (Options Analytics)
Purpose: Advanced options flow analysis with unusual activity detection

Description:
    This module provides institutional-grade options flow analysis using real-time
    OPRA data feeds. It detects unusual options activity, identifies smart money
    movements, analyzes order flow sentiment, and generates actionable trading
    signals. The module includes sweep detection, block trade analysis, and
    multi-exchange flow aggregation for comprehensive market intelligence.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-06-28
Last Updated: 2025-06-28 Time: 17:30:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import json
import bisect
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any, Set, Deque
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum, auto
import heapq

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import seaborn as sns
from scipy import stats
from sklearn.ensemble import IsolationForest

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU07_Constants import OptionType, OrderType
from Spyder.SpyderC_MarketData.SpyderC07_OPRAFeed import OPRAFeedHandler
from Spyder.SpyderC_MarketData.SpyderC03_OptionChain import OptionChainManager
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Flow Detection Thresholds
MIN_PREMIUM_VALUE = 25000  # Minimum premium for tracking
BLOCK_TRADE_SIZE = 500  # Minimum contracts for block
SWEEP_TIME_WINDOW = 3  # Seconds to identify sweeps
UNUSUAL_VOLUME_MULTIPLIER = 3  # Times average daily volume
UNUSUAL_OI_RATIO = 0.25  # Volume/OI ratio threshold

# Smart Money Indicators
SMART_MONEY_PREMIUM = 50000  # Minimum for smart money
INSTITUTIONAL_SIZE = 1000  # Institutional block size
REPEAT_TRADER_WINDOW = 300  # 5 minutes for repeat activity

# Flow Aggregation
FLOW_WINDOW_SIZE = 60  # Rolling window in seconds
SENTIMENT_PERIODS = [60, 300, 900, 3600]  # 1min, 5min, 15min, 1hr
EXCHANGE_WEIGHTS = {
    'CBOE': 1.2,   # Higher weight for CBOE
    'PHLX': 1.1,   # Philadelphia exchange
    'ISE': 1.0,    # International Securities Exchange
    'ARCA': 1.0,   # NYSE Arca
    'Other': 0.9   # Other exchanges
}

# Alert Thresholds
BULLISH_FLOW_ALERT = 2.0  # Call/Put ratio
BEARISH_FLOW_ALERT = 0.5  # Call/Put ratio
EXTREME_VOLUME_ALERT = 10  # Times normal volume
SENTIMENT_SHIFT_ALERT = 0.3  # 30% sentiment change

# Machine Learning Parameters
ANOMALY_CONTAMINATION = 0.05  # 5% expected anomalies
PATTERN_HISTORY_DAYS = 20  # Days of pattern history
MIN_PATTERN_OCCURRENCES = 3  # Minimum pattern frequency

# ==============================================================================
# ENUMS
# ==============================================================================
class FlowType(Enum):
    """Types of options order flow"""
    SWEEP = "sweep"
    BLOCK = "block"
    SPLIT = "split"
    REGULAR = "regular"
    INTERMARKET_SWEEP = "intermarket_sweep"
    AUCTION = "auction"

class OrderSentiment(Enum):
    """Sentiment of order flow"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    MIXED = "mixed"

class TraderType(Enum):
    """Estimated trader type"""
    RETAIL = "retail"
    INSTITUTIONAL = "institutional"
    MARKET_MAKER = "market_maker"
    SMART_MONEY = "smart_money"
    UNKNOWN = "unknown"

class FlowSignal(Enum):
    """Trading signals from flow analysis"""
    BULLISH_SWEEP = "bullish_sweep"
    BEARISH_SWEEP = "bearish_sweep"
    SMART_MONEY_ACCUMULATION = "smart_money_accumulation"
    INSTITUTIONAL_BUYING = "institutional_buying"
    INSTITUTIONAL_SELLING = "institutional_selling"
    UNUSUAL_ACTIVITY = "unusual_activity"
    SENTIMENT_EXTREME = "sentiment_extreme"
    VOLUME_SPIKE = "volume_spike"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OptionFlow:
    """Individual option flow transaction"""
    timestamp: datetime
    symbol: str
    strike: float
    expiry: date
    option_type: str  # 'CALL' or 'PUT'
    
    # Trade details
    price: float
    size: int
    premium: float
    exchange: str
    
    # Flow characteristics
    flow_type: FlowType
    at_ask: bool
    at_bid: bool
    above_ask: bool
    below_bid: bool
    
    # Analysis
    sentiment: OrderSentiment
    trader_type: TraderType
    is_unusual: bool
    volume_ratio: float  # vs average
    oi_ratio: float  # volume/OI
    
    # Context
    underlying_price: float
    iv: float
    delta: Optional[float] = None
    days_to_expiry: int = 0

@dataclass
class FlowCluster:
    """Cluster of related flows (potential sweep)"""
    flows: List[OptionFlow]
    total_premium: float
    total_contracts: int
    time_span: float  # seconds
    exchanges: Set[str]
    cluster_type: str  # 'sweep', 'block', 'accumulation'
    confidence: float

@dataclass
class FlowSentiment:
    """Aggregated flow sentiment metrics"""
    timestamp: datetime
    period: int  # seconds
    
    # Volume metrics
    call_volume: int
    put_volume: int
    call_premium: float
    put_premium: float
    total_volume: int
    total_premium: float
    
    # Ratios
    call_put_ratio: float
    premium_ratio: float
    
    # Sentiment scores
    bullish_score: float  # 0-100
    bearish_score: float  # 0-100
    sentiment: OrderSentiment
    strength: float  # 0-1
    
    # Flow breakdown
    retail_pct: float
    institutional_pct: float
    smart_money_pct: float

@dataclass
class UnusualActivity:
    """Detected unusual options activity"""
    timestamp: datetime
    symbol: str
    activity_type: str
    
    # Details
    description: str
    flows: List[OptionFlow]
    total_premium: float
    size_vs_average: float
    
    # Significance
    unusual_score: float  # 0-100
    confidence: float  # 0-1
    
    # Trading implications
    suggested_action: str
    price_target: Optional[float]
    time_horizon: str

@dataclass
class SmartMoneyFlow:
    """Identified smart money transaction"""
    flow: OptionFlow
    indicators: List[str]  # Why classified as smart money
    repeat_trader: bool
    historical_accuracy: Optional[float]
    follow_confidence: float  # Confidence to follow

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class AdvancedOptionsFlowAnalyzer:
    """
    Professional options flow analyzer with ML-enhanced detection.
    
    This class provides institutional-grade options flow analysis including
    sweep detection, unusual activity identification, smart money tracking,
    and sentiment analysis. It uses machine learning to identify patterns
    and generates actionable trading signals.
    
    Attributes:
        logger: Module logger
        flow_buffer: Recent flows for analysis
        sentiment_trackers: Sentiment by time period
        unusual_patterns: Detected patterns
        
    Example:
        >>> analyzer = AdvancedOptionsFlowAnalyzer()
        >>> analyzer.start_monitoring()
        >>> signals = analyzer.get_flow_signals()
        >>> sentiment = analyzer.get_current_sentiment()
    """
    
    def __init__(self,
                 opra_feed: Optional[OPRAFeedHandler] = None,
                 option_chain_mgr: Optional[OptionChainManager] = None):
        """
        Initialize flow analyzer.
        
        Args:
            opra_feed: OPRA feed handler
            option_chain_mgr: Option chain manager
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Data sources
        self.opra_feed = opra_feed or OPRAFeedHandler()
        self.option_chain_mgr = option_chain_mgr or OptionChainManager()
        self.event_manager = get_event_manager()
        
        # Flow storage
        self.flow_buffer: Deque[OptionFlow] = deque(maxlen=10000)
        self.flow_by_symbol: Dict[str, Deque[OptionFlow]] = defaultdict(lambda: deque(maxlen=1000))
        self.sweep_candidates: List[FlowCluster] = []
        
        # Sentiment tracking
        self.sentiment_trackers: Dict[int, FlowSentiment] = {}
        self.sentiment_history: Deque[FlowSentiment] = deque(maxlen=1000)
        
        # Unusual activity detection
        self.unusual_patterns: List[UnusualActivity] = []
        self.volume_baselines: Dict[str, float] = {}
        self.anomaly_detector = self._initialize_anomaly_detector()
        
        # Smart money tracking
        self.smart_money_flows: Deque[SmartMoneyFlow] = deque(maxlen=500)
        self.trader_signatures: Dict[str, List[OptionFlow]] = defaultdict(list)
        
        # Performance tracking
        self.processing_times: Deque[float] = deque(maxlen=100)
        self.alert_history: Deque[Dict] = deque(maxlen=100)
        
        # Threading
        self._lock = threading.RLock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Initialize baselines
        self._load_historical_baselines()
        
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    # ==========================================================================
    # PUBLIC METHODS - FLOW PROCESSING
    # ==========================================================================
    
    def process_option_trade(self, trade_data: Dict[str, Any]) -> Optional[OptionFlow]:
        """
        Process incoming option trade from OPRA feed.
        
        Args:
            trade_data: Raw trade data from feed
            
        Returns:
            Processed OptionFlow object if significant
        """
        start_time = time.time()
        
        try:
            # Parse trade data
            flow = self._parse_trade_data(trade_data)
            if not flow:
                return None
            
            # Check significance
            if flow.premium < MIN_PREMIUM_VALUE:
                return None
            
            # Analyze flow characteristics
            self._analyze_flow_characteristics(flow)
            
            # Classify trader type
            flow.trader_type = self._classify_trader_type(flow)
            
            # Check for unusual activity
            flow.is_unusual = self._is_unusual_activity(flow)
            
            # Add to buffers
            with self._lock:
                self.flow_buffer.append(flow)
                self.flow_by_symbol[flow.symbol].append(flow)
            
            # Check for sweeps
            self._check_for_sweeps(flow)
            
            # Update sentiment
            self._update_sentiment(flow)
            
            # Check for smart money
            if flow.trader_type == TraderType.SMART_MONEY:
                self._track_smart_money(flow)
            
            # Track processing time
            self.processing_times.append(time.time() - start_time)
            
            # Emit event if significant
            if flow.is_unusual or flow.premium > SMART_MONEY_PREMIUM:
                self._emit_flow_event(flow)
            
            return flow
            
        except Exception as e:
            self.logger.error(f"Error processing trade: {e}")
            self.error_handler.handle_error(e)
            return None
    
    def detect_sweeps(self, time_window: float = SWEEP_TIME_WINDOW) -> List[FlowCluster]:
        """
        Detect option sweeps across multiple exchanges.
        
        Args:
            time_window: Time window for sweep detection
            
        Returns:
            List of detected sweep clusters
        """
        sweeps = []
        current_time = datetime.now()
        
        # Group recent flows by symbol/strike/expiry
        flow_groups = defaultdict(list)
        
        for flow in self.flow_buffer:
            if (current_time - flow.timestamp).total_seconds() > time_window:
                continue
            
            key = (flow.symbol, flow.strike, flow.expiry, flow.option_type)
            flow_groups[key].append(flow)
        
        # Identify sweeps
        for key, flows in flow_groups.items():
            if len(flows) < 2:
                continue
            
            # Check sweep criteria
            exchanges = set(f.exchange for f in flows)
            if len(exchanges) < 2:  # Must hit multiple exchanges
                continue
            
            total_contracts = sum(f.size for f in flows)
            if total_contracts < BLOCK_TRADE_SIZE:
                continue
            
            # Calculate time span
            time_span = (max(f.timestamp for f in flows) - 
                        min(f.timestamp for f in flows)).total_seconds()
            
            if time_span <= time_window:
                # Create sweep cluster
                cluster = FlowCluster(
                    flows=flows,
                    total_premium=sum(f.premium for f in flows),
                    total_contracts=total_contracts,
                    time_span=time_span,
                    exchanges=exchanges,
                    cluster_type='sweep',
                    confidence=self._calculate_sweep_confidence(flows, exchanges, time_span)
                )
                
                sweeps.append(cluster)
                
                # Log significant sweeps
                if cluster.total_premium > INSTITUTIONAL_SIZE * 100:
                    self.logger.info(f"Major sweep detected: {key[0]} "
                                   f"${cluster.total_premium:,.0f} across {len(exchanges)} exchanges")
        
        # Update sweep candidates
        with self._lock:
            self.sweep_candidates = sweeps
        
        return sweeps
    
    def analyze_unusual_activity(self) -> List[UnusualActivity]:
        """
        Analyze and detect unusual options activity.
        
        Returns:
            List of unusual activity detections
        """
        unusual_activities = []
        
        # Group flows by symbol
        for symbol, flows in self.flow_by_symbol.items():
            if not flows:
                continue
            
            # Get baseline volume
            baseline = self.volume_baselines.get(symbol, 1000)
            
            # Calculate recent volume
            recent_flows = [f for f in flows if 
                          (datetime.now() - f.timestamp).total_seconds() < 3600]
            
            if not recent_flows:
                continue
            
            recent_volume = sum(f.size for f in recent_flows)
            volume_ratio = recent_volume / baseline if baseline > 0 else 0
            
            # Check for unusual volume
            if volume_ratio > UNUSUAL_VOLUME_MULTIPLIER:
                # Analyze the nature of unusual activity
                activity_type, description = self._analyze_unusual_pattern(recent_flows)
                
                unusual = UnusualActivity(
                    timestamp=datetime.now(),
                    symbol=symbol,
                    activity_type=activity_type,
                    description=description,
                    flows=recent_flows,
                    total_premium=sum(f.premium for f in recent_flows),
                    size_vs_average=volume_ratio,
                    unusual_score=min(volume_ratio * 10, 100),
                    confidence=self._calculate_unusual_confidence(recent_flows, volume_ratio),
                    suggested_action=self._suggest_action_for_unusual(recent_flows, activity_type),
                    price_target=self._estimate_price_target(recent_flows),
                    time_horizon=self._estimate_time_horizon(recent_flows)
                )
                
                unusual_activities.append(unusual)
        
        # ML-based anomaly detection
        ml_anomalies = self._detect_ml_anomalies()
        unusual_activities.extend(ml_anomalies)
        
        # Update stored patterns
        with self._lock:
            self.unusual_patterns = unusual_activities
        
        return unusual_activities
    
    def get_current_sentiment(self, period: int = 300) -> FlowSentiment:
        """
        Get current flow sentiment for specified period.
        
        Args:
            period: Time period in seconds
            
        Returns:
            Current flow sentiment metrics
        """
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(seconds=period)
        
        # Filter flows within period
        period_flows = [f for f in self.flow_buffer 
                       if f.timestamp > cutoff_time]
        
        if not period_flows:
            return self._create_neutral_sentiment(period)
        
        # Calculate metrics
        call_flows = [f for f in period_flows if f.option_type == 'CALL']
        put_flows = [f for f in period_flows if f.option_type == 'PUT']
        
        call_volume = sum(f.size for f in call_flows)
        put_volume = sum(f.size for f in put_flows)
        call_premium = sum(f.premium for f in call_flows)
        put_premium = sum(f.premium for f in put_flows)
        
        # Calculate ratios
        total_volume = call_volume + put_volume
        call_put_ratio = call_volume / put_volume if put_volume > 0 else float('inf')
        premium_ratio = call_premium / put_premium if put_premium > 0 else float('inf')
        
        # Calculate sentiment scores
        bullish_score = self._calculate_bullish_score(period_flows)
        bearish_score = self._calculate_bearish_score(period_flows)
        
        # Determine overall sentiment
        if bullish_score > bearish_score * 1.5:
            sentiment = OrderSentiment.BULLISH
        elif bearish_score > bullish_score * 1.5:
            sentiment = OrderSentiment.BEARISH
        else:
            sentiment = OrderSentiment.NEUTRAL
        
        # Calculate trader type breakdown
        trader_breakdown = self._calculate_trader_breakdown(period_flows)
        
        flow_sentiment = FlowSentiment(
            timestamp=current_time,
            period=period,
            call_volume=call_volume,
            put_volume=put_volume,
            call_premium=call_premium,
            put_premium=put_premium,
            total_volume=total_volume,
            total_premium=call_premium + put_premium,
            call_put_ratio=call_put_ratio,
            premium_ratio=premium_ratio,
            bullish_score=bullish_score,
            bearish_score=bearish_score,
            sentiment=sentiment,
            strength=abs(bullish_score - bearish_score) / 100,
            retail_pct=trader_breakdown['retail'],
            institutional_pct=trader_breakdown['institutional'],
            smart_money_pct=trader_breakdown['smart_money']
        )
        
        # Store sentiment
        with self._lock:
            self.sentiment_trackers[period] = flow_sentiment
            self.sentiment_history.append(flow_sentiment)
        
        return flow_sentiment
    
    def identify_smart_money(self) -> List[SmartMoneyFlow]:
        """
        Identify potential smart money flows.
        
        Returns: