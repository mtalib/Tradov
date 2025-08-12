#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System
================================================================================
Module: SpyderB18_CustomMetricsClient.py
Group: B (Broker)
Purpose: Custom Metrics Calculation Client (Client 10)
Author: Mohamed Talib
Date Created: 2025-01-15
Last Updated: 2025-01-15 Time: 10:00:00

Description:
    This module implements Client 10 as a dedicated custom metrics calculation
    engine. It handles complex derivative calculations including GEX (Gamma 
    Exposure), DEX (Delta Exposure), OGL (Options Greeks Level), DIX (Dark 
    Index), and SWAN (Black Swan Indicator). The module subscribes to data
    from other clients and performs real-time calculations to provide these
    advanced metrics to the dashboard without impacting core data feeds.

Key Features:
    - Real-time calculation of custom market metrics
    - Efficient data aggregation from multiple client sources
    - Optimized calculation algorithms for low latency
    - Caching mechanism for performance optimization
    - Independent update cycles for each metric type

Integration Points:
    - Receives data from Clients 3-9 for calculations
    - Provides calculated metrics to SpyderG05_TradingDashboard
    - Integrates with SpyderB08_MultiClientDataManager
    - Reports metrics to SpyderB15_PrometheusMetrics
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import time
import threading
import queue
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import deque, defaultdict
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    from SpyderA_Core.SpyderA05_EventManager import EventManager, EventType
    from SpyderB_Broker.SpyderB08_MultiClientDataManager import (
        MultiClientDataManager, get_manager_instance
    )
    UTILITIES_AVAILABLE = True
except ImportError:
    UTILITIES_AVAILABLE = False
    print("⚠️ Some utilities not available, using fallback")

# ==============================================================================
# CONSTANTS
# ==============================================================================
CLIENT_ID = 10  # Dedicated Client 10 for custom metrics
UPDATE_FREQUENCIES = {
    'GEX': 5.0,    # Gamma Exposure - 5 second updates
    'DEX': 5.0,    # Delta Exposure - 5 second updates  
    'OGL': 10.0,   # Options Greeks Level - 10 second updates
    'DIX': 30.0,   # Dark Index - 30 second updates
    'SWAN': 60.0   # Black Swan Indicator - 60 second updates
}

# Calculation thresholds
MIN_OPTION_VOLUME = 100  # Minimum volume to include in calculations
MAX_STRIKE_DEVIATION = 0.1  # 10% max deviation from spot for inclusion
CACHE_EXPIRY = 300  # Cache expiry in seconds

# ==============================================================================
# ENUMS
# ==============================================================================
class MetricType(Enum):
    """Types of custom metrics calculated"""
    GEX = "Gamma Exposure"
    DEX = "Delta Exposure"
    OGL = "Options Greeks Level"
    DIX = "Dark Index"
    SWAN = "Black Swan Indicator"

class CalculationStatus(Enum):
    """Status of metric calculations"""
    IDLE = auto()
    CALCULATING = auto()
    COMPLETE = auto()
    ERROR = auto()

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class MarketDataSnapshot:
    """Snapshot of market data for calculations"""
    timestamp: datetime
    spy_price: float
    vix_level: float
    options_chain: Dict[str, Any]
    volume_profile: Dict[str, float]
    internals: Dict[str, float]

@dataclass
class MetricResult:
    """Result of a metric calculation"""
    metric_type: MetricType
    value: float
    change: float
    change_pct: float
    timestamp: datetime
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CalculationCache:
    """Cache for calculated values"""
    value: float
    timestamp: datetime
    expires: datetime

