#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderN09_GammaExposure.py
Group: N (Options Analytics)
Purpose: Real-time Gamma Exposure (GEX) calculation and analysis

Description:
    This module calculates real-time gamma exposure (GEX) using OPRA data feeds
    to identify key market maker hedging levels. It provides institutional-grade
    GEX calculations, identifies gamma flip points, and generates actionable
    trading signals based on dealer positioning. The module integrates with
    existing OPRA handlers for ultra-low latency calculations.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-06-28
Last Updated: 2025-06-28 Time: 17:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import json
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum, auto
import bisect

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import seaborn as sns
from scipy import interpolate
from scipy.stats import norm

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU07_Constants import OptionType
from Spyder.SpyderN_OptionsAnalytics.SpyderN07_OPRAGreeksHandler import OPRAGreeksHandler
from Spyder.SpyderC_MarketData.SpyderC03_OptionChain import OptionChainManager
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

# ==============================================================================
# CONSTANTS
# ==============================================================================
# GEX Calculation Parameters
SPOT_RANGE_PERCENTAGE = 0.20  # Calculate GEX for +/- 20% of spot
SPOT_INCREMENTS = 0.50  # $0.50 increments for GEX profile
MIN_OPEN_INTEREST = 100  # Minimum OI to include in calculations
MIN_GAMMA = 0.0001  # Minimum gamma threshold

# Market Maker Assumptions
DEALER_CALL_POSITION = -1  # Dealers typically short calls
DEALER_PUT_POSITION = 1   # Dealers typically long puts
MM_HEDGE_RATIO = 1.0  # Assume 100% hedging

# Update Frequencies
GEX_UPDATE_INTERVAL = 60  # Full GEX update every 60 seconds
FLIP_CHECK_INTERVAL = 5   # Check flip points every 5 seconds
PROFILE_UPDATE_INTERVAL = 300  # Update full profile every 5 minutes

# Alert Thresholds
HIGH_GEX_THRESHOLD = 1000000000  # $1B in gamma exposure
FLIP_PROXIMITY_ALERT = 5.0  # Alert when within $5 of flip
VOLATILITY_SUPPRESSION_LEVEL = 0.5e9  # $500M GEX suppresses volatility

# Historical Tracking
HISTORY_DAYS = 20  # Keep 20 days of GEX history
INTRADAY_POINTS = 78  # Store every 5 minutes (6.5 hours * 12)

# ==============================================================================
# ENUMS
# ==============================================================================
class GEXRegime(Enum):
    """Market regime based on gamma exposure"""
    HIGH_POSITIVE = "high_positive"  # Volatility suppression
    MODERATE_POSITIVE = "moderate_positive"  # Normal hedging
    NEAR_FLIP = "near_flip"  # Close to gamma flip
    NEGATIVE = "negative"  # Volatility expansion
    EXTREME_NEGATIVE = "extreme_negative"  # Potential squeeze

class HedgingFlow(Enum):
    """Expected dealer hedging flow"""
    STRONG_BUYING = "strong_buying"
    MODERATE_BUYING = "moderate_buying"
    NEUTRAL = "neutral"
    MODERATE_SELLING = "moderate_selling"
    STRONG_SELLING = "strong_selling"

class GEXSignal(Enum):
    """Trading signals from GEX analysis"""
    VOLATILITY_SUPPRESSED = "volatility_suppressed"  # Sell volatility
    APPROACHING_FLIP = "approaching_flip"  # Prepare for volatility
    NEGATIVE_GEX_SQUEEZE = "negative_gex_squeeze"  # Potential rally
    HEDGING_FLOW_BUY = "hedging_flow_buy"  # Join dealer buying
    HEDGING_FLOW_SELL = "hedging_flow_sell"  # Join dealer selling
    NEUTRAL = "neutral"  # No clear signal

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class GEXPoint:
    """Gamma exposure at a specific price level"""
    price: float
    total_gamma: float
    call_gamma: float
    put_gamma: float
    net_gamma: float  # Dealer perspective
    timestamp: datetime

@dataclass
class GEXProfile:
    """Complete gamma exposure profile"""
    timestamp: datetime
    spot_price: float
    current_gex: float  # GEX at current spot
    
    # Profile data
    price_levels: np.ndarray
    gamma_exposure: np.ndarray
    call_gamma: np.ndarray
    put_gamma: np.ndarray
    
    # Key levels
    zero_gamma_level: Optional[float]  # Gamma flip point
    max_gamma_level: float
    max_gamma_value: float
    
    # Regime information
    regime: GEXRegime
    expected_flow: HedgingFlow
    
    # Statistics
    total_gamma_notional: float
    weighted_average_gamma: float
    gamma_concentration: float  # How concentrated is gamma

@dataclass
class GEXMetrics:
    """Key GEX metrics and analytics"""
    current_gex: float
    prev_close_gex: float
    gex_change: float
    gex_change_pct: float
    
    # Intraday metrics
    intraday_high: float
    intraday_low: float
    avg_gex_5d: float
    avg_gex_20d: float
    
    # Volatility relationship
    expected_volatility: float  # Based on GEX level
    volatility_regime: str
    
    # Key levels
    nearest_flip: Optional[float]
    distance_to_flip: Optional[float]
    major_gamma_levels: List[float]  # High gamma strikes
    
    # Flow metrics
    expected_hedging_flow: float  # Dollar amount
    flow_direction: HedgingFlow

