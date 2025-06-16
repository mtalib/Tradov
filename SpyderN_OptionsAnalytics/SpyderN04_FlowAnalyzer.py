#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderN04_FlowAnalyzer.py
Group: N (Options Analytics)
Purpose: Basic options flow analysis

Description:
    This module provides fundamental options flow analysis including volume tracking,
    open interest changes, and buy/sell pressure indicators. It serves as a complement
    to the advanced SpyderN05_OptionsFlowAnalyzer, focusing on real-time flow metrics
    and volume profile analysis.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4

Status: IMPLEMENTED
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from threading import Lock, Thread
import statistics
import time

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderC_MarketData.SpyderC01_OptionsDataFeed import OptionsDataFeed
from SpyderA_Core.SpyderA03_EventManager import EventManager, Event

# ==============================================================================
# CONSTANTS
# ==============================================================================
VOLUME_WINDOW_SIZE = 1000  # Number of trades to keep in history
OI_CHANGE_THRESHOLD = 0.1  # 10% change threshold for alerts
UNUSUAL_VOLUME_MULTIPLIER = 2.0  # Multiplier for unusual activity
LARGE_TRADE_PERCENTILE = 95  # Percentile for large trade identification
UPDATE_INTERVAL = 5  # Seconds between flow updates

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class FlowMetrics:
    """Real-time flow metrics for an option."""
    timestamp: datetime
    symbol: str
    strike: float
    expiration: datetime
    option_type: str  # 'CALL' or 'PUT'
    volume: int
    open_interest: int
    oi_change: int
    oi_change_pct: float
    bid_ask_spread: float
    trade_count: int
    avg_trade_size: float
    large_trades: int
    bid_volume: int
    ask_volume: int
    mid_volume: int
    
@dataclass
class FlowSummary:
    """Aggregated flow summary across all options."""
    timestamp: datetime
    total_volume: int
    call_volume: int
    put_volume: int
    put_call_ratio: float
    volume_weighted_pcr: float  # Volume-weighted put/call ratio
    net_premium: float
    net_delta: float
    unusual_activity_count: int
    large_trade_count: int
    bullish_flow_score: float  # 0-100 score
    bearish_flow_score: float  # 0-100 score
    
@dataclass
class VolumeProfile:
    """Volume profile at specific price levels."""
    price_level: float
    call_volume: int
    put_volume: int
    net_delta: float
    net_gamma: float
    trade_count: int
    avg_trade_size: float
    institutional_volume: int  # Estimated institutional volume