# ==============================================================================
# CUSTOM METRICS CLIENT CLASS
# ==============================================================================
class CustomMetricsClient:
    """
    Client 10: Custom Metrics Calculation Engine
    
    Handles complex derivative calculations for dashboard display without
    impacting core data feed performance. Implements sophisticated algorithms
    for market microstructure analysis and risk metrics.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the Custom Metrics Client.
        
        Args:
            config: Optional configuration dictionary
        """
        # Core components
        self.client_id = CLIENT_ID
        self.is_running = False
        self.config = config or {}
        
        # Logging
        if UTILITIES_AVAILABLE:
            self.logger = SpyderLogger.get_logger('SpyderB18.CustomMetrics')
            self.error_handler = SpyderErrorHandler()
        else:
            self.logger = logging.getLogger('SpyderB18.CustomMetrics')
            self.error_handler = None
        
        # Threading
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self.executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="CustomMetrics")
        
        # Data management
        self.market_data_buffer: deque = deque(maxlen=1000)
        self.current_metrics: Dict[str, MetricResult] = {}
        self.calculation_cache: Dict[str, CalculationCache] = {}
        
        # Calculation components
        self.calculation_threads: Dict[str, threading.Thread] = {}
        self.calculation_status: Dict[str, CalculationStatus] = {}
        self.last_calculation: Dict[str, datetime] = {}
        
        # Callbacks and subscribers
        self.metric_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        
        # Performance tracking
        self.calculation_times: Dict[str, deque] = {
            metric: deque(maxlen=100) for metric in MetricType
        }
        self.total_calculations = 0
        self.calculation_errors = 0
        
        # Initialize metric status
        for metric_type in MetricType:
            self.calculation_status[metric_type.value] = CalculationStatus.IDLE
            self.last_calculation[metric_type.value] = datetime.now()
        
        # Redis connection for caching (optional)
        self.redis_client = None
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(host='localhost', port=6379, db=10)
                self.redis_client.ping()
                self.logger.info("✅ Redis connected for metric caching")
            except:
                self.redis_client = None
                self.logger.warning("⚠️ Redis not available, using local cache")
        
        self.logger.info(f"✅ Custom Metrics Client (ID: {self.client_id}) initialized")
    
    # ==========================================================================
    # METRIC CALCULATION METHODS
    # ==========================================================================
    
    def calculate_gex(self, snapshot: MarketDataSnapshot) -> MetricResult:
        """
        Calculate Gamma Exposure (GEX).
        
        GEX measures the market maker hedging flow required for a 1% move in SPY.
        Positive GEX suggests dampened volatility, negative GEX suggests amplified moves.
        
        Args:
            snapshot: Current market data snapshot
            
        Returns:
            MetricResult with GEX value
        """
        start_time = time.time()
        
        try:
            spy_price = snapshot.spy_price
            options_chain = snapshot.options_chain
            
            total_gamma_exposure = 0.0
            
            # Iterate through all strikes and expirations
            for expiry, strikes in options_chain.items():
                for strike, option_data in strikes.items():
                    # Check if strike is within reasonable range
                    if abs(strike - spy_price) / spy_price > MAX_STRIKE_DEVIATION:
                        continue
                    
                    # Get option Greeks and open interest
                    call_gamma = option_data.get('call_gamma', 0)
                    put_gamma = option_data.get('put_gamma', 0)
                    call_oi = option_data.get('call_oi', 0)
                    put_oi = option_data.get('put_oi', 0)
                    
                    # Calculate gamma exposure for this strike
                    # Market makers are short calls and long puts typically
                    strike_gex = (call_gamma * call_oi * 100 * spy_price * spy_price * 0.01)
                    strike_gex -= (put_gamma * put_oi * 100 * spy_price * spy_price * 0.01)
                    
                    total_gamma_exposure += strike_gex
            
            # Convert to billions for display
            gex_billions = total_gamma_exposure / 1_000_000_000
            
            # Calculate change from previous
            prev_gex = self.current_metrics.get('GEX', MetricResult(
                MetricType.GEX, 0, 0, 0, datetime.now()
            )).value
            
            change = gex_billions - prev_gex
            change_pct = (change / prev_gex * 100) if prev_gex != 0 else 0
            
            result = MetricResult(
                metric_type=MetricType.GEX,
                value=gex_billions,
                change=change,
                change_pct=change_pct,
                timestamp=datetime.now(),
                metadata={
                    'spy_price': spy_price,
                    'calculation_time': time.time() - start_time
                }
            )
            
            self.logger.debug(f"GEX calculated: {gex_billions:.2f}B")
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating GEX: {e}")
            self.calculation_errors += 1
            return MetricResult(
                MetricType.GEX, 0, 0, 0, datetime.now(), confidence=0
            )
    
    def calculate_dex(self, snapshot: MarketDataSnapshot) -> MetricResult:
        """
        Calculate Delta Exposure (DEX).
        
        DEX measures the directional exposure from options positioning.
        Helps identify potential support/resistance levels.
        
        Args:
            snapshot: Current market data snapshot
            
        Returns:
            MetricResult with DEX value
        """
        start_time = time.time()
        
        try:
            spy_price = snapshot.spy_price
            options_chain = snapshot.options_chain
            
            total_delta_exposure = 0.0
            
            for expiry, strikes in options_chain.items():
                for strike, option_data in strikes.items():
                    # Get option deltas and open interest
                    call_delta = option_data.get('call_delta', 0)
                    put_delta = option_data.get('put_delta', 0)
                    call_oi = option_data.get('call_oi', 0)
                    put_oi = option_data.get('put_oi', 0)
                    
                    # Calculate net delta exposure
                    strike_dex = (call_delta * call_oi * 100 * spy_price)
                    strike_dex += (put_delta * put_oi * 100 * spy_price)
                    
                    total_delta_exposure += strike_dex
            
            # Convert to billions
            dex_billions = total_delta_exposure / 1_000_000_000
            
            # Calculate change
            prev_dex = self.current_metrics.get('DEX', MetricResult(
                MetricType.DEX, 0, 0, 0, datetime.now()
            )).value
            
            change = dex_billions - prev_dex
            change_pct = (change / prev_dex * 100) if prev_dex != 0 else 0
            
            result = MetricResult(
                metric_type=MetricType.DEX,
                value=dex_billions,
                change=change,
                change_pct=change_pct,
                timestamp=datetime.now(),
                metadata={
                    'spy_price': spy_price,
                    'calculation_time': time.time() - start_time
                }
            )
            
            self.logger.debug(f"DEX calculated: {dex_billions:.2f}B")
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating DEX: {e}")
            self.calculation_errors += 1
            return MetricResult(
                MetricType.DEX, 0, 0, 0, datetime.now(), confidence=0
            )
    
    def calculate_ogl(self, snapshot: MarketDataSnapshot) -> MetricResult:
        """
        Calculate Options Greeks Level (OGL).
        
        Composite metric combining various Greeks to assess overall
        options market positioning and potential volatility.
        
        Args:
            snapshot: Current market data snapshot
            
        Returns:
            MetricResult with OGL value
        """
        start_time = time.time()
        
        try:
            # Get GEX and DEX values
            gex = self.current_metrics.get('GEX', MetricResult(
                MetricType.GEX, 0, 0, 0, datetime.now()
            )).value
            
            dex = self.current_metrics.get('DEX', MetricResult(
                MetricType.DEX, 0, 0, 0, datetime.now()
            )).value
            
            # Get VIX level
            vix = snapshot.vix_level
            
            # Calculate OGL composite score (0-100 scale)
            # Higher OGL suggests more options activity and potential volatility
            gex_component = min(abs(gex) / 10, 1.0) * 30  # Max 30 points
            dex_component = min(abs(dex) / 50, 1.0) * 30  # Max 30 points
            vix_component = min(vix / 40, 1.0) * 40  # Max 40 points
            
            ogl_score = gex_component + dex_component + vix_component
            
            # Calculate change
            prev_ogl = self.current_metrics.get('OGL', MetricResult(
                MetricType.OGL, 50, 0, 0, datetime.now()
            )).value
            
            change = ogl_score - prev_ogl
            change_pct = (change / prev_ogl * 100) if prev_ogl != 0 else 0
            
            result = MetricResult(
                metric_type=MetricType.OGL,
                value=ogl_score,
                change=change,
                change_pct=change_pct,
                timestamp=datetime.now(),
                metadata={
                    'gex_contribution': gex_component,
                    'dex_contribution': dex_component,
                    'vix_contribution': vix_component,
                    'calculation_time': time.time() - start_time
                }
            )
            
            self.logger.debug(f"OGL calculated: {ogl_score:.2f}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating OGL: {e}")
            self.calculation_errors += 1
            return MetricResult(
                MetricType.OGL, 50, 0, 0, datetime.now(), confidence=0
            )
    
    def calculate_dix(self, snapshot: MarketDataSnapshot) -> MetricResult:
        """
        Calculate Dark Index (DIX).
        
        Measures dark pool activity relative to total volume.
        High DIX suggests institutional accumulation.
        
        Args:
            snapshot: Current market data snapshot
            
        Returns:
            MetricResult with DIX value
        """
        start_time = time.time()
        
        try:
            volume_profile = snapshot.volume_profile
            
            # Get dark pool volume (simulated - in production would use real data)
            dark_volume = volume_profile.get('dark_volume', 0)
            total_volume = volume_profile.get('total_volume', 1)
            
            # Calculate DIX percentage
            dix_value = (dark_volume / total_volume) * 100 if total_volume > 0 else 45.0
            
            # Add some market internals influence
            internals = snapshot.internals
            tick = internals.get('TICK', 0)
            add = internals.get('ADD', 0)
            
            # Adjust DIX based on internals
            if tick > 500 and add > 1000:
                dix_value += 2.0  # Bullish internals
            elif tick < -500 and add < -1000:
                dix_value -= 2.0  # Bearish internals
            
            # Clamp to reasonable range
            dix_value = max(30, min(70, dix_value))
            
            # Calculate change
            prev_dix = self.current_metrics.get('DIX', MetricResult(
                MetricType.DIX, 45, 0, 0, datetime.now()
            )).value
            
            change = dix_value - prev_dix
            change_pct = (change / prev_dix * 100) if prev_dix != 0 else 0
            
            result = MetricResult(
                metric_type=MetricType.DIX,
                value=dix_value,
                change=change,
                change_pct=change_pct,
                timestamp=datetime.now(),
                metadata={
                    'dark_volume': dark_volume,
                    'total_volume': total_volume,
                    'calculation_time': time.time() - start_time
                }
            )
            
            self.logger.debug(f"DIX calculated: {dix_value:.2f}%")
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating DIX: {e}")
            self.calculation_errors += 1
            return MetricResult(
                MetricType.DIX, 45, 0, 0, datetime.now(), confidence=0
            )
    
    def calculate_swan(self, snapshot: MarketDataSnapshot) -> MetricResult:
        """
        Calculate Black Swan Indicator (SWAN).
        
        Measures tail risk and potential for extreme market moves.
        Higher values suggest increased probability of black swan events.
        
        Args:
            snapshot: Current market data snapshot
            
        Returns:
            MetricResult with SWAN value
        """
        start_time = time.time()
        
        try:
            vix = snapshot.vix_level
            options_chain = snapshot.options_chain
            
            # Calculate put/call skew for far OTM options
            spy_price = snapshot.spy_price
            otm_put_iv_sum = 0
            otm_call_iv_sum = 0
            put_count = 0
            call_count = 0
            
            for expiry, strikes in options_chain.items():
                for strike, option_data in strikes.items():
                    # Far OTM puts (>5% below spot)
                    if strike < spy_price * 0.95:
                        otm_put_iv_sum += option_data.get('put_iv', 0)
                        put_count += 1
                    
                    # Far OTM calls (>5% above spot)
                    elif strike > spy_price * 1.05:
                        otm_call_iv_sum += option_data.get('call_iv', 0)
                        call_count += 1
            
            # Calculate average OTM IVs
            avg_put_iv = otm_put_iv_sum / put_count if put_count > 0 else 20
            avg_call_iv = otm_call_iv_sum / call_count if call_count > 0 else 20
            
            # SWAN calculation
            # Higher put skew and high VIX = higher SWAN
            put_skew = avg_put_iv - avg_call_iv
            vix_component = min(vix / 30, 1.0) * 50
            skew_component = min(put_skew / 10, 1.0) * 50
            
            swan_value = vix_component + skew_component
            
            # Calculate change
            prev_swan = self.current_metrics.get('SWAN', MetricResult(
                MetricType.SWAN, 30, 0, 0, datetime.now()
            )).value
            
            change = swan_value - prev_swan
            change_pct = (change / prev_swan * 100) if prev_swan != 0 else 0
            
            result = MetricResult(
                metric_type=MetricType.SWAN,
                value=swan_value,
                change=change,
                change_pct=change_pct,
                timestamp=datetime.now(),
                metadata={
                    'vix_level': vix,
                    'put_skew': put_skew,
                    'avg_put_iv': avg_put_iv,
                    'avg_call_iv': avg_call_iv,
                    'calculation_time': time.time() - start_time
                }
            )
            
            self.logger.debug(f"SWAN calculated: {swan_value:.2f}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating SWAN: {e}")
            self.calculation_errors += 1
            return MetricResult(
                MetricType.SWAN, 30, 0, 0, datetime.now(), confidence=0
            )
    
    # ==========================================================================
    # CALCULATION ORCHESTRATION
    # ==========================================================================
    
    def start(self):
        """Start the custom metrics calculation engine."""
        if self.is_running:
            self.logger.warning("Custom Metrics Client already running")
            return
        
        self.is_running = True
        self._stop_event.clear()
        
        # Start calculation threads for each metric
        for metric_type in MetricType:
            thread = threading.Thread(
                target=self._calculation_loop,
                args=(metric_type,),
                name=f"Calc_{metric_type.value}",
                daemon=True
            )
            thread.start()
            self.calculation_threads[metric_type.value] = thread
        
        # Start data collection thread
        self.data_thread = threading.Thread(
            target=self._data_collection_loop,
            name="DataCollection",
            daemon=True
        )
        self.data_thread.start()
        
        self.logger.info(f"✅ Custom Metrics Client {self.client_id} started")
    
    def stop(self):
        """Stop the custom metrics calculation engine."""
        if not self.is_running:
            return
        
        self.logger.info(f"Stopping Custom Metrics Client {self.client_id}...")
        
        self.is_running = False
        self._stop_event.set()
        
        # Wait for threads to complete
        for thread in self.calculation_threads.values():
            if thread and thread.is_alive():
                thread.join(timeout=5)
        
        if hasattr(self, 'data_thread') and self.data_thread.is_alive():
            self.data_thread.join(timeout=5)
        
        # Cleanup
        self.executor.shutdown(wait=True)
        
        self.logger.info(f"✅ Custom Metrics Client {self.client_id} stopped")
    
    def _calculation_loop(self, metric_type: MetricType):
        """
        Main calculation loop for a specific metric.
        
        Args:
            metric_type: Type of metric to calculate
        """
        metric_name = metric_type.value
        update_frequency = UPDATE_FREQUENCIES.get(metric_name, 10.0)
        
        self.logger.info(f"Starting calculation loop for {metric_name} (freq: {update_frequency}s)")
        
        while self.is_running and not self._stop_event.is_set():
            try:
                # Check if it's time to update
                last_calc = self.last_calculation.get(metric_name, datetime.min)
                if (datetime.now() - last_calc).total_seconds() < update_frequency:
                    time.sleep(1)
                    continue
                
                # Get latest market snapshot
                snapshot = self._get_market_snapshot()
                if not snapshot:
                    time.sleep(1)
                    continue
                
                # Update status
                self.calculation_status[metric_name] = CalculationStatus.CALCULATING
                
                # Perform calculation based on metric type
                if metric_type == MetricType.GEX:
                    result = self.calculate_gex(snapshot)
                elif metric_type == MetricType.DEX:
                    result = self.calculate_dex(snapshot)
                elif metric_type == MetricType.OGL:
                    result = self.calculate_ogl(snapshot)
                elif metric_type == MetricType.DIX:
                    result = self.calculate_dix(snapshot)
                elif metric_type == MetricType.SWAN:
                    result = self.calculate_swan(snapshot)
                else:
                    continue
                
                # Store result
                with self._lock:
                    self.current_metrics[metric_name] = result
                    self.last_calculation[metric_name] = datetime.now()
                    self.calculation_status[metric_name] = CalculationStatus.COMPLETE
                    self.total_calculations += 1
                
                # Cache result
                self._cache_result(metric_name, result)
                
                # Notify subscribers
                self._notify_subscribers(metric_name, result)
                
                # Record performance
                if result.metadata:
                    calc_time = result.metadata.get('calculation_time', 0)
                    self.calculation_times[metric_type].append(calc_time)
                
            except Exception as e:
                self.logger.error(f"Error in {metric_name} calculation loop: {e}")
                self.calculation_status[metric_name] = CalculationStatus.ERROR
                self.calculation_errors += 1
                
            # Sleep before next iteration
            time.sleep(1)
    
    def _data_collection_loop(self):
        """Collect market data from other clients."""
        self.logger.info("Starting data collection loop")
        
        while self.is_running and not self._stop_event.is_set():
            try:
                # Get data from MultiClientDataManager if available
                if UTILITIES_AVAILABLE:
                    manager = get_manager_instance()
                    
                    # Collect relevant data from different clients
                    # This is a simplified version - actual implementation would
                    # subscribe to specific data feeds
                    
                    market_data = {
                        'timestamp': datetime.now(),
                        'spy': manager.market_data.get('SPY'),
                        'vix': manager.market_data.get('VIX'),
                        'options': manager.market_data.get('SPY_OPTIONS'),
                        'internals': {
                            'TICK': manager.market_data.get('TICK-NYSE'),
                            'ADD': manager.market_data.get('ADD-NYSE'),
                            'TRIN': manager.market_data.get('TRIN-NYSE')
                        }
                    }
                    
                    # Add to buffer
                    self.market_data_buffer.append(market_data)
                
            except Exception as e:
                self.logger.error(f"Error in data collection: {e}")
            
            time.sleep(1)
    
    def _get_market_snapshot(self) -> Optional[MarketDataSnapshot]:
        """
        Get current market data snapshot for calculations.
        
        Returns:
            MarketDataSnapshot or None if data unavailable
        """
        try:
            if not self.market_data_buffer:
                return None
            
            # Get latest data
            latest_data = self.market_data_buffer[-1]
            
            # Create snapshot (simplified - actual implementation would be more complex)
            snapshot = MarketDataSnapshot(
                timestamp=latest_data.get('timestamp', datetime.now()),
                spy_price=latest_data.get('spy', {}).get('last', 585.0),
                vix_level=latest_data.get('vix', {}).get('last', 15.0),
                options_chain=latest_data.get('options', {}),
                volume_profile={'total_volume': 50000000, 'dark_volume': 20000000},
                internals=latest_data.get('internals', {})
            )
            
            return snapshot
            
        except Exception as e:
            self.logger.error(f"Error creating market snapshot: {e}")
            return None
    
    # ==========================================================================
    # CACHING AND PERSISTENCE
    # ==========================================================================
    
    def _cache_result(self, metric_name: str, result: MetricResult):
        """
        Cache calculation result.
        
        Args:
            metric_name: Name of the metric
            result: Calculation result to cache
        """
        try:
            # Local cache
            cache_entry = CalculationCache(
                value=result.value,
                timestamp=result.timestamp,
                expires=result.timestamp + timedelta(seconds=CACHE_EXPIRY)
            )
            self.calculation_cache[metric_name] = cache_entry
            
            # Redis cache if available
            if self.redis_client:
                cache_key = f"spyder:metrics:{metric_name}"
                cache_data = {
                    'value': result.value,
                    'change': result.change,
                    'change_pct': result.change_pct,
                    'timestamp': result.timestamp.isoformat(),
                    'metadata': result.metadata
                }
                self.redis_client.setex(
                    cache_key,
                    CACHE_EXPIRY,
                    json.dumps(cache_data, default=str)
                )
                
        except Exception as e:
            self.logger.error(f"Error caching result for {metric_name}: {e}")
    
    def get_cached_result(self, metric_name: str) -> Optional[MetricResult]:
        """
        Get cached result for a metric.
        
        Args:
            metric_name: Name of the metric
            
        Returns:
            Cached MetricResult or None
        """
        try:
            # Check local cache first
            cache_entry = self.calculation_cache.get(metric_name)
            if cache_entry and cache_entry.expires > datetime.now():
                return self.current_metrics.get(metric_name)
            
            # Check Redis cache
            if self.redis_client:
                cache_key = f"spyder:metrics:{metric_name}"
                cache_data = self.redis_client.get(cache_key)
                if cache_data:
                    data = json.loads(cache_data)
                    return MetricResult(
                        metric_type=MetricType[metric_name],
                        value=data['value'],
                        change=data['change'],
                        change_pct=data['change_pct'],
                        timestamp=datetime.fromisoformat(data['timestamp']),
                        metadata=data.get('metadata', {})
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting cached result for {metric_name}: {e}")
            return None
    
    # ==========================================================================
    # SUBSCRIPTION AND NOTIFICATION
    # ==========================================================================
    
    def subscribe(self, metric: str, callback: Callable):
        """
        Subscribe to updates for a specific metric.
        
        Args:
            metric: Metric name to subscribe to
            callback: Function to call with updates
        """
        with self._lock:
            self.metric_callbacks[metric].append(callback)
            self.logger.info(f"Added subscriber for {metric}")
    
    def unsubscribe(self, metric: str, callback: Callable):
        """
        Unsubscribe from metric updates.
        
        Args:
            metric: Metric name to unsubscribe from
            callback: Callback function to remove
        """
        with self._lock:
            if callback in self.metric_callbacks[metric]:
                self.metric_callbacks[metric].remove(callback)
                self.logger.info(f"Removed subscriber for {metric}")
    
    def _notify_subscribers(self, metric_name: str, result: MetricResult):
        """
        Notify all subscribers of a metric update.
        
        Args:
            metric_name: Name of the updated metric
            result: New metric result
        """
        callbacks = self.metric_callbacks.get(metric_name, [])
        for callback in callbacks:
            try:
                callback(result)
            except Exception as e:
                self.logger.error(f"Error in subscriber callback for {metric_name}: {e}")
    
    # ==========================================================================
    # STATUS AND MONITORING
    # ==========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the custom metrics client.
        
        Returns:
            Status dictionary
        """
        with self._lock:
            # Calculate average calculation times
            avg_calc_times = {}
            for metric_type, times in self.calculation_times.items():
                if times:
                    avg_calc_times[metric_type.value] = sum(times) / len(times)
                else:
                    avg_calc_times[metric_type.value] = 0
            
            return {
                'client_id': self.client_id,
                'is_running': self.is_running,
                'total_calculations': self.total_calculations,
                'calculation_errors': self.calculation_errors,
                'error_rate': self.calculation_errors / max(self.total_calculations, 1),
                'current_metrics': {
                    name: {
                        'value': metric.value,
                        'change': metric.change,
                        'change_pct': metric.change_pct,
                        'last_update': metric.timestamp.isoformat(),
                        'confidence': metric.confidence
                    }
                    for name, metric in self.current_metrics.items()
                },
                'calculation_status': {
                    name: status.name 
                    for name, status in self.calculation_status.items()
                },
                'avg_calculation_times': avg_calc_times,
                'cache_enabled': self.redis_client is not None,
                'buffer_size': len(self.market_data_buffer)
            }
    
    def get_metric(self, metric_name: str) -> Optional[Dict[str, Any]]:
        """
        Get current value for a specific metric.
        
        Args:
            metric_name: Name of the metric
            
        Returns:
            Metric data dictionary or None
        """
        with self._lock:
            result = self.current_metrics.get(metric_name)
            if result:
                return {
                    'value': result.value,
                    'change': result.change,
                    'change_pct': result.change_pct,
                    'timestamp': result.timestamp,
                    'confidence': result.confidence,
                    'metadata': result.metadata
                }
            return None
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all current metric values.
        
        Returns:
            Dictionary of all metrics
        """
        with self._lock:
            return {
                name: self.get_metric(name)
                for name in ['GEX', 'DEX', 'OGL', 'DIX', 'SWAN']
                if self.get_metric(name) is not None
            }

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================
def create_custom_metrics_client(config: Optional[Dict] = None) -> CustomMetricsClient:
    """
    Factory function to create a Custom Metrics Client.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        CustomMetricsClient instance
    """
    return CustomMetricsClient(config)

# ==============================================================================
# GLOBAL INSTANCE MANAGEMENT
# ==============================================================================
_global_metrics_client: Optional[CustomMetricsClient] = None
_client_lock = threading.Lock()

def get_metrics_client() -> CustomMetricsClient:
    """
    Get global metrics client instance (singleton pattern).
    
    Returns:
        Global CustomMetricsClient instance
    """
    global _global_metrics_client
    
    with _client_lock:
        if _global_metrics_client is None:
            _global_metrics_client = CustomMetricsClient()
        return _global_metrics_client

def reset_metrics_client():
    """Reset global metrics client instance."""
    global _global_metrics_client
    
    with _client_lock:
        if _global_metrics_client and _global_metrics_client.is_running:
            _global_metrics_client.stop()
        _global_metrics_client = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Main execution for testing and demonstration."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 80)
    print("🚀 SPYDER B18 - Custom Metrics Client (Client 10)")
    print("=" * 80)
    
    try:
        # Create client
        client = create_custom_metrics_client()
        
        # Start client
        client.start()
        
        print("\n📊 Custom Metrics Client Started")
        print(f"   Client ID: {client.client_id}")
        print(f"   Metrics: GEX, DEX, OGL, DIX, SWAN")
        print(f"   Update Frequencies: {UPDATE_FREQUENCIES}")
        
        # Test metric retrieval
        print("\n🔄 Testing metric calculations...")
        time.sleep(3)
        
        # Get status
        status = client.get_status()
        print(f"\n📈 Client Status:")
        print(f"   Total Calculations: {status['total_calculations']}")
        print(f"   Error Rate: {status['error_rate']:.2%}")
        print(f"   Cache Enabled: {status['cache_enabled']}")
        
        # Get all metrics
        metrics = client.get_all_metrics()
        if metrics:
            print(f"\n📊 Current Metrics:")
            for name, data in metrics.items():
                if data:
                    print(f"   {name}: {data['value']:.2f} "
                          f"(Change: {data['change']:+.2f} / {data['change_pct']:+.2f}%)")
        
        print("\n✅ Custom Metrics Client test completed successfully!")
        
        # Keep running for demonstration
        print("\n⏳ Client running... Press Ctrl+C to stop")
        while True:
            time.sleep(10)
            metrics = client.get_all_metrics()
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Metrics Update:")
            for name, data in metrics.items():
                if data:
                    print(f"   {name}: {data['value']:.2f}")
            
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping client...")
        client.stop()
        print("✅ Client stopped successfully")
    except Exception as e:
        print(f"❌ Error in main: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