@dataclass
class DealerPositioning:
    """Estimated dealer positioning"""
    timestamp: datetime
    total_delta_exposure: float
    total_gamma_exposure: float
    total_vega_exposure: float
    
    # By expiration
    gamma_by_expiry: Dict[date, float]
    delta_by_expiry: Dict[date, float]
    
    # Hedging needs
    delta_to_hedge: float
    expected_hedge_direction: str
    hedge_urgency: str  # 'immediate', 'moderate', 'low'

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class GammaExposureCalculator:
    """
    Professional gamma exposure (GEX) calculator.
    
    This class provides institutional-grade GEX calculations using real-time
    OPRA data. It identifies key market maker hedging levels, gamma flip points,
    and generates actionable trading signals based on dealer positioning.
    
    Attributes:
        opra_handler: OPRA Greeks data handler
        logger: Module logger
        current_profile: Current GEX profile
        historical_gex: Historical GEX data
        
    Example:
        >>> gex_calc = GammaExposureCalculator()
        >>> profile = gex_calc.calculate_gex_profile()
        >>> print(f"Current GEX: ${profile.current_gex:,.0f}")
        >>> print(f"Gamma Flip: ${profile.zero_gamma_level:.2f}")
    """
    
    def __init__(self, 
                 opra_handler: Optional[OPRAGreeksHandler] = None,
                 option_chain_mgr: Optional[OptionChainManager] = None):
        """
        Initialize GEX calculator.
        
        Args:
            opra_handler: OPRA Greeks handler for real-time data
            option_chain_mgr: Option chain manager for market data
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Data sources
        self.opra_handler = opra_handler or OPRAGreeksHandler()
        self.option_chain_mgr = option_chain_mgr or OptionChainManager()
        self.event_manager = get_event_manager()
        
        # Current state
        self.current_profile: Optional[GEXProfile] = None
        self.current_metrics: Optional[GEXMetrics] = None
        self.dealer_positioning: Optional[DealerPositioning] = None
        
        # Historical tracking
        self.historical_gex: deque = deque(maxlen=HISTORY_DAYS * INTRADAY_POINTS)
        self.flip_history: deque = deque(maxlen=100)
        self.regime_history: deque = deque(maxlen=1000)
        
        # Caching
        self._gamma_cache: Dict[str, float] = {}
        self._profile_cache: Optional[GEXProfile] = None
        self._cache_timestamp: Optional[datetime] = None
        
        # Threading
        self._lock = threading.RLock()
        self._update_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Performance tracking
        self.calculation_times: deque = deque(maxlen=100)
        self.last_update_time: Optional[datetime] = None
        
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    # ==========================================================================
    # PUBLIC METHODS - MAIN CALCULATIONS
    # ==========================================================================
    
    def calculate_gex_profile(self, 
                            spot_price: Optional[float] = None,
                            expiries: Optional[List[date]] = None) -> GEXProfile:
        """
        Calculate complete gamma exposure profile.
        
        Args:
            spot_price: Current spot price (uses latest if None)
            expiries: List of expiries to include (uses all if None)
            
        Returns:
            Complete GEX profile with all metrics
        """
        start_time = time.time()
        
        try:
            # Check cache first
            if self._is_cache_valid():
                return self._profile_cache
            
            # Get current spot price
            if spot_price is None:
                spot_price = self._get_spot_price()
            
            # Get option chain data
            if expiries is None:
                expiries = self._get_active_expiries()
            
            # Calculate price range for analysis
            price_range = self._calculate_price_range(spot_price)
            
            # Initialize arrays
            n_points = len(price_range)
            total_gamma = np.zeros(n_points)
            call_gamma = np.zeros(n_points)
            put_gamma = np.zeros(n_points)
            
            # Calculate gamma exposure at each price level
            for i, price_level in enumerate(price_range):
                for expiry in expiries:
                    # Get options data for this expiry
                    chain_data = self._get_option_chain(expiry)
                    if chain_data is None:
                        continue
                    
                    # Calculate gamma contribution at this price
                    level_gamma = self._calculate_gamma_at_price(
                        price_level, spot_price, expiry, chain_data
                    )
                    
                    total_gamma[i] += level_gamma['total']
                    call_gamma[i] += level_gamma['calls']
                    put_gamma[i] += level_gamma['puts']
            
            # Find key levels
            zero_gamma = self._find_zero_gamma_level(price_range, total_gamma)
            max_gamma_idx = np.argmax(np.abs(total_gamma))
            max_gamma_level = price_range[max_gamma_idx]
            max_gamma_value = total_gamma[max_gamma_idx]
            
            # Determine regime
            current_gex = np.interp(spot_price, price_range, total_gamma)
            regime = self._determine_regime(current_gex, zero_gamma, spot_price)
            
            # Expected hedging flow
            expected_flow = self._calculate_expected_flow(
                spot_price, price_range, total_gamma
            )
            
            # Create profile
            profile = GEXProfile(
                timestamp=datetime.now(),
                spot_price=spot_price,
                current_gex=current_gex,
                price_levels=price_range,
                gamma_exposure=total_gamma,
                call_gamma=call_gamma,
                put_gamma=put_gamma,
                zero_gamma_level=zero_gamma,
                max_gamma_level=max_gamma_level,
                max_gamma_value=max_gamma_value,
                regime=regime,
                expected_flow=expected_flow,
                total_gamma_notional=np.sum(np.abs(total_gamma)),
                weighted_average_gamma=self._calculate_weighted_gamma(
                    price_range, total_gamma, spot_price
                ),
                gamma_concentration=self._calculate_concentration(total_gamma)
            )
            
            # Update state
            with self._lock:
                self.current_profile = profile
                self._profile_cache = profile
                self._cache_timestamp = datetime.now()
                
                # Track history
                self.historical_gex.append({
                    'timestamp': profile.timestamp,
                    'spot': spot_price,
                    'gex': current_gex,
                    'flip': zero_gamma,
                    'regime': regime.value
                })
            
            # Calculate metrics
            self.current_metrics = self._calculate_metrics(profile)
            
            # Track calculation time
            calc_time = time.time() - start_time
            self.calculation_times.append(calc_time)
            
            self.logger.debug(f"GEX profile calculated in {calc_time:.3f}s")
            
            # Emit update event
            self._emit_gex_update(profile)
            
            return profile
            
        except Exception as e:
            self.logger.error(f"Error calculating GEX profile: {e}")
            self.error_handler.handle_error(e)
            raise
    
    def get_gamma_flip_points(self, 
                            num_days: int = 5) -> List[Dict[str, Any]]:
        """
        Get historical and current gamma flip points.
        
        Args:
            num_days: Number of days of history to return
            
        Returns:
            List of gamma flip points with metadata
        """
        flip_points = []
        
        # Current flip point
        if self.current_profile and self.current_profile.zero_gamma_level:
            flip_points.append({
                'timestamp': self.current_profile.timestamp,
                'flip_level': self.current_profile.zero_gamma_level,
                'current_spot': self.current_profile.spot_price,
                'distance': self.current_profile.spot_price - self.current_profile.zero_gamma_level,
                'regime': self.current_profile.regime.value,
                'is_current': True
            })
        
        # Historical flip points
        cutoff_date = datetime.now() - timedelta(days=num_days)
        for flip in self.flip_history:
            if flip['timestamp'] > cutoff_date:
                flip_points.append(flip)
        
        return sorted(flip_points, key=lambda x: x['timestamp'], reverse=True)
    
    def get_major_gamma_levels(self, 
                             threshold_pct: float = 0.1) -> List[Dict[str, Any]]:
        """
        Get price levels with significant gamma concentration.
        
        Args:
            threshold_pct: Minimum % of total gamma to be considered major
            
        Returns:
            List of major gamma levels with details
        """
        if not self.current_profile:
            return []
        
        levels = []
        total_gamma = np.sum(np.abs(self.current_profile.gamma_exposure))
        threshold = total_gamma * threshold_pct
        
        # Find peaks in gamma exposure
        for i in range(1, len(self.current_profile.price_levels) - 1):
            gamma = abs(self.current_profile.gamma_exposure[i])
            
            # Check if local maximum and above threshold
            if (gamma > threshold and 
                gamma > abs(self.current_profile.gamma_exposure[i-1]) and
                gamma > abs(self.current_profile.gamma_exposure[i+1])):
                
                levels.append({
                    'price': self.current_profile.price_levels[i],
                    'gamma': self.current_profile.gamma_exposure[i],
                    'gamma_pct': gamma / total_gamma,
                    'type': 'resistance' if self.current_profile.gamma_exposure[i] > 0 else 'support',
                    'distance_from_spot': self.current_profile.price_levels[i] - self.current_profile.spot_price
                })
        
        return sorted(levels, key=lambda x: abs(x['gamma']), reverse=True)
    
    def analyze_dealer_positioning(self) -> DealerPositioning:
        """
        Analyze estimated dealer positioning and hedging needs.
        
        Returns:
            Dealer positioning analysis
        """
        try:
            # Get current Greeks from OPRA
            portfolio_greeks = self.opra_handler.calculate_portfolio_greeks()
            
            # Estimate dealer exposure (opposite of retail)
            dealer_delta = -portfolio_greeks.total_delta * 100  # Per contract
            dealer_gamma = -portfolio_greeks.total_gamma * 100
            dealer_vega = -portfolio_greeks.total_vega * 100
            
            # Get exposures by expiry
            gamma_by_expiry = {}
            delta_by_expiry = {}
            
            for expiry in self._get_active_expiries():
                expiry_greeks = self._calculate_expiry_exposure(expiry)
                gamma_by_expiry[expiry] = expiry_greeks['gamma']
                delta_by_expiry[expiry] = expiry_greeks['delta']
            
            # Calculate hedging needs
            spot_price = self._get_spot_price()
            delta_to_hedge = dealer_delta
            
            # Determine urgency based on gamma
            if abs(dealer_gamma) > 100000:
                urgency = 'immediate'
            elif abs(dealer_gamma) > 50000:
                urgency = 'moderate'
            else:
                urgency = 'low'
            
            positioning = DealerPositioning(
                timestamp=datetime.now(),
                total_delta_exposure=dealer_delta,
                total_gamma_exposure=dealer_gamma,
                total_vega_exposure=dealer_vega,
                gamma_by_expiry=gamma_by_expiry,
                delta_by_expiry=delta_by_expiry,
                delta_to_hedge=delta_to_hedge,
                expected_hedge_direction='BUY' if delta_to_hedge > 0 else 'SELL',
                hedge_urgency=urgency
            )
            
            self.dealer_positioning = positioning
            return positioning
            
        except Exception as e:
            self.logger.error(f"Error analyzing dealer positioning: {e}")
            self.error_handler.handle_error(e)
            raise
    
    # ==========================================================================
    # PUBLIC METHODS - SIGNALS AND ANALYSIS
    # ==========================================================================
    
    def generate_trading_signals(self) -> List[Dict[str, Any]]:
        """
        Generate trading signals based on GEX analysis.
        
        Returns:
            List of actionable trading signals
        """
        signals = []
        
        if not self.current_profile or not self.current_metrics:
            return signals
        
        spot = self.current_profile.spot_price
        gex = self.current_profile.current_gex
        
        # Signal 1: Volatility suppression
        if gex > VOLATILITY_SUPPRESSION_LEVEL:
            signals.append({
                'signal': GEXSignal.VOLATILITY_SUPPRESSED,
                'strength': min(gex / (2 * VOLATILITY_SUPPRESSION_LEVEL), 1.0),
                'action': 'SELL_VOLATILITY',
                'reason': f'High positive GEX (${gex/1e9:.1f}B) suppressing volatility',
                'suggested_trades': [
                    'Sell ATM straddles',
                    'Short VIX calls',
                    'Iron condors with tight strikes'
                ]
            })
        
        # Signal 2: Approaching gamma flip
        if self.current_metrics.distance_to_flip and abs(self.current_metrics.distance_to_flip) < FLIP_PROXIMITY_ALERT:
            signals.append({
                'signal': GEXSignal.APPROACHING_FLIP,
                'strength': 1.0 - abs(self.current_metrics.distance_to_flip) / FLIP_PROXIMITY_ALERT,
                'action': 'PREPARE_FOR_VOLATILITY',
                'reason': f'Within ${abs(self.current_metrics.distance_to_flip):.2f} of gamma flip',
                'suggested_trades': [
                    'Buy straddles/strangles',
                    'Reduce short volatility',
                    'Consider protective puts'
                ]
            })
        
        # Signal 3: Negative GEX squeeze potential
        if self.current_profile.regime == GEXRegime.NEGATIVE:
            signals.append({
                'signal': GEXSignal.NEGATIVE_GEX_SQUEEZE,
                'strength': min(abs(gex) / VOLATILITY_SUPPRESSION_LEVEL, 1.0),
                'action': 'POSITION_FOR_SQUEEZE',
                'reason': f'Negative GEX (${gex/1e9:.1f}B) could fuel rally',
                'suggested_trades': [
                    'Buy calls on dips',
                    'Call spreads',
                    'Avoid shorts'
                ]
            })
        
        # Signal 4: Hedging flow opportunities
        if self.current_profile.expected_flow in [HedgingFlow.STRONG_BUYING, HedgingFlow.STRONG_SELLING]:
            flow_direction = 'BUYING' if 'BUYING' in self.current_profile.expected_flow.value else 'SELLING'
            signals.append({
                'signal': GEXSignal.HEDGING_FLOW_BUY if flow_direction == 'BUYING' else GEXSignal.HEDGING_FLOW_SELL,
                'strength': 0.8,
                'action': f'JOIN_DEALER_{flow_direction}',
                'reason': f'Expected strong dealer {flow_direction.lower()}',
                'suggested_trades': [
                    f'{"Buy" if flow_direction == "BUYING" else "Sell"} SPY with stops',
                    'Use options to define risk',
                    'Monitor for exhaustion'
                ]
            })
        
        return signals
    
    def get_intraday_profile(self) -> pd.DataFrame:
        """
        Get intraday GEX profile as DataFrame.
        
        Returns:
            DataFrame with intraday GEX data
        """
        if not self.historical_gex:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(list(self.historical_gex))
        
        # Filter to today only
        today = datetime.now().date()
        df['date'] = pd.to_datetime(df['timestamp']).dt.date
        df = df[df['date'] == today].copy()
        
        # Add calculated fields
        if len(df) > 0:
            df['gex_change'] = df['gex'].diff()
            df['flip_change'] = df['flip'].diff()
            df['volatility_regime'] = df['regime'].map(lambda x: 'suppressed' if 'positive' in x else 'elevated')
        
        return df
    
    # ==========================================================================
    # PRIVATE METHODS - CALCULATIONS
    # ==========================================================================
    
    def _calculate_gamma_at_price(self, 
                                price_level: float,
                                spot_price: float,
                                expiry: date,
                                chain_data: pd.DataFrame) -> Dict[str, float]:
        """Calculate gamma exposure at specific price level."""
        total_gamma = 0.0
        call_gamma = 0.0
        put_gamma = 0.0
        
        # Time to expiry
        dte = (expiry - date.today()).days / 365.0
        if dte <= 0:
            return {'total': 0, 'calls': 0, 'puts': 0}
        
        # Process each strike
        for _, option in chain_data.iterrows():
            strike = option['strike']
            oi = option.get('open_interest', 0)
            
            # Skip if insufficient OI
            if oi < MIN_OPEN_INTEREST:
                continue
            
            # Get gamma from OPRA or calculate
            gamma = self._get_option_gamma(strike, expiry, option['type'])
            if gamma < MIN_GAMMA:
                continue
            
            # Calculate spot gamma at this price level
            spot_gamma = self._calculate_spot_gamma(
                price_level, strike, gamma, dte
            )
            
            # Dollar gamma exposure
            dollar_gamma = spot_gamma * oi * 100 * price_level
            
            # Apply dealer positioning assumptions
            if option['type'] == 'CALL':
                dealer_gamma = dollar_gamma * DEALER_CALL_POSITION
                call_gamma += dealer_gamma
            else:
                dealer_gamma = dollar_gamma * DEALER_PUT_POSITION
                put_gamma += dealer_gamma
            
            total_gamma += dealer_gamma
        
        return {
            'total': total_gamma,
            'calls': call_gamma,
            'puts': put_gamma
        }
    
    def _calculate_spot_gamma(self, 
                            spot: float, 
                            strike: float,
                            atm_gamma: float,
                            tte: float) -> float:
        """
        Calculate gamma at different spot levels.
        Uses approximation that gamma peaks at strike.
        """
        # Simplified gamma profile - peaks at strike
        moneyness = spot / strike
        
        # Gamma decay away from strike
        # This is a simplification - actual calculation would use BS model
        gamma_decay = np.exp(-2 * (np.log(moneyness))**2 / (0.2**2 * tte))
        
        return atm_gamma * gamma_decay
    
    def _find_zero_gamma_level(self, 
                              prices: np.ndarray,
                              gamma: np.ndarray) -> Optional[float]:
        """Find price level where gamma crosses zero."""
        # Find zero crossings
        zero_crossings = np.where(np.diff(np.sign(gamma)))[0]
        
        if len(zero_crossings) == 0:
            return None
        
        # Find crossing closest to current spot
        spot_idx = len(prices) // 2
        closest_idx = zero_crossings[np.argmin(np.abs(zero_crossings - spot_idx))]
        
        # Interpolate exact crossing point
        if closest_idx < len(prices) - 1:
            x1, x2 = prices[closest_idx], prices[closest_idx + 1]
            y1, y2 = gamma[closest_idx], gamma[closest_idx + 1]
            
            # Linear interpolation
            zero_level = x1 - y1 * (x2 - x1) / (y2 - y1)
            return zero_level
        
        return None
    
    def _determine_regime(self, 
                        current_gex: float,
                        flip_level: Optional[float],
                        spot: float) -> GEXRegime:
        """Determine market regime based on GEX."""
        if current_gex > HIGH_GEX_THRESHOLD:
            return GEXRegime.HIGH_POSITIVE
        elif current_gex > VOLATILITY_SUPPRESSION_LEVEL:
            return GEXRegime.MODERATE_POSITIVE
        elif current_gex < -VOLATILITY_SUPPRESSION_LEVEL:
            return GEXRegime.EXTREME_NEGATIVE
        elif current_gex < 0:
            return GEXRegime.NEGATIVE
        elif flip_level and abs(spot - flip_level) < FLIP_PROXIMITY_ALERT:
            return GEXRegime.NEAR_FLIP
        else:
            return GEXRegime.MODERATE_POSITIVE
    
    def _calculate_expected_flow(self, 
                               spot: float,
                               prices: np.ndarray,
                               gamma: np.ndarray) -> HedgingFlow:
        """Calculate expected dealer hedging flow."""
        # Find current index
        current_idx = np.argmin(np.abs(prices - spot))
        
        # Calculate gamma gradient
        if current_idx > 0 and current_idx < len(prices) - 1:
            gamma_slope = (gamma[current_idx + 1] - gamma[current_idx - 1]) / (prices[current_idx + 1] - prices[current_idx - 1])
        else:
            gamma_slope = 0
        
        # Negative gamma slope means dealers buy on rally, sell on decline
        # Positive gamma slope means opposite
        if gamma_slope < -1e8:
            return HedgingFlow.STRONG_BUYING
        elif gamma_slope < -5e7:
            return HedgingFlow.MODERATE_BUYING
        elif gamma_slope > 1e8:
            return HedgingFlow.STRONG_SELLING
        elif gamma_slope > 5e7:
            return HedgingFlow.MODERATE_SELLING
        else:
            return HedgingFlow.NEUTRAL
    
    def _calculate_metrics(self, profile: GEXProfile) -> GEXMetrics:
        """Calculate comprehensive GEX metrics."""
        # Get historical data
        hist_df = pd.DataFrame(list(self.historical_gex))
        if len(hist_df) == 0:
            hist_df = pd.DataFrame({'gex': [profile.current_gex]})
        
        # Calculate metrics
        current_gex = profile.current_gex
        prev_close_gex = self._get_previous_close_gex()
        
        # Intraday stats
        today_data = hist_df[pd.to_datetime(hist_df['timestamp']).dt.date == date.today()] if 'timestamp' in hist_df else hist_df
        intraday_high = today_data['gex'].max() if len(today_data) > 0 else current_gex
        intraday_low = today_data['gex'].min() if len(today_data) > 0 else current_gex
        
        # Moving averages
        avg_5d = hist_df['gex'].tail(5 * INTRADAY_POINTS).mean() if len(hist_df) > 5 else current_gex
        avg_20d = hist_df['gex'].tail(20 * INTRADAY_POINTS).mean() if len(hist_df) > 20 else current_gex
        
        # Expected volatility based on GEX
        expected_vol = self._estimate_volatility_from_gex(current_gex)
        
        # Find major gamma levels
        major_levels = [level['price'] for level in self.get_major_gamma_levels(0.05)]
        
        # Distance to flip
        distance_to_flip = None
        if profile.zero_gamma_level:
            distance_to_flip = profile.spot_price - profile.zero_gamma_level
        
        # Expected hedging flow
        spot_move_1pct = profile.spot_price * 0.01
        flow_1pct = self._calculate_flow_for_move(profile, spot_move_1pct)
        
        metrics = GEXMetrics(
            current_gex=current_gex,
            prev_close_gex=prev_close_gex,
            gex_change=current_gex - prev_close_gex,
            gex_change_pct=((current_gex - prev_close_gex) / abs(prev_close_gex) * 100) if prev_close_gex != 0 else 0,
            intraday_high=intraday_high,
            intraday_low=intraday_low,
            avg_gex_5d=avg_5d,
            avg_gex_20d=avg_20d,
            expected_volatility=expected_vol,
            volatility_regime='suppressed' if current_gex > VOLATILITY_SUPPRESSION_LEVEL else 'elevated',
            nearest_flip=profile.zero_gamma_level,
            distance_to_flip=distance_to_flip,
            major_gamma_levels=major_levels[:5],  # Top 5 levels
            expected_hedging_flow=flow_1pct,
            flow_direction=profile.expected_flow
        )
        
        return metrics
    
    def _estimate_volatility_from_gex(self, gex: float) -> float:
        """Estimate expected volatility based on GEX level."""
        # Empirical relationship - negative GEX increases vol
        # This is simplified - would use historical calibration
        base_vol = 0.15  # 15% base volatility
        
        if gex > 0:
            # Positive GEX suppresses volatility
            suppression_factor = min(gex / (2 * VOLATILITY_SUPPRESSION_LEVEL), 0.5)
            return base_vol * (1 - suppression_factor)
        else:
            # Negative GEX amplifies volatility
            amplification_factor = min(abs(gex) / VOLATILITY_SUPPRESSION_LEVEL, 1.0)
            return base_vol * (1 + amplification_factor)
    
    def _calculate_flow_for_move(self, 
                               profile: GEXProfile,
                               move_size: float) -> float:
        """Calculate expected dealer flow for given move."""
        spot_idx = np.argmin(np.abs(profile.price_levels - profile.spot_price))
        new_spot = profile.spot_price + move_size
        new_idx = np.argmin(np.abs(profile.price_levels - new_spot))
        
        if new_idx != spot_idx and 0 <= new_idx < len(profile.gamma_exposure):
            # Change in gamma exposure
            gamma_change = profile.gamma_exposure[new_idx] - profile.gamma_exposure[spot_idx]
            # Dealers hedge opposite direction
            return -gamma_change
        
        return 0.0
    
    # ==========================================================================
    # PRIVATE METHODS - DATA ACCESS
    # ==========================================================================
    
    def _get_spot_price(self) -> float:
        """Get current SPY spot price."""
        try:
            # Get from option chain manager
            spot = self.option_chain_mgr.get_underlying_price()
            if spot and spot > 0:
                return spot
            
            # Fallback to a default or last known
            if self.current_profile:
                return self.current_profile.spot_price
            
            return 440.0  # Default
            
        except Exception as e:
            self.logger.warning(f"Error getting spot price: {e}")
            return 440.0
    
    def _get_active_expiries(self) -> List[date]:
        """Get list of active expiries to include in GEX calculation."""
        try:
            # Get from option chain manager
            all_expiries = self.option_chain_mgr.get_expiry_dates()
            
            # Filter to reasonable range (e.g., within 60 days)
            cutoff = date.today() + timedelta(days=60)
            active = [exp for exp in all_expiries if exp <= cutoff]
            
            return sorted(active)[:10]  # Max 10 expiries
            
        except Exception as e:
            self.logger.warning(f"Error getting expiries: {e}")
            # Return some defaults
            today = date.today()
            return [
                today + timedelta(days=1),
                today + timedelta(days=7),
                today + timedelta(days=14),
                today + timedelta(days=30)
            ]
    
    def _get_option_chain(self, expiry: date) -> Optional[pd.DataFrame]:
        """Get option chain data for specific expiry."""
        try:
            # Get from option chain manager
            chain = self.option_chain_mgr.get_option_chain(expiry)
            
            if chain is not None and not chain.empty:
                # Ensure required columns
                required_cols = ['strike', 'type', 'open_interest', 'bid', 'ask']
                if all(col in chain.columns for col in required_cols):
                    return chain
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Error getting option chain for {expiry}: {e}")
            return None
    
    def _get_option_gamma(self, 
                        strike: float,
                        expiry: date,
                        option_type: str) -> float:
        """Get gamma for specific option from OPRA or calculate."""
        # Check cache first
        cache_key = f"{strike}_{expiry}_{option_type}"
        if cache_key in self._gamma_cache:
            return self._gamma_cache[cache_key]
        
        try:
            # Try to get from OPRA handler
            symbol = self._construct_option_symbol(strike, expiry, option_type)
            if symbol in self.opra_handler.validated_greeks:
                gamma = self.opra_handler.validated_greeks[symbol].gamma
                self._gamma_cache[cache_key] = gamma
                return gamma
            
            # Fallback to calculation
            # This is simplified - would use proper Greeks calculator
            spot = self._get_spot_price()
            tte = (expiry - date.today()).days / 365.0
            
            if tte > 0:
                # Simplified ATM gamma approximation
                iv = 0.20  # Default IV
                gamma = np.exp(-0.5 * ((spot - strike) / (spot * iv * np.sqrt(tte)))**2) / (spot * iv * np.sqrt(2 * np.pi * tte))
                
                self._gamma_cache[cache_key] = gamma
                return gamma
            
            return 0.0
            
        except Exception as e:
            self.logger.debug(f"Error getting gamma for {strike}/{expiry}: {e}")
            return 0.0
    
    def _construct_option_symbol(self, 
                               strike: float,
                               expiry: date,
                               option_type: str) -> str:
        """Construct option symbol for lookups."""
        # Format: SPY231215C450
        exp_str = expiry.strftime('%y%m%d')
        type_char = 'C' if option_type.upper() == 'CALL' else 'P'
        strike_str = f"{int(strike)}"
        return f"SPY{exp_str}{type_char}{strike_str}"
    
    def _calculate_price_range(self, spot: float) -> np.ndarray:
        """Calculate price range for GEX profile."""
        lower = spot * (1 - SPOT_RANGE_PERCENTAGE)
        upper = spot * (1 + SPOT_RANGE_PERCENTAGE)
        
        return np.arange(lower, upper + SPOT_INCREMENTS, SPOT_INCREMENTS)
    
    def _get_previous_close_gex(self) -> float:
        """Get previous trading day close GEX."""
        if not self.historical_gex:
            return 0.0
        
        # Find last entry from previous day
        yesterday = date.today() - timedelta(days=1)
        
        for entry in reversed(self.historical_gex):
            if entry['timestamp'].date() <= yesterday:
                return entry['gex']
        
        return 0.0
    
    def _calculate_weighted_gamma(self, 
                                prices: np.ndarray,
                                gamma: np.ndarray,
                                spot: float) -> float:
        """Calculate volume-weighted average gamma."""
        weights = np.exp(-0.5 * ((prices - spot) / (0.05 * spot))**2)
        weights /= np.sum(weights)
        
        return np.sum(gamma * weights)
    
    def _calculate_concentration(self, gamma: np.ndarray) -> float:
        """Calculate gamma concentration (Herfindahl index)."""
        total = np.sum(np.abs(gamma))
        if total == 0:
            return 0.0
        
        shares = np.abs(gamma) / total
        hhi = np.sum(shares**2)
        
        return hhi
    
    def _calculate_expiry_exposure(self, expiry: date) -> Dict[str, float]:
        """Calculate dealer exposure for specific expiry."""
        chain = self._get_option_chain(expiry)
        if chain is None:
            return {'delta': 0, 'gamma': 0}
        
        total_delta = 0.0
        total_gamma = 0.0
        
        for _, opt in chain.iterrows():
            oi = opt.get('open_interest', 0)
            if oi < MIN_OPEN_INTEREST:
                continue
            
            # Get Greeks
            symbol = self._construct_option_symbol(opt['strike'], expiry, opt['type'])
            if symbol in self.opra_handler.validated_greeks:
                greeks = self.opra_handler.validated_greeks[symbol]
                
                # Apply dealer positioning
                if opt['type'] == 'CALL':
                    total_delta += greeks.delta * oi * 100 * DEALER_CALL_POSITION
                    total_gamma += greeks.gamma * oi * 100 * DEALER_CALL_POSITION
                else:
                    total_delta += greeks.delta * oi * 100 * DEALER_PUT_POSITION
                    total_gamma += greeks.gamma * oi * 100 * DEALER_PUT_POSITION
        
        return {'delta': total_delta, 'gamma': total_gamma}
    
    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================
    
    def _is_cache_valid(self) -> bool:
        """Check if cached profile is still valid."""
        if not self._profile_cache or not self._cache_timestamp:
            return False
        
        age = (datetime.now() - self._cache_timestamp).total_seconds()
        return age < GEX_UPDATE_INTERVAL
    
    def _emit_gex_update(self, profile: GEXProfile) -> None:
        """Emit GEX update event."""
        event = Event(
            type=EventType.ANALYTICS,
            data={
                'type': 'gex_update',
                'timestamp': profile.timestamp.isoformat(),
                'spot': profile.spot_price,
                'current_gex': profile.current_gex,
                'flip_level': profile.zero_gamma_level,
                'regime': profile.regime.value,
                'expected_flow': profile.expected_flow.value
            }
        )
        self.event_manager.emit(event)
    
    # ==========================================================================
    # PUBLIC METHODS - MONITORING
    # ==========================================================================
    
    def start_monitoring(self) -> None:
        """Start real-time GEX monitoring."""
        if self._running:
            self.logger.warning("GEX monitoring already running")
            return
        
        self._running = True
        self._update_thread = threading.Thread(
            target=self._monitoring_loop,
            name="GEX-Monitor",
            daemon=True
        )
        self._update_thread.start()
        self.logger.info("GEX monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop GEX monitoring."""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=5)
        self.logger.info("GEX monitoring stopped")
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        last_full_update = time.time()
        last_flip_check = time.time()
        
        while self._running:
            try:
                current_time = time.time()
                
                # Full GEX update
                if current_time - last_full_update >= GEX_UPDATE_INTERVAL:
                    self.calculate_gex_profile()
                    last_full_update = current_time
                
                # Flip point check
                elif current_time - last_flip_check >= FLIP_CHECK_INTERVAL:
                    self._check_flip_proximity()
                    last_flip_check = current_time
                
                # Sleep briefly
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)
    
    def _check_flip_proximity(self) -> None:
        """Check if approaching gamma flip point."""
        if not self.current_profile or not self.current_profile.zero_gamma_level:
            return
        
        spot = self._get_spot_price()
        flip = self.current_profile.zero_gamma_level
        distance = abs(spot - flip)
        
        if distance < FLIP_PROXIMITY_ALERT:
            self.logger.warning(f"Approaching gamma flip: Spot ${spot:.2f}, Flip ${flip:.2f}, Distance ${distance:.2f}")
            
            # Emit alert event
            event = Event(
                type=EventType.RISK_ALERT,
                data={
                    'type': 'gamma_flip_proximity',
                    'spot': spot,
                    'flip_level': flip,
                    'distance': distance,
                    'direction': 'above' if spot > flip else 'below'
                }
            )
            self.event_manager.emit(event)
    
    # ==========================================================================
    # PUBLIC METHODS - VISUALIZATION
    # ==========================================================================
    
    def plot_gex_profile(self, 
                       save_path: Optional[str] = None) -> None:
        """Plot current GEX profile."""
        if not self.current_profile:
            self.logger.warning("No GEX profile to plot")
            return
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        # Plot 1: GEX Profile
        ax1.plot(self.current_profile.price_levels, 
                self.current_profile.gamma_exposure / 1e9,
                'b-', linewidth=2, label='Total GEX')
        ax1.plot(self.current_profile.price_levels,
                self.current_profile.call_gamma / 1e9,
                'g--', alpha=0.7, label='Call Gamma')
        ax1.plot(self.current_profile.price_levels,
                self.current_profile.put_gamma / 1e9,
                'r--', alpha=0.7, label='Put Gamma')
        
        # Mark current spot
        ax1.axvline(self.current_profile.spot_price, color='black', 
                   linestyle=':', alpha=0.7, label='Current Spot')
        
        # Mark gamma flip
        if self.current_profile.zero_gamma_level:
            ax1.axvline(self.current_profile.zero_gamma_level, color='orange',
                       linestyle='--', alpha=0.7, label='Gamma Flip')
        
        # Zero line
        ax1.axhline(0, color='gray', linestyle='-', alpha=0.3)
        
        ax1.set_xlabel('SPY Price ($)')
        ax1.set_ylabel('Gamma Exposure ($B)')
        ax1.set_title(f'Gamma Exposure Profile - {self.current_profile.timestamp.strftime("%Y-%m-%d %H:%M")}')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: Intraday GEX
        intraday_df = self.get_intraday_profile()
        if not intraday_df.empty:
            ax2.plot(pd.to_datetime(intraday_df['timestamp']), 
                    intraday_df['gex'] / 1e9, 'b-', linewidth=2)
            ax2.fill_between(pd.to_datetime(intraday_df['timestamp']),
                           intraday_df['gex'] / 1e9, 0, alpha=0.3)
            
            ax2.set_xlabel('Time')
            ax2.set_ylabel('GEX ($B)')
            ax2.set_title('Intraday Gamma Exposure')
            ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for GEX."""
        if not self.current_profile or not self.current_metrics:
            return {}
        
        return {
            'current_gex': f"${self.current_metrics.current_gex/1e9:.2f}B",
            'gex_change': f"${self.current_metrics.gex_change/1e9:.2f}B",
            'gex_change_pct': f"{self.current_metrics.gex_change_pct:+.1f}%",
            'regime': self.current_profile.regime.value,
            'flip_level': f"${self.current_profile.zero_gamma_level:.2f}" if self.current_profile.zero_gamma_level else "N/A",
            'distance_to_flip': f"${abs(self.current_metrics.distance_to_flip):.2f}" if self.current_metrics.distance_to_flip else "N/A",
            'expected_volatility': f"{self.current_metrics.expected_volatility:.1%}",
            'expected_flow': self.current_profile.expected_flow.value,
            'major_levels': [f"${level:.2f}" for level in self.current_metrics.major_gamma_levels],
            'calculation_time': f"{np.mean(list(self.calculation_times)):.3f}s" if self.calculation_times else "N/A"
        }

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_gex_calculator(
    opra_handler: Optional[OPRAGreeksHandler] = None,
    option_chain_mgr: Optional[OptionChainManager] = None
) -> GammaExposureCalculator:
    """
    Factory function to create GEX calculator.
    
    Args:
        opra_handler: OPRA Greeks handler
        option_chain_mgr: Option chain manager
        
    Returns:
        Configured GammaExposureCalculator instance
    """
    return GammaExposureCalculator(opra_handler, option_chain_mgr)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

# Module-level initialization code
pass

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Module testing code
    print("=" * 80)
    print("SPYDER N09 - Gamma Exposure Calculator Test")
    print("=" * 80)
    
    # Create calculator
    gex_calc = GammaExposureCalculator()
    
    # Calculate GEX profile
    print("\n1. Calculating GEX Profile...")
    profile = gex_calc.calculate_gex_profile()
    
    print(f"\nCurrent GEX: ${profile.current_gex/1e9:.2f}B")
    print(f"Spot Price: ${profile.spot_price:.2f}")
    print(f"Gamma Flip: ${profile.zero_gamma_level:.2f}" if profile.zero_gamma_level else "Gamma Flip: None")
    print(f"Regime: {profile.regime.value}")
    print(f"Expected Flow: {profile.expected_flow.value}")
    
    # Get major gamma levels
    print("\n2. Major Gamma Levels:")
    major_levels = gex_calc.get_major_gamma_levels()
    for level in major_levels[:5]:
        print(f"   ${level['price']:.2f}: {level['gamma']/1e9:.2f}B gamma ({level['type']})")
    
    # Generate trading signals
    print("\n3. Trading Signals:")
    signals = gex_calc.generate_trading_signals()
    for signal in signals:
        print(f"\n   Signal: {signal['signal'].value}")
        print(f"   Strength: {signal['strength']:.1%}")
        print(f"   Action: {signal['action']}")
        print(f"   Reason: {signal['reason']}")
    
    # Get summary stats
    print("\n4. Summary Statistics:")
    stats = gex_calc.get_summary_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Plot profile
    print("\n5. Plotting GEX Profile...")
    gex_calc.plot_gex_profile()
    
    print("\n" + "=" * 80)
    print("GEX Calculator test completed successfully!")