@dataclass
class FlowSignal:
    """Trading signal based on flow analysis."""
    timestamp: datetime
    signal_type: str  # 'BULLISH_FLOW', 'BEARISH_FLOW', 'UNUSUAL_ACTIVITY'
    strength: float  # 0-100
    strike: Optional[float]
    expiration: Optional[datetime]
    metrics: Dict[str, Any]
    action: str  # 'BUY', 'SELL', 'MONITOR'
    reason: str

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class FlowAnalyzer:
    """
    Basic options flow analyzer for real-time monitoring.
    
    This class tracks volume, open interest, and trading patterns to identify
    potential opportunities and market sentiment shifts.
    """
    
    def __init__(self, symbol: str = "SPY"):
        """
        Initialize the flow analyzer.
        
        Args:
            symbol: Underlying symbol to analyze
        """
        self.logger = SpyderLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.symbol = symbol
        
        # Data storage
        self.flow_history: deque = deque(maxlen=VOLUME_WINDOW_SIZE)
        self.volume_profiles: Dict[float, VolumeProfile] = {}
        self.oi_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=20))
        self.flow_cache: Dict[str, FlowMetrics] = {}
        
        # Statistics
        self.avg_volumes: Dict[str, float] = {}
        self.avg_oi: Dict[str, float] = {}
        
        # Threading
        self.lock = Lock()
        self.running = False
        self.monitor_thread: Optional[Thread] = None
        
        # Data feed
        self.data_feed = OptionsDataFeed(symbol)
        self.event_manager = EventManager()
        
        self.logger.info(f"FlowAnalyzer initialized for {symbol}")
        
    # ==========================================================================
    # FLOW TRACKING
    # ==========================================================================
    def track_flow(self, option_data: Dict[str, Any]) -> FlowMetrics:
        """
        Track flow for a single option.
        
        Args:
            option_data: Real-time option data
            
        Returns:
            Flow metrics for the option
        """
        try:
            # Extract key fields
            strike = option_data['strike']
            expiry = option_data['expiration']
            opt_type = option_data['type']
            key = f"{strike}_{expiry}_{opt_type}"
            
            # Calculate flow metrics
            current_oi = option_data.get('open_interest', 0)
            prev_oi = self._get_previous_oi(key)
            oi_change = current_oi - prev_oi if prev_oi else 0
            oi_change_pct = (oi_change / prev_oi * 100) if prev_oi > 0 else 0
            
            # Estimate bid/ask volume (simplified)
            bid_volume = self._estimate_bid_volume(option_data)
            ask_volume = self._estimate_ask_volume(option_data)
            mid_volume = option_data['volume'] - bid_volume - ask_volume
            
            # Create metrics
            metrics = FlowMetrics(
                timestamp=datetime.now(),
                symbol=self.symbol,
                strike=strike,
                expiration=expiry,
                option_type=opt_type,
                volume=option_data['volume'],
                open_interest=current_oi,
                oi_change=oi_change,
                oi_change_pct=oi_change_pct,
                bid_ask_spread=option_data['ask'] - option_data['bid'],
                trade_count=option_data.get('trade_count', 0),
                avg_trade_size=option_data['volume'] / max(option_data.get('trade_count', 1), 1),
                large_trades=self._count_large_trades(option_data),
                bid_volume=bid_volume,
                ask_volume=ask_volume,
                mid_volume=mid_volume
            )
            
            # Update caches
            with self.lock:
                self.flow_cache[key] = metrics
                self.flow_history.append(metrics)
                self.oi_history[key].append(current_oi)
                
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error tracking flow: {e}")
            return self._create_empty_metrics()
            
    def get_flow_summary(self, lookback_minutes: int = 60) -> FlowSummary:
        """
        Get aggregated flow summary.
        
        Args:
            lookback_minutes: Minutes to analyze
            
        Returns:
            Flow summary
        """
        try:
            cutoff_time = datetime.now() - timedelta(minutes=lookback_minutes)
            
            with self.lock:
                recent_flows = [f for f in self.flow_history 
                               if f.timestamp > cutoff_time]
                
            if not recent_flows:
                return self._create_empty_summary()
                
            # Aggregate metrics
            call_volume = sum(f.volume for f in recent_flows if f.option_type == 'CALL')
            put_volume = sum(f.volume for f in recent_flows if f.option_type == 'PUT')
            total_volume = call_volume + put_volume
            
            # Calculate ratios
            pcr = put_volume / max(call_volume, 1)
            
            # Calculate weighted PCR (by premium)
            call_premium = sum(f.volume * self._get_option_price(f) 
                             for f in recent_flows if f.option_type == 'CALL')
            put_premium = sum(f.volume * self._get_option_price(f) 
                            for f in recent_flows if f.option_type == 'PUT')
            volume_weighted_pcr = put_premium / max(call_premium, 1)
            
            # Calculate flow scores
            bullish_score = self._calculate_bullish_score(recent_flows)
            bearish_score = self._calculate_bearish_score(recent_flows)
            
            # Count unusual activity
            unusual_count = sum(1 for f in recent_flows 
                              if self._is_unusual_activity(f))
            large_count = sum(f.large_trades for f in recent_flows)
            
            return FlowSummary(
                timestamp=datetime.now(),
                total_volume=total_volume,
                call_volume=call_volume,
                put_volume=put_volume,
                put_call_ratio=pcr,
                volume_weighted_pcr=volume_weighted_pcr,
                net_premium=call_premium - put_premium,
                net_delta=self._calculate_net_delta(recent_flows),
                unusual_activity_count=unusual_count,
                large_trade_count=large_count,
                bullish_flow_score=bullish_score,
                bearish_flow_score=bearish_score
            )
            
        except Exception as e:
            self.logger.error(f"Error creating flow summary: {e}")
            return self._create_empty_summary()
            
    # ==========================================================================
    # UNUSUAL ACTIVITY DETECTION
    # ==========================================================================
    def detect_unusual_activity(self, 
                              current_flow: FlowMetrics,
                              threshold_multiplier: float = UNUSUAL_VOLUME_MULTIPLIER) -> Optional[Dict[str, Any]]:
        """
        Detect unusual options activity.
        
        Args:
            current_flow: Current flow metrics
            threshold_multiplier: Volume threshold multiplier
            
        Returns:
            Unusual activity details if detected
        """
        try:
            key = f"{current_flow.strike}_{current_flow.expiration}_{current_flow.option_type}"
            
            # Get average volume
            avg_volume = self.avg_volumes.get(key, 0)
            if avg_volume == 0:
                # Not enough history
                return None
                
            # Check volume spike
            if current_flow.volume > avg_volume * threshold_multiplier:
                # Check additional conditions
                oi_increasing = current_flow.oi_change > 0
                spread_tight = current_flow.bid_ask_spread < self._get_avg_spread(key) * 0.8
                
                return {
                    'type': 'VOLUME_SPIKE',
                    'strike': current_flow.strike,
                    'expiration': current_flow.expiration,
                    'option_type': current_flow.option_type,
                    'volume': current_flow.volume,
                    'avg_volume': avg_volume,
                    'multiplier': current_flow.volume / avg_volume,
                    'oi_increasing': oi_increasing,
                    'spread_tight': spread_tight,
                    'signal_strength': self._calculate_signal_strength(current_flow, avg_volume)
                }
                
            # Check OI spike
            if abs(current_flow.oi_change_pct) > OI_CHANGE_THRESHOLD * 100:
                return {
                    'type': 'OI_SPIKE',
                    'strike': current_flow.strike,
                    'expiration': current_flow.expiration,
                    'option_type': current_flow.option_type,
                    'oi_change': current_flow.oi_change,
                    'oi_change_pct': current_flow.oi_change_pct,
                    'volume': current_flow.volume,
                    'direction': 'BULLISH' if current_flow.oi_change > 0 else 'BEARISH'
                }
                
            return None
            
        except Exception as e:
            self.logger.error(f"Error detecting unusual activity: {e}")
            return None
            
    def identify_large_trades(self, 
                            min_size: int = 100,
                            min_premium: float = 50000) -> List[Dict[str, Any]]:
        """
        Identify large option trades.
        
        Args:
            min_size: Minimum contract size
            min_premium: Minimum premium value
            
        Returns:
            List of large trades
        """
        try:
            large_trades = []
            
            with self.lock:
                for flow in self.flow_history:
                    if flow.avg_trade_size >= min_size:
                        premium = flow.avg_trade_size * self._get_option_price(flow) * 100
                        
                        if premium >= min_premium:
                            large_trades.append({
                                'timestamp': flow.timestamp,
                                'strike': flow.strike,
                                'expiration': flow.expiration,
                                'option_type': flow.option_type,
                                'size': flow.avg_trade_size,
                                'premium': premium,
                                'likely_direction': self._infer_trade_direction(flow)
                            })
                            
            return sorted(large_trades, key=lambda x: x['premium'], reverse=True)
            
        except Exception as e:
            self.logger.error(f"Error identifying large trades: {e}")
            return []
            
    # ==========================================================================
    # VOLUME PROFILE ANALYSIS
    # ==========================================================================
    def calculate_volume_profile(self, 
                               price_range: Tuple[float, float],
                               bucket_size: float = 1.0) -> List[VolumeProfile]:
        """
        Calculate volume profile by price level.
        
        Args:
            price_range: (min_price, max_price) tuple
            bucket_size: Price bucket size
            
        Returns:
            List of volume profiles
        """
        try:
            profiles = []
            current_price = price_range[0]
            
            while current_price <= price_range[1]:
                # Aggregate volume at this price level
                call_vol, put_vol = self._aggregate_volume_at_price(current_price, bucket_size)
                
                if call_vol > 0 or put_vol > 0:
                    profile = VolumeProfile(
                        price_level=current_price,
                        call_volume=call_vol,
                        put_volume=put_vol,
                        net_delta=self._calculate_level_delta(current_price),
                        net_gamma=self._calculate_level_gamma(current_price),
                        trade_count=self._count_trades_at_price(current_price),
                        avg_trade_size=self._avg_trade_size_at_price(current_price),
                        institutional_volume=self._estimate_institutional_volume(current_price)
                    )
                    profiles.append(profile)
                    
                current_price += bucket_size
                
            return profiles
            
        except Exception as e:
            self.logger.error(f"Error calculating volume profile: {e}")
            return []
            
    def get_strike_flow_map(self) -> Dict[float, Dict[str, Any]]:
        """
        Get flow aggregated by strike price.
        
        Returns:
            Dictionary mapping strikes to flow data
        """
        try:
            strike_map = defaultdict(lambda: {
                'call_volume': 0,
                'put_volume': 0,
                'call_oi': 0,
                'put_oi': 0,
                'net_premium': 0,
                'pcr': 0,
                'trade_count': 0
            })
            
            with self.lock:
                for key, metrics in self.flow_cache.items():
                    strike = metrics.strike
                    
                    if metrics.option_type == 'CALL':
                        strike_map[strike]['call_volume'] += metrics.volume
                        strike_map[strike]['call_oi'] = metrics.open_interest
                    else:
                        strike_map[strike]['put_volume'] += metrics.volume
                        strike_map[strike]['put_oi'] = metrics.open_interest
                        
                    strike_map[strike]['trade_count'] += metrics.trade_count
                    
            # Calculate derived metrics
            for strike, data in strike_map.items():
                data['pcr'] = data['put_volume'] / max(data['call_volume'], 1)
                data['total_volume'] = data['call_volume'] + data['put_volume']
                data['oi_pcr'] = data['put_oi'] / max(data['call_oi'], 1)
                
            return dict(strike_map)
            
        except Exception as e:
            self.logger.error(f"Error creating strike flow map: {e}")
            return {}
            
    # ==========================================================================
    # FLOW PATTERN ANALYSIS
    # ==========================================================================
    def analyze_flow_pattern(self, 
                           time_window: int = 30) -> Dict[str, Any]:
        """
        Analyze flow patterns over time.
        
        Args:
            time_window: Minutes to analyze
            
        Returns:
            Flow pattern analysis
        """
        try:
            cutoff_time = datetime.now() - timedelta(minutes=time_window)
            
            with self.lock:
                recent_flows = [f for f in self.flow_history 
                               if f.timestamp > cutoff_time]
                
            if len(recent_flows) < 10:
                return {
                    'trend': 'INSUFFICIENT_DATA',
                    'momentum': 0.0,
                    'consistency': 0.0
                }
                
            # Analyze trend
            pcr_trend = self._analyze_pcr_trend(recent_flows)
            volume_trend = self._analyze_volume_trend(recent_flows)
            
            # Calculate momentum
            momentum = self._calculate_flow_momentum(recent_flows)
            
            # Calculate consistency
            consistency = self._calculate_flow_consistency(recent_flows)
            
            # Determine overall pattern
            if pcr_trend > 0.2 and momentum > 50:
                pattern = 'BEARISH_ACCUMULATION'
            elif pcr_trend < -0.2 and momentum > 50:
                pattern = 'BULLISH_ACCUMULATION'
            elif abs(momentum) < 20:
                pattern = 'NEUTRAL'
            else:
                pattern = 'MIXED'
                
            return {
                'trend': pattern,
                'pcr_trend': pcr_trend,
                'volume_trend': volume_trend,
                'momentum': momentum,
                'consistency': consistency,
                'key_levels': self._identify_key_flow_levels(recent_flows),
                'time_window': time_window
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing flow pattern: {e}")
            return {'trend': 'ERROR', 'momentum': 0.0, 'consistency': 0.0}
            
    # ==========================================================================
    # SIGNAL GENERATION
    # ==========================================================================
    def generate_flow_signals(self) -> List[FlowSignal]:
        """
        Generate trading signals based on flow analysis.
        
        Returns:
            List of flow-based trading signals
        """
        try:
            signals = []
            
            # Get recent summary
            summary = self.get_flow_summary(30)
            
            # Check for strong directional flow
            if summary.bullish_flow_score > 70:
                signals.append(FlowSignal(
                    timestamp=datetime.now(),
                    signal_type='BULLISH_FLOW',
                    strength=summary.bullish_flow_score,
                    strike=None,
                    expiration=None,
                    metrics={
                        'pcr': summary.put_call_ratio,
                        'net_premium': summary.net_premium,
                        'volume': summary.total_volume
                    },
                    action='BUY',
                    reason=f"Strong bullish flow detected: score {summary.bullish_flow_score:.1f}"
                ))
                
            elif summary.bearish_flow_score > 70:
                signals.append(FlowSignal(
                    timestamp=datetime.now(),
                    signal_type='BEARISH_FLOW',
                    strength=summary.bearish_flow_score,
                    strike=None,
                    expiration=None,
                    metrics={
                        'pcr': summary.put_call_ratio,
                        'net_premium': summary.net_premium,
                        'volume': summary.total_volume
                    },
                    action='SELL',
                    reason=f"Strong bearish flow detected: score {summary.bearish_flow_score:.1f}"
                ))
                
            # Check for unusual activity
            for key, metrics in self.flow_cache.items():
                unusual = self.detect_unusual_activity(metrics)
                if unusual and unusual['signal_strength'] > 60:
                    signals.append(FlowSignal(
                        timestamp=datetime.now(),
                        signal_type='UNUSUAL_ACTIVITY',
                        strength=unusual['signal_strength'],
                        strike=metrics.strike,
                        expiration=metrics.expiration,
                        metrics=unusual,
                        action='MONITOR',
                        reason=f"Unusual {unusual['type']} at {metrics.strike} strike"
                    ))
                    
            return signals
            
        except Exception as e:
            self.logger.error(f"Error generating flow signals: {e}")
            return []
            
    # ==========================================================================
    # MONITORING
    # ==========================================================================
    def start_monitoring(self, update_interval: int = UPDATE_INTERVAL) -> None:
        """
        Start real-time flow monitoring.
        
        Args:
            update_interval: Seconds between updates
        """
        if self.running:
            self.logger.warning("Flow monitoring already running")
            return
            
        self.running = True
        self.monitor_thread = Thread(
            target=self._monitor_loop,
            args=(update_interval,),
            daemon=True
        )
        self.monitor_thread.start()
        self.logger.info("Flow monitoring started")
        
    def stop_monitoring(self) -> None:
        """Stop flow monitoring."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("Flow monitoring stopped")
        
    def _monitor_loop(self, update_interval: int) -> None:
        """
        Main monitoring loop.
        
        Args:
            update_interval: Seconds between updates
        """
        while self.running:
            try:
                # Get latest option chain
                chain_data = self.data_feed.get_options_chain(self.symbol)
                
                if chain_data:
                    # Track flow for each option
                    for _, option in chain_data.iterrows():
                        metrics = self.track_flow(option.to_dict())
                        
                        # Check for unusual activity
                        unusual = self.detect_unusual_activity(metrics)
                        if unusual:
                            self._emit_unusual_activity_event(unusual)
                            
                    # Generate and emit signals
                    signals = self.generate_flow_signals()
                    for signal in signals:
                        self._emit_signal_event(signal)
                        
                    # Update statistics
                    self._update_statistics()
                    
                time.sleep(update_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
                time.sleep(update_interval)
                
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _get_previous_oi(self, key: str) -> int:
        """Get previous open interest for comparison."""
        history = self.oi_history.get(key, [])
        return history[-2] if len(history) >= 2 else 0
        
    def _estimate_bid_volume(self, option_data: Dict[str, Any]) -> int:
        """Estimate volume at bid (sells)."""
        # Simplified estimation - in practice would use trade tape
        if option_data.get('last_price', 0) <= option_data['bid']:
            return int(option_data['volume'] * 0.7)
        return int(option_data['volume'] * 0.2)
        
    def _estimate_ask_volume(self, option_data: Dict[str, Any]) -> int:
        """Estimate volume at ask (buys)."""
        # Simplified estimation - in practice would use trade tape
        if option_data.get('last_price', 0) >= option_data['ask']:
            return int(option_data['volume'] * 0.7)
        return int(option_data['volume'] * 0.2)
        
    def _count_large_trades(self, option_data: Dict[str, Any]) -> int:
        """Count number of large trades."""
        # Simplified - would use actual trade data
        avg_size = option_data['volume'] / max(option_data.get('trade_count', 1), 1)
        if avg_size > 100:
            return max(1, option_data.get('trade_count', 0) // 10)
        return 0
        
    def _get_option_price(self, metrics: FlowMetrics) -> float:
        """Get current option price."""
        # Simplified - would get from market data
        key = f"{metrics.strike}_{metrics.expiration}_{metrics.option_type}"
        return self.flow_cache.get(key, metrics).bid_ask_spread / 2 + 1.0
        
    def _is_unusual_activity(self, metrics: FlowMetrics) -> bool:
        """Check if flow represents unusual activity."""
        key = f"{metrics.strike}_{metrics.expiration}_{metrics.option_type}"
        avg_vol = self.avg_volumes.get(key, metrics.volume)
        return metrics.volume > avg_vol * UNUSUAL_VOLUME_MULTIPLIER
        
    def _calculate_bullish_score(self, flows: List[FlowMetrics]) -> float:
        """Calculate bullish flow score (0-100)."""
        if not flows:
            return 50.0
            
        # Factors: call/put ratio, OI changes, ask volume
        call_vol = sum(f.volume for f in flows if f.option_type == 'CALL')
        put_vol = sum(f.volume for f in flows if f.option_type == 'PUT')
        
        # Volume ratio component (40%)
        vol_ratio = call_vol / max(call_vol + put_vol, 1)
        vol_score = vol_ratio * 40
        
        # OI change component (30%)
        call_oi_change = sum(f.oi_change for f in flows if f.option_type == 'CALL' and f.oi_change > 0)
        put_oi_change = sum(f.oi_change for f in flows if f.option_type == 'PUT' and f.oi_change > 0)
        oi_ratio = call_oi_change / max(call_oi_change + put_oi_change, 1)
        oi_score = oi_ratio * 30
        
        # Buy pressure component (30%)
        call_ask_vol = sum(f.ask_volume for f in flows if f.option_type == 'CALL')
        put_bid_vol = sum(f.bid_volume for f in flows if f.option_type == 'PUT')
        buy_pressure = (call_ask_vol + put_bid_vol) / max(sum(f.volume for f in flows), 1)
        buy_score = buy_pressure * 30
        
        return min(100, vol_score + oi_score + buy_score)
        
    def _calculate_bearish_score(self, flows: List[FlowMetrics]) -> float:
        """Calculate bearish flow score (0-100)."""
        if not flows:
            return 50.0
            
        # Inverse of bullish score with put emphasis
        call_vol = sum(f.volume for f in flows if f.option_type == 'CALL')
        put_vol = sum(f.volume for f in flows if f.option_type == 'PUT')
        
        # Volume ratio component (40%)
        vol_ratio = put_vol / max(call_vol + put_vol, 1)
        vol_score = vol_ratio * 40
        
        # OI change component (30%)
        put_oi_change = sum(f.oi_change for f in flows if f.option_type == 'PUT' and f.oi_change > 0)
        call_oi_change = sum(f.oi_change for f in flows if f.option_type == 'CALL' and f.oi_change > 0)
        oi_ratio = put_oi_change / max(call_oi_change + put_oi_change, 1)
        oi_score = oi_ratio * 30
        
        # Sell pressure component (30%)
        put_ask_vol = sum(f.ask_volume for f in flows if f.option_type == 'PUT')
        call_bid_vol = sum(f.bid_volume for f in flows if f.option_type == 'CALL')
        sell_pressure = (put_ask_vol + call_bid_vol) / max(sum(f.volume for f in flows), 1)
        sell_score = sell_pressure * 30
        
        return min(100, vol_score + oi_score + sell_score)
        
    def _calculate_net_delta(self, flows: List[FlowMetrics]) -> float:
        """Calculate net delta flow."""
        # Simplified - would use actual Greeks
        call_delta = sum(f.volume * 0.5 for f in flows if f.option_type == 'CALL')
        put_delta = sum(f.volume * -0.5 for f in flows if f.option_type == 'PUT')
        return call_delta + put_delta
        
    def _get_avg_spread(self, key: str) -> float:
        """Get average bid-ask spread."""
        if key in self.flow_cache:
            return self.flow_cache[key].bid_ask_spread
        return 0.05  # Default
        
    def _calculate_signal_strength(self, flow: FlowMetrics, avg_volume: float) -> float:
        """Calculate signal strength (0-100)."""
        # Volume component
        vol_mult = flow.volume / max(avg_volume, 1)
        vol_score = min(50, vol_mult * 10)
        
        # OI component
        oi_score = min(30, abs(flow.oi_change_pct))
        
        # Spread component (tighter = stronger)
        spread_score = max(0, 20 - flow.bid_ask_spread * 100)
        
        return vol_score + oi_score + spread_score
        
    def _infer_trade_direction(self, flow: FlowMetrics) -> str:
        """Infer likely trade direction."""
        if flow.ask_volume > flow.bid_volume * 1.5:
            return 'BUY'
        elif flow.bid_volume > flow.ask_volume * 1.5:
            return 'SELL'
        else:
            return 'NEUTRAL'
            
    def _aggregate_volume_at_price(self, price: float, bucket_size: float) -> Tuple[int, int]:
        """Aggregate volume at price level."""
        call_vol = 0
        put_vol = 0
        
        with self.lock:
            for metrics in self.flow_cache.values():
                if abs(metrics.strike - price) <= bucket_size / 2:
                    if metrics.option_type == 'CALL':
                        call_vol += metrics.volume
                    else:
                        put_vol += metrics.volume
                        
        return call_vol, put_vol
        
    def _calculate_level_delta(self, price: float) -> float:
        """Calculate net delta at price level."""
        # Simplified calculation
        return 0.0
        
    def _calculate_level_gamma(self, price: float) -> float:
        """Calculate net gamma at price level."""
        # Simplified calculation
        return 0.0
        
    def _count_trades_at_price(self, price: float) -> int:
        """Count trades at price level."""
        count = 0
        with self.lock:
            for metrics in self.flow_cache.values():
                if abs(metrics.strike - price) <= 0.5:
                    count += metrics.trade_count
        return count
        
    def _avg_trade_size_at_price(self, price: float) -> float:
        """Average trade size at price level."""
        sizes = []
        with self.lock:
            for metrics in self.flow_cache.values():
                if abs(metrics.strike - price) <= 0.5:
                    sizes.append(metrics.avg_trade_size)
        return sum(sizes) / len(sizes) if sizes else 0
        
    def _estimate_institutional_volume(self, price: float) -> int:
        """Estimate institutional volume at price."""
        # Large trades likely institutional
        inst_vol = 0
        with self.lock:
            for metrics in self.flow_cache.values():
                if abs(metrics.strike - price) <= 0.5 and metrics.avg_trade_size > 50:
                    inst_vol += int(metrics.volume * 0.7)
        return inst_vol
        
    def _analyze_pcr_trend(self, flows: List[FlowMetrics]) -> float:
        """Analyze put/call ratio trend."""
        if len(flows) < 5:
            return 0.0
            
        # Calculate PCR over time windows
        pcr_values = []
        window_size = len(flows) // 5
        
        for i in range(0, len(flows) - window_size, window_size):
            window = flows[i:i + window_size]
            call_vol = sum(f.volume for f in window if f.option_type == 'CALL')
            put_vol = sum(f.volume for f in window if f.option_type == 'PUT')
            pcr = put_vol / max(call_vol, 1)
            pcr_values.append(pcr)
            
        # Calculate trend
        if len(pcr_values) >= 2:
            return (pcr_values[-1] - pcr_values[0]) / len(pcr_values)
        return 0.0
        
    def _analyze_volume_trend(self, flows: List[FlowMetrics]) -> float:
        """Analyze volume trend."""
        if len(flows) < 5:
            return 0.0
            
        # Simple linear regression on volume
        volumes = [f.volume for f in flows]
        x = np.arange(len(volumes))
        
        # Calculate slope
        if len(volumes) > 1:
            slope = np.polyfit(x, volumes, 1)[0]
            avg_vol = np.mean(volumes)
            return slope / max(avg_vol, 1)  # Normalized slope
        return 0.0
        
    def _calculate_flow_momentum(self, flows: List[FlowMetrics]) -> float:
        """Calculate flow momentum (-100 to 100)."""
        if not flows:
            return 0.0
            
        # Recent vs older flow comparison
        mid = len(flows) // 2
        recent = flows[mid:]
        older = flows[:mid]
        
        recent_bull = self._calculate_bullish_score(recent)
        older_bull = self._calculate_bullish_score(older)
        
        momentum = recent_bull - older_bull
        return max(-100, min(100, momentum * 2))
        
    def _calculate_flow_consistency(self, flows: List[FlowMetrics]) -> float:
        """Calculate flow consistency (0-100)."""
        if len(flows) < 10:
            return 0.0
            
        # Check directional consistency
        pcr_values = []
        for i in range(0, len(flows), 5):
            window = flows[i:i + 5]
            call_vol = sum(f.volume for f in window if f.option_type == 'CALL')
            put_vol = sum(f.volume for f in window if f.option_type == 'PUT')
            pcr = put_vol / max(call_vol + put_vol, 1)
            pcr_values.append(pcr)
            
        # Calculate standard deviation
        if pcr_values:
            std_dev = np.std(pcr_values)
            # Lower std dev = higher consistency
            consistency = max(0, 100 - std_dev * 200)
            return consistency
        return 50.0
        
    def _identify_key_flow_levels(self, flows: List[FlowMetrics]) -> List[float]:
        """Identify key price levels with high flow."""
        strike_volumes = defaultdict(int)
        
        for flow in flows:
            strike_volumes[flow.strike] += flow.volume
            
        # Sort by volume and return top strikes
        sorted_strikes = sorted(strike_volumes.items(), 
                               key=lambda x: x[1], 
                               reverse=True)
        
        return [strike for strike, _ in sorted_strikes[:5]]
        
    def _update_statistics(self) -> None:
        """Update running statistics."""
        with self.lock:
            for key, metrics in self.flow_cache.items():
                # Update average volume
                if key in self.avg_volumes:
                    self.avg_volumes[key] = self.avg_volumes[key] * 0.95 + metrics.volume * 0.05
                else:
                    self.avg_volumes[key] = metrics.volume
                    
                # Update average OI
                if key in self.avg_oi:
                    self.avg_oi[key] = self.avg_oi[key] * 0.95 + metrics.open_interest * 0.05
                else:
                    self.avg_oi[key] = metrics.open_interest
                    
    def _emit_unusual_activity_event(self, activity: Dict[str, Any]) -> None:
        """Emit unusual activity event."""
        event = Event(
            'flow.unusual_activity',
            {
                'symbol': self.symbol,
                'activity': activity,
                'timestamp': datetime.now()
            }
        )
        self.event_manager.emit(event)
        
    def _emit_signal_event(self, signal: FlowSignal) -> None:
        """Emit flow signal event."""
        event = Event(
            'flow.signal',
            {
                'symbol': self.symbol,
                'signal': signal,
                'timestamp': signal.timestamp
            }
        )
        self.event_manager.emit(event)
        
    def _create_empty_metrics(self) -> FlowMetrics:
        """Create empty flow metrics."""
        return FlowMetrics(
            timestamp=datetime.now(),
            symbol=self.symbol,
            strike=0.0,
            expiration=datetime.now(),
            option_type='CALL',
            volume=0,
            open_interest=0,
            oi_change=0,
            oi_change_pct=0.0,
            bid_ask_spread=0.0,
            trade_count=0,
            avg_trade_size=0.0,
            large_trades=0,
            bid_volume=0,
            ask_volume=0,
            mid_volume=0
        )
        
    def _create_empty_summary(self) -> FlowSummary:
        """Create empty flow summary."""
        return FlowSummary(
            timestamp=datetime.now(),
            total_volume=0,
            call_volume=0,
            put_volume=0,
            put_call_ratio=1.0,
            volume_weighted_pcr=1.0,
            net_premium=0.0,
            net_delta=0.0,
            unusual_activity_count=0,
            large_trade_count=0,
            bullish_flow_score=50.0,
            bearish_flow_score=50.0
        )

# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    'FlowAnalyzer',
    'FlowMetrics',
    'FlowSummary',
    'VolumeProfile',
    'FlowSignal'
]

# ==============================================================================
# USAGE EXAMPLE
# ==============================================================================
if __name__ == "__main__":
    # Initialize analyzer
    analyzer = FlowAnalyzer("SPY")
    
    # Start monitoring
    analyzer.start_monitoring(update_interval=5)
    
    print("=== SPYDER Flow Analyzer ===")
    print("Monitoring options flow...")
    
    # Let it run for a bit
    time.sleep(30)
    
    # Get flow summary
    summary = analyzer.get_flow_summary(lookback_minutes=30)
    print(f"\n📊 Flow Summary:")
    print(f"Total Volume: {summary.total_volume:,}")
    print(f"Call Volume: {summary.call_volume:,}")
    print(f"Put Volume: {summary.put_volume:,}")
    print(f"Put/Call Ratio: {summary.put_call_ratio:.2f}")
    print(f"Bullish Score: {summary.bullish_flow_score:.1f}")
    print(f"Bearish Score: {summary.bearish_flow_score:.1f}")
    
    # Get large trades
    large_trades = analyzer.identify_large_trades()
    if large_trades:
        print(f"\n💰 Large Trades: {len(large_trades)}")
        for trade in large_trades[:3]:
            print(f"  {trade['strike']} {trade['option_type']} - "
                  f"Size: {trade['size']}, Premium: ${trade['premium']:,.0f}")
            
    # Get flow signals
    signals = analyzer.generate_flow_signals()
    if signals:
        print(f"\n📡 Flow Signals:")
        for signal in signals:
            print(f"  {signal.signal_type}: {signal.reason}")
            print(f"  Strength: {signal.strength:.1f}, Action: {signal.action}")
            
    # Get volume profile
    profiles = analyzer.calculate_volume_profile((430, 450), 5.0)
    if profiles:
        print(f"\n📈 Volume Profile:")
        for profile in profiles[:5]:
            print(f"  ${profile.price_level}: "
                  f"Calls: {profile.call_volume:,}, "
                  f"Puts: {profile.put_volume:,}")
            
    # Stop monitoring
    analyzer.stop_monitoring()
    print("\n✅ Flow monitoring stopped")